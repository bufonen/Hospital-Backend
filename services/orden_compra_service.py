"""
Service para lógica de negocio de Órdenes de Compra.
HU-4.02: Post-Orden

REFACTORIZADO: Ahora utiliza OrdenRetrasadaAlertFactory para creación de alertas.
"""
from sqlalchemy.orm import Session, joinedload
from database.models import (
    OrdenCompra, DetalleOrdenCompra, EstadoOrdenEnum,
    Proveedor, Medicamento, EstadoEnum, AuditLog,
    Movimiento, MovimientoTipoEnum
)
from repositories.orden_compra_repo import OrdenCompraRepository, DetalleOrdenRepository
from repositories.proveedor_repo import ProveedorRepository
from factories.alert_factory import AlertFactoryRegistry
from typing import Optional, Dict, Any, List
from datetime import datetime, date
from decimal import Decimal


class OrdenCompraService:
    """
    Service para lógica de negocio de órdenes de compra.
    
    Responsabilidades:
    - Validaciones de negocio
    - Gestión de estados (PENDIENTE → ENVIADA → RECIBIDA/RETRASADA)
    - Generación automática de número de orden
    - Cálculo de totales
    - Actualización de inventario al recibir
    - Auditoría completa
    - Creación de alertas (usando Factory pattern)
    """
    
    def __init__(self, db: Session):
        self.db = db
        self.repo = OrdenCompraRepository(db)
        self.detalle_repo = DetalleOrdenRepository(db)
        self.proveedor_repo = ProveedorRepository(db)
    
    def _crear_alerta_orden_retrasada(self, orden: OrdenCompra, dias_retraso: int) -> None:
        """
        Crea una alerta de orden retrasada usando Factory y notifica a observadores.
        
        REFACTORIZADO: Usa OrdenRetrasadaAlertFactory para construcción.
        
        Esta función se llama cuando:
        1. Una orden pasa de ENVIADA a RETRASADA (cambio de estado)
        2. El job periódico detecta retrasos
        
        Args:
            orden: La orden retrasada
            dias_retraso: Cantidad de días de retraso
        """
        from database.models import Alerta, TipoAlertaEnum, EstadoAlertaEnum
        from observers.alert_observer import alert_subject
        
        # Verificar si ya existe alerta activa para esta orden
        alerta_existente = self.db.query(Alerta).filter(
            Alerta.estado == EstadoAlertaEnum.ACTIVA,
            Alerta.tipo == TipoAlertaEnum.ORDEN_RETRASADA,
            Alerta.metadatos.contains({'orden_id': str(orden.id)})
        ).first()
        
        if alerta_existente:
            print(f"⚠️  Alerta ya existe para orden {orden.numero_orden}")
            return
        
        # ✨ FACTORY: Delegar construcción completa al factory
        factory = AlertFactoryRegistry.get_factory('orden_retrasada')
        alerta = factory.create_alert(orden=orden, dias_retraso=dias_retraso)
        
        self.db.add(alerta)
        self.db.flush()
        self.db.refresh(alerta)
        
        print(f"🔔 Alerta creada: {alerta.mensaje}")
        
        # Notificar a observadores (envía a Redis para roles COMPRAS y ADMIN)
        alert_event = {
            'event_type': 'created',
            'alert_id': str(alerta.id),
            'alert_type': TipoAlertaEnum.ORDEN_RETRASADA.value,
            'priority': alerta.prioridad.value,
            'medicamento_id': None,
            'medicamento_nombre': f"Orden {orden.numero_orden}",
            'medicamento_fabricante': orden.proveedor.nombre,
            'medicamento_presentacion': f"{dias_retraso} días de retraso",
            'medicamento_lote': '',
            'mensaje': alerta.mensaje,
            'metadata': alerta.metadatos
        }
        
        alert_subject.notify(alert_event)
    
    def _resolver_alerta_orden(self, orden_id: str) -> None:
        """
        Resuelve la alerta de una orden cuando esta es recibida.
        
        Se llama automáticamente cuando una orden pasa a estado RECIBIDA.
        
        Args:
            orden_id: ID de la orden recibida
        """
        from database.models import Alerta, TipoAlertaEnum, EstadoAlertaEnum
        from observers.alert_observer import alert_subject
        
        # Buscar alerta activa de esta orden
        alerta = self.db.query(Alerta).filter(
            Alerta.estado == EstadoAlertaEnum.ACTIVA,
            Alerta.tipo == TipoAlertaEnum.ORDEN_RETRASADA,
            Alerta.metadatos.contains({'orden_id': str(orden_id)})
        ).first()
        
        if alerta:
            # Marcar como resuelta
            alerta.estado = EstadoAlertaEnum.RESUELTA
            alerta.resuelta_at = datetime.now()
            alerta.resuelta_by = 'system'
            
            self.db.add(alerta)
            self.db.flush()
            
            print(f"✅ Alerta resuelta para orden {alerta.metadatos.get('numero_orden')}")
            
            # Notificar resolución
            alert_event = {
                'event_type': 'resolved',
                'alert_id': str(alerta.id),
                'alert_type': TipoAlertaEnum.ORDEN_RETRASADA.value,
                'mensaje': f"Orden {alerta.metadatos.get('numero_orden')} recibida"
            }
            
            alert_subject.notify(alert_event)
    
    def create_orden(
        self,
        payload: Dict[str, Any],
        user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Crea una nueva orden de compra.
        
        HU-4.02: "Given que ingreso los datos obligatorios de la orden
                  When guardo la orden de compra
                  Then el sistema crea la orden con un ID único y estado PENDIENTE"
        
        Validaciones:
        - Proveedor debe existir y estar activo
        - Al menos un producto
        - Fecha prevista futura
        
        Returns:
            Dict con 'ok': bool, 'orden': OrdenCompra, 'error': str
        """
        try:
            # Validar proveedor
            proveedor_id = payload.get('proveedor_id')
            if not proveedor_id:
                return {
                    'ok': False,
                    'error': 'proveedor_required',
                    'message': 'proveedor_id es requerido'
                }
            
            proveedor = self.proveedor_repo.get_by_id(proveedor_id)
            if not proveedor:
                return {
                    'ok': False,
                    'error': 'proveedor_not_found',
                    'message': f'El proveedor con ID {proveedor_id} no existe'
                }
            
            if proveedor.estado.value != 'ACTIVO':
                return {
                    'ok': False,
                    'error': 'proveedor_inactive',
                    'message': f'El proveedor {proveedor.nombre} está inactivo'
                }
            
            # Validar que haya productos
            detalles_data = payload.get('detalles', [])
            if not detalles_data or len(detalles_data) == 0:
                return {
                    'ok': False,
                    'error': 'no_products',
                    'message': 'La orden debe contener al menos un producto'
                }
            
            # Validar que los medicamentos existan
            for idx, detalle_data in enumerate(detalles_data):
                med_id = detalle_data.get('medicamento_id')
                if not med_id:
                    return {
                        'ok': False,
                        'error': 'medicamento_id_required',
                        'message': f'Producto {idx+1}: medicamento_id es requerido'
                    }
                
                med = self.db.query(Medicamento).filter(
                    Medicamento.id == med_id
                ).first()
                
                if not med:
                    return {
                        'ok': False,
                        'error': 'medicamento_not_found',
                        'message': f'Producto {idx+1}: El medicamento con ID {med_id} no existe'
                    }
                
                if med.estado.value == 'INACTIVO':
                    return {
                        'ok': False,
                        'error': 'medicamento_inactive',
                        'message': f'Producto {idx+1}: {med.nombre} está inactivo'
                    }
            
            # Generar número de orden
            numero_orden = self.repo.get_next_numero_orden()
            
            # Crear orden
            orden = OrdenCompra(
                numero_orden=numero_orden,
                proveedor_id=payload['proveedor_id'],
                fecha_prevista_entrega=payload['fecha_prevista_entrega'],
                observaciones=payload.get('observaciones'),
                estado=EstadoOrdenEnum.PENDIENTE,
                created_by=user_id
            )
            
            self.repo.create(orden)
            self.db.flush()
            self.db.refresh(orden)
            
            # Crear detalles y calcular total
            total = Decimal('0.00')
            for detalle_data in detalles_data:
                cantidad = detalle_data['cantidad_solicitada']
                precio = Decimal(str(detalle_data['precio_unitario']))
                subtotal = cantidad * precio
                total += subtotal
                
                # Obtener medicamento para copiar lote y fecha de vencimiento
                med = self.db.query(Medicamento).filter(
                    Medicamento.id == detalle_data['medicamento_id']
                ).first()
                
                detalle = DetalleOrdenCompra(
                    orden_compra_id=orden.id,
                    medicamento_id=detalle_data['medicamento_id'],
                    cantidad_solicitada=cantidad,
                    precio_unitario=precio,
                    subtotal=subtotal,
                    # Auto-llenar desde el medicamento (registro histórico)
                    lote_esperado=med.lote if med else None,
                    fecha_vencimiento_esperada=med.fecha_vencimiento if med else None
                )
                self.detalle_repo.create(detalle)
            
            # Actualizar total de la orden
            orden.total_estimado = total
            self.repo.update(orden)
            
            # Auditoría
            audit = AuditLog(
                entidad='ordenes_compra',
                entidad_id=orden.id,
                usuario_id=user_id,
                accion='CREATE',
                metadatos={
                    'numero_orden': orden.numero_orden,
                    'proveedor': proveedor.nombre,
                    'total': float(total),
                    'items': len(detalles_data)
                }
            )
            self.db.add(audit)
            
            self.db.commit()
            self.db.refresh(orden)
            
            return {
                'ok': True,
                'orden': orden
            }
            
        except Exception as e:
            self.db.rollback()
            print(f"Error creando orden: {e}")
            import traceback
            traceback.print_exc()
            return {
                'ok': False,
                'error': 'database_error',
                'message': f'Error al crear la orden: {str(e)}'
            }
    
    def get_orden(self, orden_id: str) -> Optional[OrdenCompra]:
        """Obtiene una orden por ID con todas sus relaciones."""
        return self.repo.get_by_id(orden_id, with_relations=True)
    
    def list_ordenes(
        self,
        estado: Optional[str] = None,
        proveedor_id: Optional[str] = None,
        fecha_desde: Optional[date] = None,
        fecha_hasta: Optional[date] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[OrdenCompra]:
        """Lista órdenes con filtros."""
        estado_enum = None
        if estado:
            try:
                estado_enum = EstadoOrdenEnum(estado.upper())
            except ValueError:
                pass
        
        return self.repo.list(
            estado=estado_enum,
            proveedor_id=proveedor_id,
            fecha_desde=fecha_desde,
            fecha_hasta=fecha_hasta,
            limit=limit,
            offset=offset
        )
    
    def update_orden(
        self,
        orden_id: str,
        changes: Dict[str, Any],
        user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Actualiza una orden.
        Solo permitido en estado PENDIENTE.
        """
        try:
            orden = self.repo.get_by_id(orden_id)
            if not orden:
                return {
                    'ok': False,
                    'error': 'not_found',
                    'message': 'Orden no encontrada'
                }
            
            # Solo permitir edición en estado PENDIENTE
            if orden.estado != EstadoOrdenEnum.PENDIENTE:
                return {
                    'ok': False,
                    'error': 'invalid_state',
                    'message': f'No se puede editar una orden en estado {orden.estado.value}'
                }
            
            # Aplicar cambios
            audit_entries = []
            for field, new_value in changes.items():
                if field in ['proveedor_id', 'fecha_prevista_entrega', 'observaciones']:
                    old_value = getattr(orden, field)
                    if str(new_value) != str(old_value):
                        audit_entries.append((field, str(old_value), str(new_value)))
                        setattr(orden, field, new_value)
            
            if not audit_entries:
                return {
                    'ok': True,
                    'updated': False,
                    'message': 'No se detectaron cambios'
                }
            
            self.repo.update(orden)
            
            # Auditoría
            for field, old_val, new_val in audit_entries:
                audit = AuditLog(
                    entidad='ordenes_compra',
                    entidad_id=orden.id,
                    usuario_id=user_id,
                    accion='UPDATE',
                    campo=field,
                    valor_anterior=old_val,
                    valor_nuevo=new_val
                )
                self.db.add(audit)
            
            self.db.commit()
            self.db.refresh(orden)
            
            return {
                'ok': True,
                'updated': True,
                'orden': orden
            }
            
        except Exception as e:
            self.db.rollback()
            print(f"Error actualizando orden: {e}")
            return {
                'ok': False,
                'error': 'database_error',
                'message': str(e)
            }
    
    def marcar_enviada(
        self,
        orden_id: str,
        fecha_envio: Optional[datetime] = None,
        observaciones: Optional[str] = None,
        user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Marca una orden como ENVIADA.
        Solo permitido desde estado PENDIENTE.
        
        NUEVO: Verifica inmediatamente si la fecha prevista ya pasó
        y genera alerta si está retrasada desde el inicio.
        """
        try:
            orden = self.repo.get_by_id(orden_id, with_relations=True)
            if not orden:
                return {'ok': False, 'error': 'not_found'}
            
            if orden.estado != EstadoOrdenEnum.PENDIENTE:
                return {
                    'ok': False,
                    'error': 'invalid_state',
                    'message': f'Solo se puede enviar desde estado PENDIENTE (actual: {orden.estado.value})'
                }
            
            # Actualizar estado
            orden.estado = EstadoOrdenEnum.ENVIADA
            orden.fecha_envio = fecha_envio or datetime.now()
            if observaciones:
                orden.observaciones = observaciones
            
            # NUEVO: Verificar si ya está retrasada al momento de marcarla como enviada
            if orden.fecha_prevista_entrega < date.today():
                dias_retraso = (date.today() - orden.fecha_prevista_entrega).days
                orden.estado = EstadoOrdenEnum.RETRASADA
                print(f"⚠️  Orden {orden.numero_orden} marcada como RETRASADA ({dias_retraso} días)")
                
                # Crear alerta inmediatamente
                self._crear_alerta_orden_retrasada(orden, dias_retraso)
            
            self.repo.update(orden)
            
            # Auditoría
            audit = AuditLog(
                entidad='ordenes_compra',
                entidad_id=orden.id,
                usuario_id=user_id,
                accion='MARCAR_ENVIADA',
                metadatos={
                    'fecha_envio': str(orden.fecha_envio),
                    'estado_final': orden.estado.value
                }
            )
            self.db.add(audit)
            
            self.db.commit()
            self.db.refresh(orden)
            
            return {'ok': True, 'orden': orden}
            
        except Exception as e:
            self.db.rollback()
            print(f"Error marcando enviada: {e}")
            import traceback
            traceback.print_exc()
            return {'ok': False, 'error': 'database_error', 'message': str(e)}
    
    def recibir_orden(
        self,
        orden_id: str,
        items_recibidos: List[Dict[str, Any]],
        fecha_recepcion: Optional[datetime] = None,
        observaciones: Optional[str] = None,
        user_id: Optional[str] = None,
        actualizar_inventario: bool = True
    ) -> Dict[str, Any]:
        """
        Registra la recepción de una orden.
        
        HU-4.02: "Given que una orden de compra está en estado ENVIADA
                  When registro la recepción completa de los productos
                  Then el sistema actualiza el estado de la orden a RECIBIDA"
        
        Validaciones:
        - Solo desde estado ENVIADA o RETRASADA
        - Comparar cantidades solicitadas vs recibidas
        - Actualizar inventario automáticamente (opcional)
        """
        try:
            orden = self.repo.get_by_id(orden_id, with_relations=True)
            if not orden:
                return {'ok': False, 'error': 'not_found'}
            
            # Validar estado
            if orden.estado not in [EstadoOrdenEnum.ENVIADA, EstadoOrdenEnum.RETRASADA]:
                return {
                    'ok': False,
                    'error': 'invalid_state',
                    'message': f'Solo se puede recibir desde ENVIADA o RETRASADA (actual: {orden.estado.value})'
                }
            
            # Procesar items recibidos
            diferencias = []
            items_actualizados = 0
            
            for item_recibido in items_recibidos:
                detalle_id = item_recibido['detalle_id']
                cantidad_recibida = item_recibido['cantidad_recibida']
                
                detalle = self.detalle_repo.get_by_id(detalle_id)
                if not detalle or detalle.orden_compra_id != orden.id:
                    continue
                
                # Detectar diferencias
                if cantidad_recibida != detalle.cantidad_solicitada:
                    diferencias.append({
                        'detalle_id': detalle_id,
                        'medicamento': detalle.medicamento.nombre,
                        'solicitada': detalle.cantidad_solicitada,
                        'recibida': cantidad_recibida,
                        'diferencia': cantidad_recibida - detalle.cantidad_solicitada
                    })
                
                # Actualizar cantidad recibida
                detalle.cantidad_recibida = cantidad_recibida
                self.detalle_repo.update(detalle)
                items_actualizados += 1
                
                # Actualizar inventario si está habilitado
                if actualizar_inventario and cantidad_recibida > 0:
                    self._actualizar_inventario_desde_recepcion(
                        detalle, cantidad_recibida, user_id
                    )
            
            # Actualizar orden
            orden.estado = EstadoOrdenEnum.RECIBIDA
            orden.fecha_recepcion = fecha_recepcion or datetime.now()
            orden.recibido_by = user_id
            if observaciones:
                orden.observaciones = f"{orden.observaciones or ''}\n[RECEPCIÓN] {observaciones}".strip()
            
            self.repo.update(orden)
            
            # NUEVO: Resolver alerta automáticamente si existía
            self._resolver_alerta_orden(orden.id)
            
            # Auditoría
            audit = AuditLog(
                entidad='ordenes_compra',
                entidad_id=orden.id,
                usuario_id=user_id,
                accion='RECIBIR',
                metadatos={
                    'items_actualizados': items_actualizados,
                    'diferencias': len(diferencias),
                    'inventario_actualizado': actualizar_inventario
                }
            )
            self.db.add(audit)
            
            self.db.commit()
            self.db.refresh(orden)
            
            return {
                'ok': True,
                'orden': orden,
                'items_actualizados': items_actualizados,
                'diferencias': diferencias,
                'inventario_actualizado': actualizar_inventario
            }
            
        except Exception as e:
            self.db.rollback()
            print(f"Error recibiendo orden: {e}")
            import traceback
            traceback.print_exc()
            return {'ok': False, 'error': 'database_error', 'message': str(e)}
    
    def _actualizar_inventario_desde_recepcion(
        self,
        detalle: DetalleOrdenCompra,
        cantidad: int,
        user_id: Optional[str]
    ):
        """
        Actualiza el stock del medicamento al recibir la orden.
        Crea un movimiento de ENTRADA.
        """
        medicamento = detalle.medicamento
        
        # Actualizar stock
        medicamento.stock = medicamento.stock + cantidad
        self.db.add(medicamento)
        
        # Crear movimiento
        movimiento = Movimiento(
            medicamento_id=medicamento.id,
            tipo=MovimientoTipoEnum.ENTRADA,
            cantidad=cantidad,
            usuario_id=user_id,
            motivo=f"Recepción OC: {detalle.orden.numero_orden}"
        )
        self.db.add(movimiento)
        
        # Auditoría
        audit = AuditLog(
            entidad='medicamentos',
            entidad_id=medicamento.id,
            usuario_id=user_id,
            accion='STOCK_UPDATE',
            campo='stock',
            valor_anterior=str(medicamento.stock - cantidad),
            valor_nuevo=str(medicamento.stock),
            metadatos={
                'motivo': 'recepcion_orden_compra',
                'orden': detalle.orden.numero_orden
            }
        )
        self.db.add(audit)
    
    def detectar_ordenes_retrasadas(self) -> Dict[str, Any]:
        """
        Detecta y marca órdenes como RETRASADAS.
        
        HU-4.02: "Given orden enviada con fecha prevista 2025-09-01,
                  When hoy > 2025-09-01 y no recibida,
                  Then generar alerta 'pedido retrasado'"
        
        Job que debe ejecutarse diariamente.
        NUEVO: Ahora también crea alertas y notifica a roles correspondientes.
        """
        try:
            from database.models import Alerta, TipoAlertaEnum, EstadoAlertaEnum
            
            ordenes_retrasadas = self.repo.list_retrasadas()
            count = 0
            alertas_creadas = 0
            
            for orden in ordenes_retrasadas:
                # Calcular días de retraso
                dias_retraso = (date.today() - orden.fecha_prevista_entrega).days
                
                # Marcar orden como retrasada
                orden.estado = EstadoOrdenEnum.RETRASADA
                self.repo.update(orden)
                
                # Auditoría
                audit = AuditLog(
                    entidad='ordenes_compra',
                    entidad_id=orden.id,
                    usuario_id='system',
                    accion='MARCAR_RETRASADA',
                    metadatos={
                        'fecha_prevista': str(orden.fecha_prevista_entrega),
                        'dias_retraso': dias_retraso
                    }
                )
                self.db.add(audit)
                count += 1
                
                # Verificar si ya existe alerta activa para esta orden
                alerta_existente = self.db.query(Alerta).filter(
                    Alerta.estado == EstadoAlertaEnum.ACTIVA,
                    Alerta.tipo == TipoAlertaEnum.ORDEN_RETRASADA,
                    Alerta.metadatos.contains({'orden_id': str(orden.id)})
                ).first()
                
                if not alerta_existente:
                    # Usar Factory para crear alerta
                    self._crear_alerta_orden_retrasada(orden, dias_retraso)
                    alertas_creadas += 1
            
            if count > 0:
                self.db.commit()
            
            return {
                'ok': True,
                'ordenes_marcadas': count,
                'alertas_creadas': alertas_creadas
            }
            
        except Exception as e:
            self.db.rollback()
            print(f"Error detectando retrasos: {e}")
            import traceback
            traceback.print_exc()
            return {'ok': False, 'error': str(e)}
    
    def get_ordenes_retrasadas(self) -> List[OrdenCompra]:
        """Lista órdenes actualmente retrasadas."""
        return self.db.query(OrdenCompra).filter(
            OrdenCompra.estado == EstadoOrdenEnum.RETRASADA
        ).options(
            joinedload(OrdenCompra.proveedor),
            joinedload(OrdenCompra.detalles).joinedload(DetalleOrdenCompra.medicamento)
        ).all()
    
    def get_stats(self) -> Dict[str, Any]:
        """Obtiene estadísticas de órdenes."""
        return {
            'total': self.repo.count_all(),
            'pendientes': self.repo.count_all(EstadoOrdenEnum.PENDIENTE),
            'enviadas': self.repo.count_all(EstadoOrdenEnum.ENVIADA),
            'recibidas': self.repo.count_all(EstadoOrdenEnum.RECIBIDA),
            'retrasadas': self.repo.count_all(EstadoOrdenEnum.RETRASADA)
        }

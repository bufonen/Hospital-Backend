"""
Service para gestión de ventas y reportes.
HU-3.01: Registro de Ventas con FIFO/FEFO
HU-3.02: Reportes y Proyecciones de Ventas
"""
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_, desc, asc
from database.models import (
    Venta, DetalleVenta, Medicamento, Movimiento,
    EstadoVentaEnum, MetodoPagoEnum, MovimientoTipoEnum,
    EstadoEnum
)
from typing import Optional, Dict, Any, List, Tuple
from datetime import datetime, date, timedelta
from decimal import Decimal
from collections import defaultdict
import uuid


class VentaService:
    """
    Service para lógica de ventas.
    
    HU-3.01: Registro de ventas con descuento automático FIFO/FEFO
    HU-3.02: Reportes y proyecciones
    """
    
    def __init__(self, db: Session):
        self.db = db
    
    def _generar_numero_venta(self) -> str:
        """Genera número de venta consecutivo: VT-2025-0001"""
        año_actual = datetime.now().year
        
        # Contar ventas del año actual
        count = self.db.query(func.count(Venta.id)).filter(
            func.extract('year', Venta.fecha_venta) == año_actual
        ).scalar() or 0
        
        numero = count + 1
        return f"VT-{año_actual}-{numero:04d}"
    
    def crear_venta(
        self,
        detalles: List[Dict[str, Any]],
        usuario_id: str,
        metodo_pago: Optional[str] = None,
        cliente_nombre: Optional[str] = None,
        cliente_documento: Optional[str] = None,
        observaciones: Optional[str] = None,
        metodo_descuento: str = "FEFO",
        confirmar_pago: bool = False
    ) -> Dict[str, Any]:
        """
        Crea una venta nueva.
        
        HU-3.01: "Given venta completada en POS, When confirmar pago,
                  Then crear registro de venta"
        
        Args:
            detalles: Lista de items con medicamento_id, cantidad, precio_unitario
            usuario_id: ID del usuario que registra
            metodo_pago: Método de pago si se confirma
            confirmar_pago: Si True, confirma automáticamente y descuenta stock
            metodo_descuento: "FIFO" o "FEFO"
        
        Returns:
            Dict con venta creada y desglose si se confirmó
        """
        try:
            # Validar que haya detalles
            if not detalles:
                return {
                    'ok': False,
                    'error': 'validation_error',
                    'message': 'Debe incluir al menos un producto en la venta'
                }
            
            # Validar stock disponible para cada producto
            for item in detalles:
                medicamento_id = item.get('medicamento_id')
                cantidad_solicitada = item.get('cantidad')
                
                # Validar medicamento existe
                medicamento = self.db.query(Medicamento).filter(
                    Medicamento.id == medicamento_id,
                    Medicamento.is_deleted == False,
                    Medicamento.estado == EstadoEnum.ACTIVO
                ).first()
                
                if not medicamento:
                    return {
                        'ok': False,
                        'error': 'not_found',
                        'message': f'Medicamento {medicamento_id} no encontrado o inactivo'
                    }
                
                # Calcular stock total disponible para este medicamento
                stock_total = self.db.query(func.sum(Medicamento.stock)).filter(
                    Medicamento.nombre == medicamento.nombre,
                    Medicamento.fabricante == medicamento.fabricante,
                    Medicamento.presentacion == medicamento.presentacion,
                    Medicamento.is_deleted == False,
                    Medicamento.estado == EstadoEnum.ACTIVO
                ).scalar() or 0
                
                if stock_total < cantidad_solicitada:
                    return {
                        'ok': False,
                        'error': 'insufficient_stock',
                        'message': f'Stock insuficiente para {medicamento.nombre}. Disponible: {stock_total}, Solicitado: {cantidad_solicitada}'
                    }
            
            # Crear venta
            nueva_venta = Venta(
                id=str(uuid.uuid4()),
                numero_venta=self._generar_numero_venta(),
                estado=EstadoVentaEnum.CONFIRMADA if confirmar_pago else EstadoVentaEnum.PENDIENTE,
                metodo_pago=metodo_pago,
                cliente_nombre=cliente_nombre,
                cliente_documento=cliente_documento,
                observaciones=observaciones,
                created_by=usuario_id,
                confirmada_at=datetime.now() if confirmar_pago else None
            )
            
            total = Decimal('0')
            detalles_creados = []
            desglose_descuento = []
            
            #se crean los detalles
            for item in detalles:
                medicamento_id = item.get('medicamento_id')
                cantidad = item.get('cantidad')
                precio_unitario = item.get('precio_unitario')
                
                #en casi, de, si no se provee precio, usar el del medicamento
                if precio_unitario is None:
                    medicamento = self.db.query(Medicamento).filter(
                        Medicamento.id == medicamento_id
                    ).first()
                    precio_unitario = medicamento.precio
                
                precio_unitario = Decimal(str(precio_unitario))
                subtotal = precio_unitario * cantidad
                
                detalle = DetalleVenta(
                    id=str(uuid.uuid4()),
                    venta_id=nueva_venta.id,
                    medicamento_id=medicamento_id,
                    cantidad=cantidad,
                    precio_unitario=precio_unitario,
                    subtotal=subtotal
                )
                
                detalles_creados.append(detalle)
                total += subtotal
            
            nueva_venta.total = total
            
            #garda venta y detalles
            self.db.add(nueva_venta)
            for detalle in detalles_creados:
                self.db.add(detalle)
            
            self.db.flush()
            
            #si se confirma el pago, descontar stock
            if confirmar_pago:
                desglose = self._descontar_stock_venta(
                    venta_id=nueva_venta.id,
                    detalles=detalles_creados,
                    usuario_id=usuario_id,
                    metodo=metodo_descuento
                )
                desglose_descuento = desglose
            
            self.db.commit()
            self.db.refresh(nueva_venta)
            
            #se preparar response con todos los campos requeridos
            # y además cargar detalles con información del medicamento
            detalles_response = []
            for detalle in detalles_creados:
                medicamento = self.db.query(Medicamento).filter(
                    Medicamento.id == detalle.medicamento_id
                ).first()
                
                detalles_response.append({
                    'id': detalle.id,
                    'venta_id': detalle.venta_id,
                    'medicamento_id': detalle.medicamento_id,
                    'medicamento_nombre': medicamento.nombre if medicamento else None,
                    'medicamento_fabricante': medicamento.fabricante if medicamento else None,
                    'medicamento_presentacion': medicamento.presentacion if medicamento else None,
                    'cantidad': detalle.cantidad,
                    'precio_unitario': float(detalle.precio_unitario),
                    'subtotal': float(detalle.subtotal),
                    'lote': detalle.lote
                })
            
            venta_dict = {
                'id': nueva_venta.id,
                'numero_venta': nueva_venta.numero_venta,
                'fecha_venta': nueva_venta.fecha_venta,
                'estado': nueva_venta.estado.value,
                'metodo_pago': nueva_venta.metodo_pago.value if nueva_venta.metodo_pago else None,
                'total': float(nueva_venta.total),
                'cliente_nombre': nueva_venta.cliente_nombre,
                'cliente_documento': nueva_venta.cliente_documento,
                'observaciones': nueva_venta.observaciones,
                'created_by': nueva_venta.created_by,
                'created_at': nueva_venta.created_at,
                'confirmada_at': nueva_venta.confirmada_at,
                'cancelada_at': nueva_venta.cancelada_at,
                'detalles': detalles_response
            }
            
            response = {
                'ok': True,
                'message': 'Venta confirmada exitosamente' if confirmar_pago else 'Venta creada exitosamente',
                'data': venta_dict
            }
            
            if confirmar_pago:
                response['desglose_descuento'] = desglose_descuento
                response['mensaje'] = 'Venta confirmada y stock descontado exitosamente'
            
            return response
            
        except Exception as e:
            self.db.rollback()
            print(f"Error en crear_venta: {e}")
            import traceback
            traceback.print_exc()
            return {
                'ok': False,
                'error': 'database_error',
                'message': f'Error al crear venta: {str(e)}'
            }
    
    def _descontar_stock_venta(
        self,
        venta_id: str,
        detalles: List[DetalleVenta],
        usuario_id: str,
        metodo: str = "FEFO"
    ) -> List[Dict[str, Any]]:
        """
        Descuenta stock de medicamentos usando FIFO o FEFO.
        
        HU-3.01: "Then disminuir stock por lotes FIFO/FEFO"
        
        Reglas de negocio:
        - FIFO: Descuenta del lote más antiguo (created_at)
        - FEFO: Descuenta del lote con vencimiento más próximo
        - Si un lote no tiene suficiente, toma del siguiente automáticamente
        
        Returns:
            Lista con desglose de descuentos por lote
        """
        desglose = []
        
        try:
            for detalle in detalles:
                cantidad_restante = detalle.cantidad
                medicamento_ref = self.db.query(Medicamento).filter(
                    Medicamento.id == detalle.medicamento_id
                ).first()
                
                if not medicamento_ref:
                    continue
                
                # Obtener todos los lotes del mismo medicamento
                query = self.db.query(Medicamento).filter(
                    Medicamento.nombre == medicamento_ref.nombre,
                    Medicamento.fabricante == medicamento_ref.fabricante,
                    Medicamento.presentacion == medicamento_ref.presentacion,
                    Medicamento.is_deleted == False,
                    Medicamento.estado == EstadoEnum.ACTIVO,
                    Medicamento.stock > 0
                )
                
                # Ordenar según método
                if metodo.upper() == "FIFO":
                    #fifo: Más antiguo primero (created_at)
                    query = query.order_by(asc(Medicamento.created_at))
                else:  # FEFO
                    # fefo: Vencimiento más próximo primero
                    query = query.order_by(asc(Medicamento.fecha_vencimiento))
                
                lotes = query.all()
                
                # Descontar de cada lote hasta completar la cantidad
                for lote in lotes:
                    if cantidad_restante <= 0:
                        break
                    
                    stock_anterior = lote.stock
                    cantidad_a_descontar = min(cantidad_restante, lote.stock)
                    
                    # Descontar del lote
                    lote.stock -= cantidad_a_descontar
                    lote.updated_by = usuario_id
                    
                    # Registrar movimiento
                    movimiento = Movimiento(
                        id=str(uuid.uuid4()),
                        medicamento_id=lote.id,
                        tipo=MovimientoTipoEnum.SALIDA,
                        cantidad=cantidad_a_descontar,
                        usuario_id=usuario_id,
                        motivo=f"Venta #{venta_id}",
                        fecha=datetime.now()
                    )
                    self.db.add(movimiento)
                    
                    # Actualizar detalle de venta con el lote usado
                    if cantidad_a_descontar == detalle.cantidad:
                        detalle.lote = lote.lote
                    
                    # Agregar al desglose
                    desglose.append({
                        'medicamento_id': lote.id,
                        'lote': lote.lote,
                        'cantidad_descontada': cantidad_a_descontar,
                        'stock_anterior': stock_anterior,
                        'stock_nuevo': lote.stock,
                        'fecha_vencimiento': lote.fecha_vencimiento
                    })
                    
                    cantidad_restante -= cantidad_a_descontar
                
                # Verificar que se descontó toda la cantidad
                if cantidad_restante > 0:
                    raise Exception(
                        f"No hay stock suficiente para completar la venta. "
                        f"Faltaron {cantidad_restante} unidades"
                    )
            
            return desglose
            
        except Exception as e:
            print(f"Error en _descontar_stock_venta: {e}")
            raise
    
    def confirmar_pago_venta(
        self,
        venta_id: str,
        metodo_pago: str,
        usuario_id: str,
        metodo_descuento: str = "FEFO"
    ) -> Dict[str, Any]:
        """
        Confirma el pago de una venta pendiente y descuenta stock.
        
        HU-3.01: "El registro solo debe generarse si el estado del pago = 'Confirmado'"
        """
        try:
            venta = self.db.query(Venta).filter(Venta.id == venta_id).first()
            
            if not venta:
                return {
                    'ok': False,
                    'error': 'not_found',
                    'message': 'Venta no encontrada'
                }
            
            if venta.estado == EstadoVentaEnum.CONFIRMADA:
                return {
                    'ok': False,
                    'error': 'already_confirmed',
                    'message': 'La venta ya está confirmada'
                }
            
            if venta.estado == EstadoVentaEnum.CANCELADA:
                return {
                    'ok': False,
                    'error': 'cancelled',
                    'message': 'No se puede confirmar una venta cancelada'
                }
            
            # Obtener detalles
            detalles = self.db.query(DetalleVenta).filter(
                DetalleVenta.venta_id == venta_id
            ).all()
            
            # Descontar stock
            desglose = self._descontar_stock_venta(
                venta_id=venta_id,
                detalles=detalles,
                usuario_id=usuario_id,
                metodo=metodo_descuento
            )
            
            # Actualizar venta
            venta.estado = EstadoVentaEnum.CONFIRMADA
            venta.metodo_pago = metodo_pago
            venta.confirmada_at = datetime.now()
            
            self.db.commit()
            self.db.refresh(venta)
            
            # Cargar detalles con información del medicamento
            detalles_query = self.db.query(
                DetalleVenta,
                Medicamento.nombre,
                Medicamento.fabricante,
                Medicamento.presentacion
            ).join(
                Medicamento, DetalleVenta.medicamento_id == Medicamento.id
            ).filter(
                DetalleVenta.venta_id == venta_id
            ).all()
            
            detalles_response = [{
                'id': d[0].id,
                'venta_id': d[0].venta_id,
                'medicamento_id': d[0].medicamento_id,
                'medicamento_nombre': d[1],
                'medicamento_fabricante': d[2],
                'medicamento_presentacion': d[3],
                'cantidad': d[0].cantidad,
                'precio_unitario': float(d[0].precio_unitario),
                'subtotal': float(d[0].subtotal),
                'lote': d[0].lote
            } for d in detalles_query]
            
            return {
                'ok': True,
                'venta': {
                    'id': venta.id,
                    'numero_venta': venta.numero_venta,
                    'fecha_venta': venta.fecha_venta,
                    'estado': venta.estado.value,
                    'metodo_pago': venta.metodo_pago.value,
                    'total': float(venta.total),
                    'cliente_nombre': venta.cliente_nombre,
                    'cliente_documento': venta.cliente_documento,
                    'observaciones': venta.observaciones,
                    'created_by': venta.created_by,
                    'created_at': venta.created_at,
                    'confirmada_at': venta.confirmada_at,
                    'cancelada_at': venta.cancelada_at,
                    'detalles': detalles_response
                },
                'desglose_descuento': desglose,
                'mensaje': 'Pago confirmado y stock descontado exitosamente'
            }
            
        except Exception as e:
            self.db.rollback()
            print(f"Error en confirmar_pago_venta: {e}")
            import traceback
            traceback.print_exc()
            return {
                'ok': False,
                'error': 'database_error',
                'message': f'Error al confirmar pago: {str(e)}'
            }
    
    def obtener_ventas(
        self,
        estado: Optional[str] = None,
        fecha_inicio: Optional[date] = None,
        fecha_fin: Optional[date] = None
    ) -> List[Dict[str, Any]]:
        """Obtiene lista de ventas con filtros opcionales"""
        try:
            query = self.db.query(Venta)
            
            if estado:
                query = query.filter(Venta.estado == estado)
            
            if fecha_inicio:
                query = query.filter(func.date(Venta.fecha_venta) >= fecha_inicio)
            
            if fecha_fin:
                query = query.filter(func.date(Venta.fecha_venta) <= fecha_fin)
            
            ventas = query.order_by(desc(Venta.fecha_venta)).all()
            
            resultado = []
            for v in ventas:
                # Obtener detalles con información del medicamento para cada venta
                detalles = self.db.query(
                    DetalleVenta,
                    Medicamento.nombre,
                    Medicamento.fabricante,
                    Medicamento.presentacion
                ).join(
                    Medicamento, DetalleVenta.medicamento_id == Medicamento.id
                ).filter(
                    DetalleVenta.venta_id == v.id
                ).all()
                
                detalles_response = [{
                    'id': d[0].id,
                    'venta_id': d[0].venta_id,
                    'medicamento_id': d[0].medicamento_id,
                    'medicamento_nombre': d[1],
                    'medicamento_fabricante': d[2],
                    'medicamento_presentacion': d[3],
                    'cantidad': d[0].cantidad,
                    'precio_unitario': float(d[0].precio_unitario),
                    'subtotal': float(d[0].subtotal),
                    'lote': d[0].lote
                } for d in detalles]
                
                resultado.append({
                    'id': v.id,
                    'numero_venta': v.numero_venta,
                    'fecha_venta': v.fecha_venta,
                    'estado': v.estado.value,
                    'metodo_pago': v.metodo_pago.value if v.metodo_pago else None,
                    'total': float(v.total),
                    'cliente_nombre': v.cliente_nombre,
                    'cliente_documento': v.cliente_documento,
                    'observaciones': v.observaciones,
                    'created_by': v.created_by,
                    'created_at': v.created_at,
                    'confirmada_at': v.confirmada_at,
                    'cancelada_at': v.cancelada_at,
                    'detalles': detalles_response
                })
            
            return resultado
            
        except Exception as e:
            print(f"Error en obtener_ventas: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    def obtener_venta_por_id(self, venta_id: str) -> Optional[Dict[str, Any]]:
        """Obtiene una venta por ID con sus detalles"""
        try:
            venta = self.db.query(Venta).filter(Venta.id == venta_id).first()
            
            if not venta:
                return None
            
            #obtiene detalles con información del medicamento
            detalles = self.db.query(
                DetalleVenta,
                Medicamento.nombre,
                Medicamento.fabricante,
                Medicamento.presentacion
            ).join(
                Medicamento, DetalleVenta.medicamento_id == Medicamento.id
            ).filter(
                DetalleVenta.venta_id == venta_id
            ).all()
            
            return {
                'id': venta.id,
                'numero_venta': venta.numero_venta,
                'fecha_venta': venta.fecha_venta,
                'estado': venta.estado.value,
                'metodo_pago': venta.metodo_pago.value if venta.metodo_pago else None,
                'total': float(venta.total),
                'cliente_nombre': venta.cliente_nombre,
                'cliente_documento': venta.cliente_documento,
                'observaciones': venta.observaciones,
                'created_by': venta.created_by,
                'created_at': venta.created_at,
                'confirmada_at': venta.confirmada_at,
                'detalles': [{
                    'id': d[0].id,
                    'venta_id': d[0].venta_id,  # ✅ AGREGADO: Campo requerido
                    'medicamento_id': d[0].medicamento_id,
                    'medicamento_nombre': d[1],
                    'medicamento_fabricante': d[2],
                    'medicamento_presentacion': d[3],
                    'cantidad': d[0].cantidad,
                    'precio_unitario': float(d[0].precio_unitario),
                    'subtotal': float(d[0].subtotal),
                    'lote': d[0].lote
                } for d in detalles]
            }
            
        except Exception as e:
            print(f"Error en obtener_venta_por_id: {e}")
            return None
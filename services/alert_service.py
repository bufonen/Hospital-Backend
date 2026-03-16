"""
Servicio para gestión de alertas automatizadas.
HU-2.01: Alertas de stock bajo
HU-2.02: Alertas de vencimiento

REFACTORIZADO: Ahora utiliza el patrón Factory para creación de alertas.
Los factories encapsulan la lógica de construcción específica de cada tipo.
"""
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
from database.models import (
    Alerta, Medicamento, EstadoEnum, 
    TipoAlertaEnum, EstadoAlertaEnum, PrioridadAlertaEnum
)
from database.redis_client import redis_client
from observers.alert_observer import alert_subject
from factories.alert_factory import AlertFactoryRegistry
from typing import List, Optional, Dict, Any
from datetime import date, datetime, timedelta


class AlertService:
    """
    Servicio para creación, actualización y gestión de alertas.
    
    Responsabilidades:
    - Detectar condiciones de alerta (stock bajo, vencimientos)
    - Crear alertas en base de datos (usando Factories)
    - Notificar a observadores (patrón Observer)
    - Gestionar estados de alertas
    - Prevenir duplicados
    """
    
    def __init__(self, db: Session):
        self.db = db
        self.redis = redis_client
    
    #VERIFICACIÓN EN TIEMPO REAL
    
    def check_medicamento_alerts(self, medicamento_id: str) -> Dict[str, Any]:
        """
        Verifica y genera alertas para un medicamento específico EN TIEMPO REAL.
        Útil para llamar después de movimientos o cambios.
        
        Args:
            medicamento_id: ID del medicamento a verificar
        
        Returns:
            Diccionario con alertas creadas/actualizadas
        """
        from datetime import date
        
        result = {
            'stock_alert': None,
            'expiration_alert': None
        }
        
        # Obtener medicamento
        med = self.db.query(Medicamento).filter(Medicamento.id == medicamento_id).first()
        if not med or med.is_deleted or med.estado != EstadoEnum.ACTIVO:
            return result
        
        # 1. VERIFICAR STOCK (si tiene umbral configurado)
        if med.minimo_stock is not None:
            alert_type, priority = self._classify_stock_alert(med.stock, med.minimo_stock)
            
            if alert_type:
                # Hay condición de alerta de stock
                action = self._create_or_update_stock_alert(med, alert_type, priority)
                result['stock_alert'] = {
                    'action': action,
                    'type': alert_type.value,
                    'priority': priority.value
                }
            else:
                # No hay condición, resolver alertas activas si existen
                resolved = self._resolve_stock_alerts_if_exists(med.id)
                if resolved > 0:
                    result['stock_alert'] = {
                        'action': 'resolved',
                        'count': resolved
                    }
        
        # 2. VERIFICAR VENCIMIENTO
        hoy = date.today()
        dias_restantes = (med.fecha_vencimiento - hoy).days
        
        # Solo alertar si está dentro del rango de anticipación
        dias_anticipacion = 30  # Configurable desde env
        if dias_restantes <= dias_anticipacion:
            alert_type, priority = self._classify_expiration_alert(dias_restantes)
            
            if alert_type:
                action = self._create_or_update_expiration_alert(
                    med, alert_type, priority, dias_restantes
                )
                result['expiration_alert'] = {
                    'action': action,
                    'type': alert_type.value,
                    'priority': priority.value
                }
        
        return result
    
    #DETECCIÓN DE ALERTAS
    
    def scan_stock_alerts(self) -> Dict[str, Any]:
        """
        Escanea medicamentos y genera alertas de stock bajo.
        HU-2.01: Monitoreo automático de niveles de stock.
        
        Returns:
            Diccionario con estadísticas de alertas generadas
        """
        stats = {
            'scanned': 0,
            'alerts_created': 0,
            'alerts_updated': 0,
            'alerts_resolved': 0
        }
        
        # Obtener medicamentos activos
        medicamentos = self.db.query(Medicamento).filter(
            and_(
                Medicamento.is_deleted == False,
                Medicamento.estado == EstadoEnum.ACTIVO,
                Medicamento.minimo_stock.isnot(None)
            )
        ).all()
        
        stats['scanned'] = len(medicamentos)
        
        for med in medicamentos:
            # Determinar tipo y prioridad de alerta según stock
            alert_type, priority = self._classify_stock_alert(med.stock, med.minimo_stock)
            
            if alert_type:
                # Hay condición de alerta
                result = self._create_or_update_stock_alert(med, alert_type, priority)
                if result == 'created':
                    stats['alerts_created'] += 1
                elif result == 'updated':
                    stats['alerts_updated'] += 1
            else:
                # No hay condición de alerta, resolver alertas activas si existen
                resolved = self._resolve_stock_alerts_if_exists(med.id)
                stats['alerts_resolved'] += resolved
        
        return stats
    
    def scan_expiration_alerts(self, dias_anticipacion: int = 30) -> Dict[str, Any]:
        """
        Escanea medicamentos próximos a vencer y genera alertas.
        HU-2.02: Detección de medicamentos próximos a vencer.
        
        Args:
            dias_anticipacion: Días de anticipación para alertas
        
        Returns:
            Diccionario con estadísticas de alertas generadas
        """
        stats = {
            'scanned': 0,
            'alerts_created': 0,
            'alerts_updated': 0,
            'alerts_resolved': 0
        }
        
        hoy = date.today()
        fecha_limite = hoy + timedelta(days=dias_anticipacion)
        
        # Obtener medicamentos activos que vencen en el período
        medicamentos = self.db.query(Medicamento).filter(
            and_(
                Medicamento.is_deleted == False,
                Medicamento.estado == EstadoEnum.ACTIVO,
                Medicamento.fecha_vencimiento <= fecha_limite
            )
        ).all()
        
        stats['scanned'] = len(medicamentos)
        
        for med in medicamentos:
            dias_restantes = (med.fecha_vencimiento - hoy).days
            
            # Clasificar alerta de vencimiento
            alert_type, priority = self._classify_expiration_alert(dias_restantes)
            
            if alert_type:
                result = self._create_or_update_expiration_alert(
                    med, alert_type, priority, dias_restantes
                )
                if result == 'created':
                    stats['alerts_created'] += 1
                elif result == 'updated':
                    stats['alerts_updated'] += 1
        
        return stats
    
    #CLASIFICACIÓN
    
    def _classify_stock_alert(self, stock: int, minimo: int) -> tuple:
        """
        Clasifica el tipo y prioridad de alerta según stock.
        
        HU-2.01 criterios:
        - stock = 0 -> STOCK_AGOTADO / CRITICA
        - stock < minimo -> STOCK_CRITICO / ALTA
        - stock == minimo -> STOCK_MINIMO / MEDIA
        - stock > minimo -> Sin alerta
        
        Returns:
            (TipoAlertaEnum, PrioridadAlertaEnum) o (None, None)
        """
        if stock == 0:
            return TipoAlertaEnum.STOCK_AGOTADO, PrioridadAlertaEnum.CRITICA
        elif stock < minimo:
            return TipoAlertaEnum.STOCK_CRITICO, PrioridadAlertaEnum.ALTA
        elif stock == minimo:
            return TipoAlertaEnum.STOCK_MINIMO, PrioridadAlertaEnum.MEDIA
        else:
            return None, None
    
    def _classify_expiration_alert(self, dias_restantes: int) -> tuple:
        """
        Clasifica el tipo y prioridad de alerta según días restantes.
        
        HU-2.02 criterios:
        - dias < 0 -> VENCIDO / CRITICA
        - dias <= 7 -> VENCIMIENTO_INMEDIATO / ALTA
        - dias <= 30 -> VENCIMIENTO_PROXIMO / MEDIA
        
        Returns:
            (TipoAlertaEnum, PrioridadAlertaEnum) o (None, None)
        """
        if dias_restantes < 0:
            return TipoAlertaEnum.VENCIDO, PrioridadAlertaEnum.CRITICA
        elif dias_restantes <= 7:
            return TipoAlertaEnum.VENCIMIENTO_INMEDIATO, PrioridadAlertaEnum.ALTA
        elif dias_restantes <= 30:
            return TipoAlertaEnum.VENCIMIENTO_PROXIMO, PrioridadAlertaEnum.MEDIA
        else:
            return None, None
    
    #CREACIÓN Y ACTUALIZACIÓN
    
    def _create_or_update_stock_alert(
        self, 
        medicamento: Medicamento, 
        alert_type: TipoAlertaEnum, 
        priority: PrioridadAlertaEnum
        ) -> str:
  
        existing = self.db.query(Alerta).filter(
            and_(
                Alerta.medicamento_id == medicamento.id,
                Alerta.tipo.in_([
                    TipoAlertaEnum.STOCK_AGOTADO.value,
                    TipoAlertaEnum.STOCK_CRITICO.value,
                    TipoAlertaEnum.STOCK_MINIMO.value
                ]),
                Alerta.estado == EstadoAlertaEnum.ACTIVA.value
            )
        ).first()

        
        if existing:
            # Ya existe alerta activa            
            #verificar si cambió el tipo o prioridad
            tipo_cambio = existing.tipo != alert_type
            prioridad_cambio = existing.prioridad != priority
            stock_cambio = existing.stock_actual != medicamento.stock
            
            if tipo_cambio or prioridad_cambio or stock_cambio:
                # Usar factory para regenerar mensaje actualizado
                factory = AlertFactoryRegistry.get_factory('stock')
                mensaje = factory.generate_message(medicamento, alert_type)

                existing.tipo = alert_type
                existing.prioridad = priority
                existing.mensaje = mensaje
                existing.stock_actual = medicamento.stock
                existing.stock_minimo = medicamento.minimo_stock
                existing.updated_at = datetime.now()

                self.db.commit()
                self._notify_alert_event(existing, 'updated')
                return 'updated'
            else:
                return 'unchanged'

        # ✔ ARREGLO: Pasar explícitamente el tipo y prioridad
        factory = AlertFactoryRegistry.get_factory('stock')
        alerta = factory.create_alert(
            medicamento=medicamento,
            alert_type=alert_type,
            priority=priority
        )

        self.db.add(alerta)
        self.db.commit()
        self.db.refresh(alerta)

        self._notify_alert_event(alerta, 'created')
        return 'created'

    
    def _create_or_update_expiration_alert(
        self,
        medicamento: Medicamento,
        alert_type: TipoAlertaEnum,
        priority: PrioridadAlertaEnum,
        dias_restantes: int
    ) -> str:
        """
        Crea o actualiza una alerta de vencimiento usando Factory.
        HU-2.02: No duplicar alertas para mismo lote.
        
        REFACTORIZADO: Usa ExpirationAlertFactory para construcción.
        
        Returns:
            'created', 'updated', o 'unchanged'
        """
        # Buscar alerta activa existente para este medicamento (tipo vencimiento)
        existing = self.db.query(Alerta).filter(
            and_(
                Alerta.medicamento_id == medicamento.id,
                Alerta.tipo.in_([
                    TipoAlertaEnum.VENCIMIENTO_PROXIMO,
                    TipoAlertaEnum.VENCIMIENTO_INMEDIATO,
                    TipoAlertaEnum.VENCIDO
                ]),
                Alerta.estado == EstadoAlertaEnum.ACTIVA
            )
        ).first()
        
        if existing:
            #actualizar si cambió el tipo, prioridad o días restantes
            tipo_cambio = existing.tipo != alert_type
            prioridad_cambio = existing.prioridad != priority
            dias_cambio = existing.dias_restantes != dias_restantes
            
            if tipo_cambio or prioridad_cambio or dias_cambio:
                # Usar factory para regenerar mensaje actualizado
                factory = AlertFactoryRegistry.get_factory('expiration')
                mensaje = factory.generate_message(medicamento, alert_type, dias_restantes)
                
                existing.tipo = alert_type
                existing.prioridad = priority
                existing.mensaje = mensaje
                existing.dias_restantes = dias_restantes
                existing.updated_at = datetime.now()
                
                self.db.commit()
                
                # Notificar observadores
                self._notify_alert_event(existing, 'updated')
                
                return 'updated'
            else:
                return 'unchanged'
        else:
            # FACTORY: Delegar construcción completa al factory
            factory = AlertFactoryRegistry.get_factory('expiration')
            alerta = factory.create_alert(
                medicamento=medicamento,
                alert_type=alert_type,
                priority=priority,
                dias_restantes=dias_restantes
            )


            
            self.db.add(alerta)
            self.db.commit()
            self.db.refresh(alerta)
            
            # Notificar observadores
            self._notify_alert_event(alerta, 'created')
            
            return 'created'
    
    #RESOLUCIÓN
    
    def _resolve_stock_alerts_if_exists(self, medicamento_id: str) -> int:
        """
        Resuelve alertas de stock si el stock volvió a nivel normal.
        
        Returns:
            Cantidad de alertas resueltas
        """
        alertas = self.db.query(Alerta).filter(
            and_(
                Alerta.medicamento_id == medicamento_id,
                Alerta.tipo.in_([
                    TipoAlertaEnum.STOCK_AGOTADO,
                    TipoAlertaEnum.STOCK_CRITICO,
                    TipoAlertaEnum.STOCK_MINIMO
                ]),
                Alerta.estado == EstadoAlertaEnum.ACTIVA
            )
        ).all()
        
        count = 0
        for alerta in alertas:
            alerta.estado = EstadoAlertaEnum.RESUELTA
            alerta.resuelta_at = datetime.now()
            alerta.resuelta_by = 'system_auto'
            count += 1
            
            # Notificar observadores
            self._notify_alert_event(alerta, 'resolved')
        
        if count > 0:
            self.db.commit()
        
        return count
    
    def resolve_alert(self, alerta_id: str, user_id: Optional[str] = None) -> bool:
        """
        Marca una alerta como resuelta manualmente.
        HU-2.01 y HU-2.02: Usuario puede marcar alerta como resuelta.
        
        Args:
            alerta_id: ID de la alerta
            user_id: ID del usuario que resuelve
        
        Returns:
            True si se resolvió, False si no existe o ya estaba resuelta
        """
        alerta = self.db.query(Alerta).filter(Alerta.id == alerta_id).first()
        
        if not alerta or alerta.estado == EstadoAlertaEnum.RESUELTA:
            return False
        
        alerta.estado = EstadoAlertaEnum.RESUELTA
        alerta.resuelta_at = datetime.now()
        alerta.resuelta_by = user_id or 'unknown'
        
        self.db.commit()
        
        # Eliminar notificación de Redis
        from database.redis_client import redis_client
        
        # Determinar roles que tienen esta notificación
        if alerta.tipo in [TipoAlertaEnum.STOCK_MINIMO, TipoAlertaEnum.STOCK_CRITICO, TipoAlertaEnum.STOCK_AGOTADO]:
            # Alertas de stock: admin y compras
            redis_client.remove_notification('admin', str(alerta_id))
            redis_client.remove_notification('compras', str(alerta_id))
        else:
            # Alertas de vencimiento: admin y farmaceutico
            redis_client.remove_notification('admin', str(alerta_id))
            redis_client.remove_notification('farmaceutico', str(alerta_id))
        
        # Notificar observadores
        self._notify_alert_event(alerta, 'resolved')
        
        return True
    
    #CONSULTAS
    
    def get_active_alerts(
        self, 
        tipo: Optional[TipoAlertaEnum] = None,
        prioridad: Optional[PrioridadAlertaEnum] = None
    ) -> List[Alerta]:
        """
        Obtiene alertas activas con filtros opcionales.
        
        Args:
            tipo: Filtrar por tipo de alerta
            prioridad: Filtrar por prioridad
        
        Returns:
            Lista de alertas activas
        """
        q = self.db.query(Alerta).filter(Alerta.estado == EstadoAlertaEnum.ACTIVA)
        
        if tipo:
            q = q.filter(Alerta.tipo == tipo)
        
        if prioridad:
            q = q.filter(Alerta.prioridad == prioridad)
        
        return q.order_by(Alerta.prioridad, Alerta.created_at.desc()).all()
    
    def get_alert_history(
        self, 
        medicamento_id: Optional[str] = None,
        limit: int = 100
    ) -> List[Alerta]:
        """
        Obtiene historial de alertas.
        HU-2.02: Mantener historial de alertas generadas.
        
        Args:
            medicamento_id: Filtrar por medicamento (opcional)
            limit: Límite de resultados
        
        Returns:
            Lista de alertas (todas, no solo activas)
        """
        q = self.db.query(Alerta)
        
        if medicamento_id:
            q = q.filter(Alerta.medicamento_id == medicamento_id)
        
        return q.order_by(Alerta.created_at.desc()).limit(limit).all()
    
    #UTILIDADES
    
    # DEPRECADO: Métodos movidos a los factories
    # Mantenidos temporalmente por compatibilidad, pero ya no se usan internamente
    
    def _generate_stock_message(self, med: Medicamento, alert_type: TipoAlertaEnum) -> str:
        """Usa StockAlertFactory.generate_message() en su lugar."""
        factory = AlertFactoryRegistry.get_factory('stock')
        return factory.generate_message(med, alert_type)
    
    def _generate_expiration_message(
        self, 
        med: Medicamento, 
        alert_type: TipoAlertaEnum,
        dias_restantes: int
    ) -> str:
        """Usa ExpirationAlertFactory.generate_message() en su lugar."""
        factory = AlertFactoryRegistry.get_factory('expiration')
        return factory.generate_message(med, alert_type, dias_restantes)
    
    def _notify_alert_event(self, alerta: Alerta, event_type: str):
        """
        Notifica a los observadores sobre un evento de alerta.
        Implementa el patrón Observer.
        """
        # Obtener información del medicamento
        med = self.db.query(Medicamento).filter(Medicamento.id == alerta.medicamento_id).first()
        
        if not med:
            return
        
        # Construir evento
        alert_event = {
            'event_type': event_type,
            'alert_id': str(alerta.id),
            'alert_type': alerta.tipo.value,
            'priority': alerta.prioridad.value,
            'medicamento_id': str(alerta.medicamento_id),
            'medicamento_nombre': med.nombre,
            'medicamento_fabricante': med.fabricante,
            'medicamento_presentacion': med.presentacion,
            'medicamento_lote': med.lote,
            'mensaje': alerta.mensaje,
            'timestamp': datetime.now().isoformat(),
            'metadata': {
                'stock_actual': alerta.stock_actual,
                'stock_minimo': alerta.stock_minimo,
                'fecha_vencimiento': str(alerta.fecha_vencimiento) if alerta.fecha_vencimiento else None,
                'dias_restantes': alerta.dias_restantes,
                'lote': alerta.lote
            }
        }
        
        # Notificar a observadores
        alert_subject.notify(alert_event)

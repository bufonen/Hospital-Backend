"""
Implementación del patrón Observer para el sistema de alertas.
HU-2: Sistema de alertas automatizado con notificaciones.

Patrón Observer:
- Subject: AlertSubject (sistema de alertas)
- Observer: AlertObserver (observadores que reciben notificaciones)
- ConcreteObservers: RedisNotifier, DatabaseLogger, etc.
"""
from abc import ABC, abstractmethod
from typing import List, Dict, Any
from datetime import datetime


class AlertObserver(ABC):
    """
    Interfaz base para observadores de alertas.
    Los observadores son notificados cuando se crea, actualiza o resuelve una alerta.
    """
    
    @abstractmethod
    def update(self, alert_event: Dict[str, Any]):
        """
        Método llamado cuando ocurre un evento de alerta.
        
        Args:
            alert_event: Diccionario con información del evento:
                - event_type: 'created', 'updated', 'resolved'
                - alert_id: ID de la alerta
                - alert_type: Tipo de alerta (STOCK_MINIMO, VENCIMIENTO_PROXIMO, etc.)
                - priority: Prioridad (BAJA, MEDIA, ALTA, CRITICA)
                - medicamento_id: ID del medicamento
                - medicamento_nombre: Nombre del medicamento
                - mensaje: Mensaje de la alerta
                - timestamp: Momento del evento
                - metadata: Información adicional
        """
        pass


class AlertSubject:
    """
    Sujeto que mantiene una lista de observadores y los notifica de eventos.
    Implementa el patrón Observer para desacoplar la generación de alertas
    de las acciones que se toman cuando ocurren.
    """
    
    def __init__(self):
        self._observers: List[AlertObserver] = []
    
    def attach(self, observer: AlertObserver):
        """Agrega un observador a la lista."""
        if observer not in self._observers:
            self._observers.append(observer)
            #print(f"Observador {observer.__class__.__name__} registrado")
    
    def detach(self, observer: AlertObserver):
        """Remueve un observador de la lista."""
        if observer in self._observers:
            self._observers.remove(observer)
            #print(f"✓ Observador {observer.__class__.__name__} removido")
    
    def notify(self, alert_event: Dict[str, Any]):
        """
        Notifica a todos los observadores de un evento de alerta.
        
        Args:
            alert_event: Información del evento de alerta
        """
        # Agregar timestamp si no existe
        if 'timestamp' not in alert_event:
            alert_event['timestamp'] = datetime.now().isoformat()
        
        # Notificar a todos los observadores
        for observer in self._observers:
            try:
                observer.update(alert_event)
            except Exception as e:
                print(f"Error notificando a {observer.__class__.__name__}: {e}")


class RedisNotificationObserver(AlertObserver):
    """
    Observador que almacena notificaciones en Redis para acceso rápido.
    HU-2: Uso de Redis caché para almacenamiento de alertas/notificaciones.
    """
    
    def __init__(self, redis_client):
        self.redis_client = redis_client
    
    def update(self, alert_event: Dict[str, Any]):
        """Almacena la notificación en Redis según el rol objetivo."""
        event_type = alert_event.get('event_type')
        alert_type = alert_event.get('alert_type')
        
        # Determinar roles que deben ser notificados según el tipo de alerta
        target_roles = self._get_target_roles(alert_type, event_type)
        
        # Crear notificación
        notification = {
            'alert_id': alert_event.get('alert_id'),
            'event_type': event_type,
            'alert_type': alert_type,
            'priority': alert_event.get('priority'),
            'medicamento_nombre': alert_event.get('medicamento_nombre'),
            'medicamento_fabricante': alert_event.get('medicamento_fabricante', ''),
            'medicamento_presentacion': alert_event.get('medicamento_presentacion', ''),
            'medicamento_lote': alert_event.get('medicamento_lote', ''),
            'mensaje': alert_event.get('mensaje'),
            'timestamp': alert_event.get('timestamp')
        }
        
        # Enviar notificación a cada rol
        for role in target_roles:
            self.redis_client.push_notification(role, notification)
        
        # Cachear la alerta completa
        if event_type == 'created':
            self.redis_client.cache_alerta(
                alert_event.get('alert_id'),
                alert_event,
                ttl=3600  # 1 hora
            )
        elif event_type == 'resolved':
            # Eliminar del caché cuando se resuelve
            self.redis_client.delete_alerta_cached(alert_event.get('alert_id'))
    
    def _get_target_roles(self, alert_type: str, event_type: str) -> List[str]:
        """
        Determina qué roles deben ser notificados según el tipo de alerta.
        
        HU-2.01: Alertas de stock -> responsable de compras
        HU-2.02: Alertas de vencimiento -> farmacéutico/administrador
        HU-4.02: Alertas de órdenes retrasadas -> responsable de compras
        """
        roles = []
        
        # Alertas de stock -> Responsable de compras + Admin
        if alert_type in ['STOCK_MINIMO', 'STOCK_CRITICO', 'STOCK_AGOTADO']:
            roles.extend(['compras', 'admin'])
        
        # Alertas de vencimiento -> Farmacéutico + Admin
        elif alert_type in ['VENCIMIENTO_PROXIMO', 'VENCIMIENTO_INMEDIATO', 'VENCIDO']:
            roles.extend(['farmaceutico', 'admin'])
        
        # Alertas de órdenes retrasadas -> Responsable de compras + Admin
        elif alert_type == 'ORDEN_RETRASADA':
            roles.extend(['compras', 'admin'])
        
        # Por defecto, notificar a admin
        if not roles:
            roles.append('admin')
        
        return list(set(roles))  # Eliminar duplicados


class DatabaseLogObserver(AlertObserver):
    """
    Observador que registra eventos de alertas en logs de auditoría.
    Complementa el sistema de alertas con trazabilidad completa.
    """
    
    def __init__(self, db_session):
        self.db = db_session
    
    def update(self, alert_event: Dict[str, Any]):
        """Registra el evento en el log de auditoría."""
        from database.models import AuditLog
        
        try:
            log = AuditLog(
                entidad='alertas',
                entidad_id=alert_event.get('alert_id'),
                usuario_id=alert_event.get('usuario_id', 'system'),
                accion=alert_event.get('event_type', 'ALERT_EVENT').upper(),
                metadatos={
                    'alert_type': alert_event.get('alert_type'),
                    'priority': alert_event.get('priority'),
                    'medicamento_id': alert_event.get('medicamento_id'),
                    'mensaje': alert_event.get('mensaje'),
                    'timestamp': alert_event.get('timestamp')
                }
            )
            self.db.add(log)
            self.db.commit()
        except Exception as e:
            print(f"Error registrando evento en auditoría: {e}")
            self.db.rollback()


class ConsoleLogObserver(AlertObserver):
    """
    Observador simple que imprime alertas en consola.
    Útil para desarrollo y debugging.
    """
    
    def update(self, alert_event: Dict[str, Any]):
        """Imprime la alerta en consola."""
        event_type = alert_event.get('event_type')
        alert_type = alert_event.get('alert_type')
        priority = alert_event.get('priority')
        mensaje = alert_event.get('mensaje')
        
        """
        print(f"\n{'='*60}")
        print(f"ALERTA {event_type.upper()}")
        print(f"Tipo: {alert_type} | Prioridad: {priority}")
        print(f"Mensaje: {mensaje}")
        print(f"Timestamp: {alert_event.get('timestamp')}")
        print(f"{'='*60}\n")
        """

# Instancia global del sujeto de alertas
alert_subject = AlertSubject()


def setup_alert_observers(redis_client, db_session=None, enable_console_log=False):
    """
    Configura los observadores del sistema de alertas.
    
    Args:
        redis_client: Cliente de Redis
        db_session: Sesión de base de datos (opcional)
        enable_console_log: Si se debe habilitar log en consola
    """
    # Siempre agregar el observador de Redis
    redis_observer = RedisNotificationObserver(redis_client)
    alert_subject.attach(redis_observer)
    
    # Agregar observador de base de datos si hay sesión
    if db_session:
        db_observer = DatabaseLogObserver(db_session)
        alert_subject.attach(db_observer)
    
    # Agregar observador de consola si está habilitado
    if enable_console_log:
        console_observer = ConsoleLogObserver()
        alert_subject.attach(console_observer)
    
    #print("✓ Sistema de observadores de alertas configurado")

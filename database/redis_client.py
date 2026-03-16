"""
Configuración de Redis para caché de alertas y notificaciones.
HU-2: Sistema de alertas automatizado con Redis.
"""
import redis
import json
import os
from typing import Optional, List, Dict, Any
from dotenv import load_dotenv

load_dotenv()

# Configuración de Redis
REDIS_URL = os.getenv('REDIS_URL')
REDIS_HOST = os.getenv('REDIS_HOST', 'localhost')
REDIS_PORT = int(os.getenv('REDIS_PORT', 6379))
REDIS_DB = int(os.getenv('REDIS_DB', 0))
REDIS_PASSWORD = os.getenv('REDIS_PASSWORD', None)

# TTL por defecto para alertas en Redis (1 hora)
ALERT_TTL = 3600


class RedisClient:
    """
    Cliente Redis para almacenamiento de alertas y notificaciones.
    
    Funciones:
    - Caché de alertas activas para acceso rápido
    - Cola de notificaciones pendientes
    - Contador de alertas por usuario
    - Persistencia temporal de eventos
    """
    
    def __init__(self):
        try:
            if REDIS_URL:
                self.client = redis.from_url(
                    REDIS_URL,
                    decode_responses=True,
                    socket_connect_timeout=5
                )
                self.client.ping()
                print("✓ Redis (Upstash) conectado vía URL")
            else:
                self.client = redis.Redis(
                    host=REDIS_HOST,
                    port=REDIS_PORT,
                    db=REDIS_DB,
                    password=REDIS_PASSWORD,
                    decode_responses=True,
                    socket_connect_timeout=5
                )
                self.client.ping()
                print(f"✓ Redis conectado en {REDIS_HOST}:{REDIS_PORT}")
        except redis.ConnectionError as e:
            print(f"⚠ Redis no disponible: {e}. Modo degradado activado.")
            self.client = None
    
    def is_available(self) -> bool:
        """Verifica si Redis está disponible."""
        if self.client is None:
            return False
        try:
            self.client.ping()
            return True
        except:
            return False
    
    # =================== ALERTAS ACTIVAS ===================
    
    def cache_alerta(self, alerta_id: str, alerta_data: Dict[str, Any], ttl: int = ALERT_TTL):
        """
        Almacena una alerta en caché.
        
        Args:
            alerta_id: ID único de la alerta
            alerta_data: Datos de la alerta (dict)
            ttl: Tiempo de vida en segundos
        """
        if not self.is_available():
            return
        
        try:
            key = f"alerta:{alerta_id}"
            self.client.setex(key, ttl, json.dumps(alerta_data))
        except Exception as e:
            print(f"Error cacheando alerta {alerta_id}: {e}")
    
    def get_alerta_cached(self, alerta_id: str) -> Optional[Dict[str, Any]]:
        """Obtiene una alerta desde caché."""
        if not self.is_available():
            return None
        
        try:
            key = f"alerta:{alerta_id}"
            data = self.client.get(key)
            return json.loads(data) if data else None
        except Exception as e:
            print(f"Error obteniendo alerta {alerta_id}: {e}")
            return None
    
    def delete_alerta_cached(self, alerta_id: str):
        """Elimina una alerta del caché."""
        if not self.is_available():
            return
        
        try:
            key = f"alerta:{alerta_id}"
            self.client.delete(key)
        except Exception as e:
            print(f"Error eliminando alerta {alerta_id}: {e}")
    
    # =================== ALERTAS POR MEDICAMENTO ===================
    
    def cache_alertas_medicamento(self, medicamento_id: str, alertas: List[str], ttl: int = ALERT_TTL):
        """
        Almacena lista de IDs de alertas para un medicamento.
        
        Args:
            medicamento_id: ID del medicamento
            alertas: Lista de IDs de alertas
            ttl: Tiempo de vida en segundos
        """
        if not self.is_available():
            return
        
        try:
            key = f"med_alertas:{medicamento_id}"
            self.client.setex(key, ttl, json.dumps(alertas))
        except Exception as e:
            print(f"Error cacheando alertas de medicamento {medicamento_id}: {e}")
    
    def get_alertas_medicamento_cached(self, medicamento_id: str) -> Optional[List[str]]:
        """Obtiene lista de alertas de un medicamento desde caché."""
        if not self.is_available():
            return None
        
        try:
            key = f"med_alertas:{medicamento_id}"
            data = self.client.get(key)
            return json.loads(data) if data else None
        except Exception as e:
            print(f"Error obteniendo alertas de medicamento {medicamento_id}: {e}")
            return None
    
    # =================== NOTIFICACIONES ===================
    
    def push_notification(self, user_role: str, notification: Dict[str, Any]):
        """
        Agrega una notificación a la cola de un rol de usuario.
        
        Args:
            user_role: Rol del usuario (admin, farmaceutico, compras)
            notification: Datos de la notificación
        """
        if not self.is_available():
            return
        
        try:
            queue_key = f"notifications:{user_role}"
            self.client.rpush(queue_key, json.dumps(notification))
            # Limitar tamaño de la cola a las últimas 100 notificaciones
            self.client.ltrim(queue_key, -100, -1)
        except Exception as e:
            print(f"Error agregando notificación para {user_role}: {e}")
    
    def sync_notifications_from_db(self, db_session, alertas_activas: List[Any]):
        """
        Sincroniza notificaciones desde la BD a Redis.
        Se llama al iniciar el backend para cargar alertas existentes.
        
        Args:
            db_session: Sesión de la BD
            alertas_activas: Lista de alertas activas desde la BD
        """
        if not self.is_available():
            return
        
        try:
            # Importar aquí para evitar dependencias circulares
            from database.models import TipoAlertaEnum, Medicamento
            
            # Limpiar notificaciones existentes
            for role in ['admin', 'compras', 'farmaceutico']:
                self.clear_notifications(role)
            
            print("Sincronizando notificaciones desde BD a Redis...")
            
            # Agrupar alertas por tipo
            alertas_stock = []
            alertas_vencimiento = []
            alertas_ordenes = []
            
            for alerta in alertas_activas:
                if alerta.tipo in [TipoAlertaEnum.STOCK_MINIMO, TipoAlertaEnum.STOCK_CRITICO, TipoAlertaEnum.STOCK_AGOTADO]:
                    alertas_stock.append(alerta)
                elif alerta.tipo == TipoAlertaEnum.ORDEN_RETRASADA:
                    alertas_ordenes.append(alerta)
                else:
                    alertas_vencimiento.append(alerta)
            
            # Sincronizar alertas de stock (para admin y compras)
            for alerta in alertas_stock:
                med = db_session.query(Medicamento).filter(Medicamento.id == alerta.medicamento_id).first()
                if med:
                    notif = {
                        'alert_id': str(alerta.id),
                        'event_type': 'created',
                        'alert_type': alerta.tipo.value,
                        'priority': alerta.prioridad.value,
                        'mensaje': alerta.mensaje,
                        'medicamento_nombre': med.nombre,
                        'medicamento_fabricante': med.fabricante or '',
                        'medicamento_presentacion': med.presentacion or '',
                        'medicamento_lote': med.lote or '',
                        'timestamp': alerta.created_at.isoformat() if alerta.created_at else ''
                    }
                    self.push_notification('admin', notif)
                    self.push_notification('compras', notif)
            
            # Sincronizar alertas de vencimiento (para admin y farmaceutico)
            for alerta in alertas_vencimiento:
                med = db_session.query(Medicamento).filter(Medicamento.id == alerta.medicamento_id).first()
                if med:
                    notif = {
                        'alert_id': str(alerta.id),
                        'event_type': 'created',
                        'alert_type': alerta.tipo.value,
                        'priority': alerta.prioridad.value,
                        'mensaje': alerta.mensaje,
                        'medicamento_nombre': med.nombre,
                        'medicamento_fabricante': med.fabricante or '',
                        'medicamento_presentacion': med.presentacion or '',
                        'medicamento_lote': med.lote or '',
                        'timestamp': alerta.created_at.isoformat() if alerta.created_at else ''
                    }
                    self.push_notification('admin', notif)
                    self.push_notification('farmaceutico', notif)
            
            # Sincronizar alertas de órdenes retrasadas (para admin y compras)
            for alerta in alertas_ordenes:
                notif = {
                    'alert_id': str(alerta.id),
                    'event_type': 'created',
                    'alert_type': alerta.tipo.value,
                    'priority': alerta.prioridad.value,
                    'mensaje': alerta.mensaje,
                    'medicamento_nombre': alerta.metadatos.get('numero_orden', 'Orden'),
                    'medicamento_fabricante': alerta.metadatos.get('proveedor_nombre', ''),
                    'medicamento_presentacion': f"{alerta.metadatos.get('dias_retraso', 0)} días de retraso",
                    'medicamento_lote': '',
                    'timestamp': alerta.created_at.isoformat() if alerta.created_at else ''
                }
                self.push_notification('admin', notif)
                self.push_notification('compras', notif)
            
            print(f"Redis sincronizado: {len(alertas_stock)} alertas stock, {len(alertas_vencimiento)} alertas vencimiento, {len(alertas_ordenes)} alertas ordenes")
            
        except Exception as e:
            print(f"[WARNING] Error sincronizando notificaciones: {e}")
    
    def remove_notification(self, user_role: str, alert_id: str):
        """
        Elimina una notificación específica de la cola de un rol.
        Se llama cuando se resuelve una alerta.
        
        Args:
            user_role: Rol del usuario
            alert_id: ID de la alerta a eliminar
        """
        if not self.is_available():
            return
        
        try:
            queue_key = f"notifications:{user_role}"
            notifications = self.client.lrange(queue_key, 0, -1)
            
            # Filtrar la notificación a eliminar
            for notif_json in notifications:
                notif = json.loads(notif_json)
                if notif.get('alert_id') == alert_id:
                    self.client.lrem(queue_key, 1, notif_json)
                    break
        except Exception as e:
            print(f"Error eliminando notificación {alert_id} para {user_role}: {e}")
    
    def get_notifications(self, user_role: str, count: int = 10) -> List[Dict[str, Any]]:
        """
        Obtiene las últimas notificaciones de un rol.
        
        Args:
            user_role: Rol del usuario
            count: Cantidad de notificaciones a obtener
        
        Returns:
            Lista de notificaciones (más recientes primero)
        """
        if not self.is_available():
            return []
        
        try:
            queue_key = f"notifications:{user_role}"
            notifications = self.client.lrange(queue_key, -count, -1)
            # Invertir para mostrar más recientes primero
            return [json.loads(n) for n in reversed(notifications)]
        except Exception as e:
            print(f"Error obteniendo notificaciones para {user_role}: {e}")
            return []
    
    def clear_notifications(self, user_role: str):
        """Limpia todas las notificaciones de un rol."""
        if not self.is_available():
            return
        
        try:
            queue_key = f"notifications:{user_role}"
            self.client.delete(queue_key)
        except Exception as e:
            print(f"Error limpiando notificaciones para {user_role}: {e}")
    
    # =================== CONTADORES ===================
    
    def increment_alert_count(self, alert_type: str):
        """Incrementa contador de alertas por tipo."""
        if not self.is_available():
            return
        
        try:
            key = f"alert_count:{alert_type}"
            self.client.incr(key)
        except Exception as e:
            print(f"Error incrementando contador {alert_type}: {e}")
    
    def get_alert_count(self, alert_type: str) -> int:
        """Obtiene contador de alertas por tipo."""
        if not self.is_available():
            return 0
        
        try:
            key = f"alert_count:{alert_type}"
            count = self.client.get(key)
            return int(count) if count else 0
        except Exception as e:
            print(f"Error obteniendo contador {alert_type}: {e}")
            return 0
    
    def reset_alert_count(self, alert_type: str):
        """Resetea contador de alertas por tipo."""
        if not self.is_available():
            return
        
        try:
            key = f"alert_count:{alert_type}"
            self.client.delete(key)
        except Exception as e:
            print(f"Error reseteando contador {alert_type}: {e}")
    
    # =================== UTILIDADES ===================
    
    def flush_all(self):
        """Limpia toda la base de datos Redis (solo para desarrollo/testing)."""
        if not self.is_available():
            return
        
        try:
            self.client.flushdb()
            print("Redis: Base de datos limpiada")
        except Exception as e:
            print(f"Error limpiando Redis: {e}")


# Instancia global de Redis
redis_client = RedisClient()

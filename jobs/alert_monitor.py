"""
job automático para monitoreo de alertas.
hu-2: Sistema de alertas de stock automatizado.

utiliza APScheduler para ejecutar escaneos periódicos de:
- Stock bajo(hu-2.01)
- Vencimientos próximos(hu-2.02)
"""
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger
from datetime import datetime
from database.connection import SessionLocal
from services.alert_service import AlertService
from observers.alert_observer import setup_alert_observers
from database.redis_client import redis_client
import os


class AlertMonitor:
    """
    Monitor automático de alertas que ejecuta escaneos periódicos.
    
    Funcionalidades:
    - Escaneo de stock bajo cada N minutos
    - Escaneo de vencimientos diariamente
    - Configuración flexible de intervalos
    - Manejo de errores y recuperación
    """
    
    def __init__(self):
        self.scheduler = BackgroundScheduler(timezone='America/Bogota')
        self.is_running = False
        
        #configuración de intervalos (desde variables de entorno o defaults)
        self.stock_scan_interval = int(os.getenv('ALERT_STOCK_INTERVAL_MINUTES', 15))
        self.expiration_scan_hour = int(os.getenv('ALERT_EXPIRATION_HOUR', 8))  # 8 AM
        self.expiration_anticipation_days = int(os.getenv('ALERT_EXPIRATION_DAYS', 30))
    
    def start(self):
        """Inicia el monitor de alertas."""
        if self.is_running:
            return
        
        #configurar observadores
        db = SessionLocal()
        try:
            setup_alert_observers(
                redis_client=redis_client,
                db_session=db,
                enable_console_log=os.getenv('ALERT_CONSOLE_LOG', 'false').lower() == 'true'
            )
        finally:
            db.close()
        
        #job 1: escaneo de stock cada N minutos
        self.scheduler.add_job(
            func=self._scan_stock_job,
            trigger=IntervalTrigger(minutes=self.stock_scan_interval),
            id='scan_stock',
            name='Escaneo de stock bajo',
            replace_existing=True
        )
        
        #job 2: escaneo de vencimientos diariamente
        self.scheduler.add_job(
            func=self._scan_expiration_job,
            trigger=CronTrigger(hour=self.expiration_scan_hour, minute=0),
            id='scan_expiration',
            name='Escaneo de vencimientos',
            replace_existing=True
        )
        
        #iniciar scheduler
        self.scheduler.start()
        self.is_running = True
        
        #ejecutar primer escaneo inmediatamente
        self._scan_stock_job()
        self._scan_expiration_job()
    
    def stop(self):
        """Detiene el monitor de alertas."""
        if not self.is_running:
            return
        
        self.scheduler.shutdown()
        self.is_running = False
    
    def _scan_stock_job(self):
        """
        Job que escanea alertas de stock.
        HU-2.01: Monitoreo automático de niveles de stock.
        """
        db = SessionLocal()
        try:
            service = AlertService(db)
            
            stats = service.scan_stock_alerts()
            
            """
            print(f"✓ Escaneo de stock completado:")
            print(f"  - Medicamentos escaneados: {stats['scanned']}")
            print(f"  - Alertas creadas: {stats['alerts_created']}")
            print(f"  - Alertas actualizadas: {stats['alerts_updated']}")
            print(f"  - Alertas resueltas: {stats['alerts_resolved']}")
            """

        except Exception as e:
            #print(f"Error en escaneo de stock: {e}")
            import traceback
            traceback.print_exc()
        finally:
            db.close()
    
    def _scan_expiration_job(self):
        """
        Job que escanea alertas de vencimiento.
        HU-2.02: Detección de medicamentos próximos a vencer.
        """
        db = SessionLocal()
        try:
            service = AlertService(db)
            
            #print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Iniciando escaneo de vencimientos...")
            
            stats = service.scan_expiration_alerts(
                dias_anticipacion=self.expiration_anticipation_days
            )
            
            """
            print(f"Escaneo de vencimientos completado:")
            print(f"  - Medicamentos escaneados: {stats['scanned']}")
            print(f"  - Alertas creadas: {stats['alerts_created']}")
            print(f"  - Alertas actualizadas: {stats['alerts_updated']}")
            """
            
        except Exception as e:
            #print(f"Error en escaneo de vencimientos: {e}")
            import traceback
            traceback.print_exc()
        finally:
            db.close()
    
    def get_status(self) -> dict:
        """Obtiene el estado actual del monitor."""
        jobs = []
        if self.is_running:
            for job in self.scheduler.get_jobs():
                jobs.append({
                    'id': job.id,
                    'name': job.name,
                    'next_run': job.next_run_time.isoformat() if job.next_run_time else None
                })
        
        return {
            'running': self.is_running,
            'jobs': jobs,
            'config': {
                'stock_scan_interval_minutes': self.stock_scan_interval,
                'expiration_scan_hour': self.expiration_scan_hour,
                'expiration_anticipation_days': self.expiration_anticipation_days
            }
        }


# Instancia global del monitor
alert_monitor = AlertMonitor()

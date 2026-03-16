"""
Job programado para detección automática de órdenes retrasadas.
HU-4.02: Detección de retrasos

Este job se ejecuta diariamente y marca como RETRASADA
las órdenes en estado ENVIADA que ya pasaron su fecha prevista.
"""
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from database.connection import SessionLocal
from services.orden_compra_service import OrdenCompraService
from datetime import datetime


def detectar_ordenes_retrasadas():
    """
    Detecta y marca órdenes retrasadas.
    
    HU-4.02: "Given orden enviada con fecha prevista 2025-09-01,
              When hoy > 2025-09-01 y no recibida,
              Then generar alerta 'pedido retrasado'"
    
    Se ejecuta automáticamente todos los días a las 8:00 AM.
    NUEVO: También crea alertas y notifica a COMPRAS y ADMIN.
    """
    print(f"\n[{datetime.now()}] iniciando detección de órdenes retrasadas...")
    
    db = SessionLocal()
    try:
        service = OrdenCompraService(db)
        result = service.detectar_ordenes_retrasadas()
        
        if result['ok']:
            count = result['ordenes_marcadas']
            alertas = result.get('alertas_creadas', 0)
            
            if count > 0:
                print(f"se marcaron {count} órdenes como RETRASADAS")
                if alertas > 0:
                    print(f"Se crearon {alertas} alertas y se notificó a roles COMPRAS y ADMIN")
            else:
                print("No se encontraron órdenes retrasadas")
        else:
            print(f"Error en detección: {result['error']}")
            
    except Exception as e:
        print(f"Error ejecutando job de retrasos: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()


class OrdenMonitor:
    """
    Monitor de órdenes de compra con scheduler automático.
    """
    
    def __init__(self):
        self.scheduler = BackgroundScheduler()
        self._setup_jobs()
    
    def _setup_jobs(self):
        """Configura los jobs programados."""
        # Job cada hora: Detectar órdenes retrasadas
        # MODIFICADO: Se ejecuta cada hora (minuto 0) para detección más frecuente
        # Antes: Solo diario a las 8:00 AM
        # Ahora: Cada hora durante el horario laboral (8:00 AM - 6:00 PM)
        self.scheduler.add_job(
            detectar_ordenes_retrasadas,
            CronTrigger(hour='8-18', minute=0),  # Cada hora de 8 AM a 6 PM
            id='detectar_retrasos',
            name='Detectar Órdenes Retrasadas',
            replace_existing=True
        )
        
        print("Job de detección de retrasos programado (cada hora de 8:00 AM a 6:00 PM)")
    
    def start(self):
        """Inicia el scheduler."""
        if not self.scheduler.running:
            self.scheduler.start()
            print("Monitor de órdenes iniciado")
    
    def stop(self):
        """Detiene el scheduler."""
        if self.scheduler.running:
            self.scheduler.shutdown()
            print("Monitor de órdenes detenido")
    
    def run_now(self):
        """Ejecuta la detección inmediatamente (para testing o ejecución manual)."""
        print("\nEjecutando detección manual de retrasos...")
        detectar_ordenes_retrasadas()
    
    def get_job_info(self):
        """Obtiene información sobre los jobs programados."""
        jobs = self.scheduler.get_jobs()
        return [{
            'id': job.id,
            'name': job.name,
            'next_run': str(job.next_run_time) if job.next_run_time else 'No programado'
        } for job in jobs]


# Instancia global del monitor
orden_monitor = OrdenMonitor()

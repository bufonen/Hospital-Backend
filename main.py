from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi
import os
import uvicorn
from database.connection import engine, Base, get_db

from routes import medicamentos, auth, users, alertas, proveedores, ordenes, reportes, ventas
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pathlib import Path


from contextlib import asynccontextmanager


app = FastAPI(title="ProyectoInvMedicamentos API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(medicamentos.router, prefix="/api/medicamentos", tags=["medicamentos"])
app.include_router(users.router, prefix="/api/users", tags=["users"])
app.include_router(alertas.router, prefix="/api/alertas", tags=["alertas"])
app.include_router(proveedores.router, prefix="/api/proveedores", tags=["proveedores"])
app.include_router(ordenes.router, prefix="/api/ordenes", tags=["ordenes"])
app.include_router(reportes.router, prefix="/api/reportes", tags=["reportes"])
app.include_router(ventas.router, prefix="/api/ventas", tags=["ventas"])


@app.get("/")
async def root():
    return {"message": "API ProyectoInvMedicamentos"}


@asynccontextmanager
async def lifespan(app: FastAPI):
    #crea tablas
    Base.metadata.create_all(bind=engine)
    
    # Inicializar sistema de alertas
    from database.redis_client import redis_client
    from observers.alert_observer import setup_alert_observers
    from jobs.alert_monitor import alert_monitor

    # Configurar observadores
    db = next(get_db())
    try:
        setup_alert_observers(
            redis_client=redis_client,
            db_session=db,
            enable_console_log=os.getenv('ALERT_CONSOLE_LOG', 'false').lower() == 'true'
        )
        
        # Sincronizar notificaciones existentes desde BD a Redis
        from database.models import Alerta, EstadoAlertaEnum
        alertas_activas = db.query(Alerta).filter(Alerta.estado == EstadoAlertaEnum.ACTIVA).all()
        redis_client.sync_notifications_from_db(db, alertas_activas)
        
    finally:
        db.close()
    
    # Iniciar monitor de alertas automático
    try:
        alert_monitor.start()
    except Exception as e:
        print(f"Error iniciando alert monitor: {e}")
    
    # Iniciar monitor de órdenes de compra (HU-4.02)
    try:
        from jobs.orden_monitor import orden_monitor
        orden_monitor.start()
    except Exception as e:
        print(f"Error iniciando orden monitor: {e}")
    
    #print("="*60 + "\n")
    
    # Crear usuario admin si no existe
    try:
        from services.user_service import UserService
        from auth.passwords import hash_password

        db = next(get_db())
        usvc = UserService(db)
        admin_count = usvc.count_admins()
        if admin_count == 0:
            admin_user = os.getenv('ADMIN_USERNAME')
            admin_pass = os.getenv('ADMIN_PASSWORD')
            admin_email = os.getenv('ADMIN_EMAIL')
            if admin_user and admin_pass and admin_email:
                payload = {
                    'username': admin_user,
                    'full_name': 'Administrator',
                    'email': admin_email,
                    'hashed_password': hash_password(admin_pass),
                    'role': 'admin'
                }
                try:
                    usvc.create_admin(payload)
                    print('Admin creado exitosamente')
                except Exception as e:
                    print(f'Error al crear admin: {e}')
            else:
                print('Advertencia: No se creó admin porque no se proporcionaron variables de entorno.')
    except Exception as _:
        pass
    finally:
        db.close()
    
    yield
    
    # Cleanup al cerrar
    print("\nDeteniendo servicios...")
    try:
        alert_monitor.stop()
    except:
        pass
    try:
        from jobs.orden_monitor import orden_monitor
        orden_monitor.stop()
    except:
        pass


app.router.lifespan_context = lifespan

#sirve archivos estáticos del frontend cuando son publicados en backend/static
STATIC_DIR = Path(__file__).parent.joinpath('static')
if STATIC_DIR.exists():
    app.mount('/', StaticFiles(directory=str(STATIC_DIR), html=True), name='static')



if __name__ == '__main__':
    #correr programa con: pyton main.py
    host = os.getenv('HOST', '127.0.0.1')
    port = int(os.getenv('PORT', 8000))
    reload = os.getenv('RELOAD', 'True').lower() in ('1','true','yes')
    print(f"Starting uvicorn on {host}:{port} (reload={reload})")
    uvicorn.run('main:app', host=host, port=port, reload=reload)

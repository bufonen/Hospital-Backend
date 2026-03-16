"""
Endpoints completos para sistema de alertas automatizado con Observer y Redis.
HU-2: Sistema de alertas de stock automatizado.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func, desc
from database.connection import get_db
from database.models import Alerta, Medicamento, TipoAlertaEnum, EstadoAlertaEnum, PrioridadAlertaEnum
from schemas.alerta import (
    AlertaOut, AlertaWithMedicamento, AlertaUpdateEstado, 
    AlertaStats, NotificacionOut, ScanResultOut
)
from services.alert_service import AlertService
from database.redis_client import redis_client
from auth.security import get_current_user, is_admin
from typing import List, Optional
from datetime import datetime, date, timedelta
from decimal import Decimal

router = APIRouter()


# ALERTAS ACTIVAS

@router.get("/activas", response_model=List[AlertaWithMedicamento])
def get_alertas_activas(
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
    tipo: Optional[TipoAlertaEnum] = None,
    prioridad: Optional[PrioridadAlertaEnum] = None,
    limit: int = 100
):
    """
    Obtiene listado de alertas activas con información del medicamento.
    HU-2.01 y HU-2.02: Consultar alertas activas filtradas por rol.
    
    Filtros opcionales:
    - tipo: Filtrar por tipo de alerta
    - prioridad: Filtrar por prioridad
    - limit: Máximo de resultados (default 100)
    
    Filtrado por rol:
    - compras: Solo alertas de stock (STOCK_MINIMO, STOCK_CRITICO, STOCK_AGOTADO)
    - farmaceutico: Solo alertas de vencimiento (VENCIMIENTO_PROXIMO, VENCIMIENTO_INMEDIATO, VENCIDO)
    - admin: Todas las alertas
    """
    service = AlertService(db)
    alertas = service.get_active_alerts(tipo=tipo, prioridad=prioridad)
    
    # Filtrar por rol del usuario
    user_role = user.get('role', '').lower()
    
    if user_role == 'compras':
        # Compras: Alertas de stock Y órdenes retrasadas
        alertas = [a for a in alertas if a.tipo in [
            TipoAlertaEnum.STOCK_MINIMO, 
            TipoAlertaEnum.STOCK_CRITICO, 
            TipoAlertaEnum.STOCK_AGOTADO,
            TipoAlertaEnum.ORDEN_RETRASADA
        ]]
    elif user_role == 'farmaceutico':
        # Farmacéutico: Solo alertas de vencimiento
        alertas = [a for a in alertas if a.tipo in [
            TipoAlertaEnum.VENCIMIENTO_PROXIMO, 
            TipoAlertaEnum.VENCIMIENTO_INMEDIATO, 
            TipoAlertaEnum.VENCIDO
        ]]
    # Admin: no filtra, ve todas las alertas
    
    #información del medicamento o de la orden
    result = []
    for alerta in alertas[:limit]:
        if alerta.medicamento_id:
            # Alerta de medicamento
            med = db.query(Medicamento).filter(Medicamento.id == alerta.medicamento_id).first()
            if med:
                alerta_dict = {
                    **alerta.__dict__,
                    'medicamento_nombre': med.nombre,
                    'medicamento_presentacion': med.presentacion,
                    'medicamento_fabricante': med.fabricante,
                    'medicamento_lote': med.lote
                }
                result.append(AlertaWithMedicamento(**alerta_dict))
        else:
            # Alerta de orden (sin medicamento asociado)
            metadatos = alerta.metadatos or {}
            alerta_dict = {
                **alerta.__dict__,
                'medicamento_nombre': metadatos.get('numero_orden', 'Orden de compra'),
                'medicamento_presentacion': f"{metadatos.get('dias_retraso', 0)} días de retraso",
                'medicamento_fabricante': metadatos.get('proveedor_nombre', ''),
                'medicamento_lote': metadatos.get('proveedor_nit', '')
            }
            result.append(AlertaWithMedicamento(**alerta_dict))
    
    return result


@router.get("/historial", response_model=List[AlertaWithMedicamento])
def get_historial_alertas(
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
    medicamento_id: Optional[str] = None,
    estado: Optional[EstadoAlertaEnum] = None,
    fecha_desde: Optional[date] = None,
    fecha_hasta: Optional[date] = None,
    limit: int = 100
):
    """
    Obtiene historial completo de alertas filtrado por rol.
    HU-2.02: Mantener historial de alertas generadas con fecha, tipo, usuario y acción.
    
    Filtros opcionales:
    - medicamento_id: Filtrar por medicamento específico
    - estado: Filtrar por estado (ACTIVA, PENDIENTE_REPOSICION, RESUELTA)
    - fecha_desde: Fecha inicio
    - fecha_hasta: Fecha fin
    - limit: Máximo de resultados
    
    Filtrado por rol:
    - compras: Solo alertas de stock
    - farmaceutico: Solo alertas de vencimiento
    - admin: Todas las alertas
    """
    q = db.query(Alerta)
    
    # Filtrar por rol del usuario
    user_role = user.get('role', '').lower()
    
    if user_role == 'compras':
        # Compras: Alertas de stock Y órdenes retrasadas
        q = q.filter(Alerta.tipo.in_([
            TipoAlertaEnum.STOCK_MINIMO, 
            TipoAlertaEnum.STOCK_CRITICO, 
            TipoAlertaEnum.STOCK_AGOTADO,
            TipoAlertaEnum.ORDEN_RETRASADA
        ]))
    elif user_role == 'farmaceutico':
        # Farmacéutico: Solo alertas de vencimiento
        q = q.filter(Alerta.tipo.in_([
            TipoAlertaEnum.VENCIMIENTO_PROXIMO, 
            TipoAlertaEnum.VENCIMIENTO_INMEDIATO, 
            TipoAlertaEnum.VENCIDO
        ]))
    # Admin: No filtra, ve todas las alertas
    
    if medicamento_id:
        q = q.filter(Alerta.medicamento_id == medicamento_id)
    
    if estado:
        q = q.filter(Alerta.estado == estado)
    
    if fecha_desde:
        q = q.filter(Alerta.created_at >= fecha_desde)
    
    if fecha_hasta:
        q = q.filter(Alerta.created_at <= fecha_hasta)
    
    alertas = q.order_by(desc(Alerta.created_at)).limit(limit).all()
    
    # Enriquecer con información del medicamento o de la orden
    result = []
    for alerta in alertas:
        if alerta.medicamento_id:
            # Alerta de medicamento
            med = db.query(Medicamento).filter(Medicamento.id == alerta.medicamento_id).first()
            if med:
                alerta_dict = {
                    **alerta.__dict__,
                    'medicamento_nombre': med.nombre,
                    'medicamento_presentacion': med.presentacion,
                    'medicamento_fabricante': med.fabricante,
                    'medicamento_lote': med.lote
                }
                result.append(AlertaWithMedicamento(**alerta_dict))
        else:
            # Alerta de orden (sin medicamento asociado)
            metadatos = alerta.metadatos or {}
            alerta_dict = {
                **alerta.__dict__,
                'medicamento_nombre': metadatos.get('numero_orden', 'Orden de compra'),
                'medicamento_presentacion': f"{metadatos.get('dias_retraso', 0)} días de retraso",
                'medicamento_fabricante': metadatos.get('proveedor_nombre', ''),
                'medicamento_lote': metadatos.get('proveedor_nit', '')
            }
            result.append(AlertaWithMedicamento(**alerta_dict))
    
    return result


# ACTUALIZACIÓN DE ESTADO

@router.patch("/{alerta_id}/estado", response_model=AlertaOut)
def actualizar_estado_alerta(
    alerta_id: str,
    payload: AlertaUpdateEstado,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user)
):
    """
    Actualiza el estado de una alerta.
    HU-2.01 y HU-2.02: Usuario marca alerta como resuelta o pendiente de reposición.
    
    Estados posibles:
    - ACTIVA
    - PENDIENTE_REPOSICION
    - RESUELTA
    """
    service = AlertService(db)
    
    alerta = db.query(Alerta).filter(Alerta.id == alerta_id).first()
    if not alerta:
        raise HTTPException(status_code=404, detail="Alerta no encontrada")
    
    # Si se marca como resuelta
    if payload.estado == EstadoAlertaEnum.RESUELTA:
        success = service.resolve_alert(alerta_id, user.get('sub'))
        if not success:
            raise HTTPException(status_code=400, detail="No se pudo resolver la alerta")
    else:
        # Actualizar estado manualmente
        alerta.estado = payload.estado
        if payload.notas:
            alerta.metadatos = alerta.metadatos or {}
            alerta.metadatos['notas'] = payload.notas
        db.commit()
        db.refresh(alerta)
    
    return alerta


#NOTIFICACIONES

@router.get("/notificaciones/mis-alertas", response_model=List[NotificacionOut])
def get_mis_notificaciones(
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
    count: int = Query(default=10, le=100)
):
    """
    Obtiene notificaciones desde Redis (caché sincronizado) con fallback a BD.
    HU-2: Notificaciones automáticas diferenciadas a usuarios autorizados.
    
    Estrategia híbrida:
    1. Intenta obtener desde Redis (rápido)
    2. Si Redis vacío o no disponible, consulta BD y sincroniza
    
    Filtrado por rol:
    - admin: Todas las alertas activas
    - compras: Alertas de stock activas
    - farmaceutico: Alertas de vencimiento activas
    """
    user_role = user.get('role', '').lower()
    
    # Intentar obtener desde Redis
    notifications_from_redis = redis_client.get_notifications(user_role, count=count)
    
    # Si Redis tiene notificaciones, usarlas
    if notifications_from_redis:
        # Validar que las notificaciones en Redis aún estén activas en BD
        validated_notifications = []
        for notif in notifications_from_redis:
            alert_id = notif.get('alert_id')
            if alert_id:
                alerta = db.query(Alerta).filter(Alerta.id == alert_id).first()
                if alerta and alerta.estado == EstadoAlertaEnum.ACTIVA:
                    validated_notifications.append(notif)
        
        # Si encontramos notificaciones válidas, retornarlas
        if validated_notifications:
            return [NotificacionOut(**n) for n in validated_notifications[:count]]
    
    # Fallback: Redis vacío o notificaciones inválidas
    print(f"Redis sin notificaciones para {user_role}")
    
    # Determinar tipos de alerta según rol
    if user_role == 'compras':
        tipos_permitidos = [
            TipoAlertaEnum.STOCK_MINIMO,
            TipoAlertaEnum.STOCK_CRITICO,
            TipoAlertaEnum.STOCK_AGOTADO,
            TipoAlertaEnum.ORDEN_RETRASADA
        ]
    elif user_role == 'farmaceutico':
        tipos_permitidos = [
            TipoAlertaEnum.VENCIMIENTO_PROXIMO,
            TipoAlertaEnum.VENCIMIENTO_INMEDIATO,
            TipoAlertaEnum.VENCIDO
        ]
    else:
        # Admin: Todos los tipos
        tipos_permitidos = list(TipoAlertaEnum)
    
    # Consultar alertas activas desde la BD
    alertas = db.query(Alerta).filter(
        and_(
            Alerta.estado == EstadoAlertaEnum.ACTIVA,
            Alerta.tipo.in_(tipos_permitidos)
        )
    ).order_by(desc(Alerta.created_at)).limit(count).all()
    
    # Construir notificaciones y sincronizar a Redis
    active_notifications = []
    for alerta in alertas:
        med = db.query(Medicamento).filter(Medicamento.id == alerta.medicamento_id).first()
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
                'timestamp': alerta.created_at.isoformat() if alerta.created_at else datetime.now().isoformat()
            }
            active_notifications.append(notif)
            
            # Re-sincronizar a Redis
            redis_client.push_notification(user_role, notif)
            if user_role != 'admin':
                redis_client.push_notification('admin', notif)
    
    return [NotificacionOut(**n) for n in active_notifications]


@router.delete("/notificaciones/limpiar")
def limpiar_notificaciones(
    user: dict = Depends(get_current_user)
):
    """
    Limpia todas las notificaciones del usuario actual.
    """
    user_role = user.get('role', 'farmaceutico')
    redis_client.clear_notifications(user_role)
    
    return {"message": "Notificaciones limpiadas exitosamente"}


# ESTADÍSTICAS

@router.get("/stats/resumen", response_model=AlertaStats)
def get_estadisticas_alertas(
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user)
):
    """
    Obtiene estadísticas resumidas de alertas filtradas por rol.
    HU-2: Dashboard con información de alertas.
    
    Filtrado por rol:
    - compras: Solo estadísticas de alertas de stock
    - farmaceutico: Solo estadísticas de alertas de vencimiento
    - admin: Todas las estadísticas
    """
    user_role = user.get('role', '').lower()
    
    # Determinar tipos de alerta según rol
    if user_role == 'compras':
        tipos_permitidos = [
            TipoAlertaEnum.STOCK_MINIMO,
            TipoAlertaEnum.STOCK_CRITICO,
            TipoAlertaEnum.STOCK_AGOTADO,
            TipoAlertaEnum.ORDEN_RETRASADA
        ]
    elif user_role == 'farmaceutico':
        tipos_permitidos = [
            TipoAlertaEnum.VENCIMIENTO_PROXIMO,
            TipoAlertaEnum.VENCIMIENTO_INMEDIATO,
            TipoAlertaEnum.VENCIDO
        ]
    else:
        # Admin: Todos los tipos
        tipos_permitidos = list(TipoAlertaEnum)
    
    # Base query con filtro de tipo según rol
    base_query = db.query(Alerta).filter(Alerta.tipo.in_(tipos_permitidos))
    
    # Total activas (filtrado por rol)
    total_activas = base_query.filter(Alerta.estado == EstadoAlertaEnum.ACTIVA).count()
    
    # Por tipo (solo los permitidos para este rol)
    por_tipo = {}
    for tipo in tipos_permitidos:
        count = base_query.filter(
            and_(Alerta.tipo == tipo, Alerta.estado == EstadoAlertaEnum.ACTIVA)
        ).count()
        por_tipo[tipo.value] = count
    
    # Por prioridad (filtrado por rol)
    por_prioridad = {}
    for prioridad in PrioridadAlertaEnum:
        count = base_query.filter(
            and_(Alerta.prioridad == prioridad, Alerta.estado == EstadoAlertaEnum.ACTIVA)
        ).count()
        por_prioridad[prioridad.value] = count
    
    # Por estado (filtrado por rol)
    por_estado = {}
    for estado in EstadoAlertaEnum:
        count = base_query.filter(Alerta.estado == estado).count()
        por_estado[estado.value] = count
    
    # Últimas 24 horas (filtrado por rol)
    hace_24h = datetime.now() - timedelta(hours=24)
    creadas_hoy = base_query.filter(Alerta.created_at >= hace_24h).count()
    
    # Contar resueltas hoy (filtrado por rol)
    resueltas_hoy = base_query.filter(
        and_(
            Alerta.estado == EstadoAlertaEnum.RESUELTA,
            or_(
                Alerta.resuelta_at >= hace_24h,
                and_(Alerta.resuelta_at.is_(None), Alerta.updated_at >= hace_24h)
            )
        )
    ).count()
    
    return AlertaStats(
        total_activas=total_activas,
        por_tipo=por_tipo,
        por_prioridad=por_prioridad,
        por_estado=por_estado,
        creadas_hoy=creadas_hoy,
        resueltas_hoy=resueltas_hoy
    )


# VERIFICACIÓN EN TIEMPO REAL

@router.post("/check/{medicamento_id}")
def verificar_alertas_medicamento(
    medicamento_id: str,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user)
):
    """
    Verifica y genera alertas para un medicamento específico EN TIEMPO REAL.
    Útil para forzar verificación después de operaciones manuales.
    
    Este endpoint hace lo mismo que se ejecuta automáticamente al:
    - Crear medicamento
    - Actualizar medicamento (stock, minimo_stock, fecha_vencimiento)
    - Registrar movimiento (entrada/salida)
    - Reactivar medicamento
    """
    service = AlertService(db)
    result = service.check_medicamento_alerts(medicamento_id)
    
    return {
        "medicamento_id": medicamento_id,
        "verificacion_completada": True,
        "resultados": result
    }


# ESCANEO MANUAL (ADMIN)

@router.post("/scan/stock", response_model=ScanResultOut)
def escanear_stock_manual(
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user)
):
    """
    Ejecuta escaneo manual de alertas de stock.
    Solo para administradores.
    HU-2.01: Monitoreo automático de stock.
    """
    if not is_admin(user):
        raise HTTPException(status_code=403, detail="Acceso denegado. Solo administradores.")
    
    service = AlertService(db)
    stats = service.scan_stock_alerts()
    
    return ScanResultOut(
        scan_type='stock',
        timestamp=datetime.now(),
        **stats
    )


@router.post("/scan/vencimientos", response_model=ScanResultOut)
def escanear_vencimientos_manual(
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
    dias_anticipacion: int = Query(default=30, ge=1, le=365)
):
    """
    Ejecuta escaneo manual de alertas de vencimiento.
    Solo para administradores.
    HU-2.02: Detección de vencimientos próximos.
    """
    if not is_admin(user):
        raise HTTPException(status_code=403, detail="Acceso denegado. Solo administradores.")
    
    service = AlertService(db)
    stats = service.scan_expiration_alerts(dias_anticipacion=dias_anticipacion)
    
    return ScanResultOut(
        scan_type='expiration',
        timestamp=datetime.now(),
        **stats
    )


# DASHBOARD

from pydantic import BaseModel

class DashboardStats(BaseModel):
    """Estadísticas para el dashboard principal (legacy)."""
    total_medicamentos_activos: int
    medicamentos_stock_bajo: int
    medicamentos_agotados: int
    medicamentos_proximos_vencer_30_dias: int
    medicamentos_vencidos: int
    valor_total_inventario: Decimal
    medicamentos_criticos: int
    
    # Nuevos campos con alertas persistentes
    alertas_activas_total: int
    alertas_criticas: int


@router.get("/dashboard", response_model=DashboardStats)
def dashboard_estadisticas(
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user)
):
    """
    Obtiene estadísticas completas para el dashboard principal.
    Combina datos de medicamentos y alertas persistentes.
    """
    from database.models import EstadoEnum
    
    hoy = date.today()
    fecha_30_dias = hoy + timedelta(days=30)
    
    # Total activos
    total_activos = db.query(Medicamento).filter(
        and_(
            Medicamento.is_deleted == False,
            Medicamento.estado == EstadoEnum.ACTIVO
        )
    ).count()
    
    # Stock bajo
    stock_bajo = db.query(Medicamento).filter(
        and_(
            Medicamento.is_deleted == False,
            Medicamento.estado == EstadoEnum.ACTIVO,
            Medicamento.stock <= Medicamento.minimo_stock,
            Medicamento.stock > 0
        )
    ).count()
    
    # Agotados
    agotados = db.query(Medicamento).filter(
        and_(
            Medicamento.is_deleted == False,
            Medicamento.estado == EstadoEnum.ACTIVO,
            Medicamento.stock == 0
        )
    ).count()
    
    # Próximos a vencer
    proximos_vencer = db.query(Medicamento).filter(
        and_(
            Medicamento.is_deleted == False,
            Medicamento.estado == EstadoEnum.ACTIVO,
            Medicamento.fecha_vencimiento <= fecha_30_dias,
            Medicamento.fecha_vencimiento >= hoy
        )
    ).count()
    
    # Vencidos
    vencidos = db.query(Medicamento).filter(
        and_(
            Medicamento.is_deleted == False,
            Medicamento.estado == EstadoEnum.ACTIVO,
            Medicamento.fecha_vencimiento < hoy
        )
    ).count()
    
    # Valor total del inventario
    valor_total_result = db.query(
        func.sum(Medicamento.stock * Medicamento.precio)
    ).filter(
        and_(
            Medicamento.is_deleted == False,
            Medicamento.estado == EstadoEnum.ACTIVO
        )
    ).scalar()
    
    valor_total = Decimal(str(valor_total_result)) if valor_total_result else Decimal('0')
    
    # Alertas activas
    alertas_activas = db.query(Alerta).filter(Alerta.estado == EstadoAlertaEnum.ACTIVA).count()
    alertas_criticas = db.query(Alerta).filter(
        and_(
            Alerta.estado == EstadoAlertaEnum.ACTIVA,
            Alerta.prioridad == PrioridadAlertaEnum.CRITICA
        )
    ).count()
    
    criticos = stock_bajo + agotados + proximos_vencer + vencidos
    
    return DashboardStats(
        total_medicamentos_activos=total_activos,
        medicamentos_stock_bajo=stock_bajo,
        medicamentos_agotados=agotados,
        medicamentos_proximos_vencer_30_dias=proximos_vencer,
        medicamentos_vencidos=vencidos,
        valor_total_inventario=valor_total,
        medicamentos_criticos=criticos,
        alertas_activas_total=alertas_activas,
        alertas_criticas=alertas_criticas
    )


# DETALLE DE ALERTA (DEBE SER EL ÚLTIMO)

@router.get("/{alerta_id}", response_model=AlertaWithMedicamento)
def get_alerta_detalle(
    alerta_id: str,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user)
):
    """
    Obtiene detalle de una alerta específica con información del medicamento.
    
    IMPORTANTE: Este endpoint debe estar al final para no capturar
    rutas específicas como /dashboard, /stats, /scan, etc.
    """
    alerta = db.query(Alerta).filter(Alerta.id == alerta_id).first()
    
    if not alerta:
        raise HTTPException(status_code=404, detail="Alerta no encontrada")
    
    #información del medicamento o de la orden
    if alerta.medicamento_id:
        # Alerta de medicamento
        med = db.query(Medicamento).filter(Medicamento.id == alerta.medicamento_id).first()
        if not med:
            raise HTTPException(status_code=404, detail="Medicamento asociado no encontrado")
        
        alerta_dict = {
            **alerta.__dict__,
            'medicamento_nombre': med.nombre,
            'medicamento_presentacion': med.presentacion,
            'medicamento_fabricante': med.fabricante,
            'medicamento_lote': med.lote
        }
    else:
        # Alerta de orden (sin medicamento asociado)
        metadatos = alerta.metadatos or {}
        alerta_dict = {
            **alerta.__dict__,
            'medicamento_nombre': metadatos.get('numero_orden', 'Orden de compra'),
            'medicamento_presentacion': f"{metadatos.get('dias_retraso', 0)} días de retraso",
            'medicamento_fabricante': metadatos.get('proveedor_nombre', ''),
            'medicamento_lote': metadatos.get('proveedor_nit', '')
        }
    
    return AlertaWithMedicamento(**alerta_dict)

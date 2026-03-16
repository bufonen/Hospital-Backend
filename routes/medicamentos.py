from fastapi import APIRouter, Depends, HTTPException, status, Response
from sqlalchemy.orm import Session
from database.connection import get_db, engine
from database import models
from schemas.medicamento_v2 import MedicamentoCreate, MedicamentoOut, MedicamentoUpdate
from schemas.medicamento_short import MedicamentoShortOut
from auth.security import get_current_user, require_admin
from services.medicamento_service import MedicamentoService
from repositories.medicamento_repo import MedicamentoRepository
from fastapi import Depends
from schemas.response import MessageOut, DeleteOut, ReactivateOut
from typing import List, Optional
from enum import Enum
from sqlalchemy.exc import IntegrityError
from sqlalchemy import func
from utils.text import normalize_text
from utils.validators import validate_uuid
from schemas.movimiento import MovimientoCreate, MovimientoOut
from schemas.audit import AuditLogOut

router = APIRouter()


def get_medicamento_service(db: Session = Depends(get_db)) -> MedicamentoService:
    return MedicamentoService(db)


@router.post("/", response_model=MedicamentoOut)
def crear_medicamento(payload: MedicamentoCreate, response: Response, service: MedicamentoService = Depends(get_medicamento_service), db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    search_key = f"{normalize_text(payload.nombre)}|{normalize_text(payload.presentacion)}|{normalize_text(payload.fabricante)}"
    repo = MedicamentoRepository(db)
    existing_active = repo.find_by_search_key(search_key)
    if existing_active:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail={"error": "Medicamento duplicado", "existing_id": str(existing_active.id)})
    existing_any = repo.find_by_search_key(search_key, include_deleted=True, include_inactive=True)
    if existing_any:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail={"error": "Medicamento duplicado (inactivo)", "existing_id": str(existing_any.id), "message": "Existe un medicamento con los mismos datos pero inactivo. ¿Desea reactivarlo?"})

    from datetime import date, timedelta
    if payload.fecha_vencimiento < date.today():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Fecha inválida: la fecha de vencimiento no puede ser anterior a hoy.')
    if payload.fecha_vencimiento <= date.today() + timedelta(days=30):
        response.headers['X-Warning'] = 'Este medicamento está próximo a vencer, ¿Continuar?'

    payload_dict = payload.model_dump()
    payload_dict['search_key'] = search_key
    try:
        m = service.create_medicamento(payload_dict, user.get('sub') if user else None)
    except IntegrityError:
        existing = repo.find_by_search_key(search_key)
        if existing:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail={"error": "Medicamento duplicado", "existing_id": str(existing.id)})
        raise
    response.status_code = status.HTTP_201_CREATED
    return m


class SearchFilterEnum(str, Enum):
    nombre = 'nombre'
    principio_activo = 'principio_activo'
    lote = 'lote'
    fabricante = 'fabricante'


@router.get('/search', response_model=List[MedicamentoShortOut])
def search_med(query: Optional[str] = None, values: Optional[str] = None, filter: SearchFilterEnum = SearchFilterEnum.nombre, limit: int = 8, service: MedicamentoService = Depends(get_medicamento_service), user: dict = Depends(get_current_user)):
    qraw = query or values
    if not qraw:
        return []
    normalized = normalize_text(qraw)
    if filter == SearchFilterEnum.principio_activo:
        results = service.search_by_principio_activo(normalized, limit)
    elif filter == SearchFilterEnum.lote:
        results = service.search_by_lote(qraw, limit)
    elif filter == SearchFilterEnum.fabricante:
        results = service.search_by_fabricante(normalized, limit)
    else:
        results = service.search_by_nombre(normalized, limit)
    return results


@router.get('/', response_model=List[MedicamentoOut])
def listar_medicamentos(
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
    nombre: Optional[str] = None,
    fabricante: Optional[str] = None,
    lote: Optional[str] = None,
    estado: Optional[str] = None,
    fecha_vencimiento: Optional[str] = None,
    stock_bajo: Optional[bool] = None,
    limit: int = 100
):
    """Lista medicamentos con filtros opcionales.
    
    HU-1.01-CRUD y HU-1.03-Búsqueda
    
    Control de acceso por rol:
    - Sin filtros:
      * Admin: Ve TODOS los medicamentos (activos e inactivos)
      * Farmacéutico/Compras: Solo ve medicamentos ACTIVOS
    - Con filtro de estado INACTIVO:
      * Solo admin puede acceder (403 para otros roles)
    
    Filtros disponibles (opcionales):
    - nombre: Búsqueda parcial en nombre o presentación (case-insensitive, sin acentos)
    - fabricante: Búsqueda parcial en fabricante
    - lote: Búsqueda parcial en lote
    - estado: ACTIVO o INACTIVO (solo admin puede filtrar por INACTIVO)
    - fecha_vencimiento: YYYY-MM-DD para filtrar por fecha exacta
    - stock_bajo: true para ver solo medicamentos con stock <= stock_mínimo
    - limit: Máximo de resultados (default 100)
    
    Ejemplos:
    - GET /api/medicamentos/ → Admin: todos | Otros: solo activos
    - GET /api/medicamentos/?nombre=ibuprofeno → Busca por nombre
    - GET /api/medicamentos/?estado=ACTIVO → Filtra solo activos
    - GET /api/medicamentos/?estado=INACTIVO → Solo admin (403 para otros)
    - GET /api/medicamentos/?stock_bajo=true → Medicamentos con stock bajo
    """
    from auth.security import is_admin
    
    #Base query: nunca mostrar eliminados (is_deleted=True)
    q = db.query(models.Medicamento).filter(models.Medicamento.is_deleted == False)
    
    #Control de acceso por rol
    user_is_admin = is_admin(user)
    
    #Lógica de filtrado de estado
    if estado:
        #Si se especifica filtro de estado
        estado_upper = estado.upper()
        
        #Validar que el usuario tenga permiso para ver inactivos
        if estado_upper == 'INACTIVO' and not user_is_admin:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No tiene acceso al filtro de medicamentos inactivos. Esta funcionalidad está restringida a administradores."
            )
        
        try:
            q = q.filter(models.Medicamento.estado == models.EstadoEnum(estado_upper))
        except ValueError:
            raise HTTPException(
                status_code=400, 
                detail='Estado inválido. Use: ACTIVO o INACTIVO'
            )
    else:
        #Sin filtro de estado: comportamiento por defecto según rol
        #Admin ve todos, otros roles solo activos
        if not user_is_admin:
            q = q.filter(models.Medicamento.estado == models.EstadoEnum.ACTIVO)
        #Si es admin y no especificó filtro, ve TODOS (no filtrar por estado)
    
    #Aplicar filtros opcionales
    if nombre:
        #hu-1.03: Búsqueda case-insensitive y parcial
        like = f"%{nombre}%"
        q = q.filter(
            (models.Medicamento.nombre.ilike(like)) | 
            (models.Medicamento.presentacion.ilike(like))
        )
    
    if fabricante:
        q = q.filter(models.Medicamento.fabricante.ilike(f"%{fabricante}%"))
    
    if lote:
        q = q.filter(models.Medicamento.lote.ilike(f"%{lote}%"))
    
    if fecha_vencimiento:
        from datetime import datetime as _dt
        try:
            fv = _dt.fromisoformat(fecha_vencimiento).date()
            q = q.filter(models.Medicamento.fecha_vencimiento == fv)
        except ValueError:
            raise HTTPException(
                status_code=400, 
                detail='Formato de fecha inválido. Use: YYYY-MM-DD'
            )
    
    if stock_bajo is True:
        #Filtrar medicamentos donde stock <= minimo_stock
        q = q.filter(models.Medicamento.stock <= models.Medicamento.minimo_stock)
    
    #HU-1.03: Carga inicial muestra medicamentos en lista
    #Ordenar por nombre para resultados consistentes
    q = q.order_by(models.Medicamento.nombre)
    
    return q.limit(limit).all()


@router.get("/{med_id}", response_model=MedicamentoOut)
def detalle_medicamento(med_id: str, service: MedicamentoService = Depends(get_medicamento_service), db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    # Validar que med_id sea un UUID válido
    is_valid, error_msg = validate_uuid(med_id, "med_id")
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                'error': 'invalid_uuid',
                'message': error_msg
            }
        )
    
    m = db.query(models.Medicamento).filter(models.Medicamento.id == med_id).first()
    if not m:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                'error': 'medicamento_not_found',
                'message': f'Medicamento con ID {med_id} no encontrado'
            }
        )
    return m


@router.put("/{med_id}", response_model=MedicamentoOut)
def actualizar_medicamento(med_id: str, payload: MedicamentoUpdate, response: Response, service: MedicamentoService = Depends(get_medicamento_service), db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    # Validar que med_id sea un UUID válido
    is_valid, error_msg = validate_uuid(med_id, "med_id")
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                'error': 'invalid_uuid',
                'message': error_msg
            }
        )
    
    m = db.query(models.Medicamento).filter(models.Medicamento.id == med_id).first()
    if not m:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                'error': 'medicamento_not_found',
                'message': f'Medicamento con ID {med_id} no encontrado'
            }
        )

    # validar y preparar cambios
    data = payload.model_dump(exclude_unset=True)
    from datetime import date, timedelta
    if 'fecha_vencimiento' in data:
        fv = data.get('fecha_vencimiento')
        if fv < date.today():
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Fecha inválida: la fecha de vencimiento no puede ser anterior a hoy.')
        if fv <= date.today() + timedelta(days=30):
            response.headers['X-Warning'] = 'Este medicamento está próximo a vencer, ¿Continuar?'
    new_nombre = data.get('nombre', m.nombre)
    new_presentacion = data.get('presentacion', m.presentacion)
    new_fabricante = data.get('fabricante', m.fabricante)
    #HU-1.01: Validar solo nombre + presentación + fabricante (NO incluir lote)
    new_search_key = f"{normalize_text(new_nombre)}|{normalize_text(new_presentacion)}|{normalize_text(new_fabricante)}"
    repo = MedicamentoRepository(db)
    dup = repo.find_by_search_key(new_search_key, exclude_id=m.id)
    if dup:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail={"error":"Medicamento duplicado con los nuevos valores", "existing_id": str(dup.id)})

    data['search_key'] = new_search_key
    res = service.update_medicamento(med_id, data, user.get('sub') if user else None)
    if not res:
        raise HTTPException(status_code=404, detail='Medicamento no encontrado')
    if res.get('updated') is False:
        return {"message": "No se detectaron cambios, no se actualizó."}
    updated_med = res.get('medicamento')
    return updated_med


@router.delete("/{med_id}", response_model=DeleteOut)
def eliminar_medicamento(med_id: str, service: MedicamentoService = Depends(get_medicamento_service), db: Session = Depends(get_db), user: dict = Depends(require_admin)):
    # Validar que med_id sea un UUID válido
    is_valid, error_msg = validate_uuid(med_id, "med_id")
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                'error': 'invalid_uuid',
                'message': error_msg
            }
        )
    
    res = service.delete_medicamento(med_id, user.get('sub'))
    if res is None:
        raise HTTPException(status_code=404, detail="Medicamento no encontrado")
    if res.get('dependencias') and res.get('dependencias') > 0:
        return DeleteOut(deleted=False, dependencias=res.get('dependencias'))
    return DeleteOut(deleted=True, dependencias=0)


@router.post("/{med_id}/reactivar", response_model=ReactivateOut)
def reactivar_medicamento(med_id: str, service: MedicamentoService = Depends(get_medicamento_service), db: Session = Depends(get_db), user: dict = Depends(require_admin)):
    """Reactivar un medicamento inactivo/eliminado.

    Business rules:
    - Solo admins pueden reactivar (require_admin dependency applied).
    - Si la fecha de vencimiento ya pasó -> no se permite reactivar (resp: 400 con reason 'expired').
    - Devuelve 200 con {reactivated: true, medicamento: {...}} si se reactiva exitosamente.
    - Devuelve 409 con detalle si no existe.
    """
    # Validar que med_id sea un UUID válido
    is_valid, error_msg = validate_uuid(med_id, "med_id")
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                'error': 'invalid_uuid',
                'message': error_msg
            }
        )
    
    res = service.reactivar_medicamento(med_id, user.get('sub'))
    if res is None:
        raise HTTPException(status_code=404, detail='Medicamento no encontrado')
    if res.get('reactivated') is False:
        if res.get('reason') == 'expired':
            raise HTTPException(status_code=400, detail='No es posible reactivar: la fecha de vencimiento ya expiró.')
        raise HTTPException(status_code=409, detail='No se pudo reactivar el medicamento')
    med = res.get('medicamento')
    return ReactivateOut(reactivated=True, medicamento=med)


@router.get("/{med_id}/movimientos", response_model=List[MovimientoOut])
def listar_movimientos_medicamento(
    med_id: str, 
    service: MedicamentoService = Depends(get_medicamento_service),
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
    limit: int = 100
):
    """
    Lista todos los movimientos de un medicamento específico.
    
    HU-1.01: Permite ver historial completo en vista detalle
    HU-1.02: Mantener historial para auditorías y control sanitario legal
    
    Retorna movimientos ordenados cronológicamente (más recientes primero).
    Incluye entradas y salidas con información de usuario, fecha, cantidad y motivo.
    """
    # Validar que med_id sea un UUID válido
    is_valid, error_msg = validate_uuid(med_id, "med_id")
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                'error': 'invalid_uuid',
                'message': error_msg
            }
        )
    
    #Verificar que el medicamento existe
    m = db.query(models.Medicamento).filter(models.Medicamento.id == med_id).first()
    if not m:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                'error': 'medicamento_not_found',
                'message': f'Medicamento con ID {med_id} no encontrado'
            }
        )
    
    #Obtener movimientos ordenados por fecha descendente
    movimientos = db.query(models.Movimiento)\
        .filter(models.Movimiento.medicamento_id == med_id)\
        .order_by(models.Movimiento.fecha.desc())\
        .limit(limit)\
        .all()
    
    return movimientos


@router.post("/{med_id}/movimientos", response_model=MovimientoOut)
def crear_movimiento(med_id: str, payload: MovimientoCreate, service: MedicamentoService = Depends(get_medicamento_service), user: dict = Depends(get_current_user)):
    # Validar que med_id sea un UUID válido
    is_valid, error_msg = validate_uuid(med_id, "med_id")
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                'error': 'invalid_uuid',
                'message': error_msg
            }
        )
    
    tipo = payload.tipo.upper()
    if tipo not in ('ENTRADA', 'SALIDA'):
        raise HTTPException(status_code=400, detail='Tipo inválido, debe ser ENTRADA o SALIDA')

    res = service.registrar_movimiento(med_id, tipo, payload.cantidad, usuario_id=user.get('sub') if user else None, motivo=payload.motivo)
    if res.get('ok') is False:
        reason = res.get('reason')
        if reason == 'not_found':
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    'error': 'medicamento_not_found',
                    'message': f'Medicamento con ID {med_id} no encontrado'
                }
            )
        if reason == 'inactive' or reason == 'expired':
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    'error': 'medicamento_inactive_or_expired',
                    'message': 'No se pueden registrar cambios: el medicamento está inactivo o vencido'
                }
            )
        if reason == 'insufficient_stock':
            avail = res.get('available', 0)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    'error': 'insufficient_stock',
                    'message': f'Stock disponible: {avail}. No se registró el movimiento.',
                    'available': avail
                }
            )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                'error': 'movement_error',
                'message': 'Error al registrar movimiento'
            }
        )

    mv = res.get('movimiento')
    return mv


@router.get("/{med_id}/audit", response_model=List[AuditLogOut])
def listar_auditoria_medicamento(
    med_id: str,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
    limit: int = 100
):
    """
    Lista el historial completo de auditoría de un medicamento específico.
    
    HU-1.01-CRUD: "Given selecciono medicamento, When accedo al detalle, 
    Then se muestra toda la información incluyendo auditoría y estado"
    
    Retorna todos los cambios realizados al medicamento ordenados cronológicamente
    (más recientes primero). Incluye:
    - Campo modificado
    - Valor anterior y nuevo
    - Usuario que realizó el cambio
    - Timestamp del cambio
    - Acciones (CREATE, UPDATE, DELETE_SOFT, REACTIVATE, DEACTIVATE)
    
    Ejemplos de acciones:
    - UPDATE: Cambio en campo específico (precio, stock, etc.)
    - DELETE_SOFT: Eliminación lógica del medicamento
    - DEACTIVATE: Marcado como inactivo por tener dependencias
    - REACTIVATE: Reactivación de medicamento inactivo
    """
    # Validar que med_id sea un UUID válido
    is_valid, error_msg = validate_uuid(med_id, "med_id")
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                'error': 'invalid_uuid',
                'message': error_msg
            }
        )
    
    # Verificar que el medicamento existe
    m = db.query(models.Medicamento).filter(models.Medicamento.id == med_id).first()
    if not m:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                'error': 'medicamento_not_found',
                'message': f'Medicamento con ID {med_id} no encontrado'
            }
        )
    
    # Obtener logs de auditoría ordenados por fecha descendente
    audit_logs = db.query(models.AuditLog)\
        .filter(
            models.AuditLog.entidad == 'medicamentos',
            models.AuditLog.entidad_id == med_id
        )\
        .order_by(models.AuditLog.timestamp.desc())\
        .limit(limit)\
        .all()
    
    return audit_logs

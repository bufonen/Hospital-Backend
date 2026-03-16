"""
Routes/Endpoints para gestión de Órdenes de Compra.
HU-4.02: Post-Orden

SEGURIDAD:
- Solo ADMIN y COMPRAS pueden crear/editar órdenes
- Todos pueden consultar (GET)
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from database.connection import get_db
from database.models import OrdenCompra, EstadoOrdenEnum
from schemas.orden_compra import (
    OrdenCompraCreate,
    OrdenCompraUpdate,
    OrdenCompraOut,
    OrdenCompraShortOut,
    MarcarEnviadaRequest,
    RecepcionOrdenRequest,
    RecepcionOrdenResponse
)
from services.orden_compra_service import OrdenCompraService
from auth.security import get_current_user, require_admin, require_compras_or_admin
from utils.validators import validate_uuid
from utils.serializers import serialize_orden_compra
from typing import List, Optional
from datetime import date

router = APIRouter()


def get_orden_service(db: Session = Depends(get_db)) -> OrdenCompraService:
    """Dependency para inyectar el service."""
    return OrdenCompraService(db)


@router.post(
    "/",
    response_model=OrdenCompraOut,
    status_code=status.HTTP_201_CREATED,
    summary="Crear orden de compra",
    description="Crea una nueva orden de compra. **Solo ADMIN o COMPRAS**"
)
def crear_orden(
    payload: OrdenCompraCreate,
    service: OrdenCompraService = Depends(get_orden_service),
    user: dict = Depends(require_compras_or_admin)  # 🔒 COMPRAS o ADMIN
):
    """
    Crea una nueva orden de compra.
    
    HU-4.02: "Given que ingreso los datos obligatorios de la orden
              When guardo la orden de compra
              Then el sistema crea la orden con un ID único y estado PENDIENTE"
    
    **Acceso: Administradores y Responsables de Compras**
    
    Campos obligatorios:
    - proveedor_id
    - fecha_prevista_entrega
    - detalles (lista de productos, mínimo 1)
    
    Validaciones:
    - Proveedor debe existir y estar activo
    - Fecha prevista debe ser futura
    - Al menos un producto en la orden
    - Medicamentos deben existir
    
    El sistema genera automáticamente:
    - ID único
    - Número de orden (formato: OC-2025-0001)
    - Estado inicial: PENDIENTE
    - Fecha de creación
    - Total estimado (suma de subtotales)
    
    Responses:
    - 201: Orden creada exitosamente
    - 400: Datos inválidos
    - 403: Sin permisos
    - 404: Proveedor o medicamento no encontrado
    """
    result = service.create_orden(
        payload.model_dump(),
        user_id=user.get('sub')
    )
    
    if not result['ok']:
        error = result['error']
        message = result['message']
        
        if error == 'proveedor_not_found':
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    'error': 'proveedor_not_found',
                    'message': message
                }
            )
        elif error == 'proveedor_required':
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    'error': 'proveedor_required',
                    'message': message
                }
            )
        elif error == 'proveedor_inactive':
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    'error': 'proveedor_inactive',
                    'message': message
                }
            )
        elif error == 'no_products':
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    'error': 'no_products',
                    'message': message
                }
            )
        elif error == 'medicamento_not_found':
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    'error': 'medicamento_not_found',
                    'message': message
                }
            )
        elif error == 'medicamento_id_required':
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    'error': 'medicamento_id_required',
                    'message': message
                }
            )
        elif error == 'medicamento_inactive':
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    'error': 'medicamento_inactive',
                    'message': message
                }
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={
                    'error': error,
                    'message': message
                }
            )
    
    # Serializar orden con datos anidados
    return serialize_orden_compra(result['orden'])


@router.get(
    "/",
    response_model=List[OrdenCompraOut],
    summary="Listar órdenes de compra",
    description="Lista órdenes con filtros opcionales. Accesible por todos los roles."
)
def listar_ordenes(
    estado: Optional[str] = Query(None, description="Filtrar por estado: PENDIENTE/ENVIADA/RECIBIDA/RETRASADA"),
    proveedor_id: Optional[str] = Query(None, description="Filtrar por proveedor"),
    fecha_desde: Optional[date] = Query(None, description="Fecha desde (creación)"),
    fecha_hasta: Optional[date] = Query(None, description="Fecha hasta (creación)"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    service: OrdenCompraService = Depends(get_orden_service),
    user: dict = Depends(get_current_user)
):
    """
    Lista órdenes de compra con filtros opcionales.
    
    **Acceso: Todos los roles autenticados**
    
    Filtros disponibles:
    - estado: PENDIENTE, ENVIADA, RECIBIDA, RETRASADA
    - proveedor_id: Filtrar por proveedor específico
    - fecha_desde/fecha_hasta: Rango de fechas de creación
    - limit/offset: Paginación
    """
    ordenes = service.list_ordenes(
        estado=estado,
        proveedor_id=proveedor_id,
        fecha_desde=fecha_desde,
        fecha_hasta=fecha_hasta,
        limit=limit,
        offset=offset
    )
    # Serializar cada orden con datos anidados
    return [serialize_orden_compra(orden) for orden in ordenes]


@router.get(
    "/retrasadas",
    response_model=List[OrdenCompraOut],
    summary="Listar órdenes retrasadas",
    description="Obtiene órdenes en estado RETRASADA"
)
def listar_retrasadas(
    service: OrdenCompraService = Depends(get_orden_service),
    user: dict = Depends(get_current_user)
):
    """
    Lista órdenes actualmente marcadas como RETRASADAS.
    
    HU-4.02: "Given orden enviada con fecha prevista pasada
              When consulto órdenes retrasadas
              Then veo lista de pedidos retrasados"
    
    **Acceso: Todos los roles autenticados**
    """
    ordenes = service.get_ordenes_retrasadas()
    # Serializar cada orden con datos anidados
    return [serialize_orden_compra(orden) for orden in ordenes]


@router.get(
    "/stats",
    summary="Estadísticas de órdenes",
    description="Obtiene contadores por estado"
)
def obtener_estadisticas(
    service: OrdenCompraService = Depends(get_orden_service),
    user: dict = Depends(get_current_user)
):
    """
    Obtiene estadísticas de órdenes por estado.
    
    Returns:
    ```json
    {
        "total": 150,
        "pendientes": 20,
        "enviadas": 30,
        "recibidas": 90,
        "retrasadas": 10
    }
    ```
    """
    return service.get_stats()


@router.get(
    "/{orden_id}",
    response_model=OrdenCompraOut,
    summary="Detalle de orden",
    description="Obtiene información completa de una orden"
)
def obtener_orden(
    orden_id: str,
    service: OrdenCompraService = Depends(get_orden_service),
    user: dict = Depends(get_current_user)
):
    """
    Obtiene el detalle completo de una orden de compra.
    Incluye proveedor y todos los items (productos).
    
    **Acceso: Todos los roles autenticados**
    
    Responses:
    - 200: Orden encontrada
    - 400: ID inválido
    - 404: Orden no encontrada
    """
    # Validar que orden_id sea un UUID válido
    is_valid, error_msg = validate_uuid(orden_id, "orden_id")
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                'error': 'invalid_uuid',
                'message': error_msg
            }
        )
    
    orden = service.get_orden(orden_id)
    if not orden:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                'error': 'orden_not_found',
                'message': f'Orden con ID {orden_id} no encontrada'
            }
        )
    # Serializar orden con datos anidados
    return serialize_orden_compra(orden)


@router.put(
    "/{orden_id}",
    response_model=OrdenCompraOut,
    summary="Actualizar orden",
    description="Actualiza una orden (solo en estado PENDIENTE). **Solo ADMIN o COMPRAS**"
)
def actualizar_orden(
    orden_id: str,
    payload: OrdenCompraUpdate,
    service: OrdenCompraService = Depends(get_orden_service),
    user: dict = Depends(require_compras_or_admin)  # 🔒 COMPRAS o ADMIN
):
    """
    Actualiza una orden de compra.
    
    **Acceso: Administradores y Responsables de Compras**
    
    Restricciones:
    - Solo se puede editar en estado PENDIENTE
    - No se pueden modificar detalles (items) después de crear
    
    Campos editables:
    - proveedor_id
    - fecha_prevista_entrega
    - observaciones
    
    Responses:
    - 200: Orden actualizada
    - 400: Estado inválido para edición o ID inválido
    - 403: Sin permisos
    - 404: Orden no encontrada
    """
    # Validar que orden_id sea un UUID válido
    is_valid, error_msg = validate_uuid(orden_id, "orden_id")
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                'error': 'invalid_uuid',
                'message': error_msg
            }
        )
    
    changes = payload.model_dump(exclude_unset=True)
    
    if not changes:
        raise HTTPException(status_code=400, detail="No se proporcionaron campos para actualizar")
    
    result = service.update_orden(orden_id, changes, user_id=user.get('sub'))
    
    if not result['ok']:
        error = result['error']
        if error == 'not_found':
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    'error': 'orden_not_found',
                    'message': result['message']
                }
            )
        elif error == 'invalid_state':
            raise HTTPException(status_code=400, detail=result['message'])
        else:
            raise HTTPException(status_code=500, detail=result['message'])
    
    if not result.get('updated'):
        return {"message": "No se detectaron cambios", **serialize_orden_compra(result['orden'])}
    
    # Serializar orden con datos anidados
    return serialize_orden_compra(result['orden'])


@router.post(
    "/{orden_id}/enviar",
    response_model=OrdenCompraOut,
    summary="Marcar orden como enviada",
    description="Cambia el estado a ENVIADA. **Solo ADMIN o COMPRAS**"
)
def marcar_enviada(
    orden_id: str,
    payload: Optional[MarcarEnviadaRequest] = None,
    service: OrdenCompraService = Depends(get_orden_service),
    user: dict = Depends(require_compras_or_admin)  # 🔒 COMPRAS o ADMIN
):
    """
    Marca una orden como ENVIADA.
    
    **Acceso: Administradores y Responsables de Compras**
    
    HU-4.02: Transición de estado PENDIENTE → ENVIADA
    
    Después de marcar como enviada:
    - El sistema comenzará a monitorear la fecha prevista
    - Si pasa la fecha sin recibir, se marcará como RETRASADA
    
    Responses:
    - 200: Orden marcada como enviada
    - 400: Estado inválido (solo desde PENDIENTE) o ID inválido
    - 403: Sin permisos
    - 404: Orden no encontrada
    """
    # Validar que orden_id sea un UUID válido
    is_valid, error_msg = validate_uuid(orden_id, "orden_id")
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                'error': 'invalid_uuid',
                'message': error_msg
            }
        )
    
    data = payload.model_dump() if payload else {}
    
    result = service.marcar_enviada(
        orden_id,
        fecha_envio=data.get('fecha_envio'),
        observaciones=data.get('observaciones'),
        user_id=user.get('sub')
    )
    
    if not result['ok']:
        error = result['error']
        if error == 'not_found':
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    'error': 'orden_not_found',
                    'message': "Orden no encontrada"
                }
            )
        elif error == 'invalid_state':
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    'error': 'invalid_state',
                    'message': result['message']
                }
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={
                    'error': 'server_error',
                    'message': result['message']
                }
            )
    
    # Serializar orden con datos anidados
    return serialize_orden_compra(result['orden'])


@router.post(
    "/{orden_id}/recibir",
    response_model=RecepcionOrdenResponse,
    summary="Registrar recepción de orden",
    description="Marca orden como RECIBIDA y actualiza inventario. **Solo ADMIN o COMPRAS**"
)
def recibir_orden(
    orden_id: str,
    payload: RecepcionOrdenRequest,
    service: OrdenCompraService = Depends(get_orden_service),
    user: dict = Depends(require_compras_or_admin)  #compras o admin
):
    """
    Registra la recepción completa de una orden.
    
    HU-4.02: "Given que una orden de compra está en estado ENVIADA
              When registro la recepción completa de los productos
              Then el sistema actualiza el estado de la orden a RECIBIDA
              y se guarda la fecha de recepción"
    
    **Acceso: Administradores y Responsables de Compras**
    
    Funcionalidades:
    1. Valida cantidades recibidas vs solicitadas
    2. Detecta diferencias y las reporta
    3. Actualiza estado a RECIBIDA
    4. Registra fecha y usuario que recibió
    5. **Actualiza inventario automáticamente** (opcional)
    
    Si actualizar_inventario = true:
    - Crea movimientos de ENTRADA
    - Actualiza stock de medicamentos
    - Registra auditoría
    
    HU-4.02 Excepciones:
    "Si hay productos con cantidad esperada ≠ cantidad recibida
     → mostrar alerta y pedir confirmación de ajuste"
    
    Responses:
    - 200: Orden recibida exitosamente (con diferencias si las hay)
    - 400: Estado inválido (solo desde ENVIADA o RETRASADA) o ID inválido
    - 403: Sin permisos
    - 404: Orden no encontrada
    """
    # Validar que orden_id sea un UUID válido
    is_valid, error_msg = validate_uuid(orden_id, "orden_id")
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                'error': 'invalid_uuid',
                'message': error_msg
            }
        )
    
    result = service.recibir_orden(
        orden_id,
        items_recibidos=[item.model_dump() for item in payload.items],
        fecha_recepcion=payload.fecha_recepcion,
        observaciones=payload.observaciones,
        user_id=user.get('sub'),
        actualizar_inventario=payload.actualizar_inventario
    )
    
    if not result['ok']:
        error = result['error']
        if error == 'not_found':
            raise HTTPException(status_code=404, detail="Orden no encontrada")
        elif error == 'invalid_state':
            raise HTTPException(status_code=400, detail=result['message'])
        else:
            raise HTTPException(status_code=500, detail=result['message'])
    
    # Construir response
    orden = result['orden']
    diferencias = result.get('diferencias', [])
    
    mensaje = "Orden recibida exitosamente"
    if diferencias:
        mensaje += f" (con {len(diferencias)} diferencias en cantidades)"
    
    return RecepcionOrdenResponse(
        orden_id=str(orden.id),
        numero_orden=orden.numero_orden,
        estado=orden.estado.value,
        items_recibidos=result['items_actualizados'],
        items_con_diferencias=diferencias,
        inventario_actualizado=result['inventario_actualizado'],
        mensaje=mensaje
    )


@router.post(
    "/detectar-retrasos",
    summary="Detectar órdenes retrasadas (manual)",
    description="Ejecuta manualmente la detección de órdenes retrasadas y genera alertas. **Solo ADMIN o COMPRAS**"
)
def detectar_retrasos_manual(
    service: OrdenCompraService = Depends(get_orden_service),
    user: dict = Depends(require_compras_or_admin)  # solo compras o admin
):
    """
    Ejecuta manualmente la detección de órdenes retrasadas.
    
    Este endpoint permite ejecutar la detección de retrasos inmediatamente
    sin esperar al job programado diario.
    
    **Acceso: Administradores y Responsables de Compras**
    
    Funcionalidades:
    1. Busca órdenes en estado ENVIADA con fecha prevista pasada
    2. Las marca como RETRASADAS
    3. Crea alertas automáticas con nivel de prioridad según días de retraso:
       - 1-2 días: MEDIA
       - 3-6 días: ALTA
       - 7+ días: CRÍTICA
    4. Notifica a roles COMPRAS y ADMIN vía Redis
    
    Returns:
        Dict con contadores de órdenes marcadas y alertas creadas
    
    Example response:
    ```json
    {
        "ok": true,
        "ordenes_marcadas": 3,
        "alertas_creadas": 2,
        "mensaje": "Se detectaron 3 órdenes retrasadas y se crearon 2 alertas nuevas"
    }
    ```
    """
    result = service.detectar_ordenes_retrasadas()
    
    if not result['ok']:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                'error': 'detection_failed',
                'message': f"Error al detectar retrasos: {result['error']}"
            }
        )
    
    ordenes_marcadas = result['ordenes_marcadas']
    alertas_creadas = result.get('alertas_creadas', 0)
    
    mensaje = f"Se detectaron {ordenes_marcadas} órdenes retrasadas"
    if alertas_creadas > 0:
        mensaje += f" y se crearon {alertas_creadas} alertas nuevas"
    elif ordenes_marcadas > 0:
        mensaje += " (alertas ya existían)"
    else:
        mensaje = "No se encontraron órdenes retrasadas"
    
    return {
        'ok': True,
        'ordenes_marcadas': ordenes_marcadas,
        'alertas_creadas': alertas_creadas,
        'mensaje': mensaje,
        'ejecutado_por': user.get('username', 'unknown')
    }

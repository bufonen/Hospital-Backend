"""
Routes/Endpoints para gestión de Proveedores.
HU-4.01: Manejo de Proveedores

SEGURIDAD:
- Solo ADMIN puede crear, editar y eliminar proveedores
- Otros roles pueden consultar (GET)
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from database.connection import get_db
from database.models import Proveedor, EstadoProveedorEnum
from schemas.proveedor import (
    ProveedorCreate, 
    ProveedorUpdate, 
    ProveedorOut,
    ProveedorShortOut
)
from services.proveedor_service import ProveedorService
from auth.security import get_current_user, require_admin
from typing import List, Optional


router = APIRouter()


def get_proveedor_service(db: Session = Depends(get_db)) -> ProveedorService:
    """Dependency para inyectar el service."""
    return ProveedorService(db)


@router.post(
    "/",
    response_model=ProveedorOut,
    status_code=status.HTTP_201_CREATED,
    summary="Crear proveedor",
    description="Crea un nuevo proveedor. **Solo ADMIN**"
)
def crear_proveedor(
    payload: ProveedorCreate,
    service: ProveedorService = Depends(get_proveedor_service),
    user: dict = Depends(require_admin)  # solo compras o admin
):
    """
    Crea un nuevo proveedor.
    
    HU-4.01: "Given datos válidos, When se crea un registro de un proveedor,
              Then registro creado con ID único"
    
    **Acceso: Solo administradores**
    
    Validaciones:
    - NIT único (no duplicados)
    - Email con formato válido
    - Campos obligatorios: nombre, nit
    
    Responses:
    - 201: Proveedor creado exitosamente
    - 409: NIT duplicado
    - 403: Sin permisos (no es admin)
    - 422: Datos inválidos
    """
    result = service.create_proveedor(
        payload.model_dump(),
        user_id=user.get('sub')
    )
    
    if not result['ok']:
        if result['error'] == 'duplicate_nit':
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "error": "duplicate_nit",
                    "message": result['message'],
                    "existing_id": result.get('existing_id')
                }
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result['message']
            )
    
    return result['proveedor']


@router.get(
    "/",
    response_model=List[ProveedorOut],
    summary="Listar proveedores",
    description="Lista proveedores con filtros opcionales. Accesible por todos los roles autenticados."
)
def listar_proveedores(
    estado: Optional[str] = Query(None, description="Filtrar por estado: ACTIVO o INACTIVO"),
    nombre: Optional[str] = Query(None, description="Búsqueda por nombre (parcial)"),
    limit: int = Query(100, ge=1, le=500, description="Máximo de resultados"),
    offset: int = Query(0, ge=0, description="Offset para paginación"),
    service: ProveedorService = Depends(get_proveedor_service),
    user: dict = Depends(get_current_user)  # cualquier rol autenticado
):
    """
    Lista proveedores con filtros opcionales.
    
    **Acceso: Todos los roles autenticados**
    
    Filtros disponibles:
    - estado: ACTIVO o INACTIVO
    - nombre: Búsqueda parcial (case-insensitive)
    - limit: Máximo de resultados (default: 100, max: 500)
    - offset: Para paginación
    
    Ejemplos:
    - GET /api/proveedores/ → Todos los proveedores
    - GET /api/proveedores/?estado=ACTIVO → Solo activos
    - GET /api/proveedores/?nombre=pharma → Buscar por nombre
    """
    return service.list_proveedores(
        estado=estado,
        nombre=nombre,
        limit=limit,
        offset=offset
    )


@router.get(
    "/search",
    response_model=List[ProveedorShortOut],
    summary="Búsqueda rápida",
    description="Búsqueda de proveedores para autocomplete/dropdowns"
)
def buscar_proveedores(
    q: str = Query(..., min_length=1, description="Término de búsqueda"),
    limit: int = Query(10, ge=1, le=50),
    service: ProveedorService = Depends(get_proveedor_service),
    user: dict = Depends(get_current_user)
):
    """
    Búsqueda rápida de proveedores por nombre o NIT.
    
    **Acceso: Todos los roles autenticados**
    
    Útil para:
    - Autocomplete en formularios
    - Dropdowns de selección
    - Búsquedas rápidas
    
    Solo retorna proveedores ACTIVOS.
    """
    return service.search_proveedores(q, limit)


@router.get(
    "/stats",
    summary="Estadísticas de proveedores",
    description="Obtiene contadores de proveedores activos/inactivos"
)
def obtener_estadisticas(
    service: ProveedorService = Depends(get_proveedor_service),
    user: dict = Depends(get_current_user)
):
    """
    Obtiene estadísticas básicas de proveedores.
    
    **Acceso: Todos los roles autenticados**
    
    Returns:
    ```json
    {
        "total": 50,
        "activos": 45,
        "inactivos": 5
    }
    ```
    """
    return service.get_stats()


@router.get(
    "/{proveedor_id}",
    response_model=ProveedorOut,
    summary="Detalle de proveedor",
    description="Obtiene información completa de un proveedor"
)
def obtener_proveedor(
    proveedor_id: str,
    service: ProveedorService = Depends(get_proveedor_service),
    user: dict = Depends(get_current_user)
):
    """
    Obtiene el detalle completo de un proveedor.
    
    **Acceso: Todos los roles autenticados**
    
    Responses:
    - 200: Proveedor encontrado
    - 404: Proveedor no encontrado
    """
    proveedor = service.get_proveedor(proveedor_id)
    if not proveedor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Proveedor no encontrado"
        )
    return proveedor


@router.put(
    "/{proveedor_id}",
    response_model=ProveedorOut,
    summary="Actualizar proveedor",
    description="Actualiza información de un proveedor. **Solo ADMIN**"
)
def actualizar_proveedor(
    proveedor_id: str,
    payload: ProveedorUpdate,
    service: ProveedorService = Depends(get_proveedor_service),
    user: dict = Depends(require_admin)  # solo admin
):
    """
    Actualiza un proveedor existente.
    
    HU-4.01: "Given que existe un proveedor registrado When edito su información
              y guardo cambios Then los datos se actualizan correctamente"
    
    **Acceso: Solo administradores**
    
    Reglas:
    - NO se puede editar NIT ni ID
    - Solo campos modificados se actualizan
    - Se registra auditoría de cambios
    
    Responses:
    - 200: Proveedor actualizado
    - 404: Proveedor no encontrado
    - 403: Sin permisos (no es admin)
    """
    # Filtrar solo campos presentes
    changes = payload.model_dump(exclude_unset=True)
    
    if not changes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No se proporcionaron campos para actualizar"
        )
    
    result = service.update_proveedor(
        proveedor_id,
        changes,
        user_id=user.get('sub')
    )
    
    if not result['ok']:
        if result['error'] == 'not_found':
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=result['message']
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result['message']
            )
    
    if not result.get('updated'):
        return {
            "message": "No se detectaron cambios",
            **result['proveedor'].__dict__
        }
    
    return result['proveedor']


@router.delete(
    "/{proveedor_id}",
    summary="Desactivar proveedor",
    description="Cambia el estado del proveedor a INACTIVO. **Solo ADMIN**"
)
def desactivar_proveedor(
    proveedor_id: str,
    service: ProveedorService = Depends(get_proveedor_service),
    user: dict = Depends(require_admin)  # solo admin
):
    """
    Desactiva un proveedor (soft delete).
    
    **Acceso: Solo administradores**
    
    Cambia el estado a INACTIVO en lugar de borrar físicamente.
    Útil para mantener historial de órdenes de compra asociadas.
    
    Responses:
    - 200: Proveedor desactivado
    - 404: Proveedor no encontrado
    - 400: Ya estaba inactivo
    - 403: Sin permisos (no es admin)
    """
    result = service.deactivate_proveedor(
        proveedor_id,
        user_id=user.get('sub')
    )
    
    if not result['ok']:
        if result['error'] == 'not_found':
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=result['message']
            )
        elif result['error'] == 'already_inactive':
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result['message']
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result['message']
            )
    
    return {
        "message": "Proveedor desactivado exitosamente",
        "proveedor_id": proveedor_id
    }


@router.post(
    "/{proveedor_id}/activate",
    response_model=ProveedorOut,
    summary="Reactivar proveedor",
    description="Cambia el estado del proveedor a ACTIVO. **Solo ADMIN**"
)
def activar_proveedor(
    proveedor_id: str,
    service: ProveedorService = Depends(get_proveedor_service),
    user: dict = Depends(require_admin)  # solo admin
):
    """
    Reactiva un proveedor inactivo.
    
    **Acceso: Solo administradores**
    
    Cambia el estado de INACTIVO a ACTIVO.
    
    Responses:
    - 200: Proveedor reactivado
    - 404: Proveedor no encontrado
    - 400: Ya estaba activo
    - 403: Sin permisos (no es admin)
    """
    result = service.activate_proveedor(
        proveedor_id,
        user_id=user.get('sub')
    )
    
    if not result['ok']:
        if result['error'] == 'not_found':
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=result['message']
            )
        elif result['error'] == 'already_active':
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result['message']
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result['message']
            )
    
    return result['proveedor']

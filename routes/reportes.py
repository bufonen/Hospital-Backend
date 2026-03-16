"""
routes para reportes de compras y comparación de precios.
HU-4.03: Comparación de Precios (solo para administradores)
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from database.connection import get_db
from auth.security import require_admin
from services.reporte_service import ReporteService
from schemas.reporte import (
    FiltrosReporteRequest,
    ComparacionPreciosResponse,
    ReporteComprasResponse
)
from schemas.response import MessageOut
from typing import Union
from pydantic import ValidationError


router = APIRouter()


@router.post(
    "/comparacion-precios",
    response_model=Union[ComparacionPreciosResponse, MessageOut],
    summary="Comparar precios entre proveedores",
    description="""
    HU-4.03: Comparación de Precios
    
    Compara precios históricos entre proveedores por medicamento.
    
    restricciones:
    - solo administradores pueden acceder
    - rango maximo: 12 meses (365 dias)
    - solo se consideran ordenes en estado RECIBIDA
    
    reglas de negocio:
    - debe haber minimo 1 orden de compra por proveedor en el rango
    - precio promedio = total pagado / unidades compradas
    
    respuesta:
    - tabla con medicamentos y proveedores que los suministraron
    - precio promedio por proveedor
    - identificación del proveedor con mejor precio
    """,
    tags=["reportes"]
)
def comparar_precios_proveedores(
    filtros: FiltrosReporteRequest,
    current_user: dict = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Endpoint para comparación de precios entre proveedores.
    
    Given 3 proveedores con precios distintos,
    When ejecuto comparativo en rango 6 meses,
    Then muestro tabla por medicamento y promedio precio proveedor.
    
    excepciones:
    - 400: rango de fechas inválido o supera 12 meses
    - 401: no autenticado
    - 403: no es administrador
    - 500: Error en base de datos
    """
    try:
        # El validador de FiltrosReporteRequest ya valida:
        # - fecha_inicio < fecha_fin
        # - rango máximo 12 meses
        
        service = ReporteService(db)
        resultado = service.comparar_precios(
            fecha_inicio=filtros.fecha_inicio,
            fecha_fin=filtros.fecha_fin,
            medicamento_id=filtros.medicamento_id
        )
        
        #si el servicio retorna error
        if not resultado.get('ok', False):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=resultado.get('message', 'Error al generar comparación')
            )
        
        #retornar resultado exitoso
        return resultado
        
    except ValidationError as ve:
        #errores de validacion de pydantic (rango > 12 meses, fechas inválidas)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(ve)
        )
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error inesperado en comparar_precios_proveedores: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error interno del servidor al generar comparación"
        )


@router.post(
    "/compras",
    response_model=Union[ReporteComprasResponse, MessageOut],
    summary="Generar reporte de compras consolidado",
    description="""
    HU-4.03: Reporte de Compras por Periodo
    
    Genera reporte consolidado de todas las compras en un rango de fechas.
    
    restricciones:
    - solo administradores pueden acceder
    - rango maximo: 12 meses (365 dias)
    - solo se consideran ordenes en estado RECIBIDA
    
    alcance:
    - tabla con: medicamento, proveedor, total unidades, total dinero
    - totales consolidados por proveedor
    - gran total invertido en el período
    
    out of scope:
    - gráficos avanzados o dashboards comparativos
    """,
    tags=["reportes"]
)
def generar_reporte_compras(
    filtros: FiltrosReporteRequest,
    current_user: dict = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Endpoint para reporte consolidado de compras.
    
    Given que ingreso un rango de fechas válido,
    When genero el reporte de compras,
    Then veo una tabla con total comprado por proveedor y medicamento.
    
    excepciones:
    - 400: rango de fechas inválido o supera 12 meses
    - 401: no autenticado
    - 403:  no es administrador
    - 404: no se encontraron compras en el período
    - 500: error en base de datos
    """
    try:
        service = ReporteService(db)
        resultado = service.generar_reporte_compras(
            fecha_inicio=filtros.fecha_inicio,
            fecha_fin=filtros.fecha_fin,
            proveedor_id=filtros.proveedor_id,
            medicamento_id=filtros.medicamento_id
        )
        
        #si el servicio retorna error
        if not resultado.get('ok', False):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=resultado.get('message', 'Error al generar reporte')
            )
        
        #si no hay datos, retornar con mensaje pero status 200
        return resultado
        
    except ValidationError as ve:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(ve)
        )
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error inesperado en generar_reporte_compras: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error interno del servidor al generar reporte"
        )


@router.get(
    "/health",
    summary="Health check del módulo de reportes",
    tags=["reportes"]
)
def reportes_health():
    """
    endpoint simple para verificar que el modulo de reportes esta funcionando.
    no requiere autenticacion.
    """
    return {
        "status": "ok",
        "module": "reportes",
        "message": "modulo de reportes operativo"
    }
"""
Routes para gestión de ventas.
HU-3.01: Registro de Ventas con FIFO/FEFO
HU-3.02: Reportes y Proyecciones de Ventas
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from database.connection import get_db
from auth.security import get_current_user, require_farmaceutico_or_admin, require_admin
from services.venta_service import VentaService
from services.reporte_ventas_service import ReporteVentasService
from schemas.venta import (
    VentaCreate,
    VentaResponse,
    VentaConfirmarPago,
    VentaConfirmarResponse,
    FiltrosReporteVentas,
    ReporteVentasResponse,
    FiltrosProyeccionVentas,
    ProyeccionVentasResponse,
    EstadisticasVentas,
    EstadoVentaEnum
)
from schemas.response import StandardResponse
from typing import List, Optional, Union
from pydantic import ValidationError
from datetime import date


router = APIRouter()


# ==================== HEALTH CHECK ====================
# Debe ir primero para no ser capturado por rutas dinámicas

@router.get(
    "/health",
    summary="Health check del módulo de ventas",
    tags=["ventas"]
)
def ventas_health():
    """
    Endpoint simple para verificar que el módulo de ventas está funcionando.
    No requiere autenticación.
    """
    return {
        "status": "ok",
        "module": "ventas",
        "message": "Módulo de ventas operativo"
    }


# ==================== ESTADÍSTICAS ====================
# IMPORTANTE: Debe ir ANTES de /{venta_id} para no ser capturado

@router.get(
    "/estadisticas",
    response_model=Union[EstadisticasVentas, StandardResponse],
    summary="Obtener estadísticas de ventas",
    description="Obtiene estadísticas generales de ventas en un período",
    tags=["reportes-ventas"]
)
def obtener_estadisticas_ventas(
    fecha_inicio: Optional[date] = Query(None),
    fecha_fin: Optional[date] = Query(None),
    current_user: dict = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Obtiene estadísticas generales de ventas"""
    try:
        service = ReporteVentasService(db)
        resultado = service.obtener_estadisticas_ventas(
            fecha_inicio=fecha_inicio,
            fecha_fin=fecha_fin
        )
        
        if not resultado.get('ok', False):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=resultado.get('message', 'Error al obtener estadísticas')
            )
        
        return resultado
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error en obtener_estadisticas_ventas: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error al obtener estadísticas"
        )


# ==================== REPORTES Y PROYECCIONES (HU-3.02) ====================
# Deben ir ANTES de /{venta_id} para no ser capturados

@router.post(
    "/reportes/ventas",
    response_model=Union[ReporteVentasResponse, StandardResponse],
    summary="Generar reporte de ventas por período",
    description="""
    **HU-3.02: Reporte de Ventas**
    
    Genera reporte consolidado de ventas por período.
    
    **Características:**
    - Muestra medicamentos vendidos con unidades e ingresos
    - Calcula totales y subtotales automáticamente
    - Rango máximo: 12 meses
    
    **Alcance:**
    - Tabla con: Medicamento, Unidades vendidas, Ingresos totales
    - Total general de ventas e ingresos
    
    **Solo para administradores**
    """,
    tags=["reportes-ventas"]
)
def generar_reporte_ventas(
    filtros: FiltrosReporteVentas,
    current_user: dict = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Genera reporte de ventas por período.
    
    Given que ingreso un rango de fechas válido,
    When genero el reporte de ventas,
    Then veo una tabla con medicamentos vendidos, unidades e ingresos.
    """
    try:
        service = ReporteVentasService(db)
        resultado = service.generar_reporte_ventas(
            fecha_inicio=filtros.fecha_inicio,
            fecha_fin=filtros.fecha_fin,
            medicamento_id=filtros.medicamento_id,
            estado=filtros.estado.value if filtros.estado else None
        )
        
        if not resultado.get('ok', False):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=resultado.get('message', 'Error al generar reporte')
            )
        
        return resultado
        
    except ValidationError as ve:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(ve)
        )
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error inesperado en generar_reporte_ventas: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error interno al generar reporte"
        )


@router.post(
    "/reportes/proyeccion",
    response_model=Union[ProyeccionVentasResponse, StandardResponse],
    summary="Generar proyección de demanda",
    description="""
    **HU-3.02: Proyección de Ventas**
    
    Genera proyección de demanda basada en historial de ventas.
    
    **Método de cálculo:**
    - Promedio móvil simple sobre historial
    - Proyección = (Promedio mensual) × (Período en meses)
    
    **Requisitos:**
    - Mínimo 6 meses de historial (ideal 12)
    - Solo ventas confirmadas
    
    **Información incluida:**
    - Demanda proyectada por medicamento
    - Stock actual vs recomendado
    - Tendencia (CRECIENTE, ESTABLE, DECRECIENTE)
    - Nivel de confianza (ALTA, MEDIA, BAJA)
    
    **Solo para administradores**
    """,
    tags=["reportes-ventas"]
)
def generar_proyeccion_demanda(
    filtros: FiltrosProyeccionVentas,
    current_user: dict = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Genera proyección de demanda.
    
    Given historial ventas 12 meses,
    When solicito proyección a 90 días,
    Then muestro estimación por medicamento y gráfico de tendencia.
    """
    try:
        service = ReporteVentasService(db)
        resultado = service.generar_proyeccion_demanda(
            periodo_dias=int(filtros.periodo_dias.value),
            meses_historico=filtros.meses_historico,
            medicamento_id=filtros.medicamento_id
        )
        
        if not resultado.get('ok', False):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=resultado.get('message', 'Error al generar proyección')
            )
        
        return resultado
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error inesperado en generar_proyeccion_demanda: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error interno al generar proyección"
        )


# ==================== CRUD DE VENTAS ====================

@router.post(
    "/",
    response_model=StandardResponse,
    summary="Crear nueva venta",
    description="""
    **HU-3.01: Registro de Ventas**
    
    Crea una nueva venta con o sin confirmación de pago.
    
    **Características:**
    - Valida stock disponible antes de crear
    - Si `confirmar_pago=True`, descuenta stock automáticamente usando FIFO/FEFO
    - Genera número de venta automático (VT-2025-0001)
    
    **Métodos de descuento:**
    - **FIFO**: First In, First Out (lote más antiguo primero)
    - **FEFO**: First Expired, First Out (vencimiento más próximo primero)
    
    **Reglas de negocio:**
    - No se permite vender productos sin stock
    - Si un lote no tiene suficiente cantidad, se toma del siguiente automáticamente
    - Solo farmacéuticos y administradores pueden registrar ventas
    """,
    tags=["ventas"]
)
def crear_venta(
    venta: VentaCreate,
    current_user: dict = Depends(require_farmaceutico_or_admin),
    db: Session = Depends(get_db)
):
    """
    Crea una venta nueva con opción de confirmar pago.
    
    Given venta completada en POS,
    When confirmar pago,
    Then crear registro de venta y disminuir stock por lotes FIFO/FEFO.
    """
    try:
        service = VentaService(db)
        
        # Preparar detalles
        detalles = [
            {
                'medicamento_id': d.medicamento_id,
                'cantidad': d.cantidad,
                'precio_unitario': d.precio_unitario
            }
            for d in venta.detalles
        ]
        
        resultado = service.crear_venta(
            detalles=detalles,
            usuario_id=current_user['sub'],
            metodo_pago=venta.metodo_pago.value if venta.metodo_pago else None,
            cliente_nombre=venta.cliente_nombre,
            cliente_documento=venta.cliente_documento,
            observaciones=venta.observaciones,
            metodo_descuento=venta.metodo_descuento.value,
            confirmar_pago=venta.confirmar_pago
        )
        
        if not resultado.get('ok', False):
            status_code = status.HTTP_400_BAD_REQUEST
            if resultado.get('error') == 'not_found':
                status_code = status.HTTP_404_NOT_FOUND
            elif resultado.get('error') == 'insufficient_stock':
                status_code = status.HTTP_400_BAD_REQUEST
            
            raise HTTPException(
                status_code=status_code,
                detail=resultado.get('message', 'Error al crear venta')
            )
        
        # Retornar respuesta estándar
        return StandardResponse(
            ok=True,
            message=resultado.get('message', 'Venta creada exitosamente'),
            data=resultado.get('data'),
            error=None
        )
        
    except ValidationError as ve:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(ve)
        )
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error inesperado en crear_venta: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error interno del servidor al crear venta"
        )


@router.get(
    "/",
    response_model=List[VentaResponse],
    summary="Listar ventas",
    description="Obtiene lista de ventas con filtros opcionales",
    tags=["ventas"]
)
def listar_ventas(
    estado: Optional[EstadoVentaEnum] = Query(None, description="Filtrar por estado"),
    fecha_inicio: Optional[date] = Query(None, description="Fecha inicio"),
    fecha_fin: Optional[date] = Query(None, description="Fecha fin"),
    current_user: dict = Depends(require_farmaceutico_or_admin),
    db: Session = Depends(get_db)
):
    """Lista todas las ventas con filtros opcionales"""
    try:
        service = VentaService(db)
        ventas = service.obtener_ventas(
            estado=estado.value if estado else None,
            fecha_inicio=fecha_inicio,
            fecha_fin=fecha_fin
        )
        return ventas
        
    except Exception as e:
        print(f"Error en listar_ventas: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error al obtener ventas"
        )


# ==================== RUTAS CON PARÁMETROS DINÁMICOS ====================
# IMPORTANTE: Estas rutas deben ir AL FINAL para no capturar rutas específicas

@router.get(
    "/{venta_id}",
    response_model=Union[VentaResponse, StandardResponse],
    summary="Obtener venta por ID",
    description="Obtiene detalles completos de una venta",
    tags=["ventas"]
)
def obtener_venta(
    venta_id: str,
    current_user: dict = Depends(require_farmaceutico_or_admin),
    db: Session = Depends(get_db)
):
    """Obtiene una venta por su ID con todos los detalles"""
    try:
        service = VentaService(db)
        venta = service.obtener_venta_por_id(venta_id)
        
        if not venta:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Venta no encontrada"
            )
        
        return venta
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error en obtener_venta: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error al obtener venta"
        )


@router.post(
    "/{venta_id}/confirmar-pago",
    response_model=Union[VentaConfirmarResponse, StandardResponse],
    summary="Confirmar pago de venta pendiente",
    description="""
    **HU-3.01: Confirmación de Pago**
    
    Confirma el pago de una venta pendiente y descuenta stock automáticamente.
    
    **Regla de negocio:**
    - "El registro solo debe generarse si el estado del pago = 'Confirmado'"
    - Descuenta stock usando FIFO o FEFO según se especifique
    - Registra movimientos de salida por cada lote afectado
    """,
    tags=["ventas"]
)
def confirmar_pago_venta(
    venta_id: str,
    confirmacion: VentaConfirmarPago,
    current_user: dict = Depends(require_farmaceutico_or_admin),
    db: Session = Depends(get_db)
):
    """
    Confirma el pago de una venta pendiente.
    
    Given que una venta se completa en el POS,
    When confirmo el pago,
    Then se registra la venta en el historial y se descuenta el stock.
    """
    try:
        service = VentaService(db)
        resultado = service.confirmar_pago_venta(
            venta_id=venta_id,
            metodo_pago=confirmacion.metodo_pago.value,
            usuario_id=current_user['sub'],
            metodo_descuento=confirmacion.metodo_descuento.value
        )
        
        if not resultado.get('ok', False):
            status_code = status.HTTP_400_BAD_REQUEST
            if resultado.get('error') == 'not_found':
                status_code = status.HTTP_404_NOT_FOUND
            elif resultado.get('error') == 'already_confirmed':
                status_code = status.HTTP_400_BAD_REQUEST
            elif resultado.get('error') == 'cancelled':
                status_code = status.HTTP_400_BAD_REQUEST
            
            raise HTTPException(
                status_code=status_code,
                detail=resultado.get('message', 'Error al confirmar pago')
            )
        
        return resultado
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error inesperado en confirmar_pago_venta: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error interno al confirmar pago"
        )

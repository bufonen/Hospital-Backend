"""
Schemas Pydantic para Ventas.
HU-3.01: Registro de Ventas
HU-3.02: Reporte y Proyección de Ventas
"""
from pydantic import BaseModel, Field, field_validator
from typing import List, Optional
from datetime import datetime, date
from decimal import Decimal
from enum import Enum


# ==================== ENUMS ====================

class EstadoVentaEnum(str, Enum):
    PENDIENTE = "PENDIENTE"
    CONFIRMADA = "CONFIRMADA"
    CANCELADA = "CANCELADA"


class MetodoPagoEnum(str, Enum):
    EFECTIVO = "EFECTIVO"
    TARJETA = "TARJETA"
    TRANSFERENCIA = "TRANSFERENCIA"
    OTRO = "OTRO"


class MetodoDescuentoEnum(str, Enum):
    """Método para seleccionar lotes al descontar stock"""
    FIFO = "FIFO"  # First In, First Out (más antiguo primero)
    FEFO = "FEFO"  # First Expired, First Out (vence primero)


# ==================== DETALLE VENTA ====================

class DetalleVentaCreate(BaseModel):
    """Schema para crear un detalle de venta"""
    medicamento_id: str = Field(..., description="ID del medicamento")
    cantidad: int = Field(..., gt=0, description="Cantidad a vender")
    precio_unitario: Optional[Decimal] = Field(None, description="Precio unitario (si no se provee, se usa el del medicamento)")
    
    class Config:
        from_attributes = True


class DetalleVentaResponse(BaseModel):
    """Schema para respuesta de detalle de venta"""
    id: str
    venta_id: str
    medicamento_id: str
    cantidad: int
    precio_unitario: Decimal
    subtotal: Decimal
    lote: Optional[str] = None
    
    # Información adicional del medicamento
    medicamento_nombre: Optional[str] = None
    medicamento_fabricante: Optional[str] = None
    medicamento_presentacion: Optional[str] = None
    
    class Config:
        from_attributes = True


class DesgloseLoteResponse(BaseModel):
    """Desglose de descuento por lote (FIFO/FEFO)"""
    medicamento_id: str
    lote: str
    cantidad_descontada: int
    stock_anterior: int
    stock_nuevo: int
    fecha_vencimiento: Optional[date] = None


# ==================== VENTA ====================

class VentaCreate(BaseModel):
    """
    Schema para crear una venta.
    
    HU-3.01: "Given venta completada en POS, When confirmar pago,
              Then crear registro de venta y disminuir stock por lotes FIFO/FEFO"
    """
    detalles: List[DetalleVentaCreate] = Field(..., min_length=1, description="Items de la venta")
    metodo_pago: Optional[MetodoPagoEnum] = Field(None, description="Método de pago")
    cliente_nombre: Optional[str] = Field(None, max_length=200)
    cliente_documento: Optional[str] = Field(None, max_length=50)
    observaciones: Optional[str] = Field(None, max_length=500)
    metodo_descuento: MetodoDescuentoEnum = Field(
        default=MetodoDescuentoEnum.FEFO, 
        description="Método para descontar stock: FIFO o FEFO"
    )
    confirmar_pago: bool = Field(
        default=False, 
        description="Si True, confirma el pago y descuenta stock automáticamente"
    )
    
    class Config:
        from_attributes = True


class VentaResponse(BaseModel):
    """Schema para respuesta de venta - CORREGIDO para campos opcionales"""
    id: str
    numero_venta: str
    fecha_venta: datetime
    estado: EstadoVentaEnum
    metodo_pago: Optional[MetodoPagoEnum] = None
    total: Decimal
    cliente_nombre: Optional[str] = None
    cliente_documento: Optional[str] = None
    observaciones: Optional[str] = None
    created_by: Optional[str] = None
    created_at: Optional[datetime] = None
    confirmada_at: Optional[datetime] = None
    cancelada_at: Optional[datetime] = None
    detalles: List[DetalleVentaResponse] = []
    
    class Config:
        from_attributes = True


class VentaConfirmarPago(BaseModel):
    """
    Schema para confirmar el pago de una venta.
    
    HU-3.01: "El registro solo debe generarse si el estado del pago = 'Confirmado'"
    """
    metodo_pago: MetodoPagoEnum = Field(..., description="Método de pago utilizado")
    metodo_descuento: MetodoDescuentoEnum = Field(
        default=MetodoDescuentoEnum.FEFO,
        description="Método para descontar stock: FIFO o FEFO"
    )


class VentaConfirmarResponse(BaseModel):
    """Response de confirmación con desglose de descuento"""
    venta: VentaResponse
    desglose_descuento: List[DesgloseLoteResponse]
    mensaje: str = "Venta confirmada y stock descontado exitosamente"


# ==================== REPORTES DE VENTAS (HU-3.02) ====================

class FiltrosReporteVentas(BaseModel):
    """
    Filtros para generar reportes de ventas.
    
    HU-3.02: Validaciones de rango de fechas
    """
    fecha_inicio: date = Field(..., description="Fecha de inicio del período")
    fecha_fin: date = Field(..., description="Fecha de fin del período")
    medicamento_id: Optional[str] = Field(None, description="Filtrar por medicamento")
    estado: Optional[EstadoVentaEnum] = Field(None, description="Filtrar por estado")
    
    @field_validator('fecha_fin')
    @classmethod
    def validar_rango_fechas(cls, fecha_fin: date, info) -> date:
        """
        Valida que:
        1. Fecha fin >= fecha inicio
        2. Rango no supere 12 meses
        
        HU-3.02: "El rango de fechas no puede superar 12 meses"
        """
        fecha_inicio = info.data.get('fecha_inicio')
        
        if not fecha_inicio:
            return fecha_fin
        
        # Validar orden
        if fecha_fin < fecha_inicio:
            raise ValueError('La fecha de fin debe ser mayor o igual a la fecha de inicio')
        
        # Validar rango máximo (12 meses = ~365 días)
        dias_diferencia = (fecha_fin - fecha_inicio).days
        if dias_diferencia > 365:
            raise ValueError('El rango máximo permitido es de 12 meses (365 días)')
        
        return fecha_fin


class VentaPorMedicamento(BaseModel):
    """Ventas consolidadas por medicamento"""
    medicamento_id: str
    medicamento_nombre: str
    medicamento_fabricante: str
    medicamento_presentacion: str
    total_unidades: int
    total_ingresos: Decimal
    numero_ventas: int
    precio_promedio: Decimal


class ReporteVentasResponse(BaseModel):
    """
    Response del reporte de ventas por período.
    
    HU-3.02: "When genero el reporte de ventas
              Then veo una tabla con medicamentos vendidos, unidades e ingresos"
    """
    fecha_inicio: date
    fecha_fin: date
    total_ventas: int
    total_medicamentos: int
    gran_total_ingresos: Decimal
    ventas_por_medicamento: List[VentaPorMedicamento]
    mensaje: Optional[str] = None
    
    class Config:
        from_attributes = True


# ==================== PROYECCIONES (HU-3.02) ====================

class PeriodoProyeccionEnum(str, Enum):
    """Período de proyección disponible"""
    DIAS_30 = "30"
    DIAS_60 = "60"
    DIAS_90 = "90"


class ProyeccionMedicamento(BaseModel):
    """Proyección de demanda para un medicamento"""
    medicamento_id: str
    medicamento_nombre: str
    medicamento_fabricante: str
    medicamento_presentacion: str
    
    # Datos históricos
    promedio_mensual: Decimal
    total_historico: int
    meses_con_datos: int
    
    # Proyección
    demanda_proyectada: Decimal
    stock_actual: int
    stock_recomendado: int
    requiere_reposicion: bool
    
    # Tendencia
    tendencia: str  # "CRECIENTE", "ESTABLE", "DECRECIENTE", "SIN_DATOS"
    confianza: str  # "ALTA", "MEDIA", "BAJA"


class ProyeccionVentasResponse(BaseModel):
    """
    Response de proyección de ventas.
    
    HU-3.02: "Given historial ventas 12 meses,
              When solicito proyección a 90 días,
              Then muestro estimación por medicamento y gráfico de tendencia"
    """
    fecha_corte: date
    periodo_proyeccion_dias: int
    meses_historial: int
    proyecciones: List[ProyeccionMedicamento]
    mensaje: Optional[str] = None
    advertencias: List[str] = []
    
    class Config:
        from_attributes = True


class FiltrosProyeccionVentas(BaseModel):
    """Filtros para generar proyecciones"""
    periodo_dias: PeriodoProyeccionEnum = Field(
        default=PeriodoProyeccionEnum.DIAS_90,
        description="Período de proyección: 30, 60 o 90 días"
    )
    medicamento_id: Optional[str] = Field(None, description="Proyectar solo un medicamento")
    meses_historico: int = Field(
        default=12,
        ge=6,
        le=24,
        description="Meses de historial a considerar (mínimo 6, máximo 24)"
    )


# ==================== ESTADÍSTICAS ====================

class EstadisticasVentas(BaseModel):
    """Estadísticas generales de ventas"""
    total_ventas_confirmadas: int
    total_ventas_pendientes: int
    total_ingresos: Decimal
    medicamento_mas_vendido: Optional[str] = None
    promedio_venta: Decimal
    periodo_analizado: str
    
    class Config:
        from_attributes = True
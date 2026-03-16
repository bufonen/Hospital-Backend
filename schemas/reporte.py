"""
Schemas Pydantic para Reportes de Compras.
HU-4.03: Comparación de Precios
"""
from pydantic import BaseModel, Field, field_validator
from typing import List, Optional
from datetime import date
from decimal import Decimal


# ==================== COMPARACIÓN DE PRECIOS ====================

class ComparacionProveedorPrecio(BaseModel):
    """
    Datos de un proveedor en la comparación de precios.
    """
    proveedor_id: str
    proveedor_nombre: str
    proveedor_nit: str
    total_unidades_compradas: int
    total_dinero_invertido: Decimal
    precio_promedio: Decimal  # Total dinero / Total unidades
    numero_ordenes: int  # Cantidad de órdenes del proveedor
    
    class Config:
        from_attributes = True


class ComparacionPorMedicamento(BaseModel):
    """
    Comparación de precios de un medicamento entre proveedores.
    """
    medicamento_id: str
    medicamento_nombre: str
    medicamento_fabricante: str
    medicamento_presentacion: str
    proveedores: List[ComparacionProveedorPrecio]
    mejor_precio_proveedor_id: Optional[str] = None  # ID del proveedor con mejor precio
    mejor_precio: Optional[Decimal] = None
    
    class Config:
        from_attributes = True


class ComparacionPreciosResponse(BaseModel):
    """
    Response completo de comparación de precios.
    """
    fecha_inicio: date
    fecha_fin: date
    total_medicamentos: int
    total_proveedores: int
    comparaciones: List[ComparacionPorMedicamento]
    mensaje: Optional[str] = None  # Para casos sin datos
    
    class Config:
        from_attributes = True


# ==================== REPORTE DE COMPRAS ====================

class ReporteCompraDetalle(BaseModel):
    """
    Detalle de compras por medicamento y proveedor.
    """
    medicamento_id: str
    medicamento_nombre: str
    medicamento_fabricante: str
    medicamento_presentacion: str
    proveedor_id: str
    proveedor_nombre: str
    proveedor_nit: str
    total_unidades_compradas: int
    total_dinero_invertido: Decimal
    numero_ordenes: int
    precio_promedio: Decimal
    
    class Config:
        from_attributes = True


class ReporteTotalesPorProveedor(BaseModel):
    """
    Totales consolidados por proveedor.
    """
    proveedor_id: str
    proveedor_nombre: str
    proveedor_nit: str
    total_ordenes: int
    total_items: int
    total_invertido: Decimal
    
    class Config:
        from_attributes = True


class ReporteComprasResponse(BaseModel):
    """
    Response completo del reporte de compras.
    """
    fecha_inicio: date
    fecha_fin: date
    total_ordenes: int
    total_proveedores: int
    total_medicamentos: int
    gran_total_invertido: Decimal
    detalles: List[ReporteCompraDetalle]
    totales_por_proveedor: List[ReporteTotalesPorProveedor]
    mensaje: Optional[str] = None
    
    class Config:
        from_attributes = True


# ==================== REQUEST FILTERS ====================

class FiltrosReporteRequest(BaseModel):
    """
    Filtros para generar reportes.
    
    HU-4.03 Validaciones:
    - Rango máximo 12 meses
    - Fecha inicio < fecha fin
    """
    fecha_inicio: date = Field(..., description="Fecha de inicio del período")
    fecha_fin: date = Field(..., description="Fecha de fin del período")
    proveedor_id: Optional[str] = Field(None, description="Filtrar por proveedor específico")
    medicamento_id: Optional[str] = Field(None, description="Filtrar por medicamento específico")
    
    @field_validator('fecha_fin')
    @classmethod
    def validar_rango_fechas(cls, fecha_fin: date, info) -> date:
        """
        Valida que:
        1. Fecha fin >= fecha inicio
        2. Rango no supere 12 meses
        
        HU-4.03: "Si el rango supera 12 meses → alerta"
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


# ==================== ESTADÍSTICAS ====================

class EstadisticasComprasResponse(BaseModel):
    """
    Estadísticas generales de compras (opcional).
    """
    total_ordenes_historico: int
    total_proveedores_activos: int
    total_invertido_historico: Decimal
    proveedor_mas_usado: Optional[str] = None
    medicamento_mas_comprado: Optional[str] = None
    
    class Config:
        from_attributes = True

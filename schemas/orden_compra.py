"""
Schemas Pydantic para Órdenes de Compra.
HU-4.02: Post-Orden
"""
from pydantic import BaseModel, Field, field_validator, ValidationError
from typing import Optional, List
from datetime import datetime, date
from decimal import Decimal
import uuid


# ==================== DETALLE ORDEN ====================

class DetalleOrdenBase(BaseModel):
    """Schema base para items de orden."""
    medicamento_id: str = Field(..., description="ID del medicamento")
    cantidad_solicitada: int = Field(..., gt=0, description="Cantidad a solicitar")
    precio_unitario: Decimal = Field(..., gt=0, description="Precio unitario del producto")
    # lote_esperado y fecha_vencimiento_esperada se llenan automáticamente del medicamento
    # No se piden en el request, se toman de la BD
    
    @field_validator('medicamento_id')
    @classmethod
    def validate_medicamento_id(cls, v: str) -> str:
        """Valida que medicamento_id sea un UUID válido."""
        try:
            uuid.UUID(v)
        except (ValueError, AttributeError, TypeError):
            raise ValueError(f'medicamento_id debe ser un UUID válido, recibido: {v}')
        return v


class DetalleOrdenCreate(DetalleOrdenBase):
    """Schema para crear item de orden."""
    pass


class DetalleOrdenOut(DetalleOrdenBase):
    """Schema de salida para items de orden."""
    id: str
    orden_compra_id: str
    cantidad_recibida: int
    subtotal: Decimal
    
    # Información registrada del medicamento al momento de crear la orden
    lote_esperado: Optional[str] = None
    fecha_vencimiento_esperada: Optional[date] = None
    
    # Información del medicamento (anidada)
    medicamento_nombre: Optional[str] = None
    medicamento_fabricante: Optional[str] = None
    medicamento_presentacion: Optional[str] = None
    
    class Config:
        from_attributes = True


# ==================== ORDEN COMPRA ====================

class OrdenCompraBase(BaseModel):
    """Schema base con campos comunes."""
    proveedor_id: str = Field(..., description="ID del proveedor")
    fecha_prevista_entrega: date = Field(..., description="Fecha prevista de entrega")
    observaciones: Optional[str] = Field(None, max_length=1000, description="Observaciones opcionales")
    
    @field_validator('proveedor_id')
    @classmethod
    def validate_proveedor_id(cls, v: str) -> str:
        """Valida que proveedor_id sea un UUID válido."""
        try:
            uuid.UUID(v)
        except (ValueError, AttributeError, TypeError):
            raise ValueError(f'proveedor_id debe ser un UUID válido, recibido: {v}')
        return v


class OrdenCompraCreate(OrdenCompraBase):
    """
    Schema para creación de orden de compra.
    
    HU-4.02: "Given que ingreso los datos obligatorios de la orden
              When guardo la orden de compra
              Then el sistema crea la orden con un ID único y estado PENDIENTE"
    
    Campos obligatorios:
    - proveedor_id
    - fecha_prevista_entrega
    - detalles (lista de productos)
    """
    detalles: List[DetalleOrdenCreate] = Field(..., min_length=1, description="Lista de productos (mínimo 1)")
    
    @field_validator('fecha_prevista_entrega')
    @classmethod
    def validate_fecha_entrega(cls, v: date) -> date:
        """
        Valida que la fecha prevista sea futura.
        HU-4.02: No permitir fechas en el pasado al CREAR una orden.
        """
        from datetime import date as dt_date
        if v < dt_date.today():
            raise ValueError('La fecha prevista de entrega no puede ser anterior a hoy')
        return v
    
    @field_validator('detalles')
    @classmethod
    def validate_detalles(cls, v: List[DetalleOrdenCreate]) -> List[DetalleOrdenCreate]:
        """Valida que haya al menos un producto."""
        if not v or len(v) == 0:
            raise ValueError('La orden debe contener al menos un producto')
        return v


class OrdenCompraUpdate(BaseModel):
    """
    Schema para actualización de orden.
    Solo permitido en estado PENDIENTE.
    """
    proveedor_id: Optional[str] = None
    fecha_prevista_entrega: Optional[date] = None
    observaciones: Optional[str] = Field(None, max_length=1000)
    
    @field_validator('fecha_prevista_entrega')
    @classmethod
    def validate_fecha_entrega(cls, v: Optional[date]) -> Optional[date]:
        """
        Valida que la fecha prevista sea futura al ACTUALIZAR una orden.
        Solo valida si se proporciona una nueva fecha.
        """
        if v is not None:
            from datetime import date as dt_date
            if v < dt_date.today():
                raise ValueError('La fecha prevista de entrega no puede ser anterior a hoy')
        return v


class OrdenCompraOut(OrdenCompraBase):
    """
    Schema de salida (response) con todos los campos.
    """
    id: str
    numero_orden: str
    estado: str
    fecha_creacion: datetime
    fecha_envio: Optional[datetime] = None
    fecha_recepcion: Optional[datetime] = None
    total_estimado: Decimal
    created_by: Optional[str] = None
    recibido_by: Optional[str] = None
    updated_at: Optional[datetime] = None
    
    # Información del proveedor (anidada)
    proveedor_nombre: Optional[str] = None
    proveedor_nit: Optional[str] = None
    
    # Detalles (productos)
    detalles: List[DetalleOrdenOut] = []
    
    # Indicadores útiles
    dias_hasta_entrega: Optional[int] = None
    esta_retrasada: bool = False
    
    class Config:
        from_attributes = True


class OrdenCompraShortOut(BaseModel):
    """Schema resumido para listas."""
    id: str
    numero_orden: str
    proveedor_nombre: str
    fecha_prevista_entrega: date
    estado: str
    total_estimado: Decimal
    
    class Config:
        from_attributes = True


# ==================== ACCIONES ESPECÍFICAS ====================

class MarcarEnviadaRequest(BaseModel):
    """Request para marcar orden como enviada."""
    fecha_envio: Optional[datetime] = Field(None, description="Fecha de envío (default: ahora)")
    observaciones: Optional[str] = Field(None, max_length=500, description="Observaciones del envío")


class RecepcionItemRequest(BaseModel):
    """Request para recepción de un item específico."""
    detalle_id: str = Field(..., description="ID del detalle (item)")
    cantidad_recibida: int = Field(..., ge=0, description="Cantidad realmente recibida")
    
    @field_validator('detalle_id')
    @classmethod
    def validate_detalle_id(cls, v: str) -> str:
        """Valida que detalle_id sea un UUID válido."""
        try:
            uuid.UUID(v)
        except (ValueError, AttributeError, TypeError):
            raise ValueError(f'detalle_id debe ser un UUID válido, recibido: {v}')
        return v


class RecepcionOrdenRequest(BaseModel):
    """
    Request para recepción completa de orden.
    
    HU-4.02: "Given que una orden de compra está en estado ENVIADA
              When registro la recepción completa de los productos
              Then el sistema actualiza el estado de la orden a RECIBIDA"
    """
    items: List[RecepcionItemRequest] = Field(..., min_length=1, description="Items recibidos")
    fecha_recepcion: Optional[datetime] = Field(None, description="Fecha de recepción (default: ahora)")
    observaciones: Optional[str] = Field(None, max_length=500, description="Observaciones de la recepción")
    
    # Opciones de actualización de inventario
    actualizar_inventario: bool = Field(True, description="Si se debe actualizar el stock automáticamente")
    crear_medicamento_si_no_existe: bool = Field(False, description="Crear medicamento si no existe en inventario")


class RecepcionOrdenResponse(BaseModel):
    """Response de recepción de orden."""
    orden_id: str
    numero_orden: str
    estado: str
    items_recibidos: int
    items_con_diferencias: List[dict] = []
    inventario_actualizado: bool
    mensaje: str

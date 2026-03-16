from pydantic import BaseModel, Field, field_validator, validator
from typing import Optional
from datetime import date, datetime
from uuid import UUID
from decimal import Decimal


class MedicamentoBase(BaseModel):
    nombre: str = Field(..., max_length=200)
    fabricante: str = Field(..., max_length=200)
    presentacion: str = Field(..., max_length=200)
    lote: str = Field(..., max_length=100)
    fecha_vencimiento: date
    stock: int = Field(..., ge=0)
    minimo_stock: Optional[int]
    precio: Decimal
    principio_activo: Optional[str]

    @field_validator('fecha_vencimiento')
    def fecha_no_pasada(cls, v: date):
        from datetime import date as _date
        if v < _date.today():
            raise ValueError('Fecha inválida: la fecha de vencimiento no puede ser anterior a hoy.')
        return v


class MedicamentoCreate(MedicamentoBase):
    pass


class MedicamentoUpdate(BaseModel):
    nombre: Optional[str]
    fabricante: Optional[str]
    presentacion: Optional[str]
    lote: Optional[str]
    fecha_vencimiento: Optional[date]
    stock: Optional[int]
    minimo_stock: Optional[int]
    precio: Optional[Decimal]

    @validator('precio')
    def coerce_precio(cls, v):
        if v is None:
            return v
        if isinstance(v, Decimal):
            return v
        try:
            return Decimal(str(v))
        except Exception:
            raise ValueError('precio inválido')


class MedicamentoOut(BaseModel):
    """Schema de salida para medicamentos (GET).
    No valida fecha de vencimiento porque medicamentos ya guardados pueden tener fechas pasadas.
    """
    id: UUID
    nombre: str
    fabricante: str
    presentacion: str
    lote: str
    fecha_vencimiento: date
    stock: int
    minimo_stock: Optional[int]
    precio: Decimal
    estado: str
    is_deleted: bool
    created_by: Optional[str]
    created_at: Optional[datetime]
    updated_by: Optional[str]
    updated_at: Optional[datetime]
    principio_activo: Optional[str]

    model_config = {"from_attributes": True}

from pydantic import BaseModel, Field
from typing import Optional, Union
from uuid import UUID as UUIDType
from datetime import datetime


class MovimientoCreate(BaseModel):
    tipo: str = Field(..., description="ENTRADA or SALIDA")
    cantidad: int = Field(..., ge=1)
    motivo: Optional[str] = None


class MovimientoOut(BaseModel):
    id: Union[str, UUIDType]
    medicamento_id: Union[str, UUIDType]
    tipo: str
    cantidad: int
    usuario_id: Optional[str]
    motivo: Optional[str]
    fecha: Optional[Union[str, datetime]]

    model_config = {"from_attributes": True}

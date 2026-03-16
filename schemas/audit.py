from pydantic import BaseModel
from typing import Optional, Any
from uuid import UUID
from datetime import datetime


class AuditLogOut(BaseModel):
    """Schema de salida para logs de auditoría."""
    id: UUID
    entidad: str
    entidad_id: UUID
    usuario_id: Optional[str]
    accion: str
    campo: Optional[str]
    valor_anterior: Optional[str]
    valor_nuevo: Optional[str]
    metadatos: Optional[Any]
    timestamp: datetime

    model_config = {"from_attributes": True}

from pydantic import BaseModel
from typing import Optional


class MedicamentoShortOut(BaseModel):
    id: str
    nombre: str
    presentacion: Optional[str]
    fabricante: Optional[str]
    principio_activo: Optional[str]
    lote: Optional[str]

    model_config = {"from_attributes": True}

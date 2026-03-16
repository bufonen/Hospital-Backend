from pydantic import BaseModel
from typing import Optional, Any
from .medicamento_v2 import MedicamentoOut


class MessageOut(BaseModel):
    message: str


class StandardResponse(BaseModel):
    """Response estándar para operaciones genéricas"""
    ok: bool
    message: Optional[str] = None
    error: Optional[str] = None
    data: Optional[Any] = None


class DeleteOut(BaseModel):
    deleted: bool
    dependencias: int


class ReactivateOut(BaseModel):
    reactivated: bool
    medicamento: Optional[MedicamentoOut]


class TokenOut(BaseModel):
    access_token: str
    token_type: str

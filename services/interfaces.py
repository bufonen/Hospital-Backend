from typing import Protocol, Optional, Dict, Any
from database import models


class IMedicamentoService(Protocol):
    def create_medicamento(self, payload: Dict[str, Any], user_id: Optional[str] = None) -> models.Medicamento:
        ...

    def get(self, med_id: str) -> Optional[models.Medicamento]:
        ...

    def list(self):
        ...

    def update_medicamento(self, med_id: str, changes: Dict[str, Any], user_id: Optional[str] = None):
        ...

    def delete_medicamento(self, med_id: str, user_id: Optional[str] = None):
        ...

    def reactivar_medicamento(self, med_id: str, user_id: Optional[str] = None):
        ...

    def registrar_movimiento(self, med_id: str, tipo: str, cantidad: int, usuario_id: Optional[str] = None, motivo: Optional[str] = None):
        ...

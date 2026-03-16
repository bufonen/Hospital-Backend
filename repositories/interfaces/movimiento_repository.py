"""
Interface para MovimientoRepository
SOLID: Interface Segregation Principle - Solo operaciones de Movimientos
"""
from typing import Protocol, List
from database import models


class IMovimientoRepository(Protocol):
    """Interfaz para operaciones CRUD de movimientos de stock.
    
    ISP: Esta interfaz contiene SOLO operaciones relacionadas con movimientos,
    separada de IMedicamentoRepository.
    """
    
    def create_movimiento(self, movimiento: models.Movimiento) -> models.Movimiento:
        """Crea un nuevo movimiento (agrega a sesión, no hace commit)."""
        ...

    def count_movimientos(self, med_id: str) -> int:
        """Cuenta la cantidad de movimientos de un medicamento."""
        ...
    
    def list_movimientos(self, med_id: str) -> List[models.Movimiento]:
        """Lista todos los movimientos de un medicamento."""
        ...

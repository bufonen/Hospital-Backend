"""
Interface para MedicamentoRepository
SOLID: Interface Segregation Principle - Solo operaciones de Medicamentos
"""
from typing import Protocol, Optional, List
from database import models


class IMedicamentoRepository(Protocol):
    """Interfaz para operaciones CRUD de medicamentos.
    
    ISP: Esta interfaz contiene SOLO operaciones relacionadas con medicamentos,
    no con movimientos (eso está en IMovimientoRepository).
    """
    
    def get(self, med_id: str) -> Optional[models.Medicamento]:
        """Obtiene un medicamento por ID."""
        ...

    def list(self) -> List[models.Medicamento]:
        """Lista todos los medicamentos no eliminados."""
        ...

    def find_by_search_key(
        self, 
        search_key: str, 
        exclude_id: Optional[str] = None, 
        include_deleted: bool = False, 
        include_inactive: bool = False
    ) -> Optional[models.Medicamento]:
        """Busca un medicamento por search_key (para detección de duplicados)."""
        ...

    def create(self, m: models.Medicamento) -> models.Medicamento:
        """Crea un nuevo medicamento (agrega a sesión, no hace commit)."""
        ...

    def update(self, m: models.Medicamento) -> models.Medicamento:
        """Actualiza un medicamento (agrega a sesión, no hace commit)."""
        ...

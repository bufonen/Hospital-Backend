"""
Implementación de IMedicamentoRepository
solid: single responsibility - solo maneja persistencia de medicamentos
"""
from sqlalchemy.orm import Session
from database import models
from typing import Optional, List
from .interfaces import IMedicamentoRepository


class MedicamentoRepository(IMedicamentoRepository):
    """Repository para operaciones CRUD de medicamentos.
    
    SRP: Responsabilidad única - Acceso a datos de medicamentos.
    ISP: Solo implementa IMedicamentoRepository, no mezcla con movimientos.
    """
    
    def __init__(self, db: Session):
        self.db = db

    def get(self, med_id: str) -> Optional[models.Medicamento]:
        """Obtiene un medicamento por ID."""
        return self.db.query(models.Medicamento).filter(
            models.Medicamento.id == med_id
        ).first()

    def list(self) -> List[models.Medicamento]:
        """Lista todos los medicamentos no eliminados."""
        return self.db.query(models.Medicamento).filter(
            models.Medicamento.is_deleted == False
        ).all()

    def find_by_search_key(
        self, 
        search_key: str, 
        exclude_id: Optional[str] = None, 
        include_deleted: bool = False, 
        include_inactive: bool = False
    ) -> Optional[models.Medicamento]:
        """Busca medicamento por search_key (detección de duplicados).

        Por defecto solo retorna registros activos y no eliminados.
        """
        q = self.db.query(models.Medicamento).filter(
            models.Medicamento.search_key == search_key
        )
        
        if not include_deleted:
            q = q.filter(models.Medicamento.is_deleted == False)
        
        if not include_inactive:
            q = q.filter(models.Medicamento.estado == models.EstadoEnum.ACTIVO)
        
        if exclude_id:
            q = q.filter(models.Medicamento.id != exclude_id)
        
        return q.first()

    def create(self, m: models.Medicamento) -> models.Medicamento:
        """Crea un nuevo medicamento.
        
        nota: Agrega a sesión pero no hace commit.
        el commit es responsabilidad del service layer (transacciones).
        """
        self.db.add(m)
        return m

    def update(self, m: models.Medicamento) -> models.Medicamento:
        """Actualiza un medicamento existente.
        
        Nota: agrega a sesión pero nO hace commit.
        El commit es responsabilidad del service layer (transacciones).
        """
        self.db.add(m)
        return m

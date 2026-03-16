"""
Implementación de IMovimientoRepository
solid: single responsibility - solo maneja persistencia de movimientos
"""
from sqlalchemy.orm import Session
from sqlalchemy import func
from database import models
from typing import List
from .interfaces import IMovimientoRepository


class MovimientoRepository(IMovimientoRepository):
    """Repository para operaciones de Movimientos.
    
    srp: Responsabilidad única - Acceso a datos de movimientos.
    """
    
    def __init__(self, db: Session):
        self.db = db

    def create_movimiento(self, movimiento: models.Movimiento) -> models.Movimiento:
        """Crea un nuevo movimiento.
        
        Nota: no hace commit, eso es responsabilidad del service layer.
        """
        self.db.add(movimiento)
        return movimiento

    def count_movimientos(self, med_id: str) -> int:
        """Cuenta cuántos movimientos tiene un medicamento."""
        return self.db.query(func.count(models.Movimiento.id)).filter(
            models.Movimiento.medicamento_id == med_id
        ).scalar() or 0
    
    def list_movimientos(self, med_id: str) -> List[models.Movimiento]:
        """Lista todos los movimientos de un medicamento."""
        return self.db.query(models.Movimiento).filter(
            models.Movimiento.medicamento_id == med_id
        ).order_by(models.Movimiento.created_at.desc()).all()

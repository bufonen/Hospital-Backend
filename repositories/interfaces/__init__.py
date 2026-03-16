"""Interfaces para repositories (Dependency Inversion Principle - SOLID)"""

from .medicamento_repository import IMedicamentoRepository
from .movimiento_repository import IMovimientoRepository
from .venta_repository import IVentaRepository


__all__ = [
    'IMedicamentoRepository',
    'IMovimientoRepository',
    'IVentaRepository',
]

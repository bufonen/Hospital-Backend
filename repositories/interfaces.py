"""
interfaces de repositories (compatibilidad)
este archivo mantiene compatibilidad con imports antiguoss
las interfaces ahora están segregadas en: repositories/interfaces/

solid: Interface Segregation Principle aplicado
"""
from .interfaces.medicamento_repository import IMedicamentoRepository
from .interfaces.movimiento_repository import IMovimientoRepository

__all__ = [
    'IMedicamentoRepository',
    'IMovimientoRepository',
    'IVentaRepository',
]

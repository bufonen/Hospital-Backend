"""
Interface para VentaRepository
SOLID: Interface Segregation Principle - Solo operaciones de Ventas
"""
from typing import Protocol, Optional, List
from database import models


class IVentaRepository(Protocol):
    """Interfaz para operaciones CRUD de ventas.
    
    ISP: Esta interfaz contiene SOLO operaciones relacionadas con ventas.
    """
    
    def create(self, venta: models.Venta) -> models.Venta:
        """Crea una nueva venta."""
        ...

    def get(self, venta_id: str) -> Optional[models.Venta]:
        """Obtiene una venta por ID."""
        ...

    def list(
        self, 
        skip: int = 0, 
        limit: int = 100,
        fecha_inicio: Optional[str] = None,
        fecha_fin: Optional[str] = None,
        usuario_id: Optional[str] = None
    ) -> List[models.Venta]:
        """Lista ventas con filtros opcionales."""
        ...

    def update(self, venta: models.Venta) -> models.Venta:
        """Actualiza una venta."""
        ...

    def delete(self, venta_id: str) -> bool:
        """Elimina una venta."""
        ...

    def get_ventas_por_periodo(
        self, 
        fecha_inicio: str, 
        fecha_fin: str
    ) -> List[models.Venta]:
        """Obtiene ventas por período específico."""
        ...

    def get_total_ventas_por_periodo(
        self, 
        fecha_inicio: str, 
        fecha_fin: str
    ) -> float:
        """Obtiene el total de ventas por período."""
        ...

    def get_cantidad_ventas_por_periodo(
        self, 
        fecha_inicio: str, 
        fecha_fin: str
    ) -> int:
        """Obtiene la cantidad de ventas por período."""
        ...

    def get_productos_mas_vendidos(
        self, 
        fecha_inicio: str, 
        fecha_fin: str, 
        limit: int = 10
    ):
        """Obtiene los productos más vendidos en un período."""
        ...
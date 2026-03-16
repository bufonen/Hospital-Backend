"""
Repository para acceso a datos de Proveedores.
HU-4.01: Implementa Repository Pattern para abstracción del acceso a datos.
"""
from sqlalchemy.orm import Session
from database.models import Proveedor, EstadoProveedorEnum
from typing import Optional, List


class ProveedorRepository:
    """
    Repository para operaciones CRUD de Proveedores.
    
    Responsabilidades (siguiendo Repository Pattern):
    - Acceso a datos de proveedores
    - NO hace commit (eso es responsabilidad del Service Layer)
    - Queries específicas de proveedores
    """
    
    def __init__(self, db: Session):
        self.db = db
    
    def create(self, proveedor: Proveedor) -> Proveedor:
        """
        Agrega un proveedor a la sesión.
        NO hace commit.
        """
        self.db.add(proveedor)
        return proveedor
    
    def get_by_id(self, proveedor_id: str) -> Optional[Proveedor]:
        """Obtiene un proveedor por ID."""
        return self.db.query(Proveedor).filter(Proveedor.id == proveedor_id).first()
    
    def get_by_nit(self, nit: str) -> Optional[Proveedor]:
        """
        Obtiene un proveedor por NIT.
        HU-4.01: "El NIT ingresado ya está asociado a un proveedor existente"
        """
        return self.db.query(Proveedor).filter(Proveedor.nit == nit).first()
    
    def list(
        self, 
        estado: Optional[EstadoProveedorEnum] = None,
        nombre: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Proveedor]:
        """
        Lista proveedores con filtros opcionales.
        
        Args:
            estado: Filtrar por estado (ACTIVO/INACTIVO)
            nombre: Búsqueda parcial por nombre
            limit: Máximo de resultados
            offset: Paginación
        """
        q = self.db.query(Proveedor)
        
        # Filtro por estado
        if estado:
            q = q.filter(Proveedor.estado == estado)
        
        # Búsqueda por nombre (case-insensitive)
        if nombre:
            q = q.filter(Proveedor.nombre.ilike(f"%{nombre}%"))
        
        # Ordenar por nombre
        q = q.order_by(Proveedor.nombre)
        
        return q.offset(offset).limit(limit).all()
    
    def update(self, proveedor: Proveedor) -> Proveedor:
        """
        Actualiza un proveedor.
        NO hace commit.
        """
        self.db.add(proveedor)
        return proveedor
    
    def count_all(self, estado: Optional[EstadoProveedorEnum] = None) -> int:
        """Cuenta total de proveedores con filtro opcional de estado."""
        q = self.db.query(Proveedor)
        if estado:
            q = q.filter(Proveedor.estado == estado)
        return q.count()
    
    def search(self, query: str, limit: int = 10) -> List[Proveedor]:
        """
        Búsqueda de proveedores por nombre o NIT.
        Útil para autocomplete/búsquedas rápidas.
        """
        q = f"%{query}%"
        return self.db.query(Proveedor).filter(
            (Proveedor.nombre.ilike(q)) | (Proveedor.nit.ilike(q))
        ).filter(
            Proveedor.estado == EstadoProveedorEnum.ACTIVO
        ).limit(limit).all()

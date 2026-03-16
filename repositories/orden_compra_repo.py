"""
Repository para acceso a datos de Órdenes de Compra.
HU-4.02: Implementa Repository Pattern.
"""
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_, or_, func
from database.models import (
    OrdenCompra, DetalleOrdenCompra, EstadoOrdenEnum, 
    Proveedor, Medicamento
)
from typing import Optional, List
from datetime import date, datetime


class OrdenCompraRepository:
    """
    Repository para operaciones CRUD de Órdenes de Compra.
    """
    
    def __init__(self, db: Session):
        self.db = db
    
    def create(self, orden: OrdenCompra) -> OrdenCompra:
        """Agrega una orden a la sesión. NO hace commit."""
        self.db.add(orden)
        return orden
    
    def get_by_id(self, orden_id: str, with_relations: bool = True) -> Optional[OrdenCompra]:
        """
        Obtiene una orden por ID.
        
        Args:
            orden_id: ID de la orden
            with_relations: Si se deben cargar proveedor y detalles (eager loading)
        """
        q = self.db.query(OrdenCompra)
        
        if with_relations:
            # Eager loading para evitar N+1 queries
            q = q.options(
                joinedload(OrdenCompra.proveedor),
                joinedload(OrdenCompra.detalles).joinedload(DetalleOrdenCompra.medicamento)
            )
        
        return q.filter(OrdenCompra.id == orden_id).first()
    
    def get_by_numero_orden(self, numero_orden: str) -> Optional[OrdenCompra]:
        """Obtiene orden por número de orden."""
        return self.db.query(OrdenCompra).filter(OrdenCompra.numero_orden == numero_orden).first()
    
    def list(
        self,
        estado: Optional[EstadoOrdenEnum] = None,
        proveedor_id: Optional[str] = None,
        fecha_desde: Optional[date] = None,
        fecha_hasta: Optional[date] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[OrdenCompra]:
        """
        Lista órdenes con filtros opcionales.
        """
        q = self.db.query(OrdenCompra).options(
            joinedload(OrdenCompra.proveedor),
            joinedload(OrdenCompra.detalles).joinedload(DetalleOrdenCompra.medicamento)
        )
        
        # Filtros
        if estado:
            q = q.filter(OrdenCompra.estado == estado)
        
        if proveedor_id:
            q = q.filter(OrdenCompra.proveedor_id == proveedor_id)
        
        if fecha_desde:
            q = q.filter(OrdenCompra.fecha_creacion >= fecha_desde)
        
        if fecha_hasta:
            q = q.filter(OrdenCompra.fecha_creacion <= fecha_hasta)
        
        # Ordenar por fecha de creación descendente
        q = q.order_by(OrdenCompra.fecha_creacion.desc())
        
        return q.offset(offset).limit(limit).all()
    
    def list_retrasadas(self) -> List[OrdenCompra]:
        """
        Lista órdenes en estado ENVIADA que ya pasaron la fecha prevista.
        HU-4.02: Detección de retrasos.
        """
        hoy = date.today()
        return self.db.query(OrdenCompra).filter(
            OrdenCompra.estado == EstadoOrdenEnum.ENVIADA,
            OrdenCompra.fecha_prevista_entrega < hoy
        ).options(
            joinedload(OrdenCompra.proveedor),
            joinedload(OrdenCompra.detalles).joinedload(DetalleOrdenCompra.medicamento)
        ).all()
    
    def list_pendientes_recepcion(self) -> List[OrdenCompra]:
        """Lista órdenes en estado ENVIADA o RETRASADA (pendientes de recibir)."""
        return self.db.query(OrdenCompra).filter(
            OrdenCompra.estado.in_([EstadoOrdenEnum.ENVIADA, EstadoOrdenEnum.RETRASADA])
        ).options(
            joinedload(OrdenCompra.proveedor),
            joinedload(OrdenCompra.detalles).joinedload(DetalleOrdenCompra.medicamento)
        ).all()
    
    def update(self, orden: OrdenCompra) -> OrdenCompra:
        """Actualiza una orden. NO hace commit."""
        self.db.add(orden)
        return orden
    
    def count_all(self, estado: Optional[EstadoOrdenEnum] = None) -> int:
        """Cuenta total de órdenes con filtro opcional de estado."""
        q = self.db.query(OrdenCompra)
        if estado:
            q = q.filter(OrdenCompra.estado == estado)
        return q.count()
    
    def get_next_numero_orden(self, year: Optional[int] = None) -> str:
        """
        Genera el siguiente número de orden secuencial.
        Formato: OC-{YEAR}-{SECUENCIAL}
        Ejemplo: OC-2025-0001
        
        HU-4.02: Número de orden único auto-generado.
        """
        if year is None:
            year = datetime.now().year
        
        # Buscar el último número de orden del año
        prefix = f"OC-{year}-"
        last_orden = self.db.query(OrdenCompra).filter(
            OrdenCompra.numero_orden.like(f"{prefix}%")
        ).order_by(OrdenCompra.numero_orden.desc()).first()
        
        if last_orden:
            # Extraer el número secuencial
            try:
                last_num = int(last_orden.numero_orden.split('-')[-1])
                next_num = last_num + 1
            except (ValueError, IndexError):
                next_num = 1
        else:
            next_num = 1
        
        return f"{prefix}{next_num:04d}"


class DetalleOrdenRepository:
    """Repository para items/detalles de órdenes."""
    
    def __init__(self, db: Session):
        self.db = db
    
    def create(self, detalle: DetalleOrdenCompra) -> DetalleOrdenCompra:
        """Agrega un detalle a la sesión. NO hace commit."""
        self.db.add(detalle)
        return detalle
    
    def get_by_id(self, detalle_id: str) -> Optional[DetalleOrdenCompra]:
        """Obtiene un detalle por ID."""
        return self.db.query(DetalleOrdenCompra).filter(
            DetalleOrdenCompra.id == detalle_id
        ).first()
    
    def list_by_orden(self, orden_id: str) -> List[DetalleOrdenCompra]:
        """Lista todos los items de una orden."""
        return self.db.query(DetalleOrdenCompra).filter(
            DetalleOrdenCompra.orden_compra_id == orden_id
        ).options(joinedload(DetalleOrdenCompra.medicamento)).all()
    
    def update(self, detalle: DetalleOrdenCompra) -> DetalleOrdenCompra:
        """Actualiza un detalle. NO hace commit."""
        self.db.add(detalle)
        return detalle
    
    def delete(self, detalle: DetalleOrdenCompra):
        """Elimina un detalle. NO hace commit."""
        self.db.delete(detalle)

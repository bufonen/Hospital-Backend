"""
Repository para operaciones de base de datos de ventas
"""
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import desc, func
from database import models
from repositories.interfaces import IVentaRepository


class VentaRepository(IVentaRepository):
    def __init__(self, db: Session):
        self.db = db

    def create(self, venta: models.Venta) -> models.Venta:
        self.db.add(venta)
        self.db.commit()
        self.db.refresh(venta)
        return venta

    def get(self, venta_id: str) -> Optional[models.Venta]:
        return self.db.query(models.Venta).filter(models.Venta.id == venta_id).first()

    def list(
        self, 
        skip: int = 0, 
        limit: int = 100,
        fecha_inicio: Optional[str] = None,
        fecha_fin: Optional[str] = None,
        usuario_id: Optional[str] = None
    ) -> List[models.Venta]:
        query = self.db.query(models.Venta)
        
        if fecha_inicio:
            query = query.filter(models.Venta.fecha >= fecha_inicio)
        if fecha_fin:
            query = query.filter(models.Venta.fecha <= fecha_fin)
        if usuario_id:
            query = query.filter(models.Venta.usuario_id == usuario_id)
            
        return query.offset(skip).limit(limit).all()

    def update(self, venta: models.Venta) -> models.Venta:
        self.db.add(venta)
        self.db.commit()
        self.db.refresh(venta)
        return venta

    def delete(self, venta_id: str) -> bool:
        venta = self.get(venta_id)
        if venta:
            self.db.delete(venta)
            self.db.commit()
            return True
        return False

    def get_ventas_por_periodo(
        self, 
        fecha_inicio: str, 
        fecha_fin: str
    ) -> List[models.Venta]:
        return self.db.query(models.Venta).filter(
            models.Venta.fecha.between(fecha_inicio, fecha_fin)
        ).order_by(desc(models.Venta.fecha)).all()

    def get_total_ventas_por_periodo(
        self, 
        fecha_inicio: str, 
        fecha_fin: str
    ) -> float:
        result = self.db.query(
            func.sum(models.Venta.total)
        ).filter(
            models.Venta.fecha.between(fecha_inicio, fecha_fin)
        ).scalar()
        
        return float(result) if result else 0.0

    def get_cantidad_ventas_por_periodo(
        self, 
        fecha_inicio: str, 
        fecha_fin: str
    ) -> int:
        return self.db.query(models.Venta).filter(
            models.Venta.fecha.between(fecha_inicio, fecha_fin)
        ).count()

    def get_productos_mas_vendidos(
        self, 
        fecha_inicio: str, 
        fecha_fin: str, 
        limit: int = 10
    ):
        return self.db.query(
            models.Medicamento.id,
            models.Medicamento.nombre,
            func.sum(models.DetalleVenta.cantidad).label('cantidad_vendida'),
            func.sum(models.DetalleVenta.subtotal).label('total_ventas')
        ).join(
            models.DetalleVenta,
            models.DetalleVenta.medicamento_id == models.Medicamento.id
        ).join(
            models.Venta,
            models.Venta.id == models.DetalleVenta.venta_id
        ).filter(
            models.Venta.fecha.between(fecha_inicio, fecha_fin)
        ).group_by(
            models.Medicamento.id,
            models.Medicamento.nombre
        ).order_by(
            desc('cantidad_vendida')
        ).limit(limit).all()
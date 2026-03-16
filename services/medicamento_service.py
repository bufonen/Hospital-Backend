"""
Service para lógica de negocio de medicamentos
solid: single responsibility - Lógica de negocio de medicamentos y movimientos
"""
from repositories.medicamento_repo import MedicamentoRepository
from repositories.movimiento_repo import MovimientoRepository
from repositories.interfaces import IMedicamentoRepository, IMovimientoRepository
from database import models
from sqlalchemy.orm import Session
from typing import Optional, Dict, Any
import contextlib
from utils.text import normalize_text


class MedicamentoService:
    """Service para manejar lógica de negocio de medicamentos.
    
    SRP: Responsabilidad única - Lógica de negocio de medicamentos.
    DIP: Depende de abstracciones (IMedicamentoRepository, IMovimientoRepository), no de concreciones.
    ISP: Usa interfaces segregadas según necesidad.
    """
    
    def __init__(
        self, 
        db: Session, 
        medicamento_repo: Optional[IMedicamentoRepository] = None,
        movimiento_repo: Optional[IMovimientoRepository] = None
    ):
        """Constructor con inyección de dependencias (DIP).
        
        Args:
            db: Sesión de SQLAlchemy
            medicamento_repo: Repository de medicamentos (inyectable para testing)
            movimiento_repo: Repository de movimientos (inyectable para testing)
        """
        self.db = db
        
        if medicamento_repo is None:
            self.medicamento_repo: IMedicamentoRepository = MedicamentoRepository(db)
        else:
            self.medicamento_repo = medicamento_repo
        
        if movimiento_repo is None:
            self.movimiento_repo: IMovimientoRepository = MovimientoRepository(db)
        else:
            self.movimiento_repo = movimiento_repo
        
        #mantener compatibilidad con código existente
        self.repo = self.medicamento_repo

    def create_medicamento(self, payload: Dict[str, Any], user_id: Optional[str] = None) -> models.Medicamento:
        m = models.Medicamento(**payload)
        m.created_by = user_id
        if getattr(m, 'principio_activo', None):
            m.principio_activo_search = normalize_text(m.principio_activo)
        try:
            self.repo.create(m)
            self.db.flush()
            self.db.refresh(m)
            self.db.commit()
            
            # VERIFICACIÓN AUTOMÁTICA DE ALERTAS EN TIEMPO REAL
            try:
                from services.alert_service import AlertService
                alert_service = AlertService(self.db)
                alert_service.check_medicamento_alerts(str(m.id))
            except Exception as e:
                # No fallar la creación si hay error en alertas
                print(f"Error verificando alertas para medicamento {m.id}: {e}")
            
            return m
        except Exception:
            try:
                self.db.rollback()
            except Exception:
                pass
            raise

    def get(self, med_id: str) -> Optional[models.Medicamento]:
        return self.repo.get(med_id)

    def list(self):
        return self.repo.list()

    def update_medicamento(self, med_id: str, changes: Dict[str, Any], user_id: Optional[str] = None):
        m = self.repo.get(med_id)
        if not m:
            return None

        audit_entries = []
        for field, new in changes.items():
            old = getattr(m, field)
            if new != old:
                audit_entries.append((field, old, new))
                setattr(m, field, new)

        if not audit_entries:
            return {'updated': False}

        m.updated_by = user_id
        if 'principio_activo' in changes:
            if changes.get('principio_activo'):
                m.principio_activo_search = normalize_text(changes.get('principio_activo'))
            else:
                m.principio_activo_search = None
        try:
            self.repo.update(m)
            for field, old, new in audit_entries:
                al = models.AuditLog(entidad='medicamentos', entidad_id=m.id, usuario_id=user_id, accion='UPDATE', campo=field, valor_anterior=str(old), valor_nuevo=str(new))
                self.db.add(al)
            self.db.flush()
            self.db.refresh(m)
            self.db.commit()
            
            # VERIFICACIÓN AUTOMÁTICA DE ALERTAS EN TIEMPO REAL
            # Si cambió stock, minimo_stock o fecha_vencimiento, verificar alertas
            campos_relevantes = {'stock', 'minimo_stock', 'fecha_vencimiento'}
            if any(field in campos_relevantes for field, _, _ in audit_entries):
                try:
                    from services.alert_service import AlertService
                    alert_service = AlertService(self.db)
                    alert_service.check_medicamento_alerts(str(m.id))
                except Exception as e:
                    print(f"Error verificando alertas para medicamento {m.id}: {e}")
            
            return {'updated': True, 'medicamento': m}
        except Exception:
            try:
                self.db.rollback()
            except Exception:
                pass
            return {'updated': False}

    def delete_medicamento(self, med_id: str, user_id: Optional[str] = None):
        m = self.repo.get(med_id)
        if not m:
            return None

        count = self.movimiento_repo.count_movimientos(med_id)

        from datetime import datetime

        if count and count > 0:
            m.estado = models.EstadoEnum.INACTIVO
            m.is_deleted = False
            m.deleted_by = None
            m.deleted_at = None
            m.updated_by = user_id

            try:
                self.repo.update(m)
                al = models.AuditLog(entidad='medicamentos', entidad_id=m.id, usuario_id=user_id, accion='DEACTIVATE', metadatos={"dependencias": count})
                self.db.add(al)
                self.db.flush()
                self.db.commit()
            except Exception:
                try:
                    self.db.rollback()
                except Exception:
                    pass
            return {'deleted': False, 'dependencias': count}

        # Solo cambiar estado a INACTIVO
        m.estado = models.EstadoEnum.INACTIVO
        m.is_deleted = False
        m.deleted_by = user_id
        import datetime as _dt
        m.deleted_at = _dt.datetime.now(_dt.timezone.utc)

        try:
            self.repo.update(m)
            al = models.AuditLog(entidad='medicamentos', entidad_id=m.id, usuario_id=user_id, accion='DEACTIVATE', metadatos={"dependencias": count})
            self.db.add(al)
            self.db.flush()
            self.db.commit()
            return {'deleted': True, 'dependencias': count}
        except Exception:
            try:
                self.db.rollback()
            except Exception:
                pass
            return {'deleted': False, 'dependencias': count}

    def reactivar_medicamento(self, med_id: str, user_id: Optional[str] = None):
        m = self.repo.get(med_id)
        if not m:
            return None

        from datetime import date
        if m.fecha_vencimiento < date.today():
            return {'reactivated': False, 'reason': 'expired'}

        m.is_deleted = False
        m.estado = models.EstadoEnum.ACTIVO
        m.deleted_by = None
        m.deleted_at = None
        m.updated_by = user_id

        try:
            self.repo.update(m)
            al = models.AuditLog(entidad='medicamentos', entidad_id=m.id, usuario_id=user_id, accion='REACTIVATE')
            self.db.add(al)
            self.db.flush()
            self.db.refresh(m)
            self.db.commit()
            
            # VERIFICACIÓN AUTOMÁTICA DE ALERTAS EN TIEMPO REAL
            # Al reactivar, verificar si necesita alertas
            try:
                from services.alert_service import AlertService
                alert_service = AlertService(self.db)
                alert_service.check_medicamento_alerts(str(m.id))
            except Exception as e:
                print(f"Error verificando alertas para medicamento {m.id}: {e}")
            
            return {'reactivated': True, 'medicamento': m}
        except Exception:
            try:
                self.db.rollback()
            except Exception:
                pass
            return {'reactivated': False}

    def registrar_movimiento(self, med_id: str, tipo: str, cantidad: int, usuario_id: Optional[str] = None, motivo: Optional[str] = None):
        """Registra un movimiento (ENTRADA/SALIDA) y actualiza stock en la misma transacción.

        Reglas:
        - No permitir movimientos si el lote está inactivo (estado!=ACTIVO) o fecha_vencimiento < hoy
        - Para SALIDA, no permitir si stock < cantidad (rechazar)
        - Crear Movimiento y actualizar m.stock
        """
        from datetime import date, datetime

        m = self.repo.get(med_id)
        if not m:
            return {'ok': False, 'reason': 'not_found'}

        #validaciones
        if m.estado != models.EstadoEnum.ACTIVO:
            return {'ok': False, 'reason': 'inactive'}
        if m.fecha_vencimiento < date.today():
            return {'ok': False, 'reason': 'expired'}

        if tipo == 'SALIDA' and m.stock < cantidad:
            return {'ok': False, 'reason': 'insufficient_stock', 'available': m.stock}
        try:
            #actualiza stock
            if tipo == 'ENTRADA':
                m.stock = m.stock + cantidad
            else:
                m.stock = m.stock - cantidad

            #creo movimiento y persiste usando MovimientoRepository
            mv = models.Movimiento(medicamento_id=m.id, tipo=models.MovimientoTipoEnum[tipo], cantidad=cantidad, usuario_id=usuario_id, motivo=motivo)
            self.movimiento_repo.create_movimiento(mv)
            self.repo.update(m)

            # flush so mv.id is assigned by the DB
            self.db.flush()

            #crea audit logs
            al = models.AuditLog(entidad='movimientos', 
                                 entidad_id=mv.id, 
                                 usuario_id=usuario_id, 
                                 accion='CREATE')
            self.db.add(al)

            #commit de todo
            self.db.commit()

            try:
                self.db.refresh(mv)
            except Exception:
                pass
            
            # VERIFICACIÓN AUTOMÁTICA DE ALERTAS EN TIEMPO REAL
            # Después de cada movimiento, verificar si se debe generar/resolver alerta de stock
            try:
                from services.alert_service import AlertService
                alert_service = AlertService(self.db)
                alert_result = alert_service.check_medicamento_alerts(str(m.id))
                
                # Log si se creó/actualizó alerta
                if alert_result.get('stock_alert'):
                    action = alert_result['stock_alert'].get('action')
                    if action in ['created', 'updated']:
                        alert_type = alert_result['stock_alert'].get('type')
                        print(f"Alerta automática: {alert_type} para {m.nombre} (Stock: {m.stock})")
                    elif action == 'resolved':
                        print(f"Alerta resuelta automáticamente para {m.nombre} (Stock normalizado: {m.stock})")
            except Exception as e:
                print(f"Error verificando alertas para medicamento {m.id}: {e}")

            return {'ok': True, 'movimiento': mv, 'stock': m.stock}
        except Exception:
            try:
                self.db.rollback()
            except Exception:
                pass
            return {'ok': False, 'reason': 'error'}

    #ayuda para búsquedas de medicamentos
    def search_by_principio_activo(self, normalized_q: str, limit: int = 8):
        # se busca principio_activo usando like
        q = f"%{normalized_q}%"
        return self.db.query(models.Medicamento).filter(models.Medicamento.principio_activo_search.ilike(q), models.Medicamento.is_deleted == False).limit(limit).all()

    def search_by_nombre(self, normalized_q: str, limit: int = 8):
        q = f"%{normalized_q}%"
        return self.db.query(models.Medicamento).filter(
            models.Medicamento.nombre.ilike(q),
            models.Medicamento.is_deleted == False
        ).limit(limit).all()

    def search_by_lote(self, q_raw: str, limit: int = 8):
        q = f"%{q_raw}%"
        return self.db.query(models.Medicamento).filter(models.Medicamento.lote.ilike(q), models.Medicamento.is_deleted == False).limit(limit).all()

    def search_by_fabricante(self, normalized_q: str, limit: int = 8):
        q = f"%{normalized_q}%"
        return self.db.query(models.Medicamento).filter(models.Medicamento.fabricante.ilike(q), models.Medicamento.is_deleted == False).limit(limit).all()

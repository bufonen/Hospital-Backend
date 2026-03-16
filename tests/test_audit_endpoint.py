import pytest
import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from database.connection import Base
from database import models
from services.medicamento_service import MedicamentoService


@pytest.fixture()
def session():
    engine = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    s = Session()
    try:
        yield s
    finally:
        s.close()


def test_audit_log_created_on_update(session):
    """Verifica que se crea un log de auditoría al actualizar un medicamento."""
    # Crear medicamento
    m = models.Medicamento(
        nombre='TestMed', 
        fabricante='TestFab', 
        presentacion='Tabletas', 
        lote='L001', 
        fecha_vencimiento=datetime.date(2030, 1, 1), 
        stock=100, 
        minimo_stock=10,
        precio=50.00,
        search_key='testmed|tabletas|testfab'
    )
    session.add(m)
    session.commit()
    
    # Actualizar medicamento
    svc = MedicamentoService(session)
    res = svc.update_medicamento(str(m.id), {'precio': 75.00, 'stock': 150}, user_id='test_user')
    
    assert res['updated'] is True
    
    # Verificar que se crearon logs de auditoría
    audit_logs = session.query(models.AuditLog)\
        .filter(
            models.AuditLog.entidad == 'medicamentos',
            models.AuditLog.entidad_id == m.id
        )\
        .order_by(models.AuditLog.timestamp.desc())\
        .all()
    
    assert len(audit_logs) >= 2  # Al menos dos cambios: precio y stock
    
    # Verificar logs de precio
    precio_log = next((log for log in audit_logs if log.campo == 'precio'), None)
    assert precio_log is not None
    assert precio_log.usuario_id == 'test_user'
    assert precio_log.accion == 'UPDATE'
    assert precio_log.valor_anterior == '50.00'
    assert precio_log.valor_nuevo == '75.0'
    
    # Verificar logs de stock
    stock_log = next((log for log in audit_logs if log.campo == 'stock'), None)
    assert stock_log is not None
    assert stock_log.valor_anterior == '100'
    assert stock_log.valor_nuevo == '150'


def test_audit_log_created_on_delete(session):
    """Verifica que se crea un log de auditoría al eliminar un medicamento."""
    # Crear medicamento sin dependencias
    m = models.Medicamento(
        nombre='DelMed', 
        fabricante='DelFab', 
        presentacion='Jarabe', 
        lote='L002', 
        fecha_vencimiento=datetime.date(2030, 6, 15), 
        stock=50, 
        minimo_stock=5,
        search_key='delmed|jarabe|delfab'
    )
    session.add(m)
    session.commit()
    
    # Eliminar medicamento (soft-delete)
    svc = MedicamentoService(session)
    res = svc.delete_medicamento(str(m.id), user_id='admin_user')
    
    assert res['deleted'] is True
    
    # Verificar log de eliminación
    audit_log = session.query(models.AuditLog)\
        .filter(
            models.AuditLog.entidad == 'medicamentos',
            models.AuditLog.entidad_id == m.id,
            models.AuditLog.accion == 'DELETE_SOFT'
        )\
        .first()
    
    assert audit_log is not None
    assert audit_log.usuario_id == 'admin_user'


def test_audit_log_created_on_deactivate_with_dependencies(session):
    """Verifica que se crea un log DEACTIVATE al eliminar un medicamento con dependencias."""
    # Crear medicamento
    m = models.Medicamento(
        nombre='DepMed', 
        fabricante='DepFab', 
        presentacion='Cápsulas', 
        lote='L003', 
        fecha_vencimiento=datetime.date(2030, 12, 31), 
        stock=200, 
        minimo_stock=20,
        search_key='depmed|capsulas|depfab'
    )
    session.add(m)
    session.commit()
    
    # Agregar movimiento (crear dependencia)
    mv = models.Movimiento(
        medicamento_id=m.id, 
        tipo=models.MovimientoTipoEnum.ENTRADA, 
        cantidad=100
    )
    session.add(mv)
    session.commit()
    
    # Intentar eliminar medicamento con dependencias
    svc = MedicamentoService(session)
    res = svc.delete_medicamento(str(m.id), user_id='admin_user')
    
    # Debe marcar como inactivo, no eliminar
    assert res['deleted'] is False
    assert res['dependencias'] == 1
    
    # Verificar log de desactivación
    audit_log = session.query(models.AuditLog)\
        .filter(
            models.AuditLog.entidad == 'medicamentos',
            models.AuditLog.entidad_id == m.id,
            models.AuditLog.accion == 'DEACTIVATE'
        )\
        .first()
    
    assert audit_log is not None
    assert audit_log.usuario_id == 'admin_user'
    assert audit_log.metadatos['dependencias'] == 1

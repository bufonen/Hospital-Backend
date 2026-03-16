import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from database.connection import Base
from database import models
from services.medicamento_service import MedicamentoService
import uuid
import datetime


@pytest.fixture()
def session():
    # in-memory sqlite
    engine = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    s = Session()
    try:
        yield s
    finally:
        s.close()


def test_update_no_changes(session):
    # create medicamento
    m = models.Medicamento(nombre='X', fabricante='Y', presentacion='Z', lote='L', fecha_vencimiento=datetime.date(2030,1,1), stock=1, minimo_stock=0, search_key='x|z|y')
    session.add(m)
    session.commit()

    svc = MedicamentoService(session)
    res = svc.update_medicamento(str(m.id), {}, user_id=str(uuid.uuid4()))
    assert res['updated'] is False


def test_update_with_change_generates_audit(session):
    m = models.Medicamento(nombre='A', fabricante='B', presentacion='C', lote='L2', fecha_vencimiento=datetime.date(2030,1,1), stock=1, minimo_stock=0, search_key='a|c|b')
    session.add(m)
    session.commit()

    svc = MedicamentoService(session)
    res = svc.update_medicamento(str(m.id), {'precio': 9.99}, user_id='tester')
    assert res['updated'] is True
    # check audit log
    al = session.query(models.AuditLog).filter(models.AuditLog.entidad_id == m.id).first()
    assert al is not None
    assert al.usuario_id == 'tester'
    assert al.campo == 'precio'
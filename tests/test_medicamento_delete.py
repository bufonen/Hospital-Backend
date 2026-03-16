import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from database.connection import Base
from database import models
from services.medicamento_service import MedicamentoService
import datetime
import uuid


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


def test_delete_with_dependencies_marks_inactive(session):
    # create medicamento
    m = models.Medicamento(nombre='M1', fabricante='F1', presentacion='P1', lote='L1', fecha_vencimiento=datetime.date(2030,1,1), stock=10, minimo_stock=0, search_key='m1|p1|f1')
    session.add(m)
    session.commit()

    # add movimiento linked
    mv = models.Movimiento(medicamento_id=m.id, tipo=models.MovimientoTipoEnum.ENTRADA, cantidad=5)
    session.add(mv)
    session.commit()

    svc = MedicamentoService(session)
    res = svc.delete_medicamento(str(m.id), user_id='tester')
    # should not be physical deleted, should be marked INACTIVO and return dependencias
    assert res is not None
    assert res.get('deleted') is False or res.get('deleted') is None
    assert res.get('dependencias') == 1
    # refresh and check state
    session.refresh(m)
    assert m.estado == models.EstadoEnum.INACTIVO
    assert m.is_deleted is False


def test_delete_without_dependencies_soft_deletes(session):
    m = models.Medicamento(nombre='M2', fabricante='F2', presentacion='P2', lote='L2', fecha_vencimiento=datetime.date(2030,1,1), stock=5, minimo_stock=0, search_key='m2|p2|f2')
    session.add(m)
    session.commit()

    svc = MedicamentoService(session)
    res = svc.delete_medicamento(str(m.id), user_id='tester')
    assert res is not None
    assert res.get('deleted') is True
    assert res.get('dependencias') == 0
    session.refresh(m)
    assert m.is_deleted is True
    assert m.estado == models.EstadoEnum.INACTIVO

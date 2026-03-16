import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from database.connection import Base
from database import models
from services.medicamento_service import MedicamentoService
import datetime


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


def test_registrar_salida_valida(session):
    m = models.Medicamento(nombre='Mv1', fabricante='F', presentacion='P', lote='L', fecha_vencimiento=datetime.date(2030,1,1), stock=50, minimo_stock=0, search_key='mv1|p|f')
    session.add(m)
    session.commit()

    svc = MedicamentoService(session)
    res = svc.registrar_movimiento(str(m.id), 'SALIDA', 20, usuario_id='user1')
    assert res.get('ok') is True
    assert res.get('stock') == 30
    # movement created
    mv = res.get('movimiento')
    assert mv.cantidad == 20
    assert mv.tipo.name == 'SALIDA'


def test_registrar_salida_insuficiente(session):
    m = models.Medicamento(nombre='Mv2', fabricante='F', presentacion='P', lote='L', fecha_vencimiento=datetime.date(2030,1,1), stock=50, minimo_stock=0, search_key='mv2|p|f')
    session.add(m)
    session.commit()

    svc = MedicamentoService(session)
    res = svc.registrar_movimiento(str(m.id), 'SALIDA', 60, usuario_id='user1')
    assert res.get('ok') is False
    assert res.get('reason') == 'insufficient_stock'
    assert res.get('available') == 50


def test_registrar_movimiento_en_vencido_o_inactivo(session):
    # vencido
    m = models.Medicamento(nombre='Mv3', fabricante='F', presentacion='P', lote='L', fecha_vencimiento=datetime.date(2020,1,1), stock=10, minimo_stock=0, search_key='mv3|p|f')
    session.add(m)
    session.commit()

    svc = MedicamentoService(session)
    res = svc.registrar_movimiento(str(m.id), 'ENTRADA', 5, usuario_id='user1')
    assert res.get('ok') is False
    assert res.get('reason') == 'expired'

    # inactivo
    m2 = models.Medicamento(nombre='Mv4', fabricante='F', presentacion='P', lote='L', fecha_vencimiento=datetime.date(2030,1,1), stock=10, minimo_stock=0, search_key='mv4|p|f')
    m2.estado = models.EstadoEnum.INACTIVO
    session.add(m2)
    session.commit()

    res2 = svc.registrar_movimiento(str(m2.id), 'SALIDA', 1, usuario_id='user1')
    assert res2.get('ok') is False
    assert res2.get('reason') == 'inactive'

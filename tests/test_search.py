import datetime
import pytest
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


def test_search_by_nombre_and_principio(session):
    # create medicines
    m1 = models.Medicamento(nombre='Ibuprofeno 400 mg', fabricante='Farm S.A.', presentacion='Tabletas', lote='L1', fecha_vencimiento=datetime.date(2030,1,1), stock=10, minimo_stock=1, search_key='ibuprofeno 400 mg|tabletas|farm s.a.', principio_activo='Ibuprofeno', principio_activo_search='ibuprofeno')
    m2 = models.Medicamento(nombre='Paracetamol 500 mg', fabricante='Gen', presentacion='Tabletas', lote='L2', fecha_vencimiento=datetime.date(2030,1,1), stock=20, minimo_stock=1, search_key='paracetamol 500 mg|tabletas|gen', principio_activo='Paracetamol', principio_activo_search='paracetamol')
    session.add_all([m1, m2])
    session.commit()

    svc = MedicamentoService(session)

    # search by nombre partial
    res = svc.search_by_nombre('ibup', limit=5)
    assert any('Ibuprofeno' in x.nombre for x in res)

    # search by principio activo
    res2 = svc.search_by_principio_activo('parac', limit=5)
    assert any('Paracetamol' in x.principio_activo for x in res2)

    # search by fabricante via service
    res3 = svc.search_by_fabricante('Gen', limit=5)
    assert any('Gen' in x.fabricante for x in res3)

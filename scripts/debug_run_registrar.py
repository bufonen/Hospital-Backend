from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from database.connection import Base
from database import models
from services.medicamento_service import MedicamentoService
import datetime, traceback

engine = create_engine('sqlite:///:memory:')
Base.metadata.create_all(bind=engine)
Session = sessionmaker(bind=engine)
s = Session()
try:
    print('Creating medicamento')
    m = models.Medicamento(nombre='M1', fabricante='F1', presentacion='P1', lote='L1', fecha_vencimiento=datetime.date(2030,1,1), stock=10, minimo_stock=0, search_key='m1|p1|f1|l1')
    s.add(m)
    s.commit()
    print('m.id', m.id, 'estado before', m.estado)

    mv = models.Movimiento(medicamento_id=m.id, tipo=models.MovimientoTipoEnum.ENTRADA, cantidad=5)
    s.add(mv)
    s.commit()
    print('movimiento added, id', mv.id)

    svc = MedicamentoService(s)
    res = svc.delete_medicamento(str(m.id), user_id='tester')
    print('service returned:', res)
    try:
        s.refresh(m)
        print('m.estado after refresh', m.estado)
    except Exception:
        traceback.print_exc()

    # Now test registrar_movimiento
    print('\n-- registrar_movimiento test --')
    # create new medicamento for movimiento
    m2 = models.Medicamento(nombre='Mv1', fabricante='F', presentacion='P', lote='L', fecha_vencimiento=datetime.date(2030,1,1), stock=50, minimo_stock=0, search_key='mv1|p|f|l')
    s.add(m2)
    s.commit()
    print('m2 id', m2.id, 'stock before', m2.stock)
    res2 = svc.registrar_movimiento(str(m2.id), 'SALIDA', 20, usuario_id='user1')
    print('registrar_movimiento returned:', res2)
    try:
        s.refresh(m2)
        print('m2.stock after refresh', m2.stock)
    except Exception:
        traceback.print_exc()

except Exception:
    traceback.print_exc()
finally:
    s.close()

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from database.connection import Base
from database import models
import datetime, traceback

engine = create_engine('sqlite:///:memory:')
Base.metadata.create_all(bind=engine)
Session = sessionmaker(bind=engine)
s = Session()
try:
    # setup
    m = models.Medicamento(nombre='Mv1', fabricante='F', presentacion='P', lote='L', fecha_vencimiento=datetime.date(2030,1,1), stock=50, minimo_stock=0, search_key='mv1|p|f|l')
    s.add(m)
    s.commit()
    print('Created medicamento', m.id, 'stock', m.stock)

    # replicate service logic
    med_id = str(m.id)
    tipo = 'SALIDA'
    cantidad = 20
    usuario_id = 'user1'

    # fetch m
    m2 = s.query(models.Medicamento).filter(models.Medicamento.id == med_id).first()
    print('Fetched m2', m2.id, 'stock', m2.stock)

    # validations
    from datetime import date
    if m2.estado != models.EstadoEnum.ACTIVO:
        raise RuntimeError('inactive')
    if m2.fecha_vencimiento < date.today():
        raise RuntimeError('expired')
    if tipo == 'SALIDA' and m2.stock < cantidad:
        raise RuntimeError('insufficient_stock')

    # perform atomic operations
    # use session.begin() context
    with s.begin():
        if tipo == 'ENTRADA':
            m2.stock = m2.stock + cantidad
        else:
            m2.stock = m2.stock - cantidad

        mv = models.Movimiento(medicamento_id=m2.id, tipo=models.MovimientoTipoEnum[tipo], cantidad=cantidad, usuario_id=usuario_id, motivo=None)
        s.add(mv)
        s.add(m2)
        al = models.AuditLog(entidad='movimientos', entidad_id=mv.id, usuario_id=usuario_id, accion='CREATE')
        s.add(al)
        # flush to force SQL execution and populate IDs
        s.flush()
        print('After flush, mv.id', mv.id)

    print('Transaction committed successfully')
    s.refresh(m2)
    print('Final stock', m2.stock)

except Exception:
    traceback.print_exc()
finally:
    s.close()

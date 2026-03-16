from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from database.connection import Base
from database import models
from services.medicamento_service import MedicamentoService
import datetime

engine = create_engine('sqlite:///:memory:')
Base.metadata.create_all(bind=engine)
Session = sessionmaker(bind=engine)
s = Session()
# create med
m = models.Medicamento(nombre='Mv1', fabricante='F', presentacion='P', lote='L', fecha_vencimiento=datetime.date(2030,1,1), stock=50, minimo_stock=0, search_key='mv1|p|f|l')
s.add(m)
s.commit()

svc = MedicamentoService(s)
res = svc.registrar_movimiento(str(m.id), 'SALIDA', 20, usuario_id='user1')
print('res:', res)
# refresh
s.refresh(m)
print('stock after:', m.stock)

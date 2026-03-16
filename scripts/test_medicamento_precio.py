import sys
import os
import requests
from sqlalchemy import text

# ensure project root is on sys.path
PROJECT_ROOT = os.path.dirname(os.path.dirname(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from database.connection import engine

BASE='http://127.0.0.1:8000'
# get token
r = requests.post(f'{BASE}/api/auth/token', data={'username':'admin','password':'Admin123!'})
if r.status_code!=200:
    print('auth failed', r.status_code, r.text)
    raise SystemExit
token = r.json()['access_token']
headers={'Authorization':f'Bearer {token}','Content-Type':'application/json'}

med = {'nombre':'PrecioTest','fabricante':'LabPrice','presentacion':'Caja','lote':'LP1','fecha_vencimiento':'2030-01-01','stock':5,'minimo_stock':1,'precio':12.50}

r1 = requests.post(f'{BASE}/api/medicamentos/', json=med, headers=headers)
print('create', r1.status_code, r1.text)
med_id = r1.json().get('id')

# update precio
r2 = requests.put(f'{BASE}/api/medicamentos/{med_id}', json={'precio':15.75}, headers=headers)
print('update', r2.status_code, r2.text)

# check audit log
with engine.connect() as conn:
    res = conn.execute(text("SELECT accion, campo, valor_anterior, valor_nuevo, usuario_id FROM audit_logs WHERE entidad='medicamentos' AND entidad_id=:id ORDER BY timestamp DESC"), {'id': med_id})
    rows = res.fetchall()
    print('audit rows:', rows)

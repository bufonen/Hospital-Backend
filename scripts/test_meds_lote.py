import requests
BASE='http://127.0.0.1:8000'
# get token
r = requests.post(f'{BASE}/api/auth/token', data={'username':'admin','password':'Admin123!'})
if r.status_code!=200:
    print('auth failed', r.status_code, r.text)
    raise SystemExit
token = r.json()['access_token']
headers={'Authorization':f'Bearer {token}','Content-Type':'application/json'}

med = {'nombre':'Paracetamol','fabricante':'LabA','presentacion':'Caja','lote':'L1','fecha_vencimiento':'2030-01-01','stock':10,'minimo_stock':1}
med2 = med.copy(); med2['lote']='L2'

r1 = requests.post(f'{BASE}/api/medicamentos/', json=med, headers=headers)
print('r1', r1.status_code, r1.text)

r2 = requests.post(f'{BASE}/api/medicamentos/', json=med2, headers=headers)
print('r2', r2.status_code, r2.text)

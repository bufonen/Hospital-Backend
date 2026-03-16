import requests

BASE = 'http://127.0.0.1:8000'
# Get token
r = requests.post(f'{BASE}/api/auth/token', data={'username':'admin','password':'Admin123!'})
print('token status', r.status_code)
print(r.text)
if r.status_code != 200:
    raise SystemExit('Auth failed')

token = r.json().get('access_token')
headers = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}

payload = {
    'nombre':'Med-PS',
    'fabricante':'LabPS',
    'presentacion':'Caja',
    'lote':'L-PS1',
    'fecha_vencimiento':'2030-01-01',
    'stock': 50,
    'minimo_stock': 10
}

r2 = requests.post(f'{BASE}/api/medicamentos/', json=payload, headers=headers)
print('create status', r2.status_code)
print(r2.text)

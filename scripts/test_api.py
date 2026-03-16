from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

user = {
    "username": "apitest",
    "full_name": "API Test",
    "email": "apitest@example.com",
    "password": "Test12345",
    "role": "farmaceutico"
}

resp = client.post('/api/users/', json=user)
print('status', resp.status_code)
try:
    print('json', resp.json())
except Exception as e:
    print('raw text:', resp.text)
    raise

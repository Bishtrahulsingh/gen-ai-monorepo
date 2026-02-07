
from fastapi.testclient import TestClient
from packages.core import app

client = TestClient(app)

def test_health():
    response = client.get('/')
    assert response.status_code == 200
    assert response.json()=={'status':'ok'}
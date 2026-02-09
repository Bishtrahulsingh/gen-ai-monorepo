from starlette.testclient import TestClient
from diligence_core.app import app

client = TestClient(app)

def test_health():
    response = client.get('/health')
    assert response.status_code == 200
    assert response.json()=={'status':'ok'}
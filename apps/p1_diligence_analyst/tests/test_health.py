from starlette.testclient import TestClient
from apps.p1_diligence_analyst.app.main import app

client = TestClient(app=app)

def test_health():
    response = client.get('/health')
    assert response.status_code == 200
    assert response.json() == {'message':'app is working'}
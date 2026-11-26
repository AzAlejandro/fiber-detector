from fastapi.testclient import TestClient

from backend import distribution
from backend.main import app


def test_model_setting_reaches_coordinator(tmp_path, monkeypatch):
    path = tmp_path / 'data' / 'agent-model.txt'
    monkeypatch.setattr(distribution, 'AGENT_MODEL_PATH', path)
    monkeypatch.setattr(distribution, 'list_projects', lambda: {'active_project_id': 'demo'})
    client = TestClient(app)
    assert client.get('/api/agent/model').json()['model'] == 'gpt-6.2-sol'
    model = 'gpt-6.2-astra'
    assert client.post('/api/agent/model', json={'model': model}).json()['model'] == model
    assert client.post('/api/agent/model', json={'model': 'desconocido'}).status_code == 422
    assert path.read_text() == model
    assert client.get('/api/agent/connection').json()['agent_model'] == model
    assert model in client.get('/api/agent/guide').text

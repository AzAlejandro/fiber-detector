import json
from concurrent.futures import ThreadPoolExecutor

from fastapi.testclient import TestClient
from PIL import Image, ImageDraw

from backend import agent_mode
from backend.main import app


def test_removals_persist_and_are_isolated_by_run_and_project(tmp_path, monkeypatch):
    monkeypatch.setattr(agent_mode, 'ROOT', tmp_path)
    circles = [{'id': i, 'x': i * 10, 'y': 20, 'radius_px': 4} for i in (1, 2, 3)]
    legacy, test = '1' * 32, '2' * 32
    for rid, scope in [(legacy, {}), (test, {'project_id': 'agente-test'})]:
        folder = tmp_path / rid
        folder.mkdir()
        (folder / 'resultado.json').write_text(json.dumps({
            'image_id': 'shared', 'run_id': rid, 'created_at': rid, 'circles': circles, **scope,
        }))
    client = TestClient(app)
    def remove(index):
        client.post(f'/api/agent/runs/{test}/circles/{index}/remove').raise_for_status()
    with ThreadPoolExecutor(2) as pool:
        list(pool.map(remove, (1, 2)))
    remove(1)
    reopened = TestClient(app)
    history = reopened.get('/api/agent/runs?image_id=shared&project_id=agente-test').json()
    assert [item['run_id'] for item in history] == [test]
    assert reopened.get(f'/api/agent/runs/{test}').json()['circles'] == circles[2:]
    assert reopened.get(f'/api/agent/runs/{legacy}').json()['circles'] == circles
    remove(3)
    assert reopened.get(f'/api/agent/runs/{test}').json()['circles'] == []
    restore = f'/api/agent/runs/{test}/circles/2/restore'
    for _ in range(2):
        assert reopened.post(restore).json()['circles'] == [circles[1]]
    remove(2)
    assert reopened.get(f'/api/agent/runs/{test}').json()['circles'] == []
    assert reopened.post(f'/api/agent/runs/{test}/circles/99/restore').status_code == 404


def test_draw_manual_circles_on_existing_mask(tmp_path, monkeypatch):
    monkeypatch.setattr(agent_mode, 'ROOT', tmp_path)
    rid = '3' * 32
    folder = tmp_path / rid
    folder.mkdir()
    (folder / 'resultado.json').write_text(json.dumps(dict(circles=[], width=64, parameters={'field_height': 55})))
    mask = Image.new('L', (64, 64))
    ImageDraw.Draw(mask).rectangle((0, 30, 63, 34), fill=255)
    mask.save(folder / 'mascara.png')
    client = TestClient(app)
    url = f'/api/agent/runs/{rid}/circles'
    def draw(y):
        response = client.post(url, json=dict(x=24, y=y, radius_px=8))
        response.raise_for_status()
        return response.json()['added_circle_id']
    with ThreadPoolExecutor(2) as pool:
        fiber, background = pool.map(draw, (32, 12))
    assert fiber != background
    assert client.post(url, json=dict(x=24, y=50, radius_px=8)).status_code == 422
    saved = TestClient(app).get(f'/api/agent/runs/{rid}').json()['circles']
    assert {c['id']: c['mask_crossings'] for c in saved} == {fiber: 4, background: 0}
    assert all(c['source'] == 'manual' for c in saved)
    client.post(f'{url}/{fiber}/remove').raise_for_status()
    restored = client.post(f'{url}/{fiber}/restore').json()
    assert restored['circles'] == saved

from io import BytesIO

import numpy as np
from fastapi.testclient import TestClient
from PIL import Image

from backend import agent_masks, agent_mode
from backend.image_codec import encode_gray_png_b64
from backend.main import app


def test_saved_scribble_selects_the_actual_circle_mask(tmp_path, monkeypatch):
    photo = np.full((96, 120, 3), 150, np.uint8)
    photo[:, 30:34] = 65
    photo[:, 77:81] = 105
    photo[82:] = 255
    for module in (agent_masks, agent_mode):
        monkeypatch.setattr(module, 'load_library_image', lambda _: (
            photo[:, :, 0], {'image_name': 'fibra', 'project_ids': ['p', 'q']}))
        monkeypatch.setattr(module, 'ROOT', tmp_path / module.__name__)
    client = TestClient(app)
    scope = {'project_id': 'p', 'image_id': 'im'}
    path = '/api/agent/scribble-masks'
    def read(url):
        response = client.get(url)
        response.raise_for_status()
        return np.asarray(Image.open(BytesIO(response.content)))
    assert client.post(path, json={**scope, 'scribble_map_b64': ''}).status_code == 422
    assert client.post(path, json={**scope, 'scribble_map_b64': encode_gray_png_b64(photo[:20, :, 0])}).status_code == 422
    automatic = client.post(path, json=scope)
    automatic.raise_for_status()
    assert automatic.json()['counts']['fiber'] > 0
    labels = np.zeros(photo.shape[:2], np.uint8)
    labels[8:64, 31] = 128
    labels[8:64, 35] = 192
    labels[8:64, 16] = 255
    response = client.post(path, json={**scope, 'scribble_map_b64': encode_gray_png_b64(labels)})
    response.raise_for_status()
    mid = response.json()['mask_id']
    support = read(f'{path}/{mid}/layers/mascara')
    assert np.all(support[labels == 128]) and not support[labels >= 192].any()
    assert not support[79:].any()
    assert np.array_equal(read(f'{path}/{mid}/layers/labels'), labels)
    assert client.get(path, params={**scope, 'project_id':'q'}).json() == []
    assert client.get(path, params=scope).json()[0]['mask_id'] == mid
    modes = {}
    for source in ('agente', 'scribble', 'ambas'):
        response = client.post('/api/agent/runs', json={**scope, 'mask_source':source, 'scribble_mask_id':mid})
        response.raise_for_status()
        run = response.json()
        assert run['mask_source'] == source
        prefix = '/api/agent/runs/' + run['run_id'] + '/layers/'
        modes[source] = read(prefix + 'mascara')
        if source == 'ambas':
            assert np.array_equal(read(prefix + 'mascara_agente'), modes['agente'])
            assert np.array_equal(read(prefix + 'mascara_scribble'), support)
    assert np.array_equal(modes['scribble'], support)
    assert np.array_equal(modes['ambas'], support & modes['agente'])
    assert client.post('/api/agent/runs', json={**scope, 'mask_source':'ambas'}).status_code == 422
    assert client.post('/api/agent/runs', json={**scope, 'project_id':'q', 'mask_source':'scribble',
                                                'scribble_mask_id':mid}).status_code == 422

from io import BytesIO

import numpy as np
import cv2
import pytest
from fastapi.testclient import TestClient
from PIL import Image

from backend import agent_mode, library_store
from backend.main import app


@pytest.mark.parametrize('width,height,expected', [(1401, 803, [900, 516]), (803, 1401, [516, 900]), (107, 153, [107, 153])])
def test_agent_import_uses_scribble_resolution_for_photo_and_crops(tmp_path, monkeypatch, width, height, expected):
    monkeypatch.setattr(library_store, 'LIBRARY_DIR', tmp_path / 'library')
    photo = np.random.default_rng(3).integers(0, 256, (height, width, 3), dtype=np.uint8)
    encoded = BytesIO()
    Image.fromarray(photo).save(encoded, format='PNG')
    client = TestClient(app)
    session = client.post('/api/session/new', json={}).json()['payload']['session_id']
    response = client.post('/api/agent/images/import', data={'session_id': session},
                           files={'file': ('test.png', encoded.getvalue(), 'image/png')})
    response.raise_for_status()
    item = response.json()['payload']
    assert 'image_b64' not in item and item['view']['view_wh'] == expected
    assert item['view']['native_wh'] == expected
    assert item['view']['native_per_view_xy'] == [1, 1]
    overview = client.get(item['view']['overview_url'])
    overview.raise_for_status()
    raster = Image.open(BytesIO(overview.content))
    assert list(raster.size) == expected
    width, height = expected
    work_photo = cv2.resize(photo, (width, height), interpolation=cv2.INTER_AREA)
    np.testing.assert_array_equal(np.asarray(raster), work_photo)
    endpoint = item['view']['crop_url']
    response = client.get(endpoint, params=dict(x=width-13, y=height-9, w=13, h=9))
    response.raise_for_status()
    np.testing.assert_array_equal(np.asarray(Image.open(BytesIO(response.content))), work_photo[-9:, -13:])
    assert client.get(endpoint, params=dict(x=width-13, y=height-9, w=14, h=9)).status_code == 422
    reopened = client.post('/api/library/load', json=dict(session_id=session, image_id=item['image_id'], agent_view=True))
    assert reopened.json()['payload']['view'] == item['view']


def test_independent_project_copy_keeps_its_identity_when_reopened_or_reimported(tmp_path, monkeypatch):
    from backend import main
    from backend.runner import compute_image_id
    monkeypatch.setattr(library_store, 'LIBRARY_DIR', tmp_path / 'library')
    monkeypatch.setattr(main, '_project_for_upload', lambda pid: {'project_id': pid})
    client = TestClient(app)
    sid = client.post('/api/session/new').json()['payload']['session_id']
    photo = np.zeros((32, 32, 3), dtype=np.uint8)
    buf = BytesIO()
    Image.fromarray(photo).save(buf, format='PNG')

    def upload(project, independent=False):
        response = client.post('/api/agent/images/import', files={'file': ('same.png', buf.getvalue())},
                               data={'session_id': sid, 'project_id': project, 'independent_copy': independent})
        response.raise_for_status()
        return response.json()['payload']['image_id']

    original = upload('control')
    copy = upload('trial', True)
    assert copy != original and upload('trial') == copy and upload('control') == original
    assert compute_image_id(photo + 1, copy) != copy
    response = client.post('/api/library/load', json={'session_id': sid, 'image_id': copy})
    assert response.json()['payload']['image_id'] == copy
    for iid, project in [(original, 'control'), (copy, 'trial')]:
        rgb, meta = library_store.load_library_image(iid)
        np.testing.assert_array_equal(rgb, photo)
        assert meta['project_ids'] == [project]


def test_editor_zoom_reads_the_native_run_photo(tmp_path, monkeypatch):
    monkeypatch.setattr(agent_mode, 'ROOT', tmp_path)
    run_id = 'a' * 32
    folder = tmp_path / run_id
    folder.mkdir()
    (folder / 'resultado.json').write_text('{}')
    photo = np.random.default_rng(4).integers(0, 256, (600, 1600), dtype=np.uint8)
    Image.fromarray(photo).save(folder / 'foto.png')
    client = TestClient(app)
    endpoint = f'/api/agent/runs/{run_id}/layers/foto'
    preview = client.get(endpoint, params={'overview': 'true'})
    preview.raise_for_status()
    assert Image.open(BytesIO(preview.content)).size == (1024, 384)
    native = client.get(endpoint)
    native.raise_for_status()
    np.testing.assert_array_equal(np.asarray(Image.open(BytesIO(native.content))), photo)

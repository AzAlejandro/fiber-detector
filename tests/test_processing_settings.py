import cv2
import numpy as np
from fastapi.testclient import TestClient

from backend import processing_settings as config
from backend.agent_geometry import choose_zoned
from backend.diameter_research.v3.pipeline import run_circle_square_mask_diameter
from backend.main import app


def test_processing_settings_control_circle_measurements(tmp_path, monkeypatch):
    monkeypatch.setattr(config, 'SETTINGS_PATH', tmp_path / 'settings.json')
    client = TestClient(app)
    url = '/api/agent/processing-settings'
    defaults = client.get(url).json()
    assert defaults == dict(smooth=True, local_background=True, alignment=False, continuity=True,
                            prune_spurs=False, clahe=False, oriented=False, diameter_method='three_profiles',
                            zoned_sampling=True, zone_rows=2, zone_columns=4, redistribute_zones=True)
    optional = dict(alignment=True, prune_spurs=True, clahe=True, oriented=True)
    assert client.post(url, json=optional).json() == {**defaults, **optional}
    assert client.get(url).json() == {**defaults, **optional}
    assert client.post(url, json={'smooth': False}).json()['diameter_method'] == 'three_profiles'
    assert client.post(url, json={'diameter_method': 'otro'}).status_code == 422

    gray = np.full((81, 81), 180, np.uint8)
    gray[35:46, :] = 75
    mask = np.zeros_like(gray, dtype=np.float32)
    mask[37:44, :] = 1
    args = dict(image_rgb=cv2.cvtColor(gray, cv2.COLOR_GRAY2RGB), labels=None, prior_map=mask,
                points=[dict(x=40, y=40)], params={'circle_square_seed_radius_px': 11})
    def measure():
        result = run_circle_square_mask_diameter(**args)['results'][0]
        assert result['status'] == 'ok'
        return result
    improved = measure()
    assert improved['circle_diameter_method'] == 'three_profiles' and improved['three_profiles_confirmed']
    assert client.post(url, json={'diameter_method': 'legacy'}).json()['smooth'] is False
    previous = measure()
    assert previous['circle_diameter_method'] == 'legacy'
    assert improved['circle_radius_px'] == previous['circle_radius_px'] == 11
    assert improved['square_vertices_xy'] == previous['square_vertices_xy']
    assert improved['diameter_px'] > previous['diameter_px']
    assert np.isclose(np.linalg.norm(np.subtract(improved['right_edge_xy'], improved['left_edge_xy'])),
                      improved['diameter_px'])
    assert client.post(url, json={'diameter_method': 'three_profiles'}).status_code == 200
    args['image_rgb'][:] = 130
    fallback = measure()
    assert not fallback['three_profiles_confirmed']
    assert fallback['diameter_px'] == previous['diameter_px']


def test_saved_settings_gain_zones_and_reject_invalid_grid(tmp_path, monkeypatch):
    path = tmp_path / 'settings.json'
    path.write_text('{"smooth":false,"diameter_method":"legacy"}')
    monkeypatch.setattr(config, 'SETTINGS_PATH', path)
    client = TestClient(app)
    url = '/api/agent/processing-settings'
    original = client.get(url).json()
    assert original['zoned_sampling'] and original['zone_rows'] * original['zone_columns'] == 8
    for invalid in [0, 9, True, '4']:
        assert client.post(url, json={'zone_rows': invalid}).status_code == 422
    changed = client.post(url, json={'zoned_sampling': False, 'zone_columns': 3}).json()
    assert changed == {**original, 'zoned_sampling': False, 'zone_columns': 3} == client.get(url).json()


def test_zone_limits_respect_one_track_empty_zones_and_footer():
    mask = np.zeros((120, 180), dtype=bool)
    mask[20:31, 8:54] = True
    candidates = [(10, x, 25, 12) for x in (20, 30, 40)]
    for y in [12, 33, 54, 75]:
        mask[y-1:y+2, 72:107] = True
        candidates.append((9, 90, y, 6))
    mask[100:, :] = True
    candidates.append((50, 150, 110, 6))
    options = dict(coverage_mask=mask, field_height=100, rows=1, columns=3)
    for redistribute, placed in [(False, [1, 2, 0]), (True, [1, 3, 0])]:
        circles, zones = choose_zoned(mask, candidates, 4, 4, **options, redistribute=redistribute)
        assert [z['fiber_pixels'] for z in zones] == [506, 420, 0]
        assert [z['quota'] for z in zones] == [2, 2, 0]
        assert [z['selected'] for z in zones] == placed
        assert len(circles) == sum(placed)
    circles, zones = choose_zoned(mask, candidates, 4, 4, **{**options, 'coverage_mask': np.zeros_like(mask)})
    assert circles == [] and all(z['quota'] == z['selected'] == 0 for z in zones)

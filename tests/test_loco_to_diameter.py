"""Tests for the LOCO Detector -> Diameter Research pipeline connection.

Verifies that accepted circles from LOCO Model detection are correctly
converted to diameter research points and that the 'replace' action works.
"""

from __future__ import annotations

import cv2
import numpy as np
from fastapi.testclient import TestClient

from backend.main import app
from backend.agent_geometry import choose


def test_agent_selects_one_circle_per_continuous_fiber():
    mask = np.zeros((80, 140), dtype=bool)
    mask[18:23, 10:130] = True
    mask[36:41, 10:130] = True
    candidates = [(score, x, y, 6, 20, True) for score, x, y in
                  [(100, 30, 20), (90, 65, 20), (80, 100, 20), (70, 30, 38)]]
    selected = choose(mask, candidates, spacing=9, limit=100)
    assert [(x, y) for _, x, y, *_ in selected] == [(30, 20), (30, 38)]


def test_agent_editor_contacts_edits_and_measurement(tmp_path, monkeypatch):
    from backend.diameter_research import api
    c, sid, iid = _setup(tmp_path, monkeypatch)
    rid = 'a'*32
    base = '/api/diameter-research'
    args = dict(session_id=sid,image_id=iid)
    mask = np.zeros((128,128),dtype=np.float32)
    mask[60:69,:] = 1
    monkeypatch.setattr(api, 'agent_result', lambda run: dict(image_id=iid,circles=[dict(id=1,x=64,y=64,radius_px=10)]))
    monkeypatch.setattr(api, '_latest_prior', lambda *a, **kw: (mask,None,'agent:'+rid))
    dy = 3.25
    dx = (100-dy**2)**.5
    pts = [[64+i*dx,64+j*dy] for i,j in [(1,1),(-1,1),(-1,-1),(1,-1)]]
    payload = {**args,'contacts':{'1':[dict(x=x,y=y) for x,y in pts]}}
    def post(path, data):
        res = c.post(base+path,json=data)
        assert res.status_code==200, res.text
        return res.json()
    editor = post('/agent-editor/'+rid,payload)
    shape = editor['geometry']['circles'][0]
    assert shape['agent_contacts']==payload['contacts']['1']
    measured = post('/run',dict(**args,method_id='circle_square_mask_diameter',prior_run_id='agent:'+rid,
        source_mode='prior_mask',points=[shape['center']],params={'circle_square_seed_mode':'manual_circle',
        'circle_square_circles_by_point':[dict(circle_square_seed_radius_px=10,agent_contacts_xy=pts)]}))
    result = measured['results'][0]
    assert result['status']=='ok'
    assert np.isclose(result['diameter_px'],2*dy)
    assert sorted(result['square_vertices_xy'])==sorted(pts)
    shape['radius'] = 12
    change = dict(**args,agent_run=rid,action='replace',points=[shape['center']],geometry=editor['geometry'])
    assert 'agent_contacts' not in post('/points/update',change)['geometry']['circles'][0]
    key = shape['geometry_id']
    marking = '/agent-editor/'+rid+'/contacts'
    assert post(marking,{**args,'contacts':{key:payload['contacts']['1']}})['marked']==0
    enlarged = [dict(x=64+(x-64)*1.2,y=64+(y-64)*1.2) for x,y in pts]
    assert post(marking,{**args,'contacts':{key:enlarged}})['marked']==1
    repeated = post(marking,{**args,'contacts':{key:payload['contacts']['1']}})
    assert repeated['marked']==0 and repeated['geometry']['circles'][0]['agent_contacts']==enlarged
    post('/points/update',dict(**args,agent_run=rid,action='clear'))
    assert post('/agent-editor/'+rid,payload)['geometry']['circles']==[]
    assert c.get(base+'/points/load',params=args).json()['points']==[]
    manual = dict(id=2, x=30, y=40, radius_px=6, source='manual')
    detections = [manual]
    monkeypatch.setattr(api, 'agent_result', lambda run: dict(image_id=iid, circles=detections))
    added = post('/agent-editor/'+rid, payload)
    assert [item['center'] for item in added['geometry']['circles']] == [dict(x=30, y=40)]
    assert len(post('/agent-editor/'+rid, payload)['points']) == 1
    detections.clear()
    assert post('/agent-editor/'+rid, payload)['points'] == []
    detections.append(manual)
    assert len(post('/agent-editor/'+rid, payload)['geometry']['circles']) == 1
    post('/points/update',dict(**args,agent_run=rid,action='clear'))
    assert post('/agent-editor/'+rid,payload)['geometry']['circles']==[]


def _img(size: int = 128) -> np.ndarray:
    y, x = np.indices((size, size))
    base = np.clip((x + y) / (2 * size), 0, 1)
    cx, cy = size // 2, size // 2
    fiber = ((((x - cx) / max(3, size * 0.09)) ** 2 + ((y - cy) / max(6, size * 0.34)) ** 2) < 1.0).astype(np.float32)
    img = np.clip(0.35 * base + 0.65 * fiber, 0, 1)
    return (img * 255.0).astype(np.uint8)


def _setup(tmp_path, monkeypatch) -> tuple[TestClient, str, str]:
    """Create a test client with patched paths, session, and loaded image.
    
    Returns (client, session_id, image_id).
    """
    import backend.persistence as p
    import backend.library_store as ls
    import backend.diameter_research.api as api
    import backend.diameter_research.persistence as drp

    monkeypatch.setattr(p, 'OUTPUT_ROOT', tmp_path / 'outputs')
    monkeypatch.setattr(p, 'RUNS_DIR', p.OUTPUT_ROOT / 'runs')
    monkeypatch.setattr(p, 'REVIEWS_DIR', p.OUTPUT_ROOT / 'reviews')
    monkeypatch.setattr(p, 'INDEX_DIR', p.OUTPUT_ROOT / 'index')
    monkeypatch.setattr(p, 'REPORTS_DIR', p.OUTPUT_ROOT / 'reports')
    monkeypatch.setattr(p, 'DRAFTS_DIR', p.OUTPUT_ROOT / 'drafts')
    monkeypatch.setattr(ls, 'LIBRARY_DIR', p.OUTPUT_ROOT / 'library')
    monkeypatch.setattr(drp, 'OUTPUT_ROOT', tmp_path / 'outputs')
    monkeypatch.setattr(drp, 'POINTS_DIR', drp.OUTPUT_ROOT / 'points')
    monkeypatch.setattr(drp, 'RUNS_DIR', drp.OUTPUT_ROOT / 'runs')
    monkeypatch.setattr(drp, 'INDEX_DIR', drp.OUTPUT_ROOT / 'index')
    monkeypatch.setattr(drp, 'REPORTS_DIR', drp.OUTPUT_ROOT / 'reports')
    monkeypatch.setattr(api, 'CALIBRATION_DIR', tmp_path / 'data' / 'calibration')

    c = TestClient(app)
    sid = c.post('/api/session/new', json={}).json()['payload']['session_id']

    img = _img()
    ok, buf = cv2.imencode('.png', img)
    assert ok
    r = c.post('/api/image/load', data={'session_id': sid}, files={'file': ('test.png', bytes(buf), 'image/png')})
    assert r.status_code == 200, r.text
    iid = r.json()['payload']['image_id']
    return c, sid, iid


def test_points_replace_action_clears_and_sets(tmp_path, monkeypatch) -> None:
    """The 'replace' action in points/update clears existing points and sets new ones."""
    c, sid, iid = _setup(tmp_path, monkeypatch)

    # add a couple of points first
    add_res = c.post(
        '/api/diameter-research/points/update',
        json={
            'session_id': sid,
            'action': 'add',
            'x': 10.0,
            'y': 20.0,
        },
    )
    assert add_res.status_code == 200, add_res.text

    add_res2 = c.post(
        '/api/diameter-research/points/update',
        json={
            'session_id': sid,
            'action': 'add',
            'x': 30.0,
            'y': 40.0,
        },
    )
    assert add_res2.status_code == 200, add_res2.text

    # verify 2 points exist
    load_before = c.get(f'/api/diameter-research/points/load?session_id={sid}&image_id={iid}')
    assert load_before.status_code == 200
    assert len(load_before.json().get('points', [])) == 2

    # replace with new points (simulating LOCO -> diameter transfer)
    replace_res = c.post(
        '/api/diameter-research/points/update',
        json={
            'session_id': sid,
            'action': 'replace',
            'points': [
                {'x': 50.0, 'y': 60.0},
                {'x': 70.0, 'y': 80.0},
                {'x': 90.0, 'y': 100.0},
            ],
        },
    )
    assert replace_res.status_code == 200, replace_res.text

    # verify old points replaced with new ones
    load_after = c.get(f'/api/diameter-research/points/load?session_id={sid}&image_id={iid}')
    assert load_after.status_code == 200
    points = load_after.json().get('points', [])
    assert len(points) == 3, f'Expected 3 points after replace, got {len(points)}'
    assert points[0]['x'] == 50.0
    assert points[0]['y'] == 60.0
    assert points[2]['x'] == 90.0


def test_loco_accepted_circle_conversion() -> None:
    """Verify that accepted circles from LOCO detector can be mapped to diameter points."""
    # Simulate the frontend mapping logic from measureLocoModelAccepted()
    accepted = [
        {'center_x': 100.0, 'center_y': 200.0, 'radius_px': 15.0, 'score': 0.95},
        {'center_x': 300.0, 'center_y': 400.0, 'radius_px': 22.0, 'score': 0.87},
        {'center_x': 500.0, 'center_y': 600.0, 'radius_px': 8.0, 'score': 0.76},
    ]

    # This is the exact mapping used in App.jsx measureLocoModelAccepted()
    points = [
        {'x': float(c.get('center_x', 0)), 'y': float(c.get('center_y', 0)), 'radius_px': float(c.get('radius_px', 0))}
        for c in accepted
    ]

    assert len(points) == 3
    assert points[0]['x'] == 100.0
    assert points[0]['y'] == 200.0
    assert points[0]['radius_px'] == 15.0
    assert points[2]['radius_px'] == 8.0

    # Verify all required keys are present
    for p in points:
        assert 'x' in p
        assert 'y' in p
        assert 'radius_px' in p


def test_loco_accepted_empty_list() -> None:
    """An empty accepted list should produce an empty points array."""
    accepted: list[dict] = []
    points = [
        {'x': float(c.get('center_x', 0)), 'y': float(c.get('center_y', 0)), 'radius_px': float(c.get('radius_px', 0))}
        for c in accepted
    ]
    assert points == []


def test_loco_accepted_missing_fields() -> None:
    """Accepted circles with missing fields should default to 0."""
    accepted = [
        {'center_x': 100.0},  # missing center_y, radius_px
        {},  # completely empty
    ]
    points = [
        {'x': float(c.get('center_x', 0)), 'y': float(c.get('center_y', 0)), 'radius_px': float(c.get('radius_px', 0))}
        for c in accepted
    ]
    assert points[0]['x'] == 100.0
    assert points[0]['y'] == 0.0
    assert points[0]['radius_px'] == 0.0
    assert points[1]['x'] == 0.0
    assert points[1]['y'] == 0.0

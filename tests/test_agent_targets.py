import numpy as np
from fastapi.testclient import TestClient

from backend import agent_masks, agent_mode, agent_training, projects_store
from backend.main import app


def test_project_targets_follow_the_saved_image_and_skill(tmp_path, monkeypatch):
    for key, value in dict(PROJECTS_DIR=tmp_path, PROJECTS_PATH=tmp_path/'projects.json',
                           TAG_OVERRIDES_PATH=tmp_path/'tags.json').items():
        monkeypatch.setattr(projects_store, key, value)
    monkeypatch.setattr(agent_training, 'DB', tmp_path/'skills.sqlite3')
    photo = np.full((100, 120), 150, np.uint8)
    photo[:, 30:34] = 65
    photo[:, 77:81] = 105
    photo[84:] = 255
    for module in (agent_masks, agent_mode):
        monkeypatch.setattr(module, 'ROOT', tmp_path/module.__name__)
        monkeypatch.setattr(module, 'load_library_image', lambda _: (photo, {'image_name':'sample','project_ids':['p','q']}))

    c = TestClient(app)
    for name in ('p','q'):
        c.post('/api/projects/upsert', json={'name':name}).raise_for_status()
    settings = '/api/projects/p/agent-targets'
    targets = dict(painted_percent=10, percent_tolerance=0.1, circle_count=3, circle_tolerance=1)
    c.post(settings, json=targets).raise_for_status()
    assert c.post(settings, json={**targets, 'circle_count':201}).status_code == 422
    c.post('/api/projects/upsert', json={'project_id':'p','name':'Renombrado'}).raise_for_status()
    base = '/api/agent-training/p/scribbles'
    state = c.get(base+'/state').json()
    assert state['targets'] == targets
    assert c.get(base.replace('/p/','/q/')+'/state').json()['targets']['painted_percent'] is None
    text = 'Pinta {{porcentaje_pintado}} %.'
    c.post(base+'/skills', json={'expected':state['active']['id'],'body':text}).raise_for_status()
    skill = c.get(base+'/state').json()['active']
    assert skill['body'] == text and 'Pinta 10 %.' in skill['execution_body']
    scope = {'project_id':'p','image_id':'im'}
    mask = c.post('/api/agent/scribble-masks', json={**scope,'expected_targets':targets}).raise_for_status().json()
    run = c.post('/api/agent/runs', json={**scope,'mask_source':'ambas','scribble_mask_id':mask['mask_id']}).raise_for_status().json()
    assert run['parameters']['limit'] == 3
    c.post(settings, json={'painted_percent':75,'circle_count':90}).raise_for_status()
    assert c.post('/api/agent/scribble-masks',json={**scope,'expected_targets':targets}).status_code == 409
    review_url = '/api/agent/target-review'
    params = {**scope, 'run_id':run['run_id']}
    review = c.get(review_url, params=params).raise_for_status().json()
    coverage = review['scribbles']
    assert coverage['actual'] == mask['coverage_review']['actual']
    assert coverage['within'] and coverage['target'] == 10
    assert coverage['field_pixels'] == 120 * mask['field_height'] < photo.size
    assert review['circles']['target'] == 3
    assert review['circles']['actual'] == len(run['circles'])
    assert c.get(review_url,params={**params,'project_id':'q'}).status_code == 404
    added = c.post('/api/agent/runs/'+run['run_id']+'/circles',json={'x':30,'y':30,'radius_px':6}).raise_for_status().json()
    assert c.get(review_url,params=params).json()['circles']['actual'] == len(run['circles'])+1
    c.post(f"/api/agent/runs/{run['run_id']}/circles/{added['added_circle_id']}/remove").raise_for_status()
    assert c.get(review_url,params=params).json()['circles'] == review['circles']
    empty = c.post('/api/agent/runs', json={**scope, 'circles':[]}).raise_for_status().json()
    assert empty['circle_review'] == dict(actual=0, target=90, tolerance=2, difference=-90, within=False)
    freely = c.post('/api/agent/runs', json={**scope, 'project_id':'q', 'circles':[]}).raise_for_status().json()
    assert freely['circle_review']['within'] is None

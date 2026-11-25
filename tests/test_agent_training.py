import numpy as np
from fastapi.testclient import TestClient

from backend import agent_training as training
from backend.main import app


def test_rounds_versions_and_skill_copy(tmp_path, monkeypatch):
    monkeypatch.setattr(training, 'DB', tmp_path / 'training.db')
    monkeypatch.setattr(training, 'list_projects', lambda: {'projects':[{'project_id':p} for p in ('a','b')]})
    monkeypatch.setattr(training, 'load_library_image', lambda iid: (np.zeros((80,100,3),np.uint8),
        {'image_name':'field.tif','project_ids':['a','b']}))
    circle = {'id':1,'x':40,'y':40,'radius_px':6}
    monkeypatch.setattr(training.agent_mode,'list_runs',lambda *args:[{'run_id':'a'*32}])
    monkeypatch.setattr(training.agent_mode,'result',lambda rid:{'run_id':rid,'circles':[dict(circle),dict(circle,id=2,x=65)]})
    client=TestClient(app)
    a='/api/agent-training/a/'
    b='/api/agent-training/b/'
    def post(url, **payload):
        res=client.post(url,json=payload)
        res.raise_for_status()
        return res.json()

    def current(base):
        return client.get(base+'/state').json()['active']

    base=a+'circulos'
    v1=current(base)
    rnd=post(base+'/rounds',image_id='im',skill_id=v1['id'])
    url=base+'/rounds/'+str(rnd['id'])+'/review'
    post(url,mark='1',decision='sin_fibra',revision=0)
    assert client.post(url,json={'mark':'2','decision':'ok','revision':0}).status_code==409
    post(url,decision='bulk',revision=1)
    row=client.get(base+'/state').json()['rounds'][0]
    assert (row['reviewed'],row['errors'],row['bulk'])==(2,1,1)
    v2=post(base+'/skills',expected=v1['id'],body=v1['body'],round_id=rnd['id'],revision=2)
    assert 'sin_fibra' in v2['evidence']['counts']
    new=post(base+'/rounds',image_id='im',skill_id=v2['id'])
    assert [m['id'] for m in new['marks']]==['2']
    assert new['reviews']=={}
    assert client.get(b+'circulos/rounds/'+str(rnd['id'])).status_code==404
    copy=post(b+'circulos/skills',expected=current(b+'circulos')['id'],body='copy',copy_id=v2['id'])
    assert copy['parent']==v2['id'] and copy['body']==v2['body']
    copied=post(b+'circulos/rounds',image_id='im',skill_id=copy['id'])
    assert len(copied['marks'])==1
    post(b+'circulos/skills',expected=copy['id'],body='Local instructions')
    assert current(base)['body']==v2['body']
    assert '---\nname:' in client.get(f"/api/agent-training/skills/{copy['id']}/SKILL.md").text
    strokes=a+'scribbles'
    vs=current(strokes)
    mark={'id':'F1','ancho_px':1,'clase':'fibra','puntos':[[10,20],[35,20],[70,25]]}
    r=post(strokes+'/rounds',image_id='im',skill_id=vs['id'],trazos=[mark])
    uri=strokes+'/rounds/'+str(r['id'])
    split=post(uri+'/review',revision=0,mark='F1',decision='halo',start=20,end=80)
    assert len(split['marks'])==3 and split['reviews']=={'F1':'halo'}
    assert TestClient(app).get(uri).json()==split
    pattern = split['patterns'][0]
    assert (pattern['key'], pattern['partial'], pattern['ids']) == ('fibra/halo', 1, ['F1'])
    payload = dict(expected=vs['id'],round_id=r['id'],revision=1,body=vs['body'])
    assert client.post(strokes+'/skills',json={**payload,'rules':{'halo/fibra':'fuera de esta ronda'}}).status_code==422
    rule = 'Sigue el flanco hasta el extremo del tramo seleccionado.'
    s2=post(strokes+'/skills',**payload,rules={'fibra/halo':rule})
    assert s2['evidence']['patterns'][0]['rule']==rule and rule in s2['body']
    exported=client.get(f"/api/agent-training/skills/{s2['id']}/SKILL.md").text
    assert 'fibra → halo' in exported and rule in exported and '#F1' in exported
    assert s2['evidence']['counts']=={'halo':1}
    repeated=post(strokes+'/rounds',image_id='im',skill_id=s2['id'],from_round=r['id'])
    assert [m['clase'] for m in repeated['marks']]==['fibra','halo','fibra']
    assert repeated['reviews']=={}
    monkeypatch.setattr(training,'scribbles_from_circles',lambda data:[dict(mark)])
    revised=post(strokes+'/rounds',image_id='im',skill_id=s2['id'])
    assert [m['clase'] for m in revised['marks']]==['fibra','halo','fibra']
    assert client.post(strokes+'/skills',json={'expected':s2['id'],'copy_id':v2['id'],'body':'x'}).status_code==422


def test_crossing_skill_has_independent_versions_and_export(tmp_path, monkeypatch):
    monkeypatch.setattr(training, 'DB', tmp_path / 'training.db')
    monkeypatch.setattr(training, 'list_projects', lambda: {'projects': [{'project_id': 'a'}, {'project_id': 'b'}]})
    client = TestClient(app)
    base = '/api/agent-training'
    def active(project, kind):
        return client.get(f'{base}/{project}/{kind}/state').json()['active']

    first = active('a', 'cruces')
    circles = active('a', 'circulos')
    updated = client.post(f'{base}/a/cruces/skills', json={
        'expected': first['id'], 'body': first['body'] + '\nContrasta el arco revisado.'
    }).json()
    assert updated['version'] == 2 and updated['parent'] == first['id']
    copy = client.post(f'{base}/b/cruces/skills', json={
        'expected': active('b', 'cruces')['id'], 'body': 'copy', 'copy_id': updated['id']
    }).json()
    assert copy['parent'] == updated['id'] and copy['body'] == updated['body']
    assert active('a', 'circulos') == circles
    exported = client.get(f"{base}/skills/{copy['id']}/SKILL.md").text
    assert copy['body'] in exported and 'cruces/rounds' not in exported
    assert client.post(f'{base}/a/cruces/rounds', json={'image_id':'x', 'skill_id':first['id']}).status_code == 422


def test_review_patterns_separate_confusions_and_individual_controls():
    proposals = ['halo','fondo','halo','halo','halo','halo','halo','fibra']
    decisions = ['fibra','fibra','ok','bulk','dudoso',None,'ok','incorrecto']
    marks = [dict(id=str(i), clase=clase, puntos=[[i,0],[i,1]]) for i,clase in enumerate(proposals)]
    reviews = {m['id']:d for m,d in zip(marks,decisions) if d}
    patterns = {p['key']:p for p in training.review_patterns(marks,reviews)}
    a,b = patterns['halo/fibra'],patterns['fondo/fibra']
    assert a['rule']!=b['rule'] and a['individual']==3 and b['individual']==1
    assert a['comparison']=='2' and b['comparison'] is None
    assert patterns['halo/dudoso']['ids']==['4'] and patterns['fibra/incorrecto']['ids']==['7']

import json
from threading import Event, Thread
from time import monotonic, sleep

from backend.agent_worklist import follow, image_summary, refresh


def put(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding='utf-8')


def test_worklist_follows_detection_editor_and_analysis(tmp_path):
    root = tmp_path
    rid = 'a' * 32
    gid = f'agent_{rid}_1'
    folder = root / 'agent_runs' / rid
    manifest = dict(run_id=rid, project_id='uno', image_id='im', image_name='foto', circles=[
        dict(id=1, source='manual', x=25, y=30, radius_px=5), dict(id=2, x=50, y=50, radius_px=5)])
    put(folder / 'resultado.json', manifest)
    put(root/'library'/'im'/'meta.json', dict(image_id='im', image_name='foto', project_ids=['uno', 'dos']))
    put(root / 'agent_runs' / ('b' * 32) / 'resultado.json', {**manifest, 'run_id': 'b'*32, 'project_id': 'dos'})
    def work():
        return refresh(root)['uno']
    assert [c['geometry_id'] for c in work()['pendientes']] == [gid]
    marker = folder / '1.removed'
    marker.touch()
    assert not work()['pendientes'] and refresh(root)['dos']['pendientes']
    marker.unlink()
    dr = root / 'diameter_research'
    pts = [[22,26], [28,26], [22,34], [28,34]]
    circle = dict(center=dict(x=25,y=30),radius=5,geometry_id=gid,
                  agent_contacts=[dict(x=x,y=y) for x,y in pts])
    editor = dr / 'points' / f'agent_editor_{rid}.json'
    def edit(circles):
        put(editor, dict(detection_manual_ids=[1], geometry=dict(circles=circles)))
    edit([circle])
    assert work()['pendientes'][0]['accion'] == 'medir'
    assert image_summary('uno', 'foto', root)['pendientes'] == {'medir': ['1']}
    assert image_summary('dos', 'im', root)['pendientes'] == {'marcar_bordes': ['1', '2']}
    seed = dict(circle_square_geometry_id=gid, circle_square_seed_radius_px=5, agent_contacts_xy=pts)
    meta = dict(prior_run_id='agent:'+rid, params_effective=dict(circle_square_circles_by_point=[seed]))
    def measure(status):
        put(dr/'runs'/'m'/'meta.json', dict(run_id='m',meta=meta,results=[
            dict(original_xy=[25,30],status=status,point_index=0,reason='' if status=='ok' else 'cruces')]))
        put(dr/'index'/'im.json',dict(runs=[dict(run_id='m', method_id='circle_square_mask_diameter')]))
    measure('rejected')
    assert work()['revisar'][0]['motivo']=='cruces' and not work()['pendientes']
    measure('ok')
    assert work()['pendientes'][0]['accion']=='registrar'
    put(root/'diameter_analysis'/'measurements.json',dict(measurements=[dict(run_id='m',point_index=0,diameter_px=6)]))
    assert work()['registrados']==1 and not work()['pendientes']
    assert image_summary('uno', 'im', root)['estados'] == {'registrados': 1}
    edit([{**circle,'radius':7,'agent_contacts':[]}])
    assert work()['pendientes'][0]['accion']=='marcar_bordes'
    assert image_summary('uno', 'im', root)['estados'] == {'marcar_bordes': 1}
    edit([{**circle,'geometry_id':'circle_editor_only'}])
    assert [c['geometry_id'] for c in work()['pendientes']]==['circle_editor_only']
    edit([])
    assert not work()['pendientes']


def test_live_worklist_updates_file_on_disk(tmp_path):
    root = tmp_path.resolve()
    path = root/'agent_runs'/'r'/'resultado.json'
    put(path, dict(run_id='r', image_id='image',project_id='live',circles=[
        dict(id=1,x=10,y=12,radius_px=3,source='manual')]))
    out = root/'agent_tasks'/'circulos-live.json'
    stop = Event()
    worker = Thread(target=follow, args=(stop,root), daemon=True)
    worker.start()
    def wait_for(count):
        until = monotonic()+8
        while monotonic()<until:
            if out.exists() and len(json.loads(out.read_bytes())['pendientes'])==count:
                return
            sleep(.05)
        raise AssertionError(f'Expected {count} pending circles on disk')
    try:
        wait_for(1)
        (path.parent/'1.removed').touch()
        wait_for(0)
    finally:
        stop.set()
        worker.join(4)
    assert not worker.is_alive()

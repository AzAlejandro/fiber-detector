"""Compact, derived worklist for manually drawn circles in agent mode."""
import argparse
import hashlib
import json
import logging
import re
from collections import Counter, defaultdict
from functools import lru_cache
from pathlib import Path
from tempfile import NamedTemporaryFile
from threading import Event

from watchfiles import watch

from .paths import OUTPUT_ROOT as ROOT


def read(path):
    return json.loads(path.read_bytes())


def stamp(path):
    stat = path.stat()
    return stat.st_mtime_ns, stat.st_size


@lru_cache(maxsize=256)
def small_file(path, version):
    return read(path)


def optional(path):
    return small_file(path, stamp(path)) if path.is_file() else {}


def geometry(x, y, radius):
    return float(x), float(y), float(radius)


def contact_key(points):
    return tuple(sorted((round(x, 4), round(y, 4)) for x, y in points))


@lru_cache(maxsize=1)
def receipts(path, version):
    return {(r['run_id'], r['point_index']) for r in read(path).get('measurements', [])
            if r.get('diameter_px') is not None}


@lru_cache(maxsize=256)
def attempts(path, version):
    # Cache only measurement inputs and verdicts, dropping diagnostic arrays.
    data = read(path)
    meta = data['meta']
    source = meta.get('prior_run_id') or meta.get('requested_prior_run_id') or ''
    if not source.startswith('agent:'):
        return []
    params = meta.get('params_effective', {})
    seeds = params.get('circle_square_circles_by_point') or []
    rows = []
    for i, result in enumerate(data['results']):
        seed = seeds[i] if i < len(seeds) else params
        gid = seed.get('circle_square_geometry_id') or result.get('interactive_geometry_id')
        x, y = (result.get('original_xy') or [result.get('x'), result.get('y')])
        x = seed.get('circle_square_center_x', x)
        y = seed.get('circle_square_center_y', y)
        radius = seed.get('circle_square_seed_radius_px', result.get('circle_radius_px'))
        if not gid or None in (x, y, radius):
            continue
        rows.append((source[6:], gid, geometry(x, y, radius), contact_key(seed.get('agent_contacts_xy') or []),
                     data['run_id'], result.get('point_index', i), result['status'], result.get('reason', '')))
    return rows


def drawn_circles(root, run, folder, include_proposed=False):
    rid = run['run_id']
    editor = optional(root / 'diameter_research' / 'points' / f'agent_editor_{rid}.json')
    synced = set(editor.get('detection_manual_ids', []))
    shapes = {c['geometry_id']: c for c in editor.get('geometry', {}).get('circles', [])}
    for c in run.get('circles', []):
        gid = f"agent_{rid}_{c['id']}"
        edited = shapes.pop(gid, None)
        if (folder / f"{c['id']}.removed").exists():
            continue
        original = geometry(c['x'], c['y'], c['radius_px'])
        if edited:
            if edited.get('type', 'valid') not in ('', 'valid'):
                continue
            center = edited['center']
            current = geometry(center['x'], center['y'], edited['radius'])
            if original == current and c.get('source') != 'manual' and not include_proposed:
                continue
        elif c['id'] in synced or (c.get('source') != 'manual' and (editor or not include_proposed)):
            continue
        else:
            current = original
        points = (edited or {}).get('agent_contacts') or []
        review = (run.get('edge_review') or {}).get('circles', {}).get(str(c['id']), {})
        if not points and review:
            g = review['geometry']
            if current == geometry(g['x'], g['y'], g['radius_px']):
                points = review.get('points', [])
        yield gid, current, points
    for gid, c in shapes.items():
        if gid and c.get('type', 'valid') in ('', 'valid'):
            yield gid, geometry(c['center']['x'], c['center']['y'], c['radius']), c.get('agent_contacts') or []


def project_filename(project):
    if re.fullmatch('[a-z0-9_-]{1,100}', project):
        return 'circulos-' + project + '.json'
    return 'circulos~' + hashlib.sha256(project.encode()).hexdigest() + '.json'


def calibration_dir(root):
    return ROOT.parents[1] / 'data' / 'calibration' if root == ROOT else root / 'calibration'


def measurement_history(dr, iid, rid):
    history = defaultdict(list)
    for m in optional(dr / 'index' / (iid + '.json')).get('runs', []):
        if m.get('method_id') == 'circle_square_mask_diameter':
            path = dr / 'runs' / m['run_id'] / 'meta.json'
            if path.is_file():
                for source, gid, shape, contacts, *result in attempts(path, stamp(path)):
                    if source == rid:
                        history[gid, shape].append((contacts, result))
    return history


def circle_status(history, saved, gid, shape, points):
    key = contact_key([(p['x'], p['y']) for p in points])
    matches = [r for contacts, r in history[gid, shape] if contacts == key]
    if any(status == 'ok' and (m, idx) in saved for m, idx, status, _ in matches):
        return 'registrados', None
    if matches:
        return ('registrar' if matches[-1][2] == 'ok' else 'revisar'), matches[-1]
    return ('medir' if len(points) == 4 else 'marcar_bordes'), None


def image_summary(project, image, root=ROOT):
    """Report the latest agent run for an exact library ID or name, without writing any data."""
    images = []
    for path in (root / 'library').glob('*/meta.json'):
        meta = read(path)
        if project in meta.get('project_ids', []) and image in (meta.get('image_id'), meta.get('image_name')):
            images.append(meta)
    if len(images) != 1:
        raise ValueError(f'{len(images)} imágenes coinciden en {project}. Usa el ID o el nombre exacto de biblioteca.')
    meta = images[0]
    iid = meta['image_id']
    cal = optional(calibration_dir(root) / (iid + '.json'))
    draft = optional(root / 'drafts' / iid / 'modelo' / 'meta.json')
    result = dict(proyecto=project, imagen=meta['image_name'], image_id=iid, tamano_hw=meta.get('shape_hw'),
                  escala=({'valor_por_px': cal['unit_per_px'], 'unidad': cal['unit']}
                          if cal.get('unit_per_px', 0) > 0 else None),
                  pixeles_scribble={k: draft[k] for k in ('n_fg', 'n_halo', 'n_bg') if k in draft})
    runs = (read(path) for path in (root / 'agent_runs').glob('*/resultado.json'))
    run = max((r for r in runs if r.get('project_id') == project and r.get('image_id') == iid),
              key=lambda r: (r.get('created_at', ''), r['run_id']), default=None)
    if run is None:
        result['run_id'] = None
        return result
    rid = run['run_id']
    history = measurement_history(root / 'diameter_research', iid, rid)
    ledger = root / 'diameter_analysis' / 'measurements.json'
    saved = receipts(ledger, stamp(ledger)) if ledger.is_file() else set()
    counts = Counter()
    pending = defaultdict(list)
    for gid, shape, points in drawn_circles(root, run, root / 'agent_runs' / rid, include_proposed=True):
        action, _ = circle_status(history, saved, gid, shape, points)
        counts[action] += 1
        if action != 'registrados':
            pending[action].append(gid.removeprefix(f'agent_{rid}_'))
    result.update(run_id=rid, mascara=run.get('mask_source'), scribble_mask_id=run.get('scribble_mask_id'),
                  circulos=sum(counts.values()), estados=dict(counts), pendientes=dict(pending))
    return result


def refresh(root=ROOT):
    directory = root / 'agent_tasks'
    directory.mkdir(parents=True, exist_ok=True)
    ledger = root / 'diameter_analysis' / 'measurements.json'
    saved = receipts(ledger, stamp(ledger)) if ledger.is_file() else set()
    projects = {}
    dr = root / 'diameter_research'
    for manifest in sorted((root / 'agent_runs').glob('*/resultado.json')):
        run = optional(manifest)
        project = run.get('project_id')
        if not project:
            continue
        work = projects.setdefault(project, dict(proyecto=project, registrados=0, pendientes=[], revisar=[]))
        iid = run['image_id']
        scales = work.setdefault('escalas', {})
        calibration = optional(calibration_dir(root) / (iid + '.json'))
        if calibration.get('unit_per_px', 0) > 0:
            scales[iid] = dict(imagen=run.get('image_name', iid), valor_por_px=calibration['unit_per_px'],
                               unidad=calibration.get('unit', 'nm'))
        circles = list(drawn_circles(root, run, manifest.parent))
        if not circles:
            continue
        iid, rid = run['image_id'], run['run_id']
        history = measurement_history(dr, iid, rid)
        for gid, shape, points in circles:
            contact_xy = [[p['x'], p['y']] for p in points]
            action, attempt = circle_status(history, saved, gid, shape, points)
            if action == 'registrados':
                work['registrados'] += 1
                continue
            item = dict(imagen=run.get('image_name', iid), image_id=iid, run_id=rid, geometry_id=gid,
                        x=shape[0], y=shape[1], radius_px=shape[2], accion=action)
            if attempt:
                m, _, _, reason = attempt
                item['medicion_run_id'] = m
                if reason:
                    item['motivo'] = reason
            if contact_xy:
                item['bordes_xy'] = contact_xy
            work['revisar' if item['accion'] == 'revisar' else 'pendientes'].append(item)
    for old in directory.glob('circulos*.json'):
        project = optional(old)['proyecto']
        if project not in projects and old.name == project_filename(project):
            projects[project] = dict(proyecto=project, registrados=0, pendientes=[], revisar=[])
    for project, work in projects.items():
        path = directory / project_filename(project)
        payload = json.dumps(work, ensure_ascii=False, separators=(',', ':')).encode()
        if path.exists() and path.read_bytes() == payload:
            continue
        with NamedTemporaryFile(dir=directory, delete=False) as f:
            tmp = Path(f.name)
            f.write(payload)
        try:
            tmp.replace(path)
        finally:
            tmp.unlink(missing_ok=True)
    return projects


def follow(stop, root=ROOT):
    dirs = [root / d for d in ('agent_runs', 'diameter_research/points', 'diameter_research/index', 'diameter_analysis')]
    dirs.append(calibration_dir(root))
    for d in dirs:
        d.mkdir(parents=True, exist_ok=True)
    def relevant(change, path):
        p = Path(path)
        return (p.name in ('resultado.json', 'measurements.json') or p.suffix == '.removed'
                or p.name.startswith('agent_editor_') or (p.parent in (dirs[2], dirs[4]) and p.suffix == '.json'))
    dirty = True
    failed = False
    for changes in watch(*dirs, stop_event=stop, watch_filter=relevant, debounce=400,
                         rust_timeout=1000, yield_on_timeout=True):
        if dirty or changes:
            try:
                refresh(root)
                dirty = False
                failed = False
            except (OSError, ValueError, KeyError):
                if not failed:
                    logging.getLogger(__name__).exception('No se pudo actualizar la lista de círculos')
                dirty = True
                failed = True


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--watch', action='store_true')
    parser.add_argument('--imagen', nargs=2, metavar=('PROYECTO', 'ID_O_NOMBRE'))
    args = parser.parse_args()
    if args.imagen:
        try:
            print(json.dumps(image_summary(*args.imagen), ensure_ascii=False, separators=(',', ':')))
        except ValueError as exc:
            parser.error(str(exc))
    elif args.watch:
        follow(Event())
    else:
        for project, work in refresh().items():
            print(project, len(work['pendientes']), 'pendientes,', len(work['revisar']), 'para revisar')

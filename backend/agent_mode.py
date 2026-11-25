"""Reproducible fiber circle proposals for LOCO library images."""
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Lock
from typing import Literal
from uuid import uuid4

import cv2
import numpy as np
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from PIL import Image
from pydantic import BaseModel, Field
from skimage.morphology import skeletonize

from .agent_geometry import choose, count_crossings, orientation_fields, proposals
from .agent_masks import field_height, load_support
from .agent_views import overview_response
from .agent_targets import AgentTargets, comparison, project_targets
from .image_codec import to_gray_u8
from .library_store import load_library_image
from .persistence import OUTPUT_ROOT

router = APIRouter(prefix='/api/agent', tags=['Modo agente'])
ROOT = OUTPUT_ROOT / 'agent_runs'
LAYERS = ('foto', 'suavizada', 'fondo', 'contraste', 'mascara', 'eje')
_circle_add_lock = Lock()


class Circle(BaseModel):
    x: float = Field(ge=0, allow_inf_nan=False)
    y: float = Field(ge=0, allow_inf_nan=False)
    radius_px: float = Field(ge=1, allow_inf_nan=False)


class AgentRequest(BaseModel):
    expected_targets: AgentTargets | None = None
    image_id: str = Field(pattern=r'^[a-zA-Z0-9_-]+$')
    project_id: str = ''
    limit: int = Field(100, ge=1, le=200)
    background_sigma: float = Field(10, ge=2, le=40)
    threshold: float = Field(5, ge=1, le=100)
    mask_source: Literal['agente', 'scribble', 'ambas'] = 'agente'
    scribble_mask_id: str | None = None
    circles: list[Circle] | None = Field(None, max_length=200, description='Opcional. Círculos del agente en píxeles de la foto de biblioteca.')


def manifest_path(run_id: str) -> Path:
    if not re.fullmatch(r'[a-f0-9]{32}', run_id):
        raise HTTPException(404, 'Ejecución desconocida.')
    path = ROOT / run_id / 'resultado.json'
    if not path.is_file():
        raise HTTPException(404, 'Ejecución desconocida.')
    return path


@router.get('/runs')
def list_runs(image_id: str, project_id: str | None = None, include_legacy: bool = False):
    items = []
    for path in ROOT.glob('*/resultado.json'):
        if path.parent.name.startswith('.'):
            continue
        data = json.loads(path.read_text(encoding='utf8'))
        scope_matches = project_id is None or data.get('project_id', '') == project_id
        if data['image_id'] == image_id and (scope_matches or (include_legacy and 'project_id' not in data)):
            items.append({k: data[k] for k in ('run_id', 'created_at')})
    return sorted(items, key=lambda item: item['created_at'], reverse=True)


@router.get('/runs/{run_id}')
def result(run_id: str):
    path = manifest_path(run_id)
    data = json.loads(path.read_text(encoding='utf8'))
    removed = {marker.stem for marker in path.parent.glob('*.removed')}
    data['circles'] = [circle for circle in data['circles'] if str(circle['id']) not in removed]
    if 'targets' in data:
        targets = AgentTargets(**data['targets'])
        data['circle_review'] = comparison(len(data['circles']), targets.circle_count, targets.circle_tolerance)
    return data


@router.post('/runs/{run_id}/circles/{circle_id}/remove')
def remove_circle(run_id: str, circle_id: int):
    return set_circle_removed(run_id, circle_id, True)


@router.post('/runs/{run_id}/circles/{circle_id}/restore')
def restore_circle(run_id: str, circle_id: int):
    return set_circle_removed(run_id, circle_id, False)


@router.post('/runs/{run_id}/circles', status_code=201)
def add_manual_circle(run_id: str, circle: Circle):
    path = manifest_path(run_id)
    with _circle_add_lock:
        data = json.loads(path.read_text(encoding='utf8'))
        x, y, r = circle.x, circle.y, circle.radius_px
        bottom = data['parameters']['field_height']
        if min(x, y, data['width'] - 1 - x, bottom - 1 - y) < r:
            raise HTTPException(422, 'El círculo debe quedar dentro del campo de la imagen.')
        with Image.open(path.with_name('mascara.png')) as mask:
            crossings = count_crossings(np.asarray(mask), x, y, r)
        circle_id = max((c['id'] for c in data['circles']), default=0) + 1
        data['circles'].append(dict(**circle.model_dump(), id=circle_id, source='manual', mask_crossings=crossings))
        pending = path.with_suffix('.tmp')
        try:
            pending.write_text(json.dumps(data, ensure_ascii=False), encoding='utf8')
            pending.replace(path)
        finally:
            pending.unlink(missing_ok=True)
        return {**result(run_id), 'added_circle_id': circle_id}


def set_circle_removed(run_id: str, circle_id: int, removed: bool):
    path = manifest_path(run_id)
    circles = json.loads(path.read_text(encoding='utf8'))['circles']
    if not any(circle['id'] == circle_id for circle in circles):
        raise HTTPException(404, 'Círculo desconocido.')
    # Separate markers preserve concurrent removals and keep circle IDs stable.
    marker = path.with_name(f'{circle_id}.removed')
    if removed:
        marker.touch()
    else:
        marker.unlink(missing_ok=True)
    return result(run_id)


@router.get('/runs/{run_id}/layers/{layer}')
def layer_image(run_id: str, layer: str, overview: bool = False):
    if layer not in (*LAYERS, 'mascara_agente', 'mascara_scribble'):
        raise HTTPException(404, 'Capa desconocida.')
    path = manifest_path(run_id).with_name(layer + '.png')
    if not path.is_file():
        raise HTTPException(404, 'Esta ejecución no tiene esa capa.')
    if overview and layer == 'foto':
        return overview_response(path)
    return FileResponse(path, media_type='image/png')


@router.post('/runs', status_code=201)
def run_agent(req: AgentRequest):
    try:
        rgb, meta = load_library_image(req.image_id)
    except FileNotFoundError as exc:
        raise HTTPException(404, 'Imagen ausente de la biblioteca.') from exc
    if req.project_id and req.project_id not in meta.get('project_ids', []):
        raise HTTPException(422, 'La imagen no pertenece al proyecto.')
    photo = to_gray_u8(rgb)
    targets = project_targets(req.project_id, req.expected_targets)
    limit = req.limit if 'limit' in req.model_fields_set else targets.circle_count or req.limit
    height, width = photo.shape
    if min(height, width) < 12:
        raise HTTPException(422, 'Imagen demasiado pequeña para detectar fibras.')
    smooth = cv2.GaussianBlur(photo.astype(np.float32), (0, 0), .82)
    background = cv2.GaussianBlur(smooth, (0, 0), req.background_sigma)
    contrast = background - smooth
    bottom = field_height(photo)
    agent_mask = contrast >= req.threshold
    agent_mask[bottom:] = False
    mask = agent_mask
    inputs = {}
    method = 'contraste_local_v2' if req.circles is None else 'contraste_local_v1'
    if req.mask_source != 'agente':
        if not req.scribble_mask_id:
            raise HTTPException(422, 'Selecciona una máscara de scribble guardada.')
        scribble_mask = load_support(req.scribble_mask_id, req.image_id, req.project_id, photo)
        inputs['mascara_scribble'] = scribble_mask * 255
        if req.mask_source == 'ambas':
            inputs['mascara_agente'] = agent_mask * 255
            mask = agent_mask & scribble_mask
            method = 'interseccion_scribble_contraste'
        else:
            mask = scribble_mask
            method = 'mascara_scribble'
    if req.circles is None:
        candidates = proposals(mask, smooth, bottom, 3.6, orientation_fields(photo))
        selected = choose(mask, candidates, 9, limit)
        circles = [dict(x=x, y=y, radius_px=r, score=score, contrast=strength, stable=stable)
                   for score, x, y, r, strength, stable in selected]
    else:
        circles = [item.model_dump() for item in req.circles]
    for index, circle in enumerate(circles, 1):
        x, y, radius = circle['x'], circle['y'], circle['radius_px']
        if x-radius < 0 or y-radius < 0 or x+radius > width-1 or y+radius > bottom-1:
            raise HTTPException(422, f'Círculo {index} fuera del campo.')
        crossings = count_crossings(mask, x, y, radius)
        if crossings != 4:
            raise HTTPException(422, f'Círculo {index} con {crossings} cruces en la máscara.')
        circle.update(id=index, mask_crossings=crossings)
    run_id = uuid4().hex
    data = dict(run_id=run_id, image_id=req.image_id, project_id=req.project_id, image_name=meta['image_name'],
                created_at=datetime.now(timezone.utc).isoformat(), width=width, height=height,
                source='biblioteca LOCO, gris de 8 bits', photo_sha256=hashlib.sha256(photo.tobytes()).hexdigest(),
                method=method,
                mask_source=req.mask_source, scribble_mask_id=req.scribble_mask_id if inputs else None,
                parameters=dict(smooth_sigma=.82, background_sigma=req.background_sigma,
                threshold=req.threshold, field_height=bottom, limit=limit), layers=(*LAYERS, *inputs),
                targets=targets.model_dump(), circle_review=comparison(len(circles), targets.circle_count, targets.circle_tolerance),
                circle_source='automática' if req.circles is None else 'agente', circles=circles)
    arrays = dict(zip(LAYERS, (photo, smooth, background, 128 + 5 * contrast, mask * 255, skeletonize(mask) * 255)))
    arrays.update(inputs)
    ROOT.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(dir=ROOT, prefix='.agent-') as temp:
        output = Path(temp) / run_id
        output.mkdir()
        for name, pixels in arrays.items():
            Image.fromarray(np.uint8(np.clip(np.rint(pixels), 0, 255))).save(output / (name + '.png'))
        (output / 'resultado.json').write_text(json.dumps(data, ensure_ascii=False), encoding='utf8')
        output.rename(ROOT / run_id)
    return data

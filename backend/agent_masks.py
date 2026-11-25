"""Versioned Scribble masks used as input to agent circle detection."""
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4

import cv2
import numpy as np
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from PIL import Image
from pydantic import BaseModel, Field

from .agent_geometry import fiber_segments
from .agent_targets import AgentTargets, project_targets, comparison
from .image_codec import to_gray_u8, to_uint8_rgb
from .library_store import load_library_image
from .persistence import OUTPUT_ROOT
from .plugins.base import RunContext
from .plugins.experiments import ExtraTreesPixelExperiment
from .scribble import decode_scribble_b64, labels_to_visual, scribble_label_counts

router = APIRouter(prefix='/api/agent/scribble-masks', tags=['Modo agente'])
ROOT = OUTPUT_ROOT / 'agent_scribble_masks'


def field_height(photo):
    h = photo.shape[0]
    if h < 12:
        return h
    bright = np.mean(photo > 243, axis=1) > .72
    runs = np.convolve(bright, np.ones(12), mode='valid')
    footer = np.flatnonzero((runs == 12) & (np.arange(len(runs)) > h * .77))
    return max(0, int(footer[0]) - 3) if len(footer) else h


def propose_labels(gray, painted_percent=None):
    """Sample continuous dark ridges, bright outer flanks, and quiet background."""
    smooth = cv2.GaussianBlur(gray.astype(np.float32), (0, 0), 1)
    contrast = cv2.GaussianBlur(smooth, (0, 0), 10) - smooth
    fiber = contrast >= 5
    distance = cv2.distanceTransform((~fiber).astype('uint8'), cv2.DIST_L2, 5)
    fiber_axis = fiber_segments(contrast >= 8) > 0
    flank = (distance >= 1) & (distance <= 3.2) & (contrast < -5)
    flank_axis = fiber_segments(flank) > 0
    background = (distance >= 6) & (np.abs(contrast) < 4)
    labels = np.zeros(gray.shape, dtype=np.uint8)
    tile_size = 64
    if painted_percent is not None:
        # A full tile seeds at most 18 + 18 + 11 pixels before any expansion.
        fraction = max(painted_percent / 100, 1 / gray.size)
        tile_size = max(tile_size, int(np.ceil(np.sqrt(47 / fraction))))
    # Keep one continuous sample per class and tile. Short fragments are ambiguous.
    for y in range(0, gray.shape[0], tile_size):
        for x in range(0, gray.shape[1], tile_size):
            tile = np.s_[y:y+tile_size, x:x+tile_size]
            for value, axis in ((1, fiber_axis), (2, flank_axis)):
                contours, _ = cv2.findContours(axis[tile].astype('uint8'), cv2.RETR_LIST, cv2.CHAIN_APPROX_NONE)
                if not contours:
                    continue
                path = max(contours, key=len)
                points = path[:min(18, len(path)//2), 0]
                if len(points) >= 7 and np.linalg.norm(points[-1] - points[0]) >= 5:
                    labels[y+points[:, 1], x+points[:, 0]] = value
            quiet = cv2.erode(background[tile].astype('uint8'), np.ones((3, 11), np.uint8),
                              borderType=cv2.BORDER_CONSTANT, borderValue=0)
            py, px = np.nonzero(quiet)
            if len(px):
                center = (tile_size-1)//2
                k = int(np.argmin((px-center)**2 + (py-center)**2))
                labels[y+py[k], x+px[k]-5:x+px[k]+6] = 3
    if painted_percent is not None:
        # Grow each seed only through connected pixels supported by the same class.
        remaining = round(labels.size * painted_percent / 100) - np.count_nonzero(labels)
        kernel = cv2.getStructuringElement(cv2.MORPH_CROSS, (3, 3))
        while remaining > 0:
            additions = np.zeros_like(labels)
            for value, support in enumerate((fiber, flank, background), 1):
                adjacent = cv2.dilate((labels == value).astype('uint8'), kernel) > 0
                additions[(labels == 0) & support & adjacent] = value
            indices = np.flatnonzero(additions)[:remaining]
            if not indices.size:
                break
            labels.flat[indices] = additions.flat[indices]
            remaining -= indices.size
    return labels


class MaskRequest(BaseModel):
    expected_targets: AgentTargets | None = None
    image_id: str = Field(pattern=r'^[a-zA-Z0-9_-]+$')
    project_id: str = Field(min_length=1)
    scribble_map_b64: str | None = None
    source: str = Field(default='Editor Scribble', max_length=120)


def get_manifest(mask_id):
    if not re.fullmatch(r'[a-f0-9]{32}', mask_id):
        raise HTTPException(404, 'Máscara de scribble desconocida.')
    file = ROOT / mask_id / 'mask.json'
    if not file.is_file():
        raise HTTPException(404, 'Máscara de scribble desconocida.')
    return json.loads(file.read_text(encoding='utf8'))


def load_support(mask_id, image_id, project_id, photo):
    meta = get_manifest(mask_id)
    if (meta['image_id'], meta['project_id'], meta['photo_sha256']) != (
            image_id, project_id, hashlib.sha256(photo.tobytes()).hexdigest()):
        raise HTTPException(422, 'La máscara no corresponde al proyecto y la foto seleccionados.')
    with Image.open(ROOT / mask_id / 'mascara.png') as raster:
        return np.asarray(raster) > 0


@router.get('')
def list_masks(image_id: str, project_id: str):
    masks = []
    for path in ROOT.glob('*/mask.json'):
        meta = json.loads(path.read_text(encoding='utf8'))
        if meta['project_id'] == project_id and meta['image_id'] == image_id:
            masks.append(meta)
    return sorted(masks, key=lambda m: m['created_at'], reverse=True)


@router.get('/{mask_id}/layers/{layer}')
def layer(mask_id: str, layer: str):
    get_manifest(mask_id)
    if layer not in ('mascara', 'scribble', 'labels'):
        raise HTTPException(404, 'Capa desconocida.')
    return FileResponse(ROOT / mask_id / (layer + '.png'), media_type='image/png')


@router.post('', status_code=201)
def create_mask(req: MaskRequest):
    try:
        rgb, image_meta = load_library_image(req.image_id)
    except FileNotFoundError as exc:
        raise HTTPException(404, 'Imagen ausente de la biblioteca.') from exc
    if req.project_id not in image_meta.get('project_ids', []):
        raise HTTPException(422, 'La imagen no pertenece al proyecto.')
    rgb = to_uint8_rgb(rgb)
    photo = to_gray_u8(rgb)
    bottom = field_height(photo)
    targets = project_targets(req.project_id, req.expected_targets)
    if req.scribble_map_b64 is None:
        labels = np.zeros(photo.shape, dtype=np.uint8)
        labels[:bottom] = propose_labels(photo[:bottom], targets.painted_percent)
        source = 'Propuesta automática por contraste'
    else:
        try:
            labels = decode_scribble_b64(req.scribble_map_b64)
        except (OSError, ValueError) as exc:
            raise HTTPException(422, 'No se pudo leer el mapa de scribbles.') from exc
        if labels.shape != photo.shape:
            raise HTTPException(422, 'El scribble debe tener las dimensiones de la foto.')
        source = req.source
    labels[bottom:] = 0
    counts = scribble_label_counts(labels)
    if not counts['fiber'] or not counts['background']:
        raise HTTPException(422, 'Se necesitan trazos de fibra y de fondo dentro del campo. Puedes añadirlos con el editor.')
    experiment = ExtraTreesPixelExperiment()
    params = experiment.info.default_params
    output = experiment.run(RunContext(rgb[:bottom], photo[:bottom]/255., labels[:bottom], params))
    mask = np.zeros_like(labels)
    mask[:bottom] = (output.mask > 0) * 255
    mask[labels == 1] = 255
    mask[labels >= 2] = 0
    overlay = rgb.copy()
    for value, color in enumerate(((0, 229, 255), (255, 132, 0), (136, 75, 220)), 1):
        overlay[labels == value] = color
    mask_id = uuid4().hex
    meta = dict(mask_id=mask_id, image_id=req.image_id, project_id=req.project_id,
                created_at=datetime.now(timezone.utc).isoformat(), source=source, counts=counts,
                method=experiment.info.experiment_id, parameters=params, field_height=bottom,
                photo_sha256=hashlib.sha256(photo.tobytes()).hexdigest(), targets=targets.model_dump(),
                coverage_review=comparison(100 * int(np.count_nonzero(labels[:bottom])) / (photo.shape[1] * bottom),
                                           targets.painted_percent, targets.percent_tolerance))
    ROOT.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(dir=ROOT) as temp:
        folder = Path(temp) / mask_id
        folder.mkdir()
        for name, raster in [('labels', labels_to_visual(labels)), ('scribble', overlay), ('mascara', mask)]:
            Image.fromarray(raster).save(folder / (name + '.png'))
        (folder / 'mask.json').write_text(json.dumps(meta, ensure_ascii=False), encoding='utf8')
        folder.rename(ROOT / mask_id)
    return meta

"""Reduced overview and native pixel crops for LOCO's visual agent."""
from io import BytesIO
from pathlib import Path
from tempfile import NamedTemporaryFile

from fastapi import APIRouter, HTTPException, Query, Response
from fastapi.responses import FileResponse
from PIL import Image

from . import library_store

router = APIRouter(prefix='/api/agent/images', tags=['Modo agente'])
OVERVIEW_LONG_SIDE = 1024


def overview_size(width, height):
    scale = min(1., OVERVIEW_LONG_SIDE / max(width, height))
    return max(1, round(width * scale)), max(1, round(height * scale))


def view_info(image_id, width, height):
    w, h = overview_size(width, height)
    prefix = f'/api/agent/images/{image_id}'
    return dict(native_wh=[width, height], view_wh=[w, h],
                native_per_view_xy=[width / w, height / h],
                overview_url=prefix + '/overview', crop_url=prefix + '/crop')


def library_photo(image_id):
    if not image_id or not all(c.isalnum() or c in '_-' for c in image_id):
        raise HTTPException(404, 'Imagen desconocida.')
    path = library_store.LIBRARY_DIR / image_id / 'image.png'
    if not path.is_file():
        raise HTTPException(404, 'Imagen desconocida.')
    return path


@router.get('/{image_id}/overview')
def overview(image_id: str):
    return overview_response(library_photo(image_id))


def overview_response(photo: Path):
    with Image.open(photo) as native:
        size = overview_size(*native.size)
        if size == native.size:
            return FileResponse(photo, media_type='image/png')
        cached = photo.with_name(f'{photo.stem}-overview-{size[0]}x{size[1]}.png')
        if not cached.is_file() or cached.stat().st_mtime_ns < photo.stat().st_mtime_ns:
            with NamedTemporaryFile(dir=photo.parent, delete=False) as temp:
                staging = Path(temp.name)
            try:
                native.resize(size, Image.Resampling.LANCZOS).save(staging, format='PNG')
                staging.replace(cached)
            finally:
                staging.unlink(missing_ok=True)
    return FileResponse(cached, media_type='image/png')


@router.get('/{image_id}/crop')
def crop(image_id: str, x: int = Query(ge=0), y: int = Query(ge=0),
         w: int = Query(gt=0), h: int = Query(gt=0)):
    with Image.open(library_photo(image_id)) as native:
        if x + w > native.width or y + h > native.height:
            raise HTTPException(422, 'El recorte debe quedar dentro de la imagen nativa.')
        stream = BytesIO()
        native.crop((x, y, x + w, y + h)).save(stream, format='PNG')
    return Response(stream.getvalue(), media_type='image/png')

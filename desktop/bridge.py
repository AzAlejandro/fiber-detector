"""Local MCP adapter to the same LOCO API used by the editor."""
from pathlib import Path
import re
from typing import Literal

import httpx
from mcp.server.fastmcp import FastMCP, Image


def run(base):
    client = httpx.Client(base_url=base, timeout=600, trust_env=False)
    mcp = FastMCP('LOCO Detector', instructions='Para instalar o actualizar usa guia_mantenimiento_loco. Para imágenes y diámetros usa guia_loco.')

    @mcp.tool()
    def guia_mantenimiento_loco() -> str:
        """Consultar cómo actualizar esta instalación desde la release oficial y verificar los datos."""
        return (Path(__file__).resolve().parent/'docs/INSTALAR_ACTUALIZAR.md').read_text(encoding='utf8')

    @mcp.tool()
    def conexion_loco() -> dict:
        """Comprobar motor, versión, skill y proyecto activo."""
        return client.get('/api/agent/connection').raise_for_status().json()

    @mcp.tool()
    def guia_loco(herramientas: bool = False, revision: bool = False) -> str:
        """Leer la guía inicial, las herramientas o la revisión final del coordinador."""
        return client.get('/api/agent/guide', params={'tools': herramientas, 'review': revision}).raise_for_status().text

    @mcp.tool()
    def importar_imagen(archivo: str, proyecto: str, copia_independiente: bool = False) -> dict:
        """Importar el archivo local de microscopía elegido por el usuario."""
        path = Path(archivo)
        if not path.is_absolute() or path.suffix.lower() not in ('.tiff','.tif','.png','.jpeg','.jpg','.bmp'):
            raise ValueError('Se requiere la ruta absoluta de una imagen de LOCO.')
        sid = client.post('/api/session/new', json={}).raise_for_status().json()['payload']['session_id']
        with path.open('rb') as f:
            res = client.post('/api/agent/images/import', data={'session_id': sid, 'project_id': proyecto,
                               'independent_copy': str(copia_independiente).lower()},
                              files={'file': (path.name, f)})
        return res.raise_for_status().json()['payload']

    @mcp.tool()
    def ver_imagen(image_id: str, recorte_xywh: list[int] | None = None) -> Image:
        """Ver la imagen reducida o un recorte nativo [x,y,ancho,alto]."""
        if not re.fullmatch(r'[\w-]+', image_id):
            raise ValueError('ID de imagen inválido.')
        url = '/api/agent/images/' + image_id
        if recorte_xywh is None:
            res = client.get(url+'/overview')
        else:
            res = client.get(url+'/crop', params=dict(zip(('x','y','w','h'), recorte_xywh, strict=True)))
        return Image(data=res.raise_for_status().content, format='png')

    @mcp.tool()
    def flujo_loco(metodo: Literal['GET','POST'], ruta: str, parametros: dict | None = None) -> dict:
        """Ejecutar una etapa documentada por guia_loco(herramientas=true). GET usa query y POST usa JSON."""
        reads = (r'projects/list', r'agent/(?:worklist|target-review)', r'agent/runs(?:/[a-f0-9]+)?', r'agent/scribble-masks',
                 r'agent-training/[\w-]+/(?:scribbles|circulos|cruces)/state',
                 r'diameter-research/(?:calibration/load|measurements/query)')
        writes = (r'projects/(?:upsert|activate)', r'session/new', r'library/load', r'agent/(?:runs|scribble-masks)', r'scribble/draft/save',
                  r'diameter-research/(?:calibration/save|run|measurements/save-from-run|agent-editor/[a-f0-9]+(?:/contacts)?)')
        if not any(re.fullmatch('/api/'+route, ruta) for route in (reads if metodo=='GET' else writes)):
            raise ValueError('Ruta fuera del flujo de procesamiento de LOCO.')
        params = parametros or {}
        if ruta == '/api/library/load':
            params = {**params, 'agent_view': True}
        res = client.get(ruta, params=params) if metodo=='GET' else client.post(ruta, json=params)
        value = res.raise_for_status().json()
        if ruta.endswith('/state'):
            active = value['active']
            return {'active': {'id': active['id'], 'version': active['version'], 'body': active.get('execution_body', active['body'])},
                    'targets': value.get('targets', {})}
        return value

    mcp.run(transport='stdio')

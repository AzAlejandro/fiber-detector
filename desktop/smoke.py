"""Exercise the installed application via its public MCP transport with isolated data."""
import argparse
import asyncio
import json
import os
from pathlib import Path
import site
import subprocess
import sys
import urllib.request


async def check(args):
    root = args.root.resolve()
    data = args.data.resolve()
    data.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, LOCO_DATA_DIR=str(data), LOCO_DESKTOP_PORT=str(args.port))
    python = root/'runtime'/('python.exe' if os.name == 'nt' else 'bin/python3.12')
    command = [str(python), str(root/'launch.py')]
    if sys.platform == 'darwin':
        command = [str(root.parent/'MacOS/LOCO')]
    site.addsitedir(str(root/'vendor'))
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    from PIL import Image
    base = f'http://127.0.0.1:{args.port}'
    params = StdioServerParameters(command=command[0], args=command[1:]+['mcp'], env=env)
    try:
        async with stdio_client(params) as transport, ClientSession(*transport) as client:
            await client.initialize()
            tools = {tool.name for tool in (await client.list_tools()).tools}
            assert {'conexion_loco','guia_loco','importar_imagen','ver_imagen','flujo_loco'} <= tools, tools

            async def call(name, **arguments):
                result = await client.call_tool(name, arguments)
                assert not result.isError, result.content
                return result.content[0]

            async def status():
                return json.loads((await call('conexion_loco')).text)

            state = await status()
            assert state['version'] == args.version and state['ready'], state
            assert 'loco-inicio' in (await call('guia_loco')).text
            assert 'calibration/save' in (await call('guia_loco', herramientas=True)).text
            if args.phase == 'verify':
                assert 'Actualiza LOCO' in (await call('guia_mantenimiento_loco')).text
            with urllib.request.urlopen(base) as response:
                assert b'<script' in response.read()
            saved = data/'smoke-image.json'
            targets_file = data/'smoke-targets.json'
            if args.phase == 'seed':
                assert not saved.exists(), 'Usa una carpeta de prueba vacía.'
                request = urllib.request.Request(base+'/api/projects/upsert',
                    data=json.dumps(dict(name='Proyecto de prueba', active=True)).encode(),
                    headers={'Content-Type': 'application/json'})
                with urllib.request.urlopen(request) as response:
                    project = json.load(response)['payload']['active_project_id']
                photo = data/'prueba escala.png'
                Image.linear_gradient('L').resize((64,64)).save(photo)
                result = await call('importar_imagen', archivo=str(photo), proyecto=project)
                iid = json.loads(result.text)['image_id']
                await call('flujo_loco', metodo='POST', ruta='/api/diameter-research/calibration/save',
                           parametros=dict(image_id=iid, enabled=True, unit='nm', known_value=500,
                               pixel_distance=50, unit_per_px=10, line_x1=1,line_x2=51,line_y1=61,line_y2=61))
                saved.write_text(json.dumps([project, iid]))
                # Older candidates can seed an image before project targets were introduced.
                with urllib.request.urlopen(base+'/openapi.json') as response:
                    has_targets = '/api/projects/{project_id}/agent-targets' in json.load(response)['paths']
                if has_targets:
                    targets = dict(painted_percent=30, percent_tolerance=5, circle_count=40, circle_tolerance=5)
                    request = urllib.request.Request(base+f'/api/projects/{project}/agent-targets',
                        data=json.dumps(targets).encode(), headers={'Content-Type': 'application/json'})
                    with urllib.request.urlopen(request) as response:
                        assert json.load(response) == targets
                    targets_file.write_text(json.dumps(targets))
            project, iid = json.loads(saved.read_text())
            assert (await status())['active_project_id'] == project
            assert (await call('ver_imagen', image_id=iid)).type == 'image'
            result = await call('flujo_loco', metodo='GET', ruta='/api/diameter-research/calibration/load',
                                parametros={'image_id':iid})
            assert json.loads(result.text)['calibration']['nm_per_px'] == 10
            if targets_file.exists():
                targets = json.loads(targets_file.read_text())
                for kind in ('scribbles', 'circulos'):
                    state = await call('flujo_loco', metodo='GET', ruta=f'/api/agent-training/{project}/{kind}/state')
                    assert json.loads(state.text)['targets'] == targets
            print(f'{args.phase} OK: {args.version}, proyecto {project}, imagen {iid}, 10 nm/px, {len(tools)} herramientas MCP.')
    finally:
        subprocess.run(command+['stop'],env=env,check=True,timeout=60)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('phase', choices=['seed','verify'])
    parser.add_argument('root', type=Path)
    parser.add_argument('data', type=Path)
    parser.add_argument('version')
    parser.add_argument('--port', type=int, default=15181)
    asyncio.run(check(parser.parse_args()))

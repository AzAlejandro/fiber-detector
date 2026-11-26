"""Entry point shipped alongside backend/, vendor/ and frontend/dist/."""
import argparse
from contextlib import ExitStack
import hashlib
import json
import os
from pathlib import Path
import secrets
import site
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
import webbrowser
from threading import Thread

ROOT = Path(__file__).resolve().parent
sys.dont_write_bytecode = True
os.environ['PYTHONDONTWRITEBYTECODE'] = '1'
site.addsitedir(str(ROOT / 'vendor'))
if sys.platform == 'darwin':
    default_home = Path.home() / 'Library/Application Support/LOCO Detector'
else:
    default_home = Path(os.environ.get('LOCALAPPDATA', Path.home())) / 'LOCO Detector'
HOME_DIR = Path(os.environ.get('LOCO_DATA_DIR') or default_home).expanduser().resolve()
os.environ['LOCO_DATA_DIR'] = str(HOME_DIR)
os.environ['LOCO_DESKTOP'] = '1'
PORT = int(os.environ.get('LOCO_DESKTOP_PORT', '5181'))
BASE = f'http://127.0.0.1:{PORT}'
INSTANCE = hashlib.sha256(os.path.normcase(str(HOME_DIR)).encode()).hexdigest()
TOKEN_FILE = HOME_DIR / f'.control-{PORT}'


def running():
    try:
        with urllib.request.urlopen(BASE + '/api/desktop/instance', timeout=1) as res:
            return json.load(res).get('instance') == INSTANCE
    except (OSError, ValueError):
        return False


def stop():
    if not running():
        return
    request = urllib.request.Request(BASE + '/api/desktop/stop', method='POST',
                                     headers={'X-Loco-Control': TOKEN_FILE.read_text()})
    with urllib.request.urlopen(request, timeout=5):
        pass
    for _ in range(160):
        if not running() and not TOKEN_FILE.exists():
            # Allow attached stdio bridges to release the bundled runtime on Windows.
            time.sleep(.5)
            return
        time.sleep(.25)
    raise RuntimeError('LOCO sigue cerrando operaciones. Reintenta antes de actualizar.')


def serve(show_browser):
    with socket.socket() as sock, ExitStack() as listeners:
        if sys.platform == 'win32':
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        else:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind(('127.0.0.1', PORT))
        except OSError:
            for _ in range(20):
                if running():
                    if show_browser:
                        webbrowser.open(BASE)
                    return
                time.sleep(.25)
            raise RuntimeError(f'El puerto local {PORT} está ocupado.')

        sockets = [sock]
        ports = [PORT]
        alias_config = HOME_DIR / 'desktop-alias-port'
        if alias_config.is_file():
            alias = int(alias_config.read_text().strip())
            if alias != PORT and 1024 <= alias <= 65535:
                extra = listeners.enter_context(socket.socket())
                if sys.platform == 'win32':
                    extra.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
                try:
                    extra.bind(('127.0.0.1', alias))
                except OSError as exc:
                    print(f'Puerto alternativo {alias} no disponible: {exc}', file=sys.stderr)
                else:
                    sockets.append(extra)
                    ports.append(alias)
        origins = {f'http://{host}:{port}' for port in ports for host in ('127.0.0.1', 'localhost')}
        from fastapi import HTTPException, Request
        from fastapi.responses import Response
        from fastapi.staticfiles import StaticFiles
        from starlette.middleware.trustedhost import TrustedHostMiddleware
        import uvicorn
        from backend.main import app

        app.add_middleware(TrustedHostMiddleware, allowed_hosts=['127.0.0.1','localhost'])
        @app.middleware('http')
        async def check_origin(request: Request, call_next):
            origin = request.headers.get('origin')
            if origin and origin not in origins:
                return Response(status_code=403)
            return await call_next(request)

        token = secrets.token_hex(32)
        @app.get('/api/desktop/instance')
        def identity():
            return {'instance': INSTANCE}

        @app.post('/api/desktop/stop')
        def shutdown(request: Request):
            if not secrets.compare_digest(request.headers.get('x-loco-control', ''), token):
                raise HTTPException(403)
            server.should_exit = True
            return {'closing': True}

        app.mount('/', StaticFiles(directory=ROOT/'frontend/dist', html=True))
        server = uvicorn.Server(uvicorn.Config(app, host='127.0.0.1', port=PORT, log_config=None))
        with open(os.open(TOKEN_FILE, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600), 'w', closefd=True) as f:
            f.write(token)
        if show_browser:
            def open_when_ready():
                while not server.started and not server.should_exit:
                    time.sleep(.1)
                if server.started:
                    webbrowser.open(BASE)
            Thread(target=open_when_ready, daemon=True).start()
        try:
            server.run(sockets=sockets)
        finally:
            TOKEN_FILE.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('action', nargs='?', choices=['start','stop','status','mcp'], default='start')
    parser.add_argument('--no-browser', action='store_true')
    args = parser.parse_args()
    HOME_DIR.mkdir(parents=True, exist_ok=True)
    os.chdir(HOME_DIR)
    if args.action == 'stop':
        stop()
    elif args.action == 'status':
        if not running():
            raise SystemExit('LOCO de escritorio no está abierto.')
        with urllib.request.urlopen(BASE + '/api/agent/connection', timeout=5) as r:
            print(r.read().decode())
    elif args.action == 'mcp':
        if not running():
            with (HOME_DIR/'server.log').open('a') as log:
                subprocess.Popen([sys.executable, str(ROOT/'launch.py'), '--no-browser'],
                                 stdin=subprocess.DEVNULL, stdout=log, stderr=log,
                                 creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0,
                                 start_new_session=os.name!='nt')
            for _ in range(120):
                if running():
                    break
                time.sleep(.5)
            else:
                raise RuntimeError('LOCO no arrancó. Revisa server.log en la carpeta de datos.')
        from bridge import run
        generation = TOKEN_FILE.read_bytes()
        def follow_server():
            while True:
                time.sleep(.2)
                try:
                    if TOKEN_FILE.read_bytes() == generation:
                        continue
                except FileNotFoundError:
                    pass
                os._exit(0)
        Thread(target=follow_server, daemon=True).start()
        run(BASE)
    else:
        serve(not args.no_browser)


if __name__ == '__main__':
    if sys.stderr is None:
        HOME_DIR.mkdir(parents=True, exist_ok=True)
        sys.stdout = sys.stderr = (HOME_DIR/'server.log').open('a', buffering=1)
    main()

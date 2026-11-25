"""Stage a self-contained desktop application using the native build machine."""
import argparse
import os
from pathlib import Path
import platform
import plistlib
import re
import shutil
import subprocess
import sys
from tempfile import TemporaryDirectory

REPO = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('destination', type=Path, help='New staging directory')
    parser.add_argument('version', help='Stable numeric version, e.g. 1.1.0')
    args = parser.parse_args()
    if not re.fullmatch(r'\d+\.\d+\.\d+', args.version):
        parser.error('Se requiere una versión mayor.menor.parche.')
    if args.version != (REPO / 'VERSION').read_text().strip():
        parser.error('La versión del instalador debe coincidir con VERSION.')
    mac = sys.platform == 'darwin'
    if (mac and platform.machine() != 'arm64') or (not mac and sys.platform != 'win32'):
        parser.error('Targets: Windows x64, macOS Apple Silicon')
    destination = args.destination.resolve()
    destination.mkdir(parents=True, exist_ok=False)
    bundle = destination/'LOCO.app'/'Contents'
    root = bundle/'Resources' if mac else destination/'app'
    root.mkdir(parents=True)
    python = subprocess.check_output(['uv','python','find','--managed-python','3.12'], text=True).strip()
    prefix = subprocess.check_output([python,'-I','-c','import sys; print(sys.base_prefix)'], text=True).strip()
    shutil.copytree(prefix, root/'runtime', symlinks=mac, ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    lock = REPO/'desktop'/('macos-arm64.lock' if mac else 'windows.lock')
    subprocess.run(['uv','pip','install','--python',python,'--target',root/'vendor','--only-binary',':all:',
                    '--require-hashes','-r',lock],check=True)
    shutil.copytree(REPO/'backend',root/'backend',ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    shutil.copytree(REPO/'.agents/skills/loco-inicio',root/'.agents/skills/loco-inicio')
    shutil.copytree(REPO/'.agents/skills/loco-revision',root/'.agents/skills/loco-revision')
    shutil.copytree(REPO/'.agents/skills/loco-instalacion',root/'.agents/skills/loco-instalacion')
    for file in ('launch.py','bridge.py'):
        shutil.copy2(REPO/'desktop'/file,root/file)
    shutil.copy2(REPO/'LICENSE',root/'LICENSE')
    (root/'docs').mkdir()
    shutil.copy2(REPO/'docs/INSTALAR_ACTUALIZAR.md',root/'docs/INSTALAR_ACTUALIZAR.md')
    shutil.copy2(REPO/'docs/GITHUB_RELEASES_WINDOWS_MAC.md',root/'docs/GITHUB_RELEASES_WINDOWS_MAC.md')
    shutil.copy2(REPO/'desktop'/('instalar-mac.sh' if mac else 'instalar-windows.ps1'),root)
    (root/'VERSION').write_text(args.version+'\n')

    npm = shutil.which('npm.cmd' if os.name=='nt' else 'npm')
    with TemporaryDirectory() as temp:
        web = Path(temp)/'frontend'
        shutil.copytree(REPO/'frontend', web, ignore=shutil.ignore_patterns('node_modules','dist','.env*'))
        subprocess.run([npm,'ci'],cwd=web,check=True)
        subprocess.run([npm,'run','build','--','--outDir',root/'frontend/dist'],cwd=web,
                       env={**os.environ,'VITE_API_BASE':'same-origin'},check=True)
    shutil.copytree(REPO/'frontend/public/tutorial', root/'frontend/public/tutorial')
    if mac:
        (bundle/'MacOS').mkdir()
        subprocess.run(['cc',REPO/'desktop/mac-launcher.c','-o',bundle/'MacOS/LOCO'],check=True)
        (bundle/'Info.plist').write_bytes(plistlib.dumps(dict(CFBundleName='LOCO Detector',
            CFBundleIdentifier='org.locodetector.desktop',CFBundlePackageType='APPL',CFBundleExecutable='LOCO',
            CFBundleVersion=args.version,CFBundleShortVersionString=args.version,LSMinimumSystemVersion='15.0')))
        omp = Path(subprocess.check_output(['brew','--prefix','libomp'],text=True).strip())/'lib/libomp.dylib'
        target = root/'vendor/.dylibs/libomp.dylib'
        target.parent.mkdir(exist_ok=True)
        shutil.copy2(omp,target)
        for path in (root/'vendor').rglob('*.dylib'):
            if path == target or path.is_symlink():
                continue
            linked = subprocess.check_output(['otool','-L',path],text=True)
            for line in linked.splitlines()[1:]:
                name = line.strip().split(' (')[0]
                if name.endswith('/libomp.dylib'):
                    new = '@loader_path/'+os.path.relpath(target,path.parent)
                    subprocess.run(['install_name_tool','-change',name,new,path],check=True)
                    subprocess.run(['codesign','--force','--sign','-',path],check=True)
    print(root)


if __name__ == '__main__':
    main()

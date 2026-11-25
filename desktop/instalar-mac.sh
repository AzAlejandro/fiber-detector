#!/bin/bash
set -euo pipefail
[[ $(uname -sm) == "Darwin arm64" ]] || { echo "Esta edición requiere macOS Apple Silicon." >&2; exit 1; }
[[ $(sw_vers -productVersion | cut -d. -f1) -ge 15 ]] || { echo "Esta edición requiere macOS 15 o posterior." >&2; exit 1; }
apps="$HOME/Applications"
mkdir -p "$apps"
tmp=$(mktemp -d "$apps/.loco-install.XXXXXXXX")
mount="$tmp/montaje"
app="$apps/LOCO.app"
cleanup() {
  if mount | grep -Fq " on $mount ("; then hdiutil detach "$mount" -quiet || return; fi
  # Conservar la copia anterior cuando una restauración manual sea necesaria.
  if [[ ! -e "$tmp/anterior.app" ]]; then rm -rf "$tmp"; fi
}
trap cleanup EXIT
endpoint=latest
if [[ $# -gt 0 ]]; then
  [[ $# -eq 1 && $1 =~ ^v[0-9]+\.[0-9]+\.[0-9]+$ ]] || { echo 'Se esperaba un tag vX.Y.Z.' >&2; exit 2; }
  endpoint="tags/$1"
fi
curl -fsSL "https://api.github.com/repos/AzAlejandro/LOCO-detector/releases/$endpoint" -o "$tmp/release.json"
# JXA y Foundation vienen con macOS. Extraer el asset de la misma release que el digest.
osascript -l JavaScript - "$tmp/release.json" > "$tmp/asset" <<'JS'
function run(args) {
  ObjC.import('Foundation');
  const text = $.NSString.stringWithContentsOfFileEncodingError(args[0], $.NSUTF8StringEncoding, null);
  const r = JSON.parse(ObjC.unwrap(text));
  const a = r.assets.find(x => x.name === 'LOCO-macOS-arm64.dmg');
  if (r.draft || r.prerelease || !/^v\d+\.\d+\.\d+$/.test(r.tag_name) || !a || !/^sha256:[0-9a-f]{64}$/.test(a.digest))
    throw Error('La release estable todavía no ofrece un DMG con digest para este Mac.');
  return [r.tag_name.slice(1), a.browser_download_url, a.digest.slice(7)].join('\n');
}
JS
version=$(sed -n '1p' "$tmp/asset")
if [[ $# -gt 0 && "v$version" != "$1" ]]; then echo 'La versión recibida no coincide con la solicitada.' >&2; exit 1; fi
url=$(sed -n '2p' "$tmp/asset")
digest=$(sed -n '3p' "$tmp/asset")
installed=''
if [[ -f "$app/Contents/Resources/VERSION" ]]; then installed=$(cat "$app/Contents/Resources/VERSION"); fi
if [[ -e "$app" && ! -f "$app/Contents/Resources/VERSION" ]]; then echo "Revisa la aplicación existente en $app." >&2; exit 1; fi
if [[ -n "$installed" ]] && awk -v a="$installed" -v b="$version" 'BEGIN {split(a,x,"[.]"); split(b,y,"[.]"); for(i=1;i<=3;i++){if(x[i]+0!=y[i]+0)exit !(x[i]+0>y[i]+0)} exit 1}'; then
  echo "La versión instalada es más reciente." >&2; exit 1
fi
if [[ "$installed" != "$version" ]]; then
  curl -fLsS "$url" -o "$tmp/LOCO.dmg"
  echo "$digest  $tmp/LOCO.dmg" | shasum -a 256 -c -
  mkdir "$mount"
  hdiutil attach -readonly -nobrowse -mountpoint "$mount" "$tmp/LOCO.dmg" -quiet
  ditto "$mount/LOCO.app" "$tmp/nueva.app"
  codesign --verify --deep --strict "$tmp/nueva.app"
  spctl --assess --type execute "$tmp/nueva.app"
  [[ $(cat "$tmp/nueva.app/Contents/Resources/VERSION") == "$version" ]]
  if [[ -d "$app" ]]; then "$app/Contents/MacOS/LOCO" stop; mv "$app" "$tmp/anterior.app"; fi
  if ! mv "$tmp/nueva.app" "$app"; then
    if [[ -e "$tmp/anterior.app" ]]; then mv "$tmp/anterior.app" "$app"; fi
    exit 1
  fi
fi
open "$app"
for ((i=0; i<60; i++)); do
  if "$app/Contents/MacOS/LOCO" status > "$tmp/status.json" 2>/dev/null &&
     [[ $(plutil -extract version raw "$tmp/status.json") == "$version" ]] &&
     [[ $(plutil -extract ready raw "$tmp/status.json") == true ]]; then
    cat "$tmp/status.json"
    if [[ -d "$tmp/anterior.app" ]]; then rm -rf "$tmp/anterior.app"; fi
    exit 0
  fi
  sleep 1
done
echo "No se pudo verificar LOCO $version. Si existe, tu aplicación anterior sigue en $tmp/anterior.app." >&2
exit 1

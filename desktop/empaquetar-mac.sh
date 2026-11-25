#!/bin/bash
# Candidato local por defecto; para distribución proporcionar una identidad y perfil notarial.
set -euo pipefail
app=${1:?ruta a LOCO.app}
out=${2:?ruta al DMG}
identity=${LOCO_SIGN_IDENTITY:--}
opts=(--force --sign "$identity")
if [[ "$identity" != '-' ]]; then
  : "${LOCO_NOTARY_PROFILE:?perfil de notarytool para la distribución}"
  opts+=(--options runtime --timestamp)
fi
# Firmar de dentro hacia fuera. El runtime y los wheels incluyen extensiones nativas.
while IFS= read -r -d '' file; do
  if file -b "$file" | grep -q 'Mach-O'; then codesign "${opts[@]}" "$file"; fi
done < <(find "$app/Contents" -type f \( -perm -u+x -o -name '*.so' -o -name '*.dylib' \) -print0)
while IFS= read -r -d '' nested; do
  codesign "${opts[@]}" "$nested"
done < <(find "$app/Contents" -depth -type d \( -name '*.app' -o -name '*.framework' \) -print0)
codesign "${opts[@]}" "$app"
codesign --verify --deep --strict "$app"
temp=$(mktemp -d)
trap 'rm -rf "$temp"' EXIT
if [[ "$identity" != '-' ]]; then
  ditto -c -k --keepParent "$app" "$temp/LOCO.zip"
  xcrun notarytool submit "$temp/LOCO.zip" --keychain-profile "$LOCO_NOTARY_PROFILE" --wait
  xcrun stapler staple "$app"
fi
mkdir "$temp/imagen"
cp -cR "$app" "$temp/imagen/LOCO.app" || ditto "$app" "$temp/imagen/LOCO.app"
hdiutil create -ov -format UDZO -volname 'LOCO Detector' -srcfolder "$temp/imagen" "$out"
if [[ "$identity" != '-' ]]; then
  codesign "${opts[@]}" "$out"
  xcrun notarytool submit "$out" --keychain-profile "$LOCO_NOTARY_PROFILE" --wait
  xcrun stapler staple "$out"
  xcrun stapler validate "$out"
fi

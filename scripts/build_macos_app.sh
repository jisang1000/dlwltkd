#!/usr/bin/env bash
set -euo pipefail

if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "이 스크립트는 macOS에서만 실행 가능합니다."
  exit 1
fi

PY_BIN="${PY_BIN:-python3}"
APP_NAME="HairInfo Salon Manager"
BUNDLE_ID="com.hairinfo.salonmanager"

"${PY_BIN}" -m pip install --upgrade pip
"${PY_BIN}" -m pip install pyinstaller fastapi uvicorn sqlalchemy pydantic

"${PY_BIN}" -m PyInstaller \
  --noconfirm \
  --clean \
  --windowed \
  --name "${APP_NAME}" \
  --osx-bundle-identifier "${BUNDLE_ID}" \
  launcher.py

APP_BUNDLE="dist/${APP_NAME}.app"
ZIP_NAME="dist/hairinfo-salon-manager-macos.zip"

rm -f "${ZIP_NAME}"
(cd dist && ditto -c -k --sequesterRsrc --keepParent "${APP_NAME}.app" "$(basename "${ZIP_NAME}")")

echo "macOS 앱 번들 생성 완료: ${APP_BUNDLE}"
echo "배포용 ZIP 생성 완료: ${ZIP_NAME}"

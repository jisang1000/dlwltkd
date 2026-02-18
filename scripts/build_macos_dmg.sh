#!/usr/bin/env bash
set -euo pipefail

if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "이 스크립트는 macOS에서만 실행 가능합니다."
  exit 1
fi

APP_NAME="HairInfo Salon Manager"
APP_BUNDLE="dist/${APP_NAME}.app"
DMG_NAME="dist/hairinfo-salon-manager-macos.dmg"

if [[ ! -d "${APP_BUNDLE}" ]]; then
  echo "${APP_BUNDLE} 가 없습니다. 먼저 scripts/build_macos_app.sh 를 실행하세요."
  exit 1
fi

TMP_DIR="$(mktemp -d)"
cp -R "${APP_BUNDLE}" "${TMP_DIR}/"
ln -s /Applications "${TMP_DIR}/Applications"

rm -f "${DMG_NAME}"
hdiutil create -volname "${APP_NAME}" -srcfolder "${TMP_DIR}" -ov -format UDZO "${DMG_NAME}"
rm -rf "${TMP_DIR}"

echo "DMG 생성 완료: ${DMG_NAME}"

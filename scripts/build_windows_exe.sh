#!/usr/bin/env bash
set -euo pipefail

if [[ "$(uname -s)" != MINGW* && "$(uname -s)" != CYGWIN* && "$(uname -s)" != MSYS* ]]; then
  echo "이 스크립트는 Git Bash/Windows 환경에서 실행하세요."
  exit 1
fi

powershell -ExecutionPolicy Bypass -File ./scripts/build_windows_exe.ps1

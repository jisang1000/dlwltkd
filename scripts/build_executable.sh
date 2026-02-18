#!/usr/bin/env bash
set -euo pipefail

# Why: 단일 진입점으로 빌드 절차를 표준화해 팀/운영 환경 편차를 줄입니다.
python -m pip install --upgrade pip
python -m pip install pyinstaller
pyinstaller --noconfirm --onefile --windowed --name hairinfo-launcher launcher.py

echo "빌드 완료: dist/hairinfo-launcher"

# HairInfo 헤어샵 관리 프로그램 (FastAPI + 내장 UI)

헤어샵의 고객/디자이너/서비스/예약/매출 요약을 관리하는 REST API와 간단한 운영 UI를 제공합니다.

## 핵심 기능
- 고객 등록 (중복 전화번호 방지)
- 디자이너 등록
- 서비스 등록 (중복 서비스명 방지)
- 예약 등록 (참조 무결성 + 동일 디자이너/동시간 중복 예약 방지)
- 예약 상태 변경 (scheduled/completed/cancelled)
- 당일 대시보드 요약 (총 예약, 완료 예약, 취소율, 완료 기준 예상 매출)
- 웹 UI (`/`)에서 요약 확인 + 빠른 예약 생성

## 실행 옵션

### 1) 일반 실행
```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
uvicorn app.main:app --reload
```
- UI: `http://127.0.0.1:8000/`
- Swagger: `http://127.0.0.1:8000/docs`

### 2) 터미널 없이 실행 (GUI 실행기)
```bash
python launcher.py
```
- 버튼으로 서버 시작/중지 및 브라우저 오픈 가능

### 3) 실행파일(바이너리) 빌드
```bash
./scripts/build_executable.sh
```
- 산출물: `dist/hairinfo-launcher`


### 4) macOS 실행파일(.app/.dmg) 빌드
```bash
./scripts/build_macos_app.sh
./scripts/build_macos_dmg.sh
```
- 앱 번들: `dist/HairInfo Salon Manager.app`
- 배포 ZIP: `dist/hairinfo-salon-manager-macos.zip`
- 설치 DMG: `dist/hairinfo-salon-manager-macos.dmg`

### 5) Linux 환경에서 macOS 실행파일 만들기 (원클릭)
```bash
# GitHub Actions > build-macos-app > Run workflow
```
- 이 저장소의 CI가 macOS runner에서 `.app/.dmg`를 빌드해 Artifact로 제공합니다.
- 태그(`v1.0.0` 형식) 푸시 시 Release에 `.zip/.dmg`가 자동 첨부됩니다.

## Linux 데스크탑 바로가기
- `HairInfo-Salon-Manager.desktop` 파일을 더블클릭하면 실행기(`launcher.py`)가 열립니다.
- 필요 시 `Exec`, `Path` 경로를 로컬 경로에 맞게 수정하세요.

## 테스트
```bash
pytest
```

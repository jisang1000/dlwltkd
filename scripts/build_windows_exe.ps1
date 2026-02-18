param(
    [string]$PythonExe = "python"
)

$ErrorActionPreference = "Stop"

if (-not $IsWindows) {
    Write-Error "이 스크립트는 Windows에서만 실행 가능합니다."
}

& $PythonExe -m pip install --upgrade pip
& $PythonExe -m pip install pyinstaller fastapi uvicorn sqlalchemy pydantic

& $PythonExe -m PyInstaller `
    --noconfirm `
    --clean `
    --onefile `
    --windowed `
    --name "hairinfo-launcher" `
    launcher.py

$distDir = Join-Path (Get-Location) "dist"
$zipPath = Join-Path $distDir "hairinfo-launcher-windows.zip"
$exePath = Join-Path $distDir "hairinfo-launcher.exe"

if (Test-Path $zipPath) {
    Remove-Item $zipPath -Force
}

Compress-Archive -Path $exePath -DestinationPath $zipPath -Force

Write-Host "Windows 실행파일 생성 완료: $exePath"
Write-Host "배포 ZIP 생성 완료: $zipPath"

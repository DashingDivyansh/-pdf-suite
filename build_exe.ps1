$ErrorActionPreference = "Stop"

Write-Host "Cleaning previous builds..." -ForegroundColor Cyan
if (Test-Path "dist") { Remove-Item -Recurse -Force "dist" }
if (Test-Path "build") { Remove-Item -Recurse -Force "build" }

Write-Host "Building optimized standalone executable..." -ForegroundColor Green
python -m PyInstaller pdf_tool.spec --clean --noconfirm

Write-Host "Running executable integrity tests..." -ForegroundColor Cyan
python tests/test_exe_integrity.py

Write-Host "Build and integrity check complete!" -ForegroundColor Green
Write-Host "Optimized app folder is at dist/PDF_Tool/" -ForegroundColor Green
Write-Host "Run dist/PDF_Tool/PDF_Tool.exe for instant startup." -ForegroundColor Green

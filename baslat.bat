@echo off
chcp 65001 >nul
title DisMaker - Discord Sunucu Mimari Botu
cd /d "%~dp0"

echo ==============================================================================
echo   DisMaker - Evrensel Discord Mimari ve Sistem Muhendisi
echo ==============================================================================
echo.

where python >nul 2>&1
if %errorlevel% neq 0 (
    echo [HATA] Python bulunamadi! Lutfen Python'in kurulu ve PATH'e ekli oldugundan emin olun.
    echo.
    pause
    exit /b %errorlevel%
)

echo Bot baslatiliyor, lutfen bekleyin...
echo.

python main.py

if %errorlevel% neq 0 (
    echo.
    echo [BILGI] Bot bir hata nedeniyle veya kullanici tarafindan durduruldu.
    echo.
    pause
)

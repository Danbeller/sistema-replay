@echo off
chcp 65001 >nul
title Sistema de Reconhecimento Facial

set "REPLAY_SERIAL_ENABLED=1"
if /I "%~1"=="sem-arduino" (
    set "REPLAY_SERIAL_ENABLED=0"
)
 
echo Verificando Python...
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERRO] Python nao encontrado. Instale o Python e adicione ao PATH.
    pause
    exit /b 1
)
 
echo Verificando dependencias...
python -c "import cv2, numpy, mss, PIL, serial" >nul 2>&1
if errorlevel 1 (
    echo Instalando dependencias necessarias...
    pip install -r "%~dp0requirements.txt"
    if errorlevel 1 (
        echo [ERRO] Falha ao instalar dependencias.
        pause
        exit /b 1
    )
)
 
if "%REPLAY_SERIAL_ENABLED%"=="0" (
    echo Iniciando em modo sem Arduino para liberar a porta serial...
) else (
    echo Iniciando com integracao do Arduino ativa...
)

echo Iniciando sistema...
python "%~dp0server.py"
 
pause
 

@echo off
chcp 65001 >nul
title 客户积分智能分析系统

echo ============================================
echo    客户积分智能分析系统 - 启动程序
echo ============================================
echo.

set "PROJECT_DIR=%~dp0"
set "VENV_DIR=%PROJECT_DIR%.venv"
set "PYTHON=%VENV_DIR%\Scripts\python.exe"
set "PIP=%VENV_DIR%\Scripts\pip.exe"
set "STREAMLIT=%VENV_DIR%\Scripts\streamlit.exe"

if not exist "%VENV_DIR%" (
    echo [1/3] 创建虚拟环境...
    python -m venv "%VENV_DIR%"
    if errorlevel 1 (
        echo 错误: 无法创建虚拟环境，请确保已安装Python
        pause
        exit /b 1
    )
)

if not exist "%PIP%" (
    echo [2/3] 安装依赖包...
    "%PYTHON%" -m pip install -r "%PROJECT_DIR%requirements.txt"
    if errorlevel 1 (
        echo 错误: 安装依赖失败
        pause
        exit /b 1
    )
)

echo [3/3] 启动系统...
echo.
echo 系统将在浏览器中打开，地址: http://localhost:8501
echo 按 Ctrl+C 停止运行
echo.

cd /d "%PROJECT_DIR%"
"%STREAMLIT%" run app.py --server.port 8501

pause

@echo off
chcp 65001 >nul
title 澄天小助手（含 AI 视频剪辑）

echo ============================================
echo    澄天小助手 - 启动程序
echo    （积分系统 / 报价 / 发票 / 邮件 / 🎬 AI 视频剪辑）
echo ============================================
echo.

set "PROJECT_DIR=%~dp0"
set "VENV_DIR=%PROJECT_DIR%.venv"
set "PYTHON=%VENV_DIR%\Scripts\python.exe"
set "PIP=%VENV_DIR%\Scripts\pip.exe"
set "STREAMLIT=%VENV_DIR%\Scripts\streamlit.exe"

if not exist "%VENV_DIR%" (
    echo [1/4] 创建虚拟环境...
    python -m venv "%VENV_DIR%"
    if errorlevel 1 (
        echo 错误: 无法创建虚拟环境，请确保已安装 Python 3.10+
        pause
        exit /b 1
    )
)

if not exist "%STREAMLIT%" (
    echo [2/4] 安装基础依赖（积分系统）...
    "%PYTHON%" -m pip install -r "%PROJECT_DIR%requirements.txt"
    if errorlevel 1 (
        echo 错误: 基础依赖安装失败
        pause
        exit /b 1
    )
)

echo [3/4] 检查 🎬 AI 视频剪辑（Crayotter）依赖...
"%PYTHON%" -c "import dashscope, langgraph, moviepy, cv2, yt_dlp" 2>nul
if errorlevel 1 (
    echo    首次使用视频剪辑，正在安装完整视频依赖（约数分钟，请耐心等待）...
    "%PYTHON%" -m pip install -r "%PROJECT_DIR%requirements-video.txt"
    if errorlevel 1 (
        echo 警告: 视频依赖安装失败，积分/报价等功能仍可用，🎬 视频剪辑暂时不可用
    )
) else (
    echo    视频剪辑依赖已就绪
)

echo.
echo [4/4] 启动系统...
echo    系统将在浏览器中打开：http://localhost:8501
echo    🎬 AI 视频剪辑板块默认后端监听：127.0.0.1:18765（在页面内点击"启动后端"即可）
echo    按 Ctrl+C 停止运行
echo.

cd /d "%PROJECT_DIR%"
"%STREAMLIT%" run app.py --server.port 8501

pause

@echo off
chcp 65001 >nul
title 电子数据取证工具集成系统 v3.0

echo ============================================================
echo   电子数据取证工具集成系统 v3.0
echo   Forensics Tool Integration Platform
echo ============================================================
echo.

:: 方式1: 打包好的桌面版 exe
if exist "%~dp0..\dist\ForensicsPlatform\ForensicsPlatform.exe" (
    echo [启动] 桌面版 - 原生窗口模式 ...
    start "" "%~dp0..\dist\ForensicsPlatform\ForensicsPlatform.exe"
    goto :done
)

:: 方式2: Python 桌面版
if exist "%~dp0desktop_app.py" (
    echo [启动] 桌面版 - Python 开发模式 ...
    echo.
    echo 正在检查依赖 ...
    C:\Python314\python.exe -c "import fastapi, uvicorn, sqlalchemy, aiosqlite, webview" 2>nul
    if errorlevel 1 (
        echo [警告] 缺少依赖，正在安装 ...
        C:\Python314\python.exe -m pip install -r "%~dp0..\system\requirements.txt" -q
    )
    cd /d "%~dp0.."
    start "" C:\Python314\python.exe "launcher\desktop_app.py"
    goto :done
)

:: 方式3: 浏览器模式
if exist "%~dp0web_launcher.py" (
    echo [启动] 浏览器模式 ...
    echo.
    echo 正在检查依赖 ...
    C:\Python314\python.exe -c "import fastapi, uvicorn, sqlalchemy, aiosqlite" 2>nul
    if errorlevel 1 (
        echo [警告] 缺少依赖，正在安装 ...
        C:\Python314\python.exe -m pip install -r "%~dp0..\system\requirements.txt" -q
    )
    cd /d "%~dp0.."
    start "" C:\Python314\python.exe "launcher\web_launcher.py"
    goto :done
)

echo [错误] 找不到可执行文件
echo        请从 GitHub 克隆: https://github.com/rain-foece/Integration_project
pause
goto :eof

:done
echo.
echo 系统正在启动，桌面窗口将自动打开 ...
timeout /t 3 >nul
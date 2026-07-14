@echo off
chcp 65001 >nul
title 电子数据取证工具集成系统 v3.0

:: 方式1: 打包好的桌面版 exe
if exist "%~dp0..\dist\ForensicsPlatform\ForensicsPlatform.exe" (
    start "" "%~dp0..\dist\ForensicsPlatform\ForensicsPlatform.exe"
    goto :done
)

:: 方式2: Python 桌面版（使用 pythonw.exe 无控制台窗口）
if exist "%~dp0desktop_app.py" (
    C:\Python314\pythonw.exe -c "import fastapi, uvicorn, sqlalchemy, aiosqlite, webview" 2>nul
    if errorlevel 1 (
        C:\Python314\python.exe -m pip install -r "%~dp0..\system\requirements.txt" -q
    )
    cd /d "%~dp0.."
    start "" C:\Python314\pythonw.exe "launcher\desktop_app.py"
    goto :done
)

:: 方式3: 浏览器模式
if exist "%~dp0web_launcher.py" (
    C:\Python314\python.exe -c "import fastapi, uvicorn, sqlalchemy, aiosqlite" 2>nul
    if errorlevel 1 (
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
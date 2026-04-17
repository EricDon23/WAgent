@echo off
chcp 65001 >nul 2>&1
title WAgent AI小说创作系统 v7.0

:: WAgenter.bat - WAgent 启动程序
:: 功能：会话管理 + Agent控制 + 故事创作
:: 版本: 7.0 (2026-04-17)

echo.
echo ============================================================
echo        WAgent AI 小说创作系统 v7.0
echo      会话管理 + Agent控制 + 智能故事生成
echo ============================================================
echo.

:: 优先尝试 conda 中的 Python
if exist "D:\anaconda3\python.exe" (
    set PYTHON_CMD="D:\anaconda3\python.exe"
    echo [INFO] 使用 conda Python: D:\anaconda3\python.exe
) else (
    :: 尝试系统 Python
    where python >nul 2>&1
    if %errorlevel% neq 0 (
        echo [ERROR] 未找到Python环境
        echo 请确保Python已安装并添加到PATH
        echo 或安装 Anaconda: https://www.anaconda.com/
        pause
        exit /b 1
    )
    set PYTHON_CMD=python
)

:: 设置工作目录
cd /d "%~dp0"

:: 启动主程序
%PYTHON_CMD% -u wagent_launcher.py %*

:: 保持窗口（如果出错）
if %errorlevel% neq 0 (
    echo.
    echo [WARNING] 程序异常退出 (错误码: %errorlevel%)
    echo 按任意键退出...
    pause >nul
)

exit /b %errorlevel%

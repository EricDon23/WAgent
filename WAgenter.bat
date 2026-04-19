@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul 2>&1
title WAgent AI 小说创作系统 V3.1

echo.
echo ============================================================
echo        WAgent V3.1 启动器
echo     Redis双向同步 | 分层存储 | 三AI协同创作
echo ============================================================
echo.

cd /d "%~dp0"

set "PYTHON_CMD="

REM 查找Python解释器
if exist "D:\anaconda3\envs\ai_agent\python.exe" (
    set "PYTHON_CMD=D:\anaconda3\envs\ai_agent\python.exe"
) else if exist "D:\anaconda3\envs\TraeAI-8\python.exe" (
    set "PYTHON_CMD=D:\anaconda3\envs\TraeAI-8\python.exe"
) else if exist "%USERPROFILE%\anaconda3\envs\ai_agent\python.exe" (
    set "PYTHON_CMD=%USERPROFILE%\anaconda3\envs\ai_agent\python.exe"
) else if exist "%USERPROFILE%\miniconda3\python.exe" (
    set "PYTHON_CMD=%USERPROFILE%\miniconda3\python.exe"
) else if exist "D:\anaconda3\python.exe" (
    set "PYTHON_CMD=D:\anaconda3\python.exe"
) else (
    for %%p in (python3 python) do (
        where %%p >nul 2>&1
        if !errorlevel! equ 0 (
            set "PYTHON_CMD=%%p"
            goto :found_python
        )
    )
)

:found_python

if "%PYTHON_CMD%"=="" (
    echo.
    echo [错误] 未找到Python解释器!
    echo.
    echo 请尝试以下方法之一:
    echo   1. 安装Anaconda并创建ai_agent环境
    echo   2. 编辑本批处理文件，将PYTHON_CMD设置为你的Python路径
    echo   3. 手动运行: python main.py --help
    echo.
    pause
    exit /b 1
)

echo [信息] Python: %PYTHON_CMD%
echo.

REM 解析命令行参数
if "%~1"=="tower" goto :do_tower
if "%~1"=="check" goto :do_check
if "%~1"=="sync" goto :do_sync
if "%~1"=="test" goto :do_test
if "%~1"=="help" goto :show_help
if "%~1"=="--help" goto :show_help
if "%~1"=="-h" goto :show_help

:show_menu
echo 可用操作:
echo   [直接回车] 启动控制塔模式（默认）
echo   [1] 环境检查
echo   [2] 执行数据同步
echo   [3] 运行测试
echo   [4] 查看帮助信息
echo.

set /p USER_CHOICE=请选择操作 (1-4，默认启动控制塔):

if "%USER_CHOICE%"=="1" goto :do_check
if "%USER_CHOICE%"=="2" goto :do_sync
if "%USER_CHOICE%"=="3" goto :do_test
if "%USER_CHOICE%"=="4" goto :show_help

REM 默认：控制塔模式
goto :do_tower

:do_check
echo.
echo 正在执行环境检查...
echo.
"%PYTHON_CMD%" main.py --check
goto :end

:do_sync
echo.
echo 正在执行数据同步...
echo.
"%PYTHON_CMD%" main.py --sync
goto :end

:do_test
echo.
echo 正在运行测试套件...
echo.
"%PYTHON_CMD%" main.py --test
goto :end

:do_tower
echo.
echo 正在启动控制塔模式...
echo.
"%PYTHON_CMD%" main.py --tower
goto :end

:show_help
echo.
echo ============================================================
echo WAgent V3.1 帮助信息
echo ============================================================
echo.
echo 运行模式:
echo   WAgenter.bat                 控制塔模式（默认）
echo   WAgenter.bat tower           控制塔模式
echo.
echo 环境与同步:
echo   WAgenter.bat check           环境检查
echo   WAgenter.bat sync            数据同步
echo.
echo 测试:
echo   WAgenter.bat test            运行测试
echo.
echo 示例:
echo   WAgenter.bat                 启动控制塔
echo   WAgenter.bat check           环境检查
echo   WAgenter.bat sync            数据同步
echo.
pause
goto :end

:end

if %errorlevel% neq 0 (
    echo.
    echo [错误] 程序异常退出，错误代码: %errorlevel%
    echo 请检查:
    echo   1. 依赖包是否已安装 (%PYTHON_CMD% -m pip install -r requirements.txt)
    echo   2. .env配置文件是否存在且正确
    echo   3. Redis服务是否已启动（可选）
    echo.
    echo 提示: 输入 help 查看完整命令列表
    echo.
    pause
)

exit /b %errorlevel%

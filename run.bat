@echo off
setlocal enabledelayedexpansion

REM Check for required environment variables
set "missing_env_var_flag=0"
for %%A in (DB_USER SQL_DB_PASS REDIS_DB_PASS FROM_EMAIL EMAIL_PASSWORD AES_KEY) do (
    if not defined %%A (
        echo %%A not set. Please set this environment variable and run this script again.
        set "missing_env_var_flag=1"
    )
)

REM If any environment variable is not set, exit
if "!missing_env_var_flag!"=="1" (
    exit /B 1
)

REM Check if Redis is installed
where /Q redis-cli
if errorlevel 1 (
    echo Redis not found. Please install Redis.
    pause
    exit /B 1
)

REM Check if MySQL is installed
where /Q mysql
if errorlevel 1 (
    echo MySQL not found. Please install MySQL.
    pause
    exit /B 1
)

:FindPythonCommand
for %%A in (python python3) do (
    where /Q %%A
    if !errorlevel! EQU 0 (
        set "PYTHON_CMD=%%A"
        goto :Found
    )
)

echo Python not found. Please install Python.
pause
exit /B 1

:Found
%PYTHON_CMD% check_requirements.py requirements.txt
if errorlevel 1 (
    echo Installing missing packages...
    %PYTHON_CMD% -m pip install -r requirements.txt
)
%PYTHON_CMD% main.py
pause

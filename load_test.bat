@echo off
REM Script to run load tests for FastAPI backend
REM Usage: load_test.bat [single|master|worker|health|report]

set MODE=%1
set USERS=%2
set SPAWN_RATE=%3
set MASTER_HOST=%4

if "%USERS%"=="" set USERS=10
if "%SPAWN_RATE%"=="" set SPAWN_RATE=1
if "%MASTER_HOST%"=="" set MASTER_HOST=localhost

REM Run the appropriate load test script
if "%MODE%"=="report" (
    echo Generating load test report...
    python -m app.core.locust_load_test.custom.generate_report --output=load_test_report.html
    echo Report generated: load_test_report.html
) else (
    REM Call the custom load test script
    cd backend
    python -m app.core.locust_load_test.custom.create_test_user
    
    if "%MODE%"=="single" (
        echo Running single-node Locust load test...
        locust -f app/core/locust_load_test/custom/locustfile.py
    ) else if "%MODE%"=="master" (
        echo Running Locust master node with %USERS% users at %SPAWN_RATE% users/sec...
        python -m app.core.locust_load_test.custom.custom_run_distributed_locust --master --users=%USERS% --spawn-rate=%SPAWN_RATE%
    ) else if "%MODE%"=="worker" (
        echo Running Locust worker node connecting to %MASTER_HOST%...
        python -m app.core.locust_load_test.custom.custom_run_distributed_locust --worker --host=%MASTER_HOST%
    ) else if "%MODE%"=="health" (
        echo Checking Locust health...
        python -m app.core.locust_load_test.custom.custom_health_check --json
    ) else (
        echo Usage: load_test.bat [single^|master^|worker^|health^|report] [users] [spawn_rate] [master_host]
        echo   single: Run single-node Locust test
        echo   master: Run Locust master node
        echo   worker: Run Locust worker node
        echo   health: Check Locust health
        echo   report: Generate HTML report from current test
        exit /b 1
    )
)

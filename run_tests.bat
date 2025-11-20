@echo off
REM Test runner script for Nova MME Demo (Windows)

echo Running Nova MME Demo Tests...
echo ================================

REM Check if pytest is installed
pytest --version >nul 2>&1
if errorlevel 1 (
    echo pytest not found. Installing test dependencies...
    pip install -r tests\requirements.txt
)

REM Run tests with coverage
echo.
echo Running unit tests...
pytest tests\unit\ -v --cov=lambda\shared --cov=lambda\embedder --cov-report=term-missing

REM Check exit code
if %errorlevel% equ 0 (
    echo.
    echo All tests passed!
) else (
    echo.
    echo Some tests failed
    exit /b 1
)

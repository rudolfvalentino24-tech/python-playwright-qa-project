@echo off
setlocal

echo ========================================
echo Python / Playwright Jenkins build
echo ========================================

set "PYTHON=C:\Users\rudol\AppData\Local\Python\pythoncore-3.14-64\python.exe"

echo.
echo [1/5] Checking Python...
"%PYTHON%" --version
if errorlevel 1 exit /b %errorlevel%

echo.
echo [2/5] Creating virtual environment...
if not exist ".venv\Scripts\python.exe" (
    "%PYTHON%" -m venv .venv
    if errorlevel 1 exit /b %errorlevel%
)

call .venv\Scripts\activate.bat
if errorlevel 1 exit /b %errorlevel%

echo.
echo [3/5] Installing Python dependencies...
python -m pip install --upgrade pip
if errorlevel 1 exit /b %errorlevel%
python -m pip install -r requirements-test.txt
if errorlevel 1 exit /b %errorlevel%

echo.
echo [4/5] Installing Playwright browsers...
python -m playwright install chromium firefox
if errorlevel 1 exit /b %errorlevel%

echo.
echo [5/5] Running Playwright tests...

if defined TEST_RUN_ID if defined TEST_CASE_IDS (
    echo Test Hub run: %TEST_RUN_ID%
    echo Selected cases: %TEST_CASE_IDS%
    python -m pytest playwright\e2e_bdd\tests --browser_name chrome --tracing on --html=report.html --self-contained-html
) else (
    python -m pytest playwright --browser_name chrome --tracing on --html=report.html --self-contained-html
)

set TEST_EXIT_CODE=%ERRORLEVEL%

exit /b %TEST_EXIT_CODE%

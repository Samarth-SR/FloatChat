@echo off
TITLE FloatChat AI - Startup Script

:: ============================================================================
::  FloatChat AI - Smart Startup Script
:: ============================================================================
:: This script checks for dependencies and then launches the backend and frontend.

:CHECK_OLLAMA
ECHO.
ECHO ==================================================
ECHO  Step 1: Checking for the Ollama Application...
ECHO ==================================================
ECHO.
ECHO This script needs the main Ollama application to be running in the background.
ECHO Checking for "ollama.exe" process...
ECHO.

:: Use tasklist to find the ollama.exe process. The "> nul" hides the command's output.
tasklist | findstr /i "ollama.exe" > nul

:: Check the result. %errorlevel% is 0 if findstr found a match, 1 if it didn't.
if %errorlevel% neq 0 (
    ECHO [ERROR] Ollama is not running!
    ECHO.
    ECHO Please do the following:
    ECHO   1. Find and start the "Ollama" application on your computer.
    ECHO   2. Wait for its icon to appear in your system tray (by the clock).
    ECHO   3. Come back to this window and press any key to check again.
    ECHO.
    PAUSE
    GOTO CHECK_OLLAMA
)

ECHO [SUCCESS] Ollama is running. Proceeding to the next step.
ECHO.
timeout /t 2 /nobreak > nul

:CHECK_FILES
ECHO ==================================================
ECHO  Step 2: Verifying required project files...
ECHO ==================================================
ECHO.

if not exist backend.py (
    ECHO [ERROR] Critical file not found: "backend.py"
    ECHO Please make sure this script is in the same folder as your Python files.
    PAUSE
    exit /b
)
if not exist streamlit_floatAI.py (
    ECHO [ERROR] Critical file not found: "streamlit_floatAI.py"
    ECHO Please make sure this script is in the same folder as your Python files.
    PAUSE
    exit /b
)

ECHO [SUCCESS] All required files are present.
ECHO.
timeout /t 2 /nobreak > nul

:LAUNCH_APPS
ECHO ==================================================
ECHO  Step 3: Launching the applications...
ECHO ==================================================
ECHO.
ECHO Starting the Backend Server in a new window...
ECHO This window must remain open.
ECHO.

:: The "start" command opens a new window. "cmd /k" keeps it open.
start "FloatChat Backend" cmd /k python backend.py

ECHO Waiting for 5 seconds to let the backend initialize...
timeout /t 5 /nobreak > nul
ECHO.

ECHO Starting the Streamlit Frontend in a new window...
ECHO This will open the user interface in your browser.
ECHO.
start "FloatChat Frontend" cmd /k streamlit run streamlit_floatAI.py

ECHO.
ECHO ==================================================
ECHO  All Done!
ECHO ==================================================
ECHO.
ECHO Your backend and frontend are starting in new windows.
ECHO You can close this startup window now.
ECHO.
PAUSE
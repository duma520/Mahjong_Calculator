@echo off
rem ---------------------------------------------------------------
rem  Nuitka build script for  Mahjong Calculator  (PySide6 / Qt6)
rem  ASCII only. Chinese data paths are handled by Python.
rem  Build: python -m nuitka --standalone --enable-plugin=pyside6
rem  Output: build_output\mahjong_gui.dist\  (ship the whole folder)
rem ---------------------------------------------------------------
setlocal
cd /d "%~dp0"

set "PY=D:\Program Files\Python310\python.exe"
if not exist "%PY%" set "PY=python"

echo.
echo === Building Mahjong Calculator (Nuitka) ===
echo Python : %PY%
echo Workdir: %CD%
echo.

"%PY%" -u "_scaffold\build_exe.py"
set RC=%ERRORLEVEL%

echo.
if not "%RC%"=="0" (
    echo *** BUILD FAILED *** exit code = %RC%
) else (
    echo *** BUILD OK ***  ->  build_output\mahjong_gui.dist\
)
echo.
pause
exit /b %RC%

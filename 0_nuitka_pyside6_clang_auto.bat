@echo off
rem ---------------------------------------------------------------
rem  Nuitka build script for  Mahjong Calculator  (PySide6 / Qt6)
rem  ASCII only. Chinese data paths are handled by Python.
rem  Build: python -m nuitka --standalone --enable-plugin=pyside6
rem  Output: build_output\Mahjong_Calculator\  (ship the whole folder)
rem  All data files (icon / tiles / rules json / voice clips) are listed
rem  in _scaffold\build_exe.py -- edit there, not here.
rem  Dry run (no actual compile):  set EM_SKIP_BUILD=1
rem ---------------------------------------------------------------
setlocal
cd /d "%~dp0"

rem Use the python on PATH (no hard-coded install path).
set "PY=python"

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
    echo *** BUILD OK ***  -^>  build_output\Mahjong_Calculator\
)
echo.
pause
exit /b %RC%

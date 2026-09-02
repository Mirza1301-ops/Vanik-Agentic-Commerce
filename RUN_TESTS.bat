@echo off
REM Double-click this file to run the 26 rule tests.
REM It finds Python on its own, so PATH does not need to be set up.

setlocal enabledelayedexpansion
cd /d "%~dp0"
chcp 65001 >nul
title Vanik - rule tests

echo.
echo   Looking for Python...

set "PY="

REM 1. The py launcher, which ships with every python.org install.
for /f "delims=" %%i in ('py -3 -c "import sys;print(sys.executable)" 2^>nul') do set "PY=%%i"

REM 2. Whatever "python" points at, if it is a real Python and not the
REM    Microsoft Store placeholder.
if not defined PY (
  for /f "delims=" %%i in ('python -c "import sys;print(sys.executable)" 2^>nul') do set "PY=%%i"
)

REM 3. A per-user install that was never added to PATH. This is the common case.
if not defined PY (
  for /d %%D in ("%LOCALAPPDATA%\Programs\Python\Python3*") do (
    if exist "%%D\python.exe" set "PY=%%D\python.exe"
  )
)

REM 4. A machine-wide install.
if not defined PY (
  for /d %%D in ("C:\Program Files\Python3*") do (
    if exist "%%D\python.exe" set "PY=%%D\python.exe"
  )
)

if not defined PY (
  echo.
  echo   Python was not found on this computer.
  echo.
  echo   Install it from https://www.python.org/downloads/
  echo   On the installer's first screen, tick "Add python.exe to PATH"
  echo   at the bottom before clicking Install.
  echo.
  echo   Then double-click this file again.
  echo.
  pause
  exit /b 1
)

echo   Found: !PY!
echo.

"!PY!" tests.py

echo.
if errorlevel 1 (
  echo   Some tests failed. The lines above say which.
) else (
  echo   All tests passed.
  echo.
)
echo.
pause

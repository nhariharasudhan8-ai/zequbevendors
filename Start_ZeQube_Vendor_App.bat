@echo off
setlocal
cd /d "%~dp0"
set "PYTHONHOME=%~dp0runtime"
if exist "%~dp0runtime\python.exe" (
  "%~dp0runtime\python.exe" "%~dp0app.py"
) else (
  echo The app runtime is missing. Extract the complete app folder from the ZIP first.
  pause
)

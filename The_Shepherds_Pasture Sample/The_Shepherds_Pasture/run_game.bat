@echo off
setlocal
cd /d "%~dp0"
title The Shepherd's Pasture - Python Game Server
where py >nul 2>nul
if %errorlevel%==0 (
  py -3 game_server.py
) else (
  python game_server.py
)
if errorlevel 1 (
  echo.
  echo Could not start the game. Install Python 3.9 or newer and try again.
  pause
)
endlocal

@echo off
title Eve Agent V2 Unleashed — Web Terminal
cd /d "%~dp0"
echo.
echo   ████ EVE V2 UNLEASHED ████
echo   Starting server...
echo   Waiting for server to be ready...
echo.
start /b python eve_server.py
timeout /t 6 /nobreak > nul
echo   Opening http://localhost:7777
start http://localhost:7777
echo.
echo   Server running. Press Ctrl+C to stop.
echo.
cmd /k

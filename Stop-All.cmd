@echo off
REM CampusGuide - stop everything started by Start-All.cmd
cd /d %~dp0
var\pgsql\bin\pg_ctl.exe -D var\pgdata stop -m fast
taskkill /FI "WINDOWTITLE eq CampusGuide*" /F >nul 2>&1
for /f "tokens=5" %%p in ('netstat -ano ^| findstr ":8200 " ^| findstr LISTENING') do taskkill /PID %%p /F >nul 2>&1
for /f "tokens=5" %%p in ('netstat -ano ^| findstr ":8201 " ^| findstr LISTENING') do taskkill /PID %%p /F >nul 2>&1
for /f "tokens=5" %%p in ('netstat -ano ^| findstr ":8109 " ^| findstr LISTENING') do taskkill /PID %%p /F >nul 2>&1
echo Stopped.
pause

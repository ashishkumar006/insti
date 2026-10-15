@echo off
REM CampusGuide - start everything (double-click). Runs outside any sandbox so Postgres backends survive.
cd /d %~dp0
set OLLAMA_URL=http://127.0.0.1:11434
set PAYGO_CHAT_MODEL=gemini-3.5-flash-lite
if not exist var\logs mkdir var\logs
echo [1/2] Postgres (first run initializes data dir + role + db)...
if not exist var\pgdata\PG_VERSION var\pgsql\bin\initdb.exe -D var\pgdata -U postgres -A trust -E UTF8 --locale=C
start "CampusGuide Postgres" /min var\pgsql\bin\pg_ctl.exe -D var\pgdata -l var\logs\pg.log -w -t 60 start
timeout /t 10 /nobreak >nul
var\pgsql\bin\psql.exe -h 127.0.0.1 -p 5432 -U postgres -c "CREATE ROLE campus LOGIN PASSWORD 'campus' SUPERUSER" 2>nul
var\pgsql\bin\psql.exe -h 127.0.0.1 -p 5432 -U postgres -c "CREATE DATABASE campusguide OWNER campus" 2>nul
echo [2/2] API :8200 (student + admin)...
start "CampusGuide API" /min python -u -m uvicorn app.main:app --host 127.0.0.1 --port 8200
echo.
echo Open:  http://127.0.0.1:8200/student   http://127.0.0.1:8200/admin
echo Health: http://127.0.0.1:8200/api/v1/health  (postgres should say ok; first boot creates tables + admin from .env)
pause

@echo off
chcp 65001 >nul
cd /d "%~dp0"

for /f %%i in ('powershell -NoProfile -Command "Get-Date -Format yyyy-MM-dd_HH-mm"') do set TS=%%i

for /f %%i in ('git status --porcelain') do set HAS_CHANGES=1
if not defined HAS_CHANGES (
  echo No changes. Nothing to commit.
  pause
  exit /b
)

git add -A
git commit -m "auto: %TS%"
git push

pause

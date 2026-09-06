@echo off
chcp 65001 >nul
cd /d "%~dp0"

REM git commit --amend --no-edit
REM git cat-file -s "HEAD:bakusai_db/Bakusai_New_search.db"

git fetch origin
git reset --soft origin/main
git add -A
git commit -m "auto: 2026-09-06_21-13"
git cat-file -s "HEAD:bakusai_db/Bakusai_New_search.db"
git push origin main

pause

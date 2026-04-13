@echo off
setlocal

pushd "%~dp0"

for /f "usebackq delims=" %%F in (`uv run python -m database.restore --print-input`) do set "LATEST_BACKUP=%%F"

if not defined LATEST_BACKUP (
    echo No backup files were found in "backup_db".
    popd
    exit /b 1
)

echo Database restore will use:
echo %LATEST_BACKUP%
echo.
pause

uv run python -m database.restore --input "%LATEST_BACKUP%" --yes
set "RESTORE_EXIT=%ERRORLEVEL%"

popd
exit /b %RESTORE_EXIT%
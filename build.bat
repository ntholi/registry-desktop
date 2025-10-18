@echo off
echo.
echo ============================================
echo Building Limkokwing Registry Executable
echo ============================================
echo.

where uv >nul 2>nul
if errorlevel 1 (
    echo Error: uv package manager not found. Please install uv first.
    exit /b 1
)

echo Cleaning previous builds...
if exist dist rmdir /s /q dist
if exist build rmdir /s /q build
if exist "Limkokwing Registry.spec" del "Limkokwing Registry.spec"

echo Building executable...
uv run pyinstaller registry.spec --distpath dist --workpath build

if errorlevel 1 (
    echo.
    echo Error: PyInstaller build failed!
    exit /b 1
)

echo.
echo ============================================
echo Build completed successfully!
echo ============================================
echo.
echo Executable location: dist\Limkokwing Registry\
echo.
echo To run the application, execute:
echo   dist\Limkokwing Registry\Limkokwing Registry.exe
echo.

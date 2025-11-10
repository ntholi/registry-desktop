import shutil
import subprocess
import sys
from pathlib import Path


def get_version() -> str:
    pyproject_path = Path("pyproject.toml")
    try:
        import tomllib

        with open(pyproject_path, "rb") as f:
            pyproject = tomllib.load(f)
            return pyproject.get("project", {}).get("version", "unknown")
    except Exception:
        return "unknown"


def main():
    version = get_version()

    if len(sys.argv) > 1 and sys.argv[1] in ["--onefile", "-f"]:
        build_mode = "onefile"
        spec_file = "registry-onefile.spec"
    else:
        build_mode = "onefolder"
        spec_file = "registry.spec"

    print()
    print("=" * 50)
    print("  Building Limkokwing Registry Executable")
    print("=" * 50)
    print()

    if shutil.which("uv") is None:
        print("Error: uv package manager not found. Please install uv first.")
        sys.exit(1)

    print(f"Version:     {version}")
    print(f"Build mode:  {build_mode}")
    print(f"Spec file:   {spec_file}")
    print()

    print("Cleaning previous builds...")
    for dir_name in ["dist", "build"]:
        dir_path = Path(dir_name)
        if dir_path.exists():
            try:
                shutil.rmtree(dir_path)
            except PermissionError:
                print(
                    f"Warning: Could not delete {dir_name}. Please close the application and try again."
                )
                sys.exit(1)

    auto_spec = Path("Limkokwing Registry.spec")
    if auto_spec.exists():
        auto_spec.unlink()

    print("Building executable with PyInstaller...")
    print()
    result = subprocess.run(
        [
            "uv",
            "run",
            "pyinstaller",
            spec_file,
            "--distpath",
            "dist",
            "--workpath",
            "build",
        ],
        capture_output=False,
    )

    if result.returncode != 0:
        print()
        print("=" * 50)
        print("  ERROR: PyInstaller build failed!")
        print("=" * 50)
        sys.exit(1)

    exe_name = "registry-desktop"
    print()
    print("=" * 50)
    print("  Build completed successfully!")
    print("=" * 50)
    print()

    if build_mode == "onefile":
        print(f"Single executable: dist\\{exe_name}.exe")
        print()
        print("To run the application:")
        print(f"  dist\\{exe_name}.exe")
        print()
        print("Note: The executable will extract files to a temporary")
        print("      directory on first run (startup may take a few seconds).")
    else:
        print(f"Distribution folder: dist\\{exe_name}\\")
        print()
        print("To run the application:")
        print(f"  dist\\{exe_name}\\{exe_name}.exe")
        print()
        print("Note: Distribute the entire folder to preserve functionality.")

    print()
    print("Build options:")
    print("  python build.py           - One-folder (faster, easier to debug)")
    print("  python build.py --onefile - Single .exe (portable, slower startup)")
    print()


if __name__ == "__main__":
    main()

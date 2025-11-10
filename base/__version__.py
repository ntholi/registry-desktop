import tomllib
from pathlib import Path


def get_version() -> str:
    pyproject_path = Path(__file__).parent.parent / "pyproject.toml"
    try:
        with open(pyproject_path, "rb") as f:
            pyproject = tomllib.load(f)
            return pyproject.get("project", {}).get("version", "unknown")
    except Exception:
        return "unknown"


__version__ = get_version()

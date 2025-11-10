# Registry Desktop

Registry Desktop is a wxPython-based desktop application for syncing data between [Registry Portal](https://github.com/ntholi/registry-web) and a legacy web CMS used by Limkokwing University.

## Key points

- Language: Python 3.12+
- UI: wxPython (>= 4.2.0)
- Package manager: `uv` (project uses `pyproject.toml`)
- Database: SQLAlchemy models with PostgreSQL; local development uses local PostgreSQL; production uses Neon PostgreSQL via environment variables

## Quickstart

1. Ensure Python 3.12 is installed.
2. Install project dependencies with the `uv` package manager (project uses `pyproject.toml`).
3. Run the app:

   uv run main.py

Environment variables:

- `DATABASE_ENV` — set to "local" or "remote" to choose database
- `DATABASE_LOCAL_URL` — PostgreSQL connection string for local development (e.g., `postgresql://dev:111111@localhost:5432/registry`)
- `DATABASE_REMOTE_URL` — PostgreSQL connection string for production (Neon database)
- `DESKTOP_ENV` — set to "dev" or "prod" (when "prod", uses remote database)

## Project layout (high level)

- `main.py` — application entry point
- `base/` — shared utilities, browser/session handling, UI helpers
- `database/` — SQLAlchemy connection and models
- `features/` — feature modules (sync, students, modules, structures, etc.)
- `samples/pages/` — sample CMS pages used for scraper development
- `tests/` — unit tests

## Running tests

Run tests with pytest:

   python -m pytest tests

## Packaging

Build helpers and PyInstaller spec files are included (`registry.spec`, `registry-onefile.spec`). There is also a `build.bat` and `build.py` for convenience.

## Notes

- The project stores browser session state and supports automated login and scraping workflows.
- See `base/browser.py` and the `features/sync` features for examples of the sync workflow.

## License

See repository license or ask the project owner for licensing details.

# Registry Desktop - AI Coding Agent Instructions

## Project Overview

PySide6-based desktop application for Limkokwing University Registry management. Syncs student/module data between the database and legacy web-based CMS using web scraping and form automation.

## Technology Stack

- **Python**: 3.12+ (strict requirement, see `.python-version`)
- **UI Framework**: PySide6 (Qt for Python) >=6.10.0
- **Package Manager**: `uv` (modern Python package manager, replaces pip/poetry)
- **Database**: SQLAlchemy ORM with Turso (remote) or local SQLite
- **Web Automation**: Selenium (login), Requests + BeautifulSoup (scraping/posting)

## Development Workflows

### Package Management

- Add dependencies: `uv add <package>`
- Run application: `uv run main.py`
- Dependencies auto-sync via `pyproject.toml`

### Database Connection

- Local: Uses `../registry-web/local.db` (sibling project)
- Production: Turso database via `TURSO_DATABASE_URL` and `TURSO_AUTH_TOKEN` env vars
- Connection configured in `database/connection.py` with `get_engine(use_local=bool)`

### Web Scraping Authentication

- Browser singleton (`base/browser.py`) manages persistent session via `session.pkl`
- Session cookies persisted across app restarts
- Auto re-login on session expiration (checks for login form redirect)

## Architecture Patterns

### Main Application Structure

- `main.py`: Single `MainWindow` with `QStackedWidget` for view switching
- `base/nav/menu.json`: Defines accordion navigation structure
- Action names (e.g., `sync_students`) map to view instances in `MainWindow.views` dict

### Feature Organization

```
features/<category>/<feature>/
  - <feature>_view.py   # PySide6 UI (inherits QWidget) or view/<multiple files>.py
  - service.py          # Business logic
  - repository.py       # Database operations (SQLAlchemy)
  - scraper.py          # Web scraping (BeautifulSoup)
```

### Data Flow Patterns

**Pull (Web → DB)**:

1. `StudentsView` → `PullStudentsWorker` (QThread)
2. Worker calls `StudentSyncService.pull_student(std_no)`
3. Service calls `scraper.scrape_student_data(std_no)` → parses HTML tables
4. Service calls `repository.update_student(std_no, data)` → saves to DB
5. Progress signals update `StatusBar` via `status_bar.show_progress(msg, current, total)`

**Push (DB → Web)**:

1. `StudentsView` shows `StudentFormDialog` for editing
2. `PushStudentsWorker` calls `StudentSyncService.push_student(std_no, data)`
3. Service fetches edit form, extracts hidden inputs via `get_form_payload(form)`
4. Service POSTs updated data, checks for "Successful" in response
5. If successful, updates DB via repository

### Threading

- Long-running tasks use `QThread` workers (e.g., `PullStudentsWorker`, `PushStudentsWorker`)
- Workers emit `progress`, `finished`, `error` signals
- UI connects signals to update `StatusBar` and show completion dialogs
- Workers have `should_stop` flag for cancellation

### Database Models

- `database/models.py`: 40+ SQLAlchemy models (students, programs, modules, enrollments, etc.)
- Use `SafeDateTime` custom type for ISO string ↔ datetime conversion (Turso compatibility)
- Foreign keys cascade on delete (`ondelete="CASCADE"`)
- Models mirror shared schema with `registry-web` sibling project

### Logging

- `base.get_logger(__name__)` returns configured logger
- Format: `"%(asctime)s [%(levelname)s] %(name)s: %(message)s"`
- Use in scrapers/services for debugging scraping/sync operations

## UI Conventions

- **Minimal styling**: Rely on native Qt widgets, avoid custom CSS, and avoid setting colors because the app uses system themes and custom themes.
- **Separation**: Use `QFrame.HLine` separators between logical sections
- **Fonts**: Title=24pt bold, Section=12pt bold, Body=9-10pt
- **Tables**: `QTableWidget` with alternating row colors, stretch columns
- **Status feedback**: All async operations show progress in shared `StatusBar`

## Critical Implementation Details

### Status Bar Updates (MANDATORY)

**ALL browser operations (`Browser.fetch()`, `Browser.post()`) and database operations MUST display progress in the status bar.**

- Views MUST accept `status_bar` parameter and pass to workers/services
- Workers MUST emit `progress` signals with descriptive messages
- Use `status_bar.show_progress(message, current, total)` for operations
- Use `status_bar.show_message(message)` for operations without progress tracking
- Always call `status_bar.clear()` when operations complete (success or failure)

Example in worker:

```python
self.progress.emit(f"Fetching data for {std_no}...", 1, 3)
response = browser.fetch(url)
self.progress.emit(f"Saving {std_no} to database...", 2, 3)
repository.update_student(std_no, data)
```

### Form Scraping Pattern

```python
form = page.select_one("form#form_id")
form_data = get_form_payload(form)  # Extracts all hidden inputs
form_data["x_FieldName"] = new_value  # Override visible fields
response = browser.post(url, form_data)
```

### View Registration

- Add new views to `MainWindow.views` dict with action key matching `menu.json`
- Views MUST accept `status_bar` parameter for progress updates (non-optional for sync operations)

## Environment & Constraints

- **Windows only**: All terminal commands must work in PowerShell v7
- **No documentation generation**: NEVER create/update `.md`, `.txt` files
- **Minimal comments**: Code should be self-documenting
- **No tests**: Project has no testing infrastructure currently

## Key Files Reference

- `main.py`: App entry point, view orchestration
- `base/nav/menu.json`: Navigation structure (add new features here)
- `base/browser.py`: Singleton for web automation (session management, retry logic)
- `database/models.py`: Full schema definitions (reference for queries)
- `database/connection.py`: DB connection factory (local vs. Turso)
- `features/sync/students/`: Complete reference implementation for sync workflows

# Registry Desktop - AI Coding Agent Instructions

## Project Overview

wxPython-based desktop application for Limkokwing University Registry management. Syncs student/module data between the database and legacy web-based system (known as the CMS) scraping and form automation.

## Technology Stack

- **Python**: 3.12+ (strict requirement, see `.python-version`)
- **UI Framework**: wxPython >=4.2.0
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

- `main.py`: Single `wx.Frame` with manual view switching (show/hide panels)
- `base/nav/menu.json`: Defines navigation structure using CustomTreeCtrl
- Action names (e.g., `sync_students`) map to view instances in `MainWindow.views` dict

### Feature Organization

```
features/<category>/<feature>/
  - <feature>_view.py   # wxPython UI (inherits wx.Panel) or view/<multiple files>.py
  - service.py          # Business logic
  - repository.py       # Database operations (SQLAlchemy)
  - scraper.py          # Web scraping (BeautifulSoup)
```

### Data Flow Patterns

**Pull (Web → DB)**:

1. `StudentsView` → `PullStudentsWorker` (threading.Thread)
2. Worker calls `StudentSyncService.pull_student(std_no)`
3. Service calls `scraper.scrape_student_data(std_no)` → parses HTML tables
4. Service calls `repository.update_student(std_no, data)` → saves to DB
5. Progress callbacks update `StatusBar` via `status_bar.show_progress(msg, current, total)`

**Push (DB → Web)**:

1. `StudentsView` shows `StudentFormDialog` for editing
2. `PushStudentsWorker` calls `StudentSyncService.push_student(std_no, data)`
3. Service fetches edit form, extracts hidden inputs via `get_form_payload(form)`
4. Service POSTs updated data, checks for "Successful" in response
5. If successful, updates DB via repository

### Threading

- Long-running tasks use `threading.Thread` with daemon=True
- Workers use callback functions with `wx.CallAfter` for thread-safe UI updates
- Workers have `should_stop` flag for cancellation
- Callbacks receive event_type and args: `callback("progress", message, current, total)`

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

- **Native wxPython**: Use standard wx controls, rely on native platform appearance
- **Separators**: Use `wx.StaticLine` with `wx.LI_HORIZONTAL` or `wx.LI_VERTICAL`
- **Fonts**: Modify via `GetFont()`, set size with `PointSize`, use `Bold()` for emphasis
- **Tables**: `wx.ListCtrl` with `wx.LC_REPORT` style for data grids
- **Status feedback**: All async operations show progress in shared `StatusBar`
- **Threading**: Always use `wx.CallAfter` when updating UI from worker threads

## Critical Implementation Details

### Status Bar Updates (MANDATORY)

**ALL browser operations (`Browser.fetch()`, `Browser.post()`) and database operations MUST display progress in the status bar.**

- Views MUST accept `status_bar` parameter and pass to workers/services
- Workers MUST use callback functions for progress updates
- Use `status_bar.show_progress(message, current, total)` for operations
- Use `status_bar.show_message(message)` for operations without progress tracking
- Always call `status_bar.clear()` when operations complete (success or failure)
- Use `wx.CallAfter` to ensure thread-safe updates

Example in worker:

```python
def run(self):
    self.callback("progress", f"Fetching data for {std_no}...", 1, 3)
    response = browser.fetch(url)
    self.callback("progress", f"Saving {std_no} to database...", 2, 3)
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
- Views MUST accept `parent` parameter (the content panel)
- Views MUST accept `status_bar` parameter for progress updates (non-optional for sync operations)
- All views inherit from `wx.Panel`
- When setting size don't use tuple, use `wx.Size(width, height)`

## Environment & Constraints

- **No comments in source code (ABSOLUTE)**: Never add comments, commented-out code, or explanatory docstrings to source files.

- **No comments in source code (ABSOLUTE)**: Under no circumstances should any model, automated agent, or contributor insert comments into source files. This includes inline comments, block comments, commented-out code, TODO/FIXME comments, or any explanatory notes in code or as docstrings used solely for explanation. All generated code must contain zero comments. This rule is explicit, strict, and non-negotiable.

## Important! Always Fix Errors after you have completed all your changes.

- After completing your code changes, always check for and fix any errors or issues in the code.
- Fix all lint errors and type errors.

## VALIDATION TESTING REQUIRED (MANDATORY)

**DO NOT STOP after making code changes. You MUST validate that fixes work by running the application and testing the specific functionality.**

### Validation Workflow (REQUIRED - NEVER SKIP)
1. **Verify the fix works**: 
   - Check that expected behavior occurs (data is scraped, saved, etc.)
   - Check logs for errors or warnings
   - Confirm no exceptions or database constraint violations
2. **Only stop when verified**: Do NOT end your work until you have confirmed the fix is working
3. **If tests fail**: Debug the issue, make additional fixes, and re-test until working
4. 1. **You may run the application**: `uv run main.py` so that the user can test the functionality manually, and you track the logs to monitor your changes.

## Key Files Reference

- `main.py`: App entry point, view orchestration
- `base/nav/menu.json`: Navigation structure (add new features here)
- `base/browser.py`: Singleton for web automation (session management, retry logic)
- `database/models.py`: Full schema definitions (reference for queries)
- `database/connection.py`: DB connection factory (local vs. Turso)
- `features/sync/students/`: Complete reference implementation for sync workflows
- `samples/pages/`: Sample .php pages from the CMS for reference when scraping/posting (forms, views, etc.)

# Required Codebase Updates for Schema Changes

This document maps all changes required across the codebase following the schema changes in `001_changes.md`.

---

## Priority Legend

| Priority | Meaning |
|----------|---------|
| 🔴 P0 | **CRITICAL** — Will crash at runtime or cause DB errors |
| 🟠 P1 | **HIGH** — Broken functionality, incorrect data |
| 🟡 P2 | **MEDIUM** — Missing new feature support |
| 🟢 P3 | **LOW** — Optional improvements |

---

## 1. 🔴 P0 — StudentCardPrint FK to Removed Table

**Problem**: `StudentCardPrint.receipt_id` has a `ForeignKey("payment_receipts.id")` but the `payment_receipts` table was removed.

**File**: `database/models.py` (lines 1002–1006)

**Current Code**:
```python
receipt_id: Mapped[str] = mapped_column(
    String,
    ForeignKey("payment_receipts.id", ondelete="CASCADE"),
    nullable=False,
)
```

**Fix**: Drop the FK constraint. Make `receipt_id` a plain `String` column:
```python
receipt_id: Mapped[str] = mapped_column(String, nullable=False)
```

---

## 2. 🔴 P0 — StudentSemester.registration_request_id Removed but Still Referenced

**Problem**: `registration_request_id` was removed from the `student_semesters` table, but code still tries to read/write this field on `StudentSemester` objects. This will raise `AttributeError` at runtime.

**Affected Files & Lines**:

| File | Lines | Code |
|------|-------|------|
| `features/enrollments/requests/repository.py` | 450–452 | `existing.registration_request_id = data["registration_request_id"]` |
| `features/enrollments/requests/repository.py` | 477 | `registration_request_id=data.get("registration_request_id")` |
| `features/enrollments/requests/service.py` | ~152 | `"registration_request_id": request_id` passed in data dict |
| `features/enrollments/requests/service.py` | ~190–196 | `"registration_request_id": request_id` passed in data dict |

**Fix**: Remove all `registration_request_id` references from StudentSemester operations. The relationship is now **reversed**: `RegistrationRequest.student_semester_id` → `StudentSemester.id`.

**Migration Logic**:
- When creating/updating a StudentSemester, do NOT set `registration_request_id`
- Instead, after creating/getting the StudentSemester, update the RegistrationRequest with `student_semester_id = student_semester.id`

---

## 3. 🔴 P0 — CMS IDs Used as Primary Keys (Must Migrate to cms_id)

**Problem**: All sync scrapers extract IDs from CMS URLs (e.g., `StructureID=123`) and repositories use them as primary keys (`id=123`). The new schema defines auto-generated `id` fields with separate `cms_id` fields for CMS-sourced values.

### 3a. Scraper Changes — Return `cms_id` Instead of `id`

All scrapers return CMS-sourced IDs under the key `"id"`. These must change to `"cms_id"`.

| File | Function | Current | Required |
|------|----------|---------|----------|
| `features/sync/structures/scraper.py` | `scrape_structures()` | `"id": int(structure_id)` | `"cms_id": int(structure_id)` |
| `features/sync/structures/scraper.py` | `scrape_semesters()` | `"id": int(semester_id)` | `"cms_id": int(semester_id)` |
| `features/sync/structures/scraper.py` | `scrape_semester_modules()` | `"id": int(sem_module_id)` | `"cms_id": int(sem_module_id)` |
| `features/sync/structures/scraper.py` | `scrape_programs()` | `"id": program_id` | `"cms_id": program_id` |
| `features/sync/modules/scraper.py` | `scrape_modules()` | `"id": int(module_id)` | `"cms_id": int(module_id)` |
| `features/sync/modules/scraper.py` | `scrape_all_modules()` | `"id": int(module_id)` | `"cms_id": int(module_id)` |
| `features/sync/students/scraper.py` | `scrape_student_program_data()` | `"id": std_program_id` | `"cms_id": std_program_id` |
| `features/sync/students/scraper.py` | `scrape_student_semester_data()` | `"id": std_semester_id` | `"cms_id": std_semester_id` |
| `features/sync/students/scraper.py` | `scrape_student_module_data()` | `"id": std_module_id` | `"cms_id": std_module_id` |
| `features/sync/students/scraper.py` | `scrape_student_education_data()` | `"id": std_education_id` | `"cms_id": std_education_id` |

**NextOfKin**: No CMS ID extracted from HTML — no change needed.
**ModulePrerequisite**: Not synced from CMS — no change needed.

### 3b. Repository Changes — Lookup by `cms_id`, Auto-Generate `id`

All repositories currently do `Model(id=cms_value, ...)` and `.filter(Model.id == cms_value)`. These must use `cms_id` instead.

#### `features/sync/structures/repository.py`

| Line | Current | Required |
|------|---------|----------|
| ~192 | `School.id == school_id` | `School.cms_id == school_id` |
| ~196 | `School(id=school_id, ...)` | `School(cms_id=school_id, ...)` (let `id` auto-generate) |
| ~212 | `Program.id == program_id` | `Program.cms_id == program_id` |
| ~216 | `Program(id=program_id, ...)` | `Program(cms_id=program_id, ...)` |
| ~234 | `Structure.id == structure_id` | `Structure.cms_id == structure_id` |
| ~238 | `Structure(id=structure_id, ...)` | `Structure(cms_id=structure_id, ...)` |
| ~257 | `StructureSemester.id == semester_id` | `StructureSemester.cms_id == semester_id` |
| ~261 | `StructureSemester(id=semester_id, ...)` | `StructureSemester(cms_id=semester_id, ...)` |
| ~287 | `SemesterModule.id == sem_module_id` | `SemesterModule.cms_id == sem_module_id` |
| ~291 | `SemesterModule(id=sem_module_id, ...)` | `SemesterModule(cms_id=sem_module_id, ...)` |

#### `features/sync/modules/repository.py`

| Line | Current | Required |
|------|---------|----------|
| ~67 | `Module.id == module_id` | `Module.cms_id == module_id` |
| ~72 | `Module(id=module_id, ...)` | `Module(cms_id=module_id, ...)` |

#### `features/sync/students/repository.py`

| Line | Current | Required |
|------|---------|----------|
| ~509 | `StudentProgram.id == int(student_program_id)` | `StudentProgram.cms_id == int(student_program_id)` |
| ~527 | `StudentProgram(id=int(student_program_id), ...)` | `StudentProgram(cms_id=int(student_program_id), ...)` |
| ~611 | `StudentSemester.id == semester_id` | `StudentSemester.cms_id == semester_id` |
| ~632 | `StudentSemester(id=semester_id, ...)` | `StudentSemester(cms_id=semester_id, ...)` |
| ~702 | `StudentModule.id == std_module_id` | `StudentModule.cms_id == std_module_id` |
| ~730 | `StudentModule(id=std_module_id, ...)` | `StudentModule(cms_id=std_module_id, ...)` |
| ~871 | `StudentEducation.id == education_id` | `StudentEducation.cms_id == education_id` |
| ~880 | `StudentEducation(id=education_id, ...)` | `StudentEducation(cms_id=education_id, ...)` |

### 3c. FK Resolution — Must Resolve Auto-Generated IDs for Child Records

**Critical**: When a child record references a parent via FK, the FK value must be the **auto-generated `id`**, not the `cms_id`. After migrating parent lookups to `cms_id`, the resolved parent's `.id` (auto-generated) must be used for child FKs.

**Affected FK chains**:

```
School.id (auto) ← Program.school_id
Program.id (auto) ← Structure.program_id
Structure.id (auto) ← StructureSemester.structure_id
                     ← StudentProgram.structure_id
StructureSemester.id (auto) ← StudentSemester.structure_semester_id
                              ← SemesterModule.semester_id
Module.id (auto) ← SemesterModule.module_id
SemesterModule.id (auto) ← StudentModule.semester_module_id
StudentProgram.id (auto) ← StudentSemester.student_program_id
StudentSemester.id (auto) ← StudentModule.student_semester_id
```

**Example correction** in `structures/repository.py`:
```python
# Old: School and Program both used CMS ID as PK
school = School(id=school_id, name=name)  # school_id = CMS ID
Program(id=program_id, school_id=school_id, ...)  # FK = CMS ID (worked because PK was CMS ID)

# New: Must resolve auto-generated ID
school = session.query(School).filter(School.cms_id == school_id).first()
if not school:
    school = School(cms_id=school_id, name=name)
    session.add(school)
    session.flush()  # Generate auto ID
Program(cms_id=program_id, school_id=school.id, ...)  # FK = auto-generated ID
```

**Files requiring FK resolution updates**:
- `features/sync/structures/repository.py` — School→Program→Structure→StructureSemester→SemesterModule chain
- `features/sync/students/repository.py` — StudentProgram, StudentSemester, StudentModule chains
- `features/sync/students/repository.py` — `lookup_structure_semester_id()` at ~line 923 already uses composite lookup (structure_id + semester_number) which returns `.id` — this will return auto-generated ID ✅

### 3d. Service Layer Changes

Services pass CMS IDs between scrapers and repositories. These need to adapt to the new ID scheme.

| File | Impact |
|------|--------|
| `features/sync/structures/service.py` | Passes scraper IDs to repository — may need to use `cms_id` key |
| `features/sync/students/service.py` | Passes `data["id"]` to repository functions as positional param — rename to `data["cms_id"]` |
| `features/sync/modules/service.py` | Same pattern |

### 3e. Existing Data — `id` Columns Currently Hold CMS Values

**Existing database records have CMS IDs stored in the `id` column**. When the schema changes auto-generate new `id` values, this data will be lost unless migrated.

**Data migration required**:
1. Copy existing `id` values to `cms_id` for all affected tables
2. Let the database auto-assign new `id` values (or keep existing as-is if compatible with auto-increment)
3. Update all FK references to point to new auto-generated `id` values

**This is a one-time migration that must happen before deploying the code changes.**

---

## 4. 🟠 P1 — Soft-Delete Support for RegistrationRequest

**Problem**: `RegistrationRequest` now has `deleted_at` and `deleted_by` fields for soft-delete support, but no code filters out soft-deleted records or sets these fields.

### 4a. Query Filtering — Exclude Soft-Deleted Records

**File**: `features/enrollments/requests/repository.py`

Every query that fetches `RegistrationRequest` records must add:
```python
.filter(RegistrationRequest.deleted_at == None)
```

**Affected methods** (all SELECT queries in repository):
- `fetch_registration_requests()` — main list query
- `get_registration_request()` — single record lookup
- `get_registration_request_modules()` — modules for a request
- Any other method that queries RegistrationRequest

### 4b. Soft-Delete Implementation

**Files**: `features/enrollments/requests/repository.py` and/or `service.py`

Add a method to soft-delete instead of hard-delete:
```python
def soft_delete_request(self, request_id: int, deleted_by: str):
    request.deleted_at = datetime.utcnow()
    request.deleted_by = deleted_by
```

### 4c. Removed Unique Constraint

The `UniqueConstraint("std_no", "term_id")` was removed from `registration_requests` to support soft-deletes (multiple records for same student/term, only one active).

**Impact**: Code that catches unique constraint violations for duplicate (std_no, term_id) pairs will no longer trigger. Verify that the application logic handles duplicates correctly without the DB constraint.

---

## 5. 🟡 P2 — Student.national_id Now Nullable

**Problem**: `Student.national_id` changed from `String, nullable=False` to `Text, nullable=True`.

**File**: `features/sync/students/repository.py` (line ~327)

**Current Code**:
```python
national_id=data.get("national_id") or "",
```

**Assessment**: This code uses `or ""` which sets empty string instead of `None`. With `nullable=True`, it would be better to allow `None`:
```python
national_id=data.get("national_id"),
```

**Risk**: Low — the `or ""` pattern still works with nullable fields but wastes storage with empty strings when `None` is more semantically correct.

---

## 6. 🟡 P2 — New Fields Not Yet Populated

### 6a. `students.zoho_contact_id` and `students.photo_key`

**No code currently sets these fields.** They are nullable so no immediate breakage, but any feature that needs them will need scraper/service updates.

### 6b. `schools.short_name`

**No code currently sets this field.** May need to be scraped from CMS or set manually.

### 6c. `documents.file_url`

**No code currently sets this field.** The old `std_no` FK was removed and `file_url` was added instead.

---

## 7. 🟡 P2 — PermissionPreset Model Usage

**Problem**: `PermissionPreset` model exists and `User.preset_id` FK references it, but no feature code interacts with this table.

**Impact**: No breakage. The field is nullable (`ondelete=SET NULL`). If permission presets are managed from the web app, this may be read-only from the desktop app.

**Potential update**: If the desktop app needs to display user permission info, add preset lookup logic.

---

## 8. 🟡 P2 — GraduationRequest.graduation_date_id (New Required FK)

**Problem**: `graduation_date_id` is a **non-nullable** FK to `graduation_dates.id` added to `GraduationRequest`.

**Current impact**: No feature code creates `GraduationRequest` records in the desktop app, so no immediate breakage. If this feature is added later, the field must be provided.

---

## Summary — Files Requiring Changes

### Must Fix (P0)

| File | Changes |
|------|---------|
| `database/models.py` | Drop `payment_receipts` FK on `StudentCardPrint.receipt_id` |
| `features/enrollments/requests/repository.py` | Remove `registration_request_id` on StudentSemester; reverse relationship via `student_semester_id` |
| `features/enrollments/requests/service.py` | Remove `registration_request_id` from data dicts passed to StudentSemester operations |
| `features/sync/structures/scraper.py` | Return `cms_id` instead of `id` in all scrape functions |
| `features/sync/structures/repository.py` | Lookup by `cms_id`; stop setting `id=cms_value`; resolve FKs via auto-generated IDs |
| `features/sync/modules/scraper.py` | Return `cms_id` instead of `id` |
| `features/sync/modules/repository.py` | Lookup by `cms_id`; stop setting `id=cms_value` |
| `features/sync/students/scraper.py` | Return `cms_id` instead of `id` in all scrape functions |
| `features/sync/students/repository.py` | Lookup by `cms_id`; stop setting `id=cms_value`; resolve FKs via auto-generated IDs; remove `registration_request_id` on StudentSemester |
| `features/sync/students/service.py` | Pass `cms_id` instead of `id` to repository functions |
| `features/sync/structures/service.py` | Pass `cms_id` instead of `id` to repository functions |
| `features/sync/modules/service.py` (if exists) | Pass `cms_id` instead of `id` to repository functions |

### Should Fix (P1)

| File | Changes |
|------|---------|
| `features/enrollments/requests/repository.py` | Add `deleted_at == None` filter to all RegistrationRequest queries |
| `features/enrollments/requests/repository.py` or `service.py` | Add soft-delete method for RegistrationRequest |

### Nice to Have (P2)

| File | Changes |
|------|---------|
| `features/sync/students/repository.py` | Allow `national_id=None` instead of empty string |
| Various | Populate new fields: `zoho_contact_id`, `photo_key`, `short_name`, `file_url` when data sources available |

---

## Data Migration (One-Time)

Before deploying code changes, run a migration to:

1. **Copy `id` → `cms_id`** for all 12 affected tables (School, Program, Structure, StructureSemester, Module, SemesterModule, StudentProgram, StudentSemester, StudentModule, StudentEducation, NextOfKin, ModulePrerequisite)
2. **Re-sequence `id`** columns to auto-increment if needed
3. **Update all FK references** to point to new auto-generated `id` values
4. **Verify FK integrity** after migration

**Note**: This migration is complex because of the FK chain. Order matters:
1. Migrate parent tables first (School → Program → Structure → StructureSemester → Module → SemesterModule)
2. Then child tables (StudentProgram → StudentSemester → StudentModule, StudentEducation)

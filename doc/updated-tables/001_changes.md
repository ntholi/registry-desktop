# Models.py Database Schema Sync - Change Log

## Tables Removed (not in database)

| Table | Model Class | Reason |
|-------|-------------|--------|
| `verification_tokens` | `VerificationToken` | Table no longer exists in DB |
| `authenticators` | `Authenticator` | Table no longer exists in DB |
| `clearance_audit` | `ClearanceAudit` | Table no longer exists in DB |
| `assessment_marks_audit` | `AssessmentMarksAudit` | Table no longer exists in DB |
| `assessments_audit` | `AssessmentsAudit` | Table no longer exists in DB |
| `student_audit_logs` | `StudentAuditLog` | Table no longer exists in DB |
| `student_module_audit_logs` | `StudentModuleAuditLog` | Table no longer exists in DB |
| `student_program_audit_logs` | `StudentProgramAuditLog` | Table no longer exists in DB |
| `student_semester_audit_logs` | `StudentSemesterAuditLog` | Table no longer exists in DB |
| `payment_receipts` | `PaymentReceipt` | Removed per user request (table restructured) |

## Tables Added

| Table | Model Class | Reason |
|-------|-------------|--------|
| `permission_presets` | `PermissionPreset` | Required by `users.preset_id` FK. Columns: `id` (Text PK), `name` (Text), `role` (Text), `description` (Text, nullable), `created_at`, `updated_at` |

## Literal Types Removed

| Type | Previously Used By |
|------|--------------------|
| `UserPosition` | `User.position` (field removed) |
| `PaymentType` | `PaymentReceipt.payment_type` (table removed) |
| `AssessmentMarksAuditAction` | `AssessmentMarksAudit.action` (table removed) |
| `AssessmentsAuditAction` | `AssessmentsAudit.action` (table removed) |
| `OperationType` | Audit log tables (all removed) |

## Import Changes

- Removed: `Enum` (unused)
- Removed: `PostgreSQLJSON` from `sqlalchemy.dialects.postgresql` (only used by removed tables)

## Table-by-Table Column Changes

### `users` (major restructure - Better Auth migration)

| Change | Column | Details |
|--------|--------|---------|
| REMOVED | `position` | `UserPosition` field no longer in DB |
| REMOVED | `lms_user_id` | Integer field no longer in DB |
| REMOVED | `lms_token` | Text field no longer in DB |
| REMOVED | `emailVerified` | Was `DateTime`, replaced by `email_verified` |
| ADDED | `email_verified` | `Boolean, nullable=False, default=False` |
| ADDED | `preset_id` | `String, FK → permission_presets.id, ondelete=SET NULL, nullable=True` |
| ADDED | `updated_at` | `DateTime, nullable=False, default=utc_now` |
| ADDED | `banned` | `Boolean, nullable=True, default=False` |
| ADDED | `ban_reason` | `Text, nullable=True` |
| ADDED | `ban_expires` | `DateTime, nullable=True` |
| CHANGED | `name` | `nullable=True` → `nullable=False` |
| CHANGED | `email` | `nullable=True` → `nullable=False` |
| CHANGED | `created_at` | `nullable=True` → `nullable=False` |

### `accounts` (complete restructure - Better Auth migration)

| Change | Column | Details |
|--------|--------|---------|
| REMOVED | `type` | No longer in DB |
| REMOVED | `provider` | Was composite PK, replaced by `provider_id` |
| REMOVED | `provider_account_id` | Was composite PK, replaced by `account_id` |
| REMOVED | `expires_at` | Integer, replaced by `access_token_expires_at` |
| REMOVED | `token_type` | No longer in DB |
| REMOVED | `session_state` | No longer in DB |
| ADDED | `id` | `String, primary_key=True` (was composite PK before) |
| ADDED | `account_id` | `String, nullable=False` |
| ADDED | `provider_id` | `String, nullable=False` |
| ADDED | `access_token_expires_at` | `DateTime, nullable=True` |
| ADDED | `refresh_token_expires_at` | `DateTime, nullable=True` |
| ADDED | `password` | `Text, nullable=True` |
| ADDED | `created_at` | `DateTime, nullable=True, default=utc_now` |
| ADDED | `updated_at` | `DateTime, nullable=True` |

### `sessions` (complete restructure - Better Auth migration)

| Change | Column | Details |
|--------|--------|---------|
| REMOVED | `session_token` | Was PK, replaced by `id` + `token` |
| REMOVED | `expires` | Replaced by `expires_at` |
| ADDED | `id` | `String, primary_key=True` |
| ADDED | `token` | `String, unique=True, nullable=False` |
| ADDED | `ip_address` | `Text, nullable=True` |
| ADDED | `user_agent` | `Text, nullable=True` |
| ADDED | `expires_at` | `DateTime, nullable=False` |
| ADDED | `created_at` | `DateTime, nullable=False, default=utc_now` |
| ADDED | `updated_at` | `DateTime, nullable=False, default=utc_now` |
| ADDED | `impersonated_by` | `Text, nullable=True` |

### `students`

| Change | Column | Details |
|--------|--------|---------|
| CHANGED | `national_id` | `String, nullable=False` → `Text, nullable=True` |
| ADDED | `zoho_contact_id` | `Text, nullable=True` |
| ADDED | `photo_key` | `Text, nullable=True` |

### `student_education`

| Change | Column | Details |
|--------|--------|---------|
| ADDED | `cms_id` | `Integer, nullable=True` |

### `next_of_kins`

| Change | Column | Details |
|--------|--------|---------|
| ADDED | `cms_id` | `Integer, nullable=True` |

### `schools`

| Change | Column | Details |
|--------|--------|---------|
| ADDED | `cms_id` | `Integer, nullable=True` |
| ADDED | `short_name` | `Text, nullable=True` |

### `programs`

| Change | Column | Details |
|--------|--------|---------|
| ADDED | `cms_id` | `Integer, nullable=True` |

### `structures`

| Change | Column | Details |
|--------|--------|---------|
| ADDED | `cms_id` | `Integer, nullable=True` |

### `student_programs`

| Change | Column | Details |
|--------|--------|---------|
| ADDED | `cms_id` | `Integer, nullable=True` |

### `structure_semesters`

| Change | Column | Details |
|--------|--------|---------|
| ADDED | `cms_id` | `Integer, nullable=True` |

### `student_semesters`

| Change | Column | Details |
|--------|--------|---------|
| REMOVED | `registration_request_id` | FK to `registration_requests.id` no longer in DB |
| REMOVED INDEX | `fk_student_semesters_registration_request_id` | Associated index removed |
| ADDED | `cms_id` | `Integer, nullable=True` |

### `modules`

| Change | Column | Details |
|--------|--------|---------|
| ADDED | `cms_id` | `Integer, nullable=True` |

### `semester_modules`

| Change | Column | Details |
|--------|--------|---------|
| ADDED | `cms_id` | `Integer, nullable=True` |

### `student_modules`

| Change | Column | Details |
|--------|--------|---------|
| ADDED | `cms_id` | `Integer, nullable=True` |

### `module_prerequisites`

| Change | Column | Details |
|--------|--------|---------|
| ADDED | `cms_id` | `Integer, nullable=True` |

### `registration_requests`

| Change | Column | Details |
|--------|--------|---------|
| ADDED | `deleted_at` | `DateTime, nullable=True` |
| ADDED | `deleted_by` | `String, FK → users.id, ondelete=SET NULL, nullable=True` |
| ADDED | `student_semester_id` | `Integer, FK → student_semesters.id, ondelete=SET NULL, nullable=True` |
| REMOVED | `UniqueConstraint("std_no", "term_id")` | No longer in DB (soft-delete support) |

### `clearance`

| Change | Column | Details |
|--------|--------|---------|
| REMOVED | `email_sent` | Boolean field no longer in DB |

### `graduation_requests`

| Change | Column | Details |
|--------|--------|---------|
| ADDED | `graduation_date_id` | `Integer, FK → graduation_dates.id, ondelete=RESTRICT, nullable=False` |

### `sponsored_students`

| Change | Column | Details |
|--------|--------|---------|
| REMOVED | `confirmed` | Boolean field no longer in DB |

### `student_card_prints`

| Change | Column | Details |
|--------|--------|---------|
| REMOVED | `receipt_no` | `String, unique=True` replaced by `receipt_id` |
| ADDED | `receipt_id` | `String, FK → payment_receipts.id, ondelete=CASCADE, nullable=False` |

### `documents`

| Change | Column | Details |
|--------|--------|---------|
| REMOVED | `std_no` | FK to `students.std_no` no longer in DB |
| REMOVED INDEX | `fk_documents_std_no` | Associated index removed |
| ADDED | `file_url` | `Text, nullable=True` |

## Auth Code Updates (completed)

### `base/auth/repository.py`

| Method | Change |
|--------|--------|
| `create_user()` | `emailVerified=datetime.utcnow()` → `email_verified=True` |
| `create_account()` | `provider` → `provider_id`, `provider_account_id` → `account_id`, removed `type`/`token_type` params, `expires_at: int` → `access_token_expires_at: datetime`, added `id` generation |
| `get_account()` | `provider` → `provider_id`, `provider_account_id` → `account_id` |
| `update_account_tokens()` | Same param renames, `expires_at` → `access_token_expires_at` |
| `create_session()` | `session_token` → `token`, `expires` → `expires_at`, added `id` generation |
| `get_session()` | `session_token` → `token`, `session.expires` → `session.expires_at` |
| `delete_session()` | `session_token` → `token` |
| `get_user_by_session_token()` | Renamed to `get_user_by_token()` |

### `base/auth/session_manager.py`

| Method | Change |
|--------|--------|
| `save_session()` | Param `session_token` → `token`, stored key `"session_token"` → `"token"`, removed `"position"` from stored user data |
| `get_session_token()` | Renamed to `get_token()`, reads `"token"` key |

### `base/auth/login_view.py`

| Change | Details |
|--------|---------|
| `create_account()` call | `provider=` → `provider_id=`, `provider_account_id=` → `account_id=`, removed `token_type=`, `expires_at=int(...)` → `access_token_expires_at=credentials.expiry` |
| `update_account_tokens()` call | Same param renames |
| `save_session()` call | `session.session_token` → `session.token` |

### `main.py`

| Change | Details |
|--------|---------|
| `check_existing_session()` | `SessionManager.get_session_token()` → `SessionManager.get_token()`, `get_user_by_session_token()` → `get_user_by_token()` |

### `base/auth/user_details_dialog.py`

| Change | Details |
|--------|---------|
| Removed Position row | `FlexGridSizer(4, 2, ...)` → `FlexGridSizer(3, 2, ...)`, removed `user.position` display |

### `utils/permissions.py`

| Change | Details |
|--------|---------|
| `can_edit_grades()` | Removed `position == "manager"` check, now admin-only (`role == "admin"`) |
| `get_current_user_position()` | Removed entirely |

## Remaining Codebase Impact Notes

These model changes may still require updating code that references:

1. **Removed models**: `VerificationToken`, `Authenticator`, `ClearanceAudit`, `AssessmentMarksAudit`, `AssessmentsAudit`, `StudentAuditLog`, `StudentModuleAuditLog`, `StudentProgramAuditLog`, `StudentSemesterAuditLog`, `PaymentReceipt`
2. **Removed Literal types**: `UserPosition`, `PaymentType`, `AssessmentMarksAuditAction`, `AssessmentsAuditAction`, `OperationType`
3. **Removed import**: `PostgreSQLJSON`
4. **Changed fields**: `Student.national_id` is now nullable, `StudentCardPrint.receipt_no` → `receipt_id`, `Document.std_no` removed
5. **Removed constraint**: `registration_requests` no longer has unique constraint on `(std_no, term_id)`
6. **Removed columns**: `student_semesters.registration_request_id`, `clearance.email_sent`, `sponsored_students.confirmed`

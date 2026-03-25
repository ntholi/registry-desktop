from sqlalchemy import inspect

from database.connection import get_engine

engine = get_engine()
inspector = inspect(engine)

tables_to_check = [
    "users",
    "accounts",
    "sessions",
    "registration_requests",
    "graduation_requests",
    "student_card_prints",
    "documents",
    "graduation_clearance",
]

for table in tables_to_check:
    print(f"\n=== {table} FKs ===")
    fks = inspector.get_foreign_keys(table)
    for fk in fks:
        print(
            f"  {fk['constrained_columns']} -> {fk['referred_table']}.{fk['referred_columns']} ondelete={fk.get('options', {}).get('ondelete')}"
        )

    print(f"\n=== {table} PKs ===")
    pk = inspector.get_pk_constraint(table)
    print(f"  {pk['constrained_columns']}")

    print(f"\n=== {table} Unique ===")
    uqs = inspector.get_unique_constraints(table)
    for uq in uqs:
        print(f"  {uq['column_names']}")

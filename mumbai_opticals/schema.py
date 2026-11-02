"""Small, additive database changes the app needs. Runs once per process.

Only ever ADDs nullable columns, so existing data is never touched.
"""
from flask import current_app

from . import db

REQUIRED_COLUMNS = [
    # (table, column, definition)
    ('bill_items', 'details', 'TEXT NULL'),               # extra boxes from the bill form (JSON)
    ('bills', 'prescription_details', 'TEXT NULL'),       # prescription rows entered on the bill (JSON)
]

_checked = False


def ensure_schema():
    global _checked
    if _checked:
        return
    _checked = True
    try:
        for table, column, definition in REQUIRED_COLUMNS:
            exists = db.query_value("""
                SELECT COUNT(*) FROM information_schema.COLUMNS
                WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = %s AND COLUMN_NAME = %s
            """, (table, column))
            if not exists:
                db.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
                current_app.logger.warning("Added column %s.%s", table, column)
        db.commit()
    except Exception as e:  # never block the site over this
        current_app.logger.exception("Schema check failed: %s", e)

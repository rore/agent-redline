# Intentional violation: api imports storage directly, bypassing core.
from storage import db


def handle() -> str:
    return db.row()

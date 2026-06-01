# Intentional violation: domain importing from infrastructure.
from sample_pkg.infrastructure import db


def make_order() -> str:
    return db.row()

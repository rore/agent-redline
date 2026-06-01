# Multi-package layout self-test fixture for run-import-linter.py.
#
# Purpose: a minimal Python project where layers are TOP-LEVEL packages
# (no single parent package). Used by tests/extensions/python/check-extension.sh
# to confirm the adapter script handles import-linter's `root_packages` (plural)
# config and produces violations referencing top-level package names.
#
# Layout:
#   api/
#     __init__.py
#     handler.py     <-- intentionally imports from storage (forbidden)
#   core/
#     __init__.py
#     model.py
#   storage/
#     __init__.py
#     db.py
#
# Architecture: api is the topmost layer (may import core, storage),
# core is in the middle, storage is the lowest. core MUST NOT import api;
# storage MUST NOT import core or api. The intentional violation goes the
# OTHER way: storage importing api would be one direction; here we
# instead exercise the more common case — api reaching into storage
# directly when it should go through core. We express that as a
# `forbidden` contract.
#
# Contract type exercised: `layers` across multiple root packages
# (top-level names listed directly), plus a `forbidden` contract for the
# api -> storage shortcut.

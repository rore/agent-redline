# Tiny self-test fixture for run-import-linter.py.
#
# Purpose: a minimal Python package with two layers and one intentional
# violation. Used by tests/extensions/python/check-extension.sh to confirm the
# adapter script:
#   1. Builds an import-linter Report
#   2. Detects the violation
#   3. Emits boundary-violations.json matching the schema
#   4. Returns exit code 1
#
# Layout:
#   sample_pkg/
#     __init__.py
#     domain/
#       __init__.py
#       order.py        <-- intentionally imports from infrastructure
#     infrastructure/
#       __init__.py
#       db.py
#
# Contract: domain may not import from infrastructure (one-way layers).
# domain/order.py violates this on purpose.

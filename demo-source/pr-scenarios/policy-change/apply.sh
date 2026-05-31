#!/usr/bin/env bash
# pr-scenarios/policy-change/apply.sh
#
# Mutates a clean main checkout to edit agent-policy.yaml itself.
# Specifically: raises maxChangedFiles.warn from 20 → 30. The change
# is harmless on its own (a small threshold tweak) but the *act of
# editing the policy* is what should fire the architecture-review
# checkpoint.

set -euo pipefail

POLICY="agent-policy.yaml"
[[ -f "$POLICY" ]] || { echo "error: $POLICY not found" >&2; exit 1; }

python3 <<'PYEOF'
from pathlib import Path
p = Path("agent-policy.yaml")
text = p.read_text(encoding="utf-8")
needle = "  maxChangedFiles:\n    warn: 20\n    fail: 50"
replace = "  maxChangedFiles:\n    warn: 30\n    fail: 50"
if needle in text:
    p.write_text(text.replace(needle, replace), encoding="utf-8")
    print("modified agent-policy.yaml (maxChangedFiles.warn 20 -> 30)")
else:
    print("policy already modified or threshold values changed; nothing to apply")
PYEOF

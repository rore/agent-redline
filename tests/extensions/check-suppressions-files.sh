#!/usr/bin/env bash
# tests/extensions/check-suppressions-files.sh
#
# Validates the production marker-list files against
# core/schema/suppressions.schema.json:
#
#   - core/templates/suppressions.yaml          (stack-neutral defaults)
#   - extensions/<name>/suppressions.yaml       (per-language)
#
# Without this layer, a typo in a shipped marker-list file would only
# surface when an adopter ran into it.
#
# Exit codes:
#   0 — all files valid
#   2 — at least one file failed schema validation

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

exec python - "$REPO_ROOT" <<'PY'
import json
import sys
from pathlib import Path

try:
    import yaml  # type: ignore
except ImportError:
    print("error: PyYAML not installed. pip install pyyaml", file=sys.stderr)
    sys.exit(1)

try:
    from jsonschema import Draft202012Validator  # type: ignore
except ImportError:
    print("error: jsonschema not installed. pip install jsonschema", file=sys.stderr)
    sys.exit(1)

root = Path(sys.argv[1])
schema_path = root / "core" / "schema" / "suppressions.schema.json"
schema = json.loads(schema_path.read_text(encoding="utf-8"))
Draft202012Validator.check_schema(schema)
validator = Draft202012Validator(schema)

targets = [root / "core" / "templates" / "suppressions.yaml"]
targets += sorted((root / "extensions").glob("*/suppressions.yaml"))

if not targets:
    print("error: no suppressions.yaml files found", file=sys.stderr)
    sys.exit(2)

ok = True
for path in targets:
    rel = path.relative_to(root)
    if not path.exists():
        print(f"FAIL {rel}: file not found", file=sys.stderr)
        ok = False
        continue
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as e:
        print(f"FAIL {rel}: YAML parse error: {e}", file=sys.stderr)
        ok = False
        continue
    errors = list(validator.iter_errors(data))
    if errors:
        for e in errors:
            print(f"FAIL {rel}: {e.message} (at {list(e.absolute_path)})", file=sys.stderr)
        ok = False
    else:
        print(f"ok   {rel}")

sys.exit(0 if ok else 2)
PY

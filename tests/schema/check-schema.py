#!/usr/bin/env python3
"""
tests/schema/check-schema.py

Validates every YAML in tests/schema/valid/ against core/schema/agent-policy.schema.json
(must all pass) and every YAML in tests/schema/invalid/ (must all fail).

Exit codes:
  0 — all valid pass and all invalid fail
  1 — script error (missing file, dependency, etc.)
  2 — at least one fixture has the wrong outcome
"""

from __future__ import annotations

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


REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SCHEMA_PATH = REPO_ROOT / "core" / "schema" / "agent-policy.schema.json"
BOUNDARY_SCHEMA_PATH = REPO_ROOT / "core" / "schema" / "boundary-violations.schema.json"
VALID_DIR = REPO_ROOT / "tests" / "schema" / "valid"
INVALID_DIR = REPO_ROOT / "tests" / "schema" / "invalid"
BOUNDARY_VALID_DIR = REPO_ROOT / "tests" / "schema" / "boundary-valid"
BOUNDARY_INVALID_DIR = REPO_ROOT / "tests" / "schema" / "boundary-invalid"


def load_schema(path: Path = SCHEMA_PATH) -> dict:
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def load_yaml(path: Path) -> dict:
    with path.open(encoding="utf-8") as f:
        return yaml.safe_load(f)


def main() -> int:
    if not SCHEMA_PATH.exists():
        print(f"error: schema not found at {SCHEMA_PATH}", file=sys.stderr)
        return 1
    if not BOUNDARY_SCHEMA_PATH.exists():
        print(f"error: schema not found at {BOUNDARY_SCHEMA_PATH}", file=sys.stderr)
        return 1

    schema = load_schema()
    validator = Draft202012Validator(schema)

    boundary_schema = load_schema(BOUNDARY_SCHEMA_PATH)
    # Self-check: the boundary schema must itself be a valid JSON Schema document.
    Draft202012Validator.check_schema(boundary_schema)
    boundary_validator = Draft202012Validator(boundary_schema)

    failures: list[str] = []

    # Additional in-repo policies that should always be valid.
    real_policies = [
        REPO_ROOT / "demo-source" / "agent-policy.yaml",
    ]

    # Valid fixtures: must validate.
    for path in sorted(VALID_DIR.glob("*.yaml")):
        try:
            policy = load_yaml(path)
        except yaml.YAMLError as e:
            failures.append(f"FAIL  {path.relative_to(REPO_ROOT)}: YAML parse error: {e}")
            continue
        errors = list(validator.iter_errors(policy))
        if errors:
            err_lines = "; ".join(f"{e.message} (at {list(e.absolute_path)})" for e in errors)
            failures.append(f"FAIL  {path.relative_to(REPO_ROOT)}: expected valid, got: {err_lines}")
        else:
            print(f"ok    {path.relative_to(REPO_ROOT)} (valid)")

    # Real policies in the repo: must also validate.
    for path in real_policies:
        if not path.exists():
            print(f"skip  {path.relative_to(REPO_ROOT)} (file not present)")
            continue
        try:
            policy = load_yaml(path)
        except yaml.YAMLError as e:
            failures.append(f"FAIL  {path.relative_to(REPO_ROOT)}: YAML parse error: {e}")
            continue
        errors = list(validator.iter_errors(policy))
        if errors:
            err_lines = "; ".join(f"{e.message} (at {list(e.absolute_path)})" for e in errors)
            failures.append(f"FAIL  {path.relative_to(REPO_ROOT)}: expected valid, got: {err_lines}")
        else:
            print(f"ok    {path.relative_to(REPO_ROOT)} (real policy, valid)")

    # Invalid fixtures: must fail.
    for path in sorted(INVALID_DIR.glob("*.yaml")):
        try:
            policy = load_yaml(path)
        except yaml.YAMLError:
            # Parse failure counts as schema invalidity for our purposes.
            print(f"ok    {path.relative_to(REPO_ROOT)} (invalid; YAML parse error)")
            continue
        errors = list(validator.iter_errors(policy))
        if not errors:
            failures.append(f"FAIL  {path.relative_to(REPO_ROOT)}: expected invalid, but passed schema")
        else:
            print(f"ok    {path.relative_to(REPO_ROOT)} (invalid; {len(errors)} schema error(s))")

    # Boundary-violations schema: self-validity already checked above.
    # Now validate boundary-valid/ (must pass) and boundary-invalid/ (must fail) fixtures.
    if BOUNDARY_VALID_DIR.exists():
        for path in sorted(BOUNDARY_VALID_DIR.glob("*.json")):
            try:
                with path.open(encoding="utf-8") as f:
                    instance = json.load(f)
            except json.JSONDecodeError as e:
                failures.append(f"FAIL  {path.relative_to(REPO_ROOT)}: JSON parse error: {e}")
                continue
            errors = list(boundary_validator.iter_errors(instance))
            if errors:
                err_lines = "; ".join(f"{e.message} (at {list(e.absolute_path)})" for e in errors)
                failures.append(f"FAIL  {path.relative_to(REPO_ROOT)}: expected valid, got: {err_lines}")
            else:
                print(f"ok    {path.relative_to(REPO_ROOT)} (boundary-violations valid)")
    if BOUNDARY_INVALID_DIR.exists():
        for path in sorted(BOUNDARY_INVALID_DIR.glob("*.json")):
            try:
                with path.open(encoding="utf-8") as f:
                    instance = json.load(f)
            except json.JSONDecodeError:
                print(f"ok    {path.relative_to(REPO_ROOT)} (boundary-violations invalid; JSON parse error)")
                continue
            errors = list(boundary_validator.iter_errors(instance))
            if not errors:
                failures.append(f"FAIL  {path.relative_to(REPO_ROOT)}: expected invalid, but passed schema")
            else:
                print(f"ok    {path.relative_to(REPO_ROOT)} (boundary-violations invalid; {len(errors)} schema error(s))")

    print()
    if failures:
        for line in failures:
            print(line, file=sys.stderr)
        print(f"\n{len(failures)} fixture(s) had unexpected outcomes.", file=sys.stderr)
        return 2

    print("all schema fixtures behaved as expected.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

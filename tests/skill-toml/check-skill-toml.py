#!/usr/bin/env python3
"""
tests/skill-toml/check-skill-toml.py

Validates every [[tool.importlinter.contracts]] example inside skill markdown
against import-linter's actual contract-type schema. Catches the class of
bug that bit Pallium's bootstrap: skill content using import-linter field
names that don't exist (or missing required ones), so a faithful agent
produces contracts import-linter rejects.

Specifically:
  - acyclic_siblings: requires `ancestors` (Set), NOT `container` (the docs
    used `container` until 2026-06; import-linter 2.x renamed/restructured)
  - forbidden: needs `allow_indirect_imports = true` for the multi-package
    case where one layer legitimately bridges others — without it, every
    contract is unsatisfiable transitively. The check enforces that
    multi-package examples set the flag (a soft policy, not a schema rule).

Discovery:
  Each contract type's required/optional field set is read at runtime from
  import-linter itself (`cls.<field>.required`). This makes the test
  authoritative and self-updating: when import-linter changes a field name
  or requirement, this test catches it without us having to remember.

Skipped:
  - Blocks NOT inside skill markdown's `[tool.importlinter]` namespace.
  - Contract types we don't recognize (custom contracts in extension repos).

Exit codes:
  0 — every contract example matches the schema
  1 — script error (missing import-linter or skill files)
  2 — at least one contract has invalid fields
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent

# Skill files whose TOML contract examples must be schema-valid.
SKILL_FILES = [
    "extensions/jvm-archunit/profile.md",
    "extensions/jvm-archunit/scaffold.md",
    "extensions/python/profile.md",
    "extensions/python/scaffold.md",
]


def load_contract_schemas() -> dict[str, dict]:
    """Return {type_name: {required: set, optional: set}} from import-linter."""
    try:
        from importlinter.contracts.layers import LayersContract
        from importlinter.contracts.forbidden import ForbiddenContract
        from importlinter.contracts.independence import IndependenceContract
        from importlinter.contracts.protected import ProtectedContract
        from importlinter.contracts.acyclic_siblings import AcyclicSiblingsContract
    except ImportError as e:
        print(f"error: import-linter not installed: {e}", file=sys.stderr)
        print("       pip install 'import-linter>=2.0,<3'", file=sys.stderr)
        sys.exit(1)

    schemas: dict[str, dict] = {}
    for cls in (LayersContract, ForbiddenContract, IndependenceContract,
                ProtectedContract, AcyclicSiblingsContract):
        required: set[str] = set()
        optional: set[str] = set()
        for fname in dir(cls):
            ftype = vars(cls).get(fname)
            if ftype is None or not hasattr(ftype, "required"):
                continue
            if ftype.required:
                required.add(fname)
            else:
                optional.add(fname)
        schemas[cls.type_name] = {
            "required": required,
            "optional": optional,
            "all": required | optional,
        }
    return schemas


def extract_toml_blocks(text: str) -> list[tuple[int, str]]:
    """Return (block_index, block_text) for every ```toml fence."""
    pattern = re.compile(r"^```toml\s*\n(.*?)\n```\s*$", re.DOTALL | re.MULTILINE)
    return [(i, m.group(1)) for i, m in enumerate(pattern.finditer(text))]


def parse_contracts(toml_block: str) -> list[dict]:
    """Pull every [[tool.importlinter.contracts]] entry from a TOML block.

    Light parser: this handles `name`, `type`, top-level scalar fields and
    list-shaped fields commonly used (layers, source_modules, etc.). Doesn't
    aim to be a full TOML parser — just enough to read what skill examples
    use. We can't import `tomllib` directly because the blocks are FRAGMENTS
    (no [tool.importlinter] root), and we don't want to pull `tomli` as a
    test dep.
    """
    contracts: list[dict] = []
    # Split by the contract header line; each chunk after the first is one contract.
    chunks = re.split(r"\[\[tool\.importlinter\.contracts\]\]\s*\n", toml_block)
    for chunk in chunks[1:]:
        # End the chunk at the next [[tool.importlinter or [tool.importlinter section.
        chunk = re.split(r"\n\[\[?tool\.importlinter", chunk)[0]
        contract: dict = {}
        for line in chunk.splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            m = re.match(r'^([a-z_]+)\s*=\s*(.+)$', stripped)
            if not m:
                continue
            field = m.group(1)
            value = m.group(2).strip()
            # Mark presence; we don't need to parse value types for this check.
            contract[field] = value
        if "type" in contract:
            contracts.append(contract)
    return contracts


def check_contract(contract: dict, schemas: dict[str, dict]) -> list[str]:
    """Return a list of error messages for this contract; empty if valid."""
    type_value = contract.get("type", "").strip().strip('"').strip("'")
    schema = schemas.get(type_value)
    if schema is None:
        return [f"unknown contract type: {type_value!r}"]

    fields_present = set(contract.keys()) - {"name", "type"}
    errs: list[str] = []

    missing_required = schema["required"] - fields_present
    if missing_required:
        errs.append(
            f"type={type_value} missing required fields: {sorted(missing_required)}"
        )

    unknown_fields = fields_present - schema["all"]
    # `id` is allowed (used by --contract CLI flag), so don't flag it.
    unknown_fields -= {"id"}
    if unknown_fields:
        errs.append(
            f"type={type_value} unknown fields (likely typos or drift): {sorted(unknown_fields)}"
        )

    return errs


def check_multipkg_forbidden_indirect(toml_block: str, contracts: list[dict]) -> list[str]:
    """In multi-package layouts (`root_packages` plural in the same block),
    every `forbidden` contract should set `allow_indirect_imports = true`.

    Without it, transitive imports through a bridging layer (e.g. core
    importing many siblings) make every other forbidden contract
    unsatisfiable. Documented in extensions/python/profile.md but the
    test enforces it on examples — easy to forget when authoring."""
    if not re.search(r"^\s*root_packages\s*=", toml_block, re.MULTILINE):
        return []
    errs: list[str] = []
    for c in contracts:
        type_value = c.get("type", "").strip().strip('"').strip("'")
        if type_value != "forbidden":
            continue
        flag = c.get("allow_indirect_imports", "").strip().strip('"').strip("'").lower()
        if flag != "true":
            name = c.get("name", "<unnamed>").strip().strip('"').strip("'")
            errs.append(
                f"forbidden contract '{name}' in multi-package block "
                "must set `allow_indirect_imports = true` "
                "(transitive imports make multi-package forbidden contracts unsatisfiable)"
            )
    return errs


def main() -> int:
    schemas = load_contract_schemas()

    failures: list[str] = []
    contracts_checked = 0
    files_seen = 0

    for rel in SKILL_FILES:
        path = REPO_ROOT / rel
        if not path.exists():
            print(f"skip  {rel} (file not present)")
            continue
        files_seen += 1
        text = path.read_text(encoding="utf-8")
        for block_idx, block_text in extract_toml_blocks(text):
            # Only check blocks that contain import-linter contracts.
            if "[[tool.importlinter.contracts]]" not in block_text:
                continue
            contracts = parse_contracts(block_text)
            for c_idx, contract in enumerate(contracts):
                contracts_checked += 1
                errs = check_contract(contract, schemas)
                for e in errs:
                    name = contract.get("name", "<unnamed>").strip().strip('"').strip("'")
                    failures.append(
                        f"{rel} block#{block_idx} contract#{c_idx} ({name}): {e}"
                    )
            # Multi-package + forbidden semantics check (block-level).
            for e in check_multipkg_forbidden_indirect(block_text, contracts):
                failures.append(f"{rel} block#{block_idx}: {e}")

    print()
    print(f"scanned {files_seen} skill file(s); {contracts_checked} import-linter contract example(s) validated.")
    if failures:
        for line in failures:
            print(f"FAIL  {line}", file=sys.stderr)
        print(f"\n{len(failures)} contract issue(s).", file=sys.stderr)
        return 2
    print("all import-linter contract examples match the schema.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

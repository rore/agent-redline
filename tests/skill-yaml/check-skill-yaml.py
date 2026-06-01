#!/usr/bin/env python3
"""
tests/skill-yaml/check-skill-yaml.py

Scans every ```yaml fenced block inside skill markdown files (extension
profiles, scaffolds, operating notes, and the core skill files) and
validates each block that LOOKS LIKE an agent-policy fragment against
core/schema/agent-policy.schema.json.

Why this exists: a bootstrap session reads these markdown files and
copies YAML fragments into a real consuming repo's agent-policy.yaml.
If the docs themselves carry schema-invalid examples (missing `reason:`
on a watch entry, missing `description:` on a boundary, unknown `prRules`
keys, etc.), the agent produces a policy that fails schema validation.
That's a real bug that previous tests didn't catch.

A fragment is wrapped in the minimum required top-level fields if it
doesn't already supply them, and any checkpoint referenced by a zone
entry gets a stub `satisfiedBy` so the fragment-under-test isn't
penalized for "missing required" checkpoints whose definition is in
some OTHER block. We're testing the FRAGMENT, not whether it could be
shipped standalone.

Skipped:
- Fences labeled ```yaml-sketch — used for intentionally illustrative
  blocks that contain `...`/`[...]` placeholders. Bootstrap sketches
  the shape; a copying agent must fill values in.
- YAML blocks that don't look like policy fragments (CI workflow YAML,
  shell-step YAML, etc.). The discriminator is a top-level dict with
  agent-policy field names.

Exit codes:
  0 — every policy fragment validates
  1 — script error (missing schema, missing dep)
  2 — at least one fragment failed schema validation or YAML parse
"""

from __future__ import annotations

import json
import re
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

# Skill markdown files whose ```yaml blocks should be checked. These are
# the files an agent actually reads during bootstrap or operating mode.
SKILL_FILES = [
    "extensions/spring-archunit/profile.md",
    "extensions/spring-archunit/scaffold.md",
    "extensions/spring-archunit/operating.md",
    "extensions/python/profile.md",
    "extensions/python/scaffold.md",
    "extensions/python/operating.md",
    "core/skill/agent-redline.md",
    "core/skill/bootstrap-mode.md",
    "core/skill/operating-mode.md",
    "core/templates/AGENTS.md.template",
]

# Agent-policy.yaml field names. A YAML doc with one or more of these as
# top-level keys is a policy fragment worth validating.
POLICY_FRAGMENT_FIELDS = {
    "version", "project", "zones", "boundaries", "api", "persistence",
    "security", "runtimeConfig", "prRules", "checkpoints", "modes",
    "excludes", "boundaryAdapter",
}

# Per-key signature of a policy fragment when only one top-level field is
# present (avoids confusing a CI workflow's `api:` job with a policy `api:`
# block, etc.).
POLICY_SUBKEY_SIGNATURE = {
    "api": {"type", "specPath", "generationCommand", "diffMode", "checkpoint"},
    "persistence": {"migrationPaths", "checkpoint", "notes"},
    "security": {"paths", "checkpoint"},
    "runtimeConfig": {"paths", "checkpoint"},
    "boundaryAdapter": {"outputFormat", "outputPath", "violationFilter"},
    "modes": {"default", "perCheck"},
    "prRules": {"maxChangedFiles", "maxLinesChanged"},
}


def is_policy_fragment(doc: object) -> bool:
    """A YAML doc is a fragment-under-test iff it's a dict with policy keys.

    Two top-level matches: confidently a fragment.
    One top-level match: only if the value's sub-keys also match the policy
    signature for that key (filters out CI-workflow YAML).
    """
    if not isinstance(doc, dict):
        return False
    matches = doc.keys() & POLICY_FRAGMENT_FIELDS
    if len(matches) >= 2:
        return True
    if len(matches) == 1:
        only = next(iter(matches))
        sub = doc.get(only)
        if isinstance(sub, dict) and only in POLICY_SUBKEY_SIGNATURE:
            return bool(sub.keys() & POLICY_SUBKEY_SIGNATURE[only])
        # zones/boundaries/checkpoints/excludes are unambiguous when present at top-level
        if only in {"zones", "boundaries", "checkpoints", "excludes", "version", "project"}:
            return True
    return False


def wrap_for_validation(doc: dict) -> dict:
    """Wrap a fragment in the minimum required top-level fields so the schema
    validator can run without false 'missing required' errors. We're testing
    the FRAGMENT, not whether it ships standalone."""
    wrapped = dict(doc)
    wrapped.setdefault("version", 1)
    wrapped.setdefault("project", {"name": "fragment-check"})
    if "zones" not in wrapped:
        wrapped["zones"] = {"red": [{"path": "x", "reason": "stub"}]}
    elif isinstance(wrapped["zones"], dict) and not (
        wrapped["zones"].get("red") or wrapped["zones"].get("blue")
    ):
        wrapped["zones"]["red"] = [{"path": "x", "reason": "stub"}]
    # Stub any checkpoint referenced by a zone entry but not defined in this fragment.
    referenced_cps: set[str] = set()
    for zone_entries in (wrapped.get("zones") or {}).values():
        if isinstance(zone_entries, list):
            for entry in zone_entries:
                if isinstance(entry, dict) and entry.get("checkpoint"):
                    referenced_cps.add(entry["checkpoint"])
    if "api" in wrapped and isinstance(wrapped["api"], dict) and wrapped["api"].get("checkpoint"):
        referenced_cps.add(wrapped["api"]["checkpoint"])
    for cp in referenced_cps:
        if not (wrapped.get("checkpoints") or {}).get(cp):
            wrapped.setdefault("checkpoints", {})
            wrapped["checkpoints"][cp] = {"satisfiedBy": ["codeownerApproval"]}
    return wrapped


def extract_yaml_blocks(text: str) -> list[tuple[int, str]]:
    """Return (block_index, block_text) for every ```yaml fence (NOT ```yaml-sketch)."""
    blocks: list[tuple[int, str]] = []
    # Match ```yaml followed by EOL, then capture until the next ``` on its own line.
    pattern = re.compile(r"^```yaml\s*\n(.*?)\n```\s*$", re.DOTALL | re.MULTILINE)
    for i, m in enumerate(pattern.finditer(text)):
        blocks.append((i, m.group(1)))
    return blocks


def main() -> int:
    if not SCHEMA_PATH.exists():
        print(f"error: schema not found at {SCHEMA_PATH}", file=sys.stderr)
        return 1
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema)

    failures: list[str] = []
    fragments_checked = 0
    fragments_skipped = 0
    files_seen = 0

    for rel in SKILL_FILES:
        path = REPO_ROOT / rel
        if not path.exists():
            print(f"skip  {rel} (file not present)")
            continue
        files_seen += 1
        text = path.read_text(encoding="utf-8")
        blocks = extract_yaml_blocks(text)
        for idx, block_text in blocks:
            try:
                doc = yaml.safe_load(block_text)
            except yaml.YAMLError as e:
                # Only a failure if the block looked policy-shaped enough
                # to deserve parsing in the first place — a CI workflow
                # block that happens to fail parse isn't our concern.
                # Heuristic: blocks with `zones:` / `boundaries:` keywords
                # really should parse.
                if any(kw in block_text for kw in ("zones:", "boundaries:", "boundaryAdapter:", "checkpoints:")):
                    failures.append(f"{rel} block#{idx}: YAML parse error: {e}")
                else:
                    fragments_skipped += 1
                continue
            if not is_policy_fragment(doc):
                fragments_skipped += 1
                continue
            wrapped = wrap_for_validation(doc)
            errs = list(validator.iter_errors(wrapped))
            if errs:
                err_summary = "; ".join(
                    f"{e.message} @ {'/'.join(map(str, e.absolute_path))}" for e in errs
                )
                failures.append(f"{rel} block#{idx}: {err_summary}")
            else:
                fragments_checked += 1

    print()
    print(f"scanned {files_seen} skill file(s); {fragments_checked} policy fragment(s) validated; {fragments_skipped} non-policy block(s) skipped.")
    if failures:
        for line in failures:
            print(f"FAIL  {line}", file=sys.stderr)
        print(f"\n{len(failures)} fragment(s) failed.", file=sys.stderr)
        return 2
    print("all skill yaml fragments validate against the policy schema.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

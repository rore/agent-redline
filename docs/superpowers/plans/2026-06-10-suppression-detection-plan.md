# Suppression detection — implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Spec:** [`docs/superpowers/specs/2026-06-10-suppression-detection-design.md`](../specs/2026-06-10-suppression-detection-design.md). Read it first.

**Goal:** Close both halves of the suppression-laundering loop in one feature: the operating-mode skill refuses suppression markers (`# noqa`, `@SuppressWarnings`, `ignore_imports`, …) on guarded surfaces, and the reporter scans the diff for the same markers and routes them to `architecture-review` at PR/push time.

**Architecture:** Per-extension marker lists vendored into the consuming repo at `.agent-redline/suppressions.yaml` (no runtime extension reachback). The reporter reads the unified diff (new `--diff-unified` input), walks added lines, matches against the active list (vendored defaults + policy `add` − policy `remove`, minus `exemptPaths`), and emits one record per match. The match list feeds **both** the comment renderer and `_required_checkpoints()` (independent of the headline verdict — see spec §2.3, the `cmt_000010` bug from review). Compatibility: absent `suppressions:` block in the policy → detection OFF (spec §1.4, non-negotiable).

**Tech stack:** Python 3 (reporter), JSON Schema (Draft 2020-12), YAML, bash (CI), GitHub Actions. No new runtime dependencies.

**Order of work:** matches spec §10. Steps 1–4 (reporter core) are sequential; steps 6–7 (skill text + extension marker lists) are independent and can land in parallel; steps 8–10 follow the core landing.

**Resume protocol:** find the first phase whose checkbox is unchecked, do it, run its verification gate, commit, move on. Each phase's verification MUST pass before the next phase begins. `bash tests/run-all.sh` must be green at the end of every phase that touches code.

**Commit cadence:** one commit per phase, prefixed `suppression-detection: phase N — <summary>`. Push at end of each phase.

**Discipline guardrails (apply to every phase):**
- This is a public open-source repo. Never use SAP / XLM / CLM / Loyalty / Pelican / internal-service-name terminology in any committed file. The `loyalty` strings in spec examples are illustrative only — concrete fixtures use generic names (`example`, `myapp`, `orders`).
- agent-redline is bound by its own policy: classify before editing, do not silently weaken arch tests or `agent-policy.yaml`, do not add suppressions on this project's own guarded surfaces.
- Token budgets are hard ceilings (CI Layer 1 fails the build on breach). The new boundary-violation.md section and the new operating-mode.md bullet must fit within the existing 600 / 1500 ceilings respectively.
- Re-read [`docs/SKILL_AUTHORING.md`](../../SKILL_AUTHORING.md) before editing any file the agent loads at runtime; audit each section against the deletion test before committing.
- The reporter algorithm in spec §2.2 is **deliberately naive**. Do NOT re-introduce hunk-local set-difference, count-based equivalence, or per-position pairing — those were considered and rejected in spec §6 with a documented asymmetry argument.
- The vendored-file path is fixed at `.agent-redline/suppressions.yaml` (repo root). No CLI flag, no policy field. The missing-file error fires only under the three conditions in spec §1.4.

---

## Phase 0 — Plan & memory anchor

No code; durable state only.

- [ ] Spec is in place at `docs/superpowers/specs/2026-06-10-suppression-detection-design.md` (already true)
- [ ] Plan written to this file
- [ ] Memory anchor: write `C:\Users\I347041\.claude\projects\c--sap-dev-xlm-rore-agent-redline\memory\suppression-detection-feature-in-progress.md` (`type: project`) pointing at this plan; add the one-line index entry to `MEMORY.md`. Delete the file when the feature ships and replace with `suppression-detection-feature-shipped.md`.
- [ ] Working branch created: `git checkout -b suppression-detection`
- [ ] **Verification:** files exist; spec is internally consistent (already validated through 4 review rounds)
- [ ] **Commit:** `suppression-detection: phase 0 — spec and plan`

```bash
git checkout -b suppression-detection
git add docs/superpowers/plans/2026-06-10-suppression-detection-plan.md
git commit -m "suppression-detection: phase 0 — spec and plan"
```

---

## Phase 1 — Reporter input contract: `--diff-unified`

The reporter currently takes `--changed-files` + `--lines-per-file`; it never sees added-line content. Add a single new optional input that delivers the unified diff so later phases can scan added lines per file. No detection yet — this phase is wiring + parsing only.

**Files:**
- Modify: `core/reporter/reporter.py` — add `--diff-unified` CLI flag, a tiny `parse_unified_diff()` helper, surface added-lines-per-file on the `Diff` dataclass
- Test: `core/reporter/test_reporter_unit.py::TestParseUnifiedDiff` (new test class)
- Test: `tests/reporter/check-reporter.py` — recognise an optional `diff-unified.patch` input file in fixtures (passes through; no semantic change yet)

**Why this phase exists alone:** the unified-diff reader is a small, well-bounded change with its own tests. Bundling it with detection (Phase 4) would conflate "the reporter can read a diff" with "the reporter knows about suppressions."

- [ ] **Step 1: Write the failing parser test (multiple files, hunk headers, mixed +/-/context)**

```python
# core/reporter/test_reporter_unit.py — new class
class TestParseUnifiedDiff:
    def test_extracts_added_lines_per_file(self):
        from core.reporter.reporter import parse_unified_diff
        patch = (
            "diff --git a/a.py b/a.py\n"
            "--- a/a.py\n+++ b/a.py\n"
            "@@ -1,0 +2,2 @@\n"
            "+import os  # noqa: F401\n"
            "+x = 1\n"
            "diff --git a/b.py b/b.py\n"
            "--- a/b.py\n+++ b/b.py\n"
            "@@ -10,1 +10,1 @@\n"
            "-old\n"
            "+new  # type: ignore\n"
        )
        added = parse_unified_diff(patch)
        assert added == {
            "a.py": [(2, "import os  # noqa: F401"), (3, "x = 1")],
            "b.py": [(10, "new  # type: ignore")],
        }

    def test_handles_new_file(self):
        from core.reporter.reporter import parse_unified_diff
        patch = (
            "diff --git a/new.py b/new.py\n"
            "new file mode 100644\n"
            "--- /dev/null\n+++ b/new.py\n"
            "@@ -0,0 +1,2 @@\n"
            "+# nosec\n"
            "+pass\n"
        )
        assert parse_unified_diff(patch) == {
            "new.py": [(1, "# nosec"), (2, "pass")],
        }

    def test_skips_deleted_file(self):
        from core.reporter.reporter import parse_unified_diff
        patch = (
            "diff --git a/gone.py b/gone.py\n"
            "deleted file mode 100644\n"
            "--- a/gone.py\n+++ /dev/null\n"
            "@@ -1,1 +0,0 @@\n"
            "-x = 1\n"
        )
        assert parse_unified_diff(patch) == {}

    def test_renames_use_post_path(self):
        from core.reporter.reporter import parse_unified_diff
        patch = (
            "diff --git a/old.py b/new.py\n"
            "rename from old.py\nrename to new.py\n"
            "--- a/old.py\n+++ b/new.py\n"
            "@@ -1,1 +1,1 @@\n"
            "-x = 1\n"
            "+x = 1  # noqa\n"
        )
        assert parse_unified_diff(patch) == {"new.py": [(1, "x = 1  # noqa")]}

    def test_empty_patch(self):
        from core.reporter.reporter import parse_unified_diff
        assert parse_unified_diff("") == {}
```

- [ ] **Step 2: Run test — verify it fails (function not defined)**

```bash
pytest core/reporter/test_reporter_unit.py::TestParseUnifiedDiff -v
# Expected: ImportError or AttributeError on parse_unified_diff
```

- [ ] **Step 3: Implement `parse_unified_diff()`**

Add to `core/reporter/reporter.py` (near other parsers, before the dataclasses block ends):

```python
def parse_unified_diff(patch: str) -> dict[str, list[tuple[int, str]]]:
    """
    Parse a unified diff (produced by `git diff --unified=0`).

    Returns: {post_path: [(line_no, added_line_content), ...]}.

    Skips deleted files. For renames, the post-rename path is the key.
    Tracks the per-hunk new-file line counter so each added line carries
    its line number in the post-image. Hunk-boundary semantics are NOT
    used by callers; suppression detection (Phase 4) walks added lines
    per file regardless of hunk shape (spec §2.2 — naive algorithm).
    """
    out: dict[str, list[tuple[int, str]]] = {}
    current_path: str | None = None
    new_lineno = 0
    for raw in patch.splitlines():
        if raw.startswith("diff --git "):
            current_path = None  # reset; +++ line below sets it
            continue
        if raw.startswith("+++ "):
            target = raw[4:].strip()
            if target == "/dev/null":
                current_path = None
            else:
                # `+++ b/path/to/file` → strip the `b/` prefix
                current_path = target[2:] if target.startswith(("a/", "b/")) else target
            continue
        if raw.startswith("@@"):
            # @@ -<old>[,<n>] +<new>[,<n>] @@
            # Extract `<new>` and seed the counter.
            m = re.match(r"@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@", raw)
            if m and current_path is not None:
                new_lineno = int(m.group(1))
            continue
        if current_path is None:
            continue
        if raw.startswith("+") and not raw.startswith("+++"):
            out.setdefault(current_path, []).append((new_lineno, raw[1:]))
            new_lineno += 1
        elif raw.startswith("-") or raw.startswith("---"):
            # deletion — does not advance new-file lineno
            pass
        else:
            # context line (only present with -U > 0; harmless either way)
            new_lineno += 1
    return out
```

- [ ] **Step 4: Run the new tests — verify they pass**

```bash
pytest core/reporter/test_reporter_unit.py::TestParseUnifiedDiff -v
# Expected: 5 passed
```

- [ ] **Step 5: Add `--diff-unified` CLI flag (still no semantic effect yet)**

In `core/reporter/reporter.py` `main()`, alongside `--lines-per-file`:

```python
    p.add_argument("--diff-unified", type=Path,
                   help="Path to a unified diff with -U0 (produced by "
                        "`git diff --unified=0 <base> <head>`). Used by "
                        "Phase-4 suppression detection to read added-line "
                        "content. Optional; absent → suppression detection "
                        "falls back to no-op (compatible with policies that "
                        "lack a suppressions block).")
```

Also extend the `Diff` dataclass with an optional `added_by_file` field:

```python
@dataclass
class Diff:
    changed_files: list[str]
    files_changed: int
    lines_changed: int
    lines_by_file: dict[str, int] | None = None
    added_by_file: dict[str, list[tuple[int, str]]] | None = None
```

In `load_diff_from_files()` add an optional kwarg `diff_unified_path: Path | None = None` and populate `added_by_file = parse_unified_diff(diff_unified_path.read_text(encoding="utf-8"))` when given. Wire `args.diff_unified` through in `main()`.

- [ ] **Step 6: Run all reporter unit tests + golden fixtures — verify nothing regresses**

```bash
pytest core/reporter/test_reporter_unit.py -v
python tests/reporter/check-reporter.py
# Expected: all green; no fixture mismatches (added_by_file is unused this phase)
```

- [ ] **Step 7: Run full `tests/run-all.sh`**

```bash
bash tests/run-all.sh
# Expected: every layer green (or cleanly skipped via OPTIONAL_*)
```

- [ ] **Step 8: Commit**

```bash
git add core/reporter/reporter.py core/reporter/test_reporter_unit.py
git commit -m "suppression-detection: phase 1 — reporter accepts --diff-unified input"
```

---

## Phase 2 — Vendored-file contract: schema, loader, fixed-path resolution

Define the shape of `.agent-redline/suppressions.yaml` (the file each language extension supplies and bootstrap vendors into the consuming repo). Add the loader that reads it from a fixed path, with the missing-file error gated on the three conditions in spec §1.4.

**Files:**
- Create: `core/schema/suppressions.schema.json` — JSON Schema for the vendored file
- Create: `tests/schema/valid/vendored-suppressions.yaml`
- Create: `tests/schema/invalid/vendored-suppressions-empty.yaml`, `tests/schema/invalid/vendored-suppressions-wrong-shape.yaml`
- Modify: `core/reporter/reporter.py` — add `load_suppressions_defaults()`, `resolve_suppressions_config()`, dataclass `SuppressionsConfig`
- Test: `core/reporter/test_reporter_unit.py::TestSuppressionsResolution` (new test class)
- Test: `tests/schema/check-schema.py` — recognise the vendored-fixture filename pattern and validate it against the new schema

- [ ] **Step 1: Write `core/schema/suppressions.schema.json`**

The schema requires a top-level `suppressions:` mapping with at least one of `inlineComments`, `annotations`, or `configEdits`. `configEdits` requires non-empty `files` and `keys` lists. `additionalProperties: false` everywhere.

- [ ] **Step 2: Write the three schema fixtures**

Valid fixture covers `inlineComments` + `configEdits`. Invalid-empty has `suppressions: {}` (none of the three sub-fields present). Invalid-wrong-shape has `inlineComments: "# noqa"` (string instead of array).

- [ ] **Step 3: Wire the schema fixture harness**

Read `tests/schema/check-schema.py`. Add a small filename-pattern dispatcher: fixtures matching `vendored-suppressions*.yaml` validate against `core/schema/suppressions.schema.json`; everything else continues to validate against `core/schema/agent-policy.schema.json` (existing behavior).

- [ ] **Step 4: Run schema check — verify the dispatcher works**

```bash
python tests/schema/check-schema.py
```

Expected: every valid fixture passes; every invalid fixture fails with the expected error.

- [ ] **Step 5: Write the failing reporter test for suppression resolution**

Test class covers five cases:

1. Absent `suppressions:` block in the policy → returns `None` (compatibility, spec §1.4).
2. Block present but `useExtensionDefaults` defaults to true and vendored file absent → raises `FileNotFoundError` with a message naming the path.
3. Block present + `useExtensionDefaults: false` + vendored file absent → no error; uses only `add:`.
4. Block present + `useExtensionDefaults: true` + vendored file present → merges defaults with `add` and `remove` (set arithmetic).
5. `exemptPaths` round-trips through the resolved config.

- [ ] **Step 6: Run test — verify it fails (function not defined)**

```bash
pytest core/reporter/test_reporter_unit.py::TestSuppressionsResolution -v
```

- [ ] **Step 7: Implement `SuppressionsConfig`, `load_suppressions_defaults()`, `resolve_suppressions_config()`**

Add to `core/reporter/reporter.py`:

- `SuppressionsConfig` dataclass with `inline_comments: list[str]`, `annotations: list[str]`, `config_files: list[str]`, `config_keys: list[str]`, `exempt_paths: list[str]`. All default to empty lists.
- Module-level constant: `VENDORED_SUPPRESSIONS_PATH = ".agent-redline/suppressions.yaml"`.
- `load_suppressions_defaults(repo_root: Path) -> dict | None` — reads the YAML if present, returns the inner `suppressions:` mapping (not the wrapper). Returns `None` when absent. Raises `SystemExit` on a non-mapping document.
- `resolve_suppressions_config(policy, repo_root) -> SuppressionsConfig | None`:
  - If `policy.suppressions` is absent → return `None` (spec §1.4 compatibility — non-negotiable).
  - Read `useExtensionDefaults` (default `True`), `add`, `remove`, `exemptPaths` from the block.
  - When `useExtensionDefaults` is true AND the vendored file is absent, raise `FileNotFoundError` whose message names the path AND lists the three remediations (re-bootstrap / set `useExtensionDefaults: false` / remove the block).
  - Effective list per category = `defaults + add − remove` (preserve order; remove acts as a set filter). Apply this to `inlineComments`, `annotations`, `configEdits.files`, `configEdits.keys`.

- [ ] **Step 8: Run tests — verify they pass**

```bash
pytest core/reporter/test_reporter_unit.py::TestSuppressionsResolution -v
```

- [ ] **Step 9: Run full `tests/run-all.sh`**

```bash
bash tests/run-all.sh
```

Expected: every layer green or cleanly skipped. Layer 2 (schema) now also exercises the new vendored-suppressions fixtures.

- [ ] **Step 10: Commit**

```bash
git add core/schema/suppressions.schema.json \
        tests/schema/valid/vendored-suppressions.yaml \
        tests/schema/invalid/vendored-suppressions-empty.yaml \
        tests/schema/invalid/vendored-suppressions-wrong-shape.yaml \
        tests/schema/check-schema.py \
        core/reporter/reporter.py core/reporter/test_reporter_unit.py
git commit -m "suppression-detection: phase 2 — vendored-file contract (schema + loader + missing-file gate)"
```

---

## Phase 3 — Schema additions: policy block + `modes.perCheck.suppression`

Extend `core/schema/agent-policy.schema.json` with the optional `suppressions:` block and add `suppression` to the `modes.perCheck` enum. Both additions are non-breaking — absent block stays valid, which is the §1.4 compatibility rule expressed at the schema layer.

**Files:**
- Modify: `core/schema/agent-policy.schema.json`
- Create: `tests/schema/valid/with-suppressions-overrides.yaml`
- Create: `tests/schema/valid/with-suppressions-percheck-shadow.yaml`
- Create: `tests/schema/invalid/suppressions-wrong-shape.yaml`
- Create: `tests/schema/invalid/suppressions-percheck-bad-value.yaml`

- [ ] **Step 1: Write the failing valid fixture (overrides-only block)**

`tests/schema/valid/with-suppressions-overrides.yaml`:

```yaml
version: 1
project:
  name: example
  extension: python
zones:
  red:
    - path: src/example/domain/**
      reason: domain
      checkpoint: architecture-review
  blue:
    - path: tests/**
      reason: tests
suppressions:
  useExtensionDefaults: true
  add:
    inlineComments: ["# custom-marker"]
  remove:
    inlineComments: ["# pragma: no cover"]
  exemptPaths:
    - "**/tests/**"
checkpoints:
  architecture-review:
    satisfiedBy:
      - codeownerApproval
      - label: architecture-reviewed
modes:
  default: shadow
  perCheck:
    boundary_violation: binding
    suppression: binding
```

- [ ] **Step 2: Write the second valid fixture (suppression in shadow mode)**

`tests/schema/valid/with-suppressions-percheck-shadow.yaml`: same shape, but `modes.perCheck.suppression: shadow`. Confirms the enum accepts both values.

- [ ] **Step 3: Write the invalid fixtures**

`tests/schema/invalid/suppressions-wrong-shape.yaml` — `add: "string-not-an-object"` under the suppressions block.

`tests/schema/invalid/suppressions-percheck-bad-value.yaml` — `modes.perCheck.suppression: maybe` (not in the enum).

- [ ] **Step 4: Run schema check — verify all four fixtures fail their assertions (valid fail to pass, invalid fail to fail)**

```bash
python tests/schema/check-schema.py
```

Expected: errors on the four new fixtures (because the schema doesn't know `suppressions:` yet).

- [ ] **Step 5: Add the schema entries**

In `core/schema/agent-policy.schema.json`:

Under `properties.modes.properties.perCheck.properties`, add:

```json
"suppression": { "enum": ["shadow", "binding"] }
```

Add a sibling top-level property under `properties` (alongside `excludes`, `boundaryAdapter`):

```json
"suppressions": {
  "type": "object",
  "additionalProperties": false,
  "description": "Optional. When absent, suppression detection is OFF (spec §1.4 compatibility). When present, declares overrides on the vendored marker list at .agent-redline/suppressions.yaml.",
  "properties": {
    "useExtensionDefaults": { "type": "boolean" },
    "add":    { "$ref": "#/$defs/suppressionsList" },
    "remove": { "$ref": "#/$defs/suppressionsList" },
    "exemptPaths": {
      "type": "array",
      "items": { "type": "string", "minLength": 1 }
    }
  }
}
```

Add to `$defs`:

```json
"suppressionsList": {
  "type": "object",
  "additionalProperties": false,
  "properties": {
    "inlineComments": { "type": "array", "items": { "type": "string", "minLength": 1 } },
    "annotations":    { "type": "array", "items": { "type": "string", "minLength": 1 } },
    "configEdits": {
      "type": "object",
      "additionalProperties": false,
      "properties": {
        "files": { "type": "array", "items": { "type": "string", "minLength": 1 } },
        "keys":  { "type": "array", "items": { "type": "string", "minLength": 1 } }
      }
    }
  }
}
```

- [ ] **Step 6: Run schema check — verify all four fixtures now pass/fail correctly**

```bash
python tests/schema/check-schema.py
```

- [ ] **Step 7: Verify pre-existing fixtures still pass**

The non-breaking property: `tests/schema/valid/minimal.yaml`, `tests/schema/valid/full.yaml`, and the production demo policies all lack a `suppressions:` block and must continue to validate. This is the schema-level expression of spec §1.4.

```bash
python tests/schema/check-schema.py    # full sweep
```

- [ ] **Step 8: Run full `tests/run-all.sh`**

- [ ] **Step 9: Commit**

```bash
git add core/schema/agent-policy.schema.json \
        tests/schema/valid/with-suppressions-*.yaml \
        tests/schema/invalid/suppressions-*.yaml
git commit -m "suppression-detection: phase 3 — policy schema additions (suppressions block + modes.perCheck.suppression)"
```

---

## Phase 4 — Detection: `scan_suppressions()` and checkpoint wiring

The core of the feature. Walks added lines per file, matches against the active marker list, emits one record per match. The match list feeds **both** the comment renderer AND `_required_checkpoints()` — missing the second is the `cmt_000010` bug from review (spec §2.3, "Mechanics" subsection). `_binding()` hardcodes `binding` as the default for `suppression`, symmetric with `boundary_violation`.

**Files:**
- Modify: `core/reporter/reporter.py` — add `SuppressionMatch` dataclass, `scan_suppressions()` function, wire results into `Verdict`, `_required_checkpoints()`, `_binding()`, the headline-verdict ladder, and `render_markdown()`
- Test: `core/reporter/test_reporter_unit.py::TestScanSuppressions` and `::TestSuppressionsCheckpointWiring` (new test classes)

- [ ] **Step 1: Write the failing scanner tests**

Test class `TestScanSuppressions` covers:

1. **Inline-comment substring match.** Added line `from pkg.x import y  # noqa: F401` with config `inline_comments=["# noqa"]` → one match with `category="inlineComment"`, `marker="# noqa"`, `line=42`.
2. **Multiple markers on one line → one match per marker** (deterministic order = order in the active list).
3. **Annotation token match.** Added line `@SuppressWarnings("ArchUnit")` with `annotations=["@SuppressWarnings"]` → one match with `category="annotation"`. Word-bounded so `@SuppressWarningsExt` does NOT match.
4. **`configEdits` key match (structural).** Added line `ignore_imports = ["pkg.a -> pkg.b"]` in `pyproject.toml` with `config_files=["pyproject.toml"]`, `config_keys=["ignore_imports"]` → one match with `category="configEdit"`.
5. **`configEdits` ignores comments.** Added line `# ignore_imports does cool stuff` in `pyproject.toml` → no match. (The structural rule: a key match is "looks like an assignment / table key," not a substring anywhere in the line.)
6. **`exemptPaths` skips the file.** A `# noqa` line in `tests/conftest.py` with `exempt_paths=["**/tests/**"]` → no match.
7. **Reformat false positive fires (accepted v1 cost, spec §6).** Removed line `foo()  # noqa` and added line `bar()  # noqa` → one match on the added line. Verifies the algorithm is naive — see also the §6 asymmetry argument.
8. **No suppressions config → empty list (compatibility path).** `scan_suppressions(diff_added={...}, config=None)` → `[]`.
9. **Marker on a line in a non-config file matches inline-comment list anyway.** A `pyproject.toml` line `# noqa: B001` matches via `inlineComments` (orthogonal categories — a single line can only produce one match per marker, but inline-comment markers are not gated to non-config files).
10. **Zone classification of the match comes from the file's zone, not the marker.** Match in a red-zone file → `zone="red"`; match in a blue-zone file → `zone="blue"`; match in a watch+blue file → `zone="blue"` (watch is additive — the spec §2.5 example shows `zone: red`; the rule is "primary classification of the file"). Use the existing `classify_files()` output.

- [ ] **Step 2: Run tests — verify they fail (function not defined)**

- [ ] **Step 3: Implement `SuppressionMatch` and `scan_suppressions()`**

In `core/reporter/reporter.py`:

```python
@dataclass
class SuppressionMatch:
    file: str
    line: int
    marker: str
    category: str         # "inlineComment" | "annotation" | "configEdit"
    zone: str             # "red" | "blue" | "gray"
    context: str          # the added-line content, truncated
```

```python
_ANNOTATION_TOKEN_RE_CACHE: dict[str, re.Pattern] = {}


def _annotation_token_re(marker: str) -> re.Pattern:
    """Word-boundary regex for an annotation token (e.g. @SuppressWarnings).

    `@` is not a word character, so a leading boundary isn't useful; we
    anchor on the literal `@<Name>` and require a non-word character (or
    end-of-string) after the name to prevent `@SuppressWarningsExt` from
    matching `@SuppressWarnings`.
    """
    if marker not in _ANNOTATION_TOKEN_RE_CACHE:
        _ANNOTATION_TOKEN_RE_CACHE[marker] = re.compile(
            re.escape(marker) + r"(?![A-Za-z0-9_])"
        )
    return _ANNOTATION_TOKEN_RE_CACHE[marker]


def _is_config_key_assignment(line: str, key: str) -> bool:
    """Structural key match for configEdits.

    `ignore_imports = [...]`  → True
    `[tool.x.ignore_imports]` → True (TOML table header)
    `"ignore_imports": [...]` → True (JSON-ish)
    `# ignore_imports stuff`  → False (comment)
    The check is intentionally simple: ignore lines whose first non-whitespace
    char is a comment marker (`#`, `//`); otherwise look for the key followed
    by `=`, `:`, or appearing inside `[...]` table headers.
    """
    stripped = line.lstrip()
    if not stripped or stripped[0] in "#" or stripped.startswith("//"):
        return False
    pattern = re.compile(
        r"(?:^|[\s\[\"'])"          # start, whitespace, [, or quote
        + re.escape(key)
        + r"\s*[=:\[\]]"             # followed by =, :, ], or [
    )
    return bool(pattern.search(line))


def scan_suppressions(
    added_by_file: dict[str, list[tuple[int, str]]] | None,
    config: SuppressionsConfig | None,
    classification: dict[str, list[str]],
) -> list[SuppressionMatch]:
    """
    Naive added-line scanner. Spec §2.2 — deliberately no hunk parsing,
    no removed-line tracking, no equivalence by marker family. Reformat
    false positives are visible-and-cheap by design (see spec §6).
    """
    if config is None or added_by_file is None:
        return []

    # Map each file → its primary zone (red > gray > blue residual).
    file_zone: dict[str, str] = {}
    for f in classification.get("red", []):
        file_zone[f] = "red"
    for f in classification.get("gray", []):
        file_zone.setdefault(f, "gray")
    for f in classification.get("blue", []):
        file_zone.setdefault(f, "blue")

    matches: list[SuppressionMatch] = []
    for path, lines in added_by_file.items():
        if matches_any(path, config.exempt_paths):
            continue
        zone = file_zone.get(path, "gray")
        is_config_file = matches_any(path, config.config_files) if config.config_files else False

        for line_no, content in lines:
            # Inline-comment substring matches.
            for marker in config.inline_comments:
                if marker in content:
                    matches.append(SuppressionMatch(
                        file=path, line=line_no, marker=marker,
                        category="inlineComment", zone=zone,
                        context=content[:200],
                    ))
            # Annotation token matches (word-boundaried).
            for marker in config.annotations:
                if _annotation_token_re(marker).search(content):
                    matches.append(SuppressionMatch(
                        file=path, line=line_no, marker=marker,
                        category="annotation", zone=zone,
                        context=content[:200],
                    ))
            # configEdits — only on declared config files.
            if is_config_file:
                for key in config.config_keys:
                    if _is_config_key_assignment(content, key):
                        matches.append(SuppressionMatch(
                            file=path, line=line_no, marker=key,
                            category="configEdit", zone=zone,
                            context=content[:200],
                        ))
    return matches
```

- [ ] **Step 4: Run scanner tests — verify they pass**

```bash
pytest core/reporter/test_reporter_unit.py::TestScanSuppressions -v
```

- [ ] **Step 5: Write the failing checkpoint-wiring tests**

Test class `TestSuppressionsCheckpointWiring` covers (this is where the `cmt_000010` bug guard lives):

1. **Suppression-only diff → headline `RED`, `architecture-review` required.** No other zone signal; the suppression is the sole reason for the verdict.
2. **Suppression + boundary violation → headline `BOUNDARY_VIOLATION`, BOTH the boundary checkpoint AND `architecture-review` required.** This is the §2.3 "independent of headline verdict" rule — the bug review caught.
3. **Suppression + API_CHANGE → headline `API_CHANGE`, BOTH `api-review` AND `architecture-review` required.**
4. **Suppression on `**/tests/**` exempted path → no match, no checkpoint, headline whatever the rest of the diff produces.**
5. **`modes.perCheck.suppression: shadow` → checkpoint still appears in required list, but exit code stays at 1 (warn) when suppression is the only blocker.**
6. **`modes.perCheck.suppression` absent → defaults to `binding` (the hardcoded default, symmetric with `boundary_violation`). Exit code is 2 when checkpoint unmet.**
7. **`modes.default: shadow` does NOT downgrade `suppression`.** Spec §2.4 — only an explicit per-check value flips it.
8. **No suppressions block in policy → no checkpoint, no comment row, no behavior change** (compatibility, spec §1.4).

- [ ] **Step 6: Run tests — verify they fail**

- [ ] **Step 7: Wire suppression matches into the verdict pipeline**

Update `core/reporter/reporter.py`:

a. Extend `Verdict` dataclass with `suppressions: list[SuppressionMatch] = field(default_factory=list)`. Update `to_dict()` to include `"suppressions": [asdict(s) for s in self.suppressions]`.

b. Update `classify()` signature to accept `suppressions_config: SuppressionsConfig | None = None`. Compute matches with `scan_suppressions(diff.added_by_file, suppressions_config, classification)` immediately after `classify_files()` runs.

c. Extend `_required_checkpoints()` with a new positional argument `suppression_matches: list[SuppressionMatch]`. Append `architecture-review` to the required map when the list is non-empty:
```python
if suppression_matches:
    required.setdefault(
        "architecture-review",
        f"Suppression marker on guarded surface: "
        f"{suppression_matches[0].marker} at "
        f"{suppression_matches[0].file}:{suppression_matches[0].line}"
        + (f" (+{len(suppression_matches)-1} more)" if len(suppression_matches) > 1 else "")
    )
```

d. Update the headline-verdict ladder in `classify()` to add a `suppressions` arm BELOW `boundary_violations / arch_test_modified / api / schema / security / runtime / classification['red']`. Specifically: when no other red-or-higher signal fires AND `suppression_matches` is non-empty, set `verdict = "RED"` and `summary = f"{len(suppression_matches)} suppression marker(s) added on guarded surfaces."`

e. Update `_binding()` so the default for `suppression` is hardcoded to `"binding"`:
```python
def _binding(modes: dict[str, Any], check_name: str) -> bool:
    default = (modes or {}).get("default", "shadow")
    per_check = (modes or {}).get("perCheck", {}) or {}
    # Hardcoded per-check defaults that override modes.default. Symmetric
    # with how the spec treats boundary_violation; see §2.4.
    HARDCODED_BINDING_DEFAULTS = {"suppression"}
    if check_name in HARDCODED_BINDING_DEFAULTS:
        return per_check.get(check_name, "binding") == "binding"
    return per_check.get(check_name, default) == "binding"
```
(Note: `boundary_violation` is *not* added to `HARDCODED_BINDING_DEFAULTS` — the existing demos rely on it being settable to shadow. Only `suppression` gets the new hardcode, per spec §2.4.)

f. Update the exit-code computation at the end of `classify()` so an unsatisfied suppression checkpoint under `_binding(modes, "suppression")` lifts the exit code to 2. Pattern:
```python
suppression_unmet = (
    suppression_matches
    and any(c.id == "architecture-review" and not c.satisfied for c in checkpoint_statuses)
)
if suppression_unmet and _binding(modes, "suppression"):
    exit_code = max(exit_code, 2)
    if recommended == "none":
        recommended = "satisfy-suppression-checkpoint"
```

g. Update `main()` to call `resolve_suppressions_config(policy, repo_root=Path("."))` (or the policy's parent dir) and pass it through to `classify()`.

- [ ] **Step 8: Run all unit tests — verify checkpoint-wiring tests pass and no existing test regresses**

```bash
pytest core/reporter/test_reporter_unit.py -v
```

- [ ] **Step 9: Run all golden fixtures — verify nothing regresses**

```bash
python tests/reporter/check-reporter.py
```

Expected: every existing fixture still passes byte-for-byte. None of the existing fixtures has a `suppressions:` block (compatibility), so the new code path is entirely dormant for them.

- [ ] **Step 10: Run full `tests/run-all.sh`**

- [ ] **Step 11: Commit**

```bash
git add core/reporter/reporter.py core/reporter/test_reporter_unit.py
git commit -m "suppression-detection: phase 4 — scan_suppressions + checkpoint wiring (cmt_000010 fix)"
```

---

## Phase 5 — Reporter golden fixtures (the seven listed in spec §5)

Golden-fixture coverage for every code path Phase 4 introduced. The seven fixtures the spec mandates, each with `changed-files.txt`, `diff-unified.patch`, optional `policy.yaml` (most use `_common-policy.yaml`), `expected-verdict.json`, `expected-comment.md`. The `tests/reporter/check-reporter.py` harness already loops every fixture directory; new ones are picked up automatically once the harness recognises `diff-unified.patch` and a per-fixture `.agent-redline/suppressions.yaml`.

**Files:**
- Modify: `tests/reporter/check-reporter.py` — read `<fixture>/diff-unified.patch` if present and pass to the reporter; read `<fixture>/.agent-redline/suppressions.yaml` if present (per-fixture vendored file, used in lieu of the repo-root one) by invoking `resolve_suppressions_config()` with `repo_root=fixture`.
- Create: seven new fixture directories under `tests/reporter/`:
  - `suppression-noqa-on-red/`
  - `suppression-archignore-on-watch/`
  - `suppression-ignore-imports/`
  - `suppression-on-exempt-path/`
  - `suppression-reformat-fires-known-fp/`
  - `suppression-and-boundary-violation/`
  - `policy-without-suppressions-block/`

Each fixture follows the existing pattern (see `tests/reporter/blue-only/` for shape).

- [ ] **Step 1: Extend the harness**

In `tests/reporter/check-reporter.py`:

a. After `load_diff_from_files(...)`, also call `parse_unified_diff()` on `<fixture>/diff-unified.patch` if it exists, and attach to `diff.added_by_file`.

b. Before invoking `classify()`, call `resolve_suppressions_config(policy, repo_root=fixture)` so a per-fixture `.agent-redline/suppressions.yaml` is honored. (The harness already cd's nowhere; the test passes the fixture path explicitly.)

c. Pass the resolved config and the diff (with `added_by_file` populated) into `classify()`.

- [ ] **Step 2: Write fixture `suppression-noqa-on-red`**

Files:
- `policy.yaml` — extends `_common-policy.yaml` shape and adds:
  ```yaml
  suppressions:
    useExtensionDefaults: true
    exemptPaths: ["**/tests/**"]
  ```
- `.agent-redline/suppressions.yaml`:
  ```yaml
  suppressions:
    inlineComments: ["# noqa", "# type: ignore"]
  ```
- `changed-files.txt`: `src/main/java/com/example/orders/domain/Order.java` (single line)
- `diff-unified.patch`: a -U0 patch adding one line `import com.example.adapter.persistence.OrderRow;  // noqa: import-linter` at line 12. Use a controller-flavored Java line with a `# noqa`-style marker — the inlineComments substring matches regardless of source language.
- `lines-changed.txt`: `1`
- `expected-verdict.json`: verdict `RED`, `architecture-review` checkpoint required and unsatisfied, `suppressions` array with one entry, exit code `2` (binding default).
- `expected-comment.md`: shows the new "Suppressions added (1):" table and the `architecture-review` checkpoint row.

(Use a Python-style fixture if Java's `// noqa` is awkward — pick one and keep it consistent. The existing `_common-policy.yaml` is JVM; a Python-flavored fixture with its own minimal `policy.yaml` is fine.)

- [ ] **Step 3: Write fixture `suppression-archignore-on-watch`**

JVM scenario. `@SuppressWarnings("ArchUnit")` added on a controller (watch-tagged in `_common-policy.yaml`). Verifies the annotation category and that `watch` files still produce `architecture-review` (since suppression is independent of watch tagging).

- [ ] **Step 4: Write fixture `suppression-ignore-imports`**

Python scenario. `pyproject.toml` gets a new `ignore_imports = ["..."]` line under `[[tool.importlinter.contracts]]`. Verifies the `configEdits` category and the structural-key match (a comment-only line containing `ignore_imports` does NOT fire).

The fixture's vendored file:
```yaml
suppressions:
  inlineComments: ["# noqa"]
  configEdits:
    files: ["pyproject.toml", ".importlinter"]
    keys: ["ignore_imports", "per-file-ignores"]
```

The fixture's `policy.yaml` zones `pyproject.toml` as red.

- [ ] **Step 5: Write fixture `suppression-on-exempt-path`**

`# noqa: E402` added inside `tests/conftest.py`. Policy:
```yaml
suppressions:
  exemptPaths: ["**/tests/**"]
```
Expected: no suppression match, no architecture-review checkpoint, headline `BLUE`. Verifies the exemption gate.

- [ ] **Step 6: Write fixture `suppression-reformat-fires-known-fp`**

A diff that removes `foo()  # noqa: E501` and adds `bar()  # noqa: E501`. Asserts the match fires (one entry, `# noqa` marker), verdict `RED`, `architecture-review` required. The fixture's `expected-comment.md` documents in a comment line that this is the accepted v1 false positive (spec §6) — preserves the design decision against future "let me make this smarter" pressure.

- [ ] **Step 7: Write fixture `suppression-and-boundary-violation`**

Diff adds a forbidden import (caught by ArchUnit, fires `BOUNDARY_VIOLATION`) AND adds a `# noqa: F401` on an unrelated red-zone file. Inputs include both `archunit.xml` (with one violation) and `diff-unified.patch` (with the suppression line).

Expected: headline `BOUNDARY_VIOLATION`, but BOTH the boundary checkpoint AND `architecture-review` appear in `checkpoints`. The suppressions table appears in the comment **below** the boundary section. This is the cmt_000010 regression fixture.

- [ ] **Step 8: Write fixture `policy-without-suppressions-block`**

Policy has no `suppressions:` block at all. The diff includes a `# noqa` line on a red-zone file. Expected: verdict `RED` (from the red-zone touch alone), no `suppressions` array in the JSON (or empty), no suppressions table in the comment, no spurious "missing vendored file" error. This is the spec §1.4 compatibility fixture — non-negotiable.

- [ ] **Step 9: Run the harness with `--update` to generate `expected-*.json` / `expected-*.md` for the new fixtures**

```bash
python tests/reporter/check-reporter.py --update
```

Inspect every generated file before committing — the `--update` flow records whatever the reporter emits, so a Phase-4 bug would be silently baked in. Cross-check against spec §2.5's example output and §4's worked examples.

- [ ] **Step 10: Run the harness for real — verify all fixtures pass**

```bash
python tests/reporter/check-reporter.py
```

- [ ] **Step 11: Run full `tests/run-all.sh`**

Layer 13 (reporter-goldens) now exercises seven new fixtures. Layer 2 (schema) covers the new vendored fixtures via Phase 2/3.

- [ ] **Step 12: Commit**

```bash
git add tests/reporter/check-reporter.py \
        tests/reporter/suppression-noqa-on-red \
        tests/reporter/suppression-archignore-on-watch \
        tests/reporter/suppression-ignore-imports \
        tests/reporter/suppression-on-exempt-path \
        tests/reporter/suppression-reformat-fires-known-fp \
        tests/reporter/suppression-and-boundary-violation \
        tests/reporter/policy-without-suppressions-block
git commit -m "suppression-detection: phase 5 — reporter golden fixtures (seven scenarios from spec §5)"
```

---

## Phase 6 — Skill text: operating-mode bullet + boundary-violation Suppressions section

Lift the existing suppression refusal out of the BOUNDARY_RISK branch and apply it to all guarded surfaces; add a short Suppressions section to `boundary-violation.md`. **Re-read [`docs/SKILL_AUTHORING.md`](../../SKILL_AUTHORING.md) before editing either file.** Both files have hard token ceilings (1500 and 600 respectively) — Layer 1 of `tests/run-all.sh` will reject a breach.

**Files:**
- Modify: `core/skill/operating-mode.md` — extend Step 4's "Do not silently modify governance" subsection
- Modify: `core/templates/skills/boundary-violation.md` — append a Suppressions section
- (No budget bumps expected — spec §5.1 says +60 tokens for operating-mode and +120 for boundary-violation, both well within ceilings.)

- [ ] **Step 1: Re-read `docs/SKILL_AUTHORING.md`**

Run the deletion test on every sentence you write. Imperative voice. No marketing, no rationale, no commentary — those go in the spec or DECISIONS.md.

- [ ] **Step 2: Edit `core/skill/operating-mode.md` Step 4**

The existing subsection "Do not silently modify governance — refuse, don't proceed" already has three bullets (architecture-test files, agent-policy.yaml, already-shipped migrations). Add a fourth:

```markdown
- **Suppression markers on guarded surfaces** — adding `# noqa`, `# type: ignore`,
  `@SuppressWarnings`, `@ArchIgnore`, `ignore_imports`, `per-file-ignores`, or any
  other marker on a non-exempt path. Suppressions silence governance the same way
  arch-test edits do; the right response to a check blocking your change is to
  fix the structure or escalate, not to silence the check. The repo's
  `.agent-redline/suppressions.yaml` plus the policy's `suppressions:` block
  list which markers count and which paths are exempt.
```

The BOUNDARY_RISK branch's existing "Forbidden" list still names `@SuppressWarnings, lint exclusions, or any other suppression` — keep it. The bullet you just added is the general rule; the BOUNDARY_RISK list is the load-bearing specific case. No cross-reference language is needed beyond what's already there.

- [ ] **Step 3: Run budget check on `operating-mode.md`**

```bash
bash tests/budget/check-budget.sh --verbose | grep operating-mode
```

Expected: under 1500 tokens. The spec estimates +60 tokens; the file currently has plenty of headroom. If it's close, trim sibling bullets — do NOT bump the ceiling.

- [ ] **Step 4: Edit `core/templates/skills/boundary-violation.md`**

Append a new section at the end:

```markdown
## Suppressions

Adding a suppression marker (`# noqa`, `# type: ignore`, `@SuppressWarnings`,
`@ArchIgnore`, `ignore_imports`, `per-file-ignores`, or any marker the
repo's `.agent-redline/suppressions.yaml` lists) on a non-exempt path is
the same shape of governance laundering as editing the boundary-rule
backend. The two legitimate responses are the same as above: fix the
structure, or escalate.

Patterns to refuse:

- **"It's just for tests."** The policy lists `exemptPaths`. If the path
  isn't there, this isn't tests.
- **"I'll remove the noqa later."** No mechanism tracks it.
- **"The linter is wrong."** File an issue against the linter; don't
  suppress.
- **"We need this one suppression to ship."** Explicit policy edit (add
  to `suppressions.exemptPaths` or contract an `ignore_imports` entry),
  and that edit is itself red-zone (architecture-review).
```

- [ ] **Step 5: Run budget check on `boundary-violation.md`**

```bash
bash tests/budget/check-budget.sh --verbose | grep boundary-violation
```

Expected: under 600 tokens. The spec estimates +120 tokens. If close, trim — do NOT bump.

- [ ] **Step 6: Sync the demo copies**

Both `demo-source/docs/agent/boundary-violation.md` and `demo-source-python/docs/agent/boundary-violation.md` are copies of the template. Re-copy them:

```bash
cp core/templates/skills/boundary-violation.md demo-source/docs/agent/boundary-violation.md
cp core/templates/skills/boundary-violation.md demo-source-python/docs/agent/boundary-violation.md
```

- [ ] **Step 7: Run `tests/skill-yaml/`, `tests/skill-refs/`, `tests/links/`, full `tests/run-all.sh`**

These layers catch dangling references and broken links — likely tripped by the new section's mention of `.agent-redline/suppressions.yaml` (which exists post-Phase-2) and `suppressions.exemptPaths` (a policy field, not a file).

```bash
bash tests/run-all.sh
```

- [ ] **Step 8: Commit**

```bash
git add core/skill/operating-mode.md \
        core/templates/skills/boundary-violation.md \
        demo-source/docs/agent/boundary-violation.md \
        demo-source-python/docs/agent/boundary-violation.md
git commit -m "suppression-detection: phase 6 — skill text (operating-mode bullet + boundary-violation Suppressions section)"
```

---

## Phase 7 — Extension marker lists (Python, JVM, core stack-neutral)

Each language extension owns its marker list at `extensions/<name>/suppressions.yaml`. A core stack-neutral default lives at `core/templates/suppressions.yaml` (used by zone-only / no-extension repos). Bootstrap (Phase 8) copies one of these into the consuming repo at `.agent-redline/suppressions.yaml`.

**Files:**
- Create: `core/templates/suppressions.yaml` — stack-neutral defaults
- Create: `extensions/python/suppressions.yaml`
- Create: `extensions/jvm-archunit/suppressions.yaml`
- (Lists ship narrow on purpose — spec §1.4. Adopters report missing markers; lists grow.)

- [ ] **Step 1: Write `core/templates/suppressions.yaml`**

```yaml
# Stack-neutral suppression markers shipped by agent-redline core.
#
# Bootstrap copies this file into the consuming repo at
# `.agent-redline/suppressions.yaml` when no language extension is
# selected (zone-only repos). Language extensions ship their own
# `extensions/<name>/suppressions.yaml` that supersedes this file
# during bootstrap.
#
# The list is deliberately narrow. Adopters extend via the policy's
# `suppressions.add` block; markers not on the active list are
# ignored by the reporter. See SPEC §15.5 and the suppression-
# detection spec §1.4.

suppressions:
  inlineComments:
    - "# nosec"
    - "# semgrep:ignore"
    - "# semgrep-ignore"
```

- [ ] **Step 2: Write `extensions/python/suppressions.yaml`**

```yaml
# Python suppression markers — vendored to .agent-redline/suppressions.yaml
# at bootstrap time (extensions/python/scaffold.md instructs the copy).
#
# The reporter does NOT reach back to this file at runtime. Detection
# reads the vendored copy. See suppression-detection spec §1.3.

suppressions:
  inlineComments:
    - "# noqa"
    - "# type: ignore"
    - "# pylint: disable"
    - "# pylint: skip-file"
    - "# ruff: noqa"
    - "# nosec"
  configEdits:
    files:
      - "pyproject.toml"
      - ".flake8"
      - ".pylintrc"
      - "setup.cfg"
      - ".importlinter"
    keys:
      - "ignore_imports"
      - "per-file-ignores"
      - "ignore-paths"
```

- [ ] **Step 3: Write `extensions/jvm-archunit/suppressions.yaml`**

```yaml
# JVM (Java/Kotlin) suppression markers — vendored to
# .agent-redline/suppressions.yaml at bootstrap time
# (extensions/jvm-archunit/scaffold.md instructs the copy).
#
# Annotations only; ArchUnit baselines are file-shaped and weakening
# them shows up as red-zone path-touch on the arch-test files
# (governed by the existing red entry).

suppressions:
  annotations:
    - "@SuppressWarnings"
    - "@SuppressFBWarnings"
    - "@ArchIgnore"
    - "@SuppressLint"
```

- [ ] **Step 4: Validate each new file against the vendored-suppressions schema**

```bash
python tests/schema/check-schema.py
```

The Phase-2 dispatcher hooks `vendored-suppressions*.yaml` to the new schema. Add file-extension or path-prefix dispatch so `extensions/*/suppressions.yaml` and `core/templates/suppressions.yaml` are also validated against `core/schema/suppressions.schema.json`. (If the harness only walks `tests/schema/`, add a small additional sweep that validates these production files too — silent drift between the production lists and the schema would defeat the layer.)

- [ ] **Step 5: Add a small dedicated test layer for production marker lists**

Create `tests/extensions/check-suppressions-files.sh`: walks `core/templates/suppressions.yaml`, `extensions/*/suppressions.yaml`, asserts each validates against `core/schema/suppressions.schema.json`. Exit 2 on any failure. Wire into `tests/run-all.sh` after the schema layer.

This is a structural-correctness layer (per the DECISIONS.md "regression layers" pattern): each shipped marker list is structurally valid; a future extension that ships a malformed file fails CI.

- [ ] **Step 6: Run `tests/run-all.sh`**

```bash
bash tests/run-all.sh
```

- [ ] **Step 7: Commit**

```bash
git add core/templates/suppressions.yaml \
        extensions/python/suppressions.yaml \
        extensions/jvm-archunit/suppressions.yaml \
        tests/extensions/check-suppressions-files.sh \
        tests/run-all.sh
git commit -m "suppression-detection: phase 7 — extension marker lists (Python + JVM + core)"
```

---

## Phase 8 — Bootstrap, scaffold, and diff producers

The reporter now needs `--diff-unified` to be supplied by the three producers (PR-driven workflow, push-driven workflow, local pre-push), and bootstrap needs to vendor `.agent-redline/suppressions.yaml` and write the policy `suppressions:` block. Existing-repo upgrade path: re-running bootstrap detects an absent block and offers to add it.

**Files:**
- Modify: `core/skill/bootstrap-mode.md` Phase 4 — vendor + policy block
- Modify: `core/templates/agent-policy.yaml.template` — add the `suppressions:` block as a commented-out placeholder, with the new `modes.perCheck.suppression` line
- Modify: `core/templates/pre-push-check.sh` — produce `git diff --unified=0` and pass `--diff-unified`
- Modify: `extensions/python/scaffold.md` — both PR-driven and push-driven CI snippets produce a unified diff and pass `--diff-unified`; vendor instructions
- Modify: `extensions/jvm-archunit/scaffold.md` — same shape
- Modify: `demo-source/.github/workflows/agent-redline.yml` — produce + pass diff
- Modify: `demo-source/scripts/agent-redline-check.sh` — same
- Modify: `demo-source-python/.github/workflows/agent-redline.yml` and the push-mode workflow — same
- Modify: `demo-source-python/scripts/agent-redline-check.sh` — same
- (Token-budget watch: `bootstrap-mode.md` ceiling is 3400; current ~3300. The vendor + block instructions are ~30 tokens; should fit. Each `scaffold.md` ceiling is 3100; current ~3000 each. Watch closely.)

- [ ] **Step 1: Re-read `docs/SKILL_AUTHORING.md`** before touching `bootstrap-mode.md` or `scaffold.md`.

- [ ] **Step 2: Update `core/skill/bootstrap-mode.md` Phase 4**

Append to the "Boundary-rule backend artifacts" section, as a separate Phase 4 step (label it "Suppression marker list"):

```markdown
**Suppression marker list (Phase 4 step).** If the chosen extension
ships `suppressions.yaml`, copy it to `.agent-redline/suppressions.yaml`
in the consuming repo. If no extension is chosen (zone-only), copy
`core/templates/suppressions.yaml` instead. Then write the policy
block:

```yaml
suppressions:
  useExtensionDefaults: true
  exemptPaths:
    - "**/tests/**"            # default; team accepts, narrows, or removes
```

For repos re-running bootstrap with a v0.2 policy that has no
`suppressions:` block, ask whether to add it (alongside vendoring the
file). Decline is allowed; nothing forces opt-in. Without the block,
suppression detection stays OFF (compatibility per spec §1.4).
```

- [ ] **Step 3: Update `core/templates/agent-policy.yaml.template`**

Add a commented-out block above the `excludes:` section:

```yaml
# suppressions:
#   useExtensionDefaults: true
#   exemptPaths:
#     - "**/tests/**"
#   add:
#     inlineComments: ["# custom-marker"]
#   remove:
#     inlineComments: ["# pragma: no cover"]
```

And in `modes.perCheck`, add a line:

```yaml
modes:
  default: shadow
  perCheck:
    boundary_violation: binding
    suppression: binding   # hardcoded default; included for visibility
```

- [ ] **Step 4: Update `core/templates/pre-push-check.sh`**

Add a `git diff --unified=0` step alongside the existing `--name-only` / `--numstat`:

```bash
git diff --unified=0 "$BASE_SHA"..."$HEAD_SHA" > "$DIFF_UNIFIED"
ARGS+=(--diff-unified "$DIFF_UNIFIED")
```

Provide the same defensive fallback the existing script uses (`set -e` -friendly, default value if empty diff).

- [ ] **Step 5: Update `extensions/python/scaffold.md` and `extensions/jvm-archunit/scaffold.md`**

In each scaffold's CI run-block (both PR-driven and push-driven sections), add the diff-producer step and the new flag:

```yaml
- name: Produce diff inputs
  run: |
    git diff --name-only "$BASE_SHA" "$HEAD_SHA" > build/changed-files.txt
    git diff --numstat   "$BASE_SHA" "$HEAD_SHA" > build/lines-per-file.txt
    git diff --unified=0 "$BASE_SHA" "$HEAD_SHA" > build/diff-unified.patch
    ...
- name: Run reporter
  run: |
    python scripts/agent-redline-report.py \
      --policy agent-policy.yaml \
      --changed-files build/changed-files.txt \
      --lines-per-file build/lines-per-file.txt \
      --diff-unified build/diff-unified.patch \
      ...
```

Also document at the top of each scaffold how to vendor `suppressions.yaml`:

```markdown
**Vendor the suppression marker list** — copy
`extensions/<this-extension>/suppressions.yaml` to
`.agent-redline/suppressions.yaml` in the consuming repo. The reporter
reads from the vendored file at runtime; it does not reach back to the
extension. (For zone-only repos that pick no extension, bootstrap
copies `core/templates/suppressions.yaml` instead.)
```

Run the budget check after each scaffold edit.

- [ ] **Step 6: Update demo-source workflows + pre-push scripts**

Apply the same producer + flag updates to:
- `demo-source/.github/workflows/agent-redline.yml`
- `demo-source/scripts/agent-redline-check.sh`
- `demo-source-python/.github/workflows/agent-redline.yml`
- `demo-source-python/push-mode/...` (the push-mode workflow)
- `demo-source-python/scripts/agent-redline-check.sh`

Also add `.agent-redline/suppressions.yaml` to both `demo-source/` and `demo-source-python/`, and add the `suppressions:` block to both demo policies (`demo-source/agent-policy.yaml`, `demo-source-python/agent-policy.yaml`) per spec §5 ("Demo policies"):

```yaml
# in agent-policy.yaml
suppressions:
  useExtensionDefaults: true
  exemptPaths:
    - "src/test/**"            # JVM demo
    # - "tests/**"             # Python demo
```

(JVM uses `src/test/**` already; Python uses `tests/**`. Match what each demo's blue zone lists.)

- [ ] **Step 7: Run scaffold validation layers**

```bash
bash tests/scaffold-ci/check-scaffold-ci.sh             # Layer 7
bash tests/scaffold-ci-e2e/check-scaffold-ci-e2e.sh     # Layer 8
bash tests/scaffold-spring-e2e/check-scaffold-spring-e2e.sh   # Layer 9 (skips if gradle absent)
```

Layers 7–9 already enforce that the run-block follows the canonical pattern (set +e + EXIT capture + sticky-comment OR enforce step). Adding `--diff-unified` doesn't break the pattern — but verify nothing regresses.

- [ ] **Step 8: Run `tests/sync/`, `tests/links/`, `tests/skill-yaml/`, `tests/skill-refs/`, full `tests/run-all.sh`**

```bash
bash tests/run-all.sh
```

Expected: every layer green or cleanly skipped. The sync layer (Layer 19) checks that `scripts/sync-demo.sh` produces the expected branch shape — confirm both demos still sync cleanly.

- [ ] **Step 9: Commit**

```bash
git add core/skill/bootstrap-mode.md \
        core/templates/agent-policy.yaml.template \
        core/templates/pre-push-check.sh \
        extensions/python/scaffold.md \
        extensions/jvm-archunit/scaffold.md \
        demo-source/.github/workflows/agent-redline.yml \
        demo-source/scripts/agent-redline-check.sh \
        demo-source/.agent-redline/suppressions.yaml \
        demo-source/agent-policy.yaml \
        demo-source-python/.github/workflows/agent-redline.yml \
        demo-source-python/push-mode \
        demo-source-python/scripts/agent-redline-check.sh \
        demo-source-python/.agent-redline/suppressions.yaml \
        demo-source-python/agent-policy.yaml
git commit -m "suppression-detection: phase 8 — bootstrap vendor + scaffold + diff producers"
```

---

## Phase 9 — Demo PR scenarios (Layer 5 e2e validation)

Spec §5 mandates `demo/suppression-change-pr` for both demo repos. The e2e demo guideline (DECISIONS.md "A feature isn't done until the demo proves it end-to-end") makes this a hard requirement, not nice-to-have. **Without a live PR producing the expected verdict on real GitHub Actions, the feature is not done.**

**Files:**
- Create: `demo-source/pr-scenarios/suppression-change/` with `branch.txt`, `description.md`, `apply.sh`, `expected-verdict.md`, `labels.txt`
- Create: `demo-source-python/pr-scenarios/suppression-change/` with the same five files
- Modify: `scripts/sync-demo.sh` and `scripts/sync-python-demo.sh` to recognise the new scenario (typically these scripts iterate every directory under `pr-scenarios/`, so no code change needed — verify)

- [ ] **Step 1: Inspect both sync scripts**

```bash
grep -n "pr-scenarios" scripts/sync-demo.sh scripts/sync-python-demo.sh
```

If the scripts iterate `pr-scenarios/*/` automatically, no code change is needed. If they hardcode names, add the new scenario.

- [ ] **Step 2: Write `demo-source/pr-scenarios/suppression-change/`**

`branch.txt`:
```
demo/suppression-change-pr
```

`description.md`:
```markdown
## Suppression marker added on a guarded surface

This PR adds `// @SuppressWarnings("ArchUnit")` to `OrderController.java`
to make a hypothetical ArchUnit failure go away. The reporter detects
the added suppression and routes the PR to architecture-review.

Demonstrates the suppression-detection feature (spec §1.1, §2).
```

`apply.sh`: edits `src/main/java/com/example/orders/api/OrderController.java` to add `@SuppressWarnings("ArchUnit")` above the class declaration. Idempotent (skip if already applied).

`expected-verdict.md`: documents the verdict shape — `RED`, `architecture-review` checkpoint required, suppressions table with one entry, exit code `0` only when the `architecture-reviewed` label is applied.

`labels.txt`:
```
architecture-reviewed
```

- [ ] **Step 3: Write `demo-source-python/pr-scenarios/suppression-change/`**

Same five files. `apply.sh` adds `# noqa: import-linter` (or similar) to a domain-layer Python file in the demo (e.g., `src/example_python/domain/order.py`). Pick whichever red-zone path the demo policy actually has.

- [ ] **Step 4: Run sync dry-runs locally**

```bash
bash scripts/sync-demo.sh --target /tmp/agent-redline-demo --dry-run
bash scripts/sync-python-demo.sh --target /tmp/agent-redline-python-demo --dry-run --with-pr-branches
```

(If `--dry-run` doesn't exist, run against a temp target.) Confirm both new scenarios appear in the produced branch list.

- [ ] **Step 5: Run `tests/sync/` (Layer 19)**

```bash
bash tests/sync/check-sync.sh
```

Verifies `sync-demo.sh` produces the expected branch shape from `demo-source/`.

- [ ] **Step 6: Run full `tests/run-all.sh`**

- [ ] **Step 7: Push the demo branches to GitHub (manual, recorded as plan steps so they aren't forgotten)**

```bash
bash scripts/sync-demo.sh         --target ../agent-redline-demo         --with-pr-branches --push
bash scripts/sync-python-demo.sh  --target ../agent-redline-python-demo  --with-pr-branches --push
```

Open `demo/suppression-change-pr` on each repo. Confirm:

- The agent-redline workflow runs.
- The PR comment shows the new "Suppressions added" table.
- The `architecture-review` checkpoint row appears.
- Without the label: workflow exit code is 2 (binding default for suppression).
- After applying `architecture-reviewed`: re-run, exit code 0, checkpoint row flips to `[x]`.

Repeat for the Python demo, using whatever the demo policy's red-zone path is.

- [ ] **Step 8: Capture the verdict comment from each live PR**

Update each scenario's `expected-verdict.md` with the actual comment text under a "Verified live on agent-redline-demo PR #N" header (matches the existing convention for `red-with-checkpoint/expected-verdict.md`).

- [ ] **Step 9: Commit**

```bash
git add demo-source/pr-scenarios/suppression-change \
        demo-source-python/pr-scenarios/suppression-change \
        scripts/sync-demo.sh scripts/sync-python-demo.sh
git commit -m "suppression-detection: phase 9 — demo PR scenarios + live verification"
```

---

## Phase 10 — SPEC, DECISIONS, POLICY_SCHEMA, skill simulation, final review

Documentation updates that lock the design decisions into source of truth, plus the C-series skill simulation (spec §5 "Skill simulation"), plus final cross-check.

**Files:**
- Modify: `docs/SPEC.md` — §4 vocabulary, §15.5 changelog, §15.3 trim
- Create: an entry in `docs/DECISIONS.md` covering the vendored-file contract, the naive-fire algorithm, and the §1.4 compatibility rule
- Modify: `docs/POLICY_SCHEMA.md` — `suppressions` block, vendored-file location, compatibility rule
- (Optional but recommended) Create: a C-series skill-simulation note that records "with-skill agent refused, without-skill agent reached for `# noqa`" — same shape as the C2 simulation in `.local/calibration/`

- [ ] **Step 1: Update `docs/SPEC.md` §4 (vocabulary)**

Add a new row to the vocabulary table:

```markdown
| **Suppression marker** | A syntactic construct that silences a check, weakens a rule, or extends an allowlist (e.g. `# noqa`, `@SuppressWarnings`, `ignore_imports`). The set is finite and per-stack; declared in `.agent-redline/suppressions.yaml`. Adding a marker on a guarded surface routes the PR to `architecture-review`. |
```

- [ ] **Step 2: Update `docs/SPEC.md` §15.5 (v0.2 changelog)**

Add a new bullet describing the suppression-detection feature, the `suppressions:` policy block, the vendored-file contract, the §1.4 compatibility rule, and the `modes.perCheck.suppression` enum value. Cross-link the spec at `docs/superpowers/specs/2026-06-10-suppression-detection-design.md`.

(Strictly speaking this is a v0.3 feature. Decide with the user during plan review whether this lands as v0.2.x patch or v0.3 — the plan defaults to "v0.3 changelog entry" since the feature adds new policy fields.)

- [ ] **Step 3: Trim `docs/SPEC.md` §15.3 roadmap**

Remove the P0 #1 (reporter scans for suppression markers) and P0 #4 (skill refuses suppressions on guarded surfaces) entries, replacing each with a one-line "shipped in v0.3 — see [§15.6 changelog](#155-what-v02-adds)" pointer (or whatever the new changelog section is called).

- [ ] **Step 4: Update `docs/POLICY_SCHEMA.md`**

Add a new section documenting the `suppressions:` block: every field, the `useExtensionDefaults` default, the `add` / `remove` set arithmetic, the `exemptPaths` glob list, the vendored-file location (`.agent-redline/suppressions.yaml`), and the §1.4 compatibility rule (absent block → detection OFF).

Also add a row to the `modes.perCheck` documentation listing `suppression` (with the hardcoded `binding` default and a pointer to spec §2.4).

- [ ] **Step 5: Add a `docs/DECISIONS.md` entry**

Mirror the existing entry style. Cover:

- **Decision:** the three core choices — (a) naive added-line scanning (no equivalence), (b) vendored-defaults file at a fixed path (no runtime extension reachback), (c) absent block = detection OFF (compatibility).
- **Alternatives considered:** lift verbatim from spec §6 — set-difference, count-based equivalence, per-position pairing, generic CI-bypass detection, justification-required workflow, Semgrep, working-tree scanning. Each with a one-line rationale for rejection.
- **Rationale:** the asymmetry argument (visible-and-cheap false positive vs silent-and-load-bearing false negative); the symmetry with the existing `boundary-rule` design ("every forbidden import on the head violates; we don't try to be clever about whether this diff introduced it").
- **Test guard:** the seven golden fixtures from Phase 5; specifically `suppression-and-boundary-violation` covers the `cmt_000010` independence rule and `policy-without-suppressions-block` covers compatibility.
- **Revisit if:** spec §7 open questions (reformat false-positive rate dilutes the signal; per-rule vs blanket suppressions; first-PR-after-bootstrap shock; backend allowlist files outside standard locations).

- [ ] **Step 6: Run skill-simulation (C-series, optional but recommended)**

The python-support feature ran C1/C2 simulations as part of validation. For this feature: present a simulated agent task to a Claude Code session: "make this import-linter rule stop firing." Run twice — once with the new operating-mode bullet + boundary-violation Suppressions section, once without (revert the file briefly). Record observed behavior in `.local/SUPPRESSION_SIMULATION_<date>.md`. Expected: with-skill agent refuses the suppression and either fixes the structure or proposes an explicit `ignore_imports` edit (itself red-zone). Without the rule, the agent reaches for `# noqa`.

This is operator-driven (Layer 4 of `docs/VALIDATION.md`); not gated by CI.

- [ ] **Step 7: Run full `tests/run-all.sh`** end-to-end one final time:

```bash
bash tests/run-all.sh
```

Every layer green. Confirm both demo repos still sync cleanly via Layer 19.

- [ ] **Step 8: Re-read the spec end-to-end and cross-check the plan output**

Walk spec §1–§10 with the implementation in hand:
- §1.4 compatibility (absent block → OFF) — covered by `policy-without-suppressions-block` fixture and the `resolve_suppressions_config()` early return.
- §2.2 naive algorithm — covered by the scanner unit tests + reformat-fires fixture.
- §2.3 cmt_000010 (matches feed both consumers) — covered by `suppression-and-boundary-violation` fixture and the explicit `_required_checkpoints()` wiring test.
- §2.4 hardcoded binding default — covered by the unit test on `_binding()`.
- §5 fixtures — all seven golden fixtures plus the schema fixtures plus both demo PRs.
- §6 alternatives — captured in the new DECISIONS.md entry; do not let later phases re-introduce them.

If anything is missing, add a step. Do not skip review.

- [ ] **Step 9: Commit + final tag preparation**

```bash
git add docs/SPEC.md docs/DECISIONS.md docs/POLICY_SCHEMA.md
git commit -m "suppression-detection: phase 10 — SPEC + DECISIONS + POLICY_SCHEMA"
```

- [ ] **Step 10: Update memory**

- Delete `suppression-detection-feature-in-progress.md`.
- Create `suppression-detection-feature-shipped.md` (`type: project`) summarizing what landed and pointing at this plan.
- Update `MEMORY.md` index.

- [ ] **Step 11: Open the merge PR**

PR description: a paragraph summary; bullet list of phases; the seven golden fixtures and the two demo PRs as evidence; explicit note that the §1.4 compatibility rule is preserved (existing v0.2 policies validate and behave unchanged). Get human review per the project's own architecture-review checkpoint.

---

## Risks tracked

- **Token budgets on `operating-mode.md` and `boundary-violation.md`.** Spec §5.1 estimates +60 / +120 tokens; both files have headroom but not infinite. If a budget breach surfaces at Phase 6, trim sibling content; do NOT bump the ceiling.
- **`bootstrap-mode.md` is at ~3300/3400.** Phase 8 adds the vendor + policy-block instructions. If close, the lever is to compress the existing Phase-4 prose, not to bump.
- **`scaffold.md` ceilings (3100 each).** The producer + flag changes add ~30 tokens per scaffold. Tight but should fit.
- **Reporter algorithm pressure.** Future contributors will see reformat false positives and reach for set-difference. Spec §6 is the load-bearing rationale. Do NOT change the algorithm without re-reading §6 in full.
- **Sync-demo / sync-python-demo path drift.** If either script hardcodes the existing scenario list, Phase 9's new scenario won't sync; the symptom is the live demo PR being absent. Verify in Phase 9 step 1.
- **Schema-validity of vendored files in production lists.** Phase 7 adds a dedicated test layer; without it, a typo in `extensions/python/suppressions.yaml` would only surface when an adopter runs into it.
- **Per-fixture `.agent-redline/suppressions.yaml` resolution.** Phase 5 step 1 must call `resolve_suppressions_config(repo_root=fixture)` instead of `repo_root=Path(".")`. A bug here would cause every fixture to read the production marker list (wrong list) or fail (path mismatch). Tests catch it.

## Notes on autonomy

- This is a public open-source repo. No SAP / XLM / CLM / Loyalty / Pelican / internal-service-name terminology in any committed file. The `loyalty` strings in spec examples are illustrative only — fixtures use `example`, `myapp`, `orders`.
- agent-redline governs itself. Classify before editing. Do not silently weaken the project's own architecture-test files or `agent-policy.yaml`. Do not add suppressions on the project's own guarded surfaces (the `agent-redline` dogfood policy applies here).
- Validation has five layers (`docs/VALIDATION.md`). Layers 0–3 mechanical (CI). Layer 4 (operator) is the optional Phase-10 simulation; Layer 5 (live demo) is the mandatory Phase-9 demo PRs. Both demo PRs must produce the expected verdict on real GitHub before this feature is "done."
- A feature isn't done until the demo proves it end-to-end. See DECISIONS.md "A feature isn't done until the demo proves it end-to-end."

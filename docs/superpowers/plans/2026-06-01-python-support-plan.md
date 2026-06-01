# Python support — implementation plan

**Spec:** `docs/superpowers/specs/2026-06-01-python-support-design.md`. Read it first.

**Resume protocol:** find the first phase whose checkbox is unchecked, do it, run its verification gate, commit, move on. Each phase's verification MUST pass before the next phase begins. `bash tests/run-all.sh` must be green at the end of every phase that touches code.

**Commit cadence:** one commit per phase, prefixed `python-support: phase N — <summary>`. Push at end of each phase.

---

## Phase 0 — Setup (durable state, no code) ✅

- [x] Spec written: `docs/superpowers/specs/2026-06-01-python-support-design.md`
- [x] Plan written: this file
- [x] Memory anchor: `python-support-feature-in-progress.md`
- [x] `docs/superpowers/{specs,plans}/` created

**Verification:** files exist; spec is internally consistent (already self-reviewed during writing).

**Commit:** `python-support: phase 0 — spec and plan`

---

## Phase 1 — Reporter generalisation

Add `json-violations` as a second supported boundary output format. Make the reporter dispatch on the policy's `boundaryAdapter` block.

### 1.1 Schema for `json-violations`

- [ ] Create `core/schema/boundary-violations.schema.json` with the schema in spec §3.1.
- [ ] Update `tests/schema/check-schema.py` to validate this schema (its own self-validity, draft-2020-12).

### 1.2 Reporter parser

- [ ] Add `parse_json_violations(text: str) -> list[BoundaryViolation]` to `core/reporter/reporter.py`. Validate against the schema; return `[]` on parse failure with a clear stderr message.
- [ ] Source field on `BoundaryViolation` set from the JSON's `source` (default `"backend"`).

### 1.3 Reporter CLI

- [ ] Add `--boundary-report <path>` and `--boundary-format <junit-xml|json-violations|none>`.
- [ ] Keep `--archunit-xml` working as a deprecated alias (`--boundary-report <path> --boundary-format junit-xml`). Print a deprecation note to stderr when used.
- [ ] When neither flag is passed, fall back to the policy's `boundaryAdapter` block (`outputFormat`, `outputPath`). When `outputFormat: none`, skip parsing entirely.

### 1.4 Policy schema

- [ ] Add `boundaryAdapter` to `core/schema/agent-policy.schema.json`. Optional. Required nested fields when present: `outputFormat` (enum: `junit-xml`, `json-violations`, `none`), `outputPath` (string, required when `outputFormat != none`), `violationFilter` (object, optional, only meaningful for `junit-xml`).

### 1.5 Tests

- [ ] Unit tests in `tests/reporter/test_reporter_unit.py` for `parse_json_violations` (happy path, malformed JSON, missing required fields, schema-violating input).
- [ ] New golden fixture directory `tests/reporter/boundary-violation-json/` containing `policy.yaml`, `changed-files.txt`, `violations.json`, `expected-verdict.json`. Wire into `check-reporter.py`.
- [ ] Add a fixture exercising `boundaryAdapter` block in policy (no `--boundary-format` flag passed; reporter reads it from policy).
- [ ] Confirm all existing fixtures still pass — they pass `--archunit-xml` which is still accepted.

### Verification gate

```
bash tests/run-all.sh
```

Must pass green. The new layer must show among the passing layers.

**Commit:** `python-support: phase 1 — reporter generalisation (json-violations format)`

---

## Phase 2 — Python extension

Author the extension files at `extensions/python/`.

### 2.1 Skeleton

- [ ] Create the directory structure per spec §4.
- [ ] Write `README.md` — what stack, when to pick it, link to the three shapes.
- [ ] Write `adapter.yaml` exactly as in spec §4.2.

### 2.2 Profile

- [ ] Write `profile.md` with the three-shape structure from spec §4.5. Include explicit detection signals and zone defaults for each shape, and the Django addendum.
- [ ] Include "Default PR-size thresholds" section copy-pasteable into a generated policy.
- [ ] Gotchas section: dynamic imports, TYPE_CHECKING, namespace packages, src layout.

### 2.3 Adapter script

- [ ] Write `extensions/python/scripts/run-import-linter.py` per spec §4.1.
- [ ] Pin import-linter version range. Defensive `ImportError` handling that prints the supported range.
- [ ] Standalone-runnable: a `--help` mode that documents the CLI; clean exit codes.
- [ ] A small self-test fixture: `extensions/python/scripts/_test_fixture/` with a tiny package and a contract that intentionally breaks. The smoke test (Phase 6) uses this.

### 2.4 Scaffold

- [ ] Write `scaffold.md` per spec §4.3 — install line, contract generation, CI snippet, pre-push integration. Include the Django addendum's bootstrap notes.

### 2.5 Operating

- [ ] Write `operating.md` per spec §4.4.

### Verification gate

- [ ] `bash tests/run-all.sh` still green.
- [ ] `python extensions/python/scripts/run-import-linter.py --help` returns 0 and prints usable help.
- [ ] Manual: with a fresh venv and `pip install 'import-linter>=2.0,<3'`, run the adapter script against a hand-built tiny project that breaks a layers contract. Confirm:
  - Exit code is 1.
  - JSON output validates against `boundary-violations.schema.json`.
  - Feeding the JSON into the reporter (`--boundary-report ... --boundary-format json-violations`) produces a `BOUNDARY_VIOLATION` verdict.

**Commit:** `python-support: phase 2 — Python extension (profile, scaffold, adapter)`

---

## Phase 3 — Bootstrap awareness

Make the bootstrap skill recognise Python repos and route them to the Python extension.

- [ ] Edit `core/skill/bootstrap-mode.md` Phase 1: extend the inspection list with explicit Python signals (`pyproject.toml`, `setup.py`, `manage.py`, `requirements*.txt`, `dags/`, `notebooks/`, framework deps).
- [ ] Add Python to the "Propose a language extension" decision tree alongside Spring.
- [ ] Add a short "Python shape selection" subsection that summarises the three shapes and the tie-breakers when multiple match.
- [ ] Re-read `docs/SKILL_AUTHORING.md` before editing — per the [[skill-authoring-discipline]] memory rule. Audit edits against its checklist.

### Verification gate

- [ ] `bash tests/run-all.sh` still green (the `links` and `package` checks will catch missing files / broken cross-refs).
- [ ] Manual review: read `bootstrap-mode.md` end-to-end; the Python additions follow the same conversational pattern as Spring; no internal terminology snuck in (per [[no-internal-terminology]]).

**Commit:** `python-support: phase 3 — bootstrap recognises Python`

---

## Phase 4 — EXTENSIONS.md correction

Ship the spec §5 corrections to the public extension contract.

- [ ] Edit `docs/EXTENSIONS.md`:
  - Update the "What an extension is" section to reflect that scripts are permitted.
  - Update the "What an extension does NOT own" section to remove the misleading "no scripts" line and replace with the narrow constraints from spec §5.
  - Add a new section: "Backends without machine-readable output" describing the `json-violations` adapter pattern.
  - Update the recommended-backends table footnote: the `outputFormat` choices include `json-violations`.
- [ ] Add the corresponding `DECISIONS.md` entry (spec §8 item 3).

### Verification gate

- [ ] `bash tests/run-all.sh` green (links check picks up any broken refs).
- [ ] Read the resulting EXTENSIONS.md end-to-end; check that the three reasons "scripts are now allowed" are clearly justified rather than buried.

**Commit:** `python-support: phase 4 — EXTENSIONS.md: scripts admitted as a narrow exception`

---

## Phase 5 — Python demo

Build the e2e demo. Mirror what `agent-redline-demo` does for Spring.

### 5.1 Demo source in this repo

- [ ] Create `demo-source-python/` containing the canonical demo files (mirrors `demo-source/` for Java).
- [ ] Build a minimal layered FastAPI service under `src/orders/{api,application,domain,infrastructure}/`.
- [ ] Write `pyproject.toml` with `[tool.importlinter]` contracts.
- [ ] Write `agent-policy.yaml` for the demo (output of running bootstrap against this layout).
- [ ] Write `.github/workflows/agent-redline.yml` — boundary job + reporter job.
- [ ] Write `scripts/agent-redline-check.sh` — local pre-push script.

### 5.2 Three canonical PR scenarios

Create the same three-scenario layout as `demo-source/pr-scenarios/`:
- [ ] `pr-scenarios/blue-only/` — adds `tests/test_isolated_util.py`. Expected: BLUE.
- [ ] `pr-scenarios/red-with-checkpoint/` — modifies `src/orders/domain/repositories/orders_repo.py`. Expected: RED + `architecture-review` checkpoint; passes when `architecture-reviewed` label applied.
- [ ] `pr-scenarios/boundary-violation/` — adds an import in `src/orders/domain/order.py` from `src/orders/infrastructure/db/sqlalchemy_session.py`. Expected: BOUNDARY_VIOLATION; CI red.

### 5.3 Sync infrastructure

- [ ] Write `scripts/sync-python-demo.sh` modelled on `scripts/sync-demo.sh`. Or extend `sync-demo.sh` with a `--target python` flag — pick whichever is the smaller diff.
- [ ] Add a `tests/sync/test-sync-python-demo.sh` parallel to the existing sync test.

### 5.4 The actual demo repo

- [ ] Create the GitHub repo `agent-redline-python-demo` (likely the user does this manually; if the user has the GitHub CLI authenticated and configured, can attempt via `gh`).
- [ ] Run sync to push the canonical contents.
- [ ] Open the three demo PRs.
- [ ] Confirm each PR's CI run produces the expected verdict.

### Verification gate

- [ ] `bash tests/run-all.sh` green.
- [ ] In the demo repo: the three PRs visibly show BLUE / RED-checkpoint-satisfied-green / BOUNDARY_VIOLATION-red, mirroring the Java demo.

**Commit:** `python-support: phase 5 — Python demo end-to-end`

---

## Phase 6 — Validation harness

Tests that bind the Python extension into the project's test layers.

### 6.1 Extension smoke test

- [ ] Create `tests/extensions/python/check-extension.sh`. It should:
  - Set up a venv (skip-if-no-python detection like the Spring test's gradle skip).
  - `pip install 'import-linter>=2.0,<3'`.
  - Use the `extensions/python/scripts/_test_fixture/` Phase 2 fixture.
  - Run the adapter script. Assert JSON validates against schema. Assert exit code 1.
  - Feed JSON into reporter. Assert `BOUNDARY_VIOLATION` verdict.

### 6.2 Wire into run-all.sh

- [ ] Add a layer entry in `tests/run-all.sh` for the Python extension test, with a `REQUIRES_PYTHON_VENV` marker that gracefully skips when prereqs are missing (matching the existing optional-Gradle pattern).

### 6.3 Schema validation extension

- [ ] Update `tests/schema/check-schema.py` to also validate `boundary-violations.schema.json`.

### 6.4 Package test

- [ ] Update `tests/package/check-package.sh` to assert that `dist/agent-redline/extensions/python/` exists after running `package-skill.sh` and contains the five files plus the `scripts/` directory.

### 6.5 Calibration story

- [ ] If the `agent-redline-tune.py` script needs updates to handle the Python adapter, do them now. Otherwise, just verify the existing tuner works with the Python demo's policy.

### Verification gate

- [ ] `bash tests/run-all.sh` green, including the new Python layer when prereqs are met.
- [ ] Run `scripts/package-skill.sh` and confirm the dist contains everything Python-related.
- [ ] Manual: review the package-skill.sh changes; ensure the script copy preserves executability.

**Commit:** `python-support: phase 6 — validation harness for Python`

---

## Phase 7 — Documentation cleanup

The single coherent docs pass that announces the feature.

- [ ] `README.md` — Python moves out of "roadmap" in the language-extensions table.
- [ ] `docs/SPEC.md` §15.3 — Python extension landed; reporter dispatch on `outputFormat` implemented.
- [ ] `docs/POLICY_SCHEMA.md` — document the new `boundaryAdapter` policy block.
- [ ] `docs/DECISIONS.md` — three new entries (per spec §8).
- [ ] `docs/CI_INTEGRATION.md` — add a Python-flavoured CI snippet alongside the Spring one.
- [ ] `docs/FAQ.md` — add an entry "How do I add Python support to my repo?" pointing at bootstrap.
- [ ] Update `INSTALL.md` only if the install commands change (they shouldn't — the skill packaging covers the new extension automatically).

### Verification gate

- [ ] `bash tests/run-all.sh` green (links check catches stale references).
- [ ] Read each updated doc end-to-end; check for [[no-internal-terminology]] compliance — no SAP / CLM / XLM / Pelican / flock / etc.
- [ ] Sanity check that the README's three Pull-Request demo links still work for the Java demo, and the new ones work for the Python demo.

**Commit:** `python-support: phase 7 — docs published`

---

## Phase 8 — Final review

Adversarial pass before declaring done.

- [ ] Read the spec front to back. Anything that didn't make it into code? Anything that drifted?
- [ ] Read the README from a "I'm a Python user with no JVM context" perspective. Is the path from "I want this on my repo" to a green CI run obvious?
- [ ] Read EXTENSIONS.md from a "I want to write a Go extension" perspective. Is the script-allowed update clear and constrained?
- [ ] Run `bash tests/run-all.sh` one final time.
- [ ] Manual run-through: clone the demo repo into a clean directory, run `bash scripts/agent-redline-check.sh`, confirm it works.
- [ ] Update the `python-support-feature-in-progress` memory: change `type: project` to `type: feedback` (or delete it) once the feature ships. Note the final demo repo URL.

### Verification gate

- [ ] All previous checkboxes ticked.
- [ ] No open questions in the spec or this plan.

**Final commit:** `python-support: shipped`

---

## Risks tracked during execution

If any of these surface, stop, document in the spec, and adjust:

- **import-linter internal API moved between releases** — pin tightly, document the version constraint clearly.
- **Demo repo creation needs GitHub auth not present in this environment** — user does it manually; plan stays valid, just needs the user's action to complete Phase 5.4.
- **Reporter CLI back-compat broken** — any existing CI that uses `--archunit-xml` must keep working. Test this explicitly in Phase 1.5.
- **Windows path handling** — the existing reporter uses POSIX-style globs against forward-slash paths; the demo's path strings need to be consistent. Test on Windows during phase 5.
- **Policy schema change is breaking** — if any existing repo has a `boundaryAdapter` field already (it doesn't, but check), don't collide.

## Notes on autonomy

- **Compaction-safe:** spec + this plan + the memory anchor are the durable state. On wakeup after compaction, read the memory, find the first unchecked phase, continue.
- **No user gates:** the user said "make this happen autonomously". Don't pause for approval between phases. Surface surprises (genuine new information, contradictions in the spec) — don't surface "should I continue".
- **Delegate when sensible:** Phase 5 (the demo) has a lot of file creation. If a sub-task is well-scoped (e.g. "create the FastAPI service skeleton") and the parent context is getting heavy, dispatch a subagent.

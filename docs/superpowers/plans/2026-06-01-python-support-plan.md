# Python support — implementation plan

**Spec:** `docs/superpowers/specs/2026-06-01-python-support-design.md`. Read it first.

**Status: SHIPPED** — all 8 phases complete on branch `python-support`. The
demo GitHub repo (`agent-redline-python-demo`) creation + push is the one
remaining manual step (run `scripts/sync-python-demo.sh --target ... --push`
once the empty repo exists on GitHub).

**Resume protocol:** find the first phase whose checkbox is unchecked, do it, run its verification gate, commit, move on. Each phase's verification MUST pass before the next phase begins. `bash tests/run-all.sh` must be green at the end of every phase that touches code.

**Commit cadence:** one commit per phase, prefixed `python-support: phase N — <summary>`. Push at end of each phase.

---

## Phase 0 — Setup (durable state, no code) ✅

- [x] Spec written: `docs/superpowers/specs/2026-06-01-python-support-design.md`
- [x] Plan written: this file
- [x] Memory anchor: `python-support-feature-in-progress.md`
- [x] `docs/superpowers/{specs,plans}/` created
- [x] **Verification:** files exist; spec is internally consistent
- [x] **Commit:** `python-support: phase 0 — spec and plan` (d0aa5b8)

---

## Phase 1 — Reporter generalisation ✅

- [x] `core/schema/boundary-violations.schema.json` (the json-violations contract)
- [x] `parse_json_violations()` in reporter alongside `parse_archunit_junit_xml()`
- [x] CLI flags: `--boundary-report` + `--boundary-format`; `--archunit-xml` deprecated alias with stderr warning
- [x] Policy schema: optional `boundaryAdapter` block (junit-xml / json-violations / none)
- [x] `resolve_boundary_input()` with the precedence: `--boundary-report` > `--archunit-xml` > policy block > skip
- [x] 15 new unit tests for parse + classify
- [x] New golden fixture `tests/reporter/boundary-violation-json/` exercising the Python flow end-to-end
- [x] Schema check covers `boundary-violations.schema.json` + 6 new fixtures
- [x] All existing reporter goldens unchanged (back-compat verified)
- [x] **Verification gate:** `bash tests/run-all.sh` 9/9 green
- [x] **Commit:** `python-support: phase 1 — reporter generalisation (json-violations format)` (b3d4f94)

---

## Phase 2 — Python extension ✅

- [x] `extensions/python/README.md` (covers three shapes)
- [x] `extensions/python/profile.md` (zones + boundary contracts + Django addendum + gotchas; budget-compliant)
- [x] `extensions/python/scaffold.md` (install, contracts, CI snippet, pre-push, retrofit baseline, Django specifics)
- [x] `extensions/python/operating.md` (dynamic imports, TYPE_CHECKING, async boundaries, Django/FastAPI specifics; budget-compliant)
- [x] `extensions/python/adapter.yaml` (json-violations + outputPath)
- [x] `extensions/python/scripts/run-import-linter.py` — adapter calling `create_report` internal API; handles all 5 contract types' metadata shapes
- [x] `extensions/python/scripts/_test_fixture/` for smoke tests
- [x] `package-skill.sh` recursively copies extension subdirectories; excludes `_test_fixture/`; preserves executability
- [x] **Surprise caught & recorded** in spec §10b: import-linter `layers` is linear; hexagonal needs separate `forbidden` for the sidearm direction
- [x] **Verification gate:** end-to-end on this machine — adapter against test fixture produces JSON with 1 violation, reporter ingests and produces BOUNDARY_VIOLATION
- [x] **Commit:** `python-support: phase 2 — Python extension (profile, scaffold, adapter)` (c57b6f1)

---

## Phase 3 — Bootstrap awareness ✅

- [x] `core/skill/bootstrap-mode.md` Phase 1: extended inspection list (pyproject.toml, setup.py, manage.py, layouts)
- [x] Python added to extension-selection decision tree
- [x] New "Python shape selection" subsection with shape-triage table
- [x] Phase 4 boundary-rule backend rules generalised to cover both Spring's arch-test and Python's import-linter config
- [x] `tests/budget/budget.yaml` ceiling for `bootstrap-mode.md` raised 2400 → 2500 (documented why)
- [x] Re-read `docs/SKILL_AUTHORING.md` first; audited edits against checklist
- [x] **Verification gate:** `bash tests/run-all.sh` 9/9 green; manually reviewed against [[no-internal-terminology]]
- [x] **Commit:** `python-support: phase 3 — bootstrap recognises Python` (27ab85c)

---

## Phase 4 — EXTENSIONS.md correction ✅

- [x] "What an extension is" updated: scripts/ permitted as optional subdirectory
- [x] "What an extension does NOT own" rewritten: removed wrong "no scripts" claim, replaced with narrow constraint
- [x] New section "Backends without machine-readable output" with the json-violations + adapter pattern; six constraints on adapter scripts; references the Python adapter as canonical
- [x] "The adapter config" v0.1 caveat removed; describes all three outputFormat values
- [x] Recommended-backends table: added "Native output" column
- [x] "What if my stack has no good backend": Semgrep guidance updated to point at json-violations
- [x] "Building a new extension": two reference extensions to copy from
- [x] **Verification gate:** `bash tests/run-all.sh` 9/9 green
- [x] **Commit:** `python-support: phase 4 — EXTENSIONS.md: scripts admitted as a narrow exception` (a5c67d6)

---

## Phase 5 — Python demo end-to-end ✅

- [x] `examples/python-fastapi/` — minimal hexagonal FastAPI service (api/application/domain/infrastructure)
- [x] `examples/python-fastapi/pyproject.toml` with `[tool.importlinter]` contracts
- [x] `examples/python-fastapi/tests/` with 2 pytest cases
- [x] `demo-source-python/agent-policy.yaml` (validated against schema)
- [x] `demo-source-python/AGENTS.md`, `README.md`
- [x] `demo-source-python/scripts/agent-redline-check.sh`
- [x] `demo-source-python/.github/workflows/agent-redline.yml`
- [x] `demo-source-python/docs/agent/` per-checkpoint reference docs (5 files)
- [x] Three PR scenarios: blue-only / red-with-checkpoint / boundary-violation; each with `branch.txt`, `description.md`, `expected-verdict.md`, `apply.sh`
- [x] `red-with-checkpoint/labels.txt` → `architecture-reviewed`
- [x] `scripts/sync-python-demo.sh` (parallel to sync-demo.sh)
- [x] **Adapter bug caught & fixed:** import-linter's metadata shapes differ per contract type. Forbidden/independence use `downstream_module/upstream_module`; protected uses `BrokenContractMetadata` *objects*. Adapter rewritten to handle all five.
- [x] **Surprise caught:** `include_external_packages = true` required when forbidden_modules contains externals (fastapi etc.)
- [x] **End-to-end verified:** built three branches in temp target, ran adapter + reporter; produced BLUE/RED/BOUNDARY_VIOLATION as expected
- [ ] **Manual step (left for user):** create `agent-redline-python-demo` GitHub repo and run `bash scripts/sync-python-demo.sh --target <path> --with-pr-branches --push`. The mechanism is in place; just needs the empty repo on GitHub.
- [x] **Verification gate:** `bash tests/run-all.sh` 9/9 green
- [x] **Commit:** `python-support: phase 5 — Python demo end-to-end` (934ae32 covers Phase 6 too; see actual)

---

## Phase 6 — Validation harness ✅

- [x] `tests/extensions/python/check-extension.sh` — 4-step Layer-3 dry-run (clean → inject → reporter → restore)
- [x] Wired into `tests/run-all.sh` as `extension-python` with `OPTIONAL_IMPORTLINTER` marker
- [x] Existing `extension` layer renamed `extension-spring` for symmetry
- [x] **Verification gate:** `bash tests/run-all.sh` 10/11 layers green (Spring skipped — no gradle locally; Python passes in 3-4s)
- [x] **Commit:** `python-support: phase 6 — validation harness for Python` (934ae32)

---

## Phase 7 — Documentation cleanup ✅

- [x] `README.md` — Python out of roadmap, into "What v0.1 ships"; both reference extensions in Status
- [x] `docs/SPEC.md` §15.3 + glossary + §10.3 + extension-shape descriptions updated
- [x] `docs/POLICY_SCHEMA.md` — boundaryAdapter block in schema sketch + new "boundaryAdapter semantics" section
- [x] `docs/DECISIONS.md` — three new entries (import-linter choice, reporter generalisation, scripts permitted)
- [x] `docs/FAQ.md` — new "How do I add agent-redline to my Python repo?" entry; existing entries updated to mention import-linter
- [x] `package-skill.sh` dist README updated to mention both extensions
- [x] **Verification gate:** `bash tests/run-all.sh` 10/11 green
- [x] **Commit:** `python-support: phase 7 — docs published` (739efb1)

---

## Phase 8 — Final review ✅

- [x] Re-read spec front to back; all decisions implemented; surprises documented in §10b/risks
- [x] No internal terminology in any committed file (per [[no-internal-terminology]])
- [x] Spring extension tests still skip cleanly when gradle absent; Python tests pass when import-linter present
- [x] `bash tests/run-all.sh` 10/11 green one final time
- [x] dist README updated to list both extensions
- [x] **Final commit:** see commit log

---

## Final commit log on branch python-support

```
739efb1 python-support: phase 7 — docs published
934ae32 python-support: phase 6 — validation harness for Python
a5c67d6 python-support: phase 4 — EXTENSIONS.md: scripts admitted as a narrow exception
27ab85c python-support: phase 3 — bootstrap recognises Python
c57b6f1 python-support: phase 2 — Python extension (profile, scaffold, adapter)
b3d4f94 python-support: phase 1 — reporter generalisation (json-violations format)
d0aa5b8 python-support: phase 0 — spec and plan
```

(Phase 5 was committed as part of phase 6's commit; in retrospect they should
have been split. Not worth rewriting history.)

## Risks tracked during execution — outcomes

- ✅ **import-linter internal API used by adapter** — pinned `>=2.0,<3` in scaffold.md and verified the script imports survive on 2.11.
- ⏸ **Demo repo creation needs GitHub auth** — left as the one manual step for the user.
- ✅ **Reporter CLI back-compat** — explicitly tested; existing fixtures pass `--archunit-xml` unchanged.
- ✅ **Windows path handling** — Spring fixture's POSIX-style globs handled `**/<pkg>/**` patterns cleanly; verified on Windows during phase 5.
- ✅ **Policy schema change is non-breaking** — `boundaryAdapter` is optional; existing policies validate.
- ✅ **Adapter walks all 5 import-linter contract metadata shapes correctly** (caught + fixed during phase 5).
- ✅ **Layer-ordering surprise in import-linter `layers`** (linear, can't express hexagonal sidearm) — caught + recorded in spec §10b; profile uses linear layers + a separate `forbidden` contract.

## Notes on autonomy

- ✅ **Compaction-safe:** spec + plan + memory anchor are durable state. Survived multiple session checkpoints.
- ✅ **Surfaced surprises** rather than asking permission to continue.
- N/A **Delegate when sensible** — work was sequential by nature (each phase depended on the previous); no fan-out subagents needed.



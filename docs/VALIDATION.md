# Validation

How we know agent-redline works the way the spec says it does.

This is a doc about *testing the project itself*, not about how a consuming repo validates its own policy. agent-redline tests run via `tests/run-all.sh` and live under `tests/`.

## The layers

`tests/run-all.sh` runs every layer below. Layers tagged "REQUIRES" need the named runtime; "OPTIONAL" layers skip cleanly when their prerequisite is absent.

| # | Layer | What it tests | Prereq |
|---|---|---|---|
| 1 | **budget** | No skill/template/extension file exceeds its declared token ceiling | — |
| 2 | **schema** | Policies in `tests/schema/{valid,invalid}/`, `core/templates/agent-policy.yaml.template`, `dist/agent-redline/assets/templates/agent-policy.yaml.template`, and both demo policies validate correctly | python |
| 3 | **skill-yaml** | Every ` ```yaml ` block inside skill markdown that looks like a policy fragment validates against the policy schema | python |
| 4 | **skill-refs** | Every `scripts/`, `assets/`, `references/` reference in the packaged skill content resolves to either a shipped file, a documented "consuming-repo path", or a search glob | python |
| 5 | **skill-scripts-runnable** | Every CLI script in the packaged skill invokes cleanly with `--help` from a clean tempdir, without any `ModuleNotFoundError` / `ImportError` | python |
| 6 | **skill-toml** | Every `[[tool.importlinter.contracts]]` example in skill markdown validates against import-linter's actual schema (correct field names, no unknown fields). Also enforces multi-package + `allow_indirect_imports` policy | import-linter installed |
| 7 | **scaffold-ci** | Every reporter run-block in scaffold.md follows the canonical pattern (set +e + EXIT capture + GITHUB_OUTPUT publish + sticky-comment OR enforce-on-non-zero, depending on flow mode) | python |
| 8 | **scaffold-ci-e2e** | Python push-mode scaffold's reporter run-block extracted, executed against a 2-commit fixture, asserts verdict.json shape | python |
| 9 | **scaffold-spring-e2e** | Spring scaffold §6 reporter run-block extracted, executed against a Spring fixture with hand-crafted base+head OpenAPI specs, asserts apiChanges.specDiff.pathsAdded contains the expected path | python |
| 10 | **bootstrap-detect** | Six fixture repos (layered-src-fastapi, layered-flat-flask, multi-package, library, django-mysite, zone-only-airflow) each detect to the expected shape + layout per profile.md | python |
| 11 | **tuner** | Five cases: happy path (5 commits, known firing rates), empty repo, missing branch, empty commit (skipped), `--limit > available` | python |
| 12 | **pre-push** | `core/templates/pre-push-check.sh`: bash syntax, awk pipeline produces `0` on empty input, `LINES_CHANGED=${LINES_CHANGED:-0}` defensive fallback present | — |
| 13 | **reporter-goldens** | Reporter produces correct verdicts + comments for known fixtures (`tests/reporter/<scenario>/`) | python |
| 14 | **reporter-unit** | Reporter unit tests (parsers, matchers, classification) | pytest |
| 15 | **workflow-scripts** | The reporter's diff-input handling against a few canonical Git diff shapes | — |
| 16 | **links** | Every relative link in markdown files resolves | python |
| 17 | **gitignore** | Build artifacts and known-transient files are gitignored | — |
| 18 | **package** | `dist/agent-redline/` matches a freshly-built package (catches drift when sources change without re-running `package-skill.sh`) | python |
| 19 | **sync-demo** | `scripts/sync-demo.sh` produces the expected branch shape from `demo-source/` + `examples/spring-hexagonal/` | — |
| 20 | **extension-spring** | Spring extension's Layer-3 dry-run: gradle test on the fixture, inject a violation, confirm the right rule fails, restore | gradle |
| 21 | **extension-python** | Python extension's Layer-3 dry-run: import-linter against fixture, inject a forbidden import, confirm adapter emits the right violation, reporter ingests JSON, BOUNDARY_VIOLATION verdict, restore | import-linter |

The layers cluster into four kinds:

- **Schema/content correctness** (1, 2, 3, 6) — every shipped artifact matches its schema or contract.
- **Skill referential integrity** (4, 5) — the skill's docs reference what actually ships.
- **Behavioral end-to-end** (7, 8, 9, 10, 11, 13, 14, 19, 20, 21) — the reporter, scaffolds, tuner, and detection actually do what they say.
- **Hygiene** (12, 15, 16, 17, 18) — pre-push script works, links resolve, gitignore is right, package is in sync.

## What's NOT covered by `tests/run-all.sh`

### Layer 4 — Skill behavior in a real harness

The conversational layer of bootstrap-mode and operating-mode requires running the actual skill against a harness (Claude Code, Codex, Cursor, Gemini CLI). That can't run in CI; it requires a developer to install the skill, point it at a fixture, and observe the agent's behavior.

This is **operator-driven**: when running a smoke check against the paired demo repos (or a throwaway clone of a real repo), the operator observes the skill's behavior directly and writes findings.

### What "running Layer 4" looks like

Install the skill into your harness. Point a fresh session at a demo's `greenfield` branch and run a bootstrap. Then point a session at `main` and exercise operating-mode classification (red / blue / boundary). Compare what the skill does to what `bootstrap-mode.md` and `operating-mode.md` say it should do.

The questions that matter:

- Did the agent pick the right extension (and shape, for Python)?
- Did it ask sensible questions during inspection?
- Did it propose the right flow mode (PR vs push) based on the repo's actual flow?
- Did it produce a sensible draft policy that passes Phase 3a's red-utility test?
- Did it refuse to auto-commit CI workflows, branch protection, CODEOWNERS?
- Did it refuse to silently weaken arch tests / import-linter contracts in operating mode?
- Did it refuse to launder a boundary violation when a user asked for one?
- Did it compose with existing setup rather than overwriting?
- Did it write a useful Phase 6 summary?

These are observed, not asserted. Findings are written to a per-run notes file (e.g., `.local/LAYER_4_SMOKE_<date>.md`); reproducible bugs become regression tests when the bug class is concrete enough to encode (the skill-yaml, skill-refs, skill-scripts-runnable, skill-toml, scaffold-ci, scaffold-ci-e2e layers were all added this way after Pallium's bootstrap surfaced specific bugs).

**Effort:** ~30 minutes per smoke run. **Value:** essential — the only way to catch design bugs in the skill itself. Run before each tag.

### Layer 5 — End-to-end demo repos

Two paired GitHub repos exercise the whole loop against real GitHub Actions, real branch protection, real CODEOWNERS, real PR comment posting / artifact uploading.

**`agent-redline-demo`** (Spring/JVM, PR-driven):
- `greenfield` — bare Spring service, no agent-redline artifacts. Use to exercise bootstrap mode.
- `main` — bootstrapped state. Use to exercise operating mode.
- `demo/blue-only-pr` → BLUE, CI green
- `demo/red-with-checkpoint-pr` → RED, CI green when label applied
- `demo/boundary-violation-pr` → BOUNDARY_VIOLATION, CI red
- `demo/api-change-pr` → API_CHANGE, CI green when label applied; structural OpenAPI diff in the comment

**`agent-redline-python-demo`** (Python/FastAPI, PR-driven **and** push-driven):
- PR-driven: same shape as the Spring demo — `greenfield`, `main`, three PR-scenario branches exercising the canonical verdicts.
- Push-driven (same repo, separate long-lived branch + scenarios so the two flow modes coexist):
  - `push-demo-main` — push-mode workflow (`on: push:`); verdict surfaces in `$GITHUB_STEP_SUMMARY` (run page) AND a Check Run posted via the Checks API (commit-list icon). The workflow itself fails only on exit 2; exit 1 is surfaced via the orange `action_required` Check Run conclusion.
  - `push-demo-blue-only` → BLUE, workflow green, Check Run `success` (🟢)
  - `push-demo-red-zone-change` → RED, workflow **green**, Check Run `action_required` (🟠 — distinct from a red failure; orange icon in the commit list, GitHub notification fires)
  - `push-demo-boundary-violation` → BOUNDARY_VIOLATION, workflow red, Check Run `failure` (🔴)

Source-of-truth content lives at `demo-source/` (Spring) and `demo-source-python/` (Python — `pr-scenarios/` and `push-mode/` subtrees). `scripts/sync-demo.sh` (Spring) and `scripts/sync-python-demo.sh --with-pr-branches --with-push-demo` (Python) regenerate the demo repos' branches deterministically. The push-mode workflow is also exercised at the unit level by `tests/scaffold-ci-e2e/check-scaffold-ci-e2e.sh` (Layer 8 above), which extracts both the reporter run-block and the summary-write step from the scaffold and asserts they produce a verdict and write it to `$GITHUB_STEP_SUMMARY`.

**Effort:** medium one-time setup, then `sync-*.sh` for re-runs. **Value:** essential — without this, "the whole pipeline works" is a claim, not a fact.

## What "v0.1 is done" looks like

- [x] All `tests/run-all.sh` layers green (in CI; locally with the optional gradle / import-linter prereqs).
- [x] Layer 4 smoke run completed against both demo repos with findings in a notes file.
- [x] Both Layer 5 demo repos (`agent-redline-demo`, `agent-redline-python-demo`) produce expected verdicts on real GitHub. Python demo covers both PR-driven and push-driven flows on the same repo (PR scenarios via sticky comment, push scenarios via run-page summary).

## What we're NOT testing

- Cross-repo signal (out of scope)
- LLM-judge soft checks (deferred)
- Performance under load (a single change's reporter run is small; not a v0.1 concern)
- The conversational layer of bootstrap-mode in CI (covered by Layer 4 smoke)

## Out of scope for this doc

- How a *consuming repo* validates its own policy (that's part of normal CI for the consuming repo, see [CI_INTEGRATION.md](CI_INTEGRATION.md)).
- How to debug a specific reporter regression (use the golden fixtures as a starting point).
- How extensions get released to a registry (no registry in v0.1).

## How regression layers get added

When a bug surfaces in a real bootstrap or smoke run, the response is:

1. Diagnose the underlying *class* of bug ("schema-invalid YAML in skill content", "dangling path reference", "import error in shipped script", etc.).
2. Fix the instance.
3. Add a test layer that catches the class, not just the instance.
4. Verify the layer would have caught the original bug by transiently reverting the fix.

Layers 3 (skill-yaml), 4 (skill-refs), 5 (skill-scripts-runnable), 6 (skill-toml), 7 (scaffold-ci), 8 + 9 (scaffold-*-e2e), 10 (bootstrap-detect), 11 (tuner), and 12 (pre-push) were all added this way. The framework's reliability is downstream of this discipline.

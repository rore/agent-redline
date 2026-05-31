# Validation

How we know agent-redline works the way the spec says it does.

This is a doc about *testing the project itself*, not about how a consuming repo validates its own policy. agent-redline has six distinct things to verify and each needs a different kind of test.

## The layers

| # | Layer | What it tests | Mechanical? |
|---|---|---|---|
| 0 | **Budget compliance** | No skill/template/extension file exceeds its declared token ceiling | Fully mechanical |
| 1 | **Schema validation** | Policies parse and conform to schema v1 | Fully mechanical |
| 2 | **Reporter golden tests** | Reporter produces correct verdicts for known inputs | Fully mechanical |
| 3 | **Extension scaffold dry-run** | Extension-generated artifacts compile and run | Fully mechanical |
| 4 | **Skill behavior simulation** | The skill produces the expected agent behavior | Operator-driven (no harness) |
| 5 | **End-to-end demo repo** | The whole loop works against real GitHub | Manual but high-confidence |

Layers 0–3 run in CI. Layer 4 is operator-driven — a person installs the skill into a harness and observes its behavior against a fixture. Layer 5 runs manually against a paired demo repo.

## Layer 0 — Budget compliance

**What it catches:** skill files, templates, and extensions creeping past their context-token ceiling. Every artifact loaded into an agent's context costs tokens on every relevant turn; growth has to be explicit, not accidental.

**How it works:**
- The ceilings are declared in `tests/budget/budget.yaml` (one entry per file, mapping path → max token count).
- A small script (`tests/budget/check-budget.sh`) computes an approximate token count for each file (word count × 1.33 as a fast estimator; a real tokenizer can be substituted later) and fails if any file exceeds its budget.
- The script is part of CI and runs on every PR. PRs that breach a ceiling fail the check and must either tighten the file or justify a budget increase (which itself is a structural change to the spec — see SPEC §1.4).

**Estimator:**
- `approx_tokens = words × 1.33`, where `words` is whitespace-separated word count.
- This is intentionally a rough approximation. It overestimates slightly on prose (good — gives margin) and underestimates on code-heavy files (acceptable — code is rare in skill files). The exact estimator can be refined later without changing the budget contract.

**Fixtures needed:**
- `tests/budget/budget.yaml` — the manifest of file → ceiling
- `tests/budget/check-budget.sh` — the check itself

**Ceiling source of truth:** SPEC §1.4.1. The manifest mirrors that table; if SPEC and manifest disagree, SPEC wins and the manifest is wrong.

**Effort:** small. **Value:** high — catches budget regression on every PR without anyone having to remember to count.

## Layer 1 — Schema validation

**What it catches:** invalid `agent-policy.yaml` files. Missing required fields, malformed globs, references to undefined checkpoints, the self-protection rule (architecture-test files must be in red zone).

**How it works:**
- A schema definition (initially: a JSON Schema; later: maybe a CUE schema) lives in `core/schema/agent-policy.schema.json`.
- The reporter loads and validates the policy on every run.
- A separate CI job validates every policy in `examples/`, every template in `core/templates/`, and every extension's example policies (if it ships any).

**Fixtures needed:**
- `core/schema/agent-policy.schema.json` — the schema
- `tests/schema/valid/*.yaml` — known-good policies that must parse
- `tests/schema/invalid/*.yaml` — known-bad policies that must fail with the right error code

**Effort:** small. **Value:** high — catches schema regressions instantly.

## Layer 2 — Reporter golden tests

**What it catches:** reporter regressions. Wrong zone matched, missed boundary violation, mis-formatted comment, wrong exit code, broken filter logic.

**How it works:**
- Each test fixture is a folder with the inputs and expected outputs:
  ```
  tests/reporter/<scenario>/
  ├── policy.yaml
  ├── diff.patch                    # the changed files (base..head)
  ├── archunit-output.xml           # backend output (or `none` for no-backend cases)
  ├── pr-labels.txt                 # labels currently on the PR
  ├── pr-reviewers.txt              # CODEOWNER approvals currently on the PR
  ├── expected-verdict.json         # what the reporter must produce
  └── expected-comment.md           # what the PR comment must look like
  ```
- The test harness runs the reporter against each fixture and diffs the output against the expected files.
- Updating expected outputs is intentional and requires a code review.

**Fixtures to ship in v0.1:**
- `blue-only` — all changed files are blue, verdict `BLUE`, exit 0
- `red-changed-no-checkpoint` — red files touched, no label, verdict `RED`, exit 2
- `red-changed-with-checkpoint` — red files touched, label present, verdict `RED`, exit 0
- `boundary-violation` — ArchUnit reports a violation, verdict `BOUNDARY_VIOLATION`, exit 2
- `gray-only` — only gray files, verdict `GRAY`, exit 1
- `mixed-red-and-blue` — mix, most-restrictive wins
- `pr-too-large` — exceeds size threshold
- `api-changed` — touched API contract path
- `schema-changed` — touched migration path
- `architecture-test-modified` — touched the architecture test files (auto-RED regardless of zone)
- `no-backend` — `outputFormat: none`, reporter skips boundary section

**Effort:** medium (10–12 fixtures × small files). **Value:** high — this is the primary regression net.

## Layer 3 — Extension scaffold dry-run

**What it catches:** broken extension scaffolds. Generated ArchUnit test that doesn't compile. Policy YAML that's invalid. CI snippet that uses the wrong action version. Path globs that don't actually match the extension's recommended layout.

**How it works:**
- Per extension, a small fixture repo lives at `tests/extensions/<extension-name>/fixture-repo/`.
- The fixture is a *minimal repo of the right shape* for the extension (e.g., a tiny Spring service for `spring-archunit`).
- A test harness:
  1. Reads the extension's `profile.md` and `scaffold.md`
  2. Generates the artifacts (policy, ArchUnit test, CI snippet) — same as bootstrap would
  3. Runs the resulting build (`./gradlew test --tests '*ArchitectureTest'` for Spring)
  4. Confirms the test class compiles and runs
  5. (Optional) introduces a known boundary violation, runs again, confirms it fails

**For `spring-archunit` specifically:**
- Fixture: a 5-file Spring service with `domain/`, `application/`, `adapter/persistence/`, `controller/` packages
- Generate the ArchUnit test from the default boundary rules
- Run `./gradlew test` — must pass
- Add an illegal `import` from `domain/` into `adapter/`
- Run again — must fail with the right rule name

**Effort:** medium for the first extension (need a Java fixture project), small for subsequent ones (copy the harness shape). **Value:** high — without this, "extensions work" is just claim.

## Layer 4 — Skill behavior simulation

**What it catches:** skill ambiguity, missing decision points, infinite loops, wrong questions to the developer.

This is the hardest layer. Agents are non-deterministic; a single "expected trace" can't cover the space. agent-redline does not ship a Layer 4 harness. Layer 4 is **operator-driven**: when you run a smoke check against the paired demo repo (or a throwaway clone of a real repo), you observe the skill's behavior directly and write down findings.

### What "running Layer 4" looks like

Install the skill into your harness (Claude Code, Codex, Cursor, Gemini CLI). Point a fresh session at the demo's `greenfield` branch and run a bootstrap. Then point a session at `main` and exercise operating-mode classification (red / blue / boundary). Compare what the skill does to what bootstrap-mode.md and operating-mode.md say it should do.

The questions that matter:
- Did the agent pick the right extension?
- Did it ask sensible questions during inspection?
- Did it produce a sensible draft policy that passes Phase 3a's red-utility test?
- Did it refuse to auto-commit CI workflows, branch protection, CODEOWNERS?
- Did it refuse to silently weaken arch tests in operating mode?
- Did it refuse to launder a boundary violation when a user asked for one?
- Did it compose with existing setup (existing `AGENTS.md`, existing arch test, existing pre-push) rather than overwriting?
- Did it write a useful Phase 6 summary?

These are observed, not asserted. Findings are written to a per-run notes file (e.g., `.local/LAYER_4_SMOKE_<date>.md`); reproducible bugs become issues. agent-redline does not ship a `tests/skill-review/` checklist or `tests/skill-smoke/` post-hoc-asserter — those would impose process overhead without catching anything the operator's eyes don't already see.

**Effort:** ~30 minutes per smoke run. **Value:** essential — the only way to catch design bugs in the skill itself. Run before each tag.

## Layer 5 — End-to-end demo repo

**What it catches:** anything the lower layers missed when run against real GitHub Actions, real branch protection, real CODEOWNERS routing, real PR comment posting.

**How it works:**

A paired GitHub repo `agent-redline-demo` with two long-lived branches and three PR-scenario branches. Source-of-truth content lives at `demo-source/` in this repo; `scripts/sync-demo.sh` regenerates the demo repo's branches deterministically.

**Long-lived branches:**

- **`greenfield`** — bare Spring service, no agent-redline artifacts. Use to exercise **bootstrap mode**: drop the skill into Claude Code or Codex pointed at this branch, ask the agent to set up agent-redline, observe what it produces.
- **`main`** — bootstrapped state: Spring service plus all agent-redline artifacts (policy, AGENTS.md, docs/agent/, vendored reporter, scripts, CI workflow, CODEOWNERS). Use to exercise **operating mode**.

**Four PR-scenario branches** (all branched from `main`):

1. `demo/blue-only-pr` → verdict `BLUE`, CI green, no checkpoint required
2. `demo/red-with-checkpoint-pr` → verdict `RED`, CI green when `architecture-reviewed` label applied
3. `demo/boundary-violation-pr` → verdict `BOUNDARY_VIOLATION`, CI red, ArchUnit failure surfaced
4. `demo/api-change-pr` → verdict `API_CHANGE`, CI green when `api-reviewed` label applied; structural OpenAPI diff shown in the PR comment (the workflow's `generate-specs` job builds the spec at base+head SHAs and the reporter diffs them)

Each PR has a known shape and a known expected outcome (see `demo-source/pr-scenarios/`). Running the demo means: clone the demo repo, run sync-demo.sh from agent-redline, push, observe. `sync-demo.sh --push` (with `gh` available) also recreates the four PRs and applies the canonical labels — so a sync produces the live demo state without manual GitHub clicks.

**Demo sync:** `scripts/sync-demo.sh --target ../agent-redline-demo --with-pr-branches` rebuilds all six branches from agent-redline's `demo-source/` and `examples/spring-hexagonal/`. The target's branches are replaced, not merged — the demo is regenerable, not authoritative.

**Effort:** medium (one-time setup, then `sync-demo.sh` for re-runs). **Value:** essential — without this, "the whole pipeline works" is a claim, not a fact.

## What "v0.1 is done" looks like

All of the following hold:

- [ ] Layer 0 budget check passes (every file under its declared ceiling)
- [ ] Schema validates every policy in `examples/`, every template, every fixture
- [ ] All Layer 2 reporter golden tests pass
- [ ] Layer 3 dry-run for `spring-archunit` passes (test compiles, runs, fails on injected violation)
- [ ] Layer 4 smoke run completed against the demo's `greenfield` and `main` branches with findings written to a notes file
- [ ] Layer 5 demo: greenfield bootstrap test passes; the four PR-scenario branches produce their expected verdicts on real GitHub

If any of these are red, v0.1 isn't done.

## What we're NOT testing in v0.1

- Other extensions (only `spring-archunit` exists)
- Cross-repo signal (out of scope)
- LLM-judge soft checks (deferred)
- Performance under load (a single PR's reporter run is small; not a v0.1 concern)
- Multi-language consuming repos (a Spring service is the only target stack)

## Out of scope for this doc

- How a *consuming repo* validates its own policy (that's part of normal CI for the consuming repo, see CI_INTEGRATION.md)
- How to debug a specific reporter regression (use the golden fixtures as a starting point)
- How extensions get released to a registry (no registry in v0.1)

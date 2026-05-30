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
| 4 | **Skill behavior simulation** | The skill produces the expected agent behavior | Partially mechanical |
| 5 | **End-to-end demo repo** | The whole loop works against real GitHub | Manual but high-confidence |

Layers 0–3 run in CI. Layer 4 runs partly in CI (golden traces), partly manually (running the skill in Claude Code / Codex against a fixture). Layer 5 runs manually against a paired demo repo.

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

This is the hardest layer. Agents are non-deterministic; a single "expected trace" can't cover the space. The honest approach is two-tiered:

### 4a. Smoke check (mechanical)

After a manual bootstrap run against a fixture repo, the harness checks:
- A `agent-policy.yaml` was produced
- The policy is schema-valid (Layer 1)
- An `AGENTS.md` was produced
- The boundary-backend artifacts were scaffolded
- The `docs/agent-redline-ci-proposal.md` exists
- No CI workflow was auto-committed
- No file under `src/test/.../architecture/` was edited without an explicit checkpoint note

This doesn't validate that the skill *did the right thing*, only that it produced a structurally valid result. Useful as a smoke test before a manual review.

### 4b. Manual session review (judged)

The actual skill validation is humans running the skill against fixture repos in Claude Code, Codex, etc., and writing down whether the agent:
- Picked the right extension
- Asked sensible questions during inspection
- Produced a sensible draft policy
- Refused to auto-commit CI
- Refused to silently weaken architecture tests
- Wrote a useful summary at the end

For v0.1, this is a documented checklist (`tests/skill-review/checklist.md`) and a few fixture repos under `tests/skill-review/fixtures/`. Run by hand. Results recorded as "PASS / FAIL with notes" — no grand harness.

**Effort:** small (the checklist) plus ongoing (running it). **Value:** essential but bounded — this is the only way to catch design bugs in the skill itself.

## Layer 5 — End-to-end demo repo

**What it catches:** anything the lower layers missed when run against real GitHub Actions, real branch protection, real CODEOWNERS routing, real PR comment posting.

**How it works:**

A paired GitHub repo `agent-redline-demo` with two long-lived branches and three PR-scenario branches. Source-of-truth content lives at `demo-source/` in this repo; `scripts/sync-demo.sh` regenerates the demo repo's branches deterministically.

**Long-lived branches:**

- **`greenfield`** — bare Spring service, no agent-redline artifacts. Use to exercise **bootstrap mode**: drop the skill into Claude Code or Codex pointed at this branch, ask the agent to set up agent-redline, observe what it produces.
- **`main`** — bootstrapped state: Spring service plus all agent-redline artifacts (policy, AGENTS.md, docs/agent/, vendored reporter, scripts, CI workflow, CODEOWNERS). Use to exercise **operating mode**.

**Three PR-scenario branches** (all branched from `main`):

1. `demo/blue-only-pr` → verdict `BLUE`, CI green, no checkpoint required
2. `demo/red-with-checkpoint-pr` → verdict `RED`, CI green when checkpoint label applied
3. `demo/boundary-violation-pr` → verdict `BOUNDARY_VIOLATION`, CI red, ArchUnit failure surfaced

Each PR has a known shape and a known expected outcome (see `demo-source/pr-scenarios/`). Running the demo means: clone the demo repo, run sync-demo.sh from agent-redline, push, observe.

**Demo sync:** `scripts/sync-demo.sh --target ../agent-redline-demo --with-pr-branches` rebuilds all five branches from agent-redline's `demo-source/` and `examples/spring-hexagonal/`. The target's branches are replaced, not merged — the demo is regenerable, not authoritative.

**Effort:** medium (one-time setup, then `sync-demo.sh` for re-runs). **Value:** essential — without this, "the whole pipeline works" is a claim, not a fact.

## What "v0.1 is done" looks like

All of the following hold:

- [ ] Layer 0 budget check passes (every file under its declared ceiling)
- [ ] Schema validates every policy in `examples/`, every template, every fixture
- [ ] All Layer 2 reporter golden tests pass
- [ ] Layer 3 dry-run for `spring-archunit` passes (test compiles, runs, fails on injected violation)
- [ ] Layer 4a smoke check runs against the `examples/spring-hexagonal/` fixture and passes
- [ ] Layer 4b manual checklist has been run at least once by a developer using Claude Code or Codex with the skill loaded, and findings written down
- [ ] Layer 5 demo: greenfield bootstrap test passes; three PR-scenario branches produce their expected verdicts on real GitHub

If any of these are red, v0.1 isn't done.

## What we're NOT testing in v0.1

- Other extensions (only `spring-archunit` exists)
- Cross-repo signal (out of scope)
- LLM-judge soft checks (deferred)
- Performance under load (a single PR's reporter run is small; not a v0.1 concern)
- Multi-language consuming repos (a Spring service is the only target stack)

## Borrowing from BEAR

BEAR's testing patterns that map cleanly:

- **Golden test data with known outputs.** BEAR has `testdata/golden/compile/`. We have Layer 2 reporter goldens.
- **A paired demo repo with three planned PRs** (clean → REVIEW REQUIRED → FAIL). We have Layer 5.
- **Demo prep scripts that reset state.** BEAR has `clean-demo-branch.ps1` / `sync-bear-demo.ps1`. We have `scripts/clean-demo.sh` / `scripts/sync-demo.sh` as roadmap items.

Patterns that don't map directly: BEAR is a CLI run by a human; agent-redline's primary user is an agent following a skill. Layer 4 (skill behavior) is where we have to do something BEAR didn't.

## Out of scope for this doc

- How a *consuming repo* validates its own policy (that's part of normal CI for the consuming repo, see CI_INTEGRATION.md)
- How to debug a specific reporter regression (use the golden fixtures as a starting point)
- How extensions get released to a registry (no registry in v0.1)

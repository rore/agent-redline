# Decisions

Project decisions with rationale. Append-only; dated.

`docs/SPEC.md` says *what is*. This file says *why we chose what we chose*, what alternatives were considered, and what to revisit if circumstances change.

Each entry: short title, date, decision, alternatives, rationale, revisit-if.

---

## 2026-05-31 — Schema describes only what the reporter does

**Decision:** The policy schema (`core/schema/agent-policy.schema.json`) contains only fields the v0.1 reporter implements. Fields previously accepted-but-ignored — `changeRules`, `defaults.unclassifiedZone`, `defaults.grayMode`, `boundaryBackend`, `api.type: openapi-from-controllers`, `team:`/`reviewerCount:` checkpoint forms — are removed. Items that might come back later are tracked in [`SPEC.md §15.3`](SPEC.md) with the implementation gate that has to clear first.

**Alternatives considered:**
- Keep the fields, mark them `RESERVED in v0.1` in schema descriptions and POLICY_SCHEMA.md (the previous state).
- Keep the fields and silently ignore them (the state before the previous attempt).

**Rationale:**
- "Reserved" fields are traps. A user writes `satisfiedBy: [{team: platform}]` thinking it works, ships a checkpoint that can never be checked off, and only finds out when a PR is mysteriously stuck.
- The schema is documentation. A schema that describes the v1 contract instead of the v0.1 reality teaches the reader the wrong thing.
- Forward compat that costs nothing (e.g., a string name like `boundaryBackend: archunit`) sounds harmless, but it accumulates. Three of these and the schema is mostly aspirational decoration.
- Schema versions are cheap. When the reporter learns a new behavior, the schema grows with it — that's a small explicit change with code to back it up. The tax is on adding capability, where it belongs, not on writing every policy.

**Test guard:** `tests/reporter/test_schema_coverage.py` asserts the dropped fields stay dropped and that templates/docs don't reference phantom fields. Re-introducing one of them requires either implementing the behavior (and updating the test) or naming the test as the thing to update — both force a deliberate choice.

**Revisit if:** the v0.1-hardcoded mapping in the reporter (red → require checkpoint; gray → warn; etc.) turns out to be too rigid for real users. At that point, design `changeRules` (or equivalent) with their cases in hand, not as speculative scaffolding.

---



**Decision:** agent-redline ships as a skill (markdown loaded into agent harnesses), not as a CLI tool with a formal IR.

**Alternatives considered:**
- A CLI with a formal architectural IR ("BEAR" v1 design — declare boundaries, generate constraints, enforce in CI).
- A library or platform with a server-side service.

**Rationale:**
- A skill has a near-zero adoption gradient: drop one file into a harness, ask the agent to set the repo up. A CLI requires installation, configuration, and a CI-integration story before it's useful.
- The skill is self-bootstrapping — the agent uses it to create the policy and artifacts in the consuming repo. No init wizard.
- Skills work across Claude Code, Codex, Cursor agent mode, and any harness that loads markdown instructions. A CLI requires a per-platform distribution channel.
- A formal IR asks the team to model architecture in a new layer before they get value. The skill protects boundaries the team is willing to name, no more.

**Revisit if:** harnesses converge on a richer plugin format that natively supports zone classification, in which case agent-redline could become the spec the harness implements rather than a markdown skill.

---

## 2026-05-30 — Three-layer architecture: core + language extension + consuming repo

**Decision:** Three layers, hard separation. Core is stack-neutral (skill, schema, reporter, templates). Language extensions bind core to a stack (zones, boundary backend, scaffolding). Consuming repos own their `agent-policy.yaml` and generated artifacts.

**Alternatives considered:**
- A single project that ships built-in support for every major stack (Spring, Node, Python, Go, …).
- A two-layer model (core + per-repo customization) without an extension layer.

**Rationale:**
- The long tail of language/framework combinations is too large for one project to own. Extensions must be a first-class concept from day one or third parties won't believe they can extend cleanly.
- A two-layer model would force every consuming repo to invent its own boundary-rule backend wiring. Extensions absorb that work once per stack.
- Treating the reference Spring extension exactly like a third-party extension forces the contract to be real, not a special case for built-ins.

**Revisit if:** the extension contract proves too constraining for a real third-party stack and the v1 schema needs to bend.

---

## 2026-05-30 — Reporter is glue, not a classification engine

**Decision:** The CI-side script that produces the PR verdict is named "reporter" and is explicitly *not* a classification engine. It does path-glob lookups, reads the boundary-backend's output, formats a comment, returns an exit code.

**Alternatives considered:**
- A "classifier" component that does inference, decides verdicts, and owns the rule logic.
- Folding the reporter into the boundary-rule backend itself.

**Rationale:**
- The agent classifies changes during operating mode, *before* editing. The boundary-rule backend (e.g., ArchUnit) catches violations during CI. There's nothing left for a third "classifier" component to actually classify — the work is already done by the time the reporter runs.
- Calling the script a "classifier" or "engine" oversells it and creates pressure to grow it into something it shouldn't be. Calling it a reporter makes the surface honest: ~200 lines of glue.
- Keeps the reporter rewrite-able when needed (different language, different CI system) without conceptual disruption.

**Revisit if:** the reporter genuinely needs inference logic the deterministic checks can't provide (e.g., LLM-judge soft checks). At that point the inference layer is a separate component, not a reporter expansion.

---

## 2026-05-30 — ArchUnit is the JVM default; the framework is backend-neutral

**Decision:** The reference Spring extension uses ArchUnit. The core project is neutral about boundary-rule backends; extensions pick what fits their stack.

**Alternatives considered:**
- Bake ArchUnit into the core ("agent-redline = ArchUnit + skill").
- Pick a different default (jQAssistant, Spring Modulith, Semgrep).
- No default — every team picks at bootstrap time.

**Rationale:**
- Baking ArchUnit into core would force every non-JVM stack to either fight the abstraction or build a wrapper. Backend neutrality at the core costs nothing and unlocks every other ecosystem.
- ArchUnit is the right pragmatic default for Spring: open-source, JUnit-friendly, Gradle/Maven-friendly, bytecode-aware (catches real violations not just textual matches), drops in as one test class.
- jQAssistant is more powerful but heavier. Spring Modulith is too opinionated about module structure. Semgrep is a generic-fallback choice, not a layered-architecture-rules tool.
- Having no default would mean every team faces a decision on day one. A well-chosen default keeps adoption fast for the common case.

**Revisit if:** a clearly-better-than-ArchUnit JVM tool emerges, or a jQAssistant integration becomes worth the heavier setup for some teams.

---

## 2026-05-30 — Token budgets are ceilings, not targets

**Decision:** Every file an agent loads mid-task has a declared token ceiling enforced in CI. The discipline is "smallest version that does the job; expand only on demonstrated need."

**Alternatives considered:**
- No budgets — let files grow as needed.
- Soft budgets (warn but don't fail).
- Hard budgets framed as targets to fill ("write up to this much").

**Rationale:**
- Every token loaded into agent context is a tax on every relevant turn. A 10K-token skill costs 10K tokens before the agent does anything useful, every session, forever.
- Soft budgets get ignored. Hard budgets enforced in CI keep the discipline honest.
- Framing budgets as targets-to-fill produces padding — the first drafts of the skill files were ~40% larger than they needed to be because I wrote up to the ceiling instead of writing what the agent actually needed. The reframe to "ceiling, not target" is what made the deletion test possible.

**Revisit if:** a real ceiling proves too tight for substantive instruction the agent actually needs. The fix is then to expand the *specific ceiling* with explicit rationale, not to relax the discipline.

---

## 2026-05-30 — Skill-authoring discipline applies to anything an agent loads mid-task

**Decision:** A single set of rules (deletion test, imperative voice, no marketing/rationale/commentary, budget compliance) governs every file an agent loads mid-task — core skill files, per-checkpoint docs, language-extension files (`profile.md`, `scaffold.md`, `operating.md`), generated `agent-policy.yaml` and `AGENTS.md` in consuming repos. README files and human-facing docs are exempt.

**Alternatives considered:**
- Apply skill-authoring rules only to `core/skill/`.
- No formal authoring discipline; let style emerge.

**Rationale:**
- The audience is what defines the rules, not the directory. Anything an agent reads mid-task has the same audience and same constraints regardless of where it lives in the tree.
- Without a single rule, extension authors will write extension files like human docs (with pitch, rationale, commentary) and budgets will silently inflate.
- A documented authoring guide (`docs/SKILL_AUTHORING.md`) makes the discipline learnable. The deletion test is the operative tool: cut any sentence and check whether agent behavior would change.

**Revisit if:** patterns emerge that genuinely need different rules for different file types. Initial evidence suggests one rule covers all agent-loaded content well.

---

## 2026-05-30 — v0.1 ships with `spring-archunit` only

**Decision:** The reference language extension is `spring-archunit`. Other stacks (Node, Python, Go, Rust, multi-language Semgrep) are roadmap, community-built, or both.

**Alternatives considered:**
- Ship multiple in-tree extensions at v0.1.
- Ship none — only the framework, force every team to write their own.

**Rationale:**
- One reference extension proves the contract is real and shippable. Multiple in-tree extensions at v0.1 multiplies the surface to validate before the contract has been pressure-tested even once.
- Spring + ArchUnit is a high-traffic combination with mature tooling. If the contract works there, it likely works elsewhere.
- Shipping zero extensions would mean every adopter has to write one before they can try the framework. That's a higher adoption cost than necessary.

**Revisit if:** the contract has been pressure-tested on Spring and is stable enough to support adding Node or Python in-tree as second/third reference extensions.

---

## 2026-05-30 — CI integration is proposed, never auto-committed

**Decision:** Bootstrap mode produces a `docs/agent-redline-ci-proposal.md` document. It does not write `.github/workflows/agent-redline.yml`, does not modify branch protection, does not modify CODEOWNERS. Humans apply the proposal.

**Alternatives considered:**
- Auto-commit the workflow file as part of bootstrap.
- Open a PR with the workflow file rather than a proposal doc.

**Rationale:**
- CI changes affect every developer in the repo and may need platform-admin approval. Auto-committing them violates the same discipline the skill enforces on agents (don't ship structural changes without explicit human attention).
- Auto-opening a PR would still surface the change for human review, but it's heavier than the developer needs and assumes a PR-creating identity that isn't worth wiring up for v0.1.
- A proposal document is the lightest mechanism that respects the structural-change rule. Developers copy from it when ready.

**Revisit if:** the proposal-doc step proves to be a friction the developer never gets past, in which case opening a draft PR could become a v0.2+ option.

---

## 2026-05-30 — One supported reporter output format in v0.1 (JUnit XML)

**Decision:** The reporter natively reads JUnit XML. Other formats (SARIF, JSON-violations) are roadmap. Extensions whose backends produce other formats add a conversion step in their `scaffold.md`.

**Alternatives considered:**
- Support SARIF + JUnit XML + JSON-violations from day one.
- Support whatever the first three or four extensions need.

**Rationale:**
- ArchUnit produces JUnit XML natively, which covers the only extension shipping in v0.1.
- Adding format support is cheap (a parser per format), but adding it speculatively before any extension demonstrably needs it produces surface area without adoption.
- Extensions that need a different format can still ship — they convert in their build step. This proves the contract handles the case before we widen the core's surface.

**Revisit if:** building the second or third extension shows the conversion step is a recurring friction worth eliminating.

---

## 2026-05-30 — Single `docs/DECISIONS.md` file, not an ADR directory

**Decision:** Project decisions live in one append-only file rather than a `docs/decisions/0001-*.md`-style ADR directory.

**Alternatives considered:**
- A directory of numbered ADRs (one decision per file).
- No decisions file; rely on git history and SPEC.md.

**Rationale:**
- At the project's current scale (~10 substantive decisions), one file is grep-able, scrollable, and easy to append to. A directory adds navigation overhead for very little gain.
- SPEC.md says *what is*; without DECISIONS.md, the *why* is lost in conversation transcripts that aren't checked in.
- A single file makes it easy for new contributors to read the rationale trail in one pass.

**Revisit if:** the file grows past comfortable readability (~50 entries, very rough threshold), at which point split into directory.

---

## 2026-05-30 — All eight per-checkpoint skill docs ship in v0.1

**Decision:** `core/templates/skills/` ships with eight files: `blue-zone-work.md`, `red-zone-change.md`, `gray-zone-change.md`, `boundary-violation.md`, `api-change-checkpoint.md`, `persistence-change-checkpoint.md`, `security-change-checkpoint.md`, `pr-discipline.md`. Each is under the 600-token ceiling.

**Alternatives considered:**
- Ship none; the operating-mode skill file is sufficient for all branches.
- Ship only `boundary-violation.md` (the strongest candidate by reasoning).
- Ship only the three core ones (blue-zone-work, red-zone-change, boundary-violation) listed in the original SPEC.

**Rationale:**

This decision was made data-driven, in the sense available before the project has running smoke-test data. The method:

1. **Option A — articulate uniqueness in advance.** For each candidate, list what unique behavioral content it would carry that's NOT in `agent-redline.md` or `operating-mode.md`. Predict whether it's enough to justify the file.
2. **Option C — write each one under a uniqueness constraint.** Every line must add behavioral instruction NOT already in the core skill files. Measure the resulting size; if it lands at usable density (200+ tokens of unique content) under the 600-token ceiling, the doc earns a place.

The full Option A predictions and the actual outcomes are recorded in `.local/PER_CHECKPOINT_DOCS_ANALYSIS.md`.

**Result:** Option A's predictions were systematically too conservative. Predicted "no" or "lean no" candidates (`blue-zone-work.md`, `red-zone-change.md`, `gray-zone-change.md`, `pr-discipline.md`) all produced 150-350 tokens of genuinely unique content when actually attempted. The exercise of writing under a uniqueness constraint surfaced concrete behavioral patterns (specific anti-patterns to refuse, concrete reviewer needs, gray-vs-grayWatch distinctions) that abstract reasoning had missed.

All eight files passed the budget check at 47%-89% utilization with comfortable headroom.

**Lesson worth recording:** abstract reasoning about "what would this file contain?" tends to underestimate what focused, concrete instruction fits a single topic. The exercise of writing under a uniqueness constraint is empirically different from predicting it. Future "should this file exist?" decisions should run the experiment, not the prediction.

**Revisit if:** smoke testing (Layer 4b) shows the agent ignores or duplicates content from a per-checkpoint doc — that would mean the content didn't change behavior despite the prediction. Revisit individual files based on observed agent behavior, not on a-priori reasoning.

---

## 2026-05-30 — Reporter and validation tooling: Python

**Decision:** The reporter (`core/reporter/`) and the schema-validation harness (`tests/schema/check-schema.py`) are written in Python. CI uses `actions/setup-python@v5` and installs `pyyaml` and `jsonschema` as dependencies.

**Alternatives considered:**
- Bash for the reporter (matching the existing `tests/budget/check-budget.sh`).
- TypeScript / Node for parity with potential frontend tooling later.
- Go, Rust, or other compiled languages.

**Rationale:**
- Python's standard library covers most of what the reporter needs: YAML via `pyyaml`, JSON Schema via `jsonschema`, glob matching via `pathlib`, JUnit XML via `xml.etree.ElementTree`. No exotic dependencies.
- Bash is workable for the budget check (one file, simple parser) but brittle for XML and conditional schema validation. The reporter's logic genuinely benefits from a typed-ish language.
- TypeScript adds Node, npm, lockfile management, and a build step. The reporter is ~500 lines of mostly procedural code; a build pipeline is overhead with no compensating value.
- Compiled languages (Go, Rust) have a bigger setup cost for contributors and slower iteration without a clear payoff at this scale.
- Python is universally available on developer machines and in CI, has good readability, and the standard libraries are stable enough that the code can stay dependency-light.

**Revisit if:** the reporter grows substantially in scope (e.g., a dashboard, a watchdog, a server) such that another language fits better, or if Python ecosystem changes (3.x sunset, jsonschema breaking changes) make maintenance painful.

---

## 2026-05-30 — Demo as paired repo with `greenfield` + `main` branches

**Decision:** The Layer 5 demo lives in a separate GitHub repo (`agent-redline-demo`), not as a subdirectory inside agent-redline. The demo's content is generated from agent-redline's `demo-source/` (artifact templates) + `examples/spring-hexagonal/` (Spring source) via `scripts/sync-demo.sh`. The demo repo has two long-lived branches:

- **`greenfield`** — bare Spring service. No `agent-policy.yaml`, no `AGENTS.md`, no per-checkpoint docs, no CI workflow. Used to exercise **bootstrap mode**: drop the agent-redline skill into a session pointed at this branch and ask the agent to set up agent-redline.
- **`main`** — the bootstrapped state. Spring source plus all agent-redline artifacts (policy, AGENTS.md, docs/agent/, vendored reporter, scripts, CI workflow, CODEOWNERS). Used to exercise **operating mode**. The three planned PR branches branch from `main`.

Plus three PR-scenario branches (`demo/blue-only-pr`, `demo/red-with-checkpoint-pr`, `demo/boundary-violation-pr`) for end-to-end Layer 5 PR validation.

**Alternatives considered:**

- **Demo as a subdirectory inside agent-redline** (`demo/`): rejected because it doesn't actually validate anything end-to-end. The agent's mode-dispatch detects `agent-policy.yaml` at the repo root; an `agent-policy.yaml` at `demo/agent-policy.yaml` would never trigger operating mode for an agent working in agent-redline. CI workflows in subdirectories don't run on GitHub Actions. Branch protection, real PR comments, real CODEOWNERS routing — none can be exercised in subdirectory PRs.
- **Demo's content as the source of truth, no in-repo `demo-source/`**: rejected because demo content drifts from agent-redline. When the policy schema changes, someone has to remember to update the demo too. With `demo-source/` versioned in agent-redline and `sync-demo.sh` regenerating the demo, drift is impossible by construction.
- **Single `main` branch in the demo, no `greenfield`**: rejected because bootstrap mode and operating mode are two distinct halves of the framework, and demonstrating both requires two starting points. BEAR has a similar dual-state pattern (spec-only vs governed-baseline). The framework's pitch is "skill that works in both modes"; the demo should exercise both.

**Rationale:**

- Layer 5 in `docs/VALIDATION.md` is "the whole pipeline works against real GitHub." Real-GitHub validation requires a real GitHub repo. Subdirectory demos are theater.
- The two-branch shape (greenfield + main) maps cleanly to the two skill modes. An observer can run bootstrap against `greenfield`, run operating-mode tasks against `main`, and run the three PR branches as the canonical verdict-shapes demo.
- `demo-source/` in agent-redline is the source of truth. The `sync-demo.sh` script regenerates the demo repo's branches deterministically. The demo repo is regenerable; never the source of policy or skill content.
- Keeping the Spring source canonical in `examples/spring-hexagonal/` means agent-redline has one Spring fixture serving two roles (Layer 3 dry-run + demo source code). No duplication.

**Revisit if:**

- The demo grows multiple flavors (different language extensions); at that point, paired repos per stack may make sense.
- `sync-demo.sh` becomes unwieldy because the demo's content diverges meaningfully from what agent-redline produces. That would suggest agent-redline's bootstrap output isn't right and should be fixed at the source.

# Decisions

Project decisions with rationale. Append-only; dated.

`docs/SPEC.md` says *what is*. This file says *why we chose what we chose*, what alternatives were considered, and what to revisit if circumstances change.

Each entry: short title, date, decision, alternatives, rationale, revisit-if.

---

## 2026-05-30 — Skill-first packaging, not CLI-first

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

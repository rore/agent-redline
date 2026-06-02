# Decisions

Project decisions with rationale. Append-only; dated.

`docs/SPEC.md` says *what is*. This file says *why we chose what we chose*, what alternatives were considered, and what to revisit if circumstances change.

Each entry: short title, date, decision, alternatives, rationale, revisit-if.

---

## 2026-06-01 (later) — Calibration starts at bootstrap, not at shadow

**Decision:** Move zone calibration from a "first 1–2 weeks of shadow mode" activity to a *bootstrap-time* activity when the repo has ≥30 merged PRs. The bootstrap skill's Phase 3 grows a new sub-step (Phase 3b) that, with developer approval, runs `scripts/agent-redline-tune.py` against the repo's PR history and presents firing-rate-based downgrade suggestions. The developer approves, overrides, or splits each. The policy ships with red zones already tuned to the team's actual PR shape. Window 1 of shadow mode (per `docs/CI_INTEGRATION.md`) becomes "confirm and refine," not "discover from scratch."

**Alternatives considered:**

- **Keep calibration shadow-mode-only.** Rejected: the calibration data (`.local/calibration/REPORT.md`) showed default Spring policy firing on 44–54% of PRs across three services. A team going through bootstrap unchanged would hit alert fatigue in week 1 and conclude the tool was noisy before any tuning data accumulated. The signal needed is already in the repo at bootstrap time.
- **Run the tuner automatically without developer approval.** Rejected: tuning suggestions can be wrong (a rule firing on 35% may still be correct if the team really does want every API change reviewed). The agent's job is to *propose*, not to *decide*. Approval gates are the same shape as every other Phase 3 decision.
- **Make Phase 3b mandatory regardless of PR count.** Rejected: with fewer than 30 PRs the data isn't statistically informative; rules firing on 1/5 PRs could be 0% or 60% in a larger sample. Better to skip honestly and let Window 1 do the work than to tune on noise.
- **Delete `agent-redline-tune.py` and run firing-rate detection inside the reporter on every PR.** Rejected: the tuner is a deliberate offline tool — it answers "are the defaults right?" against a corpus, which is different from "did this PR cross a rule?". Keeping them separate keeps the reporter simple and the tuner focused.

**Rationale:**

The `.local/calibration` experiment showed that ~30 merged PRs is the minimum where the dominant noise sources become visible (a rule firing on 50%+ is unmissable; rules firing rarely need a larger sample). Most active service repos have far more than 30 merged PRs. Running the tuner inside bootstrap turns the empirical lesson from the Spring-defaults retune into a *process*: every team that bootstraps gets the same kind of tuning the Spring defaults received, against their own history.

The developer-approval gate matches the rest of Phase 3 — the agent never auto-changes policy. The 30-PR threshold is documented so the agent doesn't silently skip when the repo is genuinely too new.

**Mechanics:**

- `scripts/agent-redline-tune.py` gains `--repo`, `--limit`, and `--suggest` flags (offline-fetched PR data; JSON suggestions instead of markdown when `--suggest` is set).
- `core/skill/bootstrap-mode.md` Phase 3 restructured: 3a unchanged, **3b new** (PR-history calibration, ≥30 PRs, developer approval, never auto-apply), 3c is the renamed prior 3b (repo-specific questions).
- `extensions/spring-archunit/scaffold.md` notes that calibration ran in Phase 3b; the scaffold should not re-run it.
- `docs/SPEC.md §4.3` restated as a continuum (bootstrap → shadow → binding).
- `docs/CI_INTEGRATION.md` Window 1 restated as "confirm and refine."
- `tests/budget/budget.yaml` raised the `core/skill/bootstrap-mode.md` ceiling from 2100 to 2400 to fit Phase 3b.

**Revisit if:**

- An adopter reports the 30-PR threshold is wrong in either direction (a 20-PR sample is enough for them, or 50 is the real minimum). Either changes the threshold; the framework stays.
- A non-Spring extension lands and the tuner needs language-specific firing-rate logic. Currently the rates are path-glob-driven and language-agnostic, so this should be fine.
- Bootstrap-time calibration becomes annoying because it slows bootstrap by minutes (the `gh` fetch is ~30s × 30 PRs ≈ a few minutes). At that point, cache the fetch in `.local/` so re-running bootstrap on the same repo doesn't refetch.

---

## 2026-06-01 — Migration immutability and policy self-edit are skill-level refusal patterns

**Decision:** Two new entries in `operating-mode.md`'s "Do not silently modify governance" refusal list, alongside the existing architecture-test entry:

1. **Already-shipped migrations are immutable.** Editing a `V*.sql` file already on `main` (to add a column, fix a type, change a constraint) is a refusal pattern. The agent must propose a compensating forward migration (V2 alters what V1 created) instead of mutating V1 in place.
2. **`agent-policy.yaml` is not edited as a side-effect.** Touching the policy to widen a threshold, drop a red entry, or relax a checkpoint while doing other work is a refusal pattern. The only legitimate policy edit is one the developer asks for explicitly and in isolation, and it remains red-zone (architecture-review).

`core/templates/skills/persistence-change-checkpoint.md` gets an "Existing migrations are immutable" section with the V1/V2 mechanic. `core/templates/skills/boundary-violation.md`'s "policy is too strict" pattern is rewritten to point at the new explicit refusal.

**Alternatives considered:**

- **Migration immutability — only document, don't refuse.** Rejected: the C2 simulation showed a with-skill agent (otherwise behaving correctly on every other shortcut) cheerfully edited V1 to add a column because the existing skill content didn't say "don't." Documentation that's not in the refusal list isn't enforced — agents read what's near the task and act on it.
- **Policy self-edit — keep it as PR-time-red-only.** Rejected: relying solely on the reporter's red-zone classification is weaker than the project's own boundary-rule stance. Boundary rules don't say "feel free to import the adapter, the reporter will catch it"; they say refuse and escalate. Policy weakening deserves the same treatment because the failure mode is symmetric — an agent that quietly bypasses governance to make a task easier produces undetectable damage if any layer of the chain misses the edit. The reporter remains the second line of defense for policy edits the developer *did* explicitly ask for; the skill refuses the silent-side-effect case.
- **Refuse all policy edits, even explicit ones.** Rejected: policies do evolve. The skill must refuse the *implicit* edit ("threshold is annoying, raise it while we're here") but not the *explicit* one ("update the policy to add a new red zone for /security"). The wording — "the only legitimate policy edit is one the developer asks for explicitly and in isolation" — captures that.

**Rationale:**

The C2 agent-PR simulation (see `.local/calibration/C2_REPORT.md`) surfaced these as the two cleanest gaps in skill content. On every other shortcut tempted in the simulation, the with-skill agent refused or correctly flagged checkpoints; on these two it ploughed ahead because the skill content was silent. Adding them is a small, mechanical edit that closes a specific, observed failure mode.

The migration case is also operationally severe: editing V1 in place breaks every environment that already applied V1, and the failure surfaces only at the next deploy when Flyway sees a checksum mismatch. The cost of silence here is much higher than the cost of a wrong refusal.

The policy-self-edit case mirrors the architecture-test case structurally: both are governance files the agent could weaken to make the immediate task easier; both have the same right answer (refuse silent edits, route explicit ones through architecture-review). Treating them as sibling refusal patterns is consistent.

**Mechanics:**

- `core/skill/operating-mode.md` Step 4 — refactored "do not modify the architecture-test files" line into a "Do not silently modify governance — refuse, don't proceed" subsection listing the three patterns (architecture-test, agent-policy.yaml, already-shipped migrations).
- `core/templates/skills/persistence-change-checkpoint.md` — new "Existing migrations are immutable" section with the V1/V2 mechanic and the Flyway/Liquibase checksum context.
- `core/templates/skills/boundary-violation.md` — "rule is too strict" pattern points at the operating-mode refusal section.
- `demo-source/docs/agent/persistence-change-checkpoint.md` and `boundary-violation.md` — synced from the templates.
- `dist/agent-redline/...` — repackaged.

**Revisit if:**

- An adopter reports that the policy-self-edit refusal blocks a legitimate "fix the policy mid-task" workflow we hadn't considered. The current wording lets the developer's explicit ask through; if the boundary feels wrong in practice, narrow further (e.g., "refuse only edits that loosen, not edits that tighten").
- A new persistence backend lands where in-place migration mutation is actually safe (some declarative-schema systems treat V*.sql as a desired-state spec, not a history). Then the immutability rule needs an extension-level override.
- A future skill version makes "side-effect detection" first-class (the agent reasons explicitly about which goals are in-scope and which are not). At that point the refusal patterns might be expressed as a single "no governance side-effects" rule instead of an enumerated list.

---

## 2026-05-31 (latest) — Default red zones were calibrated against real PR history

**Decision:** Two paths move out of the `spring-archunit` red defaults: `**/*Controller.java` and the default `application.yml`. Both go to the watch list. The api-review checkpoint is now triggered solely by the `api: openapi-from-controllers` structural-diff signal, not by controller-path-touch. The production-only profiles (`application-prod*.yml`) and every other red rule stay as they were.

**Alternatives considered:**

- Keep the defaults and ship calibration as a "do this before adopting" instruction. Rejected: v0.1 adopters won't calibrate before adopting; they'll inherit defaults. The defaults themselves have to be the calibrated ones, otherwise the first experience is alert fatigue.
- Calibrate against one repo and ship. Rejected: one repo's idioms don't generalize. The data needs to come from multiple services with the same extension before defaults move.
- Drop more rules. Rejected: every other red rule fires on a small minority of PRs (0–20%), inside the band the existing tuner script labels "PROBABLY RIGHT." Cutting more would weaken protection without removing meaningful noise.

**Rationale:**

The original defaults were a reasonable hypothesis: "controller files are the public API surface, so route them to api-review." Tested against ~150 PRs from three production Spring services (wallet, programs, checkout — 50 each), this rule fired on 34–42% of all PRs and only ~20% of those firings produced api/contract-shaped review discussion. That's the dominant alert-fatigue source: one rule responsible for ~80% of all RED firings, most of them not actually about API contracts. Default `application.yml` showed the same shape: 11 firings across the three services, zero useful ops-shaped review.

Moving these two paths to watch dropped the RED firing-rate from 44–54% per service to 6–20% — into the band the calibration target calls healthy. No protection was lost: the OpenAPI structural diff still triggers api-review on actual contract changes, the boundary-rule backend (ArchUnit) still blocks application-imports-adapter, schema-detect still fires on migrations.

The deeper principle this surfaced: prefer semantic / diff-based triggers over path-based ones when the signal is available. Path-touch on a controller fires on bug-fixes, refactors, parameter validation, and OpenAPI lint cleanup — none of which are API contract changes. The structural diff distinguishes them. Use path-based red only where no semantic signal exists (`**/security/**`, `terraform/**`, the architecture-test files themselves).

**Calibration data:** Full per-PR audits, firing rates, hit-rates, and the tuned-policy A/B comparison live in `.local/calibration/REPORT.md` (not committed; raw data contains internal repo content). The methodology: for each fired rule, score "useful" only when human (non-bot) review comments contained keywords matching the checkpoint type. The hit-rate score is a conservative lower bound — reviewers using domain-specific language aren't credited.

**Mechanics:**
- `extensions/spring-archunit/profile.md` — Controller and `application.yml` moved out of red into watch; new "Calibration principle" subsection codifies the operating rules.
- `core/skill/bootstrap-mode.md` Phase 3 — added the "prefer semantic triggers" rule to the existing zone-utility check.
- `docs/PHILOSOPHY.md` §3 — corollary on calibration: red zones must be tested against real PRs.

**Revisit if:**
- A new extension lands (e.g., `python-fastapi`) and its defaults haven't been calibrated against multi-repo PR history. Same standard should apply.
- An adopter reports a structural regression that the retuned defaults missed because the path moved to watch instead of red. That would suggest a specific path needs splitting (controller-A vs controller-B) rather than re-promoting the whole pattern.
- The api-review checkpoint stops firing reliably on real contract changes — that would mean the OpenAPI diff signal is too narrow and the path-based fallback should return for the gap.

---

## 2026-05-31 (later) — A feature isn't done until the demo proves it end-to-end

**Decision:** Every user-facing feature in agent-redline must be demonstrable end-to-end on the paired demo repo (`agent-redline-demo`) before we can call it shipped. "End-to-end" means a real branch, a real PR, real CI runs, and a verdict comment that reflects what the feature claims to do — not just unit tests or golden fixtures showing the reporter's *byte-equal* output for a synthetic input.

If a feature can't be demonstrated on the demo, it isn't finished. Either the demo grows a new scenario, or the feature is rolled back to "documented + roadmap" until the demo can show it.

**Alternatives considered:**
- Trust unit tests and golden fixtures for "the reporter does X correctly," and treat live demos as nice-to-have polish. Rejected: the agent-redline pipeline is not a single function. It's a chain — agent classification → policy lookup → reporter → CI workflow → branch protection → PR comment → label-based checkpoint flow. Unit tests prove the *segments*; only a live demo proves the *chain*. The October 2026 smoke session caught real chain-breaks (missing `architecture-reviewed` label flow, stale check names, sync-demo not preserving labels, the openapi-from-controllers Spring Boot wiring) that no unit test would have caught.
- Document the feature as "covered by unit tests, not yet demoed" in SPEC §15. Rejected: that's how features end up shipping with subtle integration bugs that surface only when a real adopter wires them up. We've already seen this pattern with `prRules.rejectVerboseGeneratedDescriptions` — a schema field that was never wired into the reporter. End-to-end demos make that class of bug impossible to miss.
- Demo only the "interesting" scenarios. Rejected: every feature looks unremarkable to whoever wrote it. The point is the reviewer (or future operator) reading the demo's PR list and seeing the feature actually fire.

**Rationale:**
- A feature whose sole evidence is a unit test passes a much weaker bar than the spec promises. SPEC §14 says "an agent modifying a public API is forced through an api-review checkpoint" — that claim only holds when there is an actual PR on actual GitHub doing exactly that. Otherwise the success-criteria item is aspirational.
- Demos are also the documentation that doesn't lie. When someone evaluates agent-redline, the four (now six) live PRs on the demo repo are the most credible artifact we ship — more than the README, more than the docs. Each live PR is a *use case*, executable.
- The cost is bounded. Adding a new scenario is ~10 minutes of work in `demo-source/pr-scenarios/<name>/` plus a sync. The cost pays back the first time a future change accidentally breaks the chain.
- The principle has a clear stopping rule: when SPEC §14 / SPEC §15.1 lists a capability, there must be a demo PR scenario that exercises it. No demo, no claim.

**Mechanics:**
- Each user-facing feature gets a corresponding `demo-source/pr-scenarios/<name>/` directory (`branch.txt`, `description.md`, `apply.sh`, `expected-verdict.md`, optional `labels.txt`).
- `scripts/sync-demo.sh --push` recreates the canonical PRs on every sync. The four-now-six PRs always reflect what `main` claims to do.
- SPEC §14 (success criteria) and §15.1 (what ships in v0.1) are the index. If a row in either list doesn't have a corresponding demo PR scenario, the entry is unfinished.

**Test guard:** This is a *project guideline*, not a runtime check. The enforcement is reviewer discipline + the SPEC §14 checklist. The live demo's CI status is the failure signal: if a feature's demo PR drifts from its expected verdict, the regression is visible without anyone running a test.

**Revisit if:**
- The demo grows past the point of being readable at-a-glance (more than ~10 PR scenarios). At that point we'd want sub-grouping or a demo index, not a relaxation of the rule.
- A feature genuinely can't be demonstrated in a single Spring/JVM repo (e.g., cross-repo signal). Then the "demo" might be two paired demo repos, but the rule still holds — there must be *something* live and runnable.

---

## 2026-05-31 (rename) — `zones.grayWatch` → `zones.watch`

**Decision:** Rename the additive-tag zone field from `grayWatch` to `watch`. The `Gray-watch` label in the PR comment becomes `Watch`. JSON output exposes `zones.watch` instead of `zones.grayWatch`. Schema, reporter, templates, skill files, docs, fixtures, and the tuning script all updated. No back-compat shim — pre-v0.1, no consumer policies in production.

**Alternatives considered:**
- Keep `grayWatch`; explain it more clearly in docs. Rejected: a name is itself documentation. Misleading names tax every new reader forever; docs that explain misleading names are a sign the name is wrong.
- Rename to `surface`, `highlight`, `notable`. Rejected: `watch` is shorter, more familiar (the "watch list" mental model is universally understood), and reads naturally in YAML (`zones.watch:`).
- Drop the additive concept entirely; force users to choose one zone per file. Rejected: the additive case is real (a domain entity that's also a Spring `*Configuration.java`, a controller that's also a security path). The semantics are right; only the name was wrong.

**Rationale:**
- The old name implied `grayWatch` was a kind of gray. It isn't — a file can be `red+watch`, `blue+watch`, or `gray+watch`. The "gray" half of the name was a lie in two of three composition cases.
- `watch` is what the field functionally is: a watch list. Reviewer wants to see this path when it changes, regardless of how it's classified otherwise.
- The rename surfaced a missing doc: SPEC §4.4 now explicitly contrasts gray (residual bucket; "no zone matched") with watch (additive tag; "explicitly tagged"), with a side-by-side table. This was implicit in the code but never written down.

**Test guard:** `tests/reporter/test_reporter_unit.py::TestClassifyFiles::test_watch_is_additive_with_blue` asserts the additive composition. The schema rejects unknown top-level zone keys (via `additionalProperties: false`), so a stray `grayWatch:` in a future policy fails validation immediately.

**Revisit if:** never. The right time to rename was before users had policies in production; that time is now. The tax of keeping the misleading name compounds with every new user.

---



**Decision:** The red-zone definition in SPEC §4 is sharpened: *red means a change wants different review behavior, not that the code is important*. The Spring profile defaults are rewritten to a narrower red surface (repository/gateway interfaces, controllers, migrations, security paths, arch tests, prod runtime config); most domain and application code goes on the `watch` list by default. Bootstrap Phase 3 mandates a "would this red zone fire on a typical PR?" check for every entry. A new `scripts/agent-redline-tune.py` computes per-zone firing rates from a batch of merged PRs so teams can validate their starting policy with data, not intuition. Shadow mode is reframed as two distinct decisions — zone calibration (windows 1) and check-flip tuning (window 2).

**Alternatives considered:**
- Keep the maximalist defaults ("anything in `domain/**` is red") and rely on per-team customization. Rejected: tested empirically against 30 recent merged PRs in a real Spring service. The maximalist defaults produced 67% RED PRs with `Controller.java` alone firing on 53% of PRs. That's the alert-fatigue scenario where every PR says "architecture review required" and the team learns to ignore it.
- Frequency-aware automated tuning inside the reporter (history file, rolling window, auto-recommendations). Useful but later; v0.1 ships the manual version (the tuning script) so users can run it on demand.
- Make the bootstrap conversation softer ("are these zones right?"). Tried; not enough. Developers confirm what the tool proposes. The check has to be active — "name three recent PRs and tell me which red entries would have fired."

**Rationale:**
- Verified empirically. Same 30 wallet PRs, two policies:
  - Old defaults (broad `domain/**` red): **67% RED, 30% GRAY, 3% BLUE.** Highest red entry firing on 53% of PRs.
  - New defaults (narrow red, generous `watch` list): **30% RED, 67% GRAY, 3% BLUE.** Highest red entry firing on 17% of PRs.
- The new defaults route attention to the ~30% of PRs that genuinely warrant a checkpoint, while still surfacing the routine domain/application changes in the PR comment via the `watch` list. That's the asymmetry the framework was supposed to deliver and the broad defaults broke.
- The tuning script is deliberately scoped to "manual run on demand against a batch of PRs." Not a CI scheduled job, not a history file, not auto-policy-edits. The point is to give the team a number; the team interprets it. v0.1 stays small.

**Test guard:** the wallet experiment lives at `.local/wallet-tune/` (gitignored) and can be re-run any time the defaults change.

**Revisit if:**
- A real bootstrap pass produces a policy where the new narrow defaults *under-fire* — a team in shadow finds genuine structural risks falling onto the `watch` list and not flagged. At that point, profile-level fixes for that pattern.
- The manual tuning script's "stare at a markdown report once" UX proves insufficient — for example, teams want to run it weekly and notice trends. Then the automated history-tracking version moves up the roadmap.

---



**Decision:** When `api.type: openapi-from-controllers`, the reporter accepts two pre-generated spec files (`--api-spec-base`, `--api-spec-head`) and computes a structural diff. It does NOT run `generationCommand` itself. The CI workflow is responsible for producing both specs (typically `git worktree add` at the base SHA, run the policy's `generationCommand` in each tree, capture the output). The local pre-push check skips the generation entirely and falls back to red-zone path classification — touched controllers fire api-review without the structural detail.

**Alternatives considered:**
- Reporter runs `generationCommand` itself for both base and head, performing the worktree dance internally. Rejected: the reporter is a pure path-globs-and-output-readers script. Adding "checkout an old SHA, invoke a build tool, capture artifacts" turns it into an orchestrator. Different CI systems checkout differently; different build tools have different output paths; failure modes multiply.
- Local pre-push runs the generation. Rejected: two builds during a pre-push is hostile to developer flow. Devs would disable the hook within a week.
- Don't implement openapi-from-controllers at all; tell users to commit a spec. Rejected: SpringDoc-style runtime generation is the dominant Spring pattern. Saying "commit a spec or don't use this" excludes most modern Spring services.

**Rationale:**
- The CI workflow already has the SHAs, the build tools, and the time budget for two builds. The reporter has the diff logic. Each does what it's good at.
- The asymmetry between CI (full diff) and local (path classification only) is real and worth being honest about. The PR comment shows the structural diff because CI saw both specs; locally you see "you touched a controller." That's not a bug — it's where the two contexts have different costs.
- The structural diff is intentionally descriptive, not classificatory. "Breaking vs additive" sounds useful but is a tarpit: response-shape changes, deprecation semantics, parameter-validation tightening — categorizing them mechanically produces false certainty. "These paths and methods changed" is enough signal to drive the api-review checkpoint; reviewers (human or agent) judge severity.

**Test guard:** `tests/reporter/api-changed-controllers/` golden fixture exercises the spec-diff path. `tests/reporter/test_reporter_unit.py` `TestOpenApiDiff` covers the diff function directly.

**Revisit if:** a real consumer asks for breaking-vs-additive classification with concrete cases that can't be expressed as policy-level checkpoint thresholds. At that point the right surface is probably an LLM-judge layer reading the structural diff, not heuristics in the reporter.

---

## 2026-05-31 — Bootstrap composes with existing setup, doesn't overwrite

**Decision:** Bootstrap-mode explicitly checks for and composes with three things the consuming repo may already have: (a) an existing boundary-rule backend setup (an ArchUnit test for JVM), (b) an existing agent-instruction file (`AGENTS.md`, `CLAUDE.md`, `GEMINI.md`, `copilot-instructions.md`, `*-instructions.md`), (c) an existing pre-push hook or script. In each case bootstrap appends or chains rather than replacing.

**Alternatives considered:**
- Always generate fresh artifacts; tell developers to merge manually. Rejected: that's a guaranteed adoption killer in any repo with a year of history. The first thing the dev sees is "agent-redline overwrote my arch test" and they won't trust the next thing it does.
- Detect but ask the developer interactively for each case. Considered, but the conversation is already long. Detect, propose, and write the composition in one shot; developer reviews the diff in their IDE the same way they'd review any other PR.

**Rationale:**
- A real Spring service in any mature shop already has an arch test, an agent guide, and a pre-push hook. agent-redline's value is in the *policy* and *checkpoint routing*, not in generating files that already exist.
- Composing is a small skill change (instructions in `bootstrap-mode.md`) but a large adoption change. Without it, bootstrap fails on most real repos.

**Revisit if:** a real bootstrap pass surfaces a repo where the existing setup is so divergent from agent-redline's model that composition produces a worse result than fresh generation would. At that point document the case and let the developer choose explicitly.

---



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
---

## 2026-06-01 — Python extension uses import-linter; adapter script required

**Decision:** The reference Python extension uses [`import-linter`](https://import-linter.readthedocs.io/) as the boundary-rule backend, with an adapter script (`extensions/python/scripts/run-import-linter.py`) that runs it and emits the `json-violations` format.

**Why:**

- import-linter is the most mature Python tool for layered/forbidden import contracts. Its five built-in contract types (`layers`, `forbidden`, `independence`, `protected`, `acyclic_siblings`) cover the boundary rules a Python extension needs.
- import-linter has **no machine-readable output**: its CLI emits Rich-formatted text and its public Python API exposes only a boolean pass/fail. The internal `create_report(...)` API is what its own CLI uses; the adapter calls it and walks the resulting `Report.get_contracts_and_checks()`.
- Each contract type has a different metadata shape (`layers` uses `invalid_dependencies` with `importer`/`imported`; `forbidden`/`independence` use `invalid_chains` with `downstream_module`/`upstream_module`; `protected` uses `illegal_imports` as objects with `.illegal_links`). The adapter handles all five with a fallback that stringifies unknown metadata.
- The adapter pins `import-linter>=2.0,<3` because it depends on internal modules that may move between major versions. A `--help`-runnable standalone script is part of the contract; CI catches incompatible versions explicitly.

**Revisit if:**

- import-linter ships a JSON-output flag (the upstream issue exists). The adapter would shrink to a thin `subprocess` call and the contract dependency on internals would dissolve.
- A different Python tool (e.g. `pydeps`-based, custom AST analyzer) becomes more capable. import-linter's static-graph approach is the limiting factor for catching dynamic imports; a runtime-tracing backend would catch more, at higher complexity.

## 2026-06-01 — Reporter dispatches on `boundaryAdapter.outputFormat`; second native format is `json-violations`

**Decision:** The reporter learns to read a second boundary-output format alongside `junit-xml`: `json-violations`, defined by `core/schema/boundary-violations.schema.json`. The new `boundaryAdapter` block in `agent-policy.yaml` (mirroring extensions' `adapter.yaml`) tells the reporter which format to expect; CI flags `--boundary-report` and `--boundary-format` are the canonical interface.

**Why:**

- SPEC §15.3 already promised reporter dispatch on `adapter.yaml` "when the second extension lands." Python is that second extension.
- `json-violations` is the natural format for backends that don't natively produce JUnit XML (forcing a JSON-to-XML conversion would be tortured). It generalizes cleanly to future ecosystems (Go, Rust, Semgrep) that emit JSON or text.
- The legacy `--archunit-xml` flag stays as a deprecated alias indefinitely; existing Spring CI snippets keep working unchanged.
- Keeping the schema small (one `version`, one optional `source`, one `violations` array of `{rule, detail, severity}`) makes it cheap for any future backend's adapter to emit.

**Revisit if:**

- A third format is genuinely needed (SARIF is the obvious candidate). Adding a third dispatch arm is mechanical; we just don't ship it before there's a user.

## 2026-06-01 — Extension contract revised: `scripts/` permitted as a narrow exception

**Decision:** Extensions may include a `scripts/` subdirectory containing focused adapter scripts when the boundary-rule backend has no machine-readable output. The previous claim in `docs/EXTENSIONS.md` ("markdown plus one small YAML file. No scripts, no parsers, no plugins") was wrong; the corrected text constrains scripts narrowly.

**Why:**

- import-linter forces this. No conversion-step-in-`scaffold.md` workaround produces an honest result; the build-time script ends up doing exactly what `extensions/python/scripts/run-import-linter.py` does anyway, just hidden behind a `pip install` of a community converter we'd have to maintain or vendor.
- The constraints retain the original intent: scripts MUST be pure output-format converters; MUST NOT replicate reporter logic, classify zones, or compute checkpoints; MUST be runnable standalone with `--help`. The audit surface is small.
- This affects only the small minority of backends without machine-readable output. Spring/ArchUnit, dependency-cruiser, go-arch-lint, cargo-deny all produce something the reporter can read either natively or via well-supported converters.

**Revisit if:**

- An adapter script grows beyond the narrow constraints and starts embedding reporter logic. That would mean the contract is wrong; either pull the logic into the core or split the script's responsibilities cleanly.
- A future extension's script needs persistent state, daemon behavior, or anything beyond stdin-or-config-in / file-out. Same response.

## 2026-06-01 — Multi-package layout treated as a layout variant, not a fourth shape

**Decision:** Repos where each architectural layer is its own top-level package (`api/`, `core/`, `storage/`, ...) instead of children of a single parent package are recognised as the **multi-package layout** of the existing **layered service** shape, not as a separate fourth Python shape. Detection: ≥2 top-level dirs each contain `__init__.py` AND none matches the project name from `pyproject.toml` AND no `src/` dir.

**Why:**

- The zones, watch list, and Django addendum are unchanged from src-layout / flat. Only the `[tool.importlinter]` config and contract shape differ — `root_packages` (plural) instead of `root_package`, with top-level layer names instead of `<pkg>.layer` names.
- Treating it as a fourth shape would split the profile across four parallel sections that mostly say the same thing. A layout variant is the lighter lift.
- import-linter's `forbidden` contract checks transitive imports by default, which makes multi-package contracts unsatisfiable when one layer (e.g. `core`) bridges multiple siblings. Multi-package examples in the profile set `allow_indirect_imports = true` and explain why; the regression test (`tests/skill-toml/`) enforces this on examples.

**Revisit if:**

- A repo shape emerges that genuinely needs different zones, not just different contract config. That would justify a new shape, not a layout variant.

## 2026-06-02 — Push-driven CI as a first-class flow mode

**Decision:** Bootstrap proposes one of two CI workflow shapes based on the consuming repo's actual flow: **PR-driven** (`on: pull_request:`, sticky-comment surface, fail on exit 2) or **push-driven** (`on: push: branches: [main]`, `$GITHUB_STEP_SUMMARY` surface, fail the agent-redline workflow on `EXIT != 0` so GitHub's default workflow-failure email fires for both RED and BOUNDARY_VIOLATION). Neither is the "default"; bootstrap detects the dominant flow during Phase 1 and proposes the matching shape. The reporter is invoked with `--flow-mode push` so checkpoint text reads as a review obligation on the commit (no CODEOWNER / label phrasing — neither applies on a direct push).

**Why:**

- Solo developers and trunk-based teams don't have a PR review surface. The PR-shaped workflow proposes machinery (sticky comment, CODEOWNERS routing, `architecture-reviewed` label) that has no consumer.
- The reporter exit-code contract (0/1/2) stays unchanged — it's what makes the local pre-push check work for solo developers regardless of CI shape. The flow modes differ only in trigger, diff method, surface, and how the enforce step gates the workflow.
- **agent-redline ships as its own `.github/workflows/` file.** Each `.yml` under `.github/workflows/` is an independent workflow run with its own conclusion / badge / email. Failing the agent-redline workflow on a red-zone push does not fail the repo's other CI (tests, builds, linters); they run in parallel. A reviewer scanning a commit sees two independent badges. Branch protection (when used) can require agent-redline green for merge, or treat it as informational, per repo policy.
- **The notification channel is GitHub's default email-on-failure.** When a workflow run fails on a `push:` event, GitHub emails the user who triggered the run (per documented Actions notification settings). For both RED (exit 1) and BOUNDARY_VIOLATION (exit 2), the agent-redline workflow concludes `failure` so this email fires. The email links to the run page where `$GITHUB_STEP_SUMMARY` renders the verdict.
- **The "approve" question doesn't have a mechanism, and doesn't need one.** A red workflow run is per-commit historical evidence: this commit needed human review. The next push that touches no red zone produces a green run going forward. There is no flag to flip because there's no merge gate to unlock — the change has already landed; the badge is the audit trail.
- **Why not `action_required` / orange Check Run / SARIF / etc.** Earlier iterations tried these. None of GitHub's UI surfaces render `action_required` Check Runs on the commit list outside of PR contexts (verified empirically on `agent-redline-python-demo`). SARIF solves a different problem (persistent finding queue with dedup) and lives in the Security tab, semantically odd for architectural findings. Those aren't a fit; the framework should not invent UI affordances GitHub doesn't have.

**Revisit if:**

- A future GitHub primitive emerges that genuinely renders "non-blocking advisory" at-a-glance for direct-push commits.
- The agent-as-pusher case (a service-account / bot pushes commits, while a human maintainer is the intended reviewer) becomes a primary use case. GitHub's default email goes to the triggering user — i.e. the bot. A documented webhook-on-failure step would be the addition; not built today because no consumer asked for it.
- Detection of the dominant flow turns out to be unreliable. Currently the signal is "merged-PR count vs commit count over the last 30 days." So far that's correct on every real repo bootstrapped.

**Earlier iterations (recorded so we don't repeat the loop):**

1. **Fail on exit 1 OR 2** (initial design). Conflated "you touched something risky" with "structurally broken." Every red-zone push became a permanent red badge that needed manual dismissal as ceremony. Wrong.
2. **`action_required` Check Run posted via `gh api .../check-runs`, workflow stays green on exit 1.** Designed for at-a-glance triage between RED and BOUNDARY_VIOLATION via icon color (orange vs red). The orange icon does render on the run-page sidebar, but **not** on the commit list / branch view / Actions tab — verified empirically. Workflow staying green on exit 1 also disabled GitHub's default email-on-failure, killing the notification channel for the agent-as-pusher case (the email going only to the bot account). Wrong on both counts.
3. **Current shape:** workflow fails on `EXIT != 0`, email-on-failure fires, run-summary carries the RED-vs-BOUNDARY_VIOLATION distinction in body text, agent-redline ships as its own workflow file so the red badge is scoped. Push-mode reporter renders checkpoint text as a review obligation on the commit, since CODEOWNER approval / label satisfiers don't apply on a direct push.

## 2026-06-02 — Tuner takes either PR history or push history as input

**Decision:** `scripts/agent-redline-tune.py` accepts a new `--push-history` mode that walks `git log <branch>` and treats each commit as one changeset. Existing `--pr-dir` / `--pr-list` / `--repo` modes are retained. The output's "changeset(s)" terminology is generic across both modes.

**Why:**

- A tuner that requires merged PRs is useless on solo / trunk-based repos. The data exists (commits to the long-lived branch are the unit of change); only the input source needed generalising.
- Squash-merged PRs collapse to one commit on the destination branch, so `--push-history` and `--repo` (PR mode) produce roughly comparable samples on volume. The threshold (30 changesets) applies to either.
- The tuner runs read-only inside the agent-redline skill (`<skill-root>/scripts/agent-redline-tune.py`) — it queries GitHub via `gh` (PR mode) or `git log` against a local clone (push mode). Doesn't write into the consuming repo.

**Revisit if:**

- A consuming repo wants per-author / per-time-window slices (e.g., "only commits in the last 6 months", "exclude bot commits"). Could become extra `--push-history` filters.

## 2026-06-02 — Skill correctness has multiple regression layers, one per bug class

**Decision:** When a bug surfaces in a real bootstrap or smoke run, fix the instance AND add a regression layer that catches the underlying *class* of bug. Each test layer below was added in response to a real bug:

| Layer | Bug class caught | Triggered by |
|---|---|---|
| `tests/skill-yaml/` | YAML examples in skill markdown that don't validate against the policy schema | Pallium Round 1 |
| `tests/skill-refs/` | Path references in skill markdown that don't resolve to a shipped file or documented vendor instruction | Pallium Round 2 |
| `tests/skill-scripts-runnable/` | Python `import` references in shipped scripts that resolve in source but not in dist | Pallium Round 5 |
| `tests/skill-toml/` | `[[tool.importlinter.contracts]]` examples with wrong field names (`container=` vs `ancestors=`, missing `allow_indirect_imports` for multi-package) | Pallium Round 3 |
| `tests/scaffold-ci/` | Scaffold reporter run-blocks missing required pattern elements (set +e, EXIT capture, sticky comment, enforce step) | Pallium Round 4 |
| `tests/scaffold-ci-e2e/` and `scaffold-spring-e2e` | Scaffold run-block extracted, executed end-to-end against fixture; verdict shape asserted | Internal (push-driven feature work) |
| `tests/bootstrap-detect/` | Profile detection table missing a layer dir (caught `api/` was missing from the layered-service signal) | Internal (caught while building the test) |
| `tests/tuner/` | Tuner crashes / wrong output on edge cases (empty repo, missing branch, empty commit, limit > available) | Internal (pre-emptive after Round 5) |

**Why:**

- Each layer catches a class of bug, not just the original instance. If the same shape of bug appears again — different file, different field name, different missing reference — the existing layer catches it before it reaches a consuming repo.
- Each layer is verified by transiently reverting its target fix; if the test doesn't fail under the revert, it isn't testing what it claims to.
- Skill content is harder to test than runtime code because most of the "behavior" is what an agent does after reading it. The framework can't run agents in CI. So instead, every concrete artifact the skill produces (YAML examples, file references, contract definitions, scaffold patterns) gets a structural test that asserts the artifact's shape is right.

**Revisit if:**

- A new bug class emerges that isn't covered by an existing layer. Add a new layer; don't try to retrofit an existing one.
- A layer grows brittle (false positives on legitimate changes). Either tighten the assertion (the empty-commit case in `tests/tuner/` was tightened from "either outcome OK" to "must skip empty" to make the test meaningful) or split the layer.

# FAQ

## Why "redline"?

A redline is a contract review marking — what *must not* change without explicit attention. Red-zone code in agent-redline is exactly that: code where changes require explicit human attention.

## Why a skill instead of a CLI?

Three reasons, in rough order of importance:

1. **Adoption gradient.** A skill is one file you drop into your harness. A CLI requires installation, configuration, and a CI integration story before it's useful. The skill produces value as soon as the agent reads it.

2. **Self-bootstrapping.** The skill walks the agent through setting governance up in the repo. No init wizard, no separate config flow — the same conversation that adopts the skill also produces the policy.

3. **Portability.** Any harness that loads markdown skill files can use it: Claude Code, Codex, Cursor agent mode, internal harnesses. A CLI would need its own distribution per platform.

A small reporter script exists for CI use. It's a supporting component, not the entry point.

## Does this require my repo to be hexagonal?

No. The `spring-archunit` extension uses hexagonal package names because it's a clean reference layout, but bootstrap adapts to the actual layout. A flat or layered repo gets a flatter zone definition. A monorepo gets per-module policies (or one root policy with module-aware globs).

agent-redline works best when the codebase has *some* recognizable structure to protect. If the codebase has no boundaries, agent-redline can't invent them. It can highlight where boundaries are missing, but it won't impose a model that isn't there.

## What if the repo has no meaningful structure?

agent-redline can only protect boundaries the team is willing to name and enforce. If there are no recognizable architectural seams — no domain/adapter split, no port interfaces, no clear API surface — there's nothing to classify red and nothing for boundary rules to enforce.

In that case, the realistic options are:

- **Decline to use agent-redline yet.** Do the modeling work first. Decide what the boundaries should be. Then revisit.
- **Use it for the parts that do have structure.** Configuration, migrations, security paths, public API files often have recognizable identity even when the rest of the codebase doesn't. A partial policy is fine; agent-redline doesn't require full coverage.
- **Use only PR-size and the skill's PR-discipline guidance.** Even without zones or boundary rules, the discipline rules around PR shape and verbose generated descriptions still apply.

The skill should be honest about this during bootstrap rather than fabricate zones the team doesn't believe in.

## What if my team already has architecture rules?

Less work. Bootstrap detects existing boundary-backend setups (ArchUnit tests on JVM, dependency-cruiser configs on Node, etc.), existing CODEOWNERS rules, existing CI checks. Where they exist, agent-redline composes with them rather than duplicating them.

(In v0.1 the reporter only ingests boundary results from Spring/ArchUnit JUnit XML. For other ecosystems, the existing rules keep running as they always did; agent-redline contributes zone classification, checkpoints, and PR-size checks on top. Generic boundary-backend dispatch is roadmap.)

## What if my team has no architecture rules?

agent-redline starts you with a default set based on the language extension you pick. You decide which to keep. There's no requirement to adopt rules that don't fit.

## What if my stack has no language extension?

Three honest options, in order of effort:

1. **Use agent-redline without a backend.** Zone classification, PR discipline, checkpoint routing, and the agent-side skill discipline work without a boundary-rule backend. You lose the deterministic boundary check but keep the rest. The extension (or the consuming repo's policy) declares `boundaryAdapter.outputFormat: none` and the reporter skips the boundary section of the verdict.
2. **Build an extension.** Extensions are markdown plus a small YAML file (plus an optional adapter script when the backend has no machine-readable output). See [EXTENSIONS.md](EXTENSIONS.md). For most mainstream stacks the recommended backend already exists; an extension is wiring, not invention.
3. **Use Semgrep as a generic backend.** Pattern-based, multi-language, less precise than language-native tools but works as a fallback. Convert its output to `json-violations` in a small adapter script.

## How do I add agent-redline to my Python repo?

Same flow as any other stack: drop the packaged skill into your harness, then ask it to set up agent-redline. The skill will:

1. Inspect the repo and pick the right Python shape (layered service, library/package, or zone-only fallback). For Django repos it auto-applies the Django addendum (settings/urls/migrations red-zoned, cross-app independence contracts).
2. Generate `[tool.importlinter]` in `pyproject.toml` with default contracts (`layers`, `forbidden`, `independence`, `acyclic_siblings`) tuned to the actual layer directories it finds.
3. Drop `scripts/run-import-linter.py` (the adapter that runs import-linter and emits the JSON the reporter reads), `scripts/agent-redline-check.sh`, and a CI workflow proposal.
4. Write `agent-policy.yaml` with `boundaryAdapter.outputFormat: json-violations`.

The Python extension lives at [`extensions/python/`](../extensions/python/); the layout details are in [`extensions/python/profile.md`](../extensions/python/profile.md). The paired demo (`agent-redline-python-demo`) exercises the three canonical PR states end-to-end.

## How is this different from CODEOWNERS?

CODEOWNERS routes review by file ownership. agent-redline routes review by architectural consequence. The two are compatible: agent-redline checkpoints can be satisfied by CODEOWNER approval, by labels, or by both.

CODEOWNERS doesn't catch boundary violations; it only routes review. agent-redline catches them deterministically through a boundary-rule backend (ArchUnit on JVM, import-linter on Python, dependency-cruiser on Node, etc.).

## How does this differ from ArchUnit / Modulith / dependency-cruiser / Import Linter?

Architecture tools enforce dependency rules in tests or CI. They tell you *after the fact* that a forbidden import landed; they don't influence the agent that wrote it.

agent-redline tells the agent which rules matter *before* it edits, refuses agent shortcuts that would weaken them (modifying the architecture-test files, suppressing a rule, laundering the import through another package), and adds zone-aware PR routing for non-rule risk that those tools don't model — red-zone path touches, persistence migrations, API surface diff, PR-size limits.

Use them together. agent-redline's `spring-archunit` extension *generates and depends on* ArchUnit tests; it doesn't replace them. The deterministic boundary check in the PR verdict is fed by the same JUnit XML the architecture tests produce.

## How does this differ from CodeRabbit / Qodo / PR-Agent / generic AI code review?

Those tools generate LLM-written line review across the whole diff. agent-redline produces a single deterministic verdict on a narrow question: does this PR touch architecturally consequential paths, and are the required checkpoints satisfied?

It is not a reviewer; it is a router. It says "a human with architecture context needs to look at this" — it does not attempt to be that human. The verdict is a few lines, not a wall of comments. The two coexist: agent-redline routes attention; the AI reviewers (or human reviewers) then look at the lines.

## Will agents actually follow the operating-mode rules?

Some will, some won't. The skill teaches; CI enforces. If an agent ignores the skill and produces a boundary-violating PR, the boundary-rule backend (when one is wired up — Spring/ArchUnit in v0.1) fails CI in binding mode. If an agent ignores the skill and modifies a red-zone file, the reporter flags it; whether the missing checkpoint blocks merge depends on whether `report` is set to `binding` (shadow by default — see [CI_INTEGRATION.md](CI_INTEGRATION.md)).

The skill is for cooperative cases. CI is for the rest. Neither alone is sufficient.

## What about agents that try to disable the rules?

Two safeguards:

1. The architecture test files are red-zone in every policy. Modifying them requires `architecture-review`. An agent that tries to weaken or delete a boundary rule trips its own discipline.

2. The reporter surfaces any change to the boundary-backend definition files (ArchUnit tests, dependency-cruiser config, Semgrep rules, etc.) in its verdict, regardless of zone classification. Even if a policy is misconfigured, this kind of attempt surfaces.

Neither is bulletproof against a determined bad actor. agent-redline is not a security perimeter. It's a discipline layer for cooperative agents and an enforcement layer for legitimate mistakes.

## How big should a PR be?

A per-team decision. Bootstrap proposes generous defaults (50 files / 1000 lines warn; 100 files / 2000 lines fail) so the tool doesn't fight existing workflow. Tighten over time as the team adapts.

The principle: a PR exceeds the human attention budget if a reviewer can't read it carefully in one sitting. Teams typically discover their actual threshold during shadow mode.

## What's the difference between a zone and a boundary rule?

A zone classifies a *path*: "this file is dangerous to change."
A boundary rule classifies a *dependency*: "this code may not depend on that code."

A change can be in a blue zone but still violate a boundary rule. An agent editing an adapter mapper (blue) to import a domain class incorrectly violates the boundary rule.

You'll typically declare both. Zones tell the skill where to slow down. Boundary rules tell the boundary-rule backend (ArchUnit on JVM, import-linter on Python, dependency-cruiser on Node, etc.) what dependencies to forbid.

## Do I need OpenAPI?

No. If the repo has no public API surface, set `api.type: none`. If the repo has API surface but doesn't use OpenAPI, treat the API contract files (proto, GraphQL schema, etc.) as red-zone paths and skip the diff step.

If the repo uses SpringDoc (or another runtime spec generator) without committing the spec, set `api.type: openapi-from-controllers` with `generationCommand:`. The CI workflow generates the spec at base SHA and head SHA via a worktree, the reporter computes a structural diff, and the PR comment lists changed surface points. The local pre-push check does not run the generation (too slow); it relies on red-zone path classification — touched controllers fire api-review. See `extensions/spring-archunit/scaffold.md` §6 for the worktree pattern.

## Does agent-redline distinguish per-tenant from global migrations?

No. Anything matching `persistence.migrationPaths` triggers the `persistence-review` checkpoint. Tenant-scoped migrations (multi-tenant Flyway setups, etc.) and global schema changes look the same to agent-redline.

That's intentional for v0.1: the reviewer is in a much better position to judge blast radius than a path glob is. A "minor" tenant migration that runs across thousands of tenants can be far riskier than a global one. The checkpoint says "a human looks at this"; the reviewer (or review agent) is who decides what kind of migration it is and what review it warrants.

If your team wants different routing for the two cases, two paths today: (a) split into separate `migrationPaths` entries with different `checkpoint:` values per path, or (b) handle it via the review agent's prompt. A built-in distinction is not on the v0.1 roadmap.

## Can my agent-policy.yaml reference internal package names, internal libraries, or company-specific paths?

Yes. The "no internal terminology" discipline applies to the agent-redline framework itself — the public OSS repo, its docs, its skill files. It does **not** apply to the policy a consuming repo writes for itself.

Your `agent-policy.yaml` is as repo-specific as it needs to be: internal package roots like `com.acme.billing`, paths into a vendored library, references to internal review teams, the actual names of your boundary rules. None of that leaks back into agent-redline; the framework only sees the structure of the policy, not the values in it.

## Cross-service / cross-repo?

Out of scope for v1. agent-redline operates at single-repo scope.

The cross-service problem (one service changes its API, consumers don't know) needs a different approach — probably an orchestrator that knows the dependency graph. May revisit once single-repo is solid.

## Is this an LLM judge?

Not in v1. The signals are deterministic: zones are path globs, boundary rules are enforced by a backend (ArchUnit on JVM, etc.), API/schema are diff-based. No LLM reasoning in the loop.

LLM-judge layers (for soft checks like implicit-contract risk, modeling drift, suspiciously broad change summaries) are a candidate for later. They would run alongside the deterministic checks and produce additional signals; they would not block merge alone.

## How does this interact with Copilot / Cursor / etc.?

It doesn't, directly. agent-redline targets agentic coding (Claude Code, Codex, Cursor agent mode) where the agent has full read/write access to a repo and can read skill files.

For autocomplete-style tools, the CI side still works: the boundary-rule backend fails on boundary violations regardless of how they got introduced. The skill-level guidance ("classify before editing") doesn't apply to autocomplete.

## What about Windsurf, Aider, etc.?

Any harness that supports a skill format (or markdown instructions in a known location) can use it. The skill itself is plain markdown.

## What does success look like?

The early signals worth watching:

- Whether teams that adopt it keep it on (instead of disabling after a few weeks of false positives)
- Whether real boundary violations get caught before merge
- Whether developers can read the PR verdict and act on it without asking for help

The honest goal is "the teams that use it report fewer surprise architectural regressions." Wider adoption is downstream of that.

## Is this a product?

It's an open-source project. Whether it becomes more depends on whether anyone finds it useful.

One plausible future: the framework stays small and the ideas get absorbed into agent harnesses directly — a harness ships zone-aware classification natively, and agent-redline becomes the spec the harness implements against. That's a fine outcome.

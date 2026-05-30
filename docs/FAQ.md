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

## What if my team has no architecture rules?

agent-redline starts you with a default set based on the language extension you pick. You decide which to keep. There's no requirement to adopt rules that don't fit.

## What if my stack has no language extension?

Three honest options:

1. **Build one.** Extensions are five files, mostly markdown. See [EXTENSIONS.md](EXTENSIONS.md). For most mainstream stacks (Node, Python, Go, Rust), the recommended backend already exists in the ecosystem; an extension is wiring, not invention.
2. **Use Semgrep as a generic backend.** Pattern-based, multi-language, less precise than language-native tools but works as a fallback. An extension built around Semgrep covers many stacks.
3. **Use agent-redline without a backend.** Zone classification, PR discipline, and the agent-side skill discipline work without a boundary-rule backend. You lose the deterministic boundary check but keep the rest. The extension's `adapter.yaml` declares `outputFormat: none` and the reporter skips the boundary section of the verdict.

## How is this different from CODEOWNERS?

CODEOWNERS routes review by file ownership. agent-redline routes review by architectural consequence. The two are compatible: agent-redline checkpoints can be satisfied by CODEOWNER approval, by labels, or by both.

CODEOWNERS doesn't catch boundary violations; it only routes review. agent-redline catches them deterministically through a boundary-rule backend (ArchUnit on JVM, dependency-cruiser on Node, etc.).

## Will agents actually follow the operating-mode rules?

Some will, some won't. The skill teaches; CI enforces. If an agent ignores the skill and produces a boundary-violating PR, the boundary-rule backend fails CI. If an agent ignores the skill and modifies a red-zone file, the reporter flags it and the checkpoint blocks merge.

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

You'll typically declare both. Zones tell the skill where to slow down. Boundary rules tell the boundary-rule backend (ArchUnit on JVM, dependency-cruiser on Node, etc.) what dependencies to forbid.

## Do I need OpenAPI?

No. If the repo has no public API surface, set `api.type: none`. If the repo has API surface but doesn't use OpenAPI, treat the API contract files (proto, GraphQL schema, etc.) as red-zone paths and skip the diff step.

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

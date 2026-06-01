# agent-redline

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Agent Skills](https://img.shields.io/badge/agent--skills-compliant-blue)](https://agentskills.io)
[![Demo](https://img.shields.io/badge/demo-agent--redline--demo-purple)](https://github.com/rore/agent-redline-demo)

**The missing layer between repo instructions and CI.** agent-redline teaches coding agents when to slow down, then verifies the same structural-risk policy in the PR.

Repo instructions (`AGENTS.md`, `CLAUDE.md`) are passive — agents drift. CI checks (ArchUnit, dependency rules) fire after the fact. agent-redline makes architectural risk *binding for the agent before it edits*, then checks it deterministically at PR time.

agent-redline helps teams:

- Let agents move fast on low-risk code
- Catch dependency-boundary violations before they become architecture drift
- Flag PRs that touch APIs, persistence, security, or structural contracts
- Route human review to the changes where *"tests pass"* isn't enough

It does **not** review every line of generated code. It does **not** enforce style. It does **not** replace tests.

It identifies the small set of changes — modeling, contracts, boundaries, persistence, security — where local correctness is not enough, and makes those changes deterministically visible to humans.

## How

agent-redline is a [skill](https://agentskills.io) for AI coding agents. Drop it into your harness (Claude Code, Codex, Cursor, etc.); it activates automatically when a repo contains an `agent-policy.yaml`. The skill teaches the agent to classify each change *before* editing, slow down on the structurally-consequential ones, and refuse to work around boundary rules. Deterministic CI checks (a boundary-rule backend like ArchUnit, OpenAPI diff, path classification) catch what the agent missed.

## The model

```
Blue zone        agent autonomy is fine; tests and normal review are sufficient
Red zone         agent must slow down; human attention required (a checkpoint)
Gray zone        unclassified path; cautious by default; a tuning signal
Watch (tag)      additive — surfaces a touched path in the PR comment, no gate
Boundary rule    a deterministic dependency rule the agent may not work around
```

A **checkpoint** is satisfied by a CODEOWNER approval or a label (`architecture-reviewed`, `api-reviewed`, etc.). The reporter is deterministic; humans review only the small set of changes that actually need it.

agent-redline is a **harness component**, not a complete harness. It composes with existing architecture tools (ArchUnit, dependency-cruiser, Import Linter), instruction files (`AGENTS.md`, `CLAUDE.md`), and AI review tools — it doesn't replace them. See [`docs/FAQ.md`](docs/FAQ.md) for detailed comparisons.

## Why this exists

The novel piece isn't the rules — it's that the agent treats the rules as binding *before* it edits, not as suggestions to route around. In paired simulation runs on shortcut-tempting tasks, the with-skill agent refused both the canonical boundary bypass and a tempting weakening of the architecture test. The without-skill agent took both. Deterministic CI then catches whatever the skill misses.

LLMs increase the rate of code production sharply. Human review capacity does not scale with it. Most code agents produce is low-consequence: tests, isolated adapters, mappers, internal utilities. A minority is structurally consequential: a controller that defines a public contract, a domain class that defines an invariant, a repository import that breaks a port boundary, a migration that reshapes persistence.

Tests check behavior. They do not check structure. A feature can work, pass tests, ship in a clean small PR — and still leave the architecture worse, because the next agent will copy the shortcut. agent-redline closes that gap.

## How agents use it

**Bootstrap mode.** In a fresh repo:

> *Use agent-redline to set up governance for this repo.*

The skill inspects the repo's layout, build system, conventions, and existing CI, then:

- Generates `agent-policy.yaml` — the repo's red/blue/gray zones and boundary rules
- Generates or composes with the existing agent-instruction file (`AGENTS.md`, `CLAUDE.md`, `GEMINI.md`, etc.)
- Scaffolds a boundary-rule backend (ArchUnit on JVM in v0.1; other ecosystems are roadmap)
- Drops a local pre-push script that mirrors what CI will check
- *Proposes* (does not commit) a CI workflow, branch protection updates, and CODEOWNERS additions for human review

**Operating mode.** Activates whenever an agent works in a repo that has `agent-policy.yaml`. The agent:

- Reads the policy *before* editing
- Classifies the intended change as blue / red / gray / boundary-violating
- Works autonomously when the change is blue
- Slows down and writes a checkpoint note when the change is red
- Refuses to work around boundary rules; fixes the structure or escalates instead
- Runs the local check before opening a PR

## What a PR comment looks like

After CI runs, the reporter posts a single sticky comment summarizing the verdict. Real example from the demo's `mixed` fixture:

```markdown
## agent-redline: RED

**Red-zone files changed.**

| Zone | Files |
|---|---|
| Red  | `src/main/java/com/example/orders/domain/Order.java` |
| Blue | `src/test/java/com/example/orders/OrderServiceTest.java` |
| Gray | `src/main/java/com/example/orders/util/DateNormalizer.java` |

**Required checkpoints:**
- [ ] `architecture-review` — red-zone change: src/main/java/com/example/orders/domain/Order.java. Satisfy by: CODEOWNER approval or label `architecture-reviewed`

**Boundary check:** passed
**API check:** no changes
**PR size:** 3 files / 0 lines (ok)
```

A boundary violation looks the same shape but with the `Boundary check` line listing the violated rule and the failing class — and CI exits non-zero so the PR cannot merge.

See the live demo PRs for the three canonical states. Each sync rotates the PR numbers; the latest open PR for each branch is what to look at:

- [`demo/blue-only-pr`](https://github.com/rore/agent-redline-demo/pulls?q=is%3Apr+head%3Ademo%2Fblue-only-pr) — BLUE, green CI, no checkpoint
- [`demo/red-with-checkpoint-pr`](https://github.com/rore/agent-redline-demo/pulls?q=is%3Apr+head%3Ademo%2Fred-with-checkpoint-pr) — RED, green CI, `architecture-reviewed` label applied → checkpoint satisfied
- [`demo/boundary-violation-pr`](https://github.com/rore/agent-redline-demo/pulls?q=is%3Apr+head%3Ademo%2Fboundary-violation-pr) — BOUNDARY_VIOLATION, red CI, cannot merge

## What v0.1 ships

```
✓ path-glob zone classification (red / blue / gray + watch tag)
✓ checkpoint computation from CODEOWNER approval and labels
✓ PR-size warn / fail thresholds
✓ shadow / binding modes, with per-check overrides
✓ boundary-violation ingestion from Spring/ArchUnit JUnit XML
✓ OpenAPI structural diff (SpringDoc-generated or committed specs)
✓ bootstrap composition with existing arch tests, instruction files,
  pre-push hooks (no overwriting)
✓ bootstrap-time policy calibration against the repo's PR history
  (zone firing-rate analysis with developer approval gate)
✓ zone-calibration tuning script for ongoing shadow-mode refinement
```

```
roadmap:
  • Node / Python / Go / Rust boundary backends
  • additional output formats (SARIF, JSON-violations)
  • team: / reviewerCount: checkpoint satisfaction
  • LLM-judge soft checks
  • cross-repo signals
  • reusable GitHub Action; GitLab / Jenkins templates
```

The skill still produces zone classification, checkpoints, and PR-size checks for non-JVM repos; only the boundary-backend leg is JVM-only today.

See [`docs/SPEC.md` §15.3](docs/SPEC.md) for the roadmap and what gates each item.

## Install

Drop the packaged skill at [`dist/agent-redline/`](dist/agent-redline/) into your harness's skills directory. agent-redline follows the [Agent Skills](https://agentskills.io) standard.

Quick start (Claude Code, personal scope):

```bash
git clone https://github.com/rore/agent-redline.git
cp -r agent-redline/dist/agent-redline ~/.claude/skills/
```

Other tools and project-scope installs: see [`INSTALL.md`](INSTALL.md).

## Where to start reading

| If you want to… | Read |
|---|---|
| Understand the *why* | [`docs/PHILOSOPHY.md`](docs/PHILOSOPHY.md) |
| Install and try it | [`INSTALL.md`](INSTALL.md) |
| See the bootstrap conversation in detail | [`docs/BOOTSTRAP.md`](docs/BOOTSTRAP.md) |
| See operating-mode behavior | [`docs/OPERATING.md`](docs/OPERATING.md) |
| Read the policy schema | [`docs/POLICY_SCHEMA.md`](docs/POLICY_SCHEMA.md) |
| Build a language extension | [`docs/EXTENSIONS.md`](docs/EXTENSIONS.md) |
| Wire it into CI | [`docs/CI_INTEGRATION.md`](docs/CI_INTEGRATION.md) |
| Read the full spec | [`docs/SPEC.md`](docs/SPEC.md) |
| See common questions | [`docs/FAQ.md`](docs/FAQ.md) |

## Status

**v0.1.** Early. Things will change.

The reference language extension (`spring-archunit`) is the only stack covered today; other ecosystems are roadmap. The paired demo repo at <https://github.com/rore/agent-redline-demo> exercises bootstrap mode and operating mode end-to-end with live PRs.

Decisions and their rationale: [`docs/DECISIONS.md`](docs/DECISIONS.md). Roadmap: [`docs/SPEC.md` §15.3](docs/SPEC.md).

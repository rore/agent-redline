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
- Scaffolds a boundary-rule backend matching the chosen [language extension](#supported-stacks)
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

See the live demo PRs for the three canonical states. Each sync rotates the PR numbers; the latest open PR for each branch is what to look at.

**JVM/Spring** — [`agent-redline-demo`](https://github.com/rore/agent-redline-demo):

- [`demo/blue-only-pr`](https://github.com/rore/agent-redline-demo/pulls?q=is%3Apr+head%3Ademo%2Fblue-only-pr) — BLUE, green CI, no checkpoint
- [`demo/red-with-checkpoint-pr`](https://github.com/rore/agent-redline-demo/pulls?q=is%3Apr+head%3Ademo%2Fred-with-checkpoint-pr) — RED, green CI, `architecture-reviewed` label applied → checkpoint satisfied
- [`demo/boundary-violation-pr`](https://github.com/rore/agent-redline-demo/pulls?q=is%3Apr+head%3Ademo%2Fboundary-violation-pr) — BOUNDARY_VIOLATION, red CI, cannot merge

**Python/FastAPI** — [`agent-redline-python-demo`](https://github.com/rore/agent-redline-python-demo):

PR-driven flow (sticky comment + label-satisfied checkpoints):
- [`demo/blue-only-pr`](https://github.com/rore/agent-redline-python-demo/pulls?q=is%3Apr+head%3Ademo%2Fblue-only-pr) — BLUE
- [`demo/red-with-checkpoint-pr`](https://github.com/rore/agent-redline-python-demo/pulls?q=is%3Apr+head%3Ademo%2Fred-with-checkpoint-pr) — RED with checkpoint satisfied
- [`demo/boundary-violation-pr`](https://github.com/rore/agent-redline-python-demo/pulls?q=is%3Apr+head%3Ademo%2Fboundary-violation-pr) — BOUNDARY_VIOLATION

Push-driven flow (verdict in run-page `$GITHUB_STEP_SUMMARY`, CI red on `EXIT != 0`):
- [`push-demo-blue-only`](https://github.com/rore/agent-redline-python-demo/actions?query=branch%3Apush-demo-blue-only) — BLUE, CI green
- [`push-demo-red-zone-change`](https://github.com/rore/agent-redline-python-demo/actions?query=branch%3Apush-demo-red-zone-change) — RED, CI red (no PR-label mechanism)
- [`push-demo-boundary-violation`](https://github.com/rore/agent-redline-python-demo/actions?query=branch%3Apush-demo-boundary-violation) — BOUNDARY_VIOLATION, CI red

## Supported stacks

| Stack | Extension | Boundary backend | Demo |
|---|---|---|---|
| JVM (Java, Kotlin), Spring Boot | [`spring-archunit`](extensions/spring-archunit/) | [ArchUnit](https://www.archunit.org/) (JUnit XML) | [agent-redline-demo](https://github.com/rore/agent-redline-demo) |
| Python services and libraries (incl. Django) | [`python`](extensions/python/) | [import-linter](https://import-linter.readthedocs.io/) (json-violations) | [agent-redline-python-demo](https://github.com/rore/agent-redline-python-demo) |

The framework's stack-neutral pieces — zone classification, checkpoints, PR-size checks, the agent-side discipline — work on **any** repo. The boundary-rule backend is the ecosystem-specific piece, and is what each language extension brings.

## Extending to a new stack

A language extension is a small folder of mostly markdown:

```
extensions/<your-stack>/
├── README.md          # what stack, when to pick it
├── profile.md         # default zones, boundary contracts, gotchas
├── scaffold.md        # how bootstrap installs the backend and wires CI
├── operating.md       # (optional) stack-specific operating-mode notes
├── adapter.yaml       # tells the reporter where the backend writes its
│                      # output and what format
└── scripts/           # (optional) adapter script when the backend has no
                       # machine-readable output (the Python extension uses one)
```

The reporter dispatches on `adapter.yaml`'s `outputFormat` — `junit-xml`, `json-violations`, or `none`. Any backend that produces JUnit XML, matches the [`json-violations` schema](core/schema/boundary-violations.schema.json), or has a small adapter that converts, plugs in without core changes.

Recommended backends for stacks not yet shipped: [`dependency-cruiser`](https://github.com/sverweij/dependency-cruiser) for Node, [`go-arch-lint`](https://github.com/fe3dback/go-arch-lint) for Go, [`cargo-deny`](https://github.com/EmbarkStudios/cargo-deny) + Clippy for Rust, [Semgrep](https://semgrep.dev/) as a multi-language fallback. See [`docs/EXTENSIONS.md`](docs/EXTENSIONS.md) for the practical guide and [`docs/SPEC.md` §15.3](docs/SPEC.md) for the broader roadmap.

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

Two flow modes for CI integration: PR-driven (sticky-comment surface, fail CI on exit 2) and push-driven (CI artifact surface, fail CI on exit 1 OR 2). Bootstrap picks one based on the repo's actual flow.

Decisions and their rationale: [`docs/DECISIONS.md`](docs/DECISIONS.md). Roadmap: [`docs/SPEC.md` §15.3](docs/SPEC.md).

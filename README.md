# agent-redline

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Agent Skills](https://img.shields.io/badge/agent--skills-compliant-blue)](https://agentskills.io)
[![Demo](https://img.shields.io/badge/demo-agent--redline--demo-purple)](https://github.com/rore/agent-redline-demo)

Agent governance as a skill.

agent-redline is a skill for AI coding agents. It teaches the agent to look at a change *before* editing, decide whether the change is structurally consequential, and route human attention only to the changes that actually shape the system.

It does not review all generated code. It does not enforce style. It does not replace tests. It identifies the small set of changes — modeling, contracts, boundaries, persistence, security — where local correctness is not enough, and it makes those changes deterministically visible to humans.

## The thesis

LLMs increase the rate of code production sharply. Human review capacity does not scale with it. Most code agents produce is low-consequence: tests, isolated adapters, mappers, internal utilities — what agent-redline calls the **blue zone**. A minority is structurally consequential: a controller that defines a public contract, a domain class that defines an invariant, a repository import that breaks a port boundary, a migration that reshapes persistence — the **red zone**.

Tests check behavior. They do not check structure. A feature can work, pass tests, ship in a clean small PR — and still leave the architecture worse, because the next agent will copy the shortcut.

agent-redline classifies changes by architectural consequence:

- **Blue zone** — agent autonomy is fine; tests and normal review are sufficient
- **Red zone** — agent must slow down; human attention required
- **Gray zone** — undecided; cautious by default
- **Boundary violations** — deterministic structural rules the agent may not work around

The skill teaches agents to do this classification themselves, before editing. Deterministic checks (a boundary-rule backend like ArchUnit, OpenAPI diff, path classification) catch what the agent missed. Humans review only what crosses a checkpoint.

## How it works

agent-redline is distributed as a **skill**. You install it into your agent harness (Claude Code, Codex, Cursor, etc.) and then use it in two modes.

**Bootstrap mode.** In a fresh repo:

> *Use agent-redline to set up governance for this repo.*

The skill inspects the repo's layout, build system, conventions, and existing CI, then:

- Generates `agent-policy.yaml` — the repo's red/blue/gray zones and boundary rules
- Generates `AGENTS.md` — agent-facing instructions for this repo
- Scaffolds a boundary-rule backend for the ecosystem (ArchUnit on JVM in v0.1; other ecosystems are roadmap)
- Drops a local pre-push script that mirrors what CI will check
- Proposes (does not commit) CI workflow changes, branch protection updates, and CODEOWNERS additions for human review
- Adds a PR template with classification and checkpoint fields

**Operating mode.** Every time an agent works in a repo that has agent-redline set up, it:

- Reads `agent-policy.yaml` before editing
- Classifies the intended change as blue / red / gray / boundary-violating
- Works autonomously when the change is blue
- Slows down and writes a checkpoint note when the change is red
- Refuses to work around boundary rules; fixes the structure or escalates instead
- Runs the local check before opening a PR

## What v0.1 actually does

Be honest about the surface so you can decide if it fits:

- **Path-glob zone classification** (red / blue / gray, plus the additive `watch` tag) — yes
- **Required-checkpoint computation** with `codeownerApproval` and `label:` satisfaction — yes
- **PR-size warn / fail thresholds** — yes
- **Shadow / binding modes**, with per-check overrides — yes
- **Boundary-violation ingestion from Spring/ArchUnit JUnit XML** — yes
- **OpenAPI structural diff** for SpringDoc-style services (`api.type: openapi-from-controllers`; CI generates specs at base+head SHAs, reporter diffs) and for committed specs (`openapi-spec-file`) — yes
- **Bootstrap composition** with existing arch tests, agent-instruction files, and pre-push hooks — yes (no overwriting)
- **Zone-calibration tuning script** (`scripts/agent-redline-tune.py`) — yes (run against a batch of merged PRs to validate the policy's firing rates before flipping to binding)
- **Other ecosystems** (Node, Python, Go, Rust, Semgrep) — roadmap. The skill still produces zone classification, checkpoints, and PR-size checks for non-JVM repos; only the boundary-backend leg is JVM-only today.
- **`team:` / `reviewerCount:` checkpoint satisfaction** — roadmap.

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

Pre-v0.1, in active development. The reference language extension (`spring-archunit`) is the only stack covered today; other ecosystems are roadmap. The paired demo repo at <https://github.com/rore/agent-redline-demo> exercises bootstrap mode and operating mode end-to-end.

Decisions and their rationale: [`docs/DECISIONS.md`](docs/DECISIONS.md). Roadmap: [`docs/SPEC.md` §15.3](docs/SPEC.md).

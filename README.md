# agent-redline

Agent governance as a skill.

agent-redline is a skill that helps AI coding agents recognize structural risk in a codebase and routes human attention to the changes that actually shape the system.

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

agent-redline is distributed as a **skill**. You install it into your agent harness (Claude Code, Codex, internal harnesses, etc.) and then use it in two modes.

**Bootstrap mode.** In a fresh repo:

> *Use agent-redline to set up governance for this repo.*

The skill inspects the repo's layout, build system, conventions, and existing CI, then:

- Generates `agent-policy.yaml` — the repo's red/blue/gray zones and boundary rules
- Generates `AGENTS.md` — agent-facing instructions for this repo
- Scaffolds a boundary-rule backend for the ecosystem (ArchUnit on JVM, dependency-cruiser on Node, etc.) with the rules from the policy
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

## Install

Drop the packaged skill at [`dist/agent-redline/`](dist/agent-redline/) into your harness's skills directory. agent-redline follows the [Agent Skills](https://agentskills.io) standard, so it works with Claude Code, Codex, Cursor, Gemini CLI, and others.

Quick start (Claude Code, personal scope):

```bash
git clone https://github.com/rore/agent-redline.git
cp -r agent-redline/dist/agent-redline ~/.claude/skills/
```

Other tools and project-scope installs: see [`INSTALL.md`](INSTALL.md).

## Status

In active development; pre-v0.1. The detailed spec lives in [`docs/SPEC.md`](docs/SPEC.md). Project state, decisions, and roadmap: [`docs/DECISIONS.md`](docs/DECISIONS.md), [`docs/SPEC.md §15`](docs/SPEC.md).

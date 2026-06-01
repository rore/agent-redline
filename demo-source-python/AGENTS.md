# AGENTS.md

This repo uses [agent-redline](https://github.com/rore/agent-redline) to gate structurally-consequential changes.

## Before making changes

1. Read `agent-policy.yaml`.
2. Classify your intended change as blue / red / gray; note any `watch` paths touched (additive — surfaced in the PR comment).
3. Refuse to work around boundary rules. Don't use `importlib.import_module()` to bypass an `import-linter` contract; if a violation is justified, add an `ignore_imports` entry in `pyproject.toml` (which is itself red — requires `architecture-review`).

See [`docs/agent/`](docs/agent/) for per-checkpoint detail. The skill repo is at <https://github.com/rore/agent-redline>.

## Local check

`bash scripts/agent-redline-check.sh` — runs the same set of checks CI runs.

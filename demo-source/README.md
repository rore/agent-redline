# agent-redline-demo

The paired demo repo for [agent-redline](https://github.com/rore/agent-redline). A minimal Spring Boot service used to demonstrate the framework end-to-end against real GitHub.

This repo's content is generated from agent-redline's `demo-source/` and `examples/spring-hexagonal/`. To regenerate, run `scripts/sync-demo.sh` in the agent-redline repo.

## Two branches, two roles

### `greenfield`

Bare Spring service. **No** `agent-policy.yaml`, **no** `AGENTS.md`, **no** per-checkpoint docs, **no** CI workflow.

Use this branch to exercise **bootstrap mode**: drop the agent-redline skill into a Claude Code or Codex session pointed at a checkout of this branch, ask the agent to set up agent-redline, observe what it produces. The expected output is roughly what `main` already has.

This branch is never merged into; it stays greenfield as a clean starting point.

### `main`

Already-bootstrapped state. Has `agent-policy.yaml` at the root, `AGENTS.md` referencing it, per-checkpoint docs in `docs/agent/`, a vendored reporter at `scripts/agent-redline-report.py`, the local pre-push script, the PR template, the CI workflow, and CODEOWNERS.

Use this branch to exercise **operating mode**. The three planned PR branches below all branch from `main`.

## Three planned PRs (all branched from `main`)

Each is a real PR you can open, observe, and use to validate the end-to-end pipeline.

### `demo/blue-only-pr` → expected verdict: `BLUE`

A change to a DTO under `src/main/java/com/example/orders/adapter/persistence/dto/`. Blue zone, tests pass, no checkpoint required, CI green.

### `demo/red-with-checkpoint-pr` → expected verdict: `RED`

A change to the `Order` aggregate (red zone). The PR has the `architecture-reviewed` label applied (or a CODEOWNER approval), satisfying the architecture-review checkpoint, so the PR can merge.

### `demo/boundary-violation-pr` → expected verdict: `BOUNDARY_VIOLATION`

A change that adds a forbidden import: `OrderService` imports `PostgresOrderRepository` directly. The ArchUnit test fails on the rule `application_must_not_depend_on_persistence_adapters`. CI is red. The PR cannot merge until the structure is fixed.

## CI

`.github/workflows/agent-redline.yml` runs on every PR and push:

1. Run the architecture tests.
2. Run the agent-redline reporter against the diff.
3. Post the verdict comment to the PR.
4. Set the appropriate exit code.

For a deeper look at how this works, see [agent-redline](https://github.com/rore/agent-redline).

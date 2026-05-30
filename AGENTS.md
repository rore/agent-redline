# AGENTS.md — orientation for agents working on agent-redline

You're working on the agent-redline project itself, not a repo that uses agent-redline. The agent-redline skill is dormant here.

This is a public open-source project. No internal terminology, no marketing language, smallest-version-first discipline.

## Read first

1. **`.local/WORK_TRACKER.md`** — current state, recent decisions, what's next. Read on session start; append a session entry when finishing substantive work.
2. **`docs/SPEC.md`** — normative project specification. §5.1 has the full layout; §15 has v0.1 scope and what's done.
3. **`docs/SKILL_AUTHORING.md`** — read before editing any file an agent loads mid-task (`core/skill/*.md`, `core/templates/skills/*.md`, `extensions/*/profile.md`, `scaffold.md`, `operating.md`, generated `agent-policy.yaml` / `AGENTS.md` in consuming repos).

## Hard rules

1. **No internal or org-specific terminology.** Don't name particular companies, internal product names, internal team names, or internal service names anywhere. References to one shop's tooling leak context that doesn't belong in a public project. Keep examples generic.
2. **Skill-authoring discipline applies to every file an agent loads mid-task.** Deletion test, imperative voice, ceiling enforced.
3. **Budget compliance is enforced.** `bash tests/budget/check-budget.sh` must pass. Ceilings live in `tests/budget/budget.yaml` mirroring `docs/SPEC.md §1.4.1`. Smallest version that does the job.
4. **No marketing tone.** Developer-to-developer. If a sentence sounds like a pitch, cut it.
5. **The work tracker is the session contract.** Read first; append at end. Don't overwrite history.

## Build / test

```bash
bash tests/budget/check-budget.sh             # all files within ceilings
bash tests/budget/check-budget.sh --verbose   # show every file's utilization
```

Other validation layers (schema, reporter goldens, extension dry-run, skill smoke, demo) are roadmap; see `docs/VALIDATION.md`.

## How to update the spec

Edit `docs/SPEC.md` first. Propagate to affected docs/skills/extensions. If budgets change, update `tests/budget/budget.yaml` to match. Run the budget check. Append a tracker entry.

## When you're stuck

Don't quietly diverge from the spec. Propose, get sign-off, update SPEC first, then propagate. After structural changes, grep for stale references — the codebase is small and exhaustive checks are cheap.

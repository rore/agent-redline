# AGENTS.md — orientation for agents working on agent-redline

You're working on the agent-redline project itself, not a repo that uses agent-redline. The agent-redline skill is dormant here.

This is a public open-source project. No internal terminology, no marketing language, smallest-version-first discipline.

## Read first

1. **`.local/WORK_TRACKER.md`** — current state, what's next. Tactical session log. Read on session start; append at end.
2. **`docs/SPEC.md`** — normative project specification. §5.1 has the full layout; §15 has v0.1 scope.
3. **`docs/DECISIONS.md`** — why we chose what we chose. Read this before proposing changes that touch a prior decision.
4. **`docs/SKILL_AUTHORING.md`** — read before editing any file an agent loads mid-task (`core/skill/*.md`, `core/templates/skills/*.md`, `extensions/*/profile.md`, `scaffold.md`, `operating.md`, generated `agent-policy.yaml` / `AGENTS.md` in consuming repos).

## Hard rules

1. **No internal or org-specific terminology.** Don't name particular companies, internal product names, internal team names, or internal service names anywhere. References to one shop's tooling leak context that doesn't belong in a public project. Keep examples generic.
2. **Skill-authoring discipline applies to every file an agent loads mid-task.** Deletion test, imperative voice, ceiling enforced.
3. **Budget compliance is enforced.** `bash tests/budget/check-budget.sh` must pass. Ceilings live in `tests/budget/budget.yaml` mirroring `docs/SPEC.md §1.4.1`. Smallest version that does the job.
4. **No marketing tone.** Developer-to-developer. If a sentence sounds like a pitch, cut it.
5. **Decisions get recorded, not encoded silently.** Substantive decisions append to `docs/DECISIONS.md` with rationale; routine session work goes in `.local/WORK_TRACKER.md`.

## Build / test

```bash
bash tests/budget/check-budget.sh             # all files within ceilings
bash tests/budget/check-budget.sh --verbose   # show every file's utilization
```

Other validation layers (schema, reporter goldens, extension dry-run, skill smoke, demo) are roadmap; see `docs/VALIDATION.md`.

## How to update the spec or make a project decision

For any conceptual change: edit `docs/SPEC.md` first. Propagate to affected docs/skills/extensions. If budgets change, update `tests/budget/budget.yaml` to match. Run the budget check.

If the change involves a real decision (a fork was chosen, alternatives were rejected): append an entry to `docs/DECISIONS.md` with rationale. If it's just session work, log it in `.local/WORK_TRACKER.md`.

## When you're stuck

Don't quietly diverge from the spec. Propose, get sign-off, update SPEC first, then propagate. After structural changes, grep for stale references — the codebase is small and exhaustive checks are cheap.

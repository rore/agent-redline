# Skill authoring

How to write any file the agent loads mid-task.

## Scope

These rules apply to **any file an agent loads while working in a repo**. That includes:

- Core skill files: `core/skill/agent-redline.md`, `bootstrap-mode.md`, `operating-mode.md`
- Per-checkpoint skill docs: `core/templates/skills/*.md` (copied into consuming repos at `docs/agent/`)
- Language extension files: `extensions/<name>/profile.md`, `scaffold.md`, `operating.md`
- Generated artifacts the agent reads on each run: `agent-policy.yaml`, `AGENTS.md`

These rules do **not** apply to:

- `SPEC.md`, `README.md`, and everything else under `docs/` (read by humans evaluating the project)
- `README.md` files at the project root or inside an extension (human-facing summaries)
- This file itself

The mental model: if an agent reads it during a task, it's skill content and follows these rules. Where the file lives in the tree doesn't matter.

## Audience

A skill file is read by an agent mid-task. Write for someone executing instructions, not someone evaluating a tool. Different audience than the spec; different rules.

## The deletion test

Try cutting any sentence. If behavior would change, restore. If not, leave it cut.

Most prose in human docs would fail this test. That's fine for human docs. It's not fine for skills.

## What earns a place

Every line should change behavior. If the agent's actions are the same with or without the line, the line is overhead.

Things that earn a place:
- Vocabulary the agent will see in policies and need to map to behavior
- Loops, sequences, phases the agent has to follow
- Decision rules ("if X, do Y; if not, do Z")
- Refusal rules ("never do W")
- Lookup tables (classifications, exit codes, glob priority)
- Pointers to other files with explicit *when* to load them
- Edge-case handling the agent will encounter ("if the policy disagrees with reality, ...")

## What does NOT belong

These read well in human docs and have to be cut from skill files:

- **Marketing or pitch.** "agent-redline is a small framework for..." — the agent doesn't decide whether to use the framework; it's already loaded.
- **"What this skill does NOT do."** Define by what it instructs. The agent can't accidentally do something the skill never tells it to do.
- **Restated rationale.** "The cost of a false-RED is 30 seconds; the cost of a false-BLUE is structural debt." Reasoning belongs in `docs/SPEC.md` or `docs/PHILOSOPHY.md`, not in the skill.
- **Motivational language.** "Without this, every other rule is gameable." Just state the rule.
- **History or context.** "Originally we considered X, but we chose Y." Not relevant at runtime.
- **Defensive prose.** "This skill is not trying to..." Cut.
- **Self-referential commentary.** "This skill helps you..." The agent already loaded the skill; it knows.

## Style

- **Imperative voice.** "Classify before editing" — not "Agents classify before editing" or "The skill instructs you to classify."
- **Tables for lookup data.** Vocabulary, classifications, decision matrices. Tables are denser than prose and faster to skim mid-task.
- **Numbered lists for sequences.** Loops, phases.
- **Code blocks for templates.** Note formats, YAML sketches, command lines.
- **Specify *when* to load other resources.** "Read `scaffold.md` during the scaffold phase" — not "`scaffold.md` exists."
- **Predictable headings.** An agent re-reading mid-task scans by heading. `## Step 3 — Branch` is better than `## What to do based on classification`.

## Frontmatter

Skill files start with frontmatter:

```yaml
---
name: <skill-name>
description: <when to invoke this skill, conditions for activation>
---
```

The `description` is what the harness uses to decide when to invoke the skill. Be precise about activation conditions, not flowery about purpose. "Use when working in a repo that contains `agent-policy.yaml`" is better than "Helps agents govern code changes."

## Budget

Every skill file has a declared token ceiling in `tests/budget/budget.yaml`. The CI check fails the build if any file exceeds its ceiling.

Treat the ceiling as a ceiling, not a target. **Smallest version that does the job; expand only on demonstrated need from smoke tests.**

If a file is well under its ceiling, that's good. Don't pad to "use the budget."

## When the deletion test is hard

Some content sits on the line. Two heuristics:

1. **Does cutting it change what the agent does in any concrete situation?** If you can describe a situation where the agent would behave differently without the sentence, keep it. If you can't, cut it.
2. **Is it a runtime decision rule, or is it commentary about the rule?** Keep the rule; cut the commentary. "Refuse boundary shortcuts" stays; "without this refusal the system collapses" goes.

## Audit checklist

Before merging a skill file, walk through it section by section and ask, for each section:

- Does this change agent behavior?
- Is it the smallest expression of that behavior?
- Is it written imperatively?
- Does it duplicate content already in another loaded file?
- Does the deletion test pass for every paragraph?

Then run `tests/budget/check-budget.sh` and confirm the file is under its ceiling.

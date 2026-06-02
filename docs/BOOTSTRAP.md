# Bootstrap mode

Bootstrap mode is what the agent does when a developer asks:

> *Use agent-redline to set up governance for this repo.*

It is a one-time setup conversation, not an automated install.

## Inputs

- The repo as it exists (any branch / commit)
- The developer's intent (what risks they care about, what teams own what, what CI they have)
- The matching language extension from `extensions/` (e.g., `spring-archunit`). For stacks without a built-in extension, the developer points the agent at a third-party extension or the agent works without one.

## Outputs

### Directly committed

- `agent-policy.yaml`
- `AGENTS.md` — agent-facing summary, referenced from any existing `CLAUDE.md` / `GEMINI.md`
- A boundary-rule backend setup for the ecosystem (e.g., an ArchUnit test class for JVM/Spring; a `[tool.importlinter]` block in `pyproject.toml` for Python; a dependency-cruiser config for Node; Semgrep rules as a generic fallback)
- `scripts/agent-redline-check.sh` — local pre-push check (vendored from the skill's `core/templates/pre-push-check.sh`)
- `scripts/agent-redline-report.py` — vendored reporter copy
- For Python repos: `scripts/run-import-linter.py` — vendored adapter
- `.github/pull_request_template.md` — additions or new file (PR-driven flow only)
- `docs/agent/*.md` — copied skill docs (`blue-zone-work`, `red-zone-change`, `boundary-violation`, plus any checkpoint-specific ones)

### Proposed, NOT committed

- `docs/agent-redline-ci-proposal.md` — workflow YAML, branch-protection changes, CODEOWNERS additions, decisions the human must make

## Phases

### Phase 1 — Inspect and pick an extension

The agent reads:

- Build files (`build.gradle`, `pom.xml`, `package.json`, `pyproject.toml`, `setup.py`, `setup.cfg`, `go.mod`, `Cargo.toml`, etc.)
- Source layout (top-level package structure; for Python: src-layout vs flat vs multi-package)
- Existing `CLAUDE.md` / `AGENTS.md` / `GEMINI.md`
- Existing `.github/workflows/`, `.gitlab-ci.yml`, etc. — including the trigger (`pull_request:` vs `push:`)
- Recent flow signal — `gh pr list --state merged --limit 30` count vs `git log` count over the same window — to gauge whether the dominant flow is PR-based or push-based
- Existing CODEOWNERS
- Existing OpenAPI specs, GraphQL schemas, proto files
- Existing DB migration directories (and schema-as-code files, e.g. Python's `storage/sqlite_schema.py`)
- Existing security/auth code locations

Based on what it finds, the agent **proposes a language extension** for the developer to confirm:

- For Spring Boot + Gradle/Maven, the agent suggests `spring-archunit`.
- For Python, the agent suggests `python` and triages the shape (layered service / library / zone-only fallback) and layout (src-layout / flat / multi-package).
- For other stacks, the agent surfaces the recommended backends listed in [EXTENSIONS.md](EXTENSIONS.md) and asks the developer to pick a third-party extension or proceed without one.

If no extension is selected (or available), the agent says so and offers to continue with zone-only governance — bootstrap still produces a useful policy, just without the boundary-rule backend wired in.

The agent also **picks a CI flow mode** based on Phase 1 inspection:

| Signal | Flow mode |
|---|---|
| Existing workflow on `pull_request:`, multiple recent merged PRs, multiple committers | PR-driven |
| Existing workflow on `push:`, ~zero merged PRs, dominant flow is `git push` to main | push-driven |
| Solo developer, no PRs (or PRs only for meta-changes), trunk-based | push-driven |
| Mixed | dominant signal wins; ask the developer |

PR-driven proposes a workflow on `pull_request:` with a sticky comment surface; CI fails only on exit 2. Push-driven proposes `on: push:` with the verdict in a CI artifact; CI fails on exit 1 OR 2. Both reference the matching extension scaffold for the YAML.

The agent does **not** modify anything yet. It produces a written summary of what it found, the proposed extension, and the proposed flow mode.

### Phase 2 — Extension-driven proposal

The agent loads the matching language extension's `profile.md` and proposes:

- A starting set of red zones, blue zones, and watch-list entries (gray is the residual bucket — paths no other entry matches)
- A starting set of boundary rules
- API contract location
- Persistence path
- Security path
- Initial PR-size thresholds
- The boundary-rule backend the extension prescribes (e.g., ArchUnit for `spring-archunit`)

This is presented as a draft `agent-policy.yaml` with explanatory comments. The developer reviews it.

### Phase 3 — Adapt

Phase 3 has three sub-steps, in order.

**3a. Zone-utility check.** For each red entry in the draft, the agent checks that it actually fires on a *minority* of the team's PRs. A red zone that triggers on routine work is alert fatigue, not protection. The agent walks the developer through three recent feature PRs and downgrades any red entry that fires on most of them to `watch` (still surfaced) or `blue` (autonomous). Where possible, paths are split (interfaces vs. implementations, prod-config vs. all config). The agent also prefers semantic triggers (the `api:` OpenAPI diff for API changes; schema-detect for migrations) over path-touch when both are available — path-based red zones over-fire on bug-fixes and refactors.

**3b. History-based calibration (when applicable).** The tuner takes a list of changesets and reports per-zone-entry firing rates. The unit of changeset depends on the flow mode:

- **PR-driven flow:** count merged PRs via `gh pr list --state merged --limit 1 --json number`. If 30+, run with `--repo <gh-slug> --limit 30`.
- **Push-driven flow:** count commits via `git rev-list --count main`. If 30+, run with `--push-history --branch main --limit 30`. Each commit on the long-lived branch is one changeset; squash-merged PRs naturally collapse to one commit each, so push-mode and PR-mode samples are roughly comparable on volume.

If 30+ changesets are available, the agent asks for permission and runs:

```
python <skill-root>/scripts/agent-redline-tune.py --policy <draft> \
  [--repo <gh-slug> --limit 30 | --push-history --branch main --limit 30] \
  --suggest
```

The tuner emits a JSON list of red entries firing above a 30%-of-changesets threshold. The agent presents each suggestion (path, firing rate, current zone, proposed action) for the developer to approve, override, or split. Approved demotions are applied to the draft; overrides get a one-line policy comment recording the reason. The agent **never auto-applies** suggestions and **never runs the tuner without explicit approval**.

When the repo has fewer than 30 changesets, 3b is skipped with a comment in the policy noting calibration will complete in Window 1 of shadow mode (see [CI_INTEGRATION.md](CI_INTEGRATION.md)).

**3c. Repo-specific questions.** The agent asks targeted questions that the data can't answer:

- "Does this repo have third-party adapter contracts that should be red?"
- "Is there customer-specific code that must not leak into core?"
- "Is the persistence multi-tenant? Are there special migration considerations?"
- "Are there generated artifacts that should be excluded from classification?"
- "Who owns architecture review? API review? Persistence review?"

Answers feed into the policy. The developer signs off on the final draft before Phase 4 writes anything.

### Phase 4 — Write

Once the developer signs off on the policy, the agent writes the directly-committed artifacts. Each file is small, well-commented, and matches the policy.

The agent reads the extension's `scaffold.md` to know how to generate the boundary-backend setup. Boundary rules in the policy map one-to-one to backend rules (e.g., one ArchUnit test method per `boundaries[]` entry on JVM). The scaffolding is wired into the existing build/test task.

`scripts/agent-redline-check.sh` is written and made executable. It runs the same reporter the CI runs, on the local diff.

`AGENTS.md` is written. If `CLAUDE.md` / `GEMINI.md` already exist, they get a clearly-marked reference section pointing to `AGENTS.md` and `agent-policy.yaml`.

The PR template is merged with any existing template. agent-redline does not overwrite an existing template; it adds its sections.

### Phase 5 — Propose CI

The agent writes `docs/agent-redline-ci-proposal.md`. This file contains:

1. The proposed GH Actions workflow (or equivalent), ready to copy — shaped for the flow mode picked in Phase 1 (PR-driven or push-driven; see [CI_INTEGRATION.md](CI_INTEGRATION.md))
2. Required-status-check names for branch protection (PR-driven only)
3. CODEOWNERS additions, mapped to teams as best the agent can guess (PR-driven only; push-driven solo repos skip)
4. Recommended initial mode: **shadow**
5. Timeline: 4 weeks or 30 changesets of shadow before flipping any check to binding
6. The list of decisions the human must make:
   - Who owns each checkpoint? (PR-driven only)
   - Which checks should eventually become binding?
   - Are there platform-team policies that override anything here?

The agent does **not** write `.github/workflows/agent-redline.yml`. It tells the developer:

> CI integration is a structural change to your team's workflow — it affects every developer and may need platform-admin approval. I've written everything I'm allowed to write. Open `docs/agent-redline-ci-proposal.md`, review it with whoever owns CI, and apply when you're ready.

### Phase 6 — Self-summary

The agent produces a final summary:

- What was committed
- What was proposed but not committed
- What still needs human action
- How to verify the local check works (`./scripts/agent-redline-check.sh`)
- How to run shadow mode
- Where to find the docs

## Invariants

The bootstrap skill must never:

- Auto-commit CI workflow files
- Auto-modify branch protection
- Auto-modify CODEOWNERS
- Overwrite an existing `agent-policy.yaml` without explicit confirmation
- Generate a policy that doesn't protect its own boundary-backend definition files
- Skip the inspection phase
- Skip presenting the policy for review before writing

The bootstrap skill should:

- Be conversational, not silent
- Surface uncertainty (what it couldn't classify, what it had to guess)
- Make every decision reversible
- Treat the developer as the authority on the repo's actual conventions

## Shape of the work

Bootstrap is conversational and iterative. How long it takes depends on:

- How clear the repo's existing structure is (clean hexagonal layouts go faster than mixed/legacy ones)
- How many domain-specific concerns the team wants to encode (third-party adapters, customer-specific code, multi-tenant persistence, etc.)
- Whether the team already has architecture rules (existing boundary-backend setup like ArchUnit tests, CODEOWNERS, etc.) that bootstrap can compose with

Repos with no recognizable structure may need explicit modeling work before agent-redline can usefully classify them. The skill should say so honestly rather than invent zones.

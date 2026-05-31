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
- A boundary-rule backend setup for the ecosystem (e.g., an ArchUnit test class for JVM/Spring; a dependency-cruiser config for Node; an import-linter config for Python; Semgrep rules as a generic fallback)
- `scripts/agent-redline-check.sh` — local pre-push check
- `.github/pull_request_template.md` — additions or new file
- `docs/agent/*.md` — copied skill docs (`blue-zone-work`, `red-zone-change`, `boundary-violation`, plus any checkpoint-specific ones)

### Proposed, NOT committed

- `docs/agent-redline-ci-proposal.md` — workflow YAML, branch-protection changes, CODEOWNERS additions, decisions the human must make

## Phases

### Phase 1 — Inspect and pick an extension

The agent reads:

- Build files (`build.gradle`, `pom.xml`, `package.json`, `pyproject.toml`, `go.mod`, `Cargo.toml`, etc.)
- Source layout (top-level package structure)
- Existing `CLAUDE.md` / `AGENTS.md` / `GEMINI.md`
- Existing `.github/workflows/`, `.gitlab-ci.yml`, etc.
- Existing CODEOWNERS
- Existing OpenAPI specs, GraphQL schemas, proto files
- Existing DB migration directories
- Existing security/auth code locations

Based on what it finds, the agent **proposes a language extension** for the developer to confirm:

- For Spring Boot + Gradle/Maven, the agent suggests `spring-archunit` (the reference extension shipped with agent-redline).
- For other stacks, the agent surfaces the recommended backends listed in [EXTENSIONS.md](EXTENSIONS.md) and asks the developer to pick a third-party extension or proceed without one.

If no extension is selected (or available), the agent says so and offers to continue with zone-only governance — bootstrap still produces a useful policy, just without the boundary-rule backend wired in.

The agent does **not** modify anything yet. It produces a written summary of what it found and the proposed extension.

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

The agent asks targeted questions:

- "Does this repo have third-party adapter contracts that should be red?"
- "Is there customer-specific code that must not leak into core?"
- "Is the persistence multi-tenant? Are there special migration considerations?"
- "Are there generated artifacts that should be excluded from classification?"
- "Who owns architecture review? API review? Persistence review?"

Answers feed into the policy.

### Phase 4 — Write

Once the developer signs off on the policy, the agent writes the directly-committed artifacts. Each file is small, well-commented, and matches the policy.

The agent reads the extension's `scaffold.md` to know how to generate the boundary-backend setup. Boundary rules in the policy map one-to-one to backend rules (e.g., one ArchUnit test method per `boundaries[]` entry on JVM). The scaffolding is wired into the existing build/test task.

`scripts/agent-redline-check.sh` is written and made executable. It runs the same reporter the CI runs, on the local diff.

`AGENTS.md` is written. If `CLAUDE.md` / `GEMINI.md` already exist, they get a clearly-marked reference section pointing to `AGENTS.md` and `agent-policy.yaml`.

The PR template is merged with any existing template. agent-redline does not overwrite an existing template; it adds its sections.

### Phase 5 — Propose CI

The agent writes `docs/agent-redline-ci-proposal.md`. This file contains:

1. The proposed GH Actions workflow (or equivalent), ready to copy
2. Required-status-check names for branch protection
3. CODEOWNERS additions, mapped to teams as best the agent can guess
4. Recommended initial mode: **shadow**
5. Timeline: 4 weeks or 30 PRs of shadow before flipping any check to binding
6. The list of decisions the human must make:
   - Who owns each checkpoint?
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

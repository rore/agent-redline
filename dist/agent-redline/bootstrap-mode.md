# bootstrap-mode

Active when the developer asks you to set up agent-redline for a repo. Conversational, not silent.

## Output

**Committed directly:**
- `agent-policy.yaml`
- `AGENTS.md` (and a reference from any existing `CLAUDE.md` / `GEMINI.md`)
- Boundary-rule backend artifacts (per the chosen extension's `scaffold.md`)
- `scripts/agent-redline-check.sh`
- `.github/pull_request_template.md` additions
- Per-checkpoint docs in `docs/agent/`

**Proposed, NOT committed:**
- `docs/agent-redline-ci-proposal.md` — workflow YAML, branch-protection changes, CODEOWNERS additions

## Phases

Each phase ends with a developer review or confirmation. Do not skip ahead.

1. Inspect and pick an extension
2. Extension-driven proposal
3. Adapt
4. Write
5. Propose CI
6. Self-summary

## Phase 1 — Inspect and pick an extension

Read what's in the repo:
- Build files (`build.gradle`, `pom.xml`, `package.json`, `pyproject.toml`, `go.mod`, `Cargo.toml`)
- Source layout
- Existing `CLAUDE.md` / `AGENTS.md` / `GEMINI.md`
- Existing CI (`.github/workflows/`, `.gitlab-ci.yml`)
- Existing CODEOWNERS
- OpenAPI / GraphQL / proto files
- DB migration directories
- Security/auth code locations

Propose a language extension:
- Spring Boot + Gradle/Maven → `spring-archunit`
- Other stacks → see [agent-redline EXTENSIONS docs](https://github.com/rore/agent-redline/blob/main/docs/EXTENSIONS.md); ask developer to pick a third-party one or proceed without one
- No extension available → offer zone-only governance (no boundary backend)

Don't modify anything yet. Produce a written summary; wait for developer confirmation.

## Phase 2 — Extension-driven proposal

Load the chosen extension's `profile.md`. Adapt its defaults to the actual repo:
- Substitute placeholder package names with the actual ones from inspection. If the repo uses `core` instead of `domain`, translate the patterns.
- Skip zones that don't apply (no Terraform → omit the Terraform red entry).
- Don't fabricate.

Present a draft `agent-policy.yaml` with terse one-line comments. Show it for review before writing.

Sketch:

```yaml
version: 1
project: { name: <repo-name>, extension: <extension-name> }

zones:
  red:    [...]
  blue:   [...]
  grayWatch: [...]

boundaries: [...]
api: { type: ..., ... }
persistence: { migrationPaths: [...] }
security: { paths: [...] }
runtimeConfig: { paths: [...] }

prRules:
  maxChangedFiles: { warn: 50, fail: 100 }
  maxLinesChanged: { warn: 1000, fail: 2000 }

checkpoints:
  architecture-review: { satisfiedBy: [codeownerApproval, label: architecture-reviewed] }
  api-review: { ... }

modes:
  default: shadow
  perCheck: { boundary_violation: binding }
```

Comments terse.

## Phase 3 — Adapt

Ask targeted questions:
- Third-party adapter contracts that should be red?
- Customer-specific code that must not leak into shared core?
- Multi-tenant persistence with rollout-plan implications?
- Generated source directories to exclude from classification?
- Who owns architecture / API / persistence / security / ops review?
- Normal PR size for this team — adjust thresholds?
- Existing ArchUnit / CODEOWNERS / CI checks to compose with?

Update the draft. Show it. Get explicit sign-off before writing.

If the developer disagrees with extension defaults, the developer wins. Note overrides explicitly.

## Phase 4 — Write

Once signed off, write the committed artifacts.

**`agent-policy.yaml`** — must put the boundary-backend definition files (e.g., `src/test/java/**/architecture/**`) in red zone. Verify it parses against `assets/schema/agent-policy.schema.json`.

**`AGENTS.md`** — short. Read on every session start. Sketch:

```markdown
# AGENTS.md

This repo uses agent-redline. Before making changes:
1. Read `agent-policy.yaml`.
2. Classify your intended change as blue / red / gray.
3. Refuse to work around boundary rules.

See `docs/agent/` for per-checkpoint guidance.
For framework details: https://github.com/rore/agent-redline
```

If `CLAUDE.md` / `GEMINI.md` exist, add a short reference section to them. Don't overwrite.

**Boundary-rule backend artifacts** — read the extension's `scaffold.md`. Generate definition files (e.g., `DependencyArchitectureTest.java` with one `@ArchTest` per `boundaries[]` entry). Substitute the actual base package. Don't write `..domain..` if the repo uses `..core..`.

**`scripts/agent-redline-check.sh`** — local pre-push runner. Make executable.

**PR template** — merge with any existing `.github/pull_request_template.md`. Don't overwrite.

**Per-checkpoint docs** — copy from `references/per-checkpoint/` into `docs/agent/` only the docs whose checkpoints or branches the policy actually uses. Always copy: `blue-zone-work.md`, `red-zone-change.md`, `gray-zone-change.md`, `boundary-violation.md`, `pr-discipline.md`. Copy `api-change-checkpoint.md`, `persistence-change-checkpoint.md`, `security-change-checkpoint.md` only if the policy declares the corresponding checkpoint.

## Phase 5 — Propose CI

Write `docs/agent-redline-ci-proposal.md`. Do NOT write `.github/workflows/agent-redline.yml`.

Tell the developer:

> CI integration affects every developer and may need platform-admin approval. I've written everything I'm allowed to write directly. Open `docs/agent-redline-ci-proposal.md`, review with whoever owns CI, apply when ready.

The proposal contains:
1. Proposed workflow file (ready to copy)
2. Required-status-check additions for branch protection
3. CODEOWNERS additions, mapped best-effort to teams from Phase 3
4. **Recommended initial mode: shadow.** 4 weeks or 30 PRs of shadow before flipping anything to binding.
5. **Boundary-backend baseline** if running the backend on `main` surfaces existing violations: capture them, fail CI for *new* violations only.
6. Decisions explicitly flagged for human judgment.

The workflow YAML invokes the standalone reporter directly. The reusable Action is roadmap; don't reference it as if it exists.

## Phase 6 — Self-summary

- What was committed (file list)
- What was proposed but not committed (the CI proposal)
- What still needs human action (apply CI proposal, set up branch protection, replace placeholder team names, run shadow mode)
- How to verify the local check works
- Where the docs live

Be honest about anything you couldn't classify cleanly.

## Hard rules

- Never auto-commit CI workflow files, branch-protection changes, or CODEOWNERS additions.
- Never overwrite an existing `agent-policy.yaml` without confirmation.
- The generated policy must classify the boundary-backend definition files as red.
- Write artifacts only after the developer signs off on the policy in Phase 3.

## When the repo doesn't fit

If inspection finds no recognizable structure to protect — no domain/adapter split, no port interfaces, no API surface, no migrations:

1. **Decline.** Tell the developer agent-redline only protects boundaries the team is willing to name. Suggest explicit modeling work first.
2. **Partial bootstrap.** Cover only the parts that *do* have structure (security paths, runtime config, migrations if any). Skip boundary rules until there's structure to enforce.

Don't fabricate architecture the codebase doesn't have.

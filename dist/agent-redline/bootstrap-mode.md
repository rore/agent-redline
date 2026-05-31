# bootstrap-mode

Active when the developer asks you to set up agent-redline for a repo. Conversational, not silent.

## Output

**Committed directly:**
- `agent-policy.yaml`
- Reference section appended to the existing agent-instruction file (`AGENTS.md`, `CLAUDE.md`, `GEMINI.md`, `copilot-instructions.md`, or a fresh `AGENTS.md` if none exists)
- Boundary-rule backend artifacts — *only if no existing setup is found*; otherwise the policy's `boundaries:` mirror the existing rules and the existing test stays authoritative
- `scripts/agent-redline-check.sh` — standalone if no pre-push hook exists; otherwise instructions for the developer to chain
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
- Existing agent-instruction file: `AGENTS.md`, `CLAUDE.md`, `GEMINI.md`, `copilot-instructions.md`, or any `*-instructions.md` at repo root
- Existing CI (`.github/workflows/`, `.gitlab-ci.yml`)
- Existing CODEOWNERS
- Existing **boundary-rule backend setup** — for JVM/Spring, look for ArchUnit test classes (search `src/test/**` for files importing `com.tngtech.archunit`). Note the test class name, package, and existing rules. Treat these as authoritative.
- Existing `pre-push` hook (`.git/hooks/pre-push`) or pre-push script (`scripts/pre-push*`)
- OpenAPI / GraphQL / proto files; SpringDoc plugin in the build
- DB migration directories
- Security/auth code locations

Propose a language extension:
- Spring Boot + Gradle/Maven → `spring-archunit`
- Other stacks → see [agent-redline EXTENSIONS docs](https://github.com/rore/agent-redline/blob/main/docs/EXTENSIONS.md); ask developer to pick a third-party one or proceed without one
- No extension available → offer zone-only governance (no boundary backend)

Don't modify anything yet. Produce a written summary; wait for developer confirmation. The summary must include:
- Whether an existing arch test was found, and if so its rules — Phase 4 composes with it, doesn't replace it
- Which agent-instruction file exists (if any) — Phase 4 adds a reference section there, not a fresh `AGENTS.md`
- Whether an existing pre-push hook exists — Phase 4 chains, doesn't replace

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

**`agent-policy.yaml`** — must classify the boundary-backend definition files as red (e.g., `src/test/java/**/architecture/**`, or wherever the existing arch test lives in this repo). Verify it parses against `assets/schema/agent-policy.schema.json`.

**Agent-instruction file** — if `AGENTS.md`, `CLAUDE.md`, `GEMINI.md`, `copilot-instructions.md`, or a similar file already exists at the repo root, append a clearly-marked agent-redline reference section to it. Do NOT create a new `AGENTS.md` alongside an existing instruction file. Only create `AGENTS.md` from scratch if none of those files exist.

The reference section is short:

```markdown
## agent-redline

This repo uses agent-redline. Before making changes:
1. Read `agent-policy.yaml`.
2. Classify your intended change as blue / red / gray.
3. Refuse to work around boundary rules.

See `docs/agent/` for per-checkpoint guidance.
Framework: https://github.com/rore/agent-redline
```

**Boundary-rule backend artifacts** — read the extension's `scaffold.md`. Two cases:

- **Existing arch test found in Phase 1:** do NOT generate a new test. Translate its rules into `boundaries:` entries in the policy (one per rule) and tell the developer the existing test is what enforces them. The policy's `boundaries:` section is metadata that the reporter surfaces; the existing test does the actual checking.
- **No existing arch test:** generate the file per `scaffold.md`. Substitute the actual base package. Don't write `..domain..` if the repo uses `..core..`.

**`scripts/agent-redline-check.sh`** — local pre-push runner. Make executable.

If an existing pre-push hook or script was found in Phase 1, do NOT replace it. Tell the developer how to chain: have the existing hook call `./scripts/agent-redline-check.sh` after its existing steps, or vice versa. Show the one-line diff they need.

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
- Never overwrite an existing arch test (or other boundary-backend definition). Compose via `boundaries:` instead.
- Never overwrite an existing agent-instruction file. Append a reference section.
- Never overwrite an existing pre-push hook. Tell the developer how to chain.
- The generated policy must classify the boundary-backend definition files as red.
- Write artifacts only after the developer signs off on the policy in Phase 3.

## When the repo doesn't fit

If inspection finds no recognizable structure to protect — no domain/adapter split, no port interfaces, no API surface, no migrations:

1. **Decline.** Tell the developer agent-redline only protects boundaries the team is willing to name. Suggest explicit modeling work first.
2. **Partial bootstrap.** Cover only the parts that *do* have structure (security paths, runtime config, migrations if any). Skip boundary rules until there's structure to enforce.

Don't fabricate architecture the codebase doesn't have.

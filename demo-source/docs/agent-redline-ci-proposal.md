# agent-redline CI proposal — agent-redline-demo

> **Note for readers.** Bootstrap normally writes this file as a *proposal*, leaving the actual workflow at `.github/workflows/agent-redline.yml` for the human to apply. **This demo deliberately ships the workflow in `main`** so the three demo PR branches (`demo/blue-only-pr`, `demo/red-with-checkpoint-pr`, `demo/boundary-violation-pr`) can demonstrate CI verdicts without manual setup. The content below documents what bootstrap would have proposed; the live workflow already implements it.

## 1. Workflow

The workflow at `.github/workflows/agent-redline.yml` runs on every PR and push:

1. Run the architecture tests (`./gradlew test --tests '*ArchitectureTest'`).
2. Run the agent-redline reporter against the diff.
3. Post the verdict comment on the PR.
4. Set the appropriate exit code.

Because this is a teaching demo, the workflow is shipped as-is in `main` so contributors can see green/red/boundary CI states without setting up anything themselves.

## 2. Branch protection

The required status checks for `main` would be:

- `agent-redline / boundary tests`
- `agent-redline / agent-redline report`

In a real-world adoption, you would not flip the second to required until you'd seen at least one shadow-mode PR produce useful output.

## 3. CODEOWNERS

`.github/CODEOWNERS` ships with `@rore` as the placeholder owner for all paths. A real adoption would split by path:

```
# Architecture-review surface
src/main/java/**/application/**/port/**       @architecture-team
src/test/java/**/architecture/**              @architecture-team

# API-review surface
src/main/java/**/*Controller.java             @api-team

# Persistence-review surface
src/main/resources/db/migration/**            @persistence-team
```

## 4. Initial mode — shadow

`modes.default: shadow`, `modes.perCheck.boundary_violation: binding`. The boundary check is binding because the underlying ArchUnit test enforces the rules at build time; flipping the policy mirror to binding only aligns the policy with reality.

## 5. Boundary-backend baseline

The demo's `DependencyArchitectureTest` is green on `main`. No baseline file is needed.

## 6. Decisions still owned by humans (in real adoptions)

- Real CODEOWNERS teams (this demo uses `@rore` as placeholder).
- Branch-protection ruleset (admin-side click).
- Shadow → binding transition timing (drive by signal, not a fixed date).
- Whether to add a real OpenAPI surface (`api.type` is currently `none`; switch to `openapi-spec-file` or `openapi-from-controllers` if API contract diffs are wanted).

# agent-policy.yaml schema reference

This document is the normative reference for `agent-policy.yaml`. The bootstrap skill writes a policy that conforms; the reporter reads a policy that conforms.

The schema describes exactly what the reporter implements. Fields are not "reserved for later" — when the reporter learns to do something new, the schema grows with it. See [`SPEC.md` §15](SPEC.md) for what's on the roadmap.

```yaml
# agent-policy.yaml — schema v1

version: 1                            # required; integer; current version is 1

project:                              # required
  name: <string>                      # required
  extension: <string>                 # optional; names the language extension, e.g. "jvm-archunit"

zones:                                # required; at least one of red or blue must be non-empty
  red:                                # paths whose changes need human attention
    - path: <glob>                    # required
      reason: <string>                # required; surfaced in reporter output
      checkpoint: <checkpoint-id>     # optional; the checkpoint a red-zone change must satisfy
  blue:                               # paths where agent autonomy is fine
    - path: <glob>
      reason: <string>
  watch:                              # additive tag — paths surfaced in the PR comment
    - path: <glob>                    # regardless of red/blue/gray classification.
      reason: <string>                # No checkpoint, no merge gate, just visibility.
  # Files not matched by red/blue/watch are gray (the residual bucket).
  # Red and blue are exclusive zone classifications.
  # Watch composes additively with all three.

boundaries:                           # optional; deterministic dependency rules.
  - id: <kebab-case-string>           # The reporter surfaces these alongside boundary-backend
    description: <string>             # results; the language extension's backend (e.g. ArchUnit)
    from: <glob>                      # actually enforces them.
    forbidImports:
      - <glob>
    severity: error                   # error | warn   (default: error)

api:                                  # optional
  type: <api-type>                    # openapi-spec-file | openapi-from-controllers | graphql | proto | none
  specPath: <path>                    # for openapi-spec-file/graphql/proto: the committed spec
  generationCommand: <string>         # required for openapi-from-controllers: command CI runs at base+head
  diffMode: structural                # structural | full   (default: structural)
  checkpoint: api-review              # default: api-review

persistence:                          # optional
  migrationPaths:
    - <glob>
  checkpoint: persistence-review      # default: persistence-review
  notes: <string>                     # optional; surfaced to agents

security:                             # optional
  paths:
    - <glob>
  checkpoint: security-review         # default: security-review

runtimeConfig:                        # optional
  paths:
    - <glob>
  checkpoint: ops-review              # default: ops-review

prRules:                              # optional; defaults applied if absent
  maxChangedFiles:
    warn: 50
    fail: 100
  maxLinesChanged:
    warn: 1000
    fail: 2000

checkpoints:                          # required if any zone references one
  <checkpoint-id>:
    description: <string>             # optional; surfaced in PR comment
    satisfiedBy:                      # required; OR-semantics across entries
      - codeownerApproval             # a CODEOWNER for any touched red-zone path approves
      - label: <label-name>           # a named label is applied to the PR

modes:                                # optional; defaults to all shadow
  default: shadow                     # shadow | binding   (default: shadow)
  perCheck:                           # named overrides; see "Mode semantics"
    boundary_violation: binding       # almost always binding from day one
    pr_size: shadow
    report: shadow                    # whether unmet required checkpoints fail the check

excludes:                             # optional; paths excluded from all classification
  - <glob>                            # e.g. generated sources, vendored code

boundaryAdapter:                      # optional; how the boundary-rule backend's output is
                                      # delivered to the reporter. Bootstrap copies this from
                                      # the chosen extension's adapter.yaml.
  outputFormat: junit-xml             # junit-xml | json-violations | none
  outputPath: <path-or-glob>          # required when outputFormat != none. Where the backend
                                      # writes its report. The reporter reads this file when
                                      # no explicit --boundary-report flag is passed.
  violationFilter:                    # optional; only meaningful for outputFormat: junit-xml.
    matchClassName: <substring>       # Identifies architecture failures vs unrelated test
    matchTestNamePattern: <regex>     # failures when both share a JUnit XML.

suppressions:                         # optional; absence turns suppression detection OFF.
                                      # Defaults come from the vendored .agent-redline/suppressions.yaml
                                      # (copied from the chosen extension at bootstrap). The
                                      # policy declares overrides-only.
  useExtensionDefaults: true          # default: true. When true, load .agent-redline/suppressions.yaml
                                      # and apply the add/remove deltas below. When false, only the
                                      # add: lists are used (the policy supplies the entire marker set).
  add:                                # markers to add on top of vendored defaults
    inlineComments:
      - <substring>                   # e.g. "# pragma: no-cover"
    annotations:
      - <token>                       # e.g. "MyTeamSuppressWarnings"
    configEdits:
      - file: <glob>                  # which file's keys count as config-edit suppressions
        keys:
          - <key>                     # e.g. "my_custom_ignore_list"
  remove:                             # markers to drop from vendored defaults
    inlineComments:
      - <substring>
    annotations:
      - <token>
    configEdits:
      - file: <glob>
        keys:
          - <key>
  exemptPaths:                        # globs where suppressions are accepted without routing
    - <glob>                          # e.g. "**/tests/**", "**/test/**"
```

## Defaults

If a section is absent, these defaults apply:

| Section | Default |
|---|---|
| `prRules.maxChangedFiles` | `{ warn: 50, fail: 100 }` |
| `prRules.maxLinesChanged` | `{ warn: 1000, fail: 2000 }` |
| `modes.default` | `shadow` |
| `modes.perCheck.boundary_violation` | `binding` |
| `modes.perCheck.suppression` | `binding` (hardcoded — symmetric with `boundary_violation`; see Mode semantics below) |
| `suppressions` | absent → suppression detection OFF (compatibility) |
| `suppressions.useExtensionDefaults` | `true` (within the block) |

Files not matched by any zone are treated as gray.

## API contract modes

`api.type` decides how the reporter detects API changes.

| `type` | Required | Reporter behavior |
|---|---|---|
| `none` | — | No api signal. Use when the repo has no public API surface. |
| `openapi-spec-file` | `specPath` | Path-glob detection. If a file matching `specPath` is in the diff, api change is flagged. The reporter does not parse the spec — the file changing is the signal. |
| `graphql` | `specPath` | Same as `openapi-spec-file` for the schema file. |
| `proto` | `specPath` | Same; for `.proto` files. |
| `openapi-from-controllers` | `generationCommand` | The CI workflow runs `generationCommand` at base SHA and head SHA (typically via `git worktree`), then passes both specs to the reporter via `--api-spec-base` / `--api-spec-head`. The reporter computes a structural diff (paths added / removed, methods added / removed / modified). The local pre-push check does not run the generation; it falls back to red-zone path classification. See `extensions/jvm-archunit/scaffold.md` §6 for the worktree pattern. |

The structural diff is descriptive, not classificatory: it reports what surface changed, not whether the change is breaking. Reviewers (human or agent) judge severity.

## Validation rules

A policy is invalid if:

1. `version` is missing or not `1`.
2. `project.name` is missing.
3. `zones.red` and `zones.blue` are both empty.
4. A `checkpoint:` reference points to an undefined checkpoint.
5. A `boundaries[].forbidImports` is empty.
6. A `boundaries[].id` is duplicated.
7. The policy does not protect its own architecture-test directory (e.g., `src/test/**/architecture/**`) as a red zone.
8. A glob is malformed.

The bootstrap skill must produce a valid policy. The reporter must refuse to run on an invalid policy with a clear error.

## Glob syntax

Globs use standard shell-style patterns:

| Pattern | Matches |
|---|---|
| `*` | Any single path component (no `/`) |
| `**` | Zero or more path components |
| `?` | A single character (no `/`) |
| `[abc]` | One of `a`, `b`, or `c` |
| `[!abc]` / `[^abc]` | Any character except `a`, `b`, `c` |

Brace expansion (`{a,b}`) is not supported. Use multiple zone entries instead.

Globs are matched against repo-relative paths.

## Mode semantics

`modes.default` (`shadow` or `binding`) is the fallback for all rule modes. `modes.perCheck` overrides it per rule name.

The reporter consults the mode for these rules:

| Rule name | Used to decide |
|---|---|
| `boundary_violation` | Whether reported boundary violations should fail the check (vs. surface as warnings) |
| `report` | Whether unmet required checkpoints should fail the check |
| `pr_size` | Whether exceeding `prRules.maxChangedFiles.fail` / `maxLinesChanged.fail` should fail the check |
| `suppression` | Whether suppression markers added on guarded surfaces should fail the check. Hardcoded default: `binding`. `modes.default: shadow` does NOT downgrade `suppression`; only an explicit `modes.perCheck.suppression: shadow` flips it. |

Other signals (`api_changed`, `schema_changed`, `security_changed`, `config_changed`, gray-zone changes) always surface in the PR comment regardless of mode. They influence the `MIXED` / `RED` / `GRAY` verdict but do not, on their own, set the binding-fail exit code.

`shadow` is the safe default while a repo is rolling out agent-redline; flip individual rules to `binding` once the team is ready to enforce them.

## `satisfiedBy` semantics

`satisfiedBy` is an OR list. Any one of the entries satisfies the checkpoint.

| Entry | Satisfied when |
|---|---|
| `codeownerApproval` | A CODEOWNER for any of the touched red-zone paths approves the PR |
| `label: <name>` | The named label is applied to the PR |

## `boundaryAdapter` semantics

The `boundaryAdapter` block tells the reporter how the boundary-rule backend's output is delivered. Bootstrap copies the chosen extension's `adapter.yaml` into the policy.

| `outputFormat` | Backend used by | What the reporter reads |
|---|---|---|
| `junit-xml` | ArchUnit (Spring extension), other JUnit-XML producers | `<testsuite>/<testcase>/<failure>` shapes from the file at `outputPath`. The optional `violationFilter` distinguishes architecture failures from unrelated test failures. |
| `json-violations` | import-linter via the python extension's adapter script; any backend whose adapter emits the schema | A JSON document matching `core/schema/boundary-violations.schema.json`. Each entry yields a `BoundaryViolation` with `source` set from the document's top-level `source` field. |
| `none` | Repos that opt out of boundary enforcement (data pipelines, mixed monorepos) | Nothing; the reporter skips the boundary leg entirely. |

When `boundaryAdapter` is present and the reporter CLI is not given an explicit `--boundary-report` flag, the reporter reads the file at `outputPath` and dispatches on `outputFormat`. CI snippets that pass `--boundary-report` and `--boundary-format` directly still work; the policy-level dispatch is a fallback for non-CI invocations (e.g. local pre-push).

The legacy `--archunit-xml <path>` flag is still accepted (it implies `outputFormat: junit-xml`) and is preserved for back-compat with v0.1 CI snippets.

## `suppressions` block

The `suppressions` block declares that the policy participates in suppression detection. The reporter scans the unified diff for added-line suppression markers and routes additions on guarded surfaces (any path that isn't on `exemptPaths`) to `architecture-review`. The full algorithm and rationale live in [`docs/superpowers/specs/2026-06-10-suppression-detection-design.md`](superpowers/specs/2026-06-10-suppression-detection-design.md); this section documents the schema surface.

### Vendored marker list

The defaults come from a vendored file at the fixed path `.agent-redline/suppressions.yaml`. Bootstrap copies it from the chosen language extension's `extensions/<name>/suppressions.yaml`; the reporter reads only the in-repo copy at runtime (no extension reachback). The path is fixed — there is no override.

The vendored file declares three categories of marker:

| Category | Match | Example |
|---|---|---|
| `inlineComments` | substring match on added lines | `# noqa`, `# type: ignore`, `// archunit: ignore` |
| `annotations` | word-bounded token match on added lines | `@SuppressWarnings`, `@ArchIgnore` |
| `configEdits` | structural assignment match in declared config files | `ignore_imports = [...]` in `**/pyproject.toml`, `per-file-ignores` in `**/setup.cfg` |

Categories and structure are defined by `core/schema/suppressions.schema.json`.

### Fields

| Field | Default | Meaning |
|---|---|---|
| `useExtensionDefaults` | `true` | Whether to load `.agent-redline/suppressions.yaml` and apply `add` / `remove` on top. When `false`, only the `add` lists are used and the vendored file is ignored. |
| `add.inlineComments` | `[]` | Extra comment substrings on top of the vendored defaults. |
| `add.annotations` | `[]` | Extra annotation tokens. |
| `add.configEdits` | `[]` | Extra `{file, keys}` entries; `file` is a glob, `keys` are exact key names. |
| `remove.inlineComments` | `[]` | Vendored substrings to drop. |
| `remove.annotations` | `[]` | Vendored tokens to drop. |
| `remove.configEdits` | `[]` | Vendored `{file, keys}` entries to drop. Match is by `file` glob; the listed `keys` are removed from that entry. |
| `exemptPaths` | `[]` | Globs (repo-relative) where suppressions are accepted without routing. Typical value: `**/tests/**`. |

### Compatibility (§1.4)

A policy without a `suppressions:` block keeps suppression detection OFF. The reporter does not require `.agent-redline/suppressions.yaml` to exist in this case. This is non-negotiable: existing v0.2 policies must keep working unchanged.

The missing-vendored-file error fires only when **all three** conditions hold:

1. The policy declares a `suppressions:` block, AND
2. `suppressions.useExtensionDefaults` is `true` (default within the block), AND
3. `.agent-redline/suppressions.yaml` is absent from the repo.

When `useExtensionDefaults: false`, the vendored file is not read and the policy's `add` lists are the entire marker set.

### Mode semantics

`modes.perCheck.suppression` is a `shadow | binding` enum. The hardcoded default is `binding` (symmetric with `boundary_violation`; see the design spec §2.4 at [`docs/superpowers/specs/2026-06-10-suppression-detection-design.md`](superpowers/specs/2026-06-10-suppression-detection-design.md)). `modes.default: shadow` does NOT downgrade `suppression`; only an explicit `modes.perCheck.suppression: shadow` flips it to advisory. This mirrors how `boundary_violation` resists the default downgrade.

### Example: opt in with the vendored defaults plus a project-specific exemption

```yaml
suppressions:
  exemptPaths:
    - "**/tests/**"
    - "**/integration-tests/**"
```

### Example: opt in, drop one vendored marker, add a project-local one

```yaml
suppressions:
  add:
    annotations:
      - "MyTeamSuppressWarnings"
  remove:
    inlineComments:
      - "# pragma: no-cover"
  exemptPaths:
    - "**/tests/**"
```

### Example: ignore vendored defaults, supply the entire marker set in the policy

```yaml
suppressions:
  useExtensionDefaults: false
  add:
    inlineComments:
      - "# noqa"
    annotations:
      - "@SuppressWarnings"
  exemptPaths:
    - "**/tests/**"
```

## Example: minimal valid policy

```yaml
version: 1

project:
  name: my-service

zones:
  red:
    - path: src/main/java/**/domain/**
      reason: domain model
      checkpoint: architecture-review
    - path: src/test/java/**/architecture/**
      reason: architecture test definitions
      checkpoint: architecture-review
  blue:
    - path: src/test/**
      reason: tests
    - path: docs/**
      reason: documentation

checkpoints:
  architecture-review:
    satisfiedBy:
      - codeownerApproval
      - label: architecture-reviewed
```

## Example: full Spring service policy

See `core/templates/agent-policy.yaml.template` for a fully-populated example.

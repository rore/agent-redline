# agent-policy.yaml schema reference

This document is the normative reference for `agent-policy.yaml`. The bootstrap skill writes a policy that conforms; the reporter reads a policy that conforms.

> **Reporter v0.1 coverage.** The schema below is the v1 contract. The first reporter release (v0.1) does not yet act on every field. Fields the v0.1 reporter supports:
>
> - `version`, `project`, `defaults`, `excludes`
> - `zones.red`, `zones.blue`, `zones.grayWatch` (path-based classification)
> - `boundaryBackend` (the reporter uses this to know which backend's output to read)
> - `boundaries` metadata (the reporter surfaces configured rules and reads boundary-backend results; the boundary-rule backend is what enforces them)
> - `persistence.migrationPaths` (path-based "schema_changed" signal)
> - `security.paths` (path-based "security_changed" signal)
> - `runtimeConfig.paths` (path-based "config_changed" signal)
> - `prRules` (size limits, verbose-description detection)
> - `checkpoints` (definitions; satisfaction is checked by reading PR labels and CODEOWNER approvals)
> - `modes` (shadow/binding per check)
> - `changeRules` (the action mapping for each `when:` condition)
>
> Fields the v0.1 reporter accepts but does *not* fully implement:
>
> - `api.type: openapi-from-controllers` — OpenAPI generation and structural diff. v0.1 supports `api.type: openapi-spec-file` (path-based diff of a committed spec) and `api.type: none`. Generation-from-controllers is on the roadmap.
>
> Policies should be written against the full schema regardless. Unsupported fields are accepted (not rejected); the reporter just doesn't act on them yet.

```yaml
# agent-policy.yaml — schema v1

version: 1                            # required; integer; current version is 1

project:                              # required
  name: <string>                      # required
  extension: <string>                 # optional; names the language extension, e.g. "spring-archunit"

defaults:                             # optional; sensible defaults applied if absent
  unclassifiedZone: gray              # gray | red | blue   (default: gray)
  grayMode: cautious                  # cautious | warn | allow   (default: cautious)

zones:                                # required
  red:                                # list of paths classified as red
    - path: <glob>                    # required
      reason: <string>                # required; surfaced in reporter output
      checkpoint: <checkpoint-id>     # optional; defaults to "architecture-review"
  blue:                               # list of paths classified as blue
    - path: <glob>
      reason: <string>
  grayWatch:                          # paths to surface in PR even though gray
    - path: <glob>
      reason: <string>
  # gray is implicit — anything not listed in red/blue is gray

boundaryBackend:                      # optional; names the enforcement tool. Examples:
                                      #   archunit         (JVM/Spring; default for spring-archunit extension)
                                      #   dependency-cruiser  (Node)
                                      #   import-linter    (Python)
                                      #   semgrep          (generic, multi-language)
                                      # If omitted, the language extension picks a default. The reporter
                                      # uses this hint to find and read backend output.

boundaries:                           # optional; deterministic dependency rules
  - id: <kebab-case-string>           # required, unique within file
    description: <string>             # required
    from: <glob>                      # required
    forbidImports:                    # required; one or more globs
      - <glob>
    severity: error                   # error | warn   (default: error)

api:                                  # optional
  type: <api-type>                    # openapi-from-controllers | openapi-spec-file | graphql | proto | none
  generationCommand: <string>         # optional; how to regenerate the spec
  specPath: <path>                    # optional; where the committed spec lives
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
  rejectVerboseGeneratedDescriptions: true
  requireVerificationSection: true

changeRules:                          # optional; sensible defaults applied
  - when: blue_only
    action: allow
  - when: red_changed
    action: require_checkpoint
  - when: gray_changed
    action: warn
  - when: boundary_violation
    action: fail
  - when: api_changed
    action: require_checkpoint
    checkpoint: api-review
  - when: schema_changed
    action: require_checkpoint
    checkpoint: persistence-review
  - when: security_changed
    action: require_checkpoint
    checkpoint: security-review
  - when: pr_size_warn
    action: warn
  - when: pr_size_fail
    action: require_split

checkpoints:                          # required if any zone/rule references one
  <checkpoint-id>:
    description: <string>             # optional; surfaced in PR comment
    satisfiedBy:                      # required; OR-semantics across entries
      - codeownerApproval
      - label: <label-name>
      - reviewerCount: <int>          # alternative: minimum number of reviewers
      - team: <team-name>             # alternative: a specific team must approve

modes:                                # optional; defaults to all shadow
  default: shadow                     # shadow | binding   (default: shadow)
  perCheck:                           # named overrides
    archunit: binding
    classification_comment: binding
    api_diff: shadow
    pr_size: shadow
    boundary_violation: binding       # almost always binding from day one

excludes:                             # optional; paths excluded from all classification
  - <glob>                            # e.g. generated sources, vendored code
```

## Defaults

If a section is absent, these defaults apply:

| Section | Default |
|---|---|
| `defaults.unclassifiedZone` | `gray` |
| `defaults.grayMode` | `cautious` |
| `prRules.maxChangedFiles` | `{ warn: 50, fail: 100 }` |
| `prRules.maxLinesChanged` | `{ warn: 1000, fail: 2000 }` |
| `modes.default` | `shadow` |
| `modes.perCheck.boundary_violation` | `binding` |
| `modes.perCheck.archunit` | `binding` |

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
9. `api.type: openapi-from-controllers` is set but no `generationCommand` is provided.

The bootstrap skill must produce a valid policy. The reporter must refuse to run on an invalid policy with a clear error.

## Glob syntax

Globs use standard shell-style patterns:

| Pattern | Matches |
|---|---|
| `*` | Any single path component (no `/`) |
| `**` | Zero or more path components |
| `?` | A single character |
| `[abc]` | One of `a`, `b`, or `c` |
| `{a,b}` | `a` or `b` |

Globs are matched against repo-relative paths.

## `when:` conditions in changeRules

| Condition | Triggers when |
|---|---|
| `blue_only` | All changed files are in blue zones |
| `red_changed` | At least one changed file is in a red zone |
| `gray_changed` | At least one changed file is gray (and none are red) |
| `boundary_violation` | A boundary rule fails (reported by the boundary-rule backend; ArchUnit on JVM, etc.) |
| `api_changed` | API contract diff (per `api.type`) shows changes |
| `schema_changed` | A path under `persistence.migrationPaths` is touched |
| `security_changed` | A path under `security.paths` is touched |
| `pr_size_warn` | PR exceeds `prRules.maxChangedFiles.warn` or `maxLinesChanged.warn` |
| `pr_size_fail` | PR exceeds `prRules.maxChangedFiles.fail` or `maxLinesChanged.fail` |

## `action:` values

| Action | Effect |
|---|---|
| `allow` | No constraint; CI passes |
| `warn` | Posts a warning in the PR comment; does not block |
| `require_checkpoint` | Requires the named checkpoint to be satisfied; blocks merge if missing |
| `require_split` | Requires the PR to be split before merging |
| `fail` | Hard fail; CI red |

## `satisfiedBy` semantics

`satisfiedBy` is an OR list. Any one of the entries satisfies the checkpoint.

| Entry | Satisfied when |
|---|---|
| `codeownerApproval` | A CODEOWNER for any of the touched red-zone paths approves the PR |
| `label: <name>` | The named label is applied to the PR |
| `reviewerCount: <n>` | At least `n` approvals on the PR |
| `team: <name>` | A member of the named team approves |

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

See `templates/agent-policy.yaml.template` (to be added in v0.1 implementation phase) for a fully-populated example.

# Suppression detection — design spec

**Status:** draft 2026-06-10 (v4 after review). Implementation plan: TBD.

## Goal

Detect and refuse the most common shape of governance laundering: **adding a suppression marker on a guarded surface**. Today the operating-mode skill forbids this only inside the BOUNDARY_RISK branch; CI never looks at suppression markers in the diff. An agent that reaches for `# noqa: import-linter`, `@SuppressWarnings`, `@ArchIgnore`, or an extension to a backend allowlist is currently caught only by skill discipline.

This spec closes the loop on both sides:

- **Skill (P0 #4):** lift the existing suppression-refusal rule out of BOUNDARY_RISK so it applies to any guarded surface.
- **Reporter (P0 #1):** scan the diff for known markers and treat additions on guarded surfaces as a `RED` + `architecture-review`.

The two halves land together because they are one loop. Splitting them ships a half-loop intermediate state.

## Non-goals (v1)

- **Generic CI-bypass detection** — no diffing of workflow YAML for `if: false`, no env-var bypass detection (`SKIP_TESTS=1`), no `--allow <finding>` flag inference. Out of scope; finite per-extension marker lists only.
- **Pre-existing suppressions.** v1 looks at the diff base..head. Existing suppressions are baseline.
- **A new verdict label.** Suppressions on guarded surfaces escalate to the existing `RED` verdict with `architecture-review`. No new ladder position. (See §6 — considered and rejected.)
- **A new per-checkpoint skill doc.** The legitimate responses (fix the structure / escalate) are identical to the boundary-violation case; a short section in `boundary-violation.md` does it.
- **Justification-required workflow.** No "rationale comment" enforcement; the `architecture-review` checkpoint is the human-attention mechanism.
- **Reformat false-positive protection.** A diff that removes a marker and re-adds the same marker (e.g. variable rename on a line that already had `# noqa`) fires. Accepted v1 cost — see §6.

## 1. The marker model

A **suppression marker** is a syntactic construct in the source language whose effect is to silence a check, weaken a rule, or extend an allowlist. The set is finite and per-stack.

### 1.1 What counts

| Category | Examples | Detection |
|---|---|---|
| **Inline comments** | `# noqa`, `# type: ignore`, `# nosec`, `# semgrep:ignore`, `// eslint-disable`, `// noinspection` | Substring on diff-added lines |
| **Annotations** | `@SuppressWarnings`, `@SuppressFBWarnings`, `@ArchIgnore`, `@SuppressLint` | Token on diff-added lines |
| **Backend-config edits** | `import-linter` `ignore_imports`, ArchUnit baseline edits, `pyproject.toml` `[tool.ruff.lint.per-file-ignores]`, `.flake8` `per-file-ignores`, ESLint rule overrides | Key on diff-added lines in declared config files |

### 1.2 What does not count

- **Removing a suppression** — improvement, not surfaced.
- **Suppressions on paths in `policy.suppressions.exemptPaths`** — explicit team-declared exemption (the policy lists which patterns; bootstrap proposes `**/tests/**` as the most common).
- **Markers not on the active list** — extensions ship narrow lists on purpose; license headers, type-import workarounds, conditional-import markers are out by virtue of not being listed.

What *does* count, even though some of it is technically a false positive: a diff that removes a marker and adds the same marker (rename, reformat). v1 fires on that. The reasoning is in §6.

### 1.3 Where the marker list lives

Each language extension owns its marker list at `extensions/<name>/suppressions.yaml`. **Bootstrap vendors this file into the consuming repo** at `.agent-redline/suppressions.yaml` — a snapshot, not a symlink. The reporter reads from the vendored file at runtime; it does not reach back to the source extension.

This pattern matches how `adapter.yaml` works today: bootstrap copies extension data into the consuming repo, and the reporter operates on what's in the repo.

The consuming repo's `agent-policy.yaml` declares only **overrides**:

```yaml
# agent-policy.yaml — overrides only.
suppressions:
  useExtensionDefaults: true       # default; reads .agent-redline/suppressions.yaml
  add:
    inlineComments: ["# custom-marker"]
  remove:
    inlineComments: ["# pragma: no cover"]   # team has decided this is too noisy
  exemptPaths:
    - "**/tests/**"
    - "**/tests/fixtures/generated/**"
```

The reporter's resolution order:

1. Load `.agent-redline/suppressions.yaml` for stack defaults (vendored at bootstrap).
2. Load `agent-policy.yaml`'s `suppressions:` block for overrides.
3. Effective list = vendored defaults + policy `add` − policy `remove`.

The reporter looks for `.agent-redline/suppressions.yaml` at a fixed path (repo root). No CLI flag, no policy field.

### 1.4 Compatibility with existing repos

**Absent `suppressions:` block in the policy → suppression detection is OFF.** No missing-file error, no upgrade-on-merge surprise. Symmetric with every other check: if the policy doesn't declare it, the reporter doesn't enforce it.

The missing-file error fires only when:

1. The policy declares a `suppressions:` block, AND
2. `useExtensionDefaults: true` (the default within the block), AND
3. `.agent-redline/suppressions.yaml` is absent.

That sequence means "the team intentionally turned this on but the vendored file is gone" — the actual broken state, not an upgrade artifact.

Existing repos opt in via re-running bootstrap (which detects the existing policy and offers to add the suppressions block) or by hand-adding the block. New repos get the block by default in Phase 4.

The lists ship narrow on purpose — the rule is "if it's not on the list, the reporter doesn't flag it." Adopters report missing markers; lists grow.

**Built-in (core, stack-neutral):**

```yaml
suppressions:
  inlineComments:
    - "# nosec"
    - "# semgrep:ignore"
    - "# semgrep-ignore"
```

**Python (`extensions/python/suppressions.yaml`):**

```yaml
suppressions:
  inlineComments:
    - "# noqa"
    - "# type: ignore"
    - "# pylint: disable"
    - "# pylint: skip-file"
    - "# ruff: noqa"
    - "# nosec"
  configEdits:
    files: ["pyproject.toml", ".flake8", ".pylintrc", "setup.cfg", ".importlinter"]
    keys: ["ignore_imports", "per-file-ignores", "ignore-paths"]
```

**JVM (`extensions/jvm-archunit/suppressions.yaml`):**

```yaml
suppressions:
  annotations:
    - "@SuppressWarnings"
    - "@SuppressFBWarnings"
    - "@ArchIgnore"
    - "@SuppressLint"
```

## 2. Reporter changes

### 2.1 New input: the unified diff

The reporter today receives changed file paths via `--changed-files` / `--lines-per-file`. It does not see added-line content.

Add one input:

```
--diff-unified <path>     unified diff with -U0, produced by:
                          git diff --unified=0 <base> <head>
```

Three producers update:

- **PR-driven workflow** — new step writes `build/agent-redline-diff.patch` from `git diff --unified=0 ${{ base.sha }} ${{ head.sha }}` and passes to the reporter.
- **Push-driven workflow** — same, against `${{ github.event.before }}..${{ github.sha }}`.
- **Local pre-push (`scripts/agent-redline-check.sh`)** — same, against `@{u}..HEAD`.

The reporter reads added lines (`+` prefix, ignoring file headers) per file. Hunk boundaries are not used (see §2.2).

### 2.2 Detection algorithm

For each touched file:

1. If the file matches any pattern in `policy.suppressions.exemptPaths`, skip.
2. Resolve the active marker list: vendored defaults + policy `add` − policy `remove`.
3. For each added line in the file's diff:
   - Substring match against `inlineComments`.
   - Token match against `annotations`.
   - For files in `configEdits.files`, key match against `configEdits.keys` (structural — `ignore_imports = [` counts; a comment containing `ignore_imports` does not).
4. Emit one record per match: `{file, line, marker, category, zone, context}`.

That's the whole algorithm. No hunk parsing, no removed-line tracking, no equivalence by marker family. A diff that removes a `# noqa` and adds a `# noqa` produces one match — the added one — and a `RED + architecture-review` lands. The reviewer sees the comment row, looks at the diff, decides whether to apply the label. Reformat false positives are visible and cheap to clear; cleverer algorithms either still leak laundering paths (set-difference, count comparison) or grow into per-position-pairing complexity that's worse than the false-positive cost. See §6.

There is no implicit blue-zone exception. Suppressions in tests are exempted only when the policy declares the path under `exemptPaths`. Bootstrap proposes `**/tests/**` as the default exemption; the team accepts, narrows, or removes.

### 2.3 Verdict and required checkpoints

A suppression match on a non-exempt path **always** contributes `architecture-review` to the reporter's required checkpoints, independent of the headline verdict.

When the diff produces a higher verdict (BOUNDARY_VIOLATION, API_CHANGE, etc.), that wins for the comment headline and verdict label per the existing ladder; the suppression rows still appear in the comment **and the `architecture-review` checkpoint is still required**. A diff with only suppression matches (no other escalation) headlines as `RED` with the same checkpoint requirement.

This separation matters because `_required_checkpoints()` is computed independently of the headline verdict. Without explicitly feeding suppressions into it, a `BOUNDARY_VIOLATION` headline would silently drop the architecture-review requirement that the suppression should have introduced.

Mechanics: `scan_suppressions()` returns the match list. The list feeds two consumers:

- The comment renderer (the suppressions table).
- `_required_checkpoints()` — any suppression match contributes `architecture-review` to the required set, deduped against any other rule that already required it.

### 2.4 Default mode

`suppression` is hardcoded to `binding` in the reporter's `_binding()` resolution, symmetric with `boundary_violation`. `modes.default: shadow` does **not** downgrade it. Only an explicit `modes.perCheck.suppression: shadow` does.

Rationale: the failure mode is the same shape as a boundary violation (an agent quietly weakening structural enforcement), so the default mode is the same. Bootstrap writes the explicit value into the policy regardless, so the behavior is visible in the file.

### 2.5 Output additions

The JSON verdict gains:

```json
{
  "suppressions": [
    {
      "file": "src/loyalty/api/orders.py",
      "line": 42,
      "marker": "# noqa: import-linter",
      "category": "inlineComment",
      "zone": "red",
      "context": "    from loyalty.adapters.postgres import OrderRepo  # noqa: import-linter"
    }
  ]
}
```

The PR comment gains a section, suppressed when empty:

```markdown
**Suppressions added (1):**

| File | Line | Marker | Zone |
|---|---|---|---|
| `src/loyalty/api/orders.py` | 42 | `# noqa: import-linter` | red |

Suppressions on guarded surfaces require `architecture-review`.
[Why this matters](docs/agent/boundary-violation.md#suppressions)
```

When the headline verdict is something else (e.g. `BOUNDARY_VIOLATION`), the suppressions table appears below the headline with a note that `architecture-review` is required *in addition to* the headline's own checkpoint(s).

### 2.6 Schema additions

```yaml
suppressions:
  useExtensionDefaults: true     # boolean, default true
  add: { inlineComments: [...], annotations: [...], configEdits: {...} }
  remove: { inlineComments: [...], annotations: [...], configEdits: {...} }
  exemptPaths: [glob, ...]

modes:
  perCheck:
    suppression: binding         # binding | shadow
```

`modes.perCheck` enum gains `suppression`, joining the existing `boundary_violation | report | pr_size` set.

`.agent-redline/suppressions.yaml` (the vendored file) gets its own schema fixture covering `inlineComments`, `annotations`, and `configEdits.files`/`keys`.

Both schema additions are non-breaking: absent `suppressions:` block in the policy means detection OFF (§1.4), so existing v0.2 policies remain valid and unaffected.

## 3. Skill changes

### 3.1 Generalise the suppression refusal

`core/skill/operating-mode.md` Step 4 — "Do not silently modify governance" — gains a fourth bullet:

```markdown
- **Suppression markers on guarded surfaces** — adding `# noqa`, `# type: ignore`,
  `@SuppressWarnings`, `@ArchIgnore`, `ignore_imports`, `per-file-ignores`, or any
  other marker on a non-exempt path. Suppressions silence governance the same way
  arch-test edits do; the right response to a check blocking your change is to
  fix the structure or escalate, not to silence the check. The repo's policy
  lists which markers count.
```

The BOUNDARY_RISK branch keeps its specific refusal list (it's load-bearing for the boundary-rule case) and points back at the new general rule. No new file.

### 3.2 Extend `boundary-violation.md`

`core/templates/skills/boundary-violation.md` gains a short "Suppressions" section at the end. The two legitimate responses are identical to the boundary-rule case (fix the structure / escalate); the section just names the suppression-specific patterns to refuse:

- "It's just for tests" — the policy lists `exemptPaths`; if the path isn't there, this isn't tests.
- "I'll remove the noqa later" — no mechanism tracks it.
- "The linter is wrong" — file an issue against the linter, don't suppress.
- "We need this one suppression to ship" — explicit policy edit (add to `suppressions.exemptPaths` or contract `ignore_imports`), and that edit is itself red-zone.

The PR comment links to `docs/agent/boundary-violation.md#suppressions`.

### 3.3 Bootstrap mode

`core/skill/bootstrap-mode.md` Phase 4 (artifact generation) gains two steps:

1. **Vendor** the chosen extension's `suppressions.yaml` to `.agent-redline/suppressions.yaml` in the consuming repo.
2. **Write** the `suppressions:` block into the generated policy with `useExtensionDefaults: true` and `exemptPaths: ["**/tests/**"]` as the proposed default.

For repos re-running bootstrap on an existing v0.2 policy, the skill detects the absent `suppressions:` block and offers to add it (alongside the vendored file). The developer can decline; nothing forces opt-in.

## 4. Worked examples

**Python — noqa on a domain import:**

```python
# src/loyalty/domain/orders.py — RED zone
from loyalty.adapters.postgres import OrderRepository  # noqa: import-linter
```

File matches a red-zone path. Added line contains `# noqa`. Path is not in `exemptPaths`. Verdict: `RED` (already would have been from the path-touch alone). `architecture-review` required *because of the suppression*, named explicitly in the comment.

**JVM — `@SuppressWarnings` on a controller:**

```java
@SuppressWarnings("ArchUnit")
public class OrderController {
    private final OrderRepository repo;
```

Controllers are watch-tagged in default Spring policy. Added token match. Comment surfaces the marker; `architecture-review` required.

**Reformat with existing marker — fires:**

```
- foo()  # noqa: E501
+ bar()  # noqa: E501
```

Added line contains `# noqa`. Match. Verdict: `RED` with `architecture-review`. Reviewer sees the comment row, looks at the diff, sees a clean rename, applies the label. Accepted false positive — see §6.

**Config edit — `ignore_imports`:**

```toml
[[tool.importlinter.contracts]]
ignore_imports = ["loyalty.domain -> loyalty.application"]   # NEW
```

`pyproject.toml` is in `configEdits.files`. Added line key match on `ignore_imports`. Verdict: `RED` with `architecture-review`. The comment names the contract weakening, which is more actionable than "you touched a red file."

**Suppression alongside boundary violation:**

A single PR adds both a forbidden import (caught by import-linter, fires `BOUNDARY_VIOLATION`) and an unrelated `# noqa: F401` on a red-zone file. Headline verdict: `BOUNDARY_VIOLATION`. Required checkpoints: the boundary-rule checkpoint **and** `architecture-review` (from the suppression). Both must be satisfied to merge under binding mode.

**Legitimate test suppression:**

```python
# tests/conftest.py
import importlib  # noqa: E402
```

`tests/**` is in `exemptPaths`. No match. No comment row. Verdict unchanged.

## 5. Validation

- **Reporter golden fixtures** —
  - `tests/reporter/suppression-noqa-on-red/` — basic positive case.
  - `tests/reporter/suppression-archignore-on-watch/` — JVM equivalent.
  - `tests/reporter/suppression-ignore-imports/` — config-edit category.
  - `tests/reporter/suppression-on-exempt-path/` — `**/tests/**` exemption.
  - `tests/reporter/suppression-reformat-fires-known-fp/` — accepted reformat false positive (asserts that it DOES fire and produces the expected comment row).
  - `tests/reporter/suppression-and-boundary-violation/` — both signals; verdict headlines as BOUNDARY_VIOLATION but `architecture-review` is in required checkpoints.
  - `tests/reporter/policy-without-suppressions-block/` — compatibility: pre-v0.3 policy with no suppressions block; suppression detection OFF, no false-positive errors.
- **Schema fixtures** —
  - `tests/schema/valid/with-suppressions-overrides.yaml` — policy block.
  - `tests/schema/invalid/suppressions-wrong-shape.yaml` — wrong types under `add`/`remove`.
  - `tests/schema/valid/vendored-suppressions.yaml` — the `.agent-redline/suppressions.yaml` shape (separate small schema).
- **Demo policies** — `demo-source/agent-policy.yaml` and `demo-source-python/agent-policy.yaml` gain the `suppressions:` block (overrides-only, with `**/tests/**` exempted) **and** a vendored `.agent-redline/suppressions.yaml` alongside the policy.
- **Demo PRs** — both demo repos gain `demo/suppression-change-pr` (new PR adds a marker on a red-zone path; verdict shows the suppression comment row; `architecture-reviewed` label satisfies the checkpoint).
- **Skill simulation** — C-series adds a task: "make this import-linter rule stop firing." Correctly-configured agent refuses the suppression and either fixes the structure or proposes an explicit `ignore_imports` edit (itself red-zone). Without this rule, the agent reaches for `# noqa`.

The `tests/bootstrap-detect/` harness does **not** assert on generated policy contents — it validates shape detection only. Generated-policy contracts live in the demo-source policies and schema fixtures.

### 5.1 Token-budget impact

- `operating-mode.md` — +60 tokens (one bullet, one cross-reference). Within ceiling.
- `boundary-violation.md` — +120 tokens (Suppressions section). Within ceiling.
- `agent-policy.yaml` — +~10 tokens for the overrides-only block (most repos accept defaults).
- `.agent-redline/suppressions.yaml` — vendored file, not on the operating-mode load path.
- Reporter — no skill-load cost.

No ceiling raises.

## 6. Alternatives considered

**A new `SUPPRESSION` top-level verdict.** Rejected. The routing outcome is the same as `RED + architecture-review`, and a new ladder slot adds vocabulary surface without new behavior. The PR comment names the suppression in its own table row regardless of verdict label.

**Detect every possible bypass mechanism.** Rejected as v1 scope. Finite per-extension marker lists only. Patterns outside the list become roadmap when adopters report them.

**Inline the full marker list into every policy.** Rejected. Bloats the operating-mode load path and duplicates information canonical to the extension. Overrides-only policy + vendored defaults file is the chosen contract.

**Reporter loads the extension directly at runtime.** Rejected (this was a v2 mistake). The reporter runs in the consuming repo and doesn't reach back to the source extension. Vendoring at bootstrap (`.agent-redline/suppressions.yaml`) makes the dependency explicit and inspectable.

**A new per-checkpoint skill doc.** Rejected. The legitimate responses are identical to `boundary-violation.md`; a new file costs tokens for no new behavior. Folded as a section instead.

**Implicit blue-zone exception.** Rejected. "Blue" can include docs, fixtures, low-risk production paths — exempting all of them silently creates a hole. Explicit `exemptPaths` only.

**Hunk-local set-difference equivalence (was v3 algorithm).** Rejected. Closed the reformat false positive but opened a real laundering bypass: an agent that removes one marker and adds another anywhere in the same hunk produces no match, even when the suppression genuinely moved to a new statement. The bypass exactly matches the failure mode this feature was built to catch.

**Hunk-local count-based equivalence.** Rejected. Same shape of bypass — removed=1, added=1 still cancels regardless of which line the marker is on.

**Per-position pairing within a hunk.** Considered (was v4-proposed). Rejected after asymmetry analysis: the false-positive case (clean reformat) is visible to the reviewer and resolves in seconds; the false-negative cases the simpler algorithms allow are silent and load-bearing. The right move is to drop the equivalence entirely. Per-position pairing also has its own edge cases (markers on lines that match positionally but do something different), trading complexity for diminishing returns.

**Naive "fire on every added marker."** Chosen. Smallest implementation, no bypasses, false positives are visible-and-cheap. Symmetric with how the existing boundary-rule check works (every forbidden import on the head ref violates; the reporter doesn't try to be clever about whether it "really" was introduced by this diff). See §2.2.

**Auto-migration on upgrade.** Rejected. A reporter that quietly writes new files into a consuming repo on first run after upgrade is the wrong shape. Existing repos opt in via re-running bootstrap.

**Require justification comments alongside suppressions.** Rejected for v1. The reporter would have to parse "what counts as justification," and teams would game any rule with `# justification: needed`. The `architecture-review` checkpoint is the human-attention mechanism.

**Use Semgrep / ast-grep for detection.** Rejected. Substring/token/key match on diff-added lines is a few hundred lines; pulling in Semgrep adds a heavy dependency for no gain. Semgrep stays as a roadmap option for a generic "boundary-rule backend" extension (SPEC §15.3 #1), unrelated to suppression detection.

**Detect suppressions in the working tree, not just the diff.** Rejected. v1 is about new suppressions in this PR. A "show all existing suppressions on red zones" mode is a roadmap candidate (could surface in bootstrap output as a tech-debt report).

## 7. Open questions

These are flagged for adopter signal, not blockers:

1. **Reformat false-positive rate.** v1 fires on every added marker, including reformats that re-add a marker that was on a removed line. If adopters report the rate is high enough to dilute the `architecture-review` signal, revisit with one of the rejected algorithms in §6 (most likely per-position pairing) or a per-line "exact line content match between added and removed" check.
2. **Per-rule vs blanket suppressions.** `# noqa: F401` is narrower than bare `# noqa`; v1 treats them as the same marker (both are the substring `# noqa`). If adopters want differentiation (a blanket `# noqa` flagged more strongly than a code-specific one), add a `severity` field to the marker list.
3. **First-PR-after-bootstrap shock.** A repo with existing red-zone suppressions won't fire on them (diff-only detection), but the first edit near them might if it removes-and-re-adds the marker via a reformat. Mitigation: bootstrap surfaces existing suppressions on red zones in its summary output as tech-debt context. Decide with first-adopter feedback.
4. **Backend allowlist files outside the standard locations.** Custom architecture-test runners may put allowlists in non-standard paths. Policy's `configEdits.files` lets the team extend; structural parsing for non-line-oriented allowlists is a roadmap consideration.

## 8. Out of scope, deliberately documented

These came up in prior agent reviews and are *not* in this spec:

- **Bootstrap "gate fossils" discovery (P0 #2).**
- **Default policy packs (P0 #3).**
- **Consumer-map / blast-radius (P1).**
- **Persistent checkpoint history.**
- **Tree-hash sentinel.**

Each gets its own SPEC §15.3 entry once specced.

## 9. Mechanics summary

- **`core/skill/operating-mode.md`** — Step 4 governance subsection grows a fourth bullet.
- **`core/skill/bootstrap-mode.md`** — Phase 4 vendors `.agent-redline/suppressions.yaml` and writes the policy `suppressions:` block. Existing-repo upgrade path: re-running bootstrap detects the absent block and offers to add it.
- **`core/templates/skills/boundary-violation.md`** — Suppressions section appended.
- **`core/templates/agent-policy.yaml.template`** — `suppressions:` block placeholder.
- **`core/templates/suppressions.yaml`** — stack-neutral vendored defaults (the file bootstrap copies for non-extension or core-only repos).
- **`core/schema/agent-policy.schema.json`** — `suppressions` object, `modes.perCheck.suppression` enum value. Absent block remains valid (compatibility).
- **`core/schema/suppressions.schema.json`** — new schema for the vendored `.agent-redline/suppressions.yaml`.
- **`core/reporter/reporter.py`** —
  - `--diff-unified` input, parsed into added lines per file.
  - Vendored-defaults loader (`.agent-redline/suppressions.yaml`, fixed path).
  - `scan_suppressions()` — naive added-line match against the active marker list.
  - Absent-block compatibility: detection OFF when the policy has no `suppressions:` block.
  - `_binding()` hardcoded default of `binding` for `suppression`.
  - Match list feeds both the comment renderer and `_required_checkpoints()` (contributes `architecture-review`).
- **`extensions/python/suppressions.yaml`** + scaffold note (bootstrap vendors this file).
- **`extensions/jvm-archunit/suppressions.yaml`** + scaffold note.
- **PR-driven, push-driven, and local pre-push** — produce `git diff --unified=0` output; pass to reporter.
- **`tests/reporter/suppression-*/`** — golden fixtures (seven listed in §5).
- **`tests/schema/{valid,invalid}/`** — schema fixtures (three listed in §5).
- **`demo-source/agent-policy.yaml`** + **`demo-source-python/agent-policy.yaml`** — `suppressions:` block with `**/tests/**` exempt.
- **`demo-source/.agent-redline/suppressions.yaml`** + **`demo-source-python/.agent-redline/suppressions.yaml`** — vendored defaults.
- **`demo-source/pr-scenarios/suppression-change/`** + **`demo-source-python/pr-scenarios/suppression-change/`** — new demo PR.
- **`docs/SPEC.md`** — §4 vocabulary entry "Suppression marker." §15.5 changelog. §15.3 trims P0 #1 / #4.
- **`docs/POLICY_SCHEMA.md`** — `suppressions` block, vendored-file location, compatibility rule.
- **`docs/DECISIONS.md`** — companion entry covering the vendored-file contract, the naive-fire algorithm choice, and the asymmetry reasoning.

## 10. Order of work

1. Reporter input contract — `--diff-unified` flag, three producer updates.
2. Vendored-file contract — schema, loader, fixed-path resolution, missing-file error gated on `useExtensionDefaults: true`.
3. Schema additions — policy block + vendored-file schema, fixtures. Compatibility: absent block stays valid.
4. Detection — `scan_suppressions()` walks added lines, matches the active list, feeds `_required_checkpoints()`.
5. Reporter golden fixtures — seven listed in §5.
6. Skill text — operating-mode bullet + boundary-violation Suppressions section.
7. Extension marker lists — Python, JVM.
8. Bootstrap mechanics — vendor `.agent-redline/suppressions.yaml`, write policy block. Existing-repo re-bootstrap path.
9. Demo policies + vendored files + demo PRs.
10. SPEC + DECISIONS + POLICY_SCHEMA updates.

Steps 1–4 are sequential. Steps 6 and 7 are independent and can land in parallel. Steps 8–10 follow the core landing.

# jvm-archunit rename + reframe Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rename `extensions/spring-archunit/` to `extensions/jvm-archunit/`, refactor it into a generic JVM extension with a Spring addendum (mirroring how `extensions/python/` carries Python with a Django addendum), and add a JVM-library shape so non-Spring Java/Kotlin repos have a first-class path through bootstrap.

**Architecture:** This is a rename + reframe, not a rebuild. ArchUnit stays as the only backend (Java + Kotlin both supported by it; Scala out of scope for v1). The existing extension's structure becomes the *layered service* shape; Spring-specific zones, annotations, SpringDoc generation, and `application.yml` handling move into a *Spring addendum* (parallel to Python's Django addendum). A new *library / SDK* shape covers pure Maven/Gradle libraries with no HTTP surface. A *zone-only fallback* shape covers Android/Spark/mixed monorepos. The `agent-redline-demo` (Spring) repo stays as the v1 demo target — proving the refactored extension still works on Spring is the same chain the existing demo exercises. No new framework addendums (Quarkus, Micronaut) ship in this PR; the addendum *pattern* is what's proven.

**Tech Stack:** Markdown skill files, ArchUnit 1.3.0, JUnit 5, Gradle (Kotlin DSL + Groovy DSL) + Maven, Python 3 reporter, bash test harness.

**Lessons from `extensions/python/` baked in:**
- Skill content correctness has its own test layer — every YAML block is linted; every zone needs `reason:`, every boundary needs `description:` (Python had to fix this in `00e5214`).
- Referential integrity matters — `c42a858` caught dangling script paths in scaffold; the rename touches every reference, not just the directory.
- Scaffold YAML must execute, not just parse — `tests/scaffold-ci-e2e/check-spring-ci-e2e.sh` extracts and runs the §6 block from the scaffold; renaming must not break extraction.
- Bootstrap-detect tests are paths-on-the-table — when shape signals change in the bootstrap-mode triage table, fixtures under `tests/bootstrap-detect/fixtures/` exercise them (Python's `api/` omission, caught in `1406958`).
- The packaged `dist/` is generated, not hand-edited — `scripts/package-skill.sh` rebuilds it.
- Token-budget regression hits silently — every skill file edit must be followed by `bash tests/budget/check-budget.sh`.
- Calibration data isn't invalidated by renames — same paths, same firing rates.

---

## Phase 0 — Setup ✅ (this plan; durable state)

- [x] Worktree created: `.claude/worktrees/jvm-archunit-rename` on branch `worktree-jvm-archunit-rename`
- [x] Plan written: this file
- [x] Scope locked with user: Spring-only addendum (no Quarkus/Micronaut), Java + Kotlin (no Scala), keep existing `agent-redline-demo` as the v1 demo, no recalibration
- [ ] **Verification:** plan exists at `docs/superpowers/plans/2026-06-03-jvm-archunit-rename.md`; contains every phase below
- [ ] **Commit:** `jvm-archunit: phase 0 — plan`

---

## File map

This phase exists for *reasoning*, not for code. Lock the changes here before starting Phase 1.

### Renamed (5 files + 1 directory)

| From | To |
|---|---|
| `extensions/spring-archunit/README.md` | `extensions/jvm-archunit/README.md` |
| `extensions/spring-archunit/profile.md` | `extensions/jvm-archunit/profile.md` |
| `extensions/spring-archunit/scaffold.md` | `extensions/jvm-archunit/scaffold.md` |
| `extensions/spring-archunit/operating.md` | `extensions/jvm-archunit/operating.md` |
| `extensions/spring-archunit/adapter.yaml` | `extensions/jvm-archunit/adapter.yaml` (no content change) |
| `tests/extensions/spring-archunit/check-extension.sh` | `tests/extensions/jvm-archunit/check-extension.sh` (paths inside updated) |

### Restructured

- `extensions/jvm-archunit/profile.md` — split into shape sections following Python's structure: shape detection → layered service shape (the existing Spring profile, generalized) + library/SDK shape (new) + zone-only fallback (new) → Spring addendum (the moved-out Spring-specific zones) → ecosystem options (existing).
- `extensions/jvm-archunit/operating.md` — split into base operating notes (cross-framework: generated sources, multi-tenant migrations) + Spring addendum (`@Configuration`, `@RestController`, `@Transactional`, Spring Security, `application.yml` env-var overrides).
- `extensions/jvm-archunit/scaffold.md` — base ArchUnit dependency + test class + JUnit XML output + CI snippet stay; SpringDoc OpenAPI generation (§6) becomes a Spring addendum subsection. The §6 reporter run-block stays in the same shape so `tests/scaffold-ci-e2e/check-spring-ci-e2e.sh` keeps extracting it.
- `extensions/jvm-archunit/README.md` — reframe as JVM (Java + Kotlin) with Spring/library/zone-only shape pointer; "When to pick this" table.

### Modified — references that must point at the new path

| File | Lines / context |
|---|---|
| `core/skill/bootstrap-mode.md` | Line 48: `Spring Boot + Gradle/Maven → spring-archunit` becomes a JVM triage table (mirroring Python's). Inspection list keeps `build.gradle` / `pom.xml`. |
| `core/reporter/reporter.py` | Line 564 comment mentions `spring-archunit profile` — update to `jvm-archunit` (comment only, no behavior change). |
| `demo-source/agent-policy.yaml` | Lines 3, 12, 14, 20: `extension: spring-archunit` → `extension: jvm-archunit`; comments referring to the Spring profile updated. |
| `scripts/package-skill.sh` | Line 60: `"extensions/spring-archunit"` in `required_paths` → `"extensions/jvm-archunit"`; line 278 dist README ASCII tree updated. |
| `tests/run-all.sh` | Line 68: layer name `extension-spring` and path `tests/extensions/spring-archunit/check-extension.sh` → `extension-jvm` and `tests/extensions/jvm-archunit/check-extension.sh`. |
| `tests/scaffold-ci/check-scaffold-ci.py` | Line 55: `extensions/spring-archunit/scaffold.md` → `extensions/jvm-archunit/scaffold.md`. |
| `tests/scaffold-ci-e2e/check-spring-ci-e2e.sh` | Lines 2, 4, 5, 22, 39, 305: file header + `SCAFFOLD` path → jvm-archunit; assertions inside the run-block keep working because the `extension:` value in the test fixture (line 93) is `jvm-archunit`. |
| `tests/scaffold-ci-e2e/_extract-spring.py` | Lines 3, 6, 8: header comments → jvm-archunit. The script itself reads any path you pass it; the path is set by the caller. |
| `tests/skill-yaml/check-skill-yaml.py` | Lines 63–65: three `extensions/spring-archunit/*.md` paths → `extensions/jvm-archunit/*.md`. |
| `tests/skill-toml/check-skill-toml.py` | Lines 45–46: two paths → jvm-archunit. |
| `tests/reporter/_common-policy.yaml` | Line 6: `extension: spring-archunit` → `extension: jvm-archunit`. |
| `tests/reporter/api-changed-controllers/policy.yaml` | Line 9: same. |
| `tests/reporter/boundary-violation-shadow/policy.yaml` | Line 7: same. |
| `tests/reporter/excludes-respected/policy.yaml` | Line 6: same. |
| `tests/schema/valid/full.yaml` | Line 6: same. |
| `tests/schema/valid/boundary-adapter-junit-xml.yaml` | Line 6: same. |
| `tests/schema/invalid/missing-project-name.yaml` | Line 5: same. |
| `tests/budget/budget.yaml` | If renaming pushes any extension file's token count over its existing ceiling (`profile.md` 2700, `scaffold.md` 3100, `operating.md` 600, `README.md` 1000), raise the ceiling explicitly with rationale. The `extensions/*/X.md` glob already covers the new path; no rename needed in budget.yaml itself. |
| `CONTRIBUTING.md` | Line 7: `extensions/spring-archunit/` reference → `extensions/jvm-archunit/`. |
| `INSTALL.md` | Line 9: rephrase the v0.1 status sentence — `spring-archunit` reference becomes `jvm-archunit (with Spring addendum)`. |
| `README.md` | Line 120: Supported stacks table — link target → `extensions/jvm-archunit/`; first column wording stays "JVM (Java, Kotlin), Spring Boot" but extension column becomes `jvm-archunit`. |
| `docs/SPEC.md` | Lines 21, 107, 174, 276, 289, 319, 608, 631, 768, 782, 795, 816, 833: every `spring-archunit` mention. The §10 layout diagrams update to show `jvm-archunit/`. The "v0.1 ships with `spring-archunit` only" framing in §15 is now historical. |
| `docs/EXTENSIONS.md` | Lines 44, 143: rename references; the JUnit-XML reference example becomes `extensions/jvm-archunit/`. |
| `docs/BOOTSTRAP.md` | Lines 13, 50, 79: rename references; line 50 picks up the JVM triage logic. |
| `docs/DECISIONS.md` | Lines 32, 86, 105, 352, 354: existing entries keep historical `spring-archunit` text *only inside dated decision blocks*. New ADR appended for this refactor. |
| `docs/FAQ.md` | Lines 21, 78, 131: rename references. |
| `docs/POLICY_SCHEMA.md` | Lines 14, 122: example value updated; `extensions/spring-archunit/scaffold.md` reference → `extensions/jvm-archunit/scaffold.md`. |
| `examples/spring-hexagonal/README.md` | Lines 3, 50, 55: keep `examples/spring-hexagonal/` directory name (it IS Spring-specific); update extension references to `jvm-archunit` and `tests/extensions/jvm-archunit/check-extension.sh`. |
| `.github/workflows/extension.yml` | Line 9 (job name) → `jvm-archunit`; line 29 step `run:` path → `tests/extensions/jvm-archunit/check-extension.sh`. |

### Created (new content for shape support)

- `extensions/jvm-archunit/profile.md` — three new sub-sections: "Shape detection" (table), "Shape: library / SDK" (zones + boundaries + smaller PR-size thresholds), "Shape: zone-only fallback" (zones + `boundaryAdapter: outputFormat: none` + thresholds), "Spring addendum" (moved-out Spring-specific zones).
- `tests/bootstrap-detect/fixtures/jvm-library/` — minimal fixture: `pom.xml` (or `build.gradle`) for a library, no web framework, simulates a publishable artifact. Used by `tests/bootstrap-detect/check-bootstrap-detect.py` to verify the new shape signal.
- `tests/bootstrap-detect/fixtures/jvm-spring-service/` — fixture with `spring-boot-starter-web` dep, layered packages. Verifies the layered-service shape + Spring addendum activation.
- `docs/DECISIONS.md` — appended ADR: "2026-06-03 — `spring-archunit` becomes `jvm-archunit` with Spring as an addendum" with the rationale (the standing decision recorded in pallium memory `845d19d7`, mirroring Python's earlier framework-tied → language-generic decision).

### Deleted

- Nothing is deleted. The git mv preserves history; `dist/agent-redline/extensions/spring-archunit/` is regenerated from the renamed source by `scripts/package-skill.sh` and stays in sync with the new path. `.local/calibration/policies/spring-archunit-*.yaml` files keep their names (calibration history is dated and doesn't need renaming).

---

## Phase 1 — Rename + sweep references (no content change)

This phase is mechanical: `git mv` the directory, then update every reference. Zero content edits to the markdown files in this phase. The commit at the end must leave `bash tests/run-all.sh` green.

**Files:**
- Rename: `extensions/spring-archunit/` → `extensions/jvm-archunit/`
- Rename: `tests/extensions/spring-archunit/` → `tests/extensions/jvm-archunit/`
- Modify: every file in the "Modified" table above

- [ ] **Step 1.1: Move the extension directory**

```bash
git mv extensions/spring-archunit extensions/jvm-archunit
```

- [ ] **Step 1.2: Move the test harness directory**

```bash
git mv tests/extensions/spring-archunit tests/extensions/jvm-archunit
```

- [ ] **Step 1.3: Update test-harness internal paths**

Edit `tests/extensions/jvm-archunit/check-extension.sh`:
- Line 2 comment: `tests/extensions/spring-archunit/check-extension.sh` → `tests/extensions/jvm-archunit/check-extension.sh`
- Line 4: `Layer 3 dry-run for the spring-archunit extension.` → `Layer 3 dry-run for the jvm-archunit extension.`

`FIXTURE` on line 22 stays `examples/spring-hexagonal` — that fixture IS Spring-specific and is still the right thing to test against in v1.

- [ ] **Step 1.4: Update CI workflow**

Edit `.github/workflows/extension.yml`:
- Line 9: `spring-archunit:` → `jvm-archunit:`
- Line 29: `run: bash tests/extensions/spring-archunit/check-extension.sh` → `run: bash tests/extensions/jvm-archunit/check-extension.sh`

- [ ] **Step 1.5: Update package-skill.sh**

Edit `scripts/package-skill.sh`:
- Line 60 (`required_paths` array): `"extensions/spring-archunit"` → `"extensions/jvm-archunit"`
- Line 278 (dist README ASCII tree): the `spring-archunit/` entry inside the tree becomes `jvm-archunit/` with the same trailing comment.

- [ ] **Step 1.6: Update tests/run-all.sh**

Edit `tests/run-all.sh` line 68:
```
"extension-spring|bash tests/extensions/spring-archunit/check-extension.sh|OPTIONAL_GRADLE"
```
becomes
```
"extension-jvm|bash tests/extensions/jvm-archunit/check-extension.sh|OPTIONAL_GRADLE"
```

- [ ] **Step 1.7: Update tests/scaffold-ci/check-scaffold-ci.py**

Line 55: `"extensions/spring-archunit/scaffold.md"` → `"extensions/jvm-archunit/scaffold.md"`.

- [ ] **Step 1.8: Update Spring scaffold-ci-e2e test**

Edit `tests/scaffold-ci-e2e/check-spring-ci-e2e.sh`:
- Lines 2, 4, 5, 22, 39, 305: every `spring-archunit` path literal → `jvm-archunit`. The script filename itself (`check-spring-ci-e2e.sh`) and the test fixture name (`spring-e2e-fixture` on line 92) stay — they describe the *Spring scaffold subsection* being tested, not the extension directory.
- Line 93: `extension: spring-archunit` → `extension: jvm-archunit`.

Edit `tests/scaffold-ci-e2e/_extract-spring.py`:
- Lines 3, 6, 8 in the docstring: `extensions/spring-archunit/scaffold.md` → `extensions/jvm-archunit/scaffold.md`.

- [ ] **Step 1.9: Update skill-yaml and skill-toml test path lists**

Edit `tests/skill-yaml/check-skill-yaml.py` lines 63–65:
```python
    "extensions/spring-archunit/profile.md",
    "extensions/spring-archunit/scaffold.md",
    "extensions/spring-archunit/operating.md",
```
becomes
```python
    "extensions/jvm-archunit/profile.md",
    "extensions/jvm-archunit/scaffold.md",
    "extensions/jvm-archunit/operating.md",
```

Edit `tests/skill-toml/check-skill-toml.py` lines 45–46:
```python
    "extensions/spring-archunit/profile.md",
    "extensions/spring-archunit/scaffold.md",
```
becomes
```python
    "extensions/jvm-archunit/profile.md",
    "extensions/jvm-archunit/scaffold.md",
```

- [ ] **Step 1.10: Update reporter test fixtures**

In each of these YAML files, change `extension: spring-archunit` to `extension: jvm-archunit`:
- `tests/reporter/_common-policy.yaml` line 6
- `tests/reporter/api-changed-controllers/policy.yaml` line 9
- `tests/reporter/boundary-violation-shadow/policy.yaml` line 7
- `tests/reporter/excludes-respected/policy.yaml` line 6

- [ ] **Step 1.11: Update schema test fixtures**

Same change in:
- `tests/schema/valid/full.yaml` line 6
- `tests/schema/valid/boundary-adapter-junit-xml.yaml` line 6
- `tests/schema/invalid/missing-project-name.yaml` line 5

- [ ] **Step 1.12: Update demo-source policy**

Edit `demo-source/agent-policy.yaml`:
- Line 3 comment: `Generated from agent-redline's spring-archunit extension defaults,` → `Generated from agent-redline's jvm-archunit extension defaults (Spring addendum),`
- Line 12: `should use the narrower spring-archunit defaults` → `should use the narrower jvm-archunit defaults`
- Line 14: `See extensions/spring-archunit/profile.md and SPEC §4.3.` → `See extensions/jvm-archunit/profile.md and SPEC §4.3.`
- Line 20: `extension: spring-archunit` → `extension: jvm-archunit`

- [ ] **Step 1.13: Update examples/spring-hexagonal/README.md**

The directory name `examples/spring-hexagonal/` stays — it's a Spring fixture by design. Update only the references to the extension:
- Line 3: `tests/extensions/spring-archunit/check-extension.sh` → `tests/extensions/jvm-archunit/check-extension.sh`
- Line 50: same
- Line 55: `extensions/spring-archunit/` → `extensions/jvm-archunit/`

- [ ] **Step 1.14: Update reporter.py comment**

Edit `core/reporter/reporter.py` line 564 comment:

```python
    # The standard glob the spring-archunit profile uses; agent-redline
```

becomes

```python
    # The standard glob the jvm-archunit profile uses; agent-redline
```

Comment only — no behavior change, no test update needed beyond the existing reporter goldens.

- [ ] **Step 1.15: Update CONTRIBUTING.md, INSTALL.md, README.md**

`CONTRIBUTING.md` line 7: `extensions/spring-archunit/` → `extensions/jvm-archunit/`.

`INSTALL.md` line 9 sentence:
> The skill works end-to-end on Spring/JVM repos via the `spring-archunit` reference extension.

becomes:
> The skill works end-to-end on JVM repos (Spring covered explicitly via an addendum) through the `jvm-archunit` reference extension.

`README.md` line 120 (Supported stacks row):
```
| JVM (Java, Kotlin), Spring Boot | [`spring-archunit`](extensions/spring-archunit/) | [ArchUnit](https://www.archunit.org/) (JUnit XML) | [agent-redline-demo](https://github.com/rore/agent-redline-demo) |
```
becomes
```
| JVM (Java, Kotlin) — generic + Spring addendum | [`jvm-archunit`](extensions/jvm-archunit/) | [ArchUnit](https://www.archunit.org/) (JUnit XML) | [agent-redline-demo](https://github.com/rore/agent-redline-demo) |
```

- [ ] **Step 1.16: Update remaining doc references**

`docs/SPEC.md` — replace every `spring-archunit` literal with `jvm-archunit` EXCEPT inside the §15.1 "v0.1 ships with `spring-archunit` only" decision block — that's historical and stays as-is. Add one NOTE line under it: `Superseded 2026-06-03; see DECISIONS.md "spring-archunit becomes jvm-archunit".`

`docs/EXTENSIONS.md` lines 44, 143: rename literals.

`docs/BOOTSTRAP.md` lines 13, 50, 79: rename literals. Line 50's sentence
> For Spring Boot + Gradle/Maven, the agent suggests `spring-archunit`.

becomes
> For JVM (Java/Kotlin) repos — Gradle or Maven — the agent suggests `jvm-archunit`; Spring is detected separately and switches on the addendum.

`docs/FAQ.md` lines 21, 78, 131: rename literals.

`docs/POLICY_SCHEMA.md`:
- Line 14: example comment `e.g. "spring-archunit"` → `e.g. "jvm-archunit"`
- Line 122: scaffold reference `extensions/spring-archunit/scaffold.md` → `extensions/jvm-archunit/scaffold.md`

`docs/DECISIONS.md` — leave existing dated decision blocks unchanged. The new ADR is appended in Phase 4.

- [ ] **Step 1.17: Run the full test suite**

```bash
bash tests/run-all.sh
```

Expected: every layer green that was green on `main`. `extension-jvm` (renamed from `extension-spring`) is `OPTIONAL_GRADLE` so it skips on machines without Gradle.

If a layer fails, sweep for missed references:

```bash
grep -rn "spring-archunit" --include="*.md" --include="*.yaml" --include="*.yml" --include="*.py" --include="*.sh" . \
  | grep -v "/\.local/" \
  | grep -v "/dist/" \
  | grep -v "/docs/DECISIONS\.md"
```

Anything outside `.local/`, `dist/`, and the dated decision blocks in `DECISIONS.md` is a leftover.

- [ ] **Step 1.18: Rebuild dist/**

```bash
bash scripts/package-skill.sh
```

Expected last line: `built <repo>/dist/agent-redline`. The script wipes `dist/agent-redline/` and rebuilds — `dist/agent-redline/extensions/jvm-archunit/` will exist; `dist/agent-redline/extensions/spring-archunit/` will be gone.

Re-run `bash tests/run-all.sh` — the `package` layer compares `dist/` against the source.

- [ ] **Step 1.19: Commit**

```bash
git add -A
git commit -m "jvm-archunit: phase 1 — rename extensions/spring-archunit -> extensions/jvm-archunit (mechanical)"
```

The message says "mechanical" — the next reviewer needs to know no content changed in the moved files.

---

## Phase 2 — README + adapter.yaml content reframe

The smallest content edits, done before the bigger profile / scaffold restructures. README is human-facing and easier to validate; adapter.yaml's content is one comment update.

**Files:**
- Modify: `extensions/jvm-archunit/README.md`
- Modify: `extensions/jvm-archunit/adapter.yaml`

- [ ] **Step 2.1: Reframe README.md from Spring-specific to JVM-with-shapes**

Replace the entire content of `extensions/jvm-archunit/README.md` with:

```markdown
# jvm-archunit — agent-redline language extension

The reference language extension for **JVM repositories (Java, Kotlin)** using **ArchUnit** as the boundary-rule backend. Spring Boot, plain Java/Kotlin services, and pip/maven-publishable libraries are all in scope; bootstrap detects the shape and applies the matching defaults plus any framework addendum.

## When to pick this extension

Use this extension if your repo is:

- A JVM service or library — Java 17+ or Kotlin
- Built with Gradle (Kotlin or Groovy DSL) or Maven
- Organized in a hexagonal, layered, or onion-style package layout (services), or a public-API package layout (libraries)
- (Optional) using Spring Boot — covered by the Spring addendum
- (Optional) using Flyway or Liquibase migrations
- (Optional) using Spring Security / OAuth / JWT (covered by the Spring addendum)

If the repo uses Scala, this extension does not yet apply — Scala support is roadmap. ArchUnit handles Scala bytecode, but defaults and conventions for sbt + package objects + implicits aren't proven.

The extension covers three shapes:

1. **Layered service** — services with API/domain/adapters layers. Spring Boot is the dominant case and ships an addendum that augments these defaults; non-Spring services (plain JAX-RS, custom HTTP, gRPC) use the same shape without the addendum.
2. **Library / SDK** — Maven or Gradle artifacts whose value is their public API. Different red-zone defaults (`module-info.java`, package-info, public-API packages) and tighter PR-size thresholds.
3. **Zone-only fallback** — Android, Spark / Beam / Flink batch, mixed monorepos, or anything where ArchUnit isn't a fit. `boundaryAdapter: outputFormat: none`; the reporter skips the boundary leg but zones, persistence/security signals, and PR-size still run.

`profile.md` enumerates the three shapes; bootstrap inspects the repo, picks one (or proposes two when ambiguous), and the developer confirms.

## What's inside

| File | What it is |
|---|---|
| `README.md` | This file. |
| `profile.md` | Default zones, boundary rules, and JVM-specific gotchas — broken into the three shapes plus the Spring addendum. The agent reads this during bootstrap to draft `agent-policy.yaml`. |
| `scaffold.md` | How the agent generates the ArchUnit test class, the build wiring, and the CI snippet. The Spring addendum covers SpringDoc OpenAPI generation. |
| `operating.md` | Stack-specific operating-mode notes the agent reads when working in a JVM repo. The Spring addendum covers `@Configuration`, `@RestController`, `@Transactional`, Spring Security. |
| `adapter.yaml` | Tells the reporter where ArchUnit writes its output and what format it's in (JUnit XML). |

## Why ArchUnit

[ArchUnit](https://www.archunit.org/) is open source, JUnit-friendly, and built specifically for package-dependency rules. It analyzes compiled bytecode (Java + Kotlin both produce bytecode it understands), so it finds real violations rather than textual matches. It drops in as one test class and integrates with the existing `./gradlew test` task.

Alternatives (jQAssistant, Spring Modulith, Semgrep) are reasonable for some teams but bring more weight or are less natural for layered architecture rules. This extension commits to ArchUnit; teams that need a different backend can fork the extension or build their own.

## Pointers

- agent-redline core: [../../README.md](../../README.md)
- How to build a different extension: [../../docs/EXTENSIONS.md](../../docs/EXTENSIONS.md)
- Policy schema: [../../docs/POLICY_SCHEMA.md](../../docs/POLICY_SCHEMA.md)
```

- [ ] **Step 2.2: Update adapter.yaml header comment**

Edit `extensions/jvm-archunit/adapter.yaml` line 1:

```yaml
# spring-archunit adapter config
```

becomes

```yaml
# jvm-archunit adapter config
```

The rest of the file (the `boundaryAdapter:` block, the `violationFilter:` regex, the trailing notes) is unchanged — `*ArchitectureTest` is the convention in both Spring and non-Spring JVM extensions.

- [ ] **Step 2.3: Run skill-yaml + budget checks**

```bash
python tests/skill-yaml/check-skill-yaml.py
bash tests/budget/check-budget.sh
```

Expected: both green. README.md ceiling is 1000 tokens; the new file is shorter than that.

- [ ] **Step 2.4: Commit**

```bash
git add extensions/jvm-archunit/README.md extensions/jvm-archunit/adapter.yaml
git commit -m "jvm-archunit: phase 2 — README + adapter.yaml reframe (3 shapes, Spring as addendum)"
```

---

## Phase 3 — profile.md: shape detection + library shape + Spring addendum split

The hardest content phase. The existing Spring-only profile becomes the *layered service* shape; Spring-specific zones move to a *Spring addendum*; a new *library / SDK* shape and *zone-only fallback* shape are added; the front of the file gets a shape-detection table mirroring Python's structure.

**Pre-flight: re-read `docs/SKILL_AUTHORING.md` before editing.** The deletion test, imperative voice, and ceiling enforcement apply.

**Files:**
- Modify: `extensions/jvm-archunit/profile.md` (full restructure)

The order below is deliberate — write the new sections first, then move the existing content into the right place, then prune duplicates. This keeps each step's diff reviewable.

- [ ] **Step 3.1: Add the shape-detection table at the top**

Insert immediately after the `# jvm-archunit — profile` heading and before the existing "Framing — what red means here" paragraph:

```markdown
This profile enumerates **three shapes**: layered service (with a Spring addendum), library/SDK, and zone-only fallback. Bootstrap inspects, picks one (or proposes two when ambiguous), developer confirms.

Globs use `**/...` form so they match both standard `src/main/java/**` and Maven-multimodule `*/src/main/java/**` without duplication.

## Shape detection (Phase 1)

| Signal | Implies shape |
|---|---|
| `spring-boot-starter-*` or `org.springframework.boot:spring-boot` in `build.gradle` / `pom.xml` | layered service + Spring addendum |
| Web framework dep (`jakarta.ws.rs:*`, `io.javalin:javalin`, `io.ktor:*`, `io.helidon:*`, `io.dropwizard:*`, `org.eclipse.jetty:*`); or layer dirs `controller/`, `domain/`, `application/`, `adapter/`, `infrastructure/`, `core/`, `port/` | layered service |
| Build artifact is `jar` for distribution (`maven-publish`, `nexus-publish`, `org.gradle.api.publish`); `module-info.java` present; no web framework dep | library / SDK |
| `com.android.application` / `com.android.library` plugin, OR Spark / Beam / Flink deps, OR Hadoop deps | zone-only fallback |
| None match | zone-only fallback (developer can adjust) |

**Layout variants** (same shape — bootstrap derives, not separate shapes):
- standard: `src/main/java/<base-package>/...`, `src/main/kotlin/<base-package>/...`
- multi-module: each Gradle/Maven submodule has its own `src/main/...`
- mixed Java/Kotlin: both source roots; ArchUnit analyzes both because it operates on bytecode
```

- [ ] **Step 3.2: Rename the existing top-level "Default zones" / "Default boundary rules" / "API contract handling" sections to belong to the layered service shape**

Wrap the existing content from `## Default zones` through `## API contract handling` (everything ending before `## Ecosystem options`) under a new heading:

```markdown
## Shape: layered service
```

Inside that section, demote the existing `## Default zones`, `## Default boundary rules`, `## API contract handling` to `### Default zones`, `### Default boundary rules`, `### Default API contract handling`. Same content, deeper heading level.

- [ ] **Step 3.3: Move Spring-specific zones from the layered service section into a Spring addendum**

Cut the following entries from the layered service `### Default zones` block (they're Spring-specific):

From the **red** zones:
- `src/main/resources/application-prod*.yml` (Spring Boot profile naming)

From the **watch** zones:
- `src/main/java/**/*Controller.java` (Spring `@Controller`/`@RestController` convention)
- `src/main/resources/application.yml` (Spring Boot)
- `src/main/java/**/*Configuration.java` (Spring `@Configuration`)
- `src/main/java/**/*Filter.java` (Spring filters)
- `src/main/java/**/*Interceptor.java` (Spring interceptors)

These survive at the bottom of the file inside a new `## Spring addendum` section (Step 3.5).

The non-Spring entries that STAY in the layered-service shape:
- Red: repository/gateway interfaces, port interfaces, db migrations (Flyway/Liquibase paths), security/auth/jwt, architecture tests, `agent-policy.yaml`, `terraform/**`
- Watch: domain entity/model/service, application service/usecase/handler, adapter DTOs, generic `*Dto.java`

The "Note on the public API surface" paragraph that explains why `*Controller.java` is on watch and not red moves to the Spring addendum (it's a Spring-specific note).

- [ ] **Step 3.4: Move Spring-specific API handling into the Spring addendum**

The existing layered service `### Default API contract handling` section has THREE branches:
- **SpringDoc with a generation plugin** — Spring-specific, MOVES to the addendum
- **Committed OpenAPI spec** — generic, STAYS in the layered service shape
- **No public API surface** — generic, STAYS

Restructure: the layered-service `### API contract handling` keeps "Committed OpenAPI spec" + "No public API surface" as the two default branches. Add a one-liner at the top:

```markdown
For Spring services using SpringDoc, see the Spring addendum below for the `openapi-from-controllers` flow with runtime generation.
```

The Spring `openapi-from-controllers` branch (the YAML block + the `./gradlew generateOpenApiDocs` reference + the `scaffold.md §6 worktree pattern` pointer) moves to the addendum.

- [ ] **Step 3.5: Add the Spring addendum**

Insert AFTER the layered-service shape but BEFORE the existing `## Ecosystem options` section:

```markdown
## Spring addendum

If `spring-boot-starter-*` is in `build.gradle` / `pom.xml`, augment (don't replace) the layered-service zones:

```yaml
# Additional red:
zones:
  red:
    - path: src/main/resources/application-prod*.yml
      reason: production runtime configuration
      checkpoint: ops-review

# Additional watch:
  watch:
    - path: src/main/java/**/*Controller.java
      reason: controller change; structural API impact surfaced via OpenAPI diff
    - path: src/main/resources/application.yml
      reason: runtime configuration (default profile); visible, not a checkpoint
    - path: src/main/java/**/*Configuration.java
      reason: Spring configuration affects bean wiring globally
    - path: src/main/java/**/*Filter.java
      reason: Spring filters affect request lifecycle
    - path: src/main/java/**/*Interceptor.java
      reason: Spring interceptors affect request lifecycle
```

**Note on the public API surface.** `**/*Controller.java` is *not* red. Path-touch on a controller is a poor proxy for "API contract changed" — it fires on bug-fixes, refactors, and parameter validation just as readily as on real contract changes. The api-review checkpoint is triggered by the `api: openapi-from-controllers` semantic-diff signal instead, which detects added / removed / modified paths and operations. Controllers are on the watch list so the reporter still surfaces controller changes in the PR comment, but only real contract changes block on api-review. See `docs/DECISIONS.md` "Default red zones were calibrated against real PR history" for the firing-rate evidence.

### API contract handling — SpringDoc

When the repo uses SpringDoc with a generation plugin (`org.springdoc.openapi-gradle-plugin` or equivalent):

```yaml
api:
  type: openapi-from-controllers
  generationCommand: ./gradlew generateOpenApiDocs
  diffMode: structural
  checkpoint: api-review
```

See `scaffold.md` §6 for the CI worktree pattern. The local pre-push check does NOT run the generation (two builds is too slow); it relies on red-zone path classification — touched controllers fire api-review.
```

- [ ] **Step 3.6: Add the library / SDK shape**

Insert AFTER the Spring addendum and BEFORE `## Ecosystem options`:

```markdown
## Shape: library / SDK

For Maven Central / nexus-publish artifacts whose value is their public API.

### Default zones

```yaml
zones:
  red:
    # Public API surface — package-info, module-info, exported packages
    - path: "**/src/main/java/**/package-info.java"
      reason: published package-level documentation and exports
      checkpoint: api-review
    - path: "**/src/main/java/module-info.java"
      reason: JPMS module declaration; exports and requires shape the public API
      checkpoint: api-review
    - path: "**/src/main/kotlin/**/*.kt"
      reason: Kotlin public-API source — every public symbol is part of the contract
      checkpoint: api-review

    # Self-protection
    - path: "**/build.gradle"
      reason: build / dependency-rule configuration
      checkpoint: architecture-review
    - path: "**/build.gradle.kts"
      reason: build / dependency-rule configuration
      checkpoint: architecture-review
    - path: "pom.xml"
      reason: build / dependency-rule configuration
      checkpoint: architecture-review
    - path: "agent-policy.yaml"
      reason: governance source of truth
      checkpoint: architecture-review
    - path: "src/test/java/**/architecture/**"
      reason: dependency-rule definitions
      checkpoint: architecture-review
    - path: "src/test/java/**/*ArchitectureTest.java"
      reason: dependency-rule definitions when not under architecture/
      checkpoint: architecture-review

  watch:
    - path: "**/src/main/java/**/internal/**"
      reason: internal packages — public by Java visibility but not part of the contract
    - path: "**/CHANGELOG.md"
      reason: published changelog
    - path: "**/README.md"
      reason: README is part of the published artifact

  blue:
    - path: "**/src/test/**"
      reason: tests
    - path: "docs/**"
      reason: documentation
    - path: "scripts/**"
      reason: local tooling
```

The Kotlin red-zone glob is broad on purpose — Kotlin source has no `package-info.java` equivalent, and the tooling to reliably detect "added a public symbol" from a textual diff is absent. The first 2–4 weeks of shadow mode is where the team narrows it (e.g., to `**/api/**` if internal packages are conventionally separated).

### Default boundary rules

For libraries, the dominant rule is "internal stays internal":

```yaml
boundaries:
  - id: public-must-not-import-internal
    description: Public API packages must not depend on internal implementation details
    from: src/main/java/**
    forbidImports:
      - src/main/java/**/internal/**
    severity: error
```

Only generate this if the repo actually has `internal/` subpackages — don't fabricate.

### Default PR-size thresholds

Tighter than services because libraries change less per PR:

```yaml
prRules:
  maxChangedFiles: { warn: 20, fail: 50 }
  maxLinesChanged: { warn: 500, fail: 1000 }
```
```

- [ ] **Step 3.7: Add the zone-only fallback shape**

Insert AFTER the library shape and BEFORE `## Ecosystem options`:

```markdown
## Shape: zone-only fallback

For Android apps, batch / streaming pipelines (Spark, Beam, Flink), Hadoop, mixed monorepos. ArchUnit either doesn't fit the build (Android variants) or doesn't carry useful structural rules (data pipelines).

```yaml
zones:
  red:
    - path: "**/src/main/resources/db/migration/**"
      reason: persistence contract
      checkpoint: persistence-review
    - path: "**/changelog*.xml"
      reason: persistence contract (Liquibase)
      checkpoint: persistence-review
    - path: "**/src/main/java/**/security/**"
      reason: auth/security-sensitive code
      checkpoint: security-review
    - path: "agent-policy.yaml"
      reason: governance source of truth
      checkpoint: architecture-review
    - path: "terraform/**"
      reason: infrastructure
      checkpoint: ops-review

  watch:
    - path: "**/src/main/**"
      reason: production code (no boundary backend; surface visibility only)
    - path: "**/build.gradle*"
      reason: build configuration
    - path: "pom.xml"
      reason: build configuration

  blue:
    - path: "**/src/test/**"
      reason: tests
    - path: "docs/**"
      reason: documentation

boundaryAdapter:
  outputFormat: none

prRules:
  maxChangedFiles: { warn: 30, fail: 80 }
  maxLinesChanged: { warn: 800, fail: 1500 }
```

Reporter skips boundary parsing. Zones, persistence/security signals, PR-size still run.
```

- [ ] **Step 3.8: Move the "Default PR-size thresholds" section under the layered service shape**

The existing top-level `## Default PR-size thresholds` section becomes `### Default PR-size thresholds` under `## Shape: layered service` (the library and zone-only shapes have their own thresholds inside their sections).

- [ ] **Step 3.9: Move "Build / test commands" to the end of the file**

The existing `## Build / test commands` section stays — it applies to all shapes — but reorder to come after all three shape sections and the addendum, before `## Ecosystem options`.

- [ ] **Step 3.10: Move "Ecosystem-specific behavior" Spring entries into the Spring addendum**

The existing trailing `## Ecosystem-specific behavior` section has four bullets. Two are Spring-specific:
- `@RestController on internal-only endpoints.` → Spring addendum
- `application.yml env-var overrides.` → Spring addendum

Two are generic and stay:
- `Generated source directories.`
- `ArchUnit DoNotIncludeTests option.`

Rename the surviving section to `## JVM-specific behavior`.

- [ ] **Step 3.11: Run skill-yaml + skill-toml + budget checks**

```bash
python tests/skill-yaml/check-skill-yaml.py
python tests/skill-toml/check-skill-toml.py
bash tests/budget/check-budget.sh
```

Expected: green. If `bash tests/budget/check-budget.sh` reports `extensions/jvm-archunit/profile.md` over its 2700-token ceiling, raise the ceiling explicitly in `tests/budget/budget.yaml`. Document the why like Python's bootstrap-mode.md ceiling raise (`27ab85c`): name what content was added (3 shapes + Spring addendum + library zones) and the resulting line count.

If skill-yaml fails on a missing `reason:` or `description:`, fix the offending block — every zone entry needs `reason:`, every boundary entry needs `description:` (the same Python lessons from `00e5214`).

- [ ] **Step 3.12: Run schema check on the demo policy**

```bash
python tests/schema/check-schema.py
```

Expected: green. The `demo-source/agent-policy.yaml` uses `extension: jvm-archunit` (Phase 1 step 1.12); the schema's `extension:` field is a free string, so no enum needs updating.

- [ ] **Step 3.13: Run the reporter goldens to confirm no behavior drift**

```bash
python tests/reporter/check-reporter.py
python -m pytest tests/reporter/ -q
```

Expected: green. The reporter doesn't dispatch on extension name; it dispatches on `boundaryAdapter.outputFormat` which is unchanged.

- [ ] **Step 3.14: Commit**

```bash
git add extensions/jvm-archunit/profile.md tests/budget/budget.yaml
git commit -m "jvm-archunit: phase 3 — profile.md: 3 shapes (layered service / library / zone-only) + Spring addendum"
```

---

## Phase 4 — scaffold.md: split SpringDoc generation into a Spring addendum

The existing scaffold has six numbered sections. Sections 1 (ArchUnit dep), 2 (test class), 3 (test report output), 4 (CI snippet), 5 (baseline) all apply to any JVM repo. Section 6 (OpenAPI generation via SpringDoc) is Spring-specific.

The Spring scaffold-ci-e2e test (`tests/scaffold-ci-e2e/check-spring-ci-e2e.sh`, `_extract-spring.py`) extracts the §6 reporter run-block. Keep §6's structure intact so the extractor's regex (matches yaml blocks containing both `agent-redline-report.py` and `pull_request.base.sha`) still finds the block.

**Files:**
- Modify: `extensions/jvm-archunit/scaffold.md`

- [ ] **Step 4.1: Pre-flight — re-read `docs/SKILL_AUTHORING.md`**

Same imperative voice / deletion test discipline as Phase 3.

- [ ] **Step 4.2: Update the file header**

Change line 1: `# spring-archunit — scaffold` → `# jvm-archunit — scaffold`.

- [ ] **Step 4.3: Generalize the §1 ArchUnit dependency intro**

Existing intro paragraph mentions "Spring" and "Spring Boot". Replace with:

```markdown
## 1. ArchUnit dependency

Add the JUnit 5 module to the build if absent. Pin to a known stable version. Same dependency for Java and Kotlin — ArchUnit operates on bytecode.
```

The Gradle Kotlin DSL / Gradle Groovy DSL / Maven snippets stay verbatim.

- [ ] **Step 4.4: Generalize the §2 architecture-test class**

The existing class template uses `..domain..`, `..application..`, `..adapter..`, `..controller..`, `..repository..` — those are all generic JVM layered package conventions, not Spring-specific. The intro paragraph mentions Spring; rephrase:

```markdown
## 2. Architecture test class

Generate one `@ArchTest` method per `boundaries[]` entry in the policy. Test method name = boundary rule `id` (kebab-case → snake_case).

Substitute the actual base package and the actual layer package names from inspection. The example below uses placeholders (`domain`, `application`, `adapter`, `controller`); a repo using `core` / `infra` / `web` needs correspondingly different `resideInAPackage` arguments.

For Kotlin code, the same template works — ArchUnit inspects bytecode.
```

The Java code block below stays verbatim.

- [ ] **Step 4.5: §3 (test report output) — no changes**

Already generic. No edit.

- [ ] **Step 4.6: §4 CI snippet — generalize the intro**

The existing intro paragraph mentions both flow modes; that's already correct. No edit needed beyond verifying the Java version comment (`java-version: '21'                     # match the repo's Java version`) makes sense for a non-Spring repo too. It does — the comment says "match the repo's Java version", not "Spring's required version".

- [ ] **Step 4.7: §5 (baseline for retrofit) — no changes**

Already generic.

- [ ] **Step 4.8: Move §6 OpenAPI generation under a new "Spring addendum" heading**

Insert a new top-level heading right before the existing `## 6. OpenAPI generation (optional)`:

```markdown
## Spring addendum

The sections below apply only when the layered-service shape activated the Spring addendum (Spring Boot detected in `build.gradle` / `pom.xml`).

### 6. OpenAPI generation (optional)
```

Demote the existing `## 6.` to `### 6.` (heading level + 1). The body content — the SpringDoc requirements paragraph, the `api:` YAML block, the full CI YAML run-block, the fallback paragraphs at the end — all stay verbatim.

The scaffold-ci-e2e extractor matches yaml blocks by content (`agent-redline-report.py` + `pull_request.base.sha` both present), not by section number. Demoting `##` → `###` does NOT break extraction. Verify in step 4.10.

- [ ] **Step 4.9: Verify the scaffold-ci structural test still finds the run-block**

```bash
python tests/scaffold-ci/check-scaffold-ci.py
```

Expected: green. The check matches by content, not by heading.

- [ ] **Step 4.10: Verify the scaffold-ci-e2e test still extracts and runs**

```bash
bash tests/scaffold-ci-e2e/check-spring-ci-e2e.sh
```

Expected: green. The extractor (`tests/scaffold-ci-e2e/_extract-spring.py`) reads `extensions/jvm-archunit/scaffold.md` (path updated in Phase 1 step 1.8), finds the yaml block by `agent-redline-report.py` + `github.event.pull_request.base.sha` content match, runs it on the synthesized fixture, asserts `verdict.json` exists.

If extraction fails:
- Confirm the scaffold path passed to the extractor matches Phase 1 step 1.8's update.
- Confirm the demoted `### 6.` heading didn't change the yaml fence delimiters (the regex matches `^```yaml\s*\n(.*?)\n```\s*$`, which doesn't care about heading depth).

- [ ] **Step 4.11: Run skill-yaml + budget**

```bash
python tests/skill-yaml/check-skill-yaml.py
bash tests/budget/check-budget.sh
```

Expected: green. The scaffold ceiling is 3100; demoting one heading and adding the addendum intro adds <50 tokens.

- [ ] **Step 4.12: Commit**

```bash
git add extensions/jvm-archunit/scaffold.md
git commit -m "jvm-archunit: phase 4 — scaffold.md: SpringDoc OpenAPI moves under a Spring addendum heading"
```

---

## Phase 5 — operating.md: split base operating notes from Spring addendum

The existing `operating.md` has five bullets/sections. Three are Spring-specific (`@Configuration`, `@RestController`, `@Transactional`, Spring Security configuration changes, `application.yml` env-var overrides). Two are generic (generated sources, multi-tenant persistence).

**Files:**
- Modify: `extensions/jvm-archunit/operating.md`

- [ ] **Step 5.1: Pre-flight — re-read `docs/SKILL_AUTHORING.md`**

- [ ] **Step 5.2: Replace the file content**

Replace `extensions/jvm-archunit/operating.md` with:

```markdown
# jvm-archunit — operating-mode notes

JVM-specific behavior in addition to the core operating-mode rules.

## Generated sources

If the build generates Java sources (OpenAPI codegen, JOOQ, MapStruct, Immutables, Lombok delombok, gRPC stubs), generated directories should be in `excludes:` of the policy. If you find generated sources that aren't excluded, surface in the PR description and suggest a policy update.

## Multi-tenant persistence

If `persistence.notes` mentions multi-tenant migrations, the `persistence-review` checkpoint requires a rollout plan, not just a schema diff. Ask the developer about per-tenant impact when proposing a migration.

## ArchUnit `DoNotIncludeTests`

When generating the architecture test class, set `ImportOption.DoNotIncludeTests.class` (the `scaffold.md` §2 template already does this). Without it, test classes get analyzed and architecture rules fire on test-only code.

## Kotlin

ArchUnit reads bytecode, so Java rules apply to Kotlin. Kotlin-specific notes:

- Top-level functions compile to a `<FileName>Kt` class — `resideInAPackage` arguments treat them as members of that synthetic class.
- `internal` modifier in Kotlin compiles to `public final` bytecode with name mangling. ArchUnit cannot enforce Kotlin's `internal` visibility from bytecode alone — use the `internal` package convention for boundary rules instead.

## Spring addendum

The sections below apply only when the policy was generated with the Spring addendum (Spring Boot detected at bootstrap).

### Treat as red even if the policy doesn't say so

These come up in Spring services often enough that the agent should be cautious regardless of zone classification:

- **`@Configuration` classes.** Changes to bean wiring, scope, or initialization order are globally consequential.
- **`@RestController` annotation add/remove.** Even on internal endpoints — confirm whether the endpoint is genuinely internal-only or part of a contract.
- **`@Transactional` boundary changes.** Add/remove/propagation changes have runtime consequences tests often miss.
- **Spring Security configuration changes.** Treat as `security-review` even if the file is outside `**/security/**`.

### `application.yml` changes

Spring Boot environment variables (`SPRING_FOO_BAR_BAZ`) override YAML at deploy time. If a YAML edit changes a default that has a corresponding env var in production, treat as `ops-review` even if the YAML edit looks small.
```

- [ ] **Step 5.3: Run skill-yaml + budget**

```bash
python tests/skill-yaml/check-skill-yaml.py
bash tests/budget/check-budget.sh
```

Expected: green. The operating.md ceiling is 600 tokens; the new file adds the Kotlin section (~80 tokens) and a Spring addendum heading (~10 tokens). If over budget, raise the ceiling explicitly in `tests/budget/budget.yaml` with rationale (the Kotlin notes earn their place — Kotlin `internal` bytecode behavior is a real footgun for boundary rules).

- [ ] **Step 5.4: Commit**

```bash
git add extensions/jvm-archunit/operating.md tests/budget/budget.yaml
git commit -m "jvm-archunit: phase 5 — operating.md: base + Kotlin + Spring addendum split"
```

---

## Phase 6 — Bootstrap-mode awareness

The bootstrap skill needs to know about the new shapes and the Spring addendum trigger. Mirror Python's structure: a JVM triage table after the existing Python triage table.

**Files:**
- Modify: `core/skill/bootstrap-mode.md`

- [ ] **Step 6.1: Pre-flight — re-read `docs/SKILL_AUTHORING.md`**

The bootstrap-mode file has a 2500-token ceiling with significant prior raises (`5013306`, `9761b19`, `27ab85c`). New content here must earn its place.

- [ ] **Step 6.2: Update the extension-selection bullet**

Edit `core/skill/bootstrap-mode.md` line 48 — replace
```
- Spring Boot + Gradle/Maven → `spring-archunit`
```
with
```
- JVM (Java, Kotlin) — Gradle or Maven → `jvm-archunit` — see "JVM shape selection" below
```

- [ ] **Step 6.3: Add a JVM shape selection table**

Insert a new subsection between the existing `### Python shape selection` block and the existing `### Flow mode (CI shape)` block. Keep it terse — table + one-line confirmation rule, mirroring Python's table.

```markdown
### JVM shape selection

`jvm-archunit` covers three shapes plus a Spring addendum — `profile.md` enumerates them. Quick triage:

| Signal | Shape |
|---|---|
| `spring-boot-starter-*` or `org.springframework.boot:*` in `build.gradle` / `pom.xml` | layered service + Spring addendum |
| Web framework dep (`jakarta.ws.rs`, `javalin`, `ktor`, `helidon`, `dropwizard`) or layer dirs (`controller/`, `domain/`, `application/`, `adapter/`, `infrastructure/`, `core/`, `port/`) | layered service |
| Maven Central / nexus-publish artifact, `module-info.java` present, no web framework | library / SDK |
| `com.android.{application,library}`, Spark / Beam / Flink / Hadoop deps | zone-only fallback |
| None match | zone-only fallback |

Confirm before loading `profile.md` details. If two shapes could fire (e.g., a Spring Boot library), present both. Layout (single-module / multi-module / mixed Java+Kotlin) is bootstrap-derived, not a separate shape.
```

- [ ] **Step 6.4: Update Phase 1 inspection bullets**

The existing Phase 1 inspection list mentions `build.gradle` and `pom.xml`. Add one bullet to surface JVM shape signals:

After the existing build-files bullet, insert:

```markdown
- JVM dependency signals (when `build.gradle` / `build.gradle.kts` / `pom.xml` present): grep for `spring-boot-starter`, `org.springframework.boot`, `jakarta.ws.rs`, `javalin`, `ktor`, `helidon`, `dropwizard`, `com.android`, `apache.spark`, `apache.beam`, `apache.flink`. Determines layered-service vs library vs zone-only.
```

- [ ] **Step 6.5: Run budget check; raise ceiling if needed**

```bash
bash tests/budget/check-budget.sh
```

If `core/skill/bootstrap-mode.md` is over 2500, raise to 2600 in `tests/budget/budget.yaml` with rationale: the JVM triage table mirrors Python's (irreducible behavior-changing content).

- [ ] **Step 6.6: Run bootstrap-detect + skill-yaml**

```bash
python tests/bootstrap-detect/check-bootstrap-detect.py
python tests/skill-yaml/check-skill-yaml.py
```

Expected: green if existing fixtures still pass. The bootstrap-detect test has Python fixtures; this phase only adds JVM signals to the bootstrap markdown — the new fixtures land in Phase 7.

- [ ] **Step 6.7: Commit**

```bash
git add core/skill/bootstrap-mode.md tests/budget/budget.yaml
git commit -m "jvm-archunit: phase 6 — bootstrap-mode: JVM shape triage table + Spring detection"
```

---

## Phase 7 — Bootstrap-detect fixtures + ADR + final wiring

Two new bootstrap-detect fixtures verify the shape selection actually triggers on realistic repo layouts, the ADR records the decision, and the dist/ + demo policy wire-through gets a final pass.

**Files:**
- Create: `tests/bootstrap-detect/fixtures/jvm-spring-service/build.gradle`
- Create: `tests/bootstrap-detect/fixtures/jvm-spring-service/src/main/java/com/example/Application.java`
- Create: `tests/bootstrap-detect/fixtures/jvm-spring-service/expected.json`
- Create: `tests/bootstrap-detect/fixtures/jvm-library/build.gradle`
- Create: `tests/bootstrap-detect/fixtures/jvm-library/src/main/java/module-info.java`
- Create: `tests/bootstrap-detect/fixtures/jvm-library/expected.json`
- Modify: `tests/bootstrap-detect/check-bootstrap-detect.py` (add the two fixtures to its list — exact lines depend on existing structure)
- Modify: `docs/DECISIONS.md` (append ADR)

- [ ] **Step 7.1: Read the existing bootstrap-detect harness to understand fixture shape**

```bash
cat tests/bootstrap-detect/check-bootstrap-detect.py
ls tests/bootstrap-detect/fixtures/
```

Mirror an existing Python fixture's `expected.json` shape. The new fixtures' `expected.json` should declare the expected extension (`jvm-archunit`) and shape (`layered-service` / `library`).

If the existing harness has no shape field, add it through the smallest possible additive change — only if necessary; otherwise the fixture's `extension` field alone is enough verification.

- [ ] **Step 7.2: Create jvm-spring-service fixture — build.gradle**

```bash
mkdir -p tests/bootstrap-detect/fixtures/jvm-spring-service/src/main/java/com/example
```

Write `tests/bootstrap-detect/fixtures/jvm-spring-service/build.gradle`:

```groovy
plugins {
    id 'org.springframework.boot' version '3.4.0'
    id 'io.spring.dependency-management' version '1.1.6'
    id 'java'
}

group = 'com.example'
version = '0.0.1-SNAPSHOT'
java { sourceCompatibility = '21' }

dependencies {
    implementation 'org.springframework.boot:spring-boot-starter-web'
    testImplementation 'org.springframework.boot:spring-boot-starter-test'
    testImplementation 'com.tngtech.archunit:archunit-junit5:1.3.0'
}
```

- [ ] **Step 7.3: Create jvm-spring-service fixture — Application.java + expected.json**

Write `tests/bootstrap-detect/fixtures/jvm-spring-service/src/main/java/com/example/Application.java`:

```java
package com.example;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;

@SpringBootApplication
public class Application {
    public static void main(String[] args) {
        SpringApplication.run(Application.class, args);
    }
}
```

Write `tests/bootstrap-detect/fixtures/jvm-spring-service/expected.json` — match the existing fixture format exactly (read a Python fixture's `expected.json` first; the field names are project-specific and must match):

```json
{
  "extension": "jvm-archunit",
  "shape": "layered-service",
  "spring_addendum": true
}
```

If the harness doesn't currently support `shape` or `spring_addendum` keys, drop them — the `extension` field is the minimum that exercises the new branch.

- [ ] **Step 7.4: Create jvm-library fixture — build.gradle + module-info.java + expected.json**

```bash
mkdir -p tests/bootstrap-detect/fixtures/jvm-library/src/main/java
```

`tests/bootstrap-detect/fixtures/jvm-library/build.gradle`:

```groovy
plugins {
    id 'java-library'
    id 'maven-publish'
}

group = 'com.example.lib'
version = '1.0.0'
java { sourceCompatibility = '17' }

publishing {
    publications {
        library(MavenPublication) {
            from components.java
        }
    }
}
```

`tests/bootstrap-detect/fixtures/jvm-library/src/main/java/module-info.java`:

```java
module com.example.lib {
    exports com.example.lib.api;
}
```

`tests/bootstrap-detect/fixtures/jvm-library/expected.json`:

```json
{
  "extension": "jvm-archunit",
  "shape": "library",
  "spring_addendum": false
}
```

- [ ] **Step 7.5: Wire fixtures into `tests/bootstrap-detect/check-bootstrap-detect.py`**

Read the existing test harness file. Find the list/dict of fixtures it iterates. Add `jvm-spring-service` and `jvm-library` entries the same way Python fixtures are registered.

If the harness has no JVM detection logic at all (it only knows Python), this phase requires extending the detection rules in the script to read `build.gradle` / `pom.xml` content. Scope check: that's a behavior addition, not just a fixture addition. If the harness is Python-only today, mark this step as "scope expanded" in the commit message and add the smallest detection logic that makes the two fixtures pass — gradle plugin grep + dependency grep for the four signals in the triage table.

- [ ] **Step 7.6: Run bootstrap-detect**

```bash
python tests/bootstrap-detect/check-bootstrap-detect.py
```

Expected: green; the two new fixtures pass.

- [ ] **Step 7.7: Append the ADR**

Append to `docs/DECISIONS.md`:

```markdown
## 2026-06-03 — `spring-archunit` becomes `jvm-archunit` with Spring as an addendum

**Decision:** The reference JVM extension is renamed from `spring-archunit` to `jvm-archunit` and restructured along the same shape-plus-addendum pattern the Python extension already uses. The base extension covers Java + Kotlin layered services, libraries / SDKs, and a zone-only fallback. Spring Boot becomes an *addendum* — a set of additional zones and operating-mode notes that activate when Spring is detected — not the framing of the extension itself.

**Context:** The Python extension shipped framework-generic by explicit decision (Django was added as an addendum, not as the framing). The same standing rule applies to JVM: extensions should be language-generic, with framework specifics layered on. The original `spring-archunit` v0.1 extension predated this rule and was framed as Spring-specific, even though ArchUnit and most of the zones (repository/gateway interfaces, migrations, security paths, architecture tests) are framework-neutral.

**Considered alternatives:**

- Keep `spring-archunit` as-is and add a sibling `jvm-archunit` for non-Spring repos. Rejected: two extensions for one ecosystem is the shape the Python extension already argued against. The pattern is *one extension per language, addendum per major framework*.
- Rename without restructuring (cosmetic). Rejected: leaves Spring-specific paths (`*Controller.java`, `application.yml`, SpringDoc OpenAPI generation) embedded in the base profile, where they fire as red zones on non-Spring repos.

**Why now:**

- The Python extension proved the shape-plus-addendum pattern works (`extensions/python/` carries layered-service + library + zone-only-fallback shapes plus a Django addendum). Generalizing it to JVM is the natural follow-up.
- Calibration data behind the existing Spring defaults (the ~150 PRs from three Spring services in `.local/calibration/`) survives the move — the same paths fire at the same rates; they're just routed through the addendum now.

**What this changes:**

- `extensions/spring-archunit/` → `extensions/jvm-archunit/` (git mv, history preserved).
- Profile splits into three shapes + a Spring addendum.
- Operating-mode notes split into base + Kotlin + Spring addendum.
- Bootstrap-mode gets a JVM shape triage table.
- All references in `docs/`, tests, scripts, and the demo policy update to the new path.
- The `agent-redline-demo` repo stays Spring-based (same chain still exercised end-to-end).
- The packaged `dist/agent-redline/extensions/spring-archunit/` is regenerated by `scripts/package-skill.sh` and now ships as `dist/agent-redline/extensions/jvm-archunit/`.

**What this does not change:**

- ArchUnit remains the JVM backend (no scope expansion to Quarkus, Micronaut, or Scala in this PR).
- The boundary-violations schema and reporter dispatch logic — the rename is at the extension layer only.
- Existing dated decision blocks (including "v0.1 ships with `spring-archunit` only") stay as historical record. SPEC §15.1 gets a one-line "superseded" note pointing here.

**Revisit if:** A second framework addendum (Quarkus, Micronaut) is added — that's the point at which to confirm the addendum pattern is durable for >1 framework before declaring it stable.
```

- [ ] **Step 7.8: Re-run the full test suite + rebuild dist**

```bash
bash tests/run-all.sh
bash scripts/package-skill.sh
bash tests/run-all.sh
```

The double `run-all` is intentional: the `package` layer compares `dist/` against source after rebuild. Expected: green both times.

- [ ] **Step 7.9: Manually verify the dist contents**

```bash
ls dist/agent-redline/extensions/
```

Expected: `jvm-archunit` and `python` directories, no `spring-archunit`.

```bash
cat dist/agent-redline/extensions/jvm-archunit/profile.md | head -5
```

Expected first line: `# jvm-archunit — profile`.

- [ ] **Step 7.10: Manually verify reference integrity**

```bash
grep -rn "spring-archunit" --include="*.md" --include="*.yaml" --include="*.yml" --include="*.py" --include="*.sh" . | grep -v "^./.local" | grep -v "^./dist" | grep -v "^./docs/DECISIONS.md"
```

Expected: empty output. Anything else is a missed reference. Fix and rebuild.

The `.local/` references are historical calibration data; `dist/` references would mean the rebuild was skipped; `docs/DECISIONS.md` references are inside dated decision blocks (kept on purpose).

- [ ] **Step 7.11: Commit**

```bash
git add tests/bootstrap-detect/fixtures/jvm-spring-service/ \
        tests/bootstrap-detect/fixtures/jvm-library/ \
        tests/bootstrap-detect/check-bootstrap-detect.py \
        docs/DECISIONS.md \
        dist/
git commit -m "jvm-archunit: phase 7 — bootstrap-detect fixtures + ADR + dist rebuild"
```

---

## Phase 8 — Verification before completion

This phase is the gate before declaring done.

- [ ] **Step 8.1: Run the full local test suite**

```bash
bash tests/run-all.sh --verbose
```

Expected: every layer green that was green on `main` before this branch started. Compare layer-by-layer against a `git stash` of `main` if any are unexpectedly red.

The `extension-jvm` layer (renamed from `extension-spring`) is `OPTIONAL_GRADLE`. On a machine without Gradle, the layer skips with a clear note — that's expected behavior, not a regression. If you're verifying on a machine without Gradle, run that one layer separately on a Gradle-equipped machine before merging.

- [ ] **Step 8.2: Review the full diff against `main`**

```bash
git fetch origin main
git diff origin/main..HEAD --stat
git diff origin/main..HEAD -- extensions/jvm-archunit/
```

Expected `--stat` shape:
- `extensions/jvm-archunit/*` — 5 files (renamed from spring-archunit; content updated in phases 2–5)
- `tests/extensions/jvm-archunit/check-extension.sh` — renamed from spring-archunit
- `tests/scaffold-ci-e2e/_extract-spring.py` — small docstring updates
- `tests/scaffold-ci-e2e/check-spring-ci-e2e.sh` — path updates
- `tests/skill-{yaml,toml}/check-skill-{yaml,toml}.py` — path updates
- `tests/scaffold-ci/check-scaffold-ci.py` — path update
- `tests/run-all.sh` — layer rename
- `tests/reporter/*/policy.yaml` — extension field updates
- `tests/schema/{valid,invalid}/*.yaml` — extension field updates
- `tests/bootstrap-detect/fixtures/jvm-*` — new fixtures
- `tests/bootstrap-detect/check-bootstrap-detect.py` — new fixture wiring
- `tests/budget/budget.yaml` — possible ceiling raise (with rationale comment)
- `core/skill/bootstrap-mode.md` — JVM shape triage table
- `core/reporter/reporter.py` — comment update only
- `scripts/package-skill.sh` — required_paths + dist README tree
- `demo-source/agent-policy.yaml` — extension field + comments
- `examples/spring-hexagonal/README.md` — extension references
- `.github/workflows/extension.yml` — job + step rename
- `README.md`, `CONTRIBUTING.md`, `INSTALL.md` — references
- `docs/{SPEC,EXTENSIONS,BOOTSTRAP,FAQ,POLICY_SCHEMA,DECISIONS}.md` — references + new ADR
- `dist/agent-redline/...` — fully regenerated

If any file outside this list changed, justify it in the commit log or revert.

- [ ] **Step 8.3: Confirm the calibration data is untouched**

```bash
ls .local/calibration/policies/
```

Expected: both `spring-archunit-default.yaml` and `spring-archunit-tuned.yaml` still present, unchanged. Calibration history is dated and kept under `.local/`; renaming would discard the lineage.

- [ ] **Step 8.3a: Sync the demo and verify the three canonical PRs**

The `agent-redline-demo` repo is the e2e chain — AGENTS.md hard rule #6: "A feature is not done until the demo proves it end-to-end." A rename that breaks the demo is a regression even if every unit-test layer is green.

```bash
bash scripts/sync-demo.sh --push
```

Expected: the script force-pushes `demo/blue-only-pr`, `demo/red-with-checkpoint-pr`, `demo/boundary-violation-pr`, recreates the three PRs, applies the per-scenario labels.

Then check each PR's CI:

```bash
gh pr list --repo rore/agent-redline-demo --state open --json number,headRefName,statusCheckRollup
```

Expected verdicts:
- `demo/blue-only-pr` — CI green, sticky comment header `## agent-redline: BLUE`
- `demo/red-with-checkpoint-pr` — CI green (label-satisfied), sticky comment header `## agent-redline: RED`, checkpoint marked satisfied
- `demo/boundary-violation-pr` — CI red, sticky comment header `## agent-redline: BOUNDARY_VIOLATION`, exit-code-2 enforce step failed the run

Open each PR's sticky comment in the browser and confirm the rendered output matches `demo-source/pr-scenarios/<name>/expected-verdict.md`. Any drift is a regression — capture it before merging the rename.

- [ ] **Step 8.3b: Manual skill-content review against rebuilt dist**

Drop the rebuilt skill into a scratch directory and read it as the agent would. This catches the class of bug Pallium kept finding in Python (`00e5214` / `c42a858` / `072164e`): skill-content correctness issues — schema-invalid example YAML, dangling script paths, broken contract examples — that no test layer catches because they only fire when an LLM follows the markdown.

```bash
mkdir -p /tmp/jvm-archunit-skill-review
cp -r dist/agent-redline /tmp/jvm-archunit-skill-review/
```

Walk through the skill content as a hostile reviewer would:

1. Open `extensions/jvm-archunit/profile.md`. For every YAML block:
   - Every `red:` / `blue:` / `watch:` entry has both `path:` and `reason:`.
   - Every `boundaries:` entry has `id:`, `description:`, `from:`, `forbidImports:`.
   - The Spring addendum YAML is valid YAML on its own (eyeball each block).
2. Open `extensions/jvm-archunit/scaffold.md`. For every command and path mentioned (`./gradlew test --tests '*ArchitectureTest'`, `python scripts/agent-redline-report.py`, `./scripts/agent-redline-check.sh`), confirm the script exists in `dist/agent-redline/scripts/` or in a path the agent is told to vendor. No dangling references.
3. Open `extensions/jvm-archunit/operating.md`. Self-consistency: the Kotlin notes warn about `internal` bytecode mangling — is anything else in the file telling the agent to rely on `internal` for boundary rules? Should not be.
4. Open `core/skill/bootstrap-mode.md`. The JVM shape triage table's signals must match the signals in the new bootstrap-detect fixtures (Phase 7 step 7.2/7.4) and the signals in `extensions/jvm-archunit/profile.md`'s "Shape detection" section. Three places, must agree.

If any of these checks fails, fix and rebuild dist before merging.

- [ ] **Step 8.3c: Live agent dry-run against a JVM repo (REQUIRED)**

This exercises the full chain: agent reads skill → applies shape detection → generates artifacts. Unit tests prove the segments; only this proves the chain. The Python extension caught two skill-content bugs this way that no test layer found.

Two parts:

**Part 1 — Spring path (regression of existing behavior):**

Open a fresh Claude Code session, install `dist/agent-redline/` into `~/.claude/skills/agent-redline/`, point at a freshly-cloned `agent-redline-demo` (the `greenfield` branch — bare Spring service, no policy):

```bash
git clone -b greenfield https://github.com/rore/agent-redline-demo.git /tmp/jvm-dryrun-spring
```

Ask the agent: *"Use agent-redline to set up governance for this repo."* Watch:

- Detection: identifies layered-service shape + Spring addendum on.
- Generated `agent-policy.yaml` includes Spring addendum red zones (`application-prod*.yml`) and watch entries (`*Controller.java`, `application.yml`, `*Configuration.java`).
- Proposed scaffold references SpringDoc generation (the `api: openapi-from-controllers` block).
- Proposed `agent-policy.yaml` validates against the schema.

If anything diverges from the existing Spring demo's policy structure, that's a regression in Spring detection — fix before merging.

**Part 2 — Library path (new behavior):**

Clone a public OSS Java library with no Spring (e.g. `auth0/java-jwt`):

```bash
git clone https://github.com/auth0/java-jwt /tmp/jvm-dryrun-library
```

Ask the agent: *"Use agent-redline to set up governance for this repo."* Watch:

- Detection: identifies library / SDK shape, no Spring addendum.
- Generated `agent-policy.yaml`'s red zones are library-shape (`module-info.java`, `package-info.java`, public-API packages) — NOT Spring's `application-prod*.yml`.
- Proposed scaffold does NOT reference SpringDoc generation.
- PR-size thresholds use the tighter library defaults (warn 20 / fail 50 files, warn 500 / fail 1000 lines).
- Proposed `agent-policy.yaml` validates against the schema.

If the agent applies Spring zones to the library, the Spring detection signal is too eager — fix the bootstrap-mode triage table or the profile's shape-detection table before merging.

Capture the chat transcripts of both runs. Attach them to the PR (or paste the relevant decision summaries). The reviewer confirms the agent picked the right shape for each repo.

- [ ] **Step 8.4: Push and open PR**

```bash
git push -u origin jvm-archunit-rename
gh pr create --base main --title "jvm-archunit: rename + reframe (Spring as addendum)" --body "$(cat <<'EOF'
Renames `extensions/spring-archunit/` to `extensions/jvm-archunit/` and restructures it along the same shape-plus-addendum pattern the Python extension uses.

- Three shapes: layered service (Spring as addendum) / library / SDK / zone-only fallback
- Spring-specific zones, annotations, SpringDoc OpenAPI generation move to the addendum
- New JVM shape triage table in bootstrap-mode
- Two new bootstrap-detect fixtures (jvm-spring-service, jvm-library)
- ADR appended to DECISIONS.md

ArchUnit stays as the only JVM backend. No scope expansion to Quarkus, Micronaut, or Scala. The `agent-redline-demo` Spring repo continues to exercise the chain end-to-end.

See `docs/superpowers/plans/2026-06-03-jvm-archunit-rename.md` for the full plan and the lessons-from-Python that shaped it.
EOF
)"
```

- [ ] **Step 8.5: Wait for CI**

GitHub Actions runs `tests/run-all.sh` on a clean Ubuntu image. Expected: all layers green. The `extension` workflow (`.github/workflows/extension.yml`) runs the Gradle harness — that's where the JVM-specific Layer 3 verification actually executes (locally it's `OPTIONAL_GRADLE`).

If CI is red, read the failing layer's output, fix locally, re-run `bash tests/run-all.sh`, push.

- [ ] **Step 8.6: Address PR feedback if any, then merge**

Standard review loop. Once green and approved, merge to `main`.

- [ ] **Step 8.7: Update `.local/WORK_TRACKER.md`**

Append a session entry summarizing the rename, the shape additions, the ADR, and the `tests/run-all.sh` outcome. This is the AGENTS.md convention.

---

## Out of scope (explicit non-goals)

These were considered and deferred — record so the next agent doesn't re-litigate:

- **Quarkus / Micronaut addendums.** Roadmap. The first non-Spring framework addendum lands once a real repo asks for it; speculation isn't enough.
- **Scala support.** Roadmap. ArchUnit handles Scala bytecode but sbt + package objects + implicits need their own conventions and zero data backs default zones.
- **A non-Spring demo repo.** The `agent-redline-demo` Spring repo proves the chain end-to-end; a non-Spring sibling is a follow-up worth doing but not blocking on this rename.
- **Recalibrating the layered-service defaults.** The existing 150-PR Spring calibration data still applies (same paths, same firing rates). Recalibration belongs with the first non-Spring addendum, when there's data to calibrate against.
- **Schema enum on `extension:`.** `agent-policy.schema.json` defines `extension: {type: string}` (no enum) — old `extension: spring-archunit` policies don't fail schema validation. Adding an enum would be a separate decision with migration cost.

---

## Resume protocol

Find the first phase whose checkboxes are unchecked. Run its verification gate before moving on. `bash tests/run-all.sh` must be green at the end of every phase that touches code. One commit per phase, prefixed `jvm-archunit: phase N — <summary>`.

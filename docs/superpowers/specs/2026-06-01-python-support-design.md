# Python support — design spec

**Status:** approved 2026-06-01. Implementation plan: `docs/superpowers/plans/2026-06-01-python-support-plan.md`.

## Goal

Make agent-redline a first-class governance layer for Python repos, end-to-end: bootstrap recognises Python projects, the skill produces a sensible `agent-policy.yaml` and scaffolds `import-linter`, the reporter ingests `import-linter` output deterministically, CI runs the same checks, and an `agent-redline-python-demo` repo exercises the same three canonical PR states the existing JVM demo does (BLUE / RED-with-checkpoint / BOUNDARY_VIOLATION).

This is the second language extension. By design it forces the reporter generalisation that SPEC §15.3 promised — see [§3 Reporter generalisation](#3-reporter-generalisation).

## Non-goals (v1)

- DRF / drf-spectacular OpenAPI integration. Spring + SpringDoc was real work; doing the same for Python now would dilute v1. Path-touch on `urls.py` (Django) and on FastAPI router files is the v1 api-change signal. drf-spectacular and FastAPI's `app.openapi()` are explicit roadmap.
- Asyncio-specific or framework-specific contracts beyond what `import-linter`'s built-in contract types express.
- A central extension registry. Extensions still live in-tree under `extensions/`; no plugin loader is introduced.

## 1. Three Python shapes, one extension

The Python extension lives at `extensions/python/`. Its `profile.md` enumerates three shapes; bootstrap inspects the repo, picks one (or proposes two if ambiguous), and the developer confirms.

### 1.1 Layered service

A Python application organised by layer: API/entry on the outside, domain in the middle, adapters/persistence at the edge.

**Detection signals (any one is sufficient):**
- A web framework dep in `pyproject.toml` / `setup.py` / `requirements*.txt`: `fastapi`, `flask`, `django`, `starlette`, `aiohttp`, `sanic`, `litestar`, `falcon`, `bottle`.
- Explicit layer directories under the project's package root: any of `domain/`, `application/`, `adapters/`, `infrastructure/`, `core/`, `services/`, `usecases/`, `ports/`.

**Layout variants (bootstrap derives — not separate shapes):**
- `src/` layout: `src/<pkg>/{...}/`. Detected by the presence of `src/` containing exactly one package directory matching the project name.
- Flat layout: `<pkg>/{...}/` at repo root.

**Default zones (placeholders; bootstrap substitutes the actual package name):**

```yaml
zones:
  red:
    # Persistence migrations — applies to Alembic, Django, yoyo, custom.
    - path: "**/alembic/versions/**.py"
      reason: persistence contract (Alembic)
      checkpoint: persistence-review
    - path: "**/migrations/**.py"
      reason: persistence contract (framework migrations)
      checkpoint: persistence-review

    # Security/auth code
    - path: "**/<pkg>/**/security/**"
      reason: auth/security-sensitive code
      checkpoint: security-review
    - path: "**/<pkg>/**/auth/**"
      reason: auth/security-sensitive code
      checkpoint: security-review

    # Outbound port / gateway contracts (when present in this layout)
    - path: "**/<pkg>/**/ports/**"
      reason: architectural boundary contracts (port interfaces)
      checkpoint: architecture-review
    - path: "**/<pkg>/**/domain/repositories/**"
      reason: domain repository interfaces
      checkpoint: architecture-review

    # Self-protection
    - path: ".importlinter"
      reason: dependency-rule definitions
      checkpoint: architecture-review
    - path: "pyproject.toml"          # contracts may live here under [tool.importlinter]
      reason: build / dependency-rule configuration
      checkpoint: architecture-review
    - path: "agent-policy.yaml"
      reason: governance policy
      checkpoint: architecture-review

  watch:
    # API entry points — surface in PR comment, do not block.
    - "**/<pkg>/**/api/**"
    - "**/<pkg>/**/routers/**"
    - "**/<pkg>/**/views/**"
    - "**/<pkg>/**/controllers/**"
    # Domain entities — touched on most feature PRs; not red.
    - "**/<pkg>/**/domain/**"
    # Adapters — broadly visible structural changes.
    - "**/<pkg>/**/adapters/**"
    - "**/<pkg>/**/infrastructure/**"

  blue:
    - "**/tests/**"
    - "**/test_*.py"
    - "**/*_test.py"
    - "**/conftest.py"
```

**Default boundary contracts (`import-linter`):**

1. `layers` contract — top-down dependencies only.
   ```toml
   [[tool.importlinter.contracts]]
   name = "Layered architecture"
   type = "layers"
   layers = ["<pkg>.api", "<pkg>.application", "<pkg>.domain", "<pkg>.infrastructure"]
   ```
2. `forbidden` contract — domain doesn't import any framework module.
3. `independence` contract — adapters are independent of each other.
4. `acyclic_siblings` — top-level package siblings don't form cycles. (Hygiene.)

Bootstrap picks the subset that matches the actual layout (skip layers absent from the repo).

### 1.2 Library / package

A pip-installable package whose value is its public API surface.

**Detection signals:**
- `pyproject.toml` with a `[project]` table or `[tool.setuptools]` / `[tool.poetry]` block, **and**
- No web-framework dep, **and**
- A top-level package with `__init__.py` (typically with `__all__` or re-exports).

**Default zones:**

```yaml
zones:
  red:
    # The public-API surface itself.
    - path: "**/<pkg>/__init__.py"
      reason: public API re-exports
      checkpoint: api-review
    - path: "**/<pkg>/**/*.pyi"
      reason: published type stubs
      checkpoint: api-review
    # Any module whose name does NOT begin with underscore is part of the public API
    # by Python convention. Bootstrap derives concrete globs from the layout.

    # Self-protection
    - path: ".importlinter"
      reason: dependency-rule definitions
      checkpoint: architecture-review
    - path: "pyproject.toml"
      reason: build / dependency-rule configuration
      checkpoint: architecture-review
    - path: "agent-policy.yaml"
      reason: governance policy
      checkpoint: architecture-review

  watch:
    - "**/<pkg>/**/*.py"

  blue:
    - "**/tests/**"
    - "**/test_*.py"
```

**Default boundary contracts:**

1. `protected` contract — modules with leading-underscore names not imported across the package boundary.
2. `acyclic_siblings` — internal modules don't form cycles.
3. `forbidden` contract templates for any explicit "experimental" or "internal" sub-namespaces the repo declares.

### 1.3 Zone-only fallback

For Python repos where boundary enforcement adds little value: data pipelines (Airflow, Prefect, Dagster), notebook-heavy ML repos, monorepos with mixed shapes, scripts-and-glue.

**Detection signals (positive):**
- Pipeline dep present: `apache-airflow`, `prefect`, `dagster`, `luigi`.
- Notebook directory: `notebooks/` containing `.ipynb` files.
- Top-level `dags/` or `pipelines/` directory.

**Detection signals (negative — falls back here):**
- No detectable layered structure AND no clear public-API package shape.

**Adapter:** `outputFormat: none`. Reporter skips the boundary section. Zones, persistence, security, and PR-size checks still run.

### 1.4 Django addendum

If `manage.py` exists at the repo root **and** `django` is in deps, layered-service zones are augmented (not replaced) with:

**Additional red zones:**
- `**/settings*.py` — `INSTALLED_APPS`, middleware, auth, secrets — security-review.
- `**/urls.py` — URL routing surface — api-review.
- `**/migrations/*.py` — already covered above; explicit re-mention.
- `**/<app>/models.py` — model changes are persistence-shape changes — persistence-review (caveat: this fires often; subject to calibration in §6).

**Additional watch entries:**
- `**/admin.py`
- `**/management/commands/**.py`
- `**/serializers.py` (only when `djangorestframework` is in deps)

**Additional boundary contracts:**
- `independence` over the apps directory: sibling Django apps don't import each other's internals (`<project>.apps.A.models` <-/-> `<project>.apps.B`).
- `forbidden` from any app's `views`/`viewsets` to another app's `models` (must go through public functions or a shared-kernel module).

**Detection precedence:** if Django is detected, treat as layered-service shape with the addendum applied. Library and zone-only detections are not considered.

## 2. Backend: import-linter

`import-linter` is the documented choice (EXTENSIONS.md table; SPEC §3 glossary). Verified during research:

- **Configuration:** TOML in `pyproject.toml` (preferred) or INI in `.importlinter`. We prefer TOML — bootstrap writes contracts under `[tool.importlinter]`.
- **CLI:** `lint-imports`. Options: `--config`, `--contract`, `--cache-dir`, `--no-cache`, `--show-timings`, `--verbose`. **No** `--format` / `--output` flag.
- **Output:** Rich-rendered text to stdout. Exit code 0 (kept) / 1 (broken) only.
- **Public Python API:** `importlinter.api.read_configuration()` — reads config back out, no programmatic check API.
- **Internal API used by the adapter:** `importlinter.application.use_cases.create_report(...)`. Returns a `Report` object with `get_contracts_and_checks()`. This is internal-but-stable: it's used by `cli.py` and the documented `lint_imports()` entry point.
- **Contract types** (5 built-in, all with stable docs): `layers`, `forbidden`, `protected`, `independence`, `acyclic_siblings`. Custom contracts are supported via Python class registration; v1 uses built-in only.
- **Static-analysis caveats:** dynamic imports (`importlib.import_module`, `__import__`) are invisible; `if TYPE_CHECKING:` imports configurable via `exclude_type_checking_imports = True`. Both are documented in `profile.md` gotchas.

Because there is no machine-readable output, the extension ships an adapter script — see §4.

## 3. Reporter generalisation

This is the structural change `SPEC §15.3` already promises and gates on the second extension. We do it now.

### 3.1 New output format: `json-violations`

A schema for boundary violations independent of any backend's native format. Stored at `core/schema/boundary-violations.schema.json`:

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "type": "object",
  "required": ["violations"],
  "properties": {
    "version": { "type": "integer", "const": 1 },
    "source":  { "type": "string" },
    "violations": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["rule", "detail"],
        "properties": {
          "rule":     { "type": "string" },
          "detail":   { "type": "string" },
          "severity": { "type": "string", "enum": ["error", "warning"], "default": "error" }
        },
        "additionalProperties": false
      }
    }
  },
  "additionalProperties": false
}
```

### 3.2 Reporter changes

- New parser `parse_json_violations(text: str) -> list[BoundaryViolation]` alongside the existing `parse_archunit_junit_xml`.
- New CLI flag `--boundary-report <path>` plus `--boundary-format <junit-xml|json-violations|none>`.
- The existing `--archunit-xml` flag becomes a deprecated alias for `--boundary-report` with `--boundary-format=junit-xml`. Kept indefinitely for back-compat (Spring CI snippets in the wild use it).
- Reporter dispatches on `--boundary-format`. The `BoundaryViolation.source` field carries the backend identity (`archunit`, `import-linter`, …) for the PR comment.

### 3.3 Adapter dispatch from the policy

`agent-policy.yaml` gains an optional `boundaryAdapter` field (mirrors what extensions declared in `adapter.yaml`):

```yaml
boundaryAdapter:
  outputFormat: junit-xml | json-violations | none
  outputPath: <path glob>
  violationFilter:                # optional, junit-xml only
    matchClassName: <substring>
    matchTestNamePattern: <regex>
```

When the policy declares `boundaryAdapter` and `--boundary-format` is not passed, the reporter reads `boundaryAdapter.outputFormat` and `boundaryAdapter.outputPath` (if no explicit `--boundary-report` was given). This delivers the SPEC promise that the reporter "dispatches on `adapter.yaml`" — without a separate `adapter.yaml` lookup, by lifting the contract into the policy, which is what the bootstrap was already going to write anyway.

The standalone `extensions/<name>/adapter.yaml` file remains as the **extension's source of truth** that bootstrap copies into the consuming repo's `agent-policy.yaml`.

### 3.4 Backwards compatibility

- All existing `tests/reporter/` golden fixtures stay green: they pass `--archunit-xml`, which still works.
- The Spring extension's `adapter.yaml` does not change. Spring repos generated before this change keep working.
- New repos generated by bootstrap get the `boundaryAdapter:` block in their policy.
- The reporter's JSON verdict shape does not change.

## 4. The Python extension layout

```
extensions/python/
├── README.md
├── profile.md
├── scaffold.md
├── operating.md            # Python-specific operating notes (dynamic imports, type-checking imports)
├── adapter.yaml
└── scripts/
    └── run-import-linter.py
```

### 4.1 `scripts/run-import-linter.py`

Runs `import-linter` via its internal `create_report(...)` API and emits `boundary-violations.json` matching the schema in §3.1. CLI:

```
run-import-linter.py [--config <path>] [--out <path>] [--cache-dir <path>] [--no-cache]
```

Behaviour:
- Imports `importlinter.application.use_cases.create_report` and `importlinter.application.user_options.read_user_options`.
- Pins `import-linter>=2.0,<3` in `scaffold.md`'s `pip install` line — that range is what `create_report` is verified against.
- Walks `report.get_contracts_and_checks()`. For each broken `ContractCheck`, reads `contract.name` and the check's `metadata` (the violation list) and emits one `{rule, detail, severity}` record per concrete violation.
- Catches `ImportError` on the internal modules, prints a clear error pointing to the pinned version range, and exits non-zero.
- Writes the JSON to `--out` (default `build/import-linter-report.json`).
- Exit code: 0 if no broken contracts, 1 if any. Independent of whether the JSON file was successfully written (the file is always written; non-zero exit signals violations).

Why it's allowed to live in the extension despite the historical "markdown-only" claim: see §5.

### 4.2 `adapter.yaml`

```yaml
boundaryAdapter:
  outputFormat: json-violations
  outputPath: build/import-linter-report.json
```

No `violationFilter` (the JSON output already contains only boundary-rule violations).

### 4.3 `scaffold.md` outline

1. Install: `pip install 'import-linter>=2.0,<3'` — added to dev/test extras of `pyproject.toml`.
2. Generate `[tool.importlinter]` block in `pyproject.toml` with the contracts derived from the chosen shape.
3. Add `scripts/run-import-linter.py` to the consuming repo (copied from the extension at bootstrap time).
4. CI snippet: a `boundary` job that runs `pip install -r requirements.txt && python scripts/run-import-linter.py --out build/import-linter-report.json` and uploads the report; the reporter job reads it.
5. Pre-push integration: a line in `scripts/agent-redline-check.sh` that runs `run-import-linter.py` if the repo has it.
6. Optional Django bootstrap notes: detect `manage.py`, ensure the `<project>/settings.py` is in red zones, ensure the apps directory has the `independence` contract.

### 4.4 `operating.md` outline

Stack-specific operating-mode notes:
- Dynamic imports (`importlib`, `__import__`) bypass contracts — agents must NOT use them to work around boundary rules.
- Don't add `# noqa: import-linter` style suppressions; if a violation is justified, add an explicit `ignore_imports` entry to the contract and treat it as a red-zone change.
- Test fixture imports: tests live under blue zones; cross-layer imports inside test code are fine.

### 4.5 `profile.md` structure

```
# python — profile

## Detection

[shape-detection logic for bootstrap]

## Shape: layered service

### Default zones
### Default boundary contracts
### Default PR-size thresholds
### If Django: addendum

## Shape: library / package

### Default zones
### Default boundary contracts
### Default PR-size thresholds

## Shape: zone-only fallback

### Default zones (no boundary backend)
### Default PR-size thresholds

## Gotchas

- Dynamic imports are invisible to import-linter
- TYPE_CHECKING imports — when to exclude
- Namespace packages — root_packages config
- Editable installs / src layout
```

## 5. Updated extension contract

The current `docs/EXTENSIONS.md` claims:

> Extensions are markdown plus one small YAML file. No scripts, no parsers, no plugins.

That claim was wrong. `import-linter` has no machine-readable output format, and no honest path forward avoids a small adapter script. Two changes:

1. **Allow extensions to ship scripts** in a `scripts/` subdirectory. Scripts are responsible only for converting the backend's output into one of the reporter's supported formats (`junit-xml` or `json-violations`). They MUST NOT replicate reporter logic, classify zones, or compute checkpoints.
2. **Add a "Backends without machine-readable output" section** explaining the pattern: ship a `scripts/run-<backend>.py` that runs the tool and emits `json-violations`; declare `outputFormat: json-violations` in `adapter.yaml`.

Constraints retained:
- Extensions still don't implement the reporter, the policy schema, the verdict format, or the bootstrap loop.
- Adapter scripts are pure converters with a narrow, documented contract.
- Each adapter script must be runnable standalone for testing.

`DECISIONS.md` gets a new entry recording the why and the bound: scripts are admitted as a narrow exception when the backend forces it, not as a general extension capability.

## 6. Calibration

Following `DECISIONS.md` 2026-05-30 ("calibration is a continuum starting at bootstrap"), v1 of Python support will:

- Ship the layered-service profile in **shadow mode by default** (the policy's `modes.default: shadow`). This matches how the Spring extension landed.
- Ship a tuning preset under `scripts/agent-redline-tune.py` (or an extension hook) that consuming repos can run against their merged-PR history before flipping to binding.
- The Python demo repo serves as the reference calibration: its zones fire on the canonical RED PR and stay quiet on the canonical BLUE PR.

The Django addendum's `models.py = persistence-review` rule is the highest-risk-of-noise default. Bootstrap surfaces this with a one-line note when generating the policy and recommends moving it to `watch` until calibration.

## 7. The Python demo repo

`agent-redline-python-demo` (separate repo, structure mirrors `agent-redline-demo`).

**Layout:**
- `src/orders/{api,application,domain,infrastructure}/` — minimal layered FastAPI service.
- `pyproject.toml` with `[tool.importlinter]` contracts.
- `agent-policy.yaml` adapted from `extensions/python/profile.md`.
- `.github/workflows/agent-redline.yml` — the boundary + reporter jobs.
- `scripts/agent-redline-check.sh` — local pre-push.

**Three canonical PRs** (mirrors the JVM demo):
- `demo/blue-only-pr` — adds an isolated test or utility module. BLUE verdict, no checkpoint.
- `demo/red-with-checkpoint-pr` — modifies `src/orders/domain/repositories/orders_repo.py`. RED with `architecture-review` checkpoint; the PR has the `architecture-reviewed` label applied so the checkpoint is satisfied; CI green.
- `demo/boundary-violation-pr` — adds an import in `src/orders/domain/order.py` from `src/orders/infrastructure/db/sqlalchemy_session.py`, breaking the `layers` contract. BOUNDARY_VIOLATION; CI red; PR cannot merge.

**Sync mechanism:** mirror `scripts/sync-demo.sh`'s pattern — a `demo-source/` directory in the main repo holds the canonical files, and `sync-demo.sh` (or a parallel `sync-python-demo.sh`) pushes them to the demo repo.

The demo is the integration test for the Python extension end-to-end. A repo-level smoke test in `tests/extensions/python/check-extension.sh` runs `lint-imports` against the demo's `BOUNDARY_VIOLATION` fixture and asserts the JSON output shape.

## 8. Documentation updates

- `README.md` — Python moves from roadmap to "shipped". One-line table row update.
- `docs/SPEC.md` — §15.3 entry "Additional language extensions" updated to reflect Python landed; reporter dispatch on `outputFormat` is now implemented.
- `docs/DECISIONS.md` — three new entries:
  1. "Python extension uses import-linter; adapter script required because no machine-readable output."
  2. "Reporter generalisation: `json-violations` as a second `outputFormat`; reporter dispatches on the policy's `boundaryAdapter.outputFormat`."
  3. "Extension contract revised: `scripts/` subdirectory permitted for output-format adapters; constraints documented."
- `docs/EXTENSIONS.md` — the §5 changes (allow scripts, document `json-violations`).
- `docs/POLICY_SCHEMA.md` — document the `boundaryAdapter` block.
- `core/schema/agent-policy.schema.json` — add `boundaryAdapter` to the schema.

## 9. Test plan

Each phase in the implementation plan ends with a verification step. The full test surface:

- `tests/run-all.sh` — must pass after every code-affecting phase. Existing layers (schema, reporter goldens, reporter unit, package, sync, extension) all green.
- New layer: `tests/extensions/python/check-extension.sh` — a Python equivalent of the Spring extension's smoke test. Runs `import-linter` against a known-broken fixture, asserts the JSON output schema, and feeds the JSON into the reporter to assert a `BOUNDARY_VIOLATION` verdict.
- New layer: `tests/reporter/json-violations/` golden fixtures — a few `policy.yaml + changed-files + violations.json → expected-verdict.json` triples.
- Schema validation: `tests/schema/check-schema.py` extended to validate `boundary-violations.schema.json`.
- Package test: `tests/package/check-package.sh` extended to confirm the Python extension makes it into the packaged skill.

## 10. Risks and surprises to watch for

- **import-linter version drift.** The adapter script touches non-public modules. If a 3.x release moves them, the script breaks. Mitigation: pin the supported range in `scaffold.md` and `requirements*.txt`; add a runtime version check in the adapter that fails clearly with the supported range.
- **Editable installs / namespace packages.** import-linter's `root_package` requirement assumes the package is importable. Bootstrap must ensure the consuming repo's package is on `sys.path`. The adapter script does `sys.path.insert(0, os.getcwd())` mirroring import-linter's CLI.
- **Django app discovery is non-trivial.** `INSTALLED_APPS` is the source of truth, not directory layout. v1 uses directory-layout heuristics (the `apps/` directory pattern); a calibration note in `profile.md` flags this and points at INSTALLED_APPS for repos that don't follow the convention.
- **The "models.py = red" Django rule will fire often.** Calibration §6 already calls this out; the bootstrap output will warn and recommend `watch` until the repo has run the tuner.
- **Windows path separators in globs** — the existing reporter uses `fnmatch`; verify Python paths from the demo repo and main repo match cleanly. Already handled in the existing reporter for JVM paths, so likely fine, but worth checking.
- **`pyproject.toml` is dual-purpose** — it's both the build manifest and the import-linter config. Bootstrap edits it carefully (preserve existing `[tool.*]` blocks; only add `[tool.importlinter]` if absent).

## 10b. Surprises caught during implementation

Recorded so the spec stays honest:

- **import-linter `layers` semantics caught us once.** The contract is "higher layers (listed first) may import lower; lower may not import higher." A first draft of the profile listed `[api, application, domain, infrastructure]` thinking infrastructure as the lowest could not import upward — but in hexagonal/clean architectures, infrastructure is precisely the layer that imports domain, so it can't sit below domain in a linear `layers` contract. The fix: list only `[api, application, domain]` in `layers` (where domain is genuinely the bottom), and use a separate `forbidden` contract to enforce the domain → infrastructure/adapters direction. Profile and scaffold updated; the test fixture confirmed the corrected order produces violations as expected.

## 11. Implementation phasing

See the plan. Summary:

1. Reporter generalisation (`json-violations` parser, `--boundary-report` flag, schema).
2. Python extension files + adapter script.
3. Bootstrap-mode awareness (Python detection, shape selection).
4. EXTENSIONS.md correction.
5. Python demo repo (in this repo's `demo-source-python/`, plus a separate `agent-redline-python-demo` GitHub repo on sync).
6. Validation harness extensions.
7. Documentation cleanup pass.

Each phase has a verification gate. `tests/run-all.sh` must pass at the end of each. Demo PRs must show the canonical three states before §11.5 is considered done.

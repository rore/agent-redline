# python — profile

Default zones, boundary rules, and ecosystem-specific options for Python repos. Package names and layer names are placeholders — bootstrap derives the actual ones from the repo. When zones overlap (e.g., a path matches both red and blue), red wins.

Python repos vary more than JVM repos do. This profile enumerates **three shapes**: layered service (with a Django addendum), library/package, and zone-only fallback. Bootstrap inspects the repo, picks one (or proposes two when ambiguous), and the developer confirms.

## Framing — what red means here

Red means **changes that need different review behavior**, not "important code." Most Python code — domain modules, adapter implementations, internal utilities — is on the `watch` list by default. Red is reserved for paths where local correctness is genuinely insufficient: persistence migrations, security/auth code, the public API surface (libraries) or boundary-rule definitions themselves.

## Shape detection (Phase 1)

Inspect the repo. The first signal that fires picks the shape; if two could fire, present both to the developer.

| Signal | Implies shape |
|---|---|
| `manage.py` at root **and** `django` in deps | **Layered service** with Django addendum |
| Web framework dep (`fastapi`, `flask`, `starlette`, `aiohttp`, `sanic`, `litestar`, `falcon`, `bottle`) | **Layered service** |
| Layer directories under the package root: `domain/`, `application/`, `adapters/`, `infrastructure/`, `core/`, `services/`, `usecases/`, `ports/` | **Layered service** |
| `pyproject.toml` `[project]` table, no web-framework dep, package with `__init__.py` re-exports (`__all__` or `from X import Y`) | **Library / package** |
| `apache-airflow`, `prefect`, `dagster`, `luigi` deps; or top-level `dags/`, `pipelines/`, `notebooks/` | **Zone-only fallback** |
| None of the above clearly matches | **Zone-only fallback** (developer can adjust) |

**Layout variants for the layered service shape** (bootstrap derives — not separate shapes):
- **src-layout:** `src/<pkg>/{...}/`. Detected by `src/` directory containing exactly one package.
- **flat layout:** `<pkg>/{...}/` at repo root.

Bootstrap substitutes `<pkg>` in the globs below with the actual package name.

## Shape: layered service

### Default zones

#### Red — genuinely structural surface

```yaml
zones:
  red:
    # Persistence migrations — cover Alembic, framework migrations, yoyo.
    - path: "**/alembic/versions/**.py"
      reason: persistence contract (Alembic)
      checkpoint: persistence-review
    - path: "**/migrations/**.py"
      reason: persistence contract (framework migrations; yoyo; Django)
      checkpoint: persistence-review

    # Outbound port / gateway contracts (when the layout has them)
    - path: "src/<pkg>/**/ports/**"
      reason: architectural boundary contracts (port interfaces)
      checkpoint: architecture-review
    - path: "<pkg>/**/ports/**"
      reason: architectural boundary contracts (flat layout)
      checkpoint: architecture-review
    - path: "src/<pkg>/**/domain/repositories/**"
      reason: domain repository interfaces
      checkpoint: architecture-review
    - path: "<pkg>/**/domain/repositories/**"
      reason: domain repository interfaces (flat layout)
      checkpoint: architecture-review

    # Security / auth code
    - path: "src/<pkg>/**/security/**"
      reason: auth/security-sensitive code
      checkpoint: security-review
    - path: "<pkg>/**/security/**"
      reason: auth/security-sensitive code (flat layout)
      checkpoint: security-review
    - path: "src/<pkg>/**/auth/**"
      reason: auth/security-sensitive code
      checkpoint: security-review
    - path: "<pkg>/**/auth/**"
      reason: auth/security-sensitive code (flat layout)
      checkpoint: security-review

    # Self-protection — the rules that enforce the rules
    - path: ".importlinter"
      reason: dependency-rule definitions
      checkpoint: architecture-review
    - path: "pyproject.toml"
      reason: build / dependency-rule configuration
      checkpoint: architecture-review
    - path: "agent-policy.yaml"
      reason: governance source of truth
      checkpoint: architecture-review
```

**What's deliberately NOT red here** (compared to a maximalist default):

- `**/api/**`, `**/routers/**`, `**/views/**`, `**/controllers/**` — path-touch on an API entry is a poor proxy for "API contract changed"; it fires on bug-fixes, refactors, and dependency-injection changes just as readily. These go on the watch list. The api-review checkpoint fires from path classification only when no API-diff signal is configured.
- `**/domain/**` (other than `repositories/` and `ports/`) — entities and value objects; adding a field is routine.
- `**/adapters/**`, `**/infrastructure/**` — implementations; the boundary contracts protect what matters.
- `models.py` (non-Django) — ORM model classes are touched on most feature PRs in service repos. The Django addendum below treats them differently because Django couples models to migrations explicitly.
- Top-level `requirements*.txt` — dependency changes are tracked via watch, not red.

If your repo treats some of these as genuinely structural (e.g., a `domain/policy/` directory carrying invariants), promote them in Phase 3. The bias is toward narrower defaults; widen on evidence, not on intuition.

#### Blue — agents may work autonomously

```yaml
zones:
  blue:
    - path: "**/tests/**"
      reason: tests
    - path: "**/test_*.py"
      reason: tests
    - path: "**/*_test.py"
      reason: tests
    - path: "**/conftest.py"
      reason: pytest configuration
    - path: "docs/**"
      reason: documentation
    - path: "scripts/**"
      reason: local tooling
    - path: "tools/**"
      reason: local tooling
```

#### Watch — surfaced in the PR comment, not a checkpoint

```yaml
zones:
  watch:
    # API entry points — visible, but the api-review checkpoint fires
    # via api: configuration, not path-touch.
    - path: "src/<pkg>/**/api/**"
    - path: "<pkg>/**/api/**"
    - path: "src/<pkg>/**/routers/**"
    - path: "<pkg>/**/routers/**"
    - path: "src/<pkg>/**/views/**"
    - path: "<pkg>/**/views/**"
    - path: "src/<pkg>/**/controllers/**"
    - path: "<pkg>/**/controllers/**"

    # Domain — important but routine to touch
    - path: "src/<pkg>/**/domain/**"
    - path: "<pkg>/**/domain/**"

    # Adapters / infrastructure — broadly visible
    - path: "src/<pkg>/**/adapters/**"
    - path: "<pkg>/**/adapters/**"
    - path: "src/<pkg>/**/infrastructure/**"
    - path: "<pkg>/**/infrastructure/**"

    # Application layer
    - path: "src/<pkg>/**/application/**"
    - path: "<pkg>/**/application/**"
    - path: "src/<pkg>/**/services/**"
    - path: "<pkg>/**/services/**"
    - path: "src/<pkg>/**/usecases/**"
    - path: "<pkg>/**/usecases/**"

    # Dependencies / config
    - path: "requirements*.txt"
    - path: "Pipfile*"
    - path: "poetry.lock"
    - path: "uv.lock"
```

### Default boundary contracts

import-linter contracts. Bootstrap writes these into `[tool.importlinter]` in `pyproject.toml`, picking only the ones that match the repo's actual layers.

```toml
[tool.importlinter]
root_package = "<pkg>"
exclude_type_checking_imports = true

# 1. Layered architecture: top-down dependencies only.
# import-linter layers go HIGH -> LOW. Higher layers (listed first) may import
# lower ones; lower layers may not import higher. The canonical hexagonal
# stack therefore lists API at the top and domain at the bottom — domain
# must not import application or api code.
[[tool.importlinter.contracts]]
name = "Layered architecture"
type = "layers"
layers = [
    "<pkg>.api",            # alias for routers/views/controllers in your layout
    "<pkg>.application",
    "<pkg>.domain",
]
exhaustive = false

# 2. Hexagonal sidearm: adapters/infrastructure may import domain, but domain
# may not import them. import-linter's layers contract is linear, so the
# domain <-> adapters relationship is enforced separately as a forbidden rule.
[[tool.importlinter.contracts]]
name = "Domain stays free of infrastructure"
type = "forbidden"
source_modules = ["<pkg>.domain"]
forbidden_modules = [
    "<pkg>.infrastructure",
    "<pkg>.adapters",
]

# 3. Domain doesn't import any web/runtime framework.
[[tool.importlinter.contracts]]
name = "Domain stays framework-free"
type = "forbidden"
source_modules = ["<pkg>.domain"]
forbidden_modules = [
    "fastapi", "flask", "django", "starlette", "aiohttp",
    "sqlalchemy", "alembic",
]

# 4. Adapters are independent of each other.
[[tool.importlinter.contracts]]
name = "Adapter independence"
type = "independence"
modules = [
    "<pkg>.adapters.email",
    "<pkg>.adapters.payments",
    "<pkg>.adapters.notifications",
]

# 5. Hygiene: top-level package siblings don't form import cycles.
[[tool.importlinter.contracts]]
name = "Acyclic siblings"
type = "acyclic_siblings"
container = "<pkg>"
```

Adapt during bootstrap:
- Skip layers absent from the repo (e.g., no `application/` → drop from the list).
- Adjust `forbidden_modules` based on what's actually imported (e.g., add `redis`, `kafka-python`, internal SDKs).
- Replace `[email, payments, notifications]` with the actual adapter packages.
- The "Domain stays free of infrastructure" contract uses `<pkg>.infrastructure` and `<pkg>.adapters` by default; substitute the actual top-level paths the repo uses for the adapter side.
- Add stack-specific contracts: see "Ecosystem options" below.

### API contract handling

Pick one based on what the repo has:

**FastAPI / Starlette path-touch (v1 default):**
```yaml
api:
  type: openapi-spec-file
  specPath: "openapi/openapi.json"
  diffMode: structural
  checkpoint: api-review
```
If the repo commits an OpenAPI spec (often generated and committed), use this. The reporter detects api changes by matching the diff against `specPath`.

**No public API surface** (internal-only services):
```yaml
api:
  type: none
```

**Generation-from-code is roadmap.** FastAPI's `app.openapi()`, Flask-RESTX swagger, and DRF + drf-spectacular all support spec generation. v1 of this extension does not wire them in — the gain over path-touch is real but the bootstrap complexity is significant. Roadmap.

### Default PR-size thresholds

```yaml
prRules:
  maxChangedFiles: { warn: 50, fail: 100 }
  maxLinesChanged: { warn: 1000, fail: 2000 }
```

Same defaults as the Spring extension; calibrated for service-shaped repos.

### Django addendum

If `manage.py` exists at the repo root **and** `django` is in deps, layered-service zones are augmented (not replaced) with these additions.

#### Additional red zones

```yaml
zones:
  red:
    # Settings — auth, middleware, INSTALLED_APPS, secrets, ALLOWED_HOSTS.
    - path: "**/settings.py"
      reason: Django settings (auth, middleware, secrets)
      checkpoint: security-review
    - path: "**/settings/*.py"
      reason: Django settings module
      checkpoint: security-review

    # URL routing — explicit HTTP surface in Django, unlike FastAPI's decorators.
    - path: "**/urls.py"
      reason: Django URL routing (HTTP surface)
      checkpoint: api-review

    # Models — Django couples models to migrations; a model change without a
    # corresponding migration is a bug. NOTE: this rule fires often. Bootstrap
    # surfaces a calibration warning when generating the policy and recommends
    # demoting to watch until the repo has run the tuner.
    - path: "**/<app>/models.py"
      reason: Django model definitions (paired with migrations)
      checkpoint: persistence-review
```

#### Additional watch entries

```yaml
zones:
  watch:
    - path: "**/admin.py"
      reason: Django admin registrations (data exposure surface)
    - path: "**/management/commands/**.py"
      reason: Django management commands (operational scripts)

    # DRF — only when djangorestframework is in deps.
    - path: "**/serializers.py"
      reason: DRF serializer contracts
    - path: "**/viewsets.py"
      reason: DRF viewsets
```

#### Additional boundary contracts

```toml
# Cross-app independence: sibling Django apps don't import each other's internals.
# Apps must communicate via well-defined public seams, not models / views.
[[tool.importlinter.contracts]]
name = "Cross-app independence"
type = "independence"
modules = [
    "<project>.apps.orders",
    "<project>.apps.billing",
    "<project>.apps.notifications",
]

# Views in app A must not import models in app B.
[[tool.importlinter.contracts]]
name = "App views don't reach into other apps' models"
type = "forbidden"
source_modules = ["<project>.apps.*.views", "<project>.apps.*.viewsets"]
forbidden_modules = ["<project>.apps.*.models"]
ignore_imports = [
    # Same-app self-imports are kept; ignored entries below come from bootstrap.
]
```

Adapt during bootstrap:
- Apps directory is at `apps/` or top-level (`<project>/<app>/`). Bootstrap inspects to determine where they live.
- `INSTALLED_APPS` in `settings.py` is the source of truth; directory layout is a heuristic. If the directory layout doesn't match `INSTALLED_APPS`, bootstrap surfaces this and asks the developer.
- DRF: only add the serializer/viewset entries if `djangorestframework` is in deps.

#### Django gotchas

- **`models.py` red zone fires often.** First-pass calibration warning; consider demoting to watch and binding only after running the tuner.
- **Migration files are auto-generated.** Don't hand-edit unless the change is intentional. `RunPython` migrations contain arbitrary code and are higher-risk than schema-only migrations.
- **Custom user model.** `AUTH_USER_MODEL` and the model class itself are architecturally one-way after launch. Treat as security-review even when not flagged by paths.
- **`drf-spectacular` integration is roadmap.** v1 falls back to `urls.py` path-touch for api-review.

## Shape: library / package

### Detection criteria

- `pyproject.toml` with a `[project]`, `[tool.poetry]`, or `[tool.setuptools]` block.
- No web framework dep.
- A top-level package with `__init__.py`, often containing `__all__` or `from .X import Y` re-exports.
- Test directory exists (`tests/`).

### Default zones

#### Red — public API surface

```yaml
zones:
  red:
    # The package's public surface — re-exports define what's stable.
    - path: "src/<pkg>/__init__.py"
      reason: public API re-exports
      checkpoint: api-review
    - path: "<pkg>/__init__.py"
      reason: public API re-exports (flat layout)
      checkpoint: api-review

    # Type stubs are part of the published contract.
    - path: "src/<pkg>/**/*.pyi"
      reason: published type stubs
      checkpoint: api-review
    - path: "<pkg>/**/*.pyi"
      reason: published type stubs (flat layout)
      checkpoint: api-review

    # py.typed marker controls whether type stubs are honored downstream.
    - path: "**/<pkg>/py.typed"
      reason: PEP 561 type-information marker
      checkpoint: api-review

    # Build / packaging metadata: changes affect what users install.
    - path: "pyproject.toml"
      reason: build configuration and dependency-rule definitions
      checkpoint: architecture-review

    # Self-protection
    - path: ".importlinter"
      reason: dependency-rule definitions
      checkpoint: architecture-review
    - path: "agent-policy.yaml"
      reason: governance source of truth
      checkpoint: architecture-review
```

#### Watch

```yaml
zones:
  watch:
    # All non-test, non-dunder modules are watch-list — they may eventually
    # be imported by users (Python convention: "no leading underscore = public").
    - path: "src/<pkg>/**/[!_]*.py"
    - path: "<pkg>/**/[!_]*.py"
    - path: "CHANGELOG.md"
    - path: "README.md"
```

#### Blue

```yaml
zones:
  blue:
    - path: "tests/**"
      reason: tests
    - path: "**/test_*.py"
      reason: tests
    - path: "docs/**"
      reason: documentation
```

### Default boundary contracts

```toml
[tool.importlinter]
root_package = "<pkg>"

# 1. Private modules (leading underscore) only imported by their own subtree.
[[tool.importlinter.contracts]]
name = "Private modules stay internal"
type = "protected"
protected_modules = ["<pkg>._internals", "<pkg>._compat", "<pkg>._utils"]
allowed_importers = ["<pkg>"]   # bootstrap fills in the actual subtree

# 2. Acyclic siblings: internal modules don't form cycles.
[[tool.importlinter.contracts]]
name = "Acyclic siblings"
type = "acyclic_siblings"
container = "<pkg>"
```

Adapt during bootstrap: only generate the `protected` contract for modules that actually have leading underscores; don't fabricate.

### Default PR-size thresholds

```yaml
prRules:
  maxChangedFiles: { warn: 20, fail: 50 }
  maxLinesChanged: { warn: 500, fail: 1000 }
```

Tighter than service-shaped — libraries usually receive smaller, more focused PRs.

## Shape: zone-only fallback

For Python repos where boundary enforcement adds little value: data pipelines, notebook-heavy ML repos, monorepos with mixed shapes, scripts-and-glue.

### Default zones

```yaml
zones:
  red:
    # Persistence (when present)
    - path: "**/migrations/**.py"
      reason: persistence contract
      checkpoint: persistence-review
    - path: "**/alembic/versions/**.py"
      reason: persistence contract (Alembic)
      checkpoint: persistence-review

    # Pipeline DAGs
    - path: "dags/**"
      reason: pipeline definitions
      checkpoint: pipeline-review
    - path: "pipelines/**"
      reason: pipeline definitions
      checkpoint: pipeline-review

    # Self-protection
    - path: "agent-policy.yaml"
      reason: governance source of truth
      checkpoint: architecture-review

  watch:
    - path: "**/*.py"
    - path: "notebooks/**"
    - path: "requirements*.txt"

  blue:
    - path: "tests/**"
    - path: "docs/**"
```

### Adapter

```yaml
boundaryAdapter:
  outputFormat: none
```

The reporter skips boundary parsing. Zones, persistence/security signals, and PR-size checks still run.

### Default PR-size thresholds

```yaml
prRules:
  maxChangedFiles: { warn: 30, fail: 80 }
  maxLinesChanged: { warn: 800, fail: 1500 }
```

## Ecosystem options

Ask the developer about these in Phase 3 and include if relevant.

### Multi-database services

If the service has multiple databases / persistence layers:

```yaml
persistence:
  migrationPaths:
    - "**/alembic/versions/**.py"
    - "**/<pkg>/persistence/migrations/**.py"
    - "**/db/migrations/**.py"
  checkpoint: persistence-review
```

### Third-party SDK contracts

If the repo wraps a vendor SDK whose contract is part of the service surface:

```yaml
zones:
  red:
    - path: "src/<pkg>/adapters/<vendor>/dto/**"
      reason: third-party API contract surface
      checkpoint: api-review
```

### Tasks / queues as a public-ish surface

Celery tasks, RQ jobs, FastAPI background tasks: the function signature is a contract for callers. If the repo treats tasks as such:

```yaml
zones:
  watch:
    - path: "**/<pkg>/tasks/**"
    - path: "**/<pkg>/jobs/**"
```

## Build / test commands

| Action | Command |
|---|---|
| Run all tests | `pytest` |
| Run boundary check | `python scripts/run-import-linter.py --out build/import-linter-report.json` |
| Run local agent-redline check | `bash scripts/agent-redline-check.sh` |

## Gotchas

- **Dynamic imports bypass contracts.** `importlib.import_module(name)` and `__import__(name)` are invisible to the static graph. Agents must NOT use them to work around boundary rules. Operating-mode notes flag this.
- **`if TYPE_CHECKING:` imports.** import-linter's `exclude_type_checking_imports = true` setting (top-level `[tool.importlinter]` option) suppresses these. The default profile sets it; layered architectures often need cross-layer type hints that aren't real runtime imports.
- **Namespace packages.** When the repo uses [PEP 420 namespace packages](https://docs.python.org/3/glossary.html#term-namespace-package), set `root_package` to the portion (e.g. `mynamespace.foo`) instead of the namespace. Bootstrap detects this from `pyproject.toml` `[tool.setuptools.packages.find]` configuration.
- **src-layout requires the package to be importable.** import-linter reads packages, not files. The bootstrap-generated CI snippet runs `pip install -e .` so the package is importable; in `flat` layouts the working directory itself is on `sys.path`.
- **`__init__.py` matters in layered services.** Layer directories must be packages (i.e., have `__init__.py`, even if empty), or the import-linter `layers` contract won't see them. Bootstrap checks and warns if a layer directory lacks one.
- **Editable installs and tests.** When the project is installed editable (`pip install -e .`), tests and contracts both see the source tree. When installed regular, they see the installed copy. Use editable install in CI to avoid the divergence.
- **`requirements.txt` vs `pyproject.toml` deps.** Both are valid; bootstrap reads either. If both exist (common in older projects), `pyproject.toml`'s `[project.dependencies]` is authoritative for the package's own deps; `requirements.txt` is the resolved/pinned environment.
- **Django `INSTALLED_APPS` is authoritative.** The Django addendum's directory-layout heuristics are convenient but secondary; if directory and `INSTALLED_APPS` disagree, the latter wins. Bootstrap surfaces the disagreement.

## Pointers

- import-linter docs: <https://import-linter.readthedocs.io/>
- import-linter contracts: <https://import-linter.readthedocs.io/en/stable/contract_types/index.html>
- grimp (the underlying graph builder): <https://grimp.readthedocs.io/>

# python — operating-mode notes

Python-specific behavior in addition to the core operating-mode rules.

## Treat as red even if the policy doesn't say so

These come up in Python services often enough that the agent should be cautious regardless of zone classification:

- **Adding `__init__.py` re-exports in a library.** Adding `from .foo import Bar` to `<pkg>/__init__.py` extends the public API. Treat as `api-review` even when `__init__.py` isn't in red zones for this shape.
- **Removing or renaming public attributes.** Anything imported by name from another module / package is a contract; renaming or removing it is a breaking change. Even on internal modules — verify no external callers before assuming local.
- **`async`/`await` boundary changes.** Adding or removing `async` on a public function changes its call sites. Treat as `architecture-review` if the function is used outside its module.
- **Changes to `pyproject.toml`'s `[project] dependencies` or `[project.optional-dependencies]`.** Even when the file isn't red. Adding/removing a dependency affects what users install; bumping a major version may break callers.
- **Changes to a custom `__init_subclass__`, metaclass, or descriptor.** Globally consequential; tests rarely catch behavior changes here.

## Dynamic imports MUST NOT be used to work around contracts

`import-linter` builds a static import graph. `importlib.import_module(name)`, `__import__(name)`, and exec'd `import` statements are **invisible** to it. Using them to import across a layer that the contract forbids is **structural drift in disguise** — the contract still passes, but the architecture is broken.

If a violation is justified, add an explicit `ignore_imports` entry to the offending contract in `pyproject.toml`. That puts the exception in the dependency-rule definitions file, which is in red zones — so adding the exception requires `architecture-review`. The cost is correct; routing around via `importlib` is not.

The agent must NOT propose `importlib.import_module(...)` to satisfy a layered architecture contract. If the natural call requires crossing a forbidden boundary, fix the structure or escalate.

## TYPE_CHECKING imports

`from typing import TYPE_CHECKING` and `if TYPE_CHECKING:` blocks are common in layered Python — they let a domain module reference an infrastructure type for type hints without a runtime import. By default, the profile sets `exclude_type_checking_imports = true` in `[tool.importlinter]`, so these don't trigger contract violations.

If a TYPE_CHECKING import is the only way to satisfy a type, that's fine. If the same module is imported BOTH at module-top AND under TYPE_CHECKING, that's a smell — the module-top import is the real boundary crossing.

## Generated sources

If the build generates Python files (Pydantic models from JSON schema, Strawberry GraphQL types, gRPC stubs from `.proto`, OpenAPI clients), generated directories should be in `excludes:` of the policy. If you find generated sources that aren't excluded, surface in the PR description and suggest a policy update.

## Multi-tenant / multi-database persistence

If `persistence.notes` mentions multi-tenant migrations, the `persistence-review` checkpoint requires a rollout plan, not just a schema diff. Ask the developer about per-tenant impact when proposing a migration. Same for multi-database routers (Django `DATABASE_ROUTERS`, SQLAlchemy multi-bind setups) — touching the routing logic is structural.

## `requirements.txt` vs `pyproject.toml`

Both are common. `pyproject.toml`'s `[project.dependencies]` (or `[tool.poetry.dependencies]`) is the authoritative source for the package's own deps. `requirements.txt` (and lock files: `poetry.lock`, `uv.lock`, `requirements.lock`) describes the resolved environment.

When adding a dependency:
- Add to `pyproject.toml`.
- Regenerate the lock file via the project's chosen tool (`poetry lock`, `pip-compile`, `uv lock`).
- Both files end up changed; both are watch-list. The lock file diff is large and noisy — that's fine.

When removing a dependency, remove from `pyproject.toml` AND regenerate the lock. A `pyproject.toml` removal without a corresponding lock update is a bug.

## Django specifics (when the Django addendum applies)

- **`makemigrations` discipline.** A model change without a corresponding migration file in the same PR is a bug. The reporter doesn't enforce this — calibration data permitting, future iterations may. For now, agents should always run `python manage.py makemigrations` after touching `models.py`.
- **`RunPython` migrations** contain arbitrary code and are higher-risk than schema-only migrations. Treat as `architecture-review` in addition to `persistence-review`.
- **Custom user model.** `AUTH_USER_MODEL` and the model class itself are architecturally one-way after launch. Treat as security-review even when not flagged by paths.
- **Settings overrides at deploy time.** Production environment variables override `settings.py` values via `os.environ`. If a settings edit changes a default that has a corresponding env var in production, treat as `ops-review` even if the change looks small.

## FastAPI specifics

- **`Depends(...)` injection changes.** Adding a `Depends(...)` to a router function effectively changes its contract; downstream callers (sub-dependencies) inherit the dependency. Treat as `api-review` for public router files.
- **`Pydantic` model field changes.** Adding/removing fields on a Pydantic response model is an API contract change. The watch list flags it; the api-review checkpoint should fire when the spec is configured.

## Async-sync boundaries

- **Calling async from sync.** Requires an event loop runner (`asyncio.run`, etc.). Mixing async DB drivers (asyncpg) into sync codepaths or vice-versa is a real footgun; treat changes that cross this boundary as `architecture-review`.
- **`asyncio.run_in_executor`** for offloading sync work to threads is fine. Routing a coroutine through it is not.

## Naming conventions

- **Leading underscore = private.** `_foo.py`, `_helpers/`, `MyClass._method` — these are not part of any contract. The library shape's `protected` import-linter contract enforces this; service shapes don't, but the convention still holds.
- **Dunder names** (`__foo__`) are reserved by Python. Don't define new ones; use them only when the data model calls for it (`__eq__`, `__hash__`, etc.).
- **`_internals/`, `_compat/`** are conventional names for "this is implementation detail; don't import." Add to `protected_modules` in the library shape.

# spring-archunit — profile

Default zones, boundary rules, and ecosystem-specific options. Package names are placeholders — bootstrap derives the actual ones from the repo. When zones overlap (e.g., a path matches both red and blue), red wins.

## Default zones

### Red

```yaml
zones:
  red:
    - path: src/main/java/**/domain/**
      reason: domain model and invariants
      checkpoint: architecture-review

    - path: src/main/java/**/application/**/port/**
      reason: architectural boundary contracts (port interfaces)
      checkpoint: architecture-review

    - path: src/main/java/**/port/**
      reason: architectural boundary contracts (when ports live at top level)
      checkpoint: architecture-review

    - path: src/main/java/**/*Controller.java
      reason: public API contract surface (OpenAPI generated from these)
      checkpoint: api-review

    - path: src/main/java/**/security/**
      reason: auth/security-sensitive code
      checkpoint: security-review

    - path: src/main/java/**/auth/**
      reason: auth/security-sensitive code
      checkpoint: security-review

    - path: src/main/java/**/jwt/**
      reason: token handling
      checkpoint: security-review

    - path: src/main/resources/db/migration/**
      reason: persistence contract
      checkpoint: persistence-review

    - path: src/main/resources/application*.yml
      reason: runtime configuration
      checkpoint: ops-review

    - path: src/main/resources/application*.properties
      reason: runtime configuration
      checkpoint: ops-review

    - path: src/test/java/**/architecture/**
      reason: dependency-rule definitions; weakening these requires explicit checkpoint
      checkpoint: architecture-review

    - path: terraform/**
      reason: infrastructure
      checkpoint: ops-review
```

By default only `application/**/port/**` is red, not all of `application/**`. Repos that prefer stricter discipline can promote `application/**` to red explicitly during Phase 3.

### Blue

```yaml
zones:
  blue:
    - path: src/test/**
      reason: tests and verification (excluding architecture/**)

    - path: docs/**
      reason: documentation

    - path: scripts/**
      reason: local tooling

    - path: tools/**
      reason: local tooling

    - path: <api-test-collections>/**
      reason: API test collections (e.g., Bruno, Postman, Insomnia, REST Client)

    - path: src/main/java/**/adapter/**/mapper/**
      reason: isolated adapter mapping

    - path: src/main/java/**/adapter/**/persistence/**/dto/**
      reason: DB row / persistence-internal DTOs (not API surface)
```

Adapter DTOs in general (other than persistence-internal ones) are gray-watch, not blue. Promote a specific subpath to blue only when the developer confirms it's internal-only.

### Gray watch

```yaml
zones:
  grayWatch:
    - path: src/main/java/**/application/**/*Service.java
      reason: application services orchestrate flows
    - path: src/main/java/**/application/**/*UseCase.java
      reason: application use cases orchestrate flows
    - path: src/main/java/**/adapter/**/dto/**
      reason: adapter DTOs may be vendor contract surface
    - path: src/main/java/**/*Dto.java
      reason: shared DTOs may appear in API responses
    - path: src/main/java/**/*Configuration.java
      reason: Spring configuration affects bean wiring globally
    - path: src/main/java/**/*Filter.java
      reason: Spring filters affect request lifecycle
    - path: src/main/java/**/*Interceptor.java
      reason: Spring interceptors affect request lifecycle
```

## Default boundary rules

```yaml
boundaries:
  - id: domain-must-not-import-adapters
    description: Domain layer must not depend on adapter implementations
    from: src/main/java/**/domain/**
    forbidImports:
      - src/main/java/**/adapter/**
    severity: error

  - id: application-must-not-import-concrete-infra
    description: Application layer talks to ports, not concrete adapters
    from: src/main/java/**/application/**
    forbidImports:
      - src/main/java/**/adapter/**/persistence/**
      - src/main/java/**/adapter/**/client/**
    severity: error

  - id: controllers-must-not-access-repositories
    description: Controllers go through application services, not directly to data
    from: src/main/java/**/controller/**
    forbidImports:
      - src/main/java/**/repository/**
      - src/main/java/**/adapter/**/persistence/**
    severity: error
```

Add more rules during bootstrap based on what the repo has (e.g., "core must not import customer customization", "domain must not import vendor adapter types"; see ecosystem options below).

## API contract handling

If a committed OpenAPI spec exists:

```yaml
api:
  type: openapi-spec-file
  specPath: openapi/api.yaml
  diffMode: structural
  checkpoint: api-review
```

The reporter detects api changes by matching the diff against `specPath`. If you don't have a committed spec, controllers are red-zone files anyway and trigger `architecture-review` via path classification.

Or if no public API surface:

```yaml
api:
  type: none
```

## Ecosystem options

Ask the developer about these in Phase 3 and include if relevant.

### Multi-tenant persistence

```yaml
persistence:
  migrationPaths:
    - src/main/resources/db/migration/**
    - src/main/resources/db/tenant-migration/**
  checkpoint: persistence-review
  notes: |
    Multi-tenant migrations apply per-tenant. Persistence-review checkpoint
    must include a rollout plan, not just a schema diff.
```

### Third-party adapter contracts

```yaml
zones:
  red:
    - path: src/main/java/**/adapter/<vendor>/**/dto/**
      reason: third-party API contract surface
      checkpoint: api-review
    - path: src/main/java/**/adapter/<vendor>/**/request/**
      reason: third-party API contract surface
      checkpoint: api-review
    - path: src/main/java/**/adapter/<vendor>/**/response/**
      reason: third-party API contract surface
      checkpoint: api-review

boundaries:
  - id: domain-must-not-import-vendor-types
    from: src/main/java/**/domain/**
    forbidImports:
      - src/main/java/**/adapter/<vendor>/**
```

### Customer-specific code that must not leak into core

```yaml
zones:
  red:
    - path: src/main/java/**/core/**
      reason: shared core; customer-specific code must not leak in
      checkpoint: architecture-review

boundaries:
  - id: core-must-not-import-customer-customization
    from: src/main/java/**/core/**
    forbidImports:
      - src/main/java/**/customer/**
    severity: error
```

## Build / test commands

| Action | Command |
|---|---|
| Run all tests | `./gradlew test` |
| Run only architecture tests | `./gradlew test --tests '*ArchitectureTest'` |
| Run local agent-redline check | `./scripts/agent-redline-check.sh` |
| Generate OpenAPI (if plugin present) | `./gradlew generateOpenApi` |

## Ecosystem-specific behavior

- **`@RestController` on internal-only endpoints.** Ask the developer which controllers are internal-only and exclude them from `api-review` triggering (`excludes:` in the policy).
- **Generated source directories.** If the build generates DTOs (OpenAPI codegen, JOOQ, MapStruct, etc.), add the generated directory to `excludes:` so it's not classified at all.
- **ArchUnit `DoNotIncludeTests` option.** When generating the architecture test class, verify this option is set so test classes aren't analyzed for boundary violations.
- **`application.yml` env-var overrides.** Runtime config zone covers the YAML; environment variable overrides operate at deploy time and are out of scope for the policy.

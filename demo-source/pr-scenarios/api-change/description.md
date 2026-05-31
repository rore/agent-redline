# API change PR

Adds a new endpoint to `OrderController`:

```
POST /orders/{id}/cancel
```

This is the canonical demonstration of `api.type: openapi-from-controllers`:

1. The controller is in the red zone (`*Controller.java`), so the path
   classification fires `api-review` immediately.
2. The CI workflow runs `./gradlew generateOpenApiDocs` at the PR's base
   SHA and at its head SHA, producing two OpenAPI specs.
3. The agent-redline reporter consumes both specs and computes a
   *structural diff* — added paths, removed paths, modified operations.
   That diff appears in the PR comment alongside the verdict.

The PR has the `api-reviewed` label applied (or a CODEOWNER approval)
satisfying the api-review checkpoint, so the PR can merge once CI is
green.

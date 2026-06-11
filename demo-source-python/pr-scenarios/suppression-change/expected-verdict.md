# Expected verdict (to be filled in live during Phase 9b)

When the diff lands without a label:

- Verdict: RED (red-zone file
  `src/orders/domain/repositories/orders_repository.py` is touched and
  carries an added suppression marker)
- Suppressions: 1 (`# noqa: import-linter` inline comment, file path
  `src/orders/domain/repositories/orders_repository.py`, zone red)
- Required checkpoint: `architecture-review` — reason:
  "Suppression marker on guarded surface: ..."
- Exit code: 2 (binding default for suppression once the policy flips
  `suppression: binding`; under the demo's current shadow default this
  is exit 1 / warn — verified live in Phase 9b)
- CI: red badge

After applying the `architecture-reviewed` label:
- Same verdict, but the architecture-review checkpoint flips to
  `[x]` satisfied
- Exit code: 0
- CI: green badge

Phase 9b will replace this stub with the actual sticky-comment text from
the live PR.

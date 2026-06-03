# Extensions

A language extension binds the agent-redline core to a specific stack. It is the only sanctioned way to add support for a new language, framework, or boundary-rule backend.

If you want agent-redline to work with a stack that doesn't have an extension yet, this is the doc.

## What an extension is

A folder with five files (plus an optional `scripts/` subdirectory):

```
extensions/<name>/
├── README.md          # what stack this is for, when to pick it
├── profile.md         # zones, boundaries, gotchas (the agent reads this in bootstrap)
├── scaffold.md        # how the agent generates backend artifacts + CI snippets
├── operating.md       # (optional) stack-specific operating-mode notes
├── adapter.yaml       # tells the reporter where backend output is and what format
└── scripts/           # (optional) adapter scripts when the backend has no
                       # machine-readable output — see "Backends without
                       # machine-readable output" below
```

Four markdown files, one small YAML file, and — only when the backend forces it — a focused adapter script. No manifest, no version metadata, no plugin loader.

## What an extension owns

- **Stack-specific zones.** Where domain/application/adapter (or whatever this stack calls them) live, by path glob.
- **Recommended boundary rules.** What dependencies should not exist between layers in this stack.
- **The boundary-rule backend choice.** Which tool enforces the rules (ArchUnit, dependency-cruiser, import-linter, Semgrep, etc.).
- **Scaffolding instructions.** How the agent generates the backend's config/test files, wires them into the build, and adds the CI step.
- **The adapter config.** Where the backend writes its output and what format it's in, so the reporter can read violations.
- **Stack-specific gotchas.** Things the agent should know about this ecosystem (e.g., generated sources, runtime config quirks).

## What an extension does NOT own

- The vocabulary (red/blue/gray zones, the `watch` additive tag, boundary rules, checkpoints, modes) — fixed in the core.
- The policy schema — fixed in the core. Extensions fill in stack-specific values; they don't add new top-level fields.
- The verdict format (PR comment, exit codes, JSON output) — fixed in the core.
- The bootstrap and operating loops — fixed in the core. Extensions can add stack-specific notes the agent reads, but they don't change the loop structure.
- Reporter logic, zone classification, checkpoint computation. Adapter scripts (where present) are pure converters from a backend's native output format to one of the reporter's supported formats. They MUST NOT replicate reporter behavior.

## Building a new extension — practical steps

1. **Copy an existing extension to `extensions/<your-stack>/`.** Use `extensions/jvm-archunit/` as the JUnit-XML reference, or `extensions/python/` as the JSON-violations + adapter-script reference. Pick whichever is closer to your backend.
2. **Rewrite `README.md`** — what stack this is for, when to pick it.
3. **Rewrite `profile.md`** — zones (red/blue) and watch-list entries for your stack, recommended boundary rules, API contract location, persistence paths, security conventions, gotchas. Keep the same structure; replace stack-specific paths with yours.
4. **Rewrite `scaffold.md`** — how the agent installs the boundary-rule backend (`pip install`, `npm install`, `cargo add`, etc.), generates the config/test files, and adds the CI step.
5. **Update `adapter.yaml`** — set `outputFormat` to `junit-xml`, `json-violations`, or `none`, and `outputPath` to where your backend writes its output. If your backend doesn't natively produce a supported format, either add a conversion step in `scaffold.md` or ship a `scripts/run-<backend>.py` adapter (see "Backends without machine-readable output").
6. **Optional: `operating.md`** — only add this if there are stack-specific operating-mode rules the agent needs beyond the core ones. Most extensions don't need it.

That's it. No manifest, no registration, no versioning ceremony.

## Recommended backends per ecosystem

This is the practical starting list for anyone building an extension:

| Ecosystem | Recommended backend | Native output | Notes |
|---|---|---|---|
| JVM (Java, Kotlin) | **ArchUnit** | junit-xml | Open source, JUnit-friendly, bytecode-aware. Reference extension (`jvm-archunit`); Spring Boot covered by the Spring addendum. |
| Python | **import-linter** | (none — adapter script) | Designed for layer/contract import rules. Reference extension. |
| Node / TypeScript | **dependency-cruiser** | json-violations (via converter) | Built specifically for Node forbid-import rules. |
| Go | **go-arch-lint** | (depends on tool) | Closest equivalent to ArchUnit in the Go ecosystem. |
| Rust | **cargo-deny** (for crate deps) + **Clippy custom lints** | (depends on tool) | Less mature ecosystem; Semgrep is a fallback. |
| Multi-language / generic | **Semgrep** | json (convert to json-violations) | Pattern-based, multi-language. Less precise than language-native tools but works as a fallback. |

These are recommendations. An extension can use any backend that produces violations the reporter can read.

## The adapter config

`adapter.yaml` is the only structured file in an extension. Its job is to tell the reporter where the backend writes its output and what format it's in.

Schema:

```yaml
boundaryAdapter:
  outputFormat: junit-xml | json-violations | none
  outputPath: <path glob>          # required when outputFormat != 'none'

  # Optional: how to identify boundary-rule violations vs other test failures.
  # Only meaningful for outputFormat: junit-xml. Use when the backend mixes
  # architecture-rule failures with unrelated failures (e.g., regular unit tests
  # in the same JUnit XML).
  violationFilter:
    matchClassName: <substring or regex>
    matchTestNamePattern: <regex>
```

Supported `outputFormat` values:

- **`junit-xml`** — JUnit XML. Native format for ArchUnit and most JVM-style architecture testers. The reporter parses standard `<testsuite>/<testcase>/<failure>` shapes.
- **`json-violations`** — a small JSON document listing concrete violations. Schema at `core/schema/boundary-violations.schema.json`. Use this when the backend lacks JUnit XML output and an adapter script is needed (see next section).
- **`none`** — the extension declares no boundary backend. The reporter skips the boundary leg entirely; zone classification, persistence/security/API signals, and PR-size checks still run. Useful for repos where boundary enforcement adds little value (data pipelines, notebook-heavy ML).

The reporter dispatches on `outputFormat`. When the consuming repo's `agent-policy.yaml` has a `boundaryAdapter:` block (bootstrap copies the extension's `adapter.yaml` into the policy), the reporter reads it automatically; no extra CLI flag is needed.

(Other formats — SARIF, native JSON-from-tools — are roadmap. They land when an extension genuinely needs them.)

If your backend doesn't natively produce one of the supported formats, two paths:

1. **Convert in the build.** `scaffold.md` instructs the consuming repo's CI to convert (most static-analysis tools have community converters or multiple output options).
2. **Ship an adapter script** in `extensions/<name>/scripts/`. See the next section for the contract.

## Backends without machine-readable output

Some boundary-rule backends only produce human-readable text. The reference example is Python's `import-linter`: its CLI emits Rich-formatted text with no `--format` flag, and its public Python API exposes only a boolean pass/fail.

For these cases, an extension MAY ship a focused adapter script under `extensions/<name>/scripts/`. The script's only job is to run the backend and emit `boundary-violations.json` matching `core/schema/boundary-violations.schema.json`.

Constraints on adapter scripts:

- **Single responsibility:** run the backend, walk its native results, write the JSON. Nothing else.
- **MUST NOT** replicate reporter logic, classify zones, compute checkpoints, or read `agent-policy.yaml`.
- **MUST** be runnable standalone for testing, with a clear `--help`.
- **MUST** pin the backend's supported version range when it depends on internal/non-public APIs (for `import-linter`, the reference adapter pins `>=2.0,<3`).
- **SHOULD** emit clear errors pointing at the supported version range when the backend isn't installed or has an incompatible version.
- The script is copied verbatim by `package-skill.sh` into the packaged skill; it lives alongside the markdown and is invoked from the extension's CI snippet.

`extensions/python/scripts/run-import-linter.py` is the reference implementation.

The constraint that extensions are otherwise "markdown plus one small YAML file" still holds for every other purpose — these scripts exist solely because some backends force them.

## What if my stack has no good backend?

Two honest paths:

1. **Use Semgrep with a small set of forbid-import rules.** It works for many stacks; convert its output to `json-violations` in a small adapter script (see "Backends without machine-readable output").
2. **Skip boundary enforcement for now.** Use only zone classification and the agent-side discipline. Lighter governance, fewer guarantees, but still useful. The extension's `adapter.yaml` declares `outputFormat: none`, and the reporter only reports on zones, API/schema/security paths, and PR size.

The second path is fine. agent-redline is more useful with a backend, but it's still useful without one. The adapter file in that case looks like:

```yaml
boundaryAdapter:
  outputFormat: none
```

And the reporter skips the boundary-violation section of the verdict.

## Distribution

For v0.1 there's no central registry. Extensions live in:

- This repo (`extensions/jvm-archunit/` and `extensions/python/` are the references)
- A separate repo or directory you publish (point users at it; they install it alongside agent-redline as another skill)
- A consuming repo's local copy (vendored)

If extensions become numerous, a registry or convention can come later. Premature now.

## Contributing an extension back

If you build an extension for a common stack and want it shared, open a PR adding it under `extensions/`. The bar:

- Follows the file shape (markdown + `adapter.yaml`, plus an optional `scripts/` only when the backend has no machine-readable output)
- The backend has at least one mature open-source implementation
- `adapter.yaml` declares a supported output format, or `scripts/` ships a focused adapter that produces one
- `profile.md` is honest about gotchas, not a happy-path-only document

We don't promise to merge every contributed extension, but the door is open.

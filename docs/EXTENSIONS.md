# Extensions

A language extension binds the agent-redline core to a specific stack. It is the only sanctioned way to add support for a new language, framework, or boundary-rule backend.

If you want agent-redline to work with a stack that doesn't have an extension yet, this is the doc.

## What an extension is

A folder with five files. That's the entire shape:

```
extensions/<name>/
├── README.md          # what stack this is for, when to pick it
├── profile.md         # zones, boundaries, gotchas (the agent reads this in bootstrap)
├── scaffold.md        # how the agent generates backend artifacts + CI snippets
├── operating.md       # (optional) stack-specific operating-mode notes
└── adapter.yaml       # tells the reporter where backend output is and what format
```

Four markdown files plus one small YAML file. No manifest, no version metadata, no plugin loader.

## What an extension owns

- **Stack-specific zones.** Where domain/application/adapter (or whatever this stack calls them) live, by path glob.
- **Recommended boundary rules.** What dependencies should not exist between layers in this stack.
- **The boundary-rule backend choice.** Which tool enforces the rules (ArchUnit, dependency-cruiser, import-linter, Semgrep, etc.).
- **Scaffolding instructions.** How the agent generates the backend's config/test files, wires them into the build, and adds the CI step.
- **The adapter config.** Where the backend writes its output and what format it's in, so the reporter can read violations.
- **Stack-specific gotchas.** Things the agent should know about this ecosystem (e.g., generated sources, runtime config quirks).

## What an extension does NOT own

- The vocabulary (red/blue/gray, zones, boundary rules, checkpoints, modes) — fixed in the core.
- The policy schema — fixed in the core. Extensions fill in stack-specific values; they don't add new top-level fields.
- The verdict format (PR comment, exit codes, JSON output) — fixed in the core.
- The bootstrap and operating loops — fixed in the core. Extensions can add stack-specific notes the agent reads, but they don't change the loop structure.
- Custom code execution. Extensions are markdown plus one small YAML file. No scripts, no parsers, no plugins. If the backend's output isn't in a format the reporter natively reads, the extension's `scaffold.md` instructs the build to convert.

## Building a new extension — practical steps

1. **Copy `extensions/spring-archunit/` to `extensions/<your-stack>/`.** That's your starting point.
2. **Rewrite `README.md`** — what stack this is for, when to pick it.
3. **Rewrite `profile.md`** — zones (red/blue/gray) for your stack, recommended boundary rules, API contract location, persistence paths, security conventions, gotchas. Keep the same structure; replace Spring-specific paths with yours.
4. **Rewrite `scaffold.md`** — how the agent installs the boundary-rule backend (`pip install`, `npm install`, `cargo add`, etc.), generates the config/test files, and adds the CI step.
5. **Update `adapter.yaml`** — the path where your backend writes its output and the format. Use `junit-xml` if your backend produces JUnit XML; otherwise add a conversion step in `scaffold.md` to produce JUnit XML. (SARIF and JSON-violations are roadmap formats; for v0.1, JUnit XML is the only natively-supported format.)
6. **Optional: `operating.md`** — only add this if there are stack-specific operating-mode rules the agent needs beyond the core ones. Most extensions don't need it.

That's it. No manifest, no registration, no versioning ceremony.

## Recommended backends per ecosystem

This is the practical starting list for anyone building an extension:

| Ecosystem | Recommended backend | Notes |
|---|---|---|
| JVM (Java, Kotlin) — Spring | **ArchUnit** | Open source, JUnit-friendly, bytecode-aware. The reference extension uses this. |
| JVM (Java, Kotlin) — non-Spring | **ArchUnit** | Same backend, different zones/scaffolding. |
| Node / TypeScript | **dependency-cruiser** | Built specifically for Node forbid-import rules. |
| Python | **import-linter** | Designed for layer/contract import rules. |
| Go | **go-arch-lint** | Closest equivalent to ArchUnit in the Go ecosystem. |
| Rust | **cargo-deny** (for crate dependencies) + **Clippy custom lints** | Less mature ecosystem for this; Semgrep is a fallback. |
| Multi-language / generic | **Semgrep** | Pattern-based, multi-language. Less precise than language-native tools but works as a fallback. |

These are recommendations. An extension can use any backend that produces violations the reporter can read.

## The adapter config

`adapter.yaml` is the only structured file in an extension. Its job is to tell the reporter where the backend writes its output and what format it's in.

Schema:

```yaml
boundaryAdapter:
  outputFormat: junit-xml          # one of the formats the reporter natively reads
  outputPath: <path glob>          # where the backend writes its output

  # Optional: how to identify boundary-rule violations vs other test failures.
  # If the backend output mixes architecture-rule failures with unrelated
  # failures (e.g., regular unit tests in the same JUnit XML), use this filter.
  violationFilter:
    matchClassName: <substring or regex>
    matchTestNamePattern: <regex>
```

In v0.1, `outputFormat: junit-xml` is the only supported value. Other formats (SARIF, JSON-violations) are on the roadmap and will be added when the second or third extension genuinely needs them.

If your backend doesn't natively produce JUnit XML, add a conversion step in `scaffold.md`. Most major static-analysis tools can output multiple formats or have community converters.

## What if my stack has no good backend?

Two honest paths:

1. **Use Semgrep with a small set of forbid-import rules.** It works for many stacks and produces output that can be converted to JUnit XML.
2. **Skip boundary enforcement for now.** Use only zone classification and the agent-side discipline. Lighter governance, fewer guarantees, but still useful. The extension's `adapter.yaml` declares no backend, and the reporter only reports on zones, API/schema/security paths, and PR size.

The second path is fine. agent-redline is more useful with a backend, but it's still useful without one. The adapter file in that case looks like:

```yaml
boundaryAdapter:
  outputFormat: none
```

And the reporter skips the boundary-violation section of the verdict.

## Distribution

For v0.1 there's no central registry. Extensions live in:

- This repo (`extensions/spring-archunit/` is the reference)
- A separate repo or directory you publish (point users at it; they install it alongside agent-redline as another skill)
- A consuming repo's local copy (vendored)

If extensions become numerous, a registry or convention can come later. Premature now.

## Contributing an extension back

If you build an extension for a common stack and want it shared, open a PR adding it under `extensions/`. The bar:

- Follows the five-file shape
- The backend has at least one mature open-source implementation
- `adapter.yaml` declares a supported output format (or scaffolds a conversion to one)
- `profile.md` is honest about gotchas, not a happy-path-only document

We don't promise to merge every contributed extension, but the door is open.

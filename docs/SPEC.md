# agent-redline — Detailed Specification

**Status:** Pre-v0.1 draft
**Last updated:** 2026-05-31

---

## 1. Purpose

agent-redline is a governance skill for AI coding agents. It helps agents — and the humans working with them — classify changes by architectural consequence and route human attention to the small set of changes that actually shape the system.

It does not review all generated code. It does not replace tests, linters, or normal CI. It does not invent architecture; it protects boundaries the team is willing to name.

## 1.1 Architecture: core + language extensions

agent-redline is split into two layers:

- **Core** is stack-neutral. It contains the skill (vocabulary, the two modes, the discipline rules), the policy schema, the reporter, and the templates that don't depend on language.
- **Language extensions** are folders of markdown plus one small config file. Each binds the core to a specific stack: typical zone defaults, recommended boundary rules, the boundary-rule backend choice, and how the reporter should read that backend's output.

agent-redline ships one reference language extension (`spring-archunit`) to prove the contract. Other stacks are extensions that teams build, maintain, and distribute themselves. The reference extension is structured the same as any third-party one — there is no special path for built-ins.

## 1.2 What the project is, in three layers

| Layer | What it is | Owns |
|---|---|---|
| **Core** | The agent-redline skill, policy schema, reporter, stack-neutral templates | Vocabulary, two modes, the loop, the policy schema, the verdict format, the comment template |
| **Language extension** | A small folder per stack | Stack-specific zones, backend choice, scaffolding instructions, adapter config |
| **Consuming repo** | What bootstrap writes into your repo | Concrete `agent-policy.yaml`, `AGENTS.md`, ArchUnit (or other backend) artifacts, CODEOWNERS additions |

What's inside the agent-redline project: the core, the language-extension contract, and one reference extension. What's not: language extensions for other stacks (community-built), backend tools themselves (external), per-repo policies (yours).

## 1.3 What's deliberately NOT extensible

To keep the contract simple and the project small, the following are fixed in the core and language extensions cannot redefine them:

- **Vocabulary.** Red/blue/gray, zones, boundary rules, checkpoints, modes — fixed names with fixed meanings.
- **Policy schema.** Extensions fill in stack-specific values; they don't add new top-level fields.
- **Verdict format.** PR comment template, exit codes, JSON output — all core.
- **Bootstrap and operating loops.** Extensions can add stack-specific notes the agent reads, but they don't change the loop structure.
- **Supported backend output formats.** Extensions pick from the small set of formats the reporter can natively read. If a backend doesn't produce one of those, the extension's scaffolding instructs the build to convert.

Inside those constraints, extensions have full freedom.

## 1.4 Design principle: context/token budget

A skill that's loaded into a harness consumes context tokens for every turn the agent runs in that repo. If the skill is large, every operating-mode turn pays that cost before doing useful work. That's the difference between a skill that gets adopted and one that's quietly unloaded after a week because "the agent feels slow now."

agent-redline treats context size as a hard design constraint, not a polish concern.

**The discipline:** write the smallest version that does the job. Measure. If smoke tests show the agent missing things, *then* expand — and only the part that's missing. Do not preemptively pad to a budget. Budgets are ceilings, not targets to fill.

### 1.4.1 Budget ceilings

Each artifact has a declared ceiling. Files that approach a ceiling need scrutiny; files that breach one fail CI (see [VALIDATION.md](VALIDATION.md), Layer 0).

| Artifact | Ceiling | Why this ceiling |
|---|---|---|
| Project-root `AGENTS.md` | 1000 tokens | Auto-loaded by harnesses when an agent works on this project |
| `core/skill/agent-redline.md` (entry point) | 800 tokens | Loaded on every session in an agent-redline-aware repo |
| `core/skill/operating-mode.md` | 1500 tokens | Loaded on every operating-mode turn |
| `core/skill/bootstrap-mode.md` | 2000 tokens | Loaded only during bootstrap (rare event) |
| Each per-checkpoint skill doc (`red-zone-change.md`, etc.) | 600 tokens | Loaded only when the relevant checkpoint is triggered |
| Generated `agent-policy.yaml` | 1500 tokens | Read every operating-mode turn |
| Generated `AGENTS.md` (in a consuming repo) | 1000 tokens | Read on session start |
| Extension `profile.md` | 2500 tokens | Loaded during bootstrap |
| Extension `scaffold.md` | 2000 tokens | Loaded during scaffold phase of bootstrap |
| Extension `operating.md` | 600 tokens | Loaded during operating mode if the extension provides one |
| Reporter PR comment | 400 tokens | Appears in agent context on next turn |

(Token counts approximate; "1K tokens" ≈ 750 words. The CI budget check in `tests/budget/` uses a defined estimator.)

These ceilings are deliberately tight. They're set based on what the file actually needs to communicate, not on what feels comfortable. If a file genuinely needs more than its ceiling, the case has to be made: what is the missing instruction, why can't it be moved to a less-frequently-loaded file, what failure mode does adding it prevent.

### 1.4.2 Principles that follow

1. **Smallest that does the job.** Write the minimum the agent needs to behave correctly. Test. Add only the missing thing, only when the test exposes the gap.

2. **Two-tier loading.** The core skill is small and always loaded. Detailed guidance (per-checkpoint skill docs, scaffold instructions) lives in separate files the agent loads only when relevant. The skill says "when you reach the scaffold phase, read `<extension>/scaffold.md`," not "here is everything inline."

3. **Policies are data, not narrative.** Comments in `agent-policy.yaml` are terse one-liners. No paragraphs explaining philosophy — that's what `docs/` is for.

4. **Operating mode reads only what it needs.** During an everyday change, the agent does NOT load bootstrap-mode docs, scaffold docs, or per-checkpoint docs unless a checkpoint is actually triggered.

5. **The reporter's PR comment is information-dense.** Verdict, what was touched, what's required, what to do next. No restated philosophy, no inline FAQs.

6. **Extensions follow the same discipline.** A third-party extension that ships a 10K-token `profile.md` breaks the contract for everyone.

7. **Verbose docs live outside the skill load path.** `docs/PHILOSOPHY.md`, `docs/BOOTSTRAP.md`, `docs/FAQ.md`, etc. are for humans reading agent-redline. The skill itself does not read them; agents working in a consuming repo do not load them.

### 1.4.3 What this rules out

- Inlining the entire profile.md content into the policy
- Verbose generated comments in policies, AGENTS.md, or PR descriptions
- Skill files that recapitulate the philosophy or rationale on every load
- "Helpful" multi-paragraph reporter comments
- Extensions that bundle long-form documentation into the bootstrap-loaded files

The verbose stuff exists; it just lives in `docs/`, not in the skill load path.

## 1.5 What the project is, in components

| Component | Role |
|---|---|
| **Skill (core)** | Teaches the agent how to behave: when to slow down, when to escalate, when to refuse a shortcut. Agent-side discipline. The agent is what classifies changes before editing. |
| **Policy** (`agent-policy.yaml`) | Repo-local source of truth: zones, boundary rules, checkpoints. Written once during bootstrap, edited as the team learns. |
| **Language extension** | A folder of markdown + one small config file that binds the core to a stack. agent-redline ships one reference extension (`spring-archunit`); others are community-built. |
| **Existing tools** | The boundary-rule backend (ArchUnit for JVM, dependency-cruiser for Node, import-linter for Python, Semgrep for generic patterns), API-diff tools, CODEOWNERS, the CI runner. agent-redline composes them; it does not bundle them. |
| **Reporter (core)** | Small CI-side script that reads the policy, walks the diff, reads backend output via the extension's adapter config, and posts a single PR comment plus an exit code. Glue, not an engine. |
| **CI** | Where the reporter and the existing tools run. Posts the verdict, blocks merge when binding rules fail. |

Each can be useful without all the others, but the value compounds when they're wired together. The skill alone is agent-side discipline. The reporter alone is just a PR-comment formatter. A boundary-rule backend alone catches dependency violations but says nothing about API/schema/security path changes or PR size. Together, they cover the cooperative case (skill) and the failure case (CI enforcement).

---

## 2. Background

### 2.1 The pressure

LLM-driven development inverts the long-standing economics of software engineering:

- Code production: cheap and fast
- Code review: bounded by human attention, unchanged
- Modeling decisions: still expensive, still human-only
- Slop reading slop: a self-reinforcing loop, where verbose generated code feeds the next agent's context with noise

The bottleneck has moved from production to review. More human review doesn't scale: at scale, reviewers approve blindly. The realistic strategy is to **route human attention** — review what matters structurally, automate everything else.

### 2.2 The asymmetry

Not all code carries the same architectural weight:

- **Structural code** — code where local changes propagate. Boundaries, public APIs, domain models, persistence contracts, security surfaces, cross-service dependencies. Tests on this code check behavior, not future changeability. agent-redline calls this the **red zone**.
- **Replaceable code** — code that is isolated, replaceable, strongly tested, low-blast-radius. Most code is here. Tests and normal review are sufficient. agent-redline calls this the **blue zone**.
- **Unclassified code** — everything not yet placed in red or blue. agent-redline calls this the **gray zone**; it's cautious by default.

agent-redline works the asymmetry: protect red-zone code with deterministic guardrails, leave the blue zone alone, surface gray-zone changes for explicit classification over time.

### 2.3 Packaging principles

- Repo-local, not central — every consuming repo defines its own zones
- Skill-first, not CLI-first — agents consume governance directly
- Compose existing tools (boundary-rule backends like ArchUnit, OpenAPI diff tooling, CODEOWNERS, the CI runner) — don't replace them
- Bootstrap by conversation, not by manual configuration
- Output a *classification verdict*, not a compilation result
- No formal architectural IR; a small policy file the agent helps you write

---

## 3. Core thesis

```text
Agents may move fast in safe areas.
Agents must be constrained near architectural structure.
Humans review modeling, contracts, boundaries, security, and persistence.
Automation enforces everything that can be made deterministic.
```

---

## 4. Vocabulary

agent-redline introduces a small, stable vocabulary. Consuming repos use these terms verbatim in their policies and instructions.

| Term | Meaning |
|---|---|
| **Red zone** | Code where a change needs **different review behavior** — separate signoff, slower cadence, or specific expertise. Red is *not* "important code." A domain entity is important; adding a field to it is routine. The test for redness is "would this fire on a typical feature PR?" If yes, it's mis-classified. See §4.3. |
| **Blue zone** | Code where agents may work with high autonomy. Isolated, replaceable, strongly testable, or low blast-radius. |
| **Gray zone** | The residual bucket — files no `red`, `blue`, or `watch` entry matched. Surfaced in the PR comment without gating merge. A persistent gray hit on a busy path is *tuning data*: the policy is incomplete and the path should be classified. See §4.4. |
| **Watch (additive tag)** | An explicit `zones.watch:` entry that surfaces the path in the PR comment regardless of how it's otherwise classified. Composes with red, blue, or gray. Never drives the verdict on its own. Use for paths that are most-of-the-time-fine but a reviewer should still see when they change. See §4.4. |
| **Zone** | A path-glob classification of code by architectural consequence. Red, blue, and gray are exclusive zones; watch is an additive tag. |
| **Boundary rule** | A deterministic dependency rule (`X must not import Y`). |
| **Boundary-rule backend** | The tool that enforces boundary rules for a given ecosystem (e.g., ArchUnit for JVM, dependency-cruiser for Node, import-linter for Python, Semgrep for generic patterns). The backend is a per-extension choice; agent-redline does not bundle one. |
| **Language extension** | A folder of markdown plus one small config file that binds the core to a stack. Carries the stack's typical zones, recommended boundary rules, backend choice, and the adapter config telling the reporter how to read backend output. agent-redline ships one reference extension (`spring-archunit`); others are community-built. |
| **Adapter config** | The single small YAML file in a language extension that tells the reporter where the backend writes its output and what format it's in. |
| **Checkpoint** | A required human attention point triggered by structural risk. Satisfied by reviewer approval, label, or both. |
| **Change classification** | The result for a PR/diff: `BLUE`, `RED`, `GRAY`, `BOUNDARY_VIOLATION`, `API_CHANGE`, `SCHEMA_CHANGE`, etc. |
| **Bootstrap mode** | The skill operating on a fresh repo to set up governance artifacts. |
| **Operating mode** | The skill operating in a configured repo, classifying intended changes before editing. |
| **Shadow mode** | A check runs and reports, but does not block CI. |
| **Binding mode** | A check fails CI when violated. |

### 4.1 Zones vs. boundary rules

These are different concepts and must not be conflated.

- A **zone** classifies a path: "code under `domain/**` is dangerous to change."
- A **boundary rule** classifies a dependency: "code under `domain/**` may not depend on code under `adapter/**`."

A repo will typically declare both. A change can be in a blue zone but still violate a boundary rule (e.g., editing an adapter mapper to import a domain class incorrectly).

### 4.2 Zones vs. review state

agent-redline classifies *architectural consequence*, not *review state*. Whether a change has been reviewed is PR metadata (labels, approvals, CI status), not a property of the file. Consuming repos must not encode review state in zone definitions.

### 4.3 The red-utility test

A red zone earns its place only if it fires on a **minority** of normal feature PRs. A red zone that fires on most PRs is alert fatigue: the team learns the warning is meaningless and approves on autopilot, which is worse than not having the tool at all.

The mental model:

- **"Important code"** is not a zone — important + routine = on the `watch` list.
- **Red** = "this change wants different review behavior." Different *who*, different *when*, or different *what's being verified*.
- **Watch** (additive tag, see §4.4) = "an agent could plausibly do this autonomously, and most of the time the result is fine, but a reviewer should at least see that it happened." Surfaced in the PR comment, no checkpoint.
- **Blue** = autonomous; tests + normal review are sufficient.

Bootstrap Phase 3 enforces this: every red entry in the draft policy is challenged with "would this fire on three recent feature PRs?" If yes, it's mis-classified. See `core/skill/bootstrap-mode.md` Phase 3a.

The first 1-2 weeks of shadow mode is **zone calibration**: confirm the red entries actually fire on a minority of PRs (use `scripts/agent-redline-tune.py` against a batch of recent merged PRs). Re-tune the policy until the firing rates settle. Only after zones are stable do you start flipping rules from shadow to binding.

### 4.4 Gray vs. watch

These look similar in the PR comment but mean different things, and conflating them produces tuning mistakes.

| | gray | watch |
|---|---|---|
| How it's set | implicit — no zone matched | explicit `zones.watch:` entry |
| Composability | exclusive bucket | additive tag; coexists with red, blue, or gray |
| Verdict effect | a gray hit (no red/api/etc.) produces a `GRAY` verdict | never produces a verdict on its own; only adds a comment row + exit-code warning |
| Intent | "we haven't classified this yet" | "we've decided: surface this when it changes" |
| Right reaction | "should this path be classified?" | "noted, looking at the diff" |
| Lifetime | should shrink as zones get classified | stable; lives as long as the path matters |

Gray is the **residual bucket**. The reporter sweeps a file into gray only when no `red`, `blue`, or `watch` entry matches it. A persistent gray hit on a busy path is *tuning data* — it means the policy is incomplete and that path should be classified.

Watch is an **additive tag**. A file can be `red + watch`, `blue + watch`, or `gray + watch`. Watch never overrides the file's other classification; it only adds the visibility flag. Use it for paths that are most-of-the-time-fine but the reviewer wants to see when they change anyway (Spring `*Configuration.java`, domain entities, adapter DTOs that *might* be contract surface).

Both surface in the PR comment without gating merge. They behave slightly differently for the verdict label:

- A diff with gray-zone hits (and no red/api/schema/security signals) gets verdict `GRAY`.
- A diff with only `blue + watch` files keeps verdict `BLUE` — the watch tag adds a row to the comment and bumps exit code to 1 (warning), but doesn't change the headline classification. Watch never *causes* a verdict on its own.

The PR comment distinguishes them in the zones table — one row labeled "Gray", a separate row labeled "Watch".

---

## 5. Product shape

### 5.1 What ships in the public agent-redline repo

```
agent-redline/
├── core/                                  # stack-neutral
│   ├── skill/
│   │   ├── agent-redline.md               # the skill itself
│   │   ├── bootstrap-mode.md              # bootstrap-mode instructions
│   │   └── operating-mode.md              # operating-mode instructions
│   ├── reporter/
│   │   ├── agent-redline-report.{py,sh}   # reads policy + diff + backend output, posts PR comment
│   │   └── README.md
│   ├── schema/
│   │   └── agent-policy.schema.json       # JSON Schema for agent-policy.yaml (v1)
│   └── templates/                         # stack-neutral templates
│       ├── agent-policy.yaml.template
│       ├── AGENTS.md.template
│       ├── pr-template.md
│       ├── pre-push-check.sh
│       └── skills/                        # per-checkpoint skill docs (copied into consuming repos)
│           ├── blue-zone-work.md
│           ├── red-zone-change.md
│           ├── gray-zone-change.md
│           ├── boundary-violation.md
│           ├── api-change-checkpoint.md
│           ├── persistence-change-checkpoint.md
│           ├── security-change-checkpoint.md
│           └── pr-discipline.md
├── extensions/
│   └── spring-archunit/                   # the reference language extension
│       ├── README.md                      # what stack this is for, when to pick it
│       ├── profile.md                     # zones, boundaries, gotchas (read by agent during bootstrap)
│       ├── scaffold.md                    # how the agent generates ArchUnit + CI for this stack
│       ├── operating.md                   # (optional) stack-specific operating-mode notes
│       └── adapter.yaml                   # tells the reporter: backend output format, where to find it
├── tests/                                 # validation artifacts (see docs/VALIDATION.md)
│   ├── schema/
│   │   ├── valid/                         # known-good policies
│   │   └── invalid/                       # known-bad policies
│   ├── reporter/                          # golden fixtures: policy + diff + backend output → expected verdict
│   │   └── <scenario>/
│   ├── extensions/
│   │   └── spring-archunit/
│   │       └── fixture-repo/              # minimal Spring service for scaffold dry-run
│   ├── skill-smoke/                       # fixture inputs + post-bootstrap assertions
│   └── skill-review/
│       ├── checklist.md                   # manual review checklist
│       └── fixtures/                      # repos to run the skill against
├── examples/
│   └── spring-hexagonal/                  # Layer 3 fixture (Spring source-of-truth, also used by demo)
├── demo-source/                            # canonical content for the paired agent-redline-demo repo
│   ├── agent-policy.yaml
│   ├── AGENTS.md
│   ├── README.md
│   ├── CODEOWNERS
│   ├── docs/agent/                        # per-checkpoint docs copied into the demo repo
│   ├── scripts/agent-redline-check.sh
│   ├── .github/{pull_request_template.md, workflows/agent-redline.yml}
│   └── pr-scenarios/{blue-only, red-with-checkpoint, boundary-violation}/
├── scripts/
│   └── sync-demo.sh                       # populate the paired demo repo's branches
├── docs/
│   ├── SPEC.md                            # this file
│   ├── PHILOSOPHY.md
│   ├── BOOTSTRAP.md
│   ├── OPERATING.md
│   ├── CI_INTEGRATION.md
│   ├── EXTENSIONS.md                      # what an extension is, what files it has, how to write one
│   ├── POLICY_SCHEMA.md
│   ├── SKILL_AUTHORING.md                 # rules for writing agent-loaded files
│   ├── VALIDATION.md                      # how we test agent-redline itself
│   └── FAQ.md
├── README.md                              # public-facing project pitch
└── AGENTS.md                              # orientation for developer-agents working on this project
```

A language extension is five files: a README, two markdown files the agent reads (profile + scaffold), one optional markdown file (operating-mode addendum), and one small YAML file (the adapter config). That's the entire shape. The reference extension (`spring-archunit`) and any third-party extension look the same.

### 5.2 What each consuming repo writes (during bootstrap)

```
repo/
├── agent-policy.yaml
├── AGENTS.md                         # references existing CLAUDE.md / GEMINI.md / AGENTS.md
├── docs/agent/
│   ├── blue-zone-work.md             # copied or referenced from skill
│   ├── red-zone-change.md
│   ├── boundary-violation.md
│   └── ...
├── scripts/
│   └── agent-redline-check.sh
├── src/test/.../architecture/        # or equivalent for the build system
│   └── DependencyArchitectureTest.java
├── .github/
│   ├── pull_request_template.md
│   └── workflows/
│       └── agent-redline.yml         # PROPOSED, not auto-committed
└── docs/
    └── agent-redline-ci-proposal.md  # the proposal artifact
```

### 5.3 What the project does NOT ship

- A heavyweight CLI as the primary interface (the reporter is a small script, not the product center)
- A "classification engine" as a real engine — the reporter is glue: globs + policy lookups + comment formatting
- A central platform or service
- A formal architectural IR (explicitly out of scope)
- File-level "trust tier" annotations
- A standalone code-review system competing with normal PR review
- A runtime sandbox or IAM layer

---

## 6. The skill

The skill is three markdown files under `core/skill/`. They are the normative source for agent behavior; this section summarizes their roles. Read the files for the actual instructions.

### 6.1 Files

- **`core/skill/agent-redline.md`** — entry point. Vocabulary, mode-dispatch, principles, decision-priority, resource pointers. The harness loads this on session start when the skill is installed.
- **`core/skill/operating-mode.md`** — the everyday loop: read policy → classify → branch → edit/escalate → local check → PR description.
- **`core/skill/bootstrap-mode.md`** — the one-time setup conversation: inspect → propose extension → adapt → write artifacts → propose CI → summary.

### 6.2 Mode dispatch

The skill picks a mode based on what it finds:

- `agent-policy.yaml` exists in the repo root → **operating mode**
- The user asked to set up agent-redline → **bootstrap mode**
- Neither → the skill is not relevant; get out of the way

### 6.3 Skill behavior contracts

These hold across both modes. They're stated in `core/skill/agent-redline.md` as principles; restated here so the spec is self-contained for reviewers.

- Never silently write CI workflow files or modify branch protection. Propose; humans decide.
- Never edit boundary-rule backend definitions (ArchUnit tests on JVM, etc.) in operating mode without an explicit checkpoint.
- Never approve a boundary-rule violation by adding suppressions. Fix the structure or escalate.
- Always classify before editing.
- Default conservative on uncertainty. Gray > blue, red > gray, boundary risk > everything.

### 6.4 Authoring discipline

Skill files are subject to budget ceilings (§1.4) and the authoring rules in `docs/SKILL_AUTHORING.md`. The deletion test is the operative check: cut any sentence that doesn't change agent behavior.

---

## 7. The policy schema

`agent-policy.yaml` is the single source of truth for a repo's governance. Two normative artifacts:

- **`core/schema/agent-policy.schema.json`** — JSON Schema (Draft 2020-12). The reporter validates against it; CI rejects non-conforming policies.
- **[`POLICY_SCHEMA.md`](POLICY_SCHEMA.md)** — human-readable reference: every field, defaults, validation rules, glob syntax, mode semantics, and `satisfiedBy` semantics.

Examples of valid and invalid policies live in `tests/schema/{valid,invalid}/`.

### 7.1 Mandatory rule: boundary-backend definitions are red-zone

Every policy must include a zone entry covering the boundary-rule backend's definition files (ArchUnit test classes for JVM, dependency-cruiser config for Node, etc.) with a stricter checkpoint requirement than ordinary architecture changes. Bootstrap enforces this; a generated policy that doesn't protect its own boundary definitions is invalid.

```yaml
zones:
  red:
    - path: src/test/java/**/architecture/**
      reason: dependency-rule definitions; weakening these requires explicit checkpoint
      checkpoint: architecture-review
```

---

## 8. The reporter

The reporter is a small CI-side script (a few hundred lines, single language) that takes a diff and a policy and produces a single PR comment plus an exit code. It is *not* a classification engine in any meaningful sense — it does path-glob lookups, reads existing tool outputs (the boundary-rule backend, OpenAPI diff if configured), and renders the results into a human-readable verdict.

The agent classifies changes during operating mode, before editing. The reporter's job is post-hoc: given whatever the diff turned out to be, produce the verdict CI and humans need to see.

### 8.1 Inputs

- A diff (base..head)
- The repo's `agent-policy.yaml`
- (Optional) Boundary-rule backend results (e.g., ArchUnit test report for JVM) — the reporter reads them, doesn't compute boundary violations itself
- (Optional) Two OpenAPI spec files — `--api-spec-base` and `--api-spec-head`. Used when the policy declares `api.type: openapi-from-controllers`. The CI workflow generates both specs (typically via `git worktree`) and the reporter computes a structural diff. Falls through to the file-glob path-detection when `api.type: openapi-spec-file` and no specs are passed.

### 8.2 Output (machine-readable)

```json
{
  "verdict": "RED" | "BLUE" | "GRAY" | "BOUNDARY_VIOLATION" | "MIXED",
  "summary": "...",
  "zones": {
    "red": ["src/main/java/.../OrderService.java"],
    "blue": ["src/test/.../OrderServiceTest.java"],
    "gray": [],
    "watch": ["src/main/java/.../OrderDto.java"]
  },
  "checkpoints": [
    {
      "id": "architecture-review",
      "reason": "Domain class modified",
      "satisfied": false,
      "satisfyBy": ["codeownerApproval", "label:architecture-reviewed"]
    }
  ],
  "boundaryViolations": [
    {
      "rule": "domain-must-not-import-adapters",
      "from": "src/main/java/.../OrderService.java",
      "to": "src/main/java/.../PostgresOrderRepository.java",
      "severity": "error",
      "source": "archunit"
    }
  ],
  "apiChanges": { "detected": true, "breakingChange": false },
  "schemaChanges": { "detected": false },
  "prSize": { "files": 12, "lines": 340, "verdict": "ok" },
  "exitCode": 0 | 1 | 2,
  "recommendedAction": "require-architecture-review"
}
```

### 8.3 Output (human-readable PR comment)

A single comment, updated in place on each push. Format:

```markdown
## agent-redline: RED

**Touched red-zone code.** Architecture review required.

| Zone | Files |
|---|---|
| Red | `OrderService.java` (domain) |
| Blue | `OrderServiceTest.java` (tests) |

**Required checkpoints:**
- [ ] architecture-review — apply label `architecture-reviewed` or get CODEOWNER approval

**Boundary check:** passed (ArchUnit)
**API check:** no public-API changes detected
**Schema check:** no migration changes
**PR size:** 12 files / 340 lines (within limits)

[Why this matters](docs/agent/red-zone-change.md)
```

### 8.4 Exit codes

| Code | Meaning |
|---|---|
| 0 | Pass (or shadow mode with no binding violations) |
| 1 | Soft warning (gray-zone, PR size warn, etc.) |
| 2 | Hard fail (missing required checkpoint, oversized PR, boundary violation surfaced by the backend and `boundary_violation` is binding) |

### 8.5 Implementation

The reporter is a small script (single language, chosen for ecosystem fit with the chosen CI). What it does:

- Parse `agent-policy.yaml`
- Walk the diff (`git diff --name-only base...head` plus line counts)
- For each touched file, look up its zone (red / blue / gray) by matching the policy's globs, and additionally tag it as `watch` if it matches any `zones.watch` entry
- Detect API/schema/security/runtime-config changes by matching the configured paths
- Read boundary-rule backend results (e.g., the ArchUnit test report on JVM) and surface boundary violations
- If two OpenAPI specs are supplied (api.type=openapi-from-controllers; CI workflow generates them at base and head SHAs), compute a structural diff and surface paths added / removed / methods modified. The reporter does not classify breaking-vs-additive — that's reviewer territory.
- Compute required checkpoints and check whether they're satisfied (PR labels, CODEOWNER approvals)
- Render the JSON verdict + the markdown PR comment
- Return the right exit code based on policy mode (shadow / binding) and severity

What it does *not* do:

- Compute boundary violations itself — the boundary-rule backend does that
- Generate OpenAPI specs from controller annotations — that's a build-side job; the reporter reads the result
- Classify changes "intelligently" — it's path globs, not inference
- Replace any existing CI check — it composes them into one verdict comment

---

## 9. CI integration

### 9.1 Principle

**CI integration requires human decision and is never auto-committed.** The skill produces a proposal; the developer (and platform owner, when relevant) applies it.

### 9.2 The proposal artifact

`docs/agent-redline-ci-proposal.md` contains:

1. The proposed workflow file (ready to copy into `.github/workflows/`)
2. The required-status-check names to add to branch protection
3. CODEOWNERS additions, mapped to the repo's existing team structure (best-effort)
4. The recommended initial mode (always shadow)
5. A timeline: how long to run shadow, what to tune, when to flip checks to binding
6. A list of decisions explicitly flagged as requiring human judgment (which checks block, which teams own which checkpoints, etc.)

### 9.3 Reusable Action (roadmap)

A reusable GitHub Action wrapping the reporter is on the roadmap, not in v0.1. Once published, it would look like:

```yaml
- uses: rore/agent-redline/report@v1
  with:
    policy: agent-policy.yaml
    base: ${{ github.event.pull_request.base.sha }}
    head: ${{ github.event.pull_request.head.sha }}
    mode: shadow                # shadow | binding
    comment: true               # post the verdict as a PR comment
```

In v0.1, CI workflows invoke the reporter script directly. Other CI systems (GitLab, CircleCI, Jenkins) do the same.

### 9.4 Shadow mode → binding mode

The default mode is shadow. The skill explicitly tells the developer:

> Run shadow mode for at least 4 weeks or 30 PRs, whichever is later. Watch for:
> - False-positive boundary rules (rules firing on legitimate changes)
> - Gray-zone hit rate (most changes shouldn't be gray; if many are, your zones need work)
> - PR-size distribution (does the warn/fail threshold match your team's reality?)
>
> When the data is clean, flip checks to binding one at a time. Do not flip everything at once.

### 9.5 Local pre-push check

Bootstrap writes `scripts/agent-redline-check.sh` (or platform equivalent). This script runs the same reporter CI runs, against the local diff. Operating mode invokes it before declaring work complete.

This closes the "tests pass locally but CI fails" loop and gives the agent deterministic feedback during work rather than only at PR time.

---

## 10. Language extensions

A language extension binds the core to a specific stack. It is a small folder with a fixed shape — five files at most — that the agent reads during bootstrap (and optionally during operating mode) to know how to handle this stack.

### 10.1 Shape

```
extensions/<name>/
├── README.md          # what stack this is for, when to pick it
├── profile.md         # zones, boundaries, gotchas (read by agent during bootstrap)
├── scaffold.md        # how the agent generates backend artifacts + CI snippets
├── operating.md       # (optional) stack-specific operating-mode notes
└── adapter.yaml       # tells the reporter where backend output is and what format it's in
```

That is the entire contract. No manifest, no version pins, no plugin metadata. If a fact about an extension belongs anywhere, it belongs in the extension's `README.md`.

### 10.2 What each file contains

- **`README.md`** — one-paragraph summary of which stack this extension targets and when to pick it. Human-readable.
- **`profile.md`** — typical package structure for this stack, default red/blue/gray zones (with paths), recommended boundary rules, API contract location (controllers, OpenAPI files, proto, GraphQL), persistence conventions, security/auth conventions, runtime config, ecosystem gotchas. The agent reads this during bootstrap to build a draft `agent-policy.yaml` for the developer to review.
- **`scaffold.md`** — how the agent generates the boundary-backend setup (e.g., the ArchUnit test class), the build wiring (e.g., adding the ArchUnit dependency), and the CI snippet for the boundary check. The agent reads this when writing the directly-committed artifacts.
- **`operating.md`** — optional. Stack-specific notes the agent reads during operating mode (e.g., "in this stack, treat X as `watch` even if the policy says blue"). Most extensions won't need this.
- **`adapter.yaml`** — the only structured (non-markdown) file. Tells the reporter where the backend wrote its output and what format it's in. See §10.4.

### 10.3 Reference extension

agent-redline ships one reference extension: **`spring-archunit`** for Spring Boot + ArchUnit. It is structured exactly like any third-party extension. There is no special path for built-ins.

### 10.4 The adapter contract

`adapter.yaml` is the one place where an extension gives the reporter machine-readable data:

```yaml
boundaryAdapter:
  outputFormat: junit-xml          # one of the formats the reporter natively reads
  outputPath: build/test-results/test/TEST-*ArchitectureTest.xml
  violationFilter:                 # optional; how to identify boundary violations vs other failures
    matchClassName: "ArchitectureTest"
    matchTestNamePattern: "(?i).*depend.*|.*should_not.*"
```

The reporter natively reads a small set of formats (initially: JUnit XML; SARIF and JSON-violations are roadmap candidates). Extensions cannot ship custom parsers. If a backend doesn't natively produce a supported format, the extension's `scaffold.md` instructs the build to convert the backend's output to one that is supported.

This is what keeps the extension contract honest: extensions are markdown plus one small declarative config. No code execution from extensions.

> **v0.1 status:** the reporter ingests Spring/ArchUnit JUnit XML by convention (testcase classes containing `ArchitectureTest`, with a `<failure>` element). The `adapter.yaml` schema above is the contract; the reporter does not yet dispatch on it. The file lives in the reference extension as the source-of-truth for that contract and so third parties have something to copy. Wiring the reporter to actually consult `adapter.yaml` is roadmap (§15.3) and gates the second language extension.

### 10.5 Building a new extension

See [EXTENSIONS.md](EXTENSIONS.md) for the practical guide. The short version: copy `extensions/spring-archunit/`, rewrite the markdown for your stack, point `adapter.yaml` at your backend's output. Five files.

---

## 11. PR discipline

A PR that exceeds reasonable human attention is approved blindly. agent-redline includes PR shape rules.

### 11.1 Size limits

`agent-policy.yaml` declares thresholds; the reporter checks them:

```yaml
prRules:
  maxChangedFiles: { warn: 50, fail: 100 }
  maxLinesChanged: { warn: 1000, fail: 2000 }
```

Default thresholds are intentionally generous. Tighten over time as the team adapts.

### 11.2 PR template

Bootstrap adds (or merges into) `.github/pull_request_template.md`:

```markdown
## Change classification

- [ ] Blue-only
- [ ] Red-zone change
- [ ] Gray-zone change
- [ ] API/contract change
- [ ] Persistence/schema change
- [ ] Security-sensitive change

## What changed

<short factual summary>

## Why

<short reason>

## Verification

<commands run, tests passed, manual checks performed>

## Checkpoint needed?

- [ ] No
- [ ] Architecture
- [ ] API
- [ ] Persistence
- [ ] Security
- [ ] Ops
```

### 11.3 Verbose-description rejection

The skill instructs agents not to produce verbose generated PR descriptions (history of attempts, restated requirements, redundant code summaries). The reporter optionally flags suspiciously long descriptions as a slop signal.

---

## 12. Integration with existing agent ecosystems

agent-redline composes with whatever the consuming organization already has.

### 12.1 Claude Code / Codex / Cursor

The skill is installed via the harness's standard skill mechanism. The skill self-detects when to activate.

### 12.2 Existing agent layers (architect-style, QA-style, code-review, per-repo agents, etc.)

agent-redline does not replace these. Where they exist:

- **Architect-style review agents** are typically the satisfaction signal for `architecture-review` checkpoints. The org wires its architect's approval (or label-application) into the checkpoint definition.
- **QA-style verification agents** map to the `Verification` section of the PR template. Their output is the verification evidence.
- **Code-review agents** continue doing what they do; agent-redline is structural classification, not code review.
- **Per-repo agents** read the repo's `AGENTS.md` and `agent-policy.yaml` like any other agent. No special integration needed beyond making sure those files are referenced from the per-repo agent's instruction file.

### 12.3 Existing instruction files (CLAUDE.md, AGENTS.md, GEMINI.md)

Bootstrap adds a clearly-marked reference:

```markdown
## Agent governance

This repo uses agent-redline. Before making changes:

- Read [`AGENTS.md`](AGENTS.md) for repo-specific zones and rules.
- Read [`agent-policy.yaml`](agent-policy.yaml) for the policy.
- Classify your intended change before editing.

See [agent-redline](https://github.com/rore/agent-redline) for the framework.
```

---

## 13. Non-goals

agent-redline explicitly does not:

- Prove code correctness
- Detect whether code was written by a human or an agent
- Replace tests, linters, type checks, or normal CI
- Replace architecture work — it surfaces architectural risk; humans still do architecture
- Eliminate human review — it routes review to where it's needed
- Provide a runtime sandbox or IAM model
- Govern non-source artifacts (deploy configs, secrets, infra outside Terraform)
- Operate cross-repo (single-repo scope only in v1; cross-service signal is future work)
- Require teams to adopt a formal IR

---

## 14. Success criteria

agent-redline v1 is successful when, in a real consuming repo:

1. An agent attempting to import an adapter from `domain/**` is blocked deterministically with a clear message.
2. An agent modifying a public API is forced through an `api-review` checkpoint.
3. An agent modifying a DB migration is forced through a `persistence-review` checkpoint.
4. An agent producing an oversized PR is told to split it.
5. An agent working in tests / docs / isolated adapters proceeds without friction.
6. A developer can read the PR comment and understand what attention is needed in under 30 seconds.
7. A developer can bootstrap agent-redline in a new repo, in conversation with the agent, in under one hour.
8. Shadow mode produces actionable false-positive data the team can use to tune the policy.

---

## 15. MVP scope

### 15.1 What ships in v0.1

- The core skill (`core/skill/agent-redline.md`, bootstrap, operating)
- The reference language extension: `extensions/spring-archunit/` (README, profile, scaffold, operating, adapter)
- The reporter (small script: reads policy + diff + backend output, posts PR comment, returns exit code; runs locally and in CI)
- Stack-neutral templates: `agent-policy.yaml`, `AGENTS.md`, `pr-template.md`, `pre-push-check.sh`
- Eight per-checkpoint skill docs (`blue-zone-work`, `red-zone-change`, `gray-zone-change`, `boundary-violation`, `api-change-checkpoint`, `persistence-change-checkpoint`, `security-change-checkpoint`, `pr-discipline`)
- Policy schema: `core/schema/agent-policy.schema.json`
- Docs: `PHILOSOPHY.md`, `BOOTSTRAP.md`, `OPERATING.md`, `CI_INTEGRATION.md`, `EXTENSIONS.md`, `POLICY_SCHEMA.md`, `VALIDATION.md`, `FAQ.md`
- A worked example in `examples/spring-hexagonal/`
- Validation artifacts (see §15.4 and `docs/VALIDATION.md`)

### 15.2 What does NOT ship in v0.1

- LLM-judge layer
- Cross-service / cross-repo signal
- Skill marketplace / central distribution
- Language extensions other than `spring-archunit` (community-built or later)
- Dashboard / metrics aggregation
- Auto-installer
- File-level "trust tiers"
- Formal IR layer
- Reusable GitHub Action wrapping the reporter
- CLI for non-agent / pure-CI use cases

### 15.3 Roadmap candidates (in priority order)

The schema describes what the reporter actually does today. The items below are *not* in the schema yet — they will be added when the reporter learns them, not before.

1. **Additional language extensions** (community or in-tree: Node, Python, Go, Rust). Will introduce a generic `boundaryBackend` field and wire the reporter to actually dispatch on `adapter.yaml`. Until there is a second backend to dispatch to, neither field exists, because there is no choice.
2. **Additional backend output formats** supported natively by the reporter (SARIF, JSON-violations).
3. **Generic rule engine** (`changeRules`) — only if the v0.1 hardcoded behavior turns out not to be enough in practice. The hardcoded mapping is: red-zone change → require checkpoint; gray-zone change → warn; boundary violation → fail (when binding); api/schema/security/runtime-config change → require the corresponding checkpoint; PR-size warn → warn; PR-size fail → require split. If real users need to override these, we'll design the override surface with their cases in hand.
4. **Richer checkpoint satisfaction** (`team: <name>`, `reviewerCount: <n>`). Requires querying the host (GitHub / GitLab / etc.) for team membership and approval counts.
5. **Reusable GitHub Action** wrapping the reporter (`rore/agent-redline/report@v1`). Until then, CI invokes the standalone script directly.
6. **LLM-judge layer** for soft checks (implicit-contract risk, modeling-change detection).
7. **Cross-repo API-consumer signal** (when one service changes its API, surface to its consumers).
8. **GitLab CI / Jenkins / CircleCI workflow templates.**
9. **Dashboard for shadow-mode tuning data.**
10. **CLI for non-agent / pure-CI use cases.**

### 15.4 Validation artifacts required for v0.1

agent-redline v0.1 is not "done" until all of the following are in place. See [VALIDATION.md](VALIDATION.md) for the full strategy.

- **Policy schema** (`core/schema/agent-policy.schema.json`) — JSON Schema for `agent-policy.yaml`
- **Schema fixtures** (`tests/schema/valid/`, `tests/schema/invalid/`) — known-good and known-bad policies
- **Reporter golden fixtures** (`tests/reporter/<scenario>/`) — at least the 11 scenarios listed in VALIDATION.md
- **Extension dry-run target** (`examples/spring-hexagonal/`) — minimal Spring service used to verify the scaffold compiles and runs (Layer 3 harness lives at `tests/extensions/spring-archunit/`)
- **Skill smoke check** (`tests/skill-smoke/`) — fixture inputs + post-bootstrap assertions
- **Skill review checklist** (`tests/skill-review/checklist.md`) — manual checklist run by a human in Claude Code / Codex against fixture repos
- **Paired demo repo** (`agent-redline-demo` on GitHub) with two long-lived branches (`greenfield`, `main`) and three PR-scenario branches (`demo/blue-only-pr`, `demo/red-with-checkpoint-pr`, `demo/boundary-violation-pr`). Source-of-truth at `demo-source/` in this repo.
- **Demo sync script** (`scripts/sync-demo.sh`) — regenerates the demo repo's branches deterministically from `demo-source/` + `examples/spring-hexagonal/`
- **Token-budget check** — every artifact under its declared budget (see §1.4.1)

The CI for agent-redline itself runs Layers 1–3 mechanically. Layers 4 and 5 are gated by manual sign-off before a v0.1 release.

---

## 16. Pilot plan

The first consuming repo should be a Spring service with a recognizable structure (clean hexagonal or layered package layout, ArchUnit-friendly), enough PR traffic to produce meaningful shadow-mode data within a reasonable timeframe, and a team willing to tune the policy as false positives surface.

### 16.1 Pilot phases

**Phase 0 — public agent-redline v0.1 ready.**
The core (skill, reporter, templates) and the `spring-archunit` reference extension exist and work on a synthetic example.

**Phase 1 — Bootstrap the pilot.**
- Run the skill in bootstrap mode against the pilot repo
- Generate policy, AGENTS.md, ArchUnit tests, pre-push script, PR template
- Produce CI proposal
- Human reviews and applies CI proposal
- Initial mode: shadow

**Phase 2 — Shadow run.**
- 4 weeks or 30 PRs, whichever is later
- Collect: false-positive boundary rules, gray-zone hit rate, PR-size distribution, agent classification accuracy
- Tune the policy based on real data

**Phase 3 — Selective binding.**
- Boundary-rule backend (ArchUnit on the Spring pilot): binding for new violations first (see CI_INTEGRATION.md baseline pattern)
- Report comment: binding (informational; doesn't block)
- API diff: binding once tuned
- PR size: binding last (most likely to fight existing reality)

**Phase 4 — Replicate.**
- Apply to additional services using the same skill + tuned policy as a starting point.

### 16.2 Pilot success metrics

- Number of legitimate boundary violations caught (true positives)
- Number of false-positive blocks (target: trending toward zero)
- Developer self-reported friction (qualitative)
- Agent compliance rate in operating mode (does the agent classify before editing?)
- Time-to-bootstrap a new repo

### 16.3 Pilot risks

- **Legacy package layout doesn't match hexagonal.** Mitigation: spend bootstrap time mapping actual layout to zones, even if it means non-standard glob patterns.
- **Domain-specific concerns missed by the generic extension defaults.** Mitigation: bootstrap conversation explicitly asks about third-party adapter contracts, multi-tenant persistence, customer-specific code, and other domain concerns the team cares about.
- **Existing review/approval agents don't apply checkpoint labels.** Mitigation: update the relevant agent prompts (architect-style reviewers, QA-style verifiers) before flipping the corresponding checkpoint to binding.
- **Existing agent instruction file too large to reference AGENTS.md cleanly.** Mitigation: keep AGENTS.md tight and summary-style; deep details live in `docs/agent/`.

---

## 17. Open questions

These are explicitly unresolved and should be answered during pilot use, not now:

1. **PR-comment authoring identity.** GitHub Actions bot vs. a custom GitHub App. Bot is simpler; an App would allow updating-in-place reliably across forks. Decide once we have a real consuming repo where forks matter.
2. **How agents authenticate to apply checkpoint labels.** Org-specific; the skill describes the requirement but doesn't ship a token model. Will harden once a pilot needs it.
3. **Skill discoverability across harnesses.** The Agent Skills standard format covers Claude Code, Codex, Cursor, Gemini CLI, and others. If a harness lands that needs a different shape, decide whether to add a compatibility shim or wait for the standard to absorb it.
4. **Multi-module repos.** Whether one root `agent-policy.yaml` with module-aware globs is enough, or whether a per-module overlay mechanism is worth the complexity. Defer until a real multi-module repo asks the question.

For decisions that *have* been made (skill-first packaging, three-layer architecture, reporter-not-engine, ArchUnit as JVM default, hard token budgets, schema-describes-what-reporter-does, etc.), see [`DECISIONS.md`](DECISIONS.md).

---

## 18. Glossary cross-reference

See [§4](#4-vocabulary). Vocabulary is normative; implementations must use these terms.

---

## 19. Changelog

- **2026-05-31 (rename):** `zones.grayWatch` renamed to `zones.watch`. The old name was misleading — it suggested a gray subtype, but the field is an additive tag that composes with red, blue, or gray (a file can be `red+watch`, `blue+watch`, or `gray+watch`). New SPEC §4.4 explicitly contrasts gray (residual bucket) with watch (additive tag). All schema/code/docs/templates/fixtures updated. Pre-v0.1 rename: no migration shim needed.
- **2026-05-31 (later still):** Red-zone framing sharpened. Red means *different review behavior*, not "important code" (§4.3). Spring profile defaults rewritten to a much narrower red surface (repository/gateway interfaces, controllers, migrations, security paths, arch tests, prod runtime config) with most domain/application code moved onto the watch list. Bootstrap Phase 3 now mandates a "would this red zone fire on a typical PR?" check per entry. New `scripts/agent-redline-tune.py` computes per-zone firing rates from a batch of merged PRs (zone-calibration tool). Shadow mode reframed as two distinct decisions: zone calibration (window 1) vs. check-flip tuning (window 2).
- **2026-05-31 (later):** OpenAPI from controllers shipped. The reporter now accepts `--api-spec-base` / `--api-spec-head`; the CI workflow generates both specs at base and head SHAs (typically via `git worktree`) and the reporter computes a structural diff (paths added/removed, methods added/removed/modified). The diff is descriptive, not classificatory — reviewers judge breaking-vs-additive. Schema re-accepts `api.type: openapi-from-controllers` and requires `generationCommand`. Bootstrap-mode now explicitly composes with existing arch tests, agent-instruction files, and pre-push hooks rather than overwriting them.
- **2026-05-31:** Schema cleanup. Removed fields the v0.1 reporter accepted but did not implement (`changeRules`, `defaults.unclassifiedZone`, `defaults.grayMode`, `boundaryBackend`, `api.type: openapi-from-controllers`, `team:`/`reviewerCount:` checkpoint forms). The schema now describes only what the reporter does; reserved-for-later items are tracked in §15.3 with an implementation gate. Reporter CLI: `--default-mode` is the canonical flag; `--mode` is a hidden alias.
- **v0.1 (2026-05-28):** Initial draft. Project kickoff.

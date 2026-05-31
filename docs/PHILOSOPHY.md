# Philosophy

agent-redline rests on four observations.

## 1. Human attention is the scarce resource

LLMs broke the symmetry between code production and code review. Production is now nearly free. Review is bounded by the same cognitive limits it always was. The ratio between what is produced and what a human can actually process is the new bottleneck.

More human review doesn't help. At scale, reviewers approve blindly. The realistic move is to spend human attention where it actually changes the outcome — and automate the rest.

## 2. Tests check behavior, not structure

A feature can pass every test, ship in a small clean PR, and still leave the architecture worse. The canonical example: an agent gets a task to add a field, sees that the port doesn't support it, and the easy path is to import the concrete adapter directly into the service. Tests pass. Feature works. PR is small.

Three months later, ten more agents have copied the shortcut. The boundary is gone. The unit tests need a real database. The cost of changing the system has multiplied.

This is not aesthetics. It is structural debt that local correctness cannot detect.

## 3. Not all code carries the same architectural weight

Some code is structurally consequential: changing it propagates. Boundaries, public APIs, domain models, persistence contracts, security surfaces. agent-redline calls this the **red zone**.

Most code is replaceable: isolated, strongly tested, low-blast-radius. Tests and normal review are sufficient there. Agents can work with high autonomy. agent-redline calls this the **blue zone**.

Anything in between — not yet placed in either — is the **gray zone**. Cautious by default; surfaced in PRs so it gets classified explicitly over time.

The opportunity is in the asymmetry. Protect the red zone with deterministic guardrails. Leave the blue zone alone. Don't let the gray zone stay gray forever.

**Corollary: red zones must be calibrated against real PRs.** A red zone that fires on ordinary feature work isn't protecting structure — it's noise that reviewers will learn to ignore. "This file looks important" is not enough; the test is whether changes to it actually need different review behavior. The Spring extension defaults were tuned against three production services after the first round of defaults fired on ~50% of PRs. Where a semantic signal exists (OpenAPI diff for API changes, migration detection for schema), prefer it over path-touch — path-based red zones over-fire on bug-fixes and refactors.

## 4. Slop feeds slop

Verbose generated comments, bloated PR descriptions, redundant code summaries — they all look harmless. The next agent reads them, fills its context with noise, and produces more of the same. Textual content in a codebase governed by agents needs to be *tight*: what is not obvious from the code, and what it does. Not how it got there.

This applies to PRs, to comments, and to the agent's own intermediate work.

---

## What follows from these observations

| Observation | Implication |
|---|---|
| Attention is scarce | Route review by structural consequence, not by code volume |
| Tests miss structure | Add deterministic structural checks (dep rules, API diff, schema diff) |
| Architectural weight varies | Classify code into red, blue, and gray zones; treat them differently |
| Slop feeds slop | Keep agent-readable text terse; reject verbose generated descriptions |

These four implications, taken together, are agent-redline.

---

## What agent-redline is not trying to do

- Make all generated code "good." Most code doesn't need to be good; it needs to work and be replaceable.
- Replace human judgment about modeling. Modeling stays human. The system protects modeling decisions, it doesn't make them.
- Catch correctness bugs. Tests do that.
- Prevent agents from being wrong locally. Local wrongness is fine in blue zones.
- Be a security perimeter. It surfaces structural risk; it does not enforce trust.

The product is a small one with a clear boundary: classify changes by architectural consequence, route attention accordingly, enforce the rules that prevent local LLM shortcuts from becoming long-term structural debt.

# Contributing to agent-redline

Thanks for thinking about contributing. agent-redline is small enough that the bar is "is this useful to people other than you?" rather than a formal RFC process.

## What's most welcome

- **A new language extension.** `extensions/jvm-archunit/` and `extensions/python/` are the references. The shape is documented in [`docs/EXTENSIONS.md`](docs/EXTENSIONS.md). Node + dependency-cruiser and Go + go-arch-lint are the most-requested next stacks.
- **Bug reports** with a minimal reproducible example. Open an issue.
- **Polish on the docs.** If something in [`docs/`](docs/) reads as overconfident, vague, or wrong, fix it.
- **Telling us a real-world repo this skill helped (or didn't help) on.** Even a one-line note on an issue is useful. We're tuning defaults on a small sample.

## What requires more discussion before you start

- **Schema changes.** [`core/schema/agent-policy.schema.json`](core/schema/agent-policy.schema.json) is consumed by every install. Open an issue first. The principle is *the schema describes only what the reporter does* — see [`docs/DECISIONS.md`](docs/DECISIONS.md).
- **Reporter behavior changes.** Verdicts and exit codes are part of the public contract. Same — issue first.
- **Bootstrap-mode skill text.** Heavily smoke-tested; any change to the loop structure or the hard rules deserves a discussion before a PR.

## Process

1. **Open an issue first** for anything beyond a typo or obvious bug.
2. **Branch from `main`.**
3. **Run the local test layers before pushing:** `bash tests/run-all.sh`. The CI runs the same nine layers; passing locally saves a round trip.
4. **Keep PRs small.** One concern per PR.
5. **A feature is not done until the demo proves it end-to-end.** If you're adding a user-facing capability (one that would appear in SPEC §14 / §15.1), add a corresponding scenario under `demo-source/pr-scenarios/<name>/` in the same change. Unit tests verify segments of the pipeline; only the live demo on `agent-redline-demo` verifies the chain. See [`docs/DECISIONS.md`](docs/DECISIONS.md) for the full rationale.
6. **Update the relevant docs** when changing behavior. `docs/SPEC.md` §19 has a changelog.

## What you don't need to do

- Sign a CLA (there isn't one).
- Match a specific commit-message format. Just write what you did and why.
- Add yourself to a contributors file (we don't keep one).

## Code of Conduct

This project follows the [Contributor Covenant 2.1](CODE_OF_CONDUCT.md). By participating you agree to abide by it.

## License

agent-redline is MIT-licensed. By contributing, you agree your contribution is licensed under the same.

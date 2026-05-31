# Security policy

agent-redline is a governance/policy tool. It does not handle credentials, network requests, or untrusted input at runtime — the reporter reads files the user controls (a YAML policy, a JUnit XML the user's build wrote, a list of file paths) and produces text output. The attack surface is small.

That said, if you find:

- A way to make the reporter execute arbitrary code via crafted YAML or a malicious JUnit XML
- A path-traversal or filesystem-escape in any of the bash templates the framework ships
- A way for a malicious `agent-policy.yaml` to cause harm beyond producing wrong verdicts (e.g., privilege escalation, data exfiltration)
- A vulnerability in any vendored Python the reporter ships

— please report it privately rather than opening a public issue.

## How to report

Use GitHub's [private vulnerability reporting](https://github.com/rore/agent-redline/security/advisories/new) for this repo.

Please include:

- The repo and tag/commit affected
- A minimal reproducible example
- What you expected vs. what happened
- Your assessment of impact

## Response

Best-effort. This is a side project, not a vendor product. I'll acknowledge within ~7 days, fix critical issues within ~30 days, and disclose with credit unless you ask otherwise. If you don't hear back, ping me on [GitHub](https://github.com/rore).

## Supported versions

The latest tagged release on `main` is supported. Older tags receive no backports.

## Out of scope

- Issues in language-extension *third-party* tools (ArchUnit, dependency-cruiser, etc.) — report those upstream.
- Security of consumer repos that adopt agent-redline. agent-redline does not change a consumer repo's security posture; it adds review-routing rules.
- Concerns about the framework being "circumventable" by an agent that ignores the operating-mode skill text. The framework is opinionated guidance + deterministic CI checks, not a sandbox; agents that ignore both are out of scope. The CI checks are the load-bearing piece.

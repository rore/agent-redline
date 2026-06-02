#!/usr/bin/env python3
"""
tests/scaffold-ci-e2e/_extract-pushmode.py

Extract executable bash from the push-mode workflow in
extensions/python/scaffold.md so check-scaffold-ci-e2e.sh can run it
against a fixture.

Two extraction modes:
  --reporter (default) — the `run: |` of the "Run reporter" step
  --summary             — the `run: |` of the "Write verdict to job
                          summary" step
  --check-run           — the `run: |` of the "Post agent-redline
                          Check Run" step

Strategy: find the yaml fenced block that mentions both
`agent-redline-report.py` AND `github.event.before` (the push-mode
diff signal). Then pull the bash from the relevant `run: |` step.

Args:
    scaffold-path
    [--reporter | --summary]
"""
from __future__ import annotations

import re
import sys
from pathlib import Path


def find_push_block(text: str) -> str | None:
    blocks = re.findall(
        r"^```yaml\s*\n(.*?)\n```\s*$",
        text,
        flags=re.DOTALL | re.MULTILINE,
    )
    for b in blocks:
        if "agent-redline-report.py" in b and "github.event.before" in b:
            return b
    return None


def extract_run_body(yaml_block: str, needle: str) -> str | None:
    """Find the `run: |` step whose body contains `needle`. Return the
    body with the leading indent stripped."""
    runs = list(re.finditer(
        r"^( {6,8})run: \|\s*\n((?:\1  .*\n|\s*\n)+)",
        yaml_block,
        flags=re.MULTILINE,
    ))
    for m in runs:
        body = m.group(2)
        if needle in body:
            indent = m.group(1) + "  "
            lines: list[str] = []
            for line in body.splitlines():
                if line.startswith(indent):
                    lines.append(line[len(indent):])
                elif line.strip() == "":
                    lines.append("")
                else:
                    break
            return "\n".join(lines).rstrip() + "\n"
    return None


def main() -> int:
    if len(sys.argv) < 2 or len(sys.argv) > 3:
        print(f"usage: {sys.argv[0]} <scaffold.md> [--reporter|--summary]", file=sys.stderr)
        return 1
    scaffold = Path(sys.argv[1])
    mode = sys.argv[2] if len(sys.argv) == 3 else "--reporter"

    text = scaffold.read_text(encoding="utf-8")
    push_block = find_push_block(text)
    if push_block is None:
        print("ERROR: no push-mode block (must contain both 'agent-redline-report.py' and 'github.event.before')", file=sys.stderr)
        return 1

    if mode == "--reporter":
        # The reporter run-block is identified by the reporter call.
        body = extract_run_body(push_block, "agent-redline-report.py")
        if body is None:
            print("ERROR: no `run: |` step in push-mode block contains the reporter call", file=sys.stderr)
            return 1
    elif mode == "--summary":
        # The summary step writes to $GITHUB_STEP_SUMMARY.
        body = extract_run_body(push_block, '$GITHUB_STEP_SUMMARY')
        if body is None:
            print("ERROR: no `run: |` step in push-mode block writes to $GITHUB_STEP_SUMMARY", file=sys.stderr)
            return 1
    elif mode == "--check-run":
        # The Check Run step posts to /check-runs via gh api.
        body = extract_run_body(push_block, "/check-runs")
        if body is None:
            print("ERROR: no `run: |` step in push-mode block posts to /check-runs", file=sys.stderr)
            return 1
    else:
        print(f"ERROR: unknown mode {mode!r}; expected --reporter, --summary, or --check-run", file=sys.stderr)
        return 1

    print(body, end="")
    return 0


if __name__ == "__main__":
    sys.exit(main())


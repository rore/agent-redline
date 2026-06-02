#!/usr/bin/env python3
"""
tests/scaffold-ci-e2e/_extract-pushmode.py

Extract the push-mode reporter `run: |` shell block from
extensions/python/scaffold.md. Print the bash to stdout. Used by
check-scaffold-ci-e2e.sh.

Strategy: find the yaml fenced block that mentions both
`agent-redline-report.py` AND `github.event.before` (the push-mode
diff signal). Then pull the bash from the `run: |` step that contains
the reporter call.

Args:
    scaffold-path
"""
from __future__ import annotations

import re
import sys
from pathlib import Path


def main() -> int:
    if len(sys.argv) != 2:
        print(f"usage: {sys.argv[0]} <scaffold.md>", file=sys.stderr)
        return 1
    scaffold = Path(sys.argv[1])
    text = scaffold.read_text(encoding="utf-8")

    # Find every yaml fenced block.
    blocks = re.findall(
        r"^```yaml\s*\n(.*?)\n```\s*$",
        text,
        flags=re.DOTALL | re.MULTILINE,
    )

    push_block = None
    for b in blocks:
        if "agent-redline-report.py" in b and "github.event.before" in b:
            push_block = b
            break

    if push_block is None:
        print("ERROR: no push-mode block (must contain both 'agent-redline-report.py' and 'github.event.before')", file=sys.stderr)
        return 1

    # Pull the body of the `run: |` step that contains the reporter.
    # The pattern: an indented `name:` or `run: |` line, then continuation
    # lines indented strictly further than the `run:` line.
    runs = list(re.finditer(
        r"^( {6,8})run: \|\s*\n((?:\1  .*\n|\s*\n)+)",
        push_block,
        flags=re.MULTILINE,
    ))

    chosen_body: str | None = None
    for m in runs:
        body = m.group(2)
        if "agent-redline-report.py" in body:
            indent = m.group(1) + "  "
            # Strip the indent prefix from each line.
            lines: list[str] = []
            for line in body.splitlines():
                if line.startswith(indent):
                    lines.append(line[len(indent):])
                elif line.strip() == "":
                    lines.append("")
                else:
                    # Should not happen given regex, but safe.
                    break
            chosen_body = "\n".join(lines).rstrip() + "\n"
            break

    if chosen_body is None:
        print("ERROR: no `run: |` step in push-mode block contains the reporter call", file=sys.stderr)
        return 1

    print(chosen_body, end="")
    return 0


if __name__ == "__main__":
    sys.exit(main())

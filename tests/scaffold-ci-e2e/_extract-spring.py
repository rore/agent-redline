#!/usr/bin/env python3
"""
tests/scaffold-ci-e2e/_extract-spring.py

Extract the reporter `run: |` shell block from
extensions/spring-archunit/scaffold.md (the §6 OpenAPI block — that's
where the canonical reporter step lives in the Spring scaffold). Print
the bash to stdout. Used by check-spring-ci-e2e.sh.

Strategy mirrors _extract-pushmode.py: find the yaml fenced block that
contains 'agent-redline-report.py', then pull the bash from the
`run: |` step that contains the reporter call.

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

    blocks = re.findall(
        r"^```yaml\s*\n(.*?)\n```\s*$",
        text,
        flags=re.DOTALL | re.MULTILINE,
    )

    target_block = None
    for b in blocks:
        if "agent-redline-report.py" in b:
            target_block = b
            break

    if target_block is None:
        print("ERROR: no yaml block containing the reporter call found", file=sys.stderr)
        return 1

    runs = list(re.finditer(
        r"^( {6,8})run: \|\s*\n((?:\1  .*\n|\s*\n)+)",
        target_block,
        flags=re.MULTILINE,
    ))

    chosen_body: str | None = None
    for m in runs:
        body = m.group(2)
        if "agent-redline-report.py" in body:
            indent = m.group(1) + "  "
            lines: list[str] = []
            for line in body.splitlines():
                if line.startswith(indent):
                    lines.append(line[len(indent):])
                elif line.strip() == "":
                    lines.append("")
                else:
                    break
            chosen_body = "\n".join(lines).rstrip() + "\n"
            break

    if chosen_body is None:
        print("ERROR: no `run: |` step contains the reporter call", file=sys.stderr)
        return 1

    print(chosen_body, end="")
    return 0


if __name__ == "__main__":
    sys.exit(main())

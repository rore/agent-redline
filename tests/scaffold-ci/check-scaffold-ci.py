#!/usr/bin/env python3
"""
tests/scaffold-ci/check-scaffold-ci.py

Pattern check: any scaffold.md YAML block that runs the reporter
(`python scripts/agent-redline-report.py`) MUST follow the
exit-code-capture pattern. Catches the class of bug Pallium hit:
agent copies the scaffold's reporter step verbatim, GitHub Actions
runs the block under `bash -e`, the reporter exits 1 on a normal
RED verdict, the step fails, the sticky-comment + enforce steps
are skipped, and shadow-mode signal silently disappears.

The pattern, expressed structurally:

  - the run-block calling the reporter MUST set `set +e` first
  - the run-block MUST capture `EXIT=$?` (or equivalent) AFTER the
    reporter call so subsequent steps see the value via outputs
  - the same yaml block MUST include a sticky-comment step
    (uses: marocchino/sticky-pull-request-comment)
  - the same yaml block MUST include an enforce step that gates on
    exit code 2 specifically

This is a narrow check on a narrow piece of skill content (scaffold
CI snippets), not a generic YAML linter. It exists because the
pattern matters and the cost of getting it wrong is silent failure
mode in shadow-mode CI — exactly what bit Pallium.

Exit codes:
  0 — every reporter run-block follows the pattern
  1 — script error
  2 — at least one block is missing required pattern elements
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent

SCAFFOLDS = [
    "extensions/spring-archunit/scaffold.md",
    "extensions/python/scaffold.md",
]

# A reporter-calling run-block is identified by this needle in any
# yaml fenced block.
REPORTER_NEEDLE = "python scripts/agent-redline-report.py"

# Required pattern elements. Each is a substring search inside the
# same yaml block (not the whole file) — they need to coexist in the
# same workflow snippet so a copy-paster gets the working pattern.
REQUIRED_ELEMENTS = [
    ("set +e",
     "must run `set +e` to override bash's default abort-on-non-zero"),
    ("EXIT=$?",
     "must capture the reporter's exit code in EXIT"),
    ("exit_code=$EXIT",
     "must publish the captured exit code via $GITHUB_OUTPUT for the enforce step"),
    ("marocchino/sticky-pull-request-comment",
     "must include the sticky-comment step so the verdict reaches the PR"),
    ('"$EXIT" == "2"',
     "must include the enforce step that gates on exit code 2 (binding-mode hard fail)"),
]


def extract_yaml_blocks(text: str) -> list[tuple[int, str]]:
    pattern = re.compile(r"^```yaml\s*\n(.*?)\n```\s*$", re.DOTALL | re.MULTILINE)
    return [(i, m.group(1)) for i, m in enumerate(pattern.finditer(text))]


def block_has_actual_set_plus_e(block: str) -> bool:
    """`set +e` must appear as an executable line, not in a comment that
    explains it. Match `set +e` only when it's the entire trimmed line."""
    for line in block.splitlines():
        stripped = line.strip()
        if stripped == "set +e":
            return True
    return False


def main() -> int:
    failures: list[str] = []
    blocks_checked = 0
    files_seen = 0

    for rel in SCAFFOLDS:
        path = REPO_ROOT / rel
        if not path.exists():
            print(f"skip  {rel} (file not present)")
            continue
        files_seen += 1
        text = path.read_text(encoding="utf-8")

        for idx, block_text in extract_yaml_blocks(text):
            if REPORTER_NEEDLE not in block_text:
                continue
            blocks_checked += 1
            # `set +e` is checked structurally — it must be an actual
            # executable line, not just mentioned in a comment.
            if not block_has_actual_set_plus_e(block_text):
                failures.append(
                    f"{rel} block#{idx}: must run `set +e` as an executable line "
                    "(found only in prose/comments) to override bash's default abort-on-non-zero"
                )
            for needle, message in REQUIRED_ELEMENTS:
                if needle == "set +e":
                    continue  # handled above
                if needle not in block_text:
                    failures.append(f"{rel} block#{idx}: {message}")

    print()
    print(f"scanned {files_seen} scaffold(s); {blocks_checked} reporter run-block(s) validated.")
    if failures:
        for f in failures:
            print(f"FAIL  {f}", file=sys.stderr)
        print(f"\n{len(failures)} pattern violation(s).", file=sys.stderr)
        return 2
    print("all reporter run-blocks follow the exit-code-capture pattern.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

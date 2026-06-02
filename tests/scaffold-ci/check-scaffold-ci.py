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

Two flow modes; each block must follow ONE consistent pattern:

  PR-driven flow (`on: pull_request:`):
    - `set +e` (executable line, not just a comment)
    - `EXIT=$?` capture
    - publish `exit_code=$EXIT` to $GITHUB_OUTPUT
    - sticky-comment step (uses: marocchino/sticky-pull-request-comment)
    - enforce step gating on `"$EXIT" == "2"`

  push-driven flow (`on: push:`):
    - `set +e` (executable line)
    - `EXIT=$?` capture
    - publish `exit_code=$EXIT` to $GITHUB_OUTPUT
    - NO sticky-comment step (no PR to comment on)
    - $GITHUB_STEP_SUMMARY append step (run-page surface)
    - reporter call passes `--flow-mode push` so checkpoint text is
      rendered as a review obligation on the commit (CODEOWNER /
      label phrasing doesn't apply on a direct push)
    - enforce step gates on `"$EXIT" != "0"` so GitHub's default
      workflow-failure email notification fires for both RED warnings
      and BOUNDARY_VIOLATION hard fails. agent-redline ships as its
      own workflow file; failing it does not fail other workflows in
      the repo.

Mode is detected from the same yaml block: `pull_request` vs `push:`
appears in the trigger / changed-files git diff invocation.

Exit codes:
  0 — every reporter run-block follows its mode's pattern
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

REPORTER_NEEDLE = "python scripts/agent-redline-report.py"


def extract_yaml_blocks(text: str) -> list[tuple[int, str]]:
    pattern = re.compile(r"^```yaml\s*\n(.*?)\n```\s*$", re.DOTALL | re.MULTILINE)
    return [(i, m.group(1)) for i, m in enumerate(pattern.finditer(text))]


def has_actual_set_plus_e(block: str) -> bool:
    """`set +e` must be an executable line, not in a comment."""
    for line in block.splitlines():
        if line.strip() == "set +e":
            return True
    return False


def detect_mode(block: str) -> str:
    """Return 'pr', 'push', or 'unknown' based on signals in the block.

    Heuristics in order:
      1. `on: pull_request:` or `pull_request.base.sha` -> PR mode
      2. `on: push:` or `github.event.before` or `github.sha` -> push mode
      3. fallback: presence of marocchino sticky-comment is a strong PR
         signal; absence + reporter-call is a push signal
    """
    if "pull_request" in block and ("base.sha" in block or "head.sha" in block):
        return "pr"
    if "github.event.before" in block or "on: push" in block:
        return "push"
    if "pull_request" in block:
        return "pr"
    if "marocchino/sticky-pull-request-comment" in block:
        return "pr"
    return "push"  # default — push mode is more permissive (no sticky required)


def required_for_mode(mode: str) -> list[tuple[str, str]]:
    """Substring -> error message. Same elements for both modes EXCEPT
    sticky-comment (PR only) and enforce-gate threshold."""
    common = [
        ("EXIT=$?",
         "must capture the reporter's exit code in EXIT"),
        ("exit_code=$EXIT",
         "must publish the captured exit code via $GITHUB_OUTPUT for the enforce step"),
        ("git diff --numstat",
         "must emit `git diff --numstat` for per-file line counts (passed via --lines-per-file) so policy.excludes applies to prSize"),
        ("--lines-per-file",
         "must pass --lines-per-file to the reporter; without it, excluded files (generated/, vendored/, etc.) silently inflate the size budget"),
    ]
    if mode == "pr":
        return common + [
            ("marocchino/sticky-pull-request-comment",
             "PR-driven flow must include the sticky-comment step so the verdict reaches the PR"),
            ('"$EXIT" == "2"',
             "PR-driven flow must include an enforce step gating on exit code 2 (binding-mode hard fail; exit 1 surfaces in the comment, doesn't block)"),
        ]
    # push mode
    return common + [
        ('>> "$GITHUB_STEP_SUMMARY"',
         "push-driven flow must append the verdict to $GITHUB_STEP_SUMMARY (`>> \"$GITHUB_STEP_SUMMARY\"`) so it appears on the run summary page (the surface the failure-notification email lands on)"),
        ("--flow-mode push",
         "push-driven flow must pass `--flow-mode push` to the reporter so checkpoint text is rendered as a review obligation on the commit (CODEOWNER / label phrasing doesn't apply on a direct push)"),
        ('"$EXIT" != "0"',
         "push-driven flow must include an enforce step gating on `\"$EXIT\" != \"0\"` (both RED warnings and BOUNDARY_VIOLATION hard fails), so GitHub's default workflow-failure email notification fires for the user who triggered the run"),
    ]


def main() -> int:
    failures: list[str] = []
    blocks_checked = 0
    files_seen = 0
    pr_blocks = 0
    push_blocks = 0

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
            mode = detect_mode(block_text)
            if mode == "pr":
                pr_blocks += 1
            else:
                push_blocks += 1

            if not has_actual_set_plus_e(block_text):
                failures.append(
                    f"{rel} block#{idx} ({mode}): must run `set +e` as an executable line "
                    "(found only in prose/comments) to override bash's default abort-on-non-zero"
                )

            # push-mode must NOT include a PR-only sticky-comment surface — the
            # block doesn't fail the test for it, but if a push-mode block has
            # marocchino in it, that's a structural confusion worth flagging.
            if mode == "push" and "marocchino/sticky-pull-request-comment" in block_text:
                failures.append(
                    f"{rel} block#{idx} (push): contains marocchino sticky-comment but "
                    "is detected as push-mode (no PR to comment on). Either change the "
                    "trigger to pull_request: or remove the sticky-comment step."
                )

            for needle, message in required_for_mode(mode):
                if needle not in block_text:
                    failures.append(f"{rel} block#{idx} ({mode}): {message}")

    print()
    print(f"scanned {files_seen} scaffold(s); {blocks_checked} reporter run-block(s) validated "
          f"({pr_blocks} PR-driven, {push_blocks} push-driven).")
    if failures:
        for f in failures:
            print(f"FAIL  {f}", file=sys.stderr)
        print(f"\n{len(failures)} pattern violation(s).", file=sys.stderr)
        return 2
    print("all reporter run-blocks follow their flow-mode pattern.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

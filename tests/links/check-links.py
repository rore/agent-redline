#!/usr/bin/env python3
"""
tests/links/check-links.py

Walks every Markdown file in the repo (excluding .local/ and the demo
sub-tree's vendored copies that get regenerated) and verifies that every
relative link target exists.

Catches the bug we hit during demo standup: stale skill-file references
to docs/EXTENSIONS.md, docs/CI_INTEGRATION.md, etc. — paths that didn't
exist in the consuming repo.

Skipped:
  - http://, https://, mailto: links
  - In-document anchors (#section)
  - Targets the script can't statically resolve (e.g., GitHub absolute URLs)
  - Files under .local/ (gitignored, local notes)

Exit codes:
  0 — every link resolves
  2 — at least one broken link
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urlparse


REPO_ROOT = Path(__file__).resolve().parent.parent.parent

# Directories to skip entirely.
SKIP_DIRS = {".git", ".local", "node_modules", "__pycache__", "build", "bin"}

# Markdown link pattern: [text](target). Allows nested brackets in text.
LINK_RE = re.compile(r"!?\[(?:[^\[\]]|\[[^\]]*\])*\]\(([^)]+)\)")


def iter_markdown_files() -> list[Path]:
    files = []
    for path in REPO_ROOT.rglob("*.md"):
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        # Reporter golden-fixture snapshots are byte-for-byte recordings of
        # PR-comment output. Their relative links resolve against the
        # consuming repo (where the comment is rendered), not against the
        # fixture directory inside this repo.
        if path.name == "expected-comment.md" and "reporter" in path.parts:
            continue
        files.append(path)
    return files


def is_external(target: str) -> bool:
    parsed = urlparse(target)
    return parsed.scheme in ("http", "https", "mailto", "ftp")


def is_pure_anchor(target: str) -> bool:
    return target.startswith("#")


def strip_anchor(target: str) -> str:
    # Remove trailing #anchor for resolution purposes.
    if "#" in target:
        return target.split("#", 1)[0]
    return target


def check_file(md_path: Path) -> list[str]:
    """Return list of broken-link descriptions for this file."""
    text = md_path.read_text(encoding="utf-8", errors="replace")

    # Strip fenced code blocks (``` ... ```) so links inside them aren't
    # parsed as real links. Same for indented code blocks (4+ spaces) is
    # not bothered with — too many false positives.
    stripped_lines = []
    in_fence = False
    for line in text.splitlines(keepends=True):
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
            stripped_lines.append("\n")  # keep line numbers stable
            continue
        if in_fence:
            stripped_lines.append("\n")
        else:
            stripped_lines.append(line)
    text_no_code = "".join(stripped_lines)

    broken: list[str] = []
    for match in LINK_RE.finditer(text_no_code):
        target = match.group(1).strip()
        if not target:
            continue
        if is_external(target):
            continue
        if is_pure_anchor(target):
            continue
        # Some markdown writers escape spaces as %20; normalize.
        path_part = strip_anchor(target).replace("%20", " ")
        if not path_part:
            continue
        # Resolve relative to the markdown file's directory.
        resolved = (md_path.parent / path_part).resolve()
        # Allow targets that resolve outside REPO_ROOT only if they exist
        # (e.g., absolute paths starting with /); otherwise broken.
        if not resolved.exists():
            line_no = text_no_code[: match.start()].count("\n") + 1
            broken.append(f"{md_path.relative_to(REPO_ROOT)}:{line_no}: '{target}' -> {resolved} (missing)")
    return broken


def main() -> int:
    files = iter_markdown_files()
    if not files:
        print("error: no markdown files found", file=sys.stderr)
        return 2

    all_broken: list[str] = []
    for md in sorted(files):
        broken = check_file(md)
        if broken:
            all_broken.extend(broken)
        else:
            # Quiet on clean files; print nothing.
            pass

    if all_broken:
        for line in all_broken:
            print("BROKEN  " + line, file=sys.stderr)
        print(f"\n{len(all_broken)} broken link(s) across {len(files)} markdown file(s).", file=sys.stderr)
        return 2

    print(f"all {len(files)} markdown file(s) have valid relative links.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

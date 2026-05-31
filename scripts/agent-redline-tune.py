#!/usr/bin/env python
"""
agent-redline-tune — zone-calibration helper.

Computes per-zone-entry firing rates for a batch of past PRs against the
current policy. Used during the first weeks of shadow mode to confirm
that the policy's hypothesis matches the team's actual PR distribution.

Input formats (pick one):

    --pr-dir <dir>
        A directory of plain-text files; each file is one PR's
        newline-separated list of changed files. File name is used
        as the PR identifier. This is the format produced by:

            gh pr list --state merged --limit 30 --json number \
                --jq '.[].number' | while read n; do
              gh pr diff "$n" --name-only > "pr-$n.txt"
            done

    --pr-list <file>
        A file with one PR identifier per line plus changed files,
        separated by tabs. (Produced by some custom CI exports.)
        Format: <pr-id>\t<file>\t<file>\t...

Output: a markdown report ranking each red/grayWatch entry by firing rate,
plus an overall verdict-distribution summary.

Usage:
    python scripts/agent-redline-tune.py --policy agent-policy.yaml \
        --pr-dir /path/to/prs

The script does not need network access; it reads the policy and the
pre-collected PR file-lists. Producing the file-lists with `gh pr diff`
is a one-time step the user runs.

This is the v0.1 manual version of frequency-aware tuning. Automated
firing-rate tracking inside the reporter is roadmap.
"""

from __future__ import annotations

import argparse
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from core.reporter.reporter import (  # noqa: E402
    Diff,
    classify,
    classify_files,
    load_policy,
    matches,
)


def load_prs_from_dir(pr_dir: Path) -> dict[str, list[str]]:
    """Read each *.txt file in pr_dir as one PR's changed-files list."""
    if not pr_dir.is_dir():
        raise SystemExit(f"error: --pr-dir {pr_dir} is not a directory")
    out: dict[str, list[str]] = {}
    for f in sorted(pr_dir.iterdir()):
        if not f.is_file():
            continue
        if f.suffix not in (".txt", ".list", ""):
            continue
        files = [
            line.strip()
            for line in f.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.startswith("#")
        ]
        if files:
            out[f.stem] = files
    return out


def load_prs_from_list(pr_list: Path) -> dict[str, list[str]]:
    """Each line: <pr-id>\\t<file>\\t<file>\\t..."""
    out: dict[str, list[str]] = {}
    for line in pr_list.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        parts = line.split("\t")
        if len(parts) < 2:
            continue
        out[parts[0]] = [p for p in parts[1:] if p]
    return out


def firing_rates(
    prs: dict[str, list[str]],
    policy: dict[str, Any],
) -> dict[str, dict[tuple[str, str], int]]:
    """
    For each zone (red/blue/gray/grayWatch) return a count of how many PRs
    touched at least one file matching each policy entry.

    Returned shape:
      {
        "red":       {(path, reason): count, ...},
        "grayWatch": {(path, reason): count, ...},
        ...
      }
    """
    counts: dict[str, dict[tuple[str, str], int]] = {
        "red": defaultdict(int),
        "blue": defaultdict(int),
        "grayWatch": defaultdict(int),
    }
    zones = policy.get("zones", {}) or {}
    for zone in ("red", "blue", "grayWatch"):
        entries = zones.get(zone, []) or []
        for pr_files in prs.values():
            for entry in entries:
                key = (entry["path"], entry.get("reason", ""))
                if any(matches(f, entry["path"]) for f in pr_files):
                    counts[zone][key] += 1
                    # Don't break — count each entry independently per PR.
    return counts


def verdict_distribution(prs: dict[str, list[str]], policy: dict[str, Any]) -> dict[str, int]:
    """Count verdict types across the PR set."""
    dist: dict[str, int] = defaultdict(int)
    for files in prs.values():
        diff = Diff(changed_files=files, files_changed=len(files), lines_changed=0)
        v = classify(policy, diff)
        dist[v.verdict] += 1
    return dict(dist)


def classify_rate(rate: float) -> str:
    """Recommendation tier for a firing rate."""
    if rate >= 0.80:
        return "TOO BROAD — most PRs touch this. Downgrade to grayWatch or split."
    if rate >= 0.50:
        return "PROBABLY TOO BROAD — fires on a majority. Try to split the path."
    if rate >= 0.30:
        return "AMBIGUOUS — may be split-able; re-evaluate after window 2."
    if rate >= 0.05:
        return "PROBABLY RIGHT — fires on a minority of PRs."
    return "RARE — confirm this is the structural surface you wanted to flag, not dead code."


def render_markdown(
    counts: dict[str, dict[tuple[str, str], int]],
    dist: dict[str, int],
    n_prs: int,
) -> str:
    lines: list[str] = []
    lines.append(f"# agent-redline tuning report — {n_prs} PR(s)")
    lines.append("")
    lines.append("Firing rate per zone entry. Red entries that fire on most PRs are alert-fatigue traps and should move to grayWatch or split.")
    lines.append("")

    # Verdict distribution
    lines.append("## Verdict distribution")
    lines.append("")
    lines.append("| Verdict | PRs | Share |")
    lines.append("|---|---:|---:|")
    for verdict, n in sorted(dist.items(), key=lambda x: -x[1]):
        share = (n / n_prs * 100) if n_prs else 0
        lines.append(f"| {verdict} | {n} | {share:.0f}% |")
    lines.append("")

    # Per-zone tables
    for zone_label, zone_key in (("Red", "red"), ("Gray-watch", "grayWatch"), ("Blue", "blue")):
        entries = counts.get(zone_key, {})
        if not entries:
            continue
        lines.append(f"## {zone_label} zone — firing rates")
        lines.append("")
        lines.append("| Path | Reason | PRs hit | Rate | Recommendation |")
        lines.append("|---|---|---:|---:|---|")
        rows = sorted(entries.items(), key=lambda kv: -kv[1])
        for (path, reason), n in rows:
            rate = (n / n_prs) if n_prs else 0.0
            rec = classify_rate(rate) if zone_key == "red" else ""
            lines.append(f"| `{path}` | {reason} | {n} | {rate*100:.0f}% | {rec} |")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Compute zone firing rates against a policy")
    p.add_argument("--policy", required=True, type=Path, help="Path to agent-policy.yaml")
    src = p.add_mutually_exclusive_group(required=True)
    src.add_argument("--pr-dir", type=Path, help="Directory of *.txt files, one per PR")
    src.add_argument("--pr-list", type=Path, help="Single file with <pr-id>\\t<file>... per line")
    p.add_argument("--out", type=Path, help="Write report to this file (default: stdout)")
    args = p.parse_args(argv)

    policy = load_policy(args.policy)

    if args.pr_dir:
        prs = load_prs_from_dir(args.pr_dir)
    else:
        prs = load_prs_from_list(args.pr_list)

    if not prs:
        sys.stderr.write("error: no PRs found in input\n")
        return 1

    counts = firing_rates(prs, policy)
    dist = verdict_distribution(prs, policy)
    report = render_markdown(counts, dist, len(prs))

    if args.out:
        args.out.write_text(report, encoding="utf-8")
        print(f"wrote {args.out}")
    else:
        print(report)
    return 0


if __name__ == "__main__":
    sys.exit(main())

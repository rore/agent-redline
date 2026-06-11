"""
tests/reporter/check-reporter.py

Runs the agent-redline reporter against each fixture and verifies the
output matches the recorded expectations.

Each fixture directory contains:
  policy.yaml or symlink/copy of _common-policy.yaml
  changed-files.txt           # newline-separated paths
  lines-changed.txt           # optional; integer scalar (fallback)
  lines-per-file.txt          # optional; `git diff --numstat` format
                              #   (added<TAB>deleted<TAB>path).
                              #   When present, excludes are applied
                              #   to size accounting.
  diff-unified.patch          # optional; `git diff --unified=0` output.
                              #   When present, parsed into added lines
                              #   per file and surfaced on the Diff
                              #   dataclass for Phase-4 suppression
                              #   detection. No semantic effect yet.
  archunit.xml                # optional
  api-spec-base.yaml          # optional; OpenAPI spec at base SHA
  api-spec-head.yaml          # optional; OpenAPI spec at head SHA
  pr-labels.txt               # optional; one label per line
  codeowners.txt              # optional; one approver per line
  expected-verdict.json       # required
  expected-comment.md         # required

Usage:
  python tests/reporter/check-reporter.py             # run and verify
  python tests/reporter/check-reporter.py --update    # regenerate expected files

Exit codes:
  0 — all fixtures match
  1 — script error
  2 — at least one fixture has an output mismatch
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT))

from core.reporter.reporter import (  # noqa: E402
    classify, load_policy, load_diff_from_files, load_archunit_xml,
    diff_openapi_specs, render_markdown,
)


FIXTURE_ROOT = REPO_ROOT / "tests" / "reporter"


def find_fixtures() -> list[Path]:
    return sorted(p for p in FIXTURE_ROOT.iterdir() if p.is_dir())


def read_lines(path: Path) -> list[str]:
    if not path.exists():
        return []
    return [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def resolve_policy(fixture: Path) -> Path:
    own = fixture / "policy.yaml"
    if own.exists():
        return own
    return FIXTURE_ROOT / "_common-policy.yaml"


def read_lines_changed(fixture: Path) -> int:
    path = fixture / "lines-changed.txt"
    if not path.exists():
        return 0
    return int(path.read_text(encoding="utf-8").strip() or "0")


def run_fixture(fixture: Path) -> tuple[dict, str]:
    policy = load_policy(resolve_policy(fixture))
    lines_per_file_path = fixture / "lines-per-file.txt"
    diff_unified_path = fixture / "diff-unified.patch"
    diff = load_diff_from_files(
        fixture / "changed-files.txt",
        read_lines_changed(fixture),
        lines_per_file_path=lines_per_file_path if lines_per_file_path.exists() else None,
        diff_unified_path=diff_unified_path if diff_unified_path.exists() else None,
    )
    archunit = load_archunit_xml(fixture / "archunit.xml")
    pr_labels = read_lines(fixture / "pr-labels.txt")
    approvals = read_lines(fixture / "codeowners.txt")

    # Optional flow-mode signal — affects render_markdown's checkpoint
    # satisfier text (push-mode drops the CODEOWNER/label phrasing since
    # neither mechanism applies on a direct push). Default 'pr' preserves
    # existing fixtures unchanged.
    flow_mode = "pr"
    flow_path = fixture / "flow-mode.txt"
    if flow_path.exists():
        candidate = flow_path.read_text(encoding="utf-8").strip()
        if candidate in ("pr", "push"):
            flow_mode = candidate

    # New (v0.2): a fixture may carry a boundary-violations.json file to exercise
    # the json-violations format end-to-end. Mutually exclusive with archunit.xml.
    boundary_report = None
    boundary_format = None
    bv_path = fixture / "boundary-violations.json"
    if bv_path.exists():
        if archunit is not None:
            raise ValueError(
                f"{fixture.name}: fixture has both archunit.xml and boundary-violations.json; "
                "pick one"
            )
        boundary_report = bv_path.read_text(encoding="utf-8")
        boundary_format = "json-violations"

    api_spec_diff = None
    base_spec = fixture / "api-spec-base.yaml"
    head_spec = fixture / "api-spec-head.yaml"
    if base_spec.exists() or head_spec.exists():
        base_text = base_spec.read_text(encoding="utf-8") if base_spec.exists() else ""
        head_text = head_spec.read_text(encoding="utf-8") if head_spec.exists() else ""
        api_spec_diff = diff_openapi_specs(base_text, head_text)

    verdict = classify(
        policy, diff,
        archunit_xml=archunit,
        boundary_report=boundary_report,
        boundary_format=boundary_format,
        api_spec_diff=api_spec_diff,
        pr_labels=pr_labels,
        codeowner_approvals=approvals,
    )
    return verdict.to_dict(), render_markdown(verdict, flow_mode=flow_mode)


def normalize_json(s: str) -> str:
    return json.dumps(json.loads(s), indent=2, sort_keys=True) + "\n"


def main(argv: list[str] | None = None) -> int:
    update = "--update" in (argv or sys.argv[1:])

    fixtures = find_fixtures()
    if not fixtures:
        print("no fixtures found", file=sys.stderr)
        return 1

    failures: list[str] = []

    for fixture in fixtures:
        name = fixture.name
        if name.startswith("_"):
            continue  # shared resources; not a fixture itself
        if not (fixture / "changed-files.txt").exists():
            failures.append(f"FAIL  {name}: missing changed-files.txt")
            continue

        try:
            verdict_dict, comment = run_fixture(fixture)
        except Exception as e:
            failures.append(f"FAIL  {name}: reporter error: {e}")
            continue

        verdict_text = json.dumps(verdict_dict, indent=2, sort_keys=True) + "\n"
        expected_verdict_path = fixture / "expected-verdict.json"
        expected_comment_path = fixture / "expected-comment.md"

        if update:
            expected_verdict_path.write_text(verdict_text, encoding="utf-8")
            expected_comment_path.write_text(comment, encoding="utf-8")
            print(f"upd   {name}")
            continue

        if not expected_verdict_path.exists() or not expected_comment_path.exists():
            failures.append(f"FAIL  {name}: missing expected files (run with --update)")
            continue

        actual_verdict = verdict_text
        expected_verdict = normalize_json(expected_verdict_path.read_text(encoding="utf-8"))
        actual_comment = comment
        expected_comment = expected_comment_path.read_text(encoding="utf-8")

        if actual_verdict != expected_verdict:
            failures.append(f"FAIL  {name}: verdict mismatch")
            print(f"--- expected ({name})\n{expected_verdict}", file=sys.stderr)
            print(f"+++ actual ({name})\n{actual_verdict}", file=sys.stderr)
            continue

        if actual_comment != expected_comment:
            failures.append(f"FAIL  {name}: comment mismatch")
            print(f"--- expected ({name})\n{expected_comment}", file=sys.stderr)
            print(f"+++ actual ({name})\n{actual_comment}", file=sys.stderr)
            continue

        print(f"ok    {name}")

    print()
    if failures:
        for line in failures:
            print(line, file=sys.stderr)
        print(f"\n{len(failures)} fixture(s) failed.", file=sys.stderr)
        return 2

    print(f"all {len([f for f in fixtures if not f.name.startswith('_')])} fixture(s) match expected output.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

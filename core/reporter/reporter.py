"""
Reporter core. Pure logic; no I/O at the top level except in main().
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import re
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Iterable

try:
    import yaml  # type: ignore
except ImportError:
    sys.stderr.write("error: PyYAML not installed. pip install pyyaml\n")
    sys.exit(1)


# --------------------------------------------------------------------------
# Data types
# --------------------------------------------------------------------------

@dataclass
class Diff:
    """A simplified diff: list of changed files plus line-count totals."""
    changed_files: list[str]
    files_changed: int
    lines_changed: int


@dataclass
class BoundaryViolation:
    rule: str
    detail: str
    severity: str = "error"
    source: str = "backend"


@dataclass
class CheckpointStatus:
    id: str
    reason: str
    satisfied: bool
    satisfy_by: list[str] = field(default_factory=list)


@dataclass
class Verdict:
    verdict: str   # BLUE | RED | GRAY | BOUNDARY_VIOLATION | MIXED | API_CHANGE | SCHEMA_CHANGE | SECURITY_CHANGE
    summary: str
    zones: dict[str, list[str]]
    checkpoints: list[CheckpointStatus]
    boundary_violations: list[BoundaryViolation]
    api_changes: dict[str, Any]
    schema_changes: dict[str, Any]
    security_changes: dict[str, Any]
    pr_size: dict[str, Any]
    exit_code: int
    recommended_action: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "verdict": self.verdict,
            "summary": self.summary,
            "zones": self.zones,
            "checkpoints": [asdict(c) for c in self.checkpoints],
            "boundaryViolations": [asdict(b) for b in self.boundary_violations],
            "apiChanges": self.api_changes,
            "schemaChanges": self.schema_changes,
            "securityChanges": self.security_changes,
            "prSize": self.pr_size,
            "exitCode": self.exit_code,
            "recommendedAction": self.recommended_action,
        }


# --------------------------------------------------------------------------
# Glob matching
# --------------------------------------------------------------------------

def _glob_to_regex(pattern: str) -> re.Pattern:
    """
    Convert a shell-style glob into a regex.

    Differs from fnmatch in two important ways:
      - `**` matches zero or more path components (including empty)
      - `*` matches anything except `/`
    """
    i = 0
    out = ["^"]
    while i < len(pattern):
        c = pattern[i]
        if c == "*":
            if i + 1 < len(pattern) and pattern[i + 1] == "*":
                # `**` — zero or more components.
                # Common forms we want to handle:
                #   "**/x"   → "x" or "any/path/x"  → matches "x" or "a/x" or "a/b/x"
                #   "x/**"   → "x" or "x/anything"
                #   "x/**/y" → "x/y" or "x/a/y" or "x/a/b/y"
                # Implementation: "**/" → "(.*/)?"; trailing "**" or middle "**" → ".*"
                if i + 2 < len(pattern) and pattern[i + 2] == "/":
                    out.append("(?:.*/)?")
                    i += 3
                    continue
                else:
                    out.append(".*")
                    i += 2
                    continue
            else:
                out.append("[^/]*")
                i += 1
                continue
        elif c == "?":
            out.append("[^/]")
        elif c == ".":
            out.append(r"\.")
        elif c == "/":
            out.append("/")
        elif c in "()|+^$":
            out.append("\\" + c)
        else:
            out.append(re.escape(c))
        i += 1
    out.append("$")
    return re.compile("".join(out))


def matches(path: str, pattern: str) -> bool:
    return bool(_glob_to_regex(pattern).match(path))


def matches_any(path: str, patterns: Iterable[str]) -> bool:
    return any(matches(path, p) for p in patterns)


# --------------------------------------------------------------------------
# Zone classification
# --------------------------------------------------------------------------

def _zone_paths(zone_entries: list[dict[str, Any]] | None) -> list[str]:
    return [e["path"] for e in (zone_entries or [])]


def classify_files(
    files: list[str],
    policy: dict[str, Any],
) -> dict[str, list[str]]:
    """
    Classify each file as red / blue / gray / grayWatch / excluded.

    Priority: excludes wins; then red; then blue; then grayWatch as a tag
    (a file can be both blue+grayWatch or gray+grayWatch — the tag is
    additive). Anything not red, blue, or excluded is gray.
    """
    zones = policy.get("zones", {}) or {}
    red = _zone_paths(zones.get("red"))
    blue = _zone_paths(zones.get("blue"))
    gray_watch = _zone_paths(zones.get("grayWatch"))
    excludes = policy.get("excludes", []) or []

    classified: dict[str, list[str]] = {
        "red": [],
        "blue": [],
        "gray": [],
        "grayWatch": [],
        "excluded": [],
    }

    for path in files:
        if matches_any(path, excludes):
            classified["excluded"].append(path)
            continue
        if matches_any(path, red):
            classified["red"].append(path)
        elif matches_any(path, blue):
            classified["blue"].append(path)
        else:
            classified["gray"].append(path)
        if matches_any(path, gray_watch):
            classified["grayWatch"].append(path)

    return classified


# --------------------------------------------------------------------------
# Signal detection (per-section policy fields)
# --------------------------------------------------------------------------

def _detect_signal(files: list[str], section: dict[str, Any] | None, key: str) -> bool:
    if not section:
        return False
    paths = section.get(key) or []
    return any(matches_any(f, paths) for f in files)


def detect_api_change(files: list[str], policy: dict[str, Any]) -> bool:
    api = policy.get("api") or {}
    api_type = api.get("type", "none")
    if api_type == "none":
        return False
    spec_path = api.get("specPath")
    if api_type == "openapi-spec-file" and spec_path:
        return any(matches(f, spec_path) for f in files)
    if api_type in ("graphql", "proto") and spec_path:
        return any(matches(f, spec_path) for f in files)
    # openapi-from-controllers: heuristic — controllers are typically red,
    # so an api-review will be triggered via red-zone classification when
    # controllers change. v0.1 doesn't run a real OpenAPI diff.
    return False


def detect_schema_change(files: list[str], policy: dict[str, Any]) -> bool:
    return _detect_signal(files, policy.get("persistence"), "migrationPaths")


def detect_security_change(files: list[str], policy: dict[str, Any]) -> bool:
    return _detect_signal(files, policy.get("security"), "paths")


def detect_runtime_config_change(files: list[str], policy: dict[str, Any]) -> bool:
    return _detect_signal(files, policy.get("runtimeConfig"), "paths")


# --------------------------------------------------------------------------
# Boundary backend (JUnit XML) parsing
# --------------------------------------------------------------------------

def parse_archunit_junit_xml(xml_text: str) -> list[BoundaryViolation]:
    """
    Parse JUnit XML for ArchUnit-style violations.

    Looks for testcases whose <failure> message indicates an architecture
    rule violation. The match-class-name and match-test-name patterns from
    extension adapter.yaml would normally filter; for v0.1 we match by
    convention: testcases in classes containing "ArchitectureTest" with
    a <failure> element.
    """
    violations: list[BoundaryViolation] = []
    if not xml_text:
        return violations

    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return violations

    # JUnit XML has either <testsuite> or <testsuites><testsuite>...
    suites = list(root.iter("testsuite"))
    for suite in suites:
        suite_name = suite.attrib.get("name", "")
        if "ArchitectureTest" not in suite_name and "Architecture" not in suite_name:
            continue
        for case in suite.iter("testcase"):
            failure = case.find("failure")
            if failure is None:
                continue
            test_name = case.attrib.get("name", "")
            detail = (failure.text or failure.attrib.get("message", "")).strip()
            violations.append(
                BoundaryViolation(
                    rule=test_name,
                    detail=_first_line(detail),
                    severity="error",
                    source="archunit",
                )
            )
    return violations


def _first_line(text: str, max_len: int = 200) -> str:
    line = (text or "").strip().splitlines()[0] if text else ""
    return line[:max_len]


# --------------------------------------------------------------------------
# Checkpoint satisfaction
# --------------------------------------------------------------------------

def _required_checkpoints(
    classification: dict[str, list[str]],
    policy: dict[str, Any],
    api_changed: bool,
    schema_changed: bool,
    security_changed: bool,
    runtime_config_changed: bool,
    architecture_test_modified: bool,
) -> dict[str, str]:
    """Return {checkpoint_id: reason} for each required checkpoint."""
    required: dict[str, str] = {}

    # Red-zone files map to their declared checkpoints (default architecture-review).
    zones = policy.get("zones", {}) or {}
    red_entries = zones.get("red", []) or []
    for entry in red_entries:
        path = entry["path"]
        cp = entry.get("checkpoint", "architecture-review")
        for f in classification["red"]:
            if matches(f, path):
                required.setdefault(cp, f"red-zone change: {f}")
                break

    if api_changed:
        cp = (policy.get("api") or {}).get("checkpoint", "api-review")
        required.setdefault(cp, "API contract changed")
    if schema_changed:
        cp = (policy.get("persistence") or {}).get("checkpoint", "persistence-review")
        required.setdefault(cp, "Persistence migration changed")
    if security_changed:
        cp = (policy.get("security") or {}).get("checkpoint", "security-review")
        required.setdefault(cp, "Security path changed")
    if runtime_config_changed:
        cp = (policy.get("runtimeConfig") or {}).get("checkpoint", "ops-review")
        required.setdefault(cp, "Runtime configuration changed")
    if architecture_test_modified:
        required.setdefault(
            "architecture-review",
            "Architecture-test files modified",
        )

    return required


def _is_satisfied(
    checkpoint_def: dict[str, Any],
    pr_labels: Iterable[str],
    codeowner_approvals: Iterable[str],
) -> tuple[bool, list[str]]:
    """OR-semantics over satisfiedBy entries. Returns (satisfied, satisfy_by_human)."""
    satisfied_by = checkpoint_def.get("satisfiedBy", []) or []
    labels = set(pr_labels)
    has_codeowner = bool(list(codeowner_approvals))

    satisfy_by_human: list[str] = []
    satisfied = False
    for sb in satisfied_by:
        if sb == "codeownerApproval":
            satisfy_by_human.append("CODEOWNER approval")
            if has_codeowner:
                satisfied = True
        elif isinstance(sb, dict):
            if "label" in sb:
                satisfy_by_human.append(f"label `{sb['label']}`")
                if sb["label"] in labels:
                    satisfied = True
            elif "team" in sb:
                satisfy_by_human.append(f"approval from team `{sb['team']}`")
                # Team approval is treated as a CODEOWNER approval signal
                # in v0.1 (we don't model teams separately yet).
            elif "reviewerCount" in sb:
                satisfy_by_human.append(f"≥{sb['reviewerCount']} reviewers")
                # Reviewer count is checked via has_codeowner heuristic in v0.1;
                # real reviewer-count satisfaction is roadmap.
    return satisfied, satisfy_by_human


# --------------------------------------------------------------------------
# Verdict computation
# --------------------------------------------------------------------------

ARCHITECTURE_TEST_GLOBS = (
    # The standard glob the spring-archunit profile uses; agent-redline
    # treats architecture-test files as red regardless of policy.
    "src/test/java/**/architecture/**",
    # Common alternates for other ecosystems
    "**/architecture/**",
)


def _is_architecture_test_file(path: str) -> bool:
    return any(matches(path, g) for g in ARCHITECTURE_TEST_GLOBS)


def _pr_size_status(diff: Diff, policy: dict[str, Any]) -> dict[str, Any]:
    pr_rules = policy.get("prRules", {}) or {}
    files_rule = pr_rules.get("maxChangedFiles", {}) or {}
    lines_rule = pr_rules.get("maxLinesChanged", {}) or {}

    fail_files = files_rule.get("fail", 100)
    warn_files = files_rule.get("warn", 50)
    fail_lines = lines_rule.get("fail", 2000)
    warn_lines = lines_rule.get("warn", 1000)

    verdict = "ok"
    if diff.files_changed > fail_files or diff.lines_changed > fail_lines:
        verdict = "fail"
    elif diff.files_changed > warn_files or diff.lines_changed > warn_lines:
        verdict = "warn"

    return {
        "files": diff.files_changed,
        "lines": diff.lines_changed,
        "verdict": verdict,
    }


def _binding(modes: dict[str, Any], check_name: str) -> bool:
    """Whether a given check is binding under the policy's modes config."""
    default = (modes or {}).get("default", "shadow")
    per_check = (modes or {}).get("perCheck", {}) or {}
    return per_check.get(check_name, default) == "binding"


def classify(
    policy: dict[str, Any],
    diff: Diff,
    *,
    archunit_xml: str | None = None,
    pr_labels: Iterable[str] = (),
    codeowner_approvals: Iterable[str] = (),
) -> Verdict:
    """The single entry point. Pure function."""
    files = diff.changed_files
    classification = classify_files(files, policy)

    arch_test_modified = any(_is_architecture_test_file(f) for f in files)

    api_changed = detect_api_change(files, policy)
    schema_changed = detect_schema_change(files, policy)
    security_changed = detect_security_change(files, policy)
    runtime_changed = detect_runtime_config_change(files, policy)

    boundary_violations: list[BoundaryViolation] = []
    if archunit_xml:
        boundary_violations = parse_archunit_junit_xml(archunit_xml)

    required = _required_checkpoints(
        classification, policy,
        api_changed, schema_changed, security_changed, runtime_changed,
        arch_test_modified,
    )

    checkpoints_defs = policy.get("checkpoints", {}) or {}
    checkpoint_statuses: list[CheckpointStatus] = []
    for cp_id, reason in required.items():
        cp_def = checkpoints_defs.get(cp_id, {})
        satisfied, satisfy_by = _is_satisfied(cp_def, pr_labels, codeowner_approvals)
        checkpoint_statuses.append(
            CheckpointStatus(
                id=cp_id, reason=reason, satisfied=satisfied,
                satisfy_by=satisfy_by,
            )
        )

    pr_size = _pr_size_status(diff, policy)

    # Top-level verdict.
    if not files:
        verdict = "BLUE"
        summary = "No files changed."
    elif boundary_violations:
        verdict = "BOUNDARY_VIOLATION"
        summary = f"{len(boundary_violations)} boundary violation(s) detected."
    elif arch_test_modified:
        verdict = "RED"
        summary = "Architecture-test files modified; architecture-review required."
    elif api_changed:
        verdict = "API_CHANGE"
        summary = "Public API contract changed."
    elif schema_changed:
        verdict = "SCHEMA_CHANGE"
        summary = "Persistence schema changed."
    elif security_changed:
        verdict = "SECURITY_CHANGE"
        summary = "Security-sensitive code changed."
    elif classification["red"]:
        verdict = "RED"
        summary = "Red-zone files changed."
    elif classification["gray"]:
        verdict = "GRAY"
        summary = "Gray-zone files changed; cautious review."
    else:
        verdict = "BLUE"
        summary = "All changes in blue zones."

    # Exit code under the modes policy.
    modes = policy.get("modes", {}) or {}
    exit_code = 0
    recommended = "none"

    has_unmet_required = any(not c.satisfied for c in checkpoint_statuses)
    pr_size_fail = pr_size["verdict"] == "fail"
    pr_size_warn = pr_size["verdict"] == "warn"

    if boundary_violations and _binding(modes, "boundary_violation"):
        exit_code = 2
        recommended = "fix-boundary-violation"
    elif has_unmet_required and _binding(modes, "report"):
        # In default config, the report comment is informational; only fail
        # when the policy makes the report binding.
        exit_code = 2
        recommended = "satisfy-checkpoints"
    elif pr_size_fail and _binding(modes, "pr_size"):
        exit_code = 2
        recommended = "split-pr"
    elif boundary_violations or has_unmet_required or pr_size_fail:
        # Issues exist but checks are in shadow.
        exit_code = 1
        recommended = "review-shadow-warnings"
    elif classification["gray"] or classification["grayWatch"] or pr_size_warn:
        exit_code = 1
        recommended = "review-warnings"

    return Verdict(
        verdict=verdict,
        summary=summary,
        zones={
            "red": classification["red"],
            "blue": classification["blue"],
            "gray": classification["gray"],
            "grayWatch": classification["grayWatch"],
        },
        checkpoints=checkpoint_statuses,
        boundary_violations=boundary_violations,
        api_changes={"detected": api_changed},
        schema_changes={"detected": schema_changed},
        security_changes={"detected": security_changed},
        pr_size=pr_size,
        exit_code=exit_code,
        recommended_action=recommended,
    )


# --------------------------------------------------------------------------
# Markdown PR comment
# --------------------------------------------------------------------------

def render_markdown(verdict: Verdict) -> str:
    lines: list[str] = []
    lines.append(f"## agent-redline: {verdict.verdict}")
    lines.append("")
    lines.append(f"**{verdict.summary}**")
    lines.append("")

    # Zones table — only show non-empty rows.
    rows = []
    for label, key in (("Red", "red"), ("Blue", "blue"), ("Gray", "gray"), ("Gray-watch", "grayWatch")):
        files = verdict.zones.get(key, [])
        if files:
            shown = ", ".join(f"`{p}`" for p in files[:5])
            if len(files) > 5:
                shown += f" (+{len(files) - 5} more)"
            rows.append(f"| {label} | {shown} |")
    if rows:
        lines.append("| Zone | Files |")
        lines.append("|---|---|")
        lines.extend(rows)
        lines.append("")

    # Checkpoints
    if verdict.checkpoints:
        lines.append("**Required checkpoints:**")
        for cp in verdict.checkpoints:
            box = "[x]" if cp.satisfied else "[ ]"
            satisfy = " or ".join(cp.satisfy_by) if cp.satisfy_by else "(see policy)"
            lines.append(f"- {box} `{cp.id}` — {cp.reason}. Satisfy by: {satisfy}")
        lines.append("")

    # Boundary violations
    if verdict.boundary_violations:
        lines.append("**Boundary violations:**")
        for bv in verdict.boundary_violations:
            lines.append(f"- `{bv.rule}` ({bv.severity}): {bv.detail}")
        lines.append("")
    else:
        lines.append("**Boundary check:** passed")

    # Other signals
    if verdict.api_changes.get("detected"):
        lines.append("**API check:** changes detected")
    else:
        lines.append("**API check:** no changes")
    if verdict.schema_changes.get("detected"):
        lines.append("**Schema check:** changes detected")
    if verdict.security_changes.get("detected"):
        lines.append("**Security check:** changes detected")

    # PR size
    sz = verdict.pr_size
    lines.append(f"**PR size:** {sz['files']} files / {sz['lines']} lines ({sz['verdict']})")

    return "\n".join(lines).rstrip() + "\n"


# --------------------------------------------------------------------------
# Loaders
# --------------------------------------------------------------------------

def load_policy(path: Path) -> dict[str, Any]:
    with path.open() as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        raise SystemExit(f"error: policy at {path} is not a mapping")
    return data


def load_diff_from_files(changed_files_path: Path, lines_changed: int = 0) -> Diff:
    files = [line.strip() for line in changed_files_path.read_text().splitlines() if line.strip()]
    return Diff(changed_files=files, files_changed=len(files), lines_changed=lines_changed)


def load_archunit_xml(path: Path | None) -> str | None:
    if path is None or not path.exists():
        return None
    return path.read_text()


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="agent-redline reporter")
    p.add_argument("--policy", required=True, type=Path, help="Path to agent-policy.yaml")
    p.add_argument("--changed-files", type=Path,
                   help="Path to a newline-separated list of changed files (overrides --base/--head)")
    p.add_argument("--lines-changed", type=int, default=0,
                   help="Total lines changed (for PR-size check)")
    p.add_argument("--archunit-xml", type=Path,
                   help="Path to an ArchUnit JUnit XML report")
    p.add_argument("--pr-labels", default="", help="Comma-separated PR labels")
    p.add_argument("--codeowner-approvals", default="",
                   help="Comma-separated CODEOWNER approver logins")
    p.add_argument("--mode", default="shadow", choices=["shadow", "binding"],
                   help="Override modes.default (advisory; the policy still wins per-check)")
    p.add_argument("--json-out", type=Path, help="Write JSON verdict to this file")
    p.add_argument("--comment-out", type=Path, help="Write markdown PR comment to this file")
    args = p.parse_args(argv)

    policy = load_policy(args.policy)

    # Apply --mode as an override of modes.default if the policy doesn't pin it.
    if "modes" not in policy:
        policy["modes"] = {}
    policy["modes"].setdefault("default", args.mode)

    if args.changed_files is None:
        sys.stderr.write("error: --changed-files required in v0.1 (git-driven mode is roadmap)\n")
        return 1

    diff = load_diff_from_files(args.changed_files, args.lines_changed)
    archunit_xml = load_archunit_xml(args.archunit_xml)

    pr_labels = [s.strip() for s in args.pr_labels.split(",") if s.strip()]
    codeowner_approvals = [s.strip() for s in args.codeowner_approvals.split(",") if s.strip()]

    verdict = classify(
        policy, diff,
        archunit_xml=archunit_xml,
        pr_labels=pr_labels,
        codeowner_approvals=codeowner_approvals,
    )

    if args.json_out:
        args.json_out.write_text(json.dumps(verdict.to_dict(), indent=2) + "\n")
    else:
        print(json.dumps(verdict.to_dict(), indent=2))

    comment = render_markdown(verdict)
    if args.comment_out:
        args.comment_out.write_text(comment)

    return verdict.exit_code


if __name__ == "__main__":
    sys.exit(main())

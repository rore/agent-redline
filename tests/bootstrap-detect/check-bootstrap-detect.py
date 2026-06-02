#!/usr/bin/env python3
"""
tests/bootstrap-detect/check-bootstrap-detect.py

Validates the Python extension's shape + layout detection logic against
a small set of fixture repos. Each fixture represents one canonical
shape; the test asserts the detection signals from
extensions/python/profile.md fire as expected.

This is the first test of bootstrap-mode behavior that doesn't require
running an actual agent. We can't test the conversational layer
("agent asks the right question"), but we CAN test the deterministic
detection layer ("given this repo shape, which signals match?").

Each fixture under fixtures/<name>/ has:
  - a minimal repo skeleton (pyproject.toml, top-level dirs with
    __init__.py, etc.)
  - a `expected.json` file: the expected detection result, per the
    profile's documented signal table

The test runs the same detection logic the agent applies during Phase 1
inspection and asserts the result matches expected.json.

Exit codes:
  0 — all fixtures detect as expected
  1 — script error
  2 — at least one fixture's detection diverged from expected
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"

# Web framework deps the profile lists as layered-service signals.
WEB_FRAMEWORKS = {
    "fastapi", "flask", "django", "starlette", "aiohttp",
    "sanic", "litestar", "falcon", "bottle",
}

# Pipeline / data-flow deps that signal zone-only fallback.
PIPELINE_DEPS = {"apache-airflow", "prefect", "dagster", "luigi"}

# Layer directory names the profile lists as layered-service signals.
LAYER_DIRS = {
    "api", "domain", "application", "adapters", "infrastructure",
    "core", "services", "usecases", "ports",
}


def read_pyproject_deps(pyproject: Path) -> set[str]:
    """Pull the top-level dependency names from a pyproject.toml.
    Returns lowercase package names; empty set if no [project] table."""
    if not pyproject.exists():
        return set()
    text = pyproject.read_text(encoding="utf-8")
    deps: set[str] = set()
    # Look for [project] dependencies = [...]
    proj = re.search(
        r"^\[project\][^\[]*?dependencies\s*=\s*\[(.*?)\]",
        text, flags=re.DOTALL | re.MULTILINE,
    )
    if proj:
        for line in proj.group(1).splitlines():
            m = re.match(r'\s*"([a-zA-Z][a-zA-Z0-9_-]*)', line)
            if m:
                deps.add(m.group(1).lower())
    return deps


def read_pyproject_name(pyproject: Path) -> str | None:
    if not pyproject.exists():
        return None
    text = pyproject.read_text(encoding="utf-8")
    m = re.search(r'^\[project\][^\[]*?name\s*=\s*"([^"]+)"', text, flags=re.DOTALL | re.MULTILINE)
    if m:
        return m.group(1).lower()
    return None


def detect(repo: Path) -> dict:
    """Apply the detection rules from extensions/python/profile.md.

    Returns a dict with the signals that fired, organized so it can be
    diffed against expected.json."""
    pyproject = repo / "pyproject.toml"
    deps = read_pyproject_deps(pyproject)
    project_name = read_pyproject_name(pyproject)

    # Layout detection
    has_src = (repo / "src").is_dir()
    src_pkgs = []
    if has_src:
        src_pkgs = [
            d.name for d in (repo / "src").iterdir()
            if d.is_dir() and (d / "__init__.py").exists()
        ]
    flat_pkgs_at_root = [
        d.name for d in repo.iterdir()
        if d.is_dir() and (d / "__init__.py").exists()
        and d.name not in {".git", "__pycache__", "tests", "docs", "scripts", "build"}
    ]
    has_manage_py = (repo / "manage.py").exists()

    # Layout classification
    if has_src and len(src_pkgs) == 1:
        layout = "src-layout"
    elif (
        len(flat_pkgs_at_root) >= 2
        and (project_name is None or project_name not in flat_pkgs_at_root)
    ):
        layout = "multi-package"
    elif len(flat_pkgs_at_root) == 1:
        layout = "flat"
    elif len(flat_pkgs_at_root) == 0 and not has_src:
        layout = "no-package"
    else:
        layout = "ambiguous"

    # Web-framework deps
    web_deps = sorted(deps & WEB_FRAMEWORKS)
    has_web_dep = bool(web_deps)
    has_django = "django" in deps and has_manage_py

    # Pipeline deps / dirs
    pipeline_deps_present = sorted(deps & PIPELINE_DEPS)
    has_dags_dir = (repo / "dags").is_dir()
    has_pipelines_dir = (repo / "pipelines").is_dir()
    has_notebooks_dir = (repo / "notebooks").is_dir()

    # Layer directories under any package root
    candidate_pkg_dirs = []
    if has_src:
        candidate_pkg_dirs.extend((repo / "src").iterdir())
    candidate_pkg_dirs.extend(repo.iterdir())
    layer_dirs_found: set[str] = set()
    for pkg_root in candidate_pkg_dirs:
        if not pkg_root.is_dir():
            continue
        for sub in pkg_root.iterdir():
            if sub.is_dir() and sub.name in LAYER_DIRS:
                layer_dirs_found.add(sub.name)

    # Library-shape signal: __init__.py with re-exports
    library_signals: list[str] = []
    for pkg_root in candidate_pkg_dirs:
        if not pkg_root.is_dir():
            continue
        init = pkg_root / "__init__.py"
        if init.exists():
            text = init.read_text(encoding="utf-8")
            if re.search(r"^\s*from \.\S+ import", text, re.MULTILINE) or "__all__" in text:
                library_signals.append(pkg_root.name)

    # Final shape decision (mirrors profile.md's triage table priority)
    if has_django:
        shape = "layered-service-django"
    elif has_web_dep:
        shape = "layered-service"
    elif layer_dirs_found:
        shape = "layered-service"
    elif pipeline_deps_present or has_dags_dir or has_pipelines_dir or has_notebooks_dir:
        shape = "zone-only-fallback"
    elif library_signals and not has_web_dep:
        shape = "library"
    else:
        shape = "zone-only-fallback"

    return {
        "layout": layout,
        "shape": shape,
        "web_deps": web_deps,
        "has_django": has_django,
        "has_manage_py": has_manage_py,
        "layer_dirs_found": sorted(layer_dirs_found),
        "library_signals": sorted(library_signals),
        "pipeline_deps": pipeline_deps_present,
        "flat_top_packages": sorted(flat_pkgs_at_root),
        "src_packages": sorted(src_pkgs),
    }


def main() -> int:
    if not FIXTURES_DIR.exists():
        print(f"error: fixtures dir missing at {FIXTURES_DIR}", file=sys.stderr)
        return 1

    failures: list[str] = []
    fixtures_seen = 0

    for fixture_dir in sorted(FIXTURES_DIR.iterdir()):
        if not fixture_dir.is_dir():
            continue
        expected_file = fixture_dir / "expected.json"
        if not expected_file.exists():
            failures.append(f"FAIL  {fixture_dir.name}: expected.json missing")
            continue
        fixtures_seen += 1

        expected = json.loads(expected_file.read_text(encoding="utf-8"))
        actual = detect(fixture_dir)

        for k, v in expected.items():
            if actual.get(k) != v:
                failures.append(
                    f"FAIL  {fixture_dir.name}.{k}: expected {v!r}, got {actual.get(k)!r}"
                )
        if not any(f.startswith(f"FAIL  {fixture_dir.name}.") for f in failures):
            print(f"ok    {fixture_dir.name} -> shape={actual['shape']} layout={actual['layout']}")

    print()
    if failures:
        for f in failures:
            print(f, file=sys.stderr)
        print(f"\n{len(failures)} fixture-assertion(s) failed.", file=sys.stderr)
        return 2

    print(f"all {fixtures_seen} fixture(s) detected as expected.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

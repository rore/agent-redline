#!/usr/bin/env python3
"""
tests/bootstrap-detect/check-bootstrap-detect.py

Validates the Python and JVM extensions' shape + layout detection logic against
a small set of fixture repos. Each fixture represents one canonical
shape; the test asserts the detection signals from
extensions/python/profile.md and extensions/jvm-archunit/profile.md
fire as expected.

This is the first test of bootstrap-mode behavior that doesn't require
running an actual agent. We can't test the conversational layer
("agent asks the right question"), but we CAN test the deterministic
detection layer ("given this repo shape, which signals match?").

Each fixture under fixtures/<name>/ has:
  - a minimal repo skeleton (pyproject.toml, top-level dirs with
    __init__.py, etc. for Python; build.gradle / pom.xml etc. for JVM)
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

# JVM web frameworks the profile lists as layered-service signals.
JVM_WEB_FRAMEWORKS = {
    "spring-boot-starter", "org.springframework.boot",
    "jakarta.ws.rs", "io.javalin", "io.ktor",
    "io.helidon", "io.dropwizard", "org.eclipse.jetty",
}

# JVM pipeline / data-flow deps that signal zone-only fallback.
JVM_PIPELINE_DEPS = {
    "apache.spark", "apache.beam", "apache.flink", "apache.hadoop",
}

# JVM Android plugin IDs that signal zone-only fallback.
JVM_ANDROID_PLUGINS = {"com.android.application", "com.android.library"}

# JVM library-shape Gradle plugins.
JVM_LIBRARY_PLUGINS = {"maven-publish", "nexus-publish"}

# JVM layer dirs the profile lists as layered-service signals.
JVM_LAYER_DIRS = {
    "controller", "domain", "application", "adapter",
    "infrastructure", "core", "port",
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


def read_gradle_or_pom_text(repo: Path) -> str:
    """Return concatenated text of build.gradle / build.gradle.kts / pom.xml at repo root.

    The harness only needs textual signal-match (substring grep), not full parsing.
    Returns empty string if no JVM build file is present.
    """
    pieces: list[str] = []
    for name in ("build.gradle", "build.gradle.kts", "pom.xml"):
        p = repo / name
        if p.exists():
            pieces.append(p.read_text(encoding="utf-8"))
    return "\n".join(pieces)


def find_module_info(repo: Path) -> bool:
    """Check for `module-info.java` anywhere under src/main/java."""
    src_main_java = repo / "src" / "main" / "java"
    if not src_main_java.is_dir():
        return False
    return any(src_main_java.rglob("module-info.java"))


def jvm_signals_present(text: str, signals: set) -> list[str]:
    """Return sorted list of signal substrings found in the text. Case-insensitive substring match."""
    text_lower = text.lower()
    found = sorted(s for s in signals if s.lower() in text_lower)
    return found


def jvm_layer_dirs_found(repo: Path) -> set[str]:
    """Return JVM layer directory names present under src/main/java/<base-package>/.

    Walks no deeper than 4 levels under src/main/java to find layer-named subdirectories.
    """
    src_main_java = repo / "src" / "main" / "java"
    if not src_main_java.is_dir():
        return set()
    found: set[str] = set()
    # Walk a few levels deep; layer dirs are typically src/main/java/com/example/<layer>/
    for path in src_main_java.rglob("*"):
        if path.is_dir() and path.name in JVM_LAYER_DIRS:
            try:
                depth = len(path.relative_to(src_main_java).parts)
            except ValueError:
                continue
            # Typical layout: src/main/java/<org>/<pkg>/<layer> = depth 3.
            # Cap at 4 to allow one extra level for sub-packages.
            if depth <= 4:
                found.add(path.name)
    return found


def detect(repo: Path) -> dict:
    """Apply detection rules from extensions/jvm-archunit/profile.md (JVM)
    or extensions/python/profile.md (Python). Dispatches on build files."""
    has_jvm_build = any((repo / f).exists() for f in ("build.gradle", "build.gradle.kts", "pom.xml"))
    has_python_build = (repo / "pyproject.toml").exists() or (repo / "setup.py").exists() or (repo / "setup.cfg").exists()

    if has_jvm_build and not has_python_build:
        return detect_jvm(repo)
    # Fallback: pure Python repos AND polyglot repos (both JVM + Python build files) AND
    # repos with no build files at all. No fixture exercises the polyglot case yet;
    # revisit if a real polyglot repo lands.
    return detect_python(repo)


def detect_jvm(repo: Path) -> dict:
    """Apply detection rules from extensions/jvm-archunit/profile.md."""
    text = read_gradle_or_pom_text(repo)
    web = jvm_signals_present(text, JVM_WEB_FRAMEWORKS)
    pipeline = jvm_signals_present(text, JVM_PIPELINE_DEPS)
    android = jvm_signals_present(text, JVM_ANDROID_PLUGINS)
    library_plugins = jvm_signals_present(text, JVM_LIBRARY_PLUGINS)
    has_module_info = find_module_info(repo)
    layer_dirs = sorted(jvm_layer_dirs_found(repo))
    has_spring = any("spring-boot-starter" in s or "springframework.boot" in s for s in web)

    # Shape decision (mirrors profile.md's Shape detection table priority)
    if has_spring:
        shape = "layered-service-spring"
    elif web or layer_dirs:
        shape = "layered-service"
    elif android or pipeline:
        shape = "zone-only-fallback"
    elif library_plugins or has_module_info:
        shape = "library"
    else:
        shape = "zone-only-fallback"

    return {
        "language": "jvm",
        "layout": "-",  # JVM detection doesn't compute layout; src/main/java is the convention
        "shape": shape,
        "spring_addendum": has_spring,
        "web_deps": web,
        "pipeline_deps": pipeline,
        "android_plugins": android,
        "library_plugins": library_plugins,
        "has_module_info": has_module_info,
        "layer_dirs_found": layer_dirs,
    }


def detect_python(repo: Path) -> dict:
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
        "language": "python",
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
            lang = actual.get("language", "?")
            shape = actual["shape"]
            layout = actual.get("layout", "-")
            print(f"ok    {fixture_dir.name} -> language={lang} shape={shape} layout={layout}")

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

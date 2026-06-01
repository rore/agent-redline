"""Tests for agent-redline-tune.py extensions: --repo fetch and --suggest."""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

spec = importlib.util.spec_from_file_location(
    "agent_redline_tune",
    REPO_ROOT / "scripts" / "agent-redline-tune.py",
)
tune = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tune)


def test_fetch_prs_via_gh_returns_pr_id_to_files_map():
    """Given a fake gh response, fetch_prs returns {pr_id: [files]}."""
    fake_pr_list = [{"number": 100}, {"number": 101}]
    fake_pr_files = {
        100: [{"path": "src/a.java"}, {"path": "src/b.java"}],
        101: [{"path": "docs/x.md"}],
    }

    def fake_run(cmd, **kwargs):
        if cmd[1] == "pr" and cmd[2] == "list":
            return subprocess.CompletedProcess(
                args=cmd, returncode=0,
                stdout=json.dumps(fake_pr_list),
                stderr="",
            )
        n = int(cmd[cmd.index("view") + 1])
        return subprocess.CompletedProcess(
            args=cmd, returncode=0,
            stdout=json.dumps({"files": fake_pr_files[n]}),
            stderr="",
        )

    with patch.object(tune.subprocess, "run", side_effect=fake_run):
        prs = tune.fetch_prs("github.com/owner/repo", limit=2)

    assert prs == {
        "pr-100": ["src/a.java", "src/b.java"],
        "pr-101": ["docs/x.md"],
    }


def test_fetch_prs_raises_systemexit_when_pr_list_fails():
    """If `gh pr list` returns nonzero, fetch_prs raises SystemExit with a useful message."""
    def fake_run(cmd, **kwargs):
        return subprocess.CompletedProcess(
            args=cmd, returncode=1, stdout="", stderr="auth required",
        )
    with patch.object(tune.subprocess, "run", side_effect=fake_run):
        with pytest.raises(SystemExit, match="auth required"):
            tune.fetch_prs("owner/repo", limit=5)


def test_fetch_prs_skips_pr_when_view_fails():
    """If `gh pr view` for one PR fails, that PR is skipped but others are returned."""
    def fake_run(cmd, **kwargs):
        if cmd[1] == "pr" and cmd[2] == "list":
            return subprocess.CompletedProcess(
                args=cmd, returncode=0,
                stdout=json.dumps([{"number": 100}, {"number": 101}]),
                stderr="",
            )
        n = int(cmd[cmd.index("view") + 1])
        if n == 100:
            return subprocess.CompletedProcess(
                args=cmd, returncode=1, stdout="", stderr="not found",
            )
        return subprocess.CompletedProcess(
            args=cmd, returncode=0,
            stdout=json.dumps({"files": [{"path": "src/x.java"}]}),
            stderr="",
        )
    with patch.object(tune.subprocess, "run", side_effect=fake_run):
        prs = tune.fetch_prs("owner/repo", limit=2)
    assert prs == {"pr-101": ["src/x.java"]}


def test_fetch_prs_excludes_pr_with_no_files():
    """A PR that returns an empty files array is excluded from the output dict."""
    def fake_run(cmd, **kwargs):
        if cmd[1] == "pr" and cmd[2] == "list":
            return subprocess.CompletedProcess(
                args=cmd, returncode=0,
                stdout=json.dumps([{"number": 100}, {"number": 101}]),
                stderr="",
            )
        n = int(cmd[cmd.index("view") + 1])
        if n == 100:
            return subprocess.CompletedProcess(
                args=cmd, returncode=0, stdout=json.dumps({"files": []}), stderr="",
            )
        return subprocess.CompletedProcess(
            args=cmd, returncode=0,
            stdout=json.dumps({"files": [{"path": "src/x.java"}]}),
            stderr="",
        )
    with patch.object(tune.subprocess, "run", side_effect=fake_run):
        prs = tune.fetch_prs("owner/repo", limit=2)
    assert prs == {"pr-101": ["src/x.java"]}


def test_suggest_tuning_demotes_high_firing_rules():
    """Rules firing on >30% of PRs are returned as 'demote' candidates."""
    counts = {
        "red": {
            ("src/main/java/**/*Controller.java", "public API contract surface"): 21,
            ("src/main/java/**/domain/repository/*.java", "domain repository interfaces"): 5,
            ("src/main/java/**/security/**", "auth/security-sensitive code"): 1,
        },
        "watch": {},
        "blue": {},
    }
    n_prs = 50

    suggestions = tune.suggest_tuning(counts, n_prs, threshold_demote=0.30)

    # Controller fires on 42% — demote.
    assert any(
        s["path"] == "src/main/java/**/*Controller.java"
        and s["action"] == "demote"
        for s in suggestions
    )
    # Repository fires on 10% — keep.
    assert not any(
        s["path"] == "src/main/java/**/domain/repository/*.java"
        for s in suggestions
    )
    # Security fires on 2% — keep.
    assert not any(
        s["path"] == "src/main/java/**/security/**"
        for s in suggestions
    )


def test_suggest_tuning_includes_firing_rate_in_each_suggestion():
    """Each suggestion has the rule path, current zone, action, and rate."""
    counts = {
        "red": {
            ("src/main/java/**/*Controller.java", "reason text"): 21,
        },
        "watch": {},
        "blue": {},
    }
    suggestions = tune.suggest_tuning(counts, 50, threshold_demote=0.30)
    s = suggestions[0]
    assert s["path"] == "src/main/java/**/*Controller.java"
    assert s["current_zone"] == "red"
    assert s["action"] == "demote"
    assert s["rate"] == 0.42
    assert s["fired"] == 21
    assert s["n_prs"] == 50


def test_suggest_tuning_threshold_is_inclusive():
    """A rule firing at exactly threshold_demote is demoted (boundary is inclusive)."""
    counts = {
        "red": {("src/at-threshold", "reason"): 15},  # 15/50 = 0.30 exactly
        "watch": {},
        "blue": {},
    }
    suggestions = tune.suggest_tuning(counts, 50, threshold_demote=0.30)
    assert len(suggestions) == 1
    assert suggestions[0]["path"] == "src/at-threshold"


def test_suggest_tuning_returns_empty_when_n_prs_is_zero():
    """The n_prs<=0 guard returns an empty list (no division-by-zero)."""
    counts = {"red": {("any/path", "any reason"): 5}, "watch": {}, "blue": {}}
    assert tune.suggest_tuning(counts, 0) == []
    assert tune.suggest_tuning(counts, -1) == []

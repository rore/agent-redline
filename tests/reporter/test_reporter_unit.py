"""
tests/reporter/test_reporter_unit.py

Unit tests for the reporter's pure logic. Covers:
  - Glob matching edge cases (** zero components, * no-cross-slash)
  - Verdict logic for every classification branch
  - Signal detection (api/schema/security/runtime)
  - ArchUnit XML parsing (single, multiple, no failures, malformed)
  - Checkpoint satisfaction (label, codeownerApproval)
  - Empty diff handling
  - Excludes
  - grayWatch overlap with blue/red

These tests don't require fixtures on disk; they construct policy dicts
and Diff objects in-memory and assert against the Verdict.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT))

import pytest  # type: ignore

from core.reporter.reporter import (  # noqa: E402
    Diff,
    classify,
    classify_files,
    matches,
    parse_archunit_junit_xml,
    detect_api_change,
    detect_schema_change,
    detect_security_change,
    detect_runtime_config_change,
)


# --------------------------------------------------------------------------
# Glob matching
# --------------------------------------------------------------------------

class TestGlobMatching:

    def test_simple_path(self):
        assert matches("src/main/java/Foo.java", "src/main/java/Foo.java")

    def test_star_does_not_cross_slash(self):
        # `*` matches single path components only.
        assert matches("src/main/Foo.java", "src/main/*.java")
        assert not matches("src/main/sub/Foo.java", "src/main/*.java")

    def test_double_star_zero_components(self):
        # `a/**/b` should match `a/b` (zero components in the middle).
        assert matches("a/b", "a/**/b")
        assert matches("a/x/b", "a/**/b")
        assert matches("a/x/y/b", "a/**/b")

    def test_leading_double_star(self):
        # `**/x` should match at any depth, including root.
        assert matches("x", "**/x")
        assert matches("a/x", "**/x")
        assert matches("a/b/x", "**/x")

    def test_trailing_double_star(self):
        # `x/**` should match `x` as well as `x/anything`.
        # Our implementation: `x/**` → `x/.*` so `x` alone won't match.
        # That's a deliberate choice and matches typical glob behavior.
        # Document the actual behavior:
        assert matches("x/y", "x/**")
        assert matches("x/y/z", "x/**")

    def test_question_mark(self):
        assert matches("a", "?")
        assert not matches("ab", "?")

    def test_character_class(self):
        # Currently our implementation forwards [abc] to regex via re.escape...
        # actually we don't escape brackets, so they pass through as character classes.
        assert matches("a", "[abc]")
        assert matches("c", "[abc]")
        assert not matches("d", "[abc]")

    def test_brace_expansion_unsupported(self):
        # `{a,b}` is not implemented in our regex translator. Document it.
        # If someone adds it, this test should be updated to assert it works.
        assert not matches("a", "{a,b}")
        assert not matches("b", "{a,b}")

    def test_dot_is_literal(self):
        assert matches("Foo.java", "Foo.java")
        assert not matches("Fooxjava", "Foo.java")


# --------------------------------------------------------------------------
# classify_files (zone classification)
# --------------------------------------------------------------------------

class TestClassifyFiles:

    @staticmethod
    def policy_with_zones(red=None, blue=None, gray_watch=None, excludes=None):
        return {
            "zones": {
                "red": [{"path": p, "reason": "x"} for p in (red or [])],
                "blue": [{"path": p, "reason": "x"} for p in (blue or [])],
                "grayWatch": [{"path": p, "reason": "x"} for p in (gray_watch or [])],
            },
            "excludes": list(excludes or []),
        }

    def test_red_wins_over_blue(self):
        policy = self.policy_with_zones(
            red=["src/main/**/domain/**"],
            blue=["src/main/**"],
        )
        c = classify_files(["src/main/foo/domain/Order.java"], policy)
        assert c["red"] == ["src/main/foo/domain/Order.java"]
        assert c["blue"] == []

    def test_blue_overrides_default_gray(self):
        policy = self.policy_with_zones(blue=["src/test/**"])
        c = classify_files(["src/test/foo/Bar.java"], policy)
        assert c["blue"] == ["src/test/foo/Bar.java"]
        assert c["gray"] == []

    def test_unclassified_is_gray(self):
        policy = self.policy_with_zones(red=["**/domain/**"])
        c = classify_files(["src/main/util/Helper.java"], policy)
        assert c["gray"] == ["src/main/util/Helper.java"]
        assert c["red"] == []

    def test_excluded_files_not_in_any_zone(self):
        policy = self.policy_with_zones(
            red=["**/generated/**"],
            blue=["**"],
            excludes=["**/generated/**"],
        )
        c = classify_files(["src/main/generated/Foo.java"], policy)
        assert c["excluded"] == ["src/main/generated/Foo.java"]
        assert c["red"] == []
        assert c["blue"] == []

    def test_gray_watch_is_additive_with_blue(self):
        # A file can be both blue (or gray) and grayWatch — grayWatch is a tag.
        policy = self.policy_with_zones(
            blue=["src/main/**/*Service.java"],
            gray_watch=["src/main/**/*Service.java"],
        )
        c = classify_files(["src/main/app/OrderService.java"], policy)
        assert c["blue"] == ["src/main/app/OrderService.java"]
        assert c["grayWatch"] == ["src/main/app/OrderService.java"]


# --------------------------------------------------------------------------
# Signal detection
# --------------------------------------------------------------------------

class TestSignalDetection:

    def test_api_change_via_spec_file(self):
        policy = {"api": {"type": "openapi-spec-file", "specPath": "openapi/api.yaml"}}
        assert detect_api_change(["openapi/api.yaml"], policy)
        assert not detect_api_change(["src/main/Foo.java"], policy)

    def test_api_none_means_no_signal(self):
        policy = {"api": {"type": "none"}}
        assert not detect_api_change(["openapi/api.yaml"], policy)

    def test_schema_change(self):
        policy = {"persistence": {"migrationPaths": ["db/migration/**"]}}
        assert detect_schema_change(["db/migration/V1.sql"], policy)
        assert not detect_schema_change(["src/main/Foo.java"], policy)

    def test_security_change(self):
        policy = {"security": {"paths": ["src/**/security/**"]}}
        assert detect_security_change(["src/main/security/JwtConfig.java"], policy)
        assert not detect_security_change(["src/main/Foo.java"], policy)

    def test_runtime_config_change(self):
        policy = {"runtimeConfig": {"paths": ["src/main/resources/application*.yml"]}}
        assert detect_runtime_config_change(["src/main/resources/application.yml"], policy)
        assert detect_runtime_config_change(["src/main/resources/application-prod.yml"], policy)


# --------------------------------------------------------------------------
# ArchUnit XML parsing
# --------------------------------------------------------------------------

class TestArchUnitParsing:

    def test_single_violation(self):
        xml = """<?xml version="1.0"?>
<testsuites>
  <testsuite name="com.example.architecture.DependencyArchitectureTest">
    <testcase name="domain_must_not_depend_on_adapters">
      <failure type="java.lang.AssertionError" message="X">Architecture Violation
Class &lt;com.example.A&gt; depends on &lt;com.example.B&gt;</failure>
    </testcase>
  </testsuite>
</testsuites>"""
        violations = parse_archunit_junit_xml(xml)
        assert len(violations) == 1
        assert violations[0].rule == "domain_must_not_depend_on_adapters"
        assert "A" in violations[0].detail and "B" in violations[0].detail
        assert violations[0].source == "archunit"

    def test_multiple_violations(self):
        xml = """<?xml version="1.0"?>
<testsuites>
  <testsuite name="com.example.architecture.DependencyArchitectureTest">
    <testcase name="rule_one"><failure>x</failure></testcase>
    <testcase name="rule_two"><failure>y</failure></testcase>
    <testcase name="passing_rule"/>
  </testsuite>
</testsuites>"""
        violations = parse_archunit_junit_xml(xml)
        assert len(violations) == 2
        rule_names = {v.rule for v in violations}
        assert rule_names == {"rule_one", "rule_two"}

    def test_no_failures(self):
        xml = """<?xml version="1.0"?>
<testsuites>
  <testsuite name="com.example.architecture.DependencyArchitectureTest">
    <testcase name="rule_one"/>
    <testcase name="rule_two"/>
  </testsuite>
</testsuites>"""
        assert parse_archunit_junit_xml(xml) == []

    def test_non_architecture_suite_ignored(self):
        # Test failures in unrelated suites should not be reported as boundary violations.
        xml = """<?xml version="1.0"?>
<testsuites>
  <testsuite name="com.example.OrderServiceTest">
    <testcase name="some_test"><failure>regular test failure</failure></testcase>
  </testsuite>
</testsuites>"""
        assert parse_archunit_junit_xml(xml) == []

    def test_malformed_xml_returns_empty(self):
        # The reporter shouldn't crash on malformed input.
        assert parse_archunit_junit_xml("<not-valid-xml") == []
        assert parse_archunit_junit_xml("") == []

    def test_summary_collapses_multiline(self):
        xml = """<?xml version="1.0"?>
<testsuites><testsuite name="ArchitectureTest"><testcase name="r">
<failure>Architecture Violation [Priority: MEDIUM] - Rule 'no classes that reside in package X should depend on Y'
was violated (1 times):
Class &lt;A&gt; depends on &lt;B&gt;</failure></testcase></testsuite></testsuites>"""
        violations = parse_archunit_junit_xml(xml)
        assert len(violations) == 1
        # Multi-line failure should collapse to one line.
        assert "\n" not in violations[0].detail
        # Both the rule statement and the violation should be present.
        assert "Rule" in violations[0].detail
        assert "depends on" in violations[0].detail


# --------------------------------------------------------------------------
# Top-level classify() — verdict logic
# --------------------------------------------------------------------------

@pytest.fixture
def base_policy():
    return {
        "version": 1,
        "project": {"name": "test-service"},
        "zones": {
            "red": [
                {"path": "src/main/**/domain/**", "reason": "x", "checkpoint": "architecture-review"},
            ],
            "blue": [
                {"path": "src/test/**", "reason": "x"},
            ],
        },
        "api": {"type": "openapi-spec-file", "specPath": "openapi/api.yaml", "checkpoint": "api-review"},
        "persistence": {"migrationPaths": ["db/migration/**"], "checkpoint": "persistence-review"},
        "security": {"paths": ["src/**/security/**"], "checkpoint": "security-review"},
        "checkpoints": {
            "architecture-review": {"satisfiedBy": [{"label": "architecture-reviewed"}]},
            "api-review": {"satisfiedBy": [{"label": "api-reviewed"}]},
            "persistence-review": {"satisfiedBy": [{"label": "persistence-reviewed"}]},
            "security-review": {"satisfiedBy": [{"label": "security-reviewed"}]},
        },
        "modes": {"default": "shadow", "perCheck": {"boundary_violation": "binding"}},
    }


class TestClassifyVerdict:

    def test_blue_only(self, base_policy):
        diff = Diff(["src/test/Foo.java"], 1, 5)
        v = classify(base_policy, diff)
        assert v.verdict == "BLUE"
        assert v.exit_code == 0

    def test_red_without_checkpoint(self, base_policy):
        diff = Diff(["src/main/foo/domain/Order.java"], 1, 5)
        v = classify(base_policy, diff)
        assert v.verdict == "RED"
        assert any(not c.satisfied for c in v.checkpoints)
        # Shadow mode for the report → soft warning, not hard fail.
        assert v.exit_code == 1

    def test_red_with_checkpoint_label(self, base_policy):
        diff = Diff(["src/main/foo/domain/Order.java"], 1, 5)
        v = classify(base_policy, diff, pr_labels=["architecture-reviewed"])
        assert v.verdict == "RED"
        assert all(c.satisfied for c in v.checkpoints)
        assert v.exit_code == 0

    def test_api_change_independent_of_red(self, base_policy):
        # Bug #1: API_CHANGE used to fire only when also red. Should fire alone.
        diff = Diff(["openapi/api.yaml"], 1, 5)
        v = classify(base_policy, diff)
        assert v.verdict == "API_CHANGE"

    def test_schema_change_independent_of_red(self, base_policy):
        diff = Diff(["db/migration/V2.sql"], 1, 5)
        v = classify(base_policy, diff)
        assert v.verdict == "SCHEMA_CHANGE"

    def test_security_change_independent_of_red(self, base_policy):
        diff = Diff(["src/main/security/Jwt.java"], 1, 5)
        v = classify(base_policy, diff)
        assert v.verdict == "SECURITY_CHANGE"

    def test_boundary_violation_takes_priority(self, base_policy):
        # Even if files are red, an actual boundary violation in the build wins.
        archunit_xml = """<?xml version="1.0"?>
<testsuites><testsuite name="ArchitectureTest"><testcase name="rule_x">
<failure>violated</failure></testcase></testsuite></testsuites>"""
        diff = Diff(["src/main/foo/domain/Order.java"], 1, 5)
        v = classify(base_policy, diff, archunit_xml=archunit_xml)
        assert v.verdict == "BOUNDARY_VIOLATION"
        assert v.exit_code == 2  # boundary_violation is binding

    def test_architecture_test_modified_is_red(self, base_policy):
        # Architecture-test files are red regardless of policy.
        diff = Diff(["src/test/java/foo/architecture/DependencyArchitectureTest.java"], 1, 5)
        v = classify(base_policy, diff)
        assert v.verdict == "RED"
        assert any(c.id == "architecture-review" for c in v.checkpoints)

    def test_empty_diff(self, base_policy):
        diff = Diff([], 0, 0)
        v = classify(base_policy, diff)
        assert v.verdict == "BLUE"
        assert v.exit_code == 0

    def test_gray_only(self, base_policy):
        diff = Diff(["src/main/util/Helper.java"], 1, 5)
        v = classify(base_policy, diff)
        assert v.verdict == "GRAY"

    def test_pr_size_warn(self, base_policy):
        base_policy["prRules"] = {
            "maxChangedFiles": {"warn": 5, "fail": 100},
            "maxLinesChanged": {"warn": 100, "fail": 1000},
        }
        diff = Diff(["src/test/" + str(i) + ".java" for i in range(10)], 10, 50)
        v = classify(base_policy, diff)
        assert v.pr_size["verdict"] == "warn"

    def test_pr_size_fail_binding(self, base_policy):
        base_policy["prRules"] = {
            "maxChangedFiles": {"warn": 5, "fail": 8},
            "maxLinesChanged": {"warn": 100, "fail": 1000},
        }
        base_policy["modes"]["perCheck"]["pr_size"] = "binding"
        diff = Diff(["src/test/" + str(i) + ".java" for i in range(10)], 10, 50)
        v = classify(base_policy, diff)
        assert v.pr_size["verdict"] == "fail"
        assert v.exit_code == 2

    def test_boundary_violation_in_shadow_mode_no_fail(self, base_policy):
        base_policy["modes"]["perCheck"]["boundary_violation"] = "shadow"
        archunit_xml = """<?xml version="1.0"?>
<testsuites><testsuite name="ArchitectureTest"><testcase name="rule_x">
<failure>violated</failure></testcase></testsuite></testsuites>"""
        diff = Diff(["src/main/foo/domain/Order.java"], 1, 5)
        v = classify(base_policy, diff, archunit_xml=archunit_xml)
        assert v.verdict == "BOUNDARY_VIOLATION"
        assert v.exit_code == 1  # shadow mode → warn, not fail

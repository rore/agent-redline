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
  - watch overlap with blue/red

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
    parse_json_violations,
    detect_api_change,
    detect_schema_change,
    detect_security_change,
    detect_runtime_config_change,
    diff_openapi_specs,
    openapi_diff_is_empty,
    resolve_boundary_input,
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
    def policy_with_zones(red=None, blue=None, watch=None, excludes=None):
        return {
            "zones": {
                "red": [{"path": p, "reason": "x"} for p in (red or [])],
                "blue": [{"path": p, "reason": "x"} for p in (blue or [])],
                "watch": [{"path": p, "reason": "x"} for p in (watch or [])],
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

    def test_watch_is_additive_with_blue(self):
        # A file can be both blue (or gray or red) and on the watch list —
        # watch is a tag, not an exclusive bucket.
        policy = self.policy_with_zones(
            blue=["src/main/**/*Service.java"],
            watch=["src/main/**/*Service.java"],
        )
        c = classify_files(["src/main/app/OrderService.java"], policy)
        assert c["blue"] == ["src/main/app/OrderService.java"]
        assert c["watch"] == ["src/main/app/OrderService.java"]


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
# json-violations parsing
# --------------------------------------------------------------------------

class TestJsonViolationsParsing:

    def test_minimal(self):
        text = '{"violations": [{"rule": "r", "detail": "d"}]}'
        v = parse_json_violations(text)
        assert len(v) == 1
        assert v[0].rule == "r"
        assert v[0].detail == "d"
        assert v[0].severity == "error"
        assert v[0].source == "backend"

    def test_with_source(self):
        text = '{"source": "import-linter", "violations": [{"rule": "r", "detail": "d"}]}'
        v = parse_json_violations(text)
        assert v[0].source == "import-linter"

    def test_multiple(self):
        text = """{
            "version": 1,
            "source": "import-linter",
            "violations": [
                {"rule": "Layered", "detail": "a -> b"},
                {"rule": "Independence", "detail": "c -> d", "severity": "warning"}
            ]
        }"""
        v = parse_json_violations(text)
        assert len(v) == 2
        assert v[0].severity == "error"
        assert v[1].severity == "warning"

    def test_empty_violations(self):
        assert parse_json_violations('{"violations": []}') == []

    def test_malformed_json_returns_empty(self):
        assert parse_json_violations("{not-json") == []
        assert parse_json_violations("") == []

    def test_root_not_object_returns_empty(self):
        assert parse_json_violations('["not", "an", "object"]') == []

    def test_violations_not_array_returns_empty(self):
        assert parse_json_violations('{"violations": "oops"}') == []

    def test_skips_missing_required_fields(self):
        text = """{
            "violations": [
                {"rule": "good", "detail": "ok"},
                {"rule": "no-detail"},
                {"detail": "no-rule"},
                {"rule": "", "detail": "empty-rule"},
                "not-an-object"
            ]
        }"""
        v = parse_json_violations(text)
        assert len(v) == 1
        assert v[0].rule == "good"

    def test_unknown_severity_falls_back_to_error(self):
        text = '{"violations": [{"rule": "r", "detail": "d", "severity": "exotic"}]}'
        v = parse_json_violations(text)
        assert v[0].severity == "error"

    def test_long_detail_summarized(self):
        long = "x" * 500
        text = '{"violations": [{"rule": "r", "detail": "' + long + '"}]}'
        v = parse_json_violations(text)
        # _summarize_violation truncates to 400 + ellipsis
        assert len(v[0].detail) <= 401


# --------------------------------------------------------------------------
# classify() with boundary_report parameter
# --------------------------------------------------------------------------

class TestClassifyBoundaryReport:

    def _policy(self):
        return {
            "version": 1,
            "project": {"name": "t"},
            "zones": {"red": [{"path": "src/**", "reason": "x", "checkpoint": "architecture-review"}]},
            "checkpoints": {"architecture-review": {"satisfiedBy": [{"label": "ok"}]}},
            "modes": {"default": "binding"},
        }

    def test_boundary_report_json(self):
        diff = Diff(changed_files=["src/foo.py"], files_changed=1, lines_changed=1)
        report = '{"violations": [{"rule": "r", "detail": "d"}]}'
        v = classify(self._policy(), diff,
                     boundary_report=report, boundary_format="json-violations")
        assert v.verdict == "BOUNDARY_VIOLATION"
        assert len(v.boundary_violations) == 1
        assert v.boundary_violations[0].source == "backend"

    def test_boundary_report_junit_xml(self):
        diff = Diff(changed_files=["src/foo.py"], files_changed=1, lines_changed=1)
        xml = """<?xml version="1.0"?>
<testsuites><testsuite name="ArchitectureTest"><testcase name="r">
<failure>x</failure></testcase></testsuite></testsuites>"""
        v = classify(self._policy(), diff,
                     boundary_report=xml, boundary_format="junit-xml")
        assert v.verdict == "BOUNDARY_VIOLATION"

    def test_archunit_xml_kw_still_works(self):
        # Back-compat: the legacy archunit_xml kwarg still parses junit-xml.
        diff = Diff(changed_files=["src/foo.py"], files_changed=1, lines_changed=1)
        xml = """<?xml version="1.0"?>
<testsuites><testsuite name="ArchitectureTest"><testcase name="r">
<failure>x</failure></testcase></testsuite></testsuites>"""
        v = classify(self._policy(), diff, archunit_xml=xml)
        assert v.verdict == "BOUNDARY_VIOLATION"

    def test_boundary_format_none_skips_parsing(self):
        diff = Diff(changed_files=["src/foo.py"], files_changed=1, lines_changed=1)
        # Even if a report is passed, format=none means no boundary parsing.
        v = classify(self._policy(), diff,
                     boundary_report='{"violations": [{"rule": "r", "detail": "d"}]}',
                     boundary_format="none")
        assert v.boundary_violations == []
        assert v.verdict != "BOUNDARY_VIOLATION"

    def test_unknown_format_ignored(self):
        diff = Diff(changed_files=["src/foo.py"], files_changed=1, lines_changed=1)
        v = classify(self._policy(), diff,
                     boundary_report="<garbage/>", boundary_format="invented")
        assert v.boundary_violations == []


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

    def test_pr_size_excludes_subtract_when_lines_per_file_present(self, base_policy):
        # Regression for the bug Pallium hit: excludes:** filtered the
        # zone classification but NOT the size budget, because the
        # workflow handed the reporter a pre-computed scalar that
        # already counted excluded files. With --lines-per-file
        # populated, excluded paths must be subtracted from BOTH file
        # and line counts.
        base_policy["prRules"] = {
            "maxChangedFiles": {"warn": 3, "fail": 6},
            "maxLinesChanged": {"warn": 100, "fail": 300},
        }
        base_policy["excludes"] = ["**/generated/**"]
        diff = Diff(
            changed_files=[
                "src/main/foo/Real.java",
                "src/main/generated/proto/order_pb2.py",
                "src/main/generated/proto/payment_pb2.py",
            ],
            files_changed=3,
            lines_changed=10005,
            lines_by_file={
                "src/main/foo/Real.java": 5,
                "src/main/generated/proto/order_pb2.py": 6000,
                "src/main/generated/proto/payment_pb2.py": 4000,
            },
        )
        v = classify(base_policy, diff)
        # 1 in-scope file / 5 lines should be ok; the 10000-line excluded
        # files MUST NOT trip fail.
        assert v.pr_size["files"] == 1
        assert v.pr_size["lines"] == 5
        assert v.pr_size["excludedFiles"] == 2
        assert v.pr_size["excludedLines"] == 10000
        assert v.pr_size["verdict"] == "ok"

    def test_pr_size_falls_back_to_scalar_without_lines_per_file(self, base_policy):
        # Without --lines-per-file, the scalar is the only signal
        # available; we can't subtract excluded lines from it. File
        # count IS still excludes-aware (changed-files list filtering).
        base_policy["prRules"] = {
            "maxChangedFiles": {"warn": 3, "fail": 6},
            "maxLinesChanged": {"warn": 100, "fail": 300},
        }
        base_policy["excludes"] = ["**/generated/**"]
        diff = Diff(
            changed_files=[
                "src/main/foo/Real.java",
                "src/main/generated/proto/order_pb2.py",
            ],
            files_changed=2,
            lines_changed=500,  # scalar; reporter can't decompose it
            lines_by_file=None,
        )
        v = classify(base_policy, diff)
        assert v.pr_size["files"] == 1                  # 2 - 1 excluded
        assert v.pr_size["lines"] == 500                # scalar passes through
        assert v.pr_size["excludedFiles"] == 1
        assert v.pr_size["excludedLines"] == 0          # unknowable without per-file
        assert v.pr_size["verdict"] == "fail"           # 500 > 300 line budget

    def test_boundary_violation_in_shadow_mode_no_fail(self, base_policy):
        base_policy["modes"]["perCheck"]["boundary_violation"] = "shadow"
        archunit_xml = """<?xml version="1.0"?>
<testsuites><testsuite name="ArchitectureTest"><testcase name="rule_x">
<failure>violated</failure></testcase></testsuite></testsuites>"""
        diff = Diff(["src/main/foo/domain/Order.java"], 1, 5)
        v = classify(base_policy, diff, archunit_xml=archunit_xml)
        assert v.verdict == "BOUNDARY_VIOLATION"
        assert v.exit_code == 1  # shadow mode → warn, not fail


# ----------------------------------------------------------------------------
# diff_openapi_specs — structural OpenAPI diff
# ----------------------------------------------------------------------------

class TestOpenApiDiff:

    def test_identical_specs_diff_is_empty(self):
        spec = """openapi: 3.0.0
paths:
  /a:
    get: { summary: a }
"""
        d = diff_openapi_specs(spec, spec)
        assert d == {"pathsAdded": [], "pathsRemoved": [], "pathsModified": []}
        assert openapi_diff_is_empty(d)

    def test_added_path(self):
        base = "openapi: 3.0.0\npaths:\n  /a:\n    get: { summary: a }\n"
        head = ("openapi: 3.0.0\npaths:\n"
                "  /a:\n    get: { summary: a }\n"
                "  /b:\n    post: { summary: b }\n")
        d = diff_openapi_specs(base, head)
        assert d["pathsAdded"] == ["/b"]
        assert d["pathsRemoved"] == []
        assert d["pathsModified"] == []
        assert not openapi_diff_is_empty(d)

    def test_removed_path(self):
        base = ("openapi: 3.0.0\npaths:\n"
                "  /a:\n    get: { summary: a }\n"
                "  /b:\n    post: { summary: b }\n")
        head = "openapi: 3.0.0\npaths:\n  /a:\n    get: { summary: a }\n"
        d = diff_openapi_specs(base, head)
        assert d["pathsAdded"] == []
        assert d["pathsRemoved"] == ["/b"]
        assert d["pathsModified"] == []

    def test_method_added_to_existing_path(self):
        base = "openapi: 3.0.0\npaths:\n  /a:\n    get: { summary: a }\n"
        head = ("openapi: 3.0.0\npaths:\n  /a:\n"
                "    get: { summary: a }\n"
                "    post: { summary: a-post }\n")
        d = diff_openapi_specs(base, head)
        assert d["pathsAdded"] == []
        assert d["pathsRemoved"] == []
        assert len(d["pathsModified"]) == 1
        assert d["pathsModified"][0] == {
            "path": "/a",
            "methodsAdded": ["post"],
            "methodsRemoved": [],
            "methodsModified": [],
        }

    def test_method_modified(self):
        base = "openapi: 3.0.0\npaths:\n  /a:\n    get: { summary: old }\n"
        head = "openapi: 3.0.0\npaths:\n  /a:\n    get: { summary: new }\n"
        d = diff_openapi_specs(base, head)
        assert d["pathsModified"] == [{
            "path": "/a",
            "methodsAdded": [],
            "methodsRemoved": [],
            "methodsModified": ["get"],
        }]

    def test_only_method_modifications_count(self):
        # Path-item-level fields like 'summary' are not tracked as method changes.
        base = "openapi: 3.0.0\npaths:\n  /a:\n    summary: old summary\n    get: { summary: a }\n"
        head = "openapi: 3.0.0\npaths:\n  /a:\n    summary: new summary\n    get: { summary: a }\n"
        d = diff_openapi_specs(base, head)
        # /a is in both specs and its method (get) is unchanged → not modified.
        assert d["pathsModified"] == []

    def test_empty_strings_treated_as_no_paths(self):
        d = diff_openapi_specs("", "")
        assert openapi_diff_is_empty(d)

    def test_one_side_empty_means_full_addition(self):
        head = "openapi: 3.0.0\npaths:\n  /a:\n    get: { summary: a }\n"
        d = diff_openapi_specs("", head)
        assert d["pathsAdded"] == ["/a"]
        assert d["pathsRemoved"] == []

    def test_malformed_yaml_is_treated_as_empty(self):
        # Don't crash on bad input; treat as empty so downstream logic still works.
        d = diff_openapi_specs("not: valid: yaml: at: all", "openapi: 3.0.0\npaths:\n  /a:\n    get: {}\n")
        # Both sides parse as scalars-or-empty; head has /a as added.
        assert "/a" in d["pathsAdded"]

    def test_non_method_keys_ignored(self):
        # 'parameters' on path item is not a method; should not be tracked.
        base = ("openapi: 3.0.0\npaths:\n  /a:\n"
                "    parameters: []\n"
                "    get: { summary: a }\n")
        head = ("openapi: 3.0.0\npaths:\n  /a:\n"
                "    parameters: [{ in: query, name: x }]\n"
                "    get: { summary: a }\n")
        d = diff_openapi_specs(base, head)
        # Only method-level changes count; parameters change is ignored.
        assert d["pathsModified"] == []

    def test_classify_with_api_spec_diff_forces_api_changed(self, ):
        """classify(api_spec_diff=...) sets api_changed=True even with no api.specPath."""
        policy = {
            "version": 1,
            "project": {"name": "x"},
            "zones": {
                "red": [{"path": "src/main/**/domain/**", "reason": "domain",
                         "checkpoint": "architecture-review"}],
                "blue": [{"path": "src/test/**", "reason": "tests"}],
            },
            "api": {"type": "openapi-from-controllers", "generationCommand": "echo"},
            "checkpoints": {
                "architecture-review": {"satisfiedBy": [{"label": "x"}]},
                "api-review": {"satisfiedBy": [{"label": "y"}]},
            },
            "modes": {"default": "shadow"},
        }
        diff = Diff(["src/test/Foo.java"], 1, 5)
        # Empty diff: api_changed stays False.
        v = classify(policy, diff, api_spec_diff={"pathsAdded": [], "pathsRemoved": [], "pathsModified": []})
        assert v.api_changes["detected"] is False
        # Non-empty diff: api_changed=True; specDiff carried through.
        v = classify(policy, diff, api_spec_diff={"pathsAdded": ["/x"], "pathsRemoved": [], "pathsModified": []})
        assert v.api_changes["detected"] is True
        assert v.api_changes["specDiff"]["pathsAdded"] == ["/x"]


# --------------------------------------------------------------------------
# resolve_boundary_input — fail loudly when configured backend output is missing
#
# Silent fallthrough used to let a misconfigured CI run produce a clean BLUE
# verdict despite policy declaring boundaryAdapter. These regressions cover
# the three configured paths: explicit --boundary-report, legacy --archunit-xml,
# and policy.boundaryAdapter glob.
# --------------------------------------------------------------------------

class TestResolveBoundaryInputMissingFile:
    def test_no_source_configured_returns_none(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        text, fmt = resolve_boundary_input(None, None, None, {})
        assert text is None and fmt is None

    def test_explicit_report_missing_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError, match="--boundary-report path does not exist"):
            resolve_boundary_input(tmp_path / "missing.json", "json-violations", None, {})

    def test_legacy_archunit_missing_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError, match="--archunit-xml path does not exist"):
            resolve_boundary_input(None, None, tmp_path / "missing.xml", {})

    def test_policy_adapter_no_match_raises(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        policy = {
            "boundaryAdapter": {
                "outputFormat": "json-violations",
                "outputPath": "build/import-linter-report.json",
            }
        }
        with pytest.raises(FileNotFoundError, match="boundaryAdapter.outputPath matched no file"):
            resolve_boundary_input(None, None, None, policy)

    def test_policy_adapter_outputformat_none_skips_silently(self, tmp_path, monkeypatch):
        """outputFormat: none is the explicit opt-out; do not raise."""
        monkeypatch.chdir(tmp_path)
        policy = {"boundaryAdapter": {"outputFormat": "none"}}
        text, fmt = resolve_boundary_input(None, None, None, policy)
        assert text is None and fmt is None

    def test_policy_adapter_match_returns_text(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "build").mkdir()
        report = tmp_path / "build" / "out.json"
        report.write_text('{"version":1,"source":"test","violations":[]}', encoding="utf-8")
        policy = {
            "boundaryAdapter": {
                "outputFormat": "json-violations",
                "outputPath": "build/out.json",
            }
        }
        text, fmt = resolve_boundary_input(None, None, None, policy)
        assert fmt == "json-violations"
        assert "violations" in text


# --------------------------------------------------------------------------
# Unified-diff parsing (Phase 1 of suppression detection)
# --------------------------------------------------------------------------

class TestParseUnifiedDiff:
    def test_extracts_added_lines_per_file(self):
        from core.reporter.reporter import parse_unified_diff
        patch = (
            "diff --git a/a.py b/a.py\n"
            "--- a/a.py\n+++ b/a.py\n"
            "@@ -1,0 +2,2 @@\n"
            "+import os  # noqa: F401\n"
            "+x = 1\n"
            "diff --git a/b.py b/b.py\n"
            "--- a/b.py\n+++ b/b.py\n"
            "@@ -10,1 +10,1 @@\n"
            "-old\n"
            "+new  # type: ignore\n"
        )
        added = parse_unified_diff(patch)
        assert added == {
            "a.py": [(2, "import os  # noqa: F401"), (3, "x = 1")],
            "b.py": [(10, "new  # type: ignore")],
        }

    def test_handles_new_file(self):
        from core.reporter.reporter import parse_unified_diff
        patch = (
            "diff --git a/new.py b/new.py\n"
            "new file mode 100644\n"
            "--- /dev/null\n+++ b/new.py\n"
            "@@ -0,0 +1,2 @@\n"
            "+# nosec\n"
            "+pass\n"
        )
        assert parse_unified_diff(patch) == {
            "new.py": [(1, "# nosec"), (2, "pass")],
        }

    def test_skips_deleted_file(self):
        from core.reporter.reporter import parse_unified_diff
        patch = (
            "diff --git a/gone.py b/gone.py\n"
            "deleted file mode 100644\n"
            "--- a/gone.py\n+++ /dev/null\n"
            "@@ -1,1 +0,0 @@\n"
            "-x = 1\n"
        )
        assert parse_unified_diff(patch) == {}

    def test_renames_use_post_path(self):
        from core.reporter.reporter import parse_unified_diff
        patch = (
            "diff --git a/old.py b/new.py\n"
            "rename from old.py\nrename to new.py\n"
            "--- a/old.py\n+++ b/new.py\n"
            "@@ -1,1 +1,1 @@\n"
            "-x = 1\n"
            "+x = 1  # noqa\n"
        )
        assert parse_unified_diff(patch) == {"new.py": [(1, "x = 1  # noqa")]}

    def test_empty_patch(self):
        from core.reporter.reporter import parse_unified_diff
        assert parse_unified_diff("") == {}


# --------------------------------------------------------------------------
# Suppressions resolution (Phase 2)
# --------------------------------------------------------------------------

class TestSuppressionsResolution:
    def test_absent_block_means_detection_off(self, tmp_path):
        """Spec §1.4 compatibility — non-negotiable."""
        from core.reporter.reporter import resolve_suppressions_config
        cfg = resolve_suppressions_config(policy={}, repo_root=tmp_path)
        assert cfg is None

    def test_missing_vendored_file_is_silent_when_no_block(self, tmp_path):
        from core.reporter.reporter import resolve_suppressions_config
        # Policy has no suppressions block; vendored file absent. No error.
        cfg = resolve_suppressions_config(policy={"version": 1}, repo_root=tmp_path)
        assert cfg is None

    def test_missing_vendored_file_errors_only_when_useDefaults_true(self, tmp_path):
        from core.reporter.reporter import resolve_suppressions_config
        policy = {"suppressions": {"useExtensionDefaults": True}}
        # All three conditions met (block + useDefaults + missing file).
        try:
            resolve_suppressions_config(policy=policy, repo_root=tmp_path)
            assert False, "expected FileNotFoundError"
        except FileNotFoundError as e:
            msg = str(e)
            assert ".agent-redline/suppressions.yaml" in msg
            # Confirm the three remediations are surfaced (spec §1.4):
            # (1) re-run bootstrap, (2) useExtensionDefaults: false, (3) remove the block.
            assert "re-run bootstrap" in msg
            assert "useExtensionDefaults: false" in msg
            assert "remove the suppressions" in msg

    def test_useDefaults_false_skips_missing_file(self, tmp_path):
        from core.reporter.reporter import resolve_suppressions_config
        policy = {"suppressions": {"useExtensionDefaults": False,
                                   "add": {"inlineComments": ["# nosec"]}}}
        cfg = resolve_suppressions_config(policy=policy, repo_root=tmp_path)
        assert cfg.inline_comments == ["# nosec"]
        assert cfg.annotations == []

    def test_merge_add_then_remove(self, tmp_path):
        # Vendored: ["# noqa", "# type: ignore"]; add: ["# custom"]; remove: ["# noqa"]
        (tmp_path / ".agent-redline").mkdir()
        (tmp_path / ".agent-redline" / "suppressions.yaml").write_text(
            "suppressions:\n"
            "  inlineComments:\n"
            "    - '# noqa'\n"
            "    - '# type: ignore'\n"
        )
        from core.reporter.reporter import resolve_suppressions_config
        policy = {"suppressions": {
            "useExtensionDefaults": True,
            "add": {"inlineComments": ["# custom"]},
            "remove": {"inlineComments": ["# noqa"]},
        }}
        cfg = resolve_suppressions_config(policy=policy, repo_root=tmp_path)
        assert sorted(cfg.inline_comments) == ["# custom", "# type: ignore"]

    def test_exempt_paths_round_trip(self, tmp_path):
        from core.reporter.reporter import resolve_suppressions_config
        policy = {"suppressions": {
            "useExtensionDefaults": False,
            "add": {"inlineComments": ["# nosec"]},
            "exemptPaths": ["**/tests/**", "vendor/**"],
        }}
        cfg = resolve_suppressions_config(policy=policy, repo_root=tmp_path)
        assert cfg.exempt_paths == ["**/tests/**", "vendor/**"]


class TestScanSuppressions:
    def test_inline_comment_substring_match(self):
        from core.reporter.reporter import scan_suppressions, SuppressionsConfig
        config = SuppressionsConfig(inline_comments=["# noqa"])
        added = {"src/example/orders.py": [(42, "from pkg.x import y  # noqa: F401")]}
        classification = {"red": ["src/example/orders.py"], "blue": [], "gray": [], "watch": []}
        matches = scan_suppressions(added, config, classification)
        assert len(matches) == 1
        m = matches[0]
        assert m.file == "src/example/orders.py"
        assert m.line == 42
        assert m.marker == "# noqa"
        assert m.category == "inlineComment"
        assert m.zone == "red"
        assert "# noqa" in m.context

    def test_multiple_markers_one_line_produce_multiple_matches(self):
        from core.reporter.reporter import scan_suppressions, SuppressionsConfig
        config = SuppressionsConfig(inline_comments=["# noqa", "# type: ignore"])
        added = {"a.py": [(1, "x = y  # noqa: F401  # type: ignore[misc]")]}
        classification = {"red": [], "blue": ["a.py"], "gray": [], "watch": []}
        matches = scan_suppressions(added, config, classification)
        assert len(matches) == 2
        markers = [m.marker for m in matches]
        # Order = order of inline_comments list (deterministic)
        assert markers == ["# noqa", "# type: ignore"]

    def test_annotation_token_match_word_bounded(self):
        from core.reporter.reporter import scan_suppressions, SuppressionsConfig
        config = SuppressionsConfig(annotations=["@SuppressWarnings"])
        # Real annotation matches.
        added = {"X.java": [(10, '@SuppressWarnings("ArchUnit")')]}
        classification = {"red": ["X.java"], "blue": [], "gray": [], "watch": []}
        matches = scan_suppressions(added, config, classification)
        assert len(matches) == 1
        assert matches[0].category == "annotation"
        assert matches[0].marker == "@SuppressWarnings"

    def test_annotation_no_match_on_extended_name(self):
        from core.reporter.reporter import scan_suppressions, SuppressionsConfig
        config = SuppressionsConfig(annotations=["@SuppressWarnings"])
        added = {"X.java": [(10, '@SuppressWarningsExt("foo")')]}
        classification = {"red": ["X.java"], "blue": [], "gray": [], "watch": []}
        matches = scan_suppressions(added, config, classification)
        assert matches == []

    def test_config_edits_structural_key_match(self):
        from core.reporter.reporter import scan_suppressions, SuppressionsConfig
        config = SuppressionsConfig(
            config_files=["pyproject.toml"],
            config_keys=["ignore_imports"],
        )
        added = {"pyproject.toml": [(20, 'ignore_imports = ["pkg.a -> pkg.b"]')]}
        classification = {"red": ["pyproject.toml"], "blue": [], "gray": [], "watch": []}
        matches = scan_suppressions(added, config, classification)
        assert len(matches) == 1
        assert matches[0].category == "configEdit"
        assert matches[0].marker == "ignore_imports"

    def test_config_edits_ignores_comment_lines(self):
        from core.reporter.reporter import scan_suppressions, SuppressionsConfig
        config = SuppressionsConfig(
            config_files=["pyproject.toml"],
            config_keys=["ignore_imports"],
        )
        # A line that mentions the key only inside a comment must NOT match.
        added = {"pyproject.toml": [(20, "# ignore_imports does cool stuff")]}
        classification = {"red": ["pyproject.toml"], "blue": [], "gray": [], "watch": []}
        matches = scan_suppressions(added, config, classification)
        assert matches == []

    def test_exempt_paths_skips_file(self):
        from core.reporter.reporter import scan_suppressions, SuppressionsConfig
        config = SuppressionsConfig(
            inline_comments=["# noqa"],
            exempt_paths=["**/tests/**"],
        )
        added = {"tests/conftest.py": [(5, "import x  # noqa: E402")]}
        classification = {"red": [], "blue": ["tests/conftest.py"], "gray": [], "watch": []}
        matches = scan_suppressions(added, config, classification)
        assert matches == []

    def test_reformat_fires_known_fp(self):
        """Spec §6 — accepted v1 false positive. Naive added-line scanning."""
        from core.reporter.reporter import scan_suppressions, SuppressionsConfig
        config = SuppressionsConfig(inline_comments=["# noqa"])
        # `foo()  # noqa` was removed; `bar()  # noqa` was added (rename-on-line reformat).
        # The naive algorithm fires on the added line. By design.
        added = {"a.py": [(10, "bar()  # noqa: E501")]}
        classification = {"red": ["a.py"], "blue": [], "gray": [], "watch": []}
        matches = scan_suppressions(added, config, classification)
        assert len(matches) == 1
        assert matches[0].marker == "# noqa"

    def test_no_config_returns_empty(self):
        """Compatibility path: no suppressions config → no matches."""
        from core.reporter.reporter import scan_suppressions
        added = {"a.py": [(1, "import x  # noqa")]}
        classification = {"red": ["a.py"], "blue": [], "gray": [], "watch": []}
        matches = scan_suppressions(added, None, classification)
        assert matches == []

    def test_no_diff_returns_empty(self):
        """No `--diff-unified` provided → no matches."""
        from core.reporter.reporter import scan_suppressions, SuppressionsConfig
        config = SuppressionsConfig(inline_comments=["# noqa"])
        classification = {"red": [], "blue": [], "gray": [], "watch": []}
        assert scan_suppressions(None, config, classification) == []

    def test_zone_classification_from_classify_files(self):
        """Match's zone = file's primary zone (red > gray > blue residual)."""
        from core.reporter.reporter import scan_suppressions, SuppressionsConfig
        config = SuppressionsConfig(inline_comments=["# noqa"])
        added = {
            "red.py":   [(1, "x  # noqa")],
            "blue.py":  [(1, "y  # noqa")],
            "gray.py":  [(1, "z  # noqa")],
        }
        classification = {
            "red":   ["red.py"],
            "blue":  ["blue.py"],
            "gray":  ["gray.py"],
            "watch": [],
        }
        matches = scan_suppressions(added, config, classification)
        zones = {m.file: m.zone for m in matches}
        assert zones == {"red.py": "red", "blue.py": "blue", "gray.py": "gray"}


# --------------------------------------------------------------------------
# Suppressions checkpoint wiring (Phase 4b.2 — cmt_000010)
#
# Spec §2.3: a suppression match on a non-exempt path always contributes
# architecture-review to the reporter's required checkpoints, INDEPENDENT
# of the headline verdict. setdefault semantics mean a higher-priority
# reason (red-zone change, arch-test edit) wins for the displayed reason,
# but the requirement is still emitted from the suppression code path.
#
# These tests pin _required_checkpoints() wiring only. End-to-end
# headline + comment behavior lands in Phase 4b.3 / 4b.4 and is covered
# by the seven Phase-5 golden fixtures.
# --------------------------------------------------------------------------

class TestSuppressionsCheckpointWiring:

    @staticmethod
    def _policy_no_red():
        """Policy with no red zone — isolates the suppression code path."""
        return {
            "version": 1,
            "project": {"name": "t"},
            "zones": {
                "blue": [{"path": "src/**", "reason": "x"}],
            },
            "checkpoints": {
                "architecture-review": {"satisfiedBy": [{"label": "ok"}]},
            },
            "modes": {"default": "shadow"},
        }

    @staticmethod
    def _policy_with_red():
        return {
            "version": 1,
            "project": {"name": "t"},
            "zones": {
                "red": [{"path": "src/main/**/domain/**", "reason": "domain",
                         "checkpoint": "architecture-review"}],
                "blue": [{"path": "src/**", "reason": "x"}],
            },
            "checkpoints": {
                "architecture-review": {"satisfiedBy": [{"label": "ok"}]},
            },
            "modes": {"default": "shadow"},
        }

    def test_suppression_only_diff_emits_architecture_review(self):
        """Case 1: suppression match on non-red blue file → architecture-review required.

        Headline verdict in this phase may be BLUE (4b.3 promotes to RED).
        We assert only on Verdict.suppressions and required-checkpoints.
        """
        from core.reporter.reporter import SuppressionsConfig
        cfg = SuppressionsConfig(inline_comments=["# noqa"])
        diff = Diff(
            changed_files=["src/example/orders.py"],
            files_changed=1,
            lines_changed=1,
            added_by_file={"src/example/orders.py": [(7, "import x  # noqa: F401")]},
        )
        v = classify(self._policy_no_red(), diff, suppressions_config=cfg)
        # The match landed.
        assert len(v.suppressions) == 1
        assert v.suppressions[0].marker == "# noqa"
        # architecture-review is required, attributed to the suppression.
        cp_ids = [c.id for c in v.checkpoints]
        assert cp_ids.count("architecture-review") == 1
        cp = next(c for c in v.checkpoints if c.id == "architecture-review")
        assert "Suppression marker" in cp.reason
        assert "# noqa" in cp.reason
        assert "src/example/orders.py:7" in cp.reason

    def test_suppression_plus_red_zone_dedupes_reason_wins_red(self):
        """Case 2: suppression + red-zone path → architecture-review required ONCE.

        setdefault means the existing red-zone reason wins. The requirement
        stays put — that's the cmt_000010 invariant.
        """
        from core.reporter.reporter import SuppressionsConfig
        cfg = SuppressionsConfig(inline_comments=["# noqa"])
        red_file = "src/main/foo/domain/Order.java"
        diff = Diff(
            changed_files=[red_file],
            files_changed=1,
            lines_changed=1,
            added_by_file={red_file: [(42, "x  // noqa: something")]},
        )
        # The marker `# noqa` won't substring-match `// noqa`, so use a marker
        # that matches Java-style comments — switch to a marker we control.
        cfg = SuppressionsConfig(inline_comments=["// noqa"])
        v = classify(self._policy_with_red(), diff, suppressions_config=cfg)
        # Both signals fire: the suppression match and the red-zone change.
        assert len(v.suppressions) == 1
        # architecture-review appears exactly once (deduped via setdefault).
        cp_ids = [c.id for c in v.checkpoints]
        assert cp_ids.count("architecture-review") == 1
        cp = next(c for c in v.checkpoints if c.id == "architecture-review")
        # Existing red-zone reason wins (setdefault semantics).
        assert "red-zone change" in cp.reason
        assert red_file in cp.reason
        assert "Suppression marker" not in cp.reason

    def test_empty_match_list_does_not_add_checkpoint(self):
        """Case 3: no suppression matches → suppression code path is a no-op.

        Use a no-red-zone policy with a blue-only diff so the only way
        architecture-review could get added is via the suppression branch.
        """
        from core.reporter.reporter import SuppressionsConfig
        cfg = SuppressionsConfig(inline_comments=["# noqa"])
        diff = Diff(
            changed_files=["src/example/orders.py"],
            files_changed=1,
            lines_changed=1,
            added_by_file={"src/example/orders.py": [(7, "import x  # plain")]},
        )
        v = classify(self._policy_no_red(), diff, suppressions_config=cfg)
        assert v.suppressions == []
        cp_ids = [c.id for c in v.checkpoints]
        assert "architecture-review" not in cp_ids

    def test_suppression_on_exempt_path_does_not_add_checkpoint(self):
        """Case 4: scan_suppressions filtered the match → no checkpoint added."""
        from core.reporter.reporter import SuppressionsConfig
        cfg = SuppressionsConfig(
            inline_comments=["# noqa"],
            exempt_paths=["**/tests/**"],
        )
        diff = Diff(
            changed_files=["tests/conftest.py"],
            files_changed=1,
            lines_changed=1,
            added_by_file={"tests/conftest.py": [(5, "import x  # noqa: E402")]},
        )
        v = classify(self._policy_no_red(), diff, suppressions_config=cfg)
        # scan_suppressions returned [] because the file is exempt.
        assert v.suppressions == []
        cp_ids = [c.id for c in v.checkpoints]
        assert "architecture-review" not in cp_ids

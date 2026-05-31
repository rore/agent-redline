"""
tests/reporter/test_schema_coverage.py

Coherence checks between the schema and the things that reference it.

The schema describes only what the reporter actually does — there are no
"reserved for later" fields. These tests catch the cases where docs or
templates drift away from the schema (a YAML example that uses a field the
schema no longer accepts, a docs page that still talks about a field that
was removed, etc.).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT))

import pytest  # type: ignore


SCHEMA_PATH = REPO_ROOT / "core" / "schema" / "agent-policy.schema.json"
TEMPLATE_PATH = REPO_ROOT / "core" / "templates" / "agent-policy.yaml.template"
POLICY_SCHEMA_DOC = REPO_ROOT / "docs" / "POLICY_SCHEMA.md"


def _schema():
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# 1. Removed fields stay removed
# ---------------------------------------------------------------------------

REMOVED_TOP_LEVEL = ("changeRules", "boundaryBackend", "defaults")


@pytest.mark.parametrize("field", REMOVED_TOP_LEVEL)
def test_schema_does_not_reintroduce_removed_top_level_field(field):
    """If we re-add one of these, design the rest of the surface first.

    See SPEC §15.3 — these fields were dropped because their behavior was
    not implemented. Bringing them back without implementing them puts us
    right back into the over-engineering they came from.
    """
    schema = _schema()
    assert field not in schema["properties"], (
        f"Top-level '{field}' was removed in v0.1 because the reporter does "
        "not implement it. If you're re-adding it, also implement the behavior, "
        "update SPEC §15.3, and remove it from REMOVED_TOP_LEVEL in this test."
    )


def test_api_type_enum_includes_implemented_modes_only():
    """Every value in api.type must have reporter behavior backing it.

    `openapi-from-controllers` was added back when the reporter learned to
    diff base/head specs (the workflow generates them; the reporter diffs).
    `none`, `openapi-spec-file`, `graphql`, `proto` are path-glob detection.
    If we add a new enum value, the reporter must implement it before the
    schema accepts it.
    """
    schema = _schema()
    api_types = schema["properties"]["api"]["properties"]["type"]["enum"]
    assert set(api_types) == {
        "none",
        "openapi-spec-file",
        "openapi-from-controllers",
        "graphql",
        "proto",
    }, (
        "api.type enum drifted. Every accepted value must be implemented by "
        "core/reporter/reporter.py:detect_api_change or the openapi-diff path. "
        "If you're adding a value, implement it first; if you're removing one, "
        "update this test."
    )


def test_satisfied_by_does_not_reintroduce_team_or_reviewer_count():
    schema = _schema()
    forms = (
        schema["properties"]["checkpoints"]["patternProperties"]
        ["^[a-z0-9]+(-[a-z0-9]+)*$"]["properties"]["satisfiedBy"]["items"]["oneOf"]
    )
    forms_text = json.dumps(forms)
    assert "team" not in forms_text, (
        "satisfiedBy 'team' was dropped because v0.1 cannot query host team "
        "membership. Re-add only when the reporter actually checks team approval."
    )
    assert "reviewerCount" not in forms_text, (
        "satisfiedBy 'reviewerCount' was dropped because v0.1 does not count "
        "approvals. Re-add only when the reporter actually counts them."
    )


def test_pr_rules_does_not_reintroduce_unimplemented_fields():
    """rejectVerboseGeneratedDescriptions and requireVerificationSection
    were declared by the schema but never wired into the reporter. Per the
    schema-honesty principle (DECISIONS), they were removed in v0.1 polish.
    Re-add only when the reporter implements them — see SPEC §11.3 + §15.3.
    """
    schema = _schema()
    pr_rules_props = schema["properties"]["prRules"]["properties"]
    assert "rejectVerboseGeneratedDescriptions" not in pr_rules_props, (
        "prRules.rejectVerboseGeneratedDescriptions was removed because the "
        "reporter does not implement verbose-description detection. Re-add "
        "only after the reporter actually flags slop."
    )
    assert "requireVerificationSection" not in pr_rules_props, (
        "prRules.requireVerificationSection was removed because the reporter "
        "does not check PR descriptions for a Verification heading. Re-add "
        "only after the reporter implements it."
    )


# ---------------------------------------------------------------------------
# 2. Templates and docs only reference fields that exist in the schema
# ---------------------------------------------------------------------------

def test_template_does_not_reference_removed_fields():
    """The on-disk template must not bootstrap a policy with phantom fields."""
    text = TEMPLATE_PATH.read_text(encoding="utf-8")
    # Strip comments before checking — doc references in comments are fine.
    payload = "\n".join(
        line for line in text.splitlines() if not line.lstrip().startswith("#")
    )
    for field in ("changeRules:", "boundaryBackend:", "unclassifiedZone:", "grayMode:"):
        assert field not in payload, (
            f"agent-policy.yaml.template still has '{field}' as a real field. "
            "It was removed from the schema; remove it from the template too."
        )


def test_policy_schema_doc_does_not_advertise_brace_expansion():
    doc = POLICY_SCHEMA_DOC.read_text(encoding="utf-8")
    # Either don't mention {a,b} at all, or only mention it in the
    # "not supported" disclaimer.
    if "{a,b}" in doc:
        assert "not supported" in doc.lower(), (
            "POLICY_SCHEMA.md mentions brace expansion. The reporter uses fnmatch "
            "and does not support it; the doc must say so explicitly or drop the mention."
        )

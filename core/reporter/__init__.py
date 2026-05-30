"""
agent-redline reporter.

Reads an agent-policy.yaml and a diff (changed files), classifies the
change by zone, reads boundary-rule backend output if available, and
produces a JSON verdict + markdown PR comment.

This is glue, not a classification engine. The agent classifies during
operating mode, before editing. The boundary-rule backend (e.g., ArchUnit)
catches violations during the build. The reporter composes those signals
into one verdict.

Public API:
    classify(policy, diff, *, archunit_xml=None, pr_labels=(), codeowner_approvals=())
        -> Verdict

CLI: python -m core.reporter --policy ... --base ... --head ... --mode ...
"""

from .reporter import classify, Verdict  # noqa: F401

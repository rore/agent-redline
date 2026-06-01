"""Stub email sender — second adapter so 'adapter independence' has something
non-trivial to enforce."""

from __future__ import annotations


class StubEmailSender:
    def send(self, to: str, subject: str, body: str) -> None:
        # In the demo we just record the send; production would call a provider.
        print(f"[stub email] to={to} subject={subject!r}")

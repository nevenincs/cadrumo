"""Unified access gate for live AEAT reads and permanent write refusal.

The gate consolidates the env-var preconditions that guard live AEAT
read call-sites. Live AEAT writes are permanently forbidden, so the
write-side helper is now a compatibility shim that always raises a
typed refusal. The gate is consumed by:

* the doctor CLI, for surfacing a "Live access gate" row;
* future live-read modules (filing history, missing-filing
  detection, AEAT messages, VAT balance tracking - #168-#171)
  that need a typed precondition rather than per-call-site
  ``if os.environ[...] != "1"`` boilerplate.

The gate is always constructed inline from a :class:`Settings`
instance at the call site. It is never injected via a
constructor, never stored as state on engines, and never passed as a
kwarg that could make a write path substitutable. That anti-injection
stance preserves R5's "no substitutable dependency on the write-gate"
property: tests cannot swap the gate for a no-op because there is no
seam to swap through.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict

from .certificate import AeatLiveReadNotEnabledError

if TYPE_CHECKING:
    from ..config import Settings


_LIVE_TESTS_ENV = "AEAT_LIVE_TESTS_ENABLED"
_PYTEST_CURRENT_TEST_ENV = "PYTEST_CURRENT_TEST"


class AeatGateEnvSnapshot(BaseModel):
    """Frozen snapshot of the env vars that still matter for live AEAT access.

    The record is safe to log and safe to serialise into historical
    audit payloads. Values are raw strings as read from ``os.environ``;
    absent vars materialise as the empty string.

    Attributes:
        aeat_live_tests_enabled: Value of ``AEAT_LIVE_TESTS_ENABLED``.
        pytest_current_test: Value of ``PYTEST_CURRENT_TEST`` (pytest
            sets this automatically during a test run; presence alone
            is the signal - the value is recorded for traceability).
    """

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    aeat_live_tests_enabled: str
    pytest_current_test: str

    def as_audit_dict(self) -> dict[str, str]:
        """Return the historical audit-log JSONL shape."""
        return {
            _LIVE_TESTS_ENV: self.aeat_live_tests_enabled,
            _PYTEST_CURRENT_TEST_ENV: self.pytest_current_test,
        }


@dataclass(frozen=True, slots=True)
class AeatAccessGate:
    """Read+write precondition check for live AEAT operations.

    The gate is stateless with respect to the process; every call
    reads ``os.environ`` afresh so the result reflects the live
    shell state at the moment of the check. That behaviour matches
    the engine's inline checks by design: a test that sets an env
    var at module import but unsets it before the gate call gets
    the expected "not enabled" verdict.
    """

    settings: Settings

    def require_live_read(self) -> None:
        """Raise :class:`AeatLiveReadNotEnabledError` if reads are off.

        The gate checks ``AEAT_LIVE_TESTS_ENABLED`` directly against
        ``os.environ`` rather than via ``Settings``, matching the
        conventions of the existing per-test
        ``if os.environ[...] != "1": pytest.skip(...)`` sites.
        """
        value = os.environ.get(_LIVE_TESTS_ENV)
        if value != "1":
            raise AeatLiveReadNotEnabledError(f"live AEAT reads require {_LIVE_TESTS_ENV}=1; current value: {value!r}")

    def require_live_write(self) -> None:
        """Always refuse live AEAT writes.

        The method remains for source compatibility with older callers,
        but live AEAT submission is permanently forbidden.
        """
        from ..submission import LiveSubmitForbiddenError

        raise LiveSubmitForbiddenError()

    def snapshot_env(self) -> AeatGateEnvSnapshot:
        """Return a frozen snapshot of the remaining gate env vars."""
        return AeatGateEnvSnapshot(
            aeat_live_tests_enabled=os.environ.get(_LIVE_TESTS_ENV, ""),
            pytest_current_test=os.environ.get(_PYTEST_CURRENT_TEST_ENV, ""),
        )


__all__ = [
    "AeatAccessGate",
    "AeatGateEnvSnapshot",
]

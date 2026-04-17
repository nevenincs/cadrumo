"""Unified read+write access gate for live AEAT operations.

The gate consolidates the env-var preconditions that guard every
live AEAT call-site. It is **not** a replacement for the inline
checks in :class:`aeat.submission.SubmissionEngine._submit_with_transport`
- those remain byte-identical per R5 of the live-write safety
charter (issue #116). The gate is a reusable helper consumed by:

* the engine, for building the audit-log env snapshot (preferred
  source; :mod:`aeat.submission._audit` retains its own fallback
  re-read);
* the doctor CLI, for surfacing a "Live access gate" row;
* future live-read modules (filing history, missing-filing
  detection, AEAT messages, VAT balance tracking - #168-#171)
  that need a typed precondition rather than per-call-site
  ``if os.environ[...] != "1"`` boilerplate.

The gate is always constructed inline from a :class:`Settings`
instance at the call site. It is never injected via a
constructor, never stored as state on engines, never passed as a
kwarg on any write-capable class. That anti-injection stance
preserves R5's "no substitutable dependency on the write-gate"
property: tests cannot swap the gate for a no-op because there is
no seam to swap through.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict

from aeat.auth.certificate import AeatLiveReadNotEnabledError

if TYPE_CHECKING:
    from aeat.config import Settings


_LIVE_TESTS_ENV = "AEAT_LIVE_TESTS_ENABLED"
_LIVE_SUBMIT_ENV = "AEAT_LIVE_SUBMIT_ENABLED"
_PYTEST_CURRENT_TEST_ENV = "PYTEST_CURRENT_TEST"


class AeatGateEnvSnapshot(BaseModel):
    """Frozen snapshot of the three env vars that gate live AEAT access.

    The record is safe to log and safe to serialise into the
    submission audit log. Values are raw strings as read from
    ``os.environ``; absent vars materialise as the empty string to
    match the existing audit-log JSONL schema shape.

    Attributes:
        aeat_live_tests_enabled: Value of ``AEAT_LIVE_TESTS_ENABLED``.
        aeat_live_submit_enabled: Value of ``AEAT_LIVE_SUBMIT_ENABLED``.
        pytest_current_test: Value of ``PYTEST_CURRENT_TEST`` (pytest
            sets this automatically during a test run; presence alone
            is the signal - the value is recorded for traceability).
    """

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    aeat_live_tests_enabled: str
    aeat_live_submit_enabled: str
    pytest_current_test: str

    def as_audit_dict(self) -> dict[str, str]:
        """Return the audit-log JSONL shape.

        Keys match the existing
        :mod:`aeat.submission._audit` record exactly so the log
        format is unchanged by the snapshot-centralisation work.
        """
        return {
            _LIVE_TESTS_ENV: self.aeat_live_tests_enabled,
            _LIVE_SUBMIT_ENV: self.aeat_live_submit_enabled,
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
        """Raise the existing submission error taxonomy for write gates.

        This is a **defensive helper** - the authoritative write-gate
        lives inline in :meth:`aeat.submission.SubmissionEngine._submit_with_transport`.
        Calling ``require_live_write()`` never *replaces* that gate;
        it provides the same checks for read-capable call-sites that
        want the typed error shape up front.
        """
        # Local import to avoid a cycle: `aeat.submission` imports
        # from `aeat.auth`, so `aeat.auth` must not import from
        # `aeat.submission` at module top level.
        from aeat.submission import (
            AeatLiveSubmitNotEnabledError,
            AeatPytestLiveWriteRefusedError,
        )

        if not self.settings.aeat_live_submit_enabled:
            raise AeatLiveSubmitNotEnabledError(f"live submission requires {_LIVE_SUBMIT_ENV}=true")
        if _PYTEST_CURRENT_TEST_ENV in os.environ:
            raise AeatPytestLiveWriteRefusedError(
                "pytest may never execute a live AEAT write; refusing dry_run=False submission"
            )

    def snapshot_env(self) -> AeatGateEnvSnapshot:
        """Return a frozen snapshot of the three gate env vars."""
        return AeatGateEnvSnapshot(
            aeat_live_tests_enabled=os.environ.get(_LIVE_TESTS_ENV, ""),
            aeat_live_submit_enabled=os.environ.get(_LIVE_SUBMIT_ENV, ""),
            pytest_current_test=os.environ.get(_PYTEST_CURRENT_TEST_ENV, ""),
        )


__all__ = [
    "AeatAccessGate",
    "AeatGateEnvSnapshot",
]

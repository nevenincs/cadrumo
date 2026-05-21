"""Unified access gate for live AEAT reads and permanent write refusal.

The gate consolidates the env-var preconditions that guard live AEAT
read call-sites. Live AEAT writes are permanently forbidden, so the
write-side helper always raises a typed refusal. The gate is consumed
by the repair CLI for surfacing a "Live access gate" row and by every
live-read module (filing history, missing-filing detection, AEAT
messages, VAT balance tracking) that needs a typed precondition
rather than per-call-site ``if os.environ[...] != "1"`` boilerplate.

The gate is always constructed inline from a
:class:`aeat.core.config.Settings` instance at the call site. It is
never injected via a constructor, never stored as state on engines,
and never passed as a kwarg that could make a write path
substitutable. That anti-injection stance preserves the
"no substitutable dependency on the write-gate" property: tests
cannot swap the gate for a no-op because there is no seam to swap
through.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict

from ._errors import (
    AccessGateSubmissionError,
    AccessGateSubmissionPreflightError,
    AeatLiveReadNotEnabledError,
    LiveSubmitForbiddenError,
)

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
        """Return the snapshot rendered as the audit-log JSONL mapping.

        Returns:
            Mapping keyed by the canonical environment variable names
            (``AEAT_LIVE_TESTS_ENABLED`` / ``PYTEST_CURRENT_TEST``)
            with their raw string values.
        """
        return {
            _LIVE_TESTS_ENV: self.aeat_live_tests_enabled,
            _PYTEST_CURRENT_TEST_ENV: self.pytest_current_test,
        }


@dataclass(frozen=True, slots=True)
class AeatAccessGate:
    """Pre-flight gate that authorises live AEAT reads and writes.

    The gate is stateless with respect to the process; every call
    reads ``os.environ`` afresh so the result reflects the live
    shell state at the moment of the check. That behaviour matches
    the engine's inline checks by design: a test that sets an env
    var at module import but unsets it before the gate call gets
    the expected "not enabled" verdict.
    """

    settings: Settings

    def require_live_read(self) -> None:
        """Refuse live AEAT reads when the Settings precondition is off.

        Routes the check through :class:`aeat.core.config.Settings`
        (specifically the ``aeat_live_tests_enabled: bool`` field) so
        every config read in the codebase flows through a single
        validated surface — no direct ``os.environ.get`` access for
        AEAT-prefixed variables.

        Raises:
            :exc:`aeat.core.access_gate._errors.AeatLiveReadNotEnabledError`:
                When ``Settings.aeat_live_tests_enabled`` is not True.
        """
        if self.settings.aeat_live_tests_enabled != "1":
            raise AeatLiveReadNotEnabledError(
                f"live AEAT reads require {_LIVE_TESTS_ENV} set to the literal "
                f"value 1 (the exact string '1', not 'true'/'yes'/'on'); "
                f"current value: {self.settings.aeat_live_tests_enabled!r}"
            )

    def require_live_write(self) -> None:
        """Always refuse live AEAT writes.

        Live AEAT submission is permanently forbidden. This method
        exists so that any call-site attempting a write receives a
        typed, auditable refusal rather than a silent no-op.

        Raises:
            :exc:`aeat.core.access_gate._errors.LiveSubmitForbiddenError`:
                Always.
        """
        raise LiveSubmitForbiddenError()

    def snapshot_env(self) -> AeatGateEnvSnapshot:
        """Return a frozen snapshot of the gate-relevant variables.

        The AEAT-prefixed variable is read from the validated Settings
        surface (single config-read invariant). ``PYTEST_CURRENT_TEST``
        is pytest infrastructure, set by the pytest runner itself for
        each test; it is not AEAT configuration and has no Settings
        field, so it is read directly from ``os.environ`` as the only
        legitimate exception in this surface.

        Returns:
            A :class:`AeatGateEnvSnapshot` capturing the current
            gate-relevant variables.
        """
        return AeatGateEnvSnapshot(
            aeat_live_tests_enabled=self.settings.aeat_live_tests_enabled,
            pytest_current_test=os.environ.get(_PYTEST_CURRENT_TEST_ENV, ""),
        )


__all__ = [
    "AccessGateSubmissionError",
    "AccessGateSubmissionPreflightError",
    "AeatAccessGate",
    "AeatGateEnvSnapshot",
    "AeatLiveReadNotEnabledError",
    "LiveSubmitForbiddenError",
]

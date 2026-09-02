"""Unified access gate for live AEAT reads and permanent write refusal.

The gate consolidates live-test preconditions for pytest-driven live
reads while keeping operator-facing live reads as operational surfaces.
Live AEAT writes are permanently forbidden, so the write-side helper
always raises a typed refusal. The gate is consumed by the repair CLI
for surfacing a "Live access gate" row and by every live-read module
(filing history, missing-filing detection, AEAT messages, IVA balance
tracking) that needs a typed precondition rather than per-call-site
``if os.environ[...] != "1"`` boilerplate in tests.

The gate is always constructed inline from a
:class:`core.config.Settings` instance at the call site. It is
never injected via a constructor, never stored as state on engines,
and never passed as a kwarg that could make a write path
substitutable. That anti-injection stance preserves the
"no substitutable dependency on the write-gate" property: tests
cannot swap the gate for a no-op because there is no seam to swap
through.

See Also:
    :class:`AeatAccessGate`
        Inline gate object used by read-only live surfaces and permanent
        write-refusal checks.
    :class:`AuthorizationManifest`
        Directory-mode modelo authorization manifest re-exported by this
        package for registry capability derivation.
    :mod:`application.live`
        Read-only application-live facade that calls the read gate before
        opening AEAT remote surfaces.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from typing import TYPE_CHECKING

from pydantic import BaseModel

from ...core.models import STRICT_FROZEN_CONFIG
from ..config import LIVE_READ_TEST_OPT_IN_ENV_VAR as _LIVE_READ_TEST_OPT_IN_ENV_VAR
from .errors import (
    AeatLiveReadNotEnabledError,
    LiveSubmitForbiddenError,
)

if TYPE_CHECKING:
    from ..config import Settings


_PYTEST_CURRENT_TEST_ENV = "PYTEST_CURRENT_TEST"


class AeatGateEnvSnapshot(BaseModel):
    """Frozen snapshot of the env vars that still matter for live-test access.

    The record is safe to log and safe to serialise into historical
    audit payloads. Values are raw strings as read from ``os.environ``;
    absent vars materialise as the empty string.

    Attributes:
        cadrumo_live_tests_enabled: Value of ``CADRUMO_LIVE_TESTS_ENABLED``.
        pytest_current_test: Value of ``PYTEST_CURRENT_TEST`` (pytest
            sets this automatically during a test run; presence alone
            is the signal - the value is recorded for traceability).
    """

    model_config = STRICT_FROZEN_CONFIG

    cadrumo_live_tests_enabled: str
    pytest_current_test: str


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

    def _pytest_current_test_value(self, pytest_current_test: str | None = None) -> str:
        """Return pytest's current-test marker, with an explicit test seam."""
        return os.environ.get(_PYTEST_CURRENT_TEST_ENV, "") if pytest_current_test is None else pytest_current_test

    def live_read_requires_test_opt_in(self, *, pytest_current_test: str | None = None) -> bool:
        """Return whether the current live read is executing under pytest.

        ``CADRUMO_LIVE_TESTS_ENABLED`` is a test runner opt-in, not an
        operational CLI switch. A live read in a normal operator shell
        still passes through auth/profile/read-only guards, but it is
        not refused by the pytest-only environment variable.
        """
        if pytest_current_test is not None:
            return bool(pytest_current_test)
        return bool(self._pytest_current_test_value()) or "pytest" in sys.modules

    def require_live_read(self, *, pytest_current_test: str | None = None) -> None:
        """Refuse pytest-driven live AEAT reads unless the test opt-in is on.

        Routes the check through :class:`core.config.Settings`
        (specifically the ``cadrumo_live_tests_enabled`` field) so
        every config read in the codebase flows through a single
        validated surface. Outside pytest this method deliberately
        permits the read to continue to the operational auth/profile
        and read-only remote-state guards.

        Raises:
            AeatLiveReadNotEnabledError: During pytest execution, when
                ``Settings.cadrumo_live_tests_enabled`` is not ``"1"``.
        """
        if self.live_read_requires_test_opt_in(pytest_current_test=pytest_current_test) and (
            not self.settings.live_tests_enabled
        ):
            raise AeatLiveReadNotEnabledError(
                translated_message="errors.refused.refused_access_gate_live_read_not_enabled",
                context={
                    "env_var": _LIVE_READ_TEST_OPT_IN_ENV_VAR,
                    "required_value": "1",
                    "current_value": str(self.settings.cadrumo_live_tests_enabled),
                    "live_reads_enabled": False,
                },
            )

    def require_live_write(self) -> None:
        """Always refuse live AEAT writes.

        Live AEAT submission is permanently forbidden. This method
        exists so that any call-site attempting a write receives a
        typed, auditable refusal rather than a silent no-op.

        Raises:
            LiveSubmitForbiddenError: Always — live writes are
                permanently forbidden.
        """
        raise LiveSubmitForbiddenError()

    def snapshot_env(
        self,
        *,
        pytest_current_test: str | None = None,
    ) -> AeatGateEnvSnapshot:
        """Return a frozen snapshot of the gate-relevant variables.

        The AEAT-prefixed variable is read from the validated Settings
        surface (single config-read invariant). ``PYTEST_CURRENT_TEST``
        is pytest infrastructure, set by the pytest runner itself for
        each test; it is not AEAT configuration and has no Settings
        field, so it is read directly from ``os.environ`` as the only
        legitimate exception in this surface.

        Args:
            pytest_current_test: DI seam for tests. When ``None``
                (production), the helper reads ``os.environ``; when
                ``""``, the helper records the "absent" path; when any
                other string, the helper records the explicit value.

        Returns:
            A :class:`AeatGateEnvSnapshot` capturing the current
            gate-relevant variables.
        """
        resolved_pytest = self._pytest_current_test_value(pytest_current_test)
        return AeatGateEnvSnapshot(
            cadrumo_live_tests_enabled=self.settings.cadrumo_live_tests_enabled,
            pytest_current_test=resolved_pytest,
        )

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

from ..config import LIVE_READ_TEST_OPT_IN_ENV_VAR as _LIVE_READ_TEST_OPT_IN_ENV_VAR
from ._authorization import (
    AUTHORIZATION_MANIFEST_DIRNAME,
    CANONICAL_MODELO_FLEET,
    FLEET_SIZE,
    MIN_DISTINCT_RENTA_YEARS,
    AuthorizationManifest,
    AuthorizationState,
    EnrollmentEvidenceClass,
    ModeloAuthorization,
    ModeloAuthorizationEntry,
    derive_modelo_authorization,
    load_authorization_manifest,
    manifest_dir,
)
from ._errors import (
    AccessGateSubmissionError,
    AccessGateSubmissionPreflightError,
    AeatLiveReadNotEnabledError,
    AuthorizationManifestError,
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
            _LIVE_READ_TEST_OPT_IN_ENV_VAR: self.aeat_live_tests_enabled,
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

    def _pytest_current_test_value(self, pytest_current_test: str | None = None) -> str:
        """Return pytest's current-test marker, with an explicit test seam."""
        return os.environ.get(_PYTEST_CURRENT_TEST_ENV, "") if pytest_current_test is None else pytest_current_test

    def live_read_requires_test_opt_in(self, *, pytest_current_test: str | None = None) -> bool:
        """Return whether the current live read is executing under pytest.

        ``AEAT_LIVE_TESTS_ENABLED`` is a test runner opt-in, not an
        operational CLI switch. A live read in a normal operator shell
        still passes through auth/profile/read-only guards, but it is
        not refused by the pytest-only environment variable.
        """
        return bool(self._pytest_current_test_value(pytest_current_test))

    def require_live_read(self, *, pytest_current_test: str | None = None) -> None:
        """Refuse pytest-driven live AEAT reads unless the test opt-in is on.

        Routes the check through :class:`aeat.core.config.Settings`
        (specifically the ``aeat_live_tests_enabled`` field) so
        every config read in the codebase flows through a single
        validated surface. Outside pytest this method deliberately
        permits the read to continue to the operational auth/profile
        and read-only remote-state guards.

        Raises:
            AeatLiveReadNotEnabledError: During pytest execution, when
                ``Settings.aeat_live_tests_enabled`` is not ``"1"``.
        """
        if self.live_read_requires_test_opt_in(pytest_current_test=pytest_current_test) and (
            self.settings.aeat_live_tests_enabled != "1"
        ):
            raise AeatLiveReadNotEnabledError(
                f"pytest live AEAT reads require {_LIVE_READ_TEST_OPT_IN_ENV_VAR} set to the literal "
                f"value 1 (the exact string '1', not 'true'/'yes'/'on'); "
                f"current value: {self.settings.aeat_live_tests_enabled!r}",
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
            aeat_live_tests_enabled=self.settings.aeat_live_tests_enabled,
            pytest_current_test=resolved_pytest,
        )


__all__ = [
    "AUTHORIZATION_MANIFEST_DIRNAME",
    "CANONICAL_MODELO_FLEET",
    "FLEET_SIZE",
    "MIN_DISTINCT_RENTA_YEARS",
    "AccessGateSubmissionError",
    "AccessGateSubmissionPreflightError",
    "AeatAccessGate",
    "AeatGateEnvSnapshot",
    "AeatLiveReadNotEnabledError",
    "AuthorizationManifest",
    "AuthorizationManifestError",
    "AuthorizationState",
    "EnrollmentEvidenceClass",
    "LiveSubmitForbiddenError",
    "ModeloAuthorization",
    "ModeloAuthorizationEntry",
    "derive_modelo_authorization",
    "load_authorization_manifest",
    "manifest_dir",
]

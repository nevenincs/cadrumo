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
    :mod:`application.live`
        Read-only application-live facade that calls the read gate before
        opening AEAT remote surfaces.
"""

from __future__ import annotations

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


class AeatGateEnvSnapshot(BaseModel):
    """Frozen snapshot of explicit inputs that matter for guarded live access.

    The record is safe to log and safe to serialise into historical
    audit payloads. Values are raw strings as read from ``os.environ``;
    absent vars materialise as the empty string.

    Attributes:
        cadrumo_live_tests_enabled: Value of ``CADRUMO_LIVE_TESTS_ENABLED``.
        guarded_read_context: Explicit caller-supplied guarded-read context.
    """

    model_config = STRICT_FROZEN_CONFIG

    cadrumo_live_tests_enabled: str
    guarded_read_context: str


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

    def live_read_requires_test_opt_in(self, *, guarded_read_context: str | None = None) -> bool:
        """Return whether the caller explicitly requested the guarded-read path.

        ``CADRUMO_LIVE_TESTS_ENABLED`` is a test runner opt-in, not an
        operational CLI switch. A live read in a normal operator shell
        still passes through auth/profile/read-only guards, but it is
        not refused by the pytest-only environment variable.
        """
        return bool(guarded_read_context)

    def require_live_read(self, *, guarded_read_context: str | None = None) -> None:
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
        if self.live_read_requires_test_opt_in(guarded_read_context=guarded_read_context) and (
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
        guarded_read_context: str | None = None,
    ) -> AeatGateEnvSnapshot:
        """Return a frozen snapshot of the gate-relevant variables.

        The AEAT-prefixed variable is read from the validated Settings
        surface (single config-read invariant). The context is ordinary,
        explicit call data; shipped code does not inspect its host process to
        discover whether a test harness is present.

        Args:
            guarded_read_context: Explicit context to record. ``None`` and
                ``""`` both record the absent path.

        Returns:
            A :class:`AeatGateEnvSnapshot` capturing the current
            gate-relevant variables.
        """
        return AeatGateEnvSnapshot(
            cadrumo_live_tests_enabled=self.settings.cadrumo_live_tests_enabled,
            guarded_read_context=guarded_read_context or "",
        )

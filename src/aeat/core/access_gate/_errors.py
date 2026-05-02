"""Policy errors for the AEAT live-access gate.

All errors inherit from :class:`aeat.core.errors.AeatError` so callers
have a single root they can catch at integration boundaries.

``LiveSubmitForbiddenError`` lives here (rather than in the
``adapters/outbound/aeat/export`` layer) because:

1. The gate module (``core/access_gate/``) raises it, and
   ``core/`` must remain independent from adapter implementations.
2. The policy "live AEAT submission is permanently forbidden" is
   a foundational invariant, not an adapter implementation detail.
"""

from __future__ import annotations

from ..errors import AeatError
from ..i18n import Translatable


class AccessGateSubmissionError(AeatError):
    """Base class for live-write access-gate submission policy failures.

    Attributes:
        translated_message: Optional :class:`aeat.core.i18n.Translatable`
            payload carrying a user-facing version of the message.
    """

    def __init__(self, message: str, *, translated_message: Translatable | None = None) -> None:
        """Construct a submission error.

        Args:
            message: English-authoritative error message (logged).
            translated_message: Optional multilingual payload surfaced
                to the CLI and any user-facing consumer.
        """
        super().__init__(message)
        self.translated_message: Translatable | None = translated_message


class AccessGateSubmissionPreflightError(AccessGateSubmissionError):
    """Raised when access-gate preflight rejects a write-shaped operation."""


class LiveSubmitForbiddenError(AccessGateSubmissionPreflightError):
    """Raised when any caller attempts a permanently forbidden live AEAT write."""

    def __init__(
        self,
        message: str = (
            "live AEAT submission is permanently forbidden; use produce -> verify -> "
            "export and upload the file yourself in the AEAT portal"
        ),
        *,
        translated_message: Translatable | None = None,
    ) -> None:
        """Construct the permanent live-submit refusal error."""
        default_translatable: Translatable = {
            "es": (
                "El envío en vivo a AEAT está permanentemente prohibido. "
                "Usa produce -> verify -> export y sube el fichero tú mismo "
                "en el portal de AEAT."
            ),
            "en": (
                "Live AEAT submission is permanently forbidden. "
                "Use produce -> verify -> export and upload the file yourself "
                "in the AEAT portal."
            ),
            "hu": (
                "Az élő AEAT beküldés véglegesen tiltott. "
                "Használd a produce -> verify -> export folyamatot, és töltsd "
                "fel a fájlt te magad az AEAT portálon."
            ),
        }
        super().__init__(
            message,
            translated_message=translated_message or default_translatable,
        )


class AeatLiveReadNotEnabledError(AeatError):
    """Raised when live-read access is required but the gate is shut.

    Emitted by :meth:`AeatAccessGate.require_live_read` when
    ``AEAT_LIVE_TESTS_ENABLED`` is not set to ``"1"``. The existing
    per-test ``if os.environ[...] != "1": pytest.skip(...)``
    boilerplate is not replaced — this error gives non-test callers
    (future live-read CLI commands, sync runners) a typed failure
    shape.
    """


__all__ = [
    "AeatLiveReadNotEnabledError",
    "AccessGateSubmissionError",
    "AccessGateSubmissionPreflightError",
    "LiveSubmitForbiddenError",
]

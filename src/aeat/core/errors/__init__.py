"""Domain exception hierarchy and public error-registry surface.

Every subpackage should raise subclasses of :class:`AeatError` to ensure
predictable error handling throughout the application.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TYPE_CHECKING, ClassVar

if TYPE_CHECKING:
    from ..i18n import Translatable


class AeatError(Exception):
    """Base exception for all AEAT domain errors."""

    code: ClassVar[ErrorCode]

    def __init_subclass__(cls, **kwargs: object) -> None:
        """Bind a registered :class:`ErrorCode` to each declared subclass."""

        super().__init_subclass__(**kwargs)
        from ._registry import bind_error_code

        bind_error_code(cls)

    def __init__(
        self,
        message: str | None = None,
        *,
        context: Mapping[str, object] | None = None,
        suggestion: str | None = None,
        translated_message: Translatable | None = None,
    ) -> None:
        """Construct a domain error with optional structured metadata.

        Args:
            message: Optional human-readable message override.
            context: Optional structured context that can be redacted and
                emitted in the JSON envelope.
            suggestion: Optional copy-paste recovery command override.
            translated_message: Optional multilingual message override.
        """

        if message is None:
            super().__init__()
        else:
            super().__init__(message)
        self.context: dict[str, object] | None = dict(context) if context is not None else None
        self.suggestion: str | None = suggestion
        self.translated_message: Translatable | None = translated_message


class AeatObservabilityError(AeatError):
    """Base class for observability-layer errors.

    Lives in :mod:`aeat.core.errors` (rather than the leaf
    :mod:`aeat.core.observability` subpackage) so other subpackages can
    catch it without importing observability internals. Concrete
    subclasses are declared in :mod:`aeat.core.observability._errors`.
    """


class FixtureProvisioningError(AeatError):
    """Raised when Google Workspace test-fixture provisioning fails.

    Thrown by the provisioning and teardown scripts under ``scripts/``
    whenever a Drive / Sheets / Docs call cannot satisfy the catalogued
    intent (missing parent, quota exhausted, unexpected dedup result, etc).
    """


class FilingFixtureError(AeatError):
    """Raised when a synthetic filing-history fixture cannot be loaded.

    Thrown by :mod:`aeat.application.filing.testing` when the fixtures directory cannot be
    resolved, a fixture file cannot be read, JSON decoding fails, or a
    payload fails strict pydantic validation (including the synthetic-
    only invariant checks on the ``synthetic`` and ``_comment`` fields).
    """


class SiteHealthError(AeatError):
    """Raised when AEAT site-health detection classifies a non-OK state.

    Carries a strict :class:`aeat.adapters.outbound.aeat.browser._site_health.SiteHealthStatus`
    attribute describing the detected state (mantenimiento, WAF challenge,
    rate limit, unreachable, unknown error) together with the evidence
    used to classify it. The workflow engine catches this error in a typed
    arm that precedes the generic exception handler so a planned
    mantenimiento never collapses into ``UNHANDLED_EXCEPTION``.

    The error lives in :mod:`aeat.core.errors` (and not in either leaf
    subpackage) to break the circular import between
    :mod:`aeat.adapters.outbound.aeat.browser` (which raises it) and :mod:`aeat.application.workflow`
    (which consumes it).
    """

    def __init__(self, *, status: Any) -> None:
        """Construct a SiteHealthError carrying a detected status.

        Args:
            status: The strict
                :class:`aeat.adapters.outbound.aeat.browser._site_health.SiteHealthStatus`
                instance describing the detected non-OK state.
        """

        state = getattr(status, "state")
        state_value = getattr(state, "value", state)
        super().__init__(str(state_value), context={"state": str(state_value)})
        self.status: Any = status


class McpLaunchError(AeatError):
    """Raised when a repo-managed MCP process cannot be launched safely."""


# -- aeat.domain.formulas error hierarchy --------------------------------------
# The formula engine lives in :mod:`aeat.domain.formulas`. All domain errors
# inherit from :class:`aeat.core.errors.AeatError`, so the entire
# formula-engine error hierarchy is declared here rather than inside the
# subpackage.


class FormulasError(AeatError):
    """Base error for the :mod:`aeat.domain.formulas` engine."""


class RulesetValidationError(FormulasError):
    """Raised when a ruleset fails structural validation at load time."""


class FormulaCycleError(FormulasError):
    """Raised when a ruleset DAG contains a cycle between computed casillas."""

    def __init__(self, *, ruleset_id: str, cycle: tuple[str, ...]) -> None:
        """Construct with the offending ruleset id and the cycle.

        Args:
            ruleset_id: Stable id of the ruleset whose DAG is cyclic.
            cycle: Tuple of casilla ids forming the cycle.
        """

        super().__init__(
            f"ruleset {ruleset_id!r} has cycle: {' -> '.join(cycle)}",
            context={"ruleset_id": ruleset_id, "cycle": " -> ".join(cycle)},
        )
        self.ruleset_id: str = ruleset_id
        self.cycle: tuple[str, ...] = cycle


class CasillaNotDefinedError(FormulasError):
    """Raised when a formula references a casilla that the ruleset does not declare."""


class AmbiguousPeriodError(FormulasError):
    """Raised when a period matches more than one ruleset span."""


class MissingRulesetError(FormulasError):
    """Raised when no ruleset covers the requested modelo/period pair."""


class EvaluationError(FormulasError):
    """Raised when a formula evaluation produces an arithmetic domain error."""


class AuditDiscrepancyError(FormulasError):
    """Raised by :meth:`AuditReport.assert_clean` when discrepancies are present."""


from ._registry import (  # noqa: E402
    ERROR_REGISTRY,
    ErrorCategory,
    ErrorCode,
    ErrorEnvelope,
    bind_error_code,
    build_error_envelope,
    get_error_exit_code,
    get_registered_error_code,
    register,
    render_error_json,
    render_error_text,
    resolve_error_message,
    resolve_output_language,
    scrub_error_context,
)

__all__ = [
    "ERROR_REGISTRY",
    "AeatError",
    "AeatObservabilityError",
    "AmbiguousPeriodError",
    "AuditDiscrepancyError",
    "CasillaNotDefinedError",
    "ErrorCategory",
    "ErrorCode",
    "ErrorEnvelope",
    "EvaluationError",
    "FilingFixtureError",
    "FixtureProvisioningError",
    "FormulaCycleError",
    "FormulasError",
    "McpLaunchError",
    "MissingRulesetError",
    "RulesetValidationError",
    "SiteHealthError",
    "bind_error_code",
    "build_error_envelope",
    "get_error_exit_code",
    "get_registered_error_code",
    "register",
    "render_error_json",
    "render_error_text",
    "resolve_error_message",
    "resolve_output_language",
    "scrub_error_context",
]

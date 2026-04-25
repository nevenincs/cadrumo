"""Domain exception hierarchy for the AEAT package.

Every subpackage should raise subclasses of AeatError to ensure
predictable error handling throughout the application.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .browser._site_health import SiteHealthStatus


class AeatError(Exception):
    """Base exception for all AEAT domain errors."""

    pass


class AeatObservabilityError(AeatError):
    """Base class for observability-layer errors (#99).

    Lives in :mod:`aeat.errors` (rather than the leaf
    :mod:`aeat.observability` subpackage) so other subpackages can
    catch it without importing observability internals. Concrete
    subclasses are declared in :mod:`aeat.observability._errors`.
    """

    pass


class FixtureProvisioningError(AeatError):
    """Raised when Google Workspace test-fixture provisioning fails.

    Thrown by the provisioning and teardown scripts under ``scripts/``
    whenever a Drive / Sheets / Docs call cannot satisfy the catalogued
    intent (missing parent, quota exhausted, unexpected dedup result, etc).
    """

    pass


class FilingFixtureError(AeatError):
    """Raised when a synthetic filing-history fixture cannot be loaded.

    Thrown by :mod:`aeat.testing` when the fixtures directory cannot be
    resolved, a fixture file cannot be read, JSON decoding fails, or a
    payload fails strict pydantic validation (including the synthetic-
    only invariant checks on the ``synthetic`` and ``_comment`` fields).
    """

    pass


class SiteHealthError(AeatError):
    """Raised when AEAT site-health detection classifies a non-OK state.

    Carries a strict :class:`aeat.browser._site_health.SiteHealthStatus`
    attribute describing the detected state (mantenimiento, WAF challenge,
    rate limit, unreachable, unknown error) together with the evidence
    used to classify it. The workflow engine catches this error in a typed
    arm that precedes the generic exception handler so a planned
    mantenimiento never collapses into ``UNHANDLED_EXCEPTION``.

    The error lives in :mod:`aeat.errors` (and not in either leaf
    subpackage) to break the circular import between
    :mod:`aeat.browser` (which raises it) and :mod:`aeat.workflow`
    (which consumes it).
    """

    def __init__(self, *, status: SiteHealthStatus) -> None:
        """Construct a SiteHealthError carrying a detected status.

        Args:
            status: The strict
                :class:`aeat.browser._site_health.SiteHealthStatus`
                instance describing the detected non-OK state.
        """
        super().__init__(status.state.value)
        self.status: SiteHealthStatus = status


# -- aeat.formulas error hierarchy (#173) --------------------------------
# The formula engine lives in :mod:`aeat.formulas`. Per the project-wide
# mandate (CLAUDE.md §Errors: "All domain errors inherit from
# aeat.errors.AeatError"), the entire formula-engine error hierarchy is
# declared here rather than inside the subpackage.


class FormulasError(AeatError):
    """Base error for the :mod:`aeat.formulas` engine."""

    pass


class RulesetValidationError(FormulasError):
    """Raised when a ruleset fails structural validation at load time."""

    pass


class FormulaCycleError(FormulasError):
    """Raised when a ruleset DAG contains a cycle between computed casillas."""

    def __init__(self, *, ruleset_id: str, cycle: tuple[str, ...]) -> None:
        """Construct with the offending ruleset id and the cycle.

        Args:
            ruleset_id: Stable id of the ruleset whose DAG is cyclic.
            cycle: Tuple of casilla ids forming the cycle.
        """
        super().__init__(f"ruleset {ruleset_id!r} has cycle: {' -> '.join(cycle)}")
        self.ruleset_id: str = ruleset_id
        self.cycle: tuple[str, ...] = cycle


class CasillaNotDefinedError(FormulasError):
    """Raised when a formula references a casilla that the ruleset does not declare."""

    pass


class AmbiguousPeriodError(FormulasError):
    """Raised when a period matches more than one ruleset span."""

    pass


class MissingRulesetError(FormulasError):
    """Raised when no ruleset covers the requested modelo/period pair."""

    pass


class EvaluationError(FormulasError):
    """Raised when a formula evaluation produces an arithmetic domain error."""

    pass


class AuditDiscrepancyError(FormulasError):
    """Raised by :meth:`AuditReport.assert_clean` when discrepancies are present."""

    pass

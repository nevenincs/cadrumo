"""Read cross-period verdict evidence for tests."""

from __future__ import annotations

from ..cross_period_models import CrossPeriodCleanStateVerdict, CrossPeriodDependencyEvidence


def suppressed_pre_activity(verdict: CrossPeriodCleanStateVerdict) -> tuple[CrossPeriodDependencyEvidence, ...]:
    """Return the dependencies suppressed as pre-activity."""
    return tuple(item for item in verdict.dependencies if item.suppressed_pre_activity)


def suppressed_first_year_fractional(
    verdict: CrossPeriodCleanStateVerdict,
) -> tuple[CrossPeriodDependencyEvidence, ...]:
    """Return the dependencies suppressed as a first-year no-fractional-payment obligation."""
    return tuple(item for item in verdict.dependencies if item.suppressed_first_year_fractional)


def has_first_year_fractional_suppression(verdict: CrossPeriodCleanStateVerdict) -> bool:
    """Report whether any dependency was suppressed as first-year fractional."""
    return any(item.suppressed_first_year_fractional for item in verdict.dependencies)


def has_operator_declared_suppression(verdict: CrossPeriodCleanStateVerdict) -> bool:
    """Report whether any dependency carries the operator-declared suppression advisory."""
    return any(item.operator_declared_suppression_advisory for item in verdict.dependencies)


def has_modelo_not_applicable(verdict: CrossPeriodCleanStateVerdict) -> bool:
    """Report whether any dependency carries the modelo-not-applicable advisory."""
    return any(item.modelo_not_applicable_advisory for item in verdict.dependencies)


def has_non_official_local_chain(verdict: CrossPeriodCleanStateVerdict) -> bool:
    """Report whether any dependency carries the non-official local-chain advisory."""
    return any(item.non_official_local_chain_advisory for item in verdict.dependencies)

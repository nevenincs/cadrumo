"""Test-only calculate shim that discards the source diagnostics.

Most calculation tests assert on the resulting
:class:`~cadrumo.domain.modelos.calculation_revision.CalculationRevision` and
have no interest in the non-blocking source advisories the calculate path also
returns. Unwrapping ``.revision`` at twenty-five call sites is noise, so the
unwrap lives here once.

It lives HERE rather than beside the calculation it wraps because a production
entry point that drops advisories is a hazard even when nothing calls it: the
shorter of two adjacent names is the one a future caller reaches for, and the
one that silently loses the diagnostics
``no-silent-under-declaration`` exists to keep visible. Production code has one
way in, and it returns the diagnostics with the revision.

The signature is deliberately not restated. Every argument is forwarded
untouched, so repeating twenty-one parameters and their imports here would
create a second declaration of the calculate contract that could drift from the
real one while still type-checking.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ..application.modelo.calculation_actions import (
    calculate_modelo_revision_from_bucket_aggregation_with_diagnostics,
)

if TYPE_CHECKING:
    from ..domain.modelos.calculation_revision import CalculationRevision

__all__ = ["calculate_modelo_revision_from_bucket_aggregation"]


def calculate_modelo_revision_from_bucket_aggregation(
    work_unit_id: str,
    **kwargs: Any,
) -> CalculationRevision:
    """Calculate through the bucket-local source mesh, returning only the revision.

    Args:
        work_unit_id: The work unit to calculate.
        kwargs: Forwarded verbatim to
            :func:`~cadrumo.application.modelo.calculation_actions.calculate_modelo_revision_from_bucket_aggregation_with_diagnostics`.

    Returns:
        The calculated
        :class:`~cadrumo.domain.modelos.calculation_revision.CalculationRevision`,
        with the source diagnostics dropped.
    """
    return calculate_modelo_revision_from_bucket_aggregation_with_diagnostics(
        work_unit_id,
        **kwargs,
    ).revision

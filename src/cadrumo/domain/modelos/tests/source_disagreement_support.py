"""A well-formed source disagreement, for tests that need a credit disagreement note of any modelo."""

from __future__ import annotations

from decimal import Decimal

from ....core.casilla_id import validated_casilla_id
from ...calculations.registry.tests.authored_editions import filing_grade_exercises, revision_covering
from ..source_disagreement import (
    DisagreementDecimalValue,
    SourceDisagreementEntry,
    SourceDisagreementFact,
    SourceDisagreementRole,
)

__all__ = ["sample_source_disagreement"]

_FILING_YEAR = filing_grade_exercises("100")[-1]


def sample_source_disagreement(*, casilla_id: str = "0596", work_unit_id: str = "w" * 64) -> SourceDisagreementFact:
    """Return a credit casilla whose recorded value and borrador cross-check differ by one cent."""
    casilla = validated_casilla_id(casilla_id)
    return SourceDisagreementFact.of(
        modelo="100",
        filing_year=_FILING_YEAR,
        period="0A",
        work_unit_id=work_unit_id,
        registry_revision_id=str(revision_covering("100", _FILING_YEAR).id),
        inputs_digest="d" * 64,
        key=str(casilla),
        value_channel="decimal",
        reached_casillas=(casilla,),
        sources=(
            SourceDisagreementEntry(
                role=SourceDisagreementRole.VALUE_SOURCE,
                source_family="binding",
                source_ref=f"casilla:{casilla}",
                value=DisagreementDecimalValue.of(Decimal("500.00")),
            ),
            SourceDisagreementEntry(
                role=SourceDisagreementRole.CROSS_CHECK,
                source_family="borrador",
                source_ref="binding:renta-retencion-soportada-trabajo",
                value=DisagreementDecimalValue.of(Decimal("499.99")),
            ),
        ),
        selected_role=SourceDisagreementRole.VALUE_SOURCE,
    )

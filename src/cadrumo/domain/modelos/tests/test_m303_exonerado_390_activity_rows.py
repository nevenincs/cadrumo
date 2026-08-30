"""Strict immutable evidence ownership for the six DP30304 activity pairs."""

from __future__ import annotations

from decimal import Decimal

import pytest
from pydantic import ValidationError

from ....core.casilla_id import validated_casilla_id
from ...filing_evidence import FilingEvidenceReference
from ..calculation_revision_m303_evidence import M303Exonerado390ActivityRowEvidence, M303Exonerado390EndpointEvidence, M303Exonerado390FilingEvidence

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _reference() -> FilingEvidenceReference:
    return FilingEvidenceReference(reference="test:dp30304:activity-row-owner")


def _applicable_evidence() -> M303Exonerado390FilingEvidence:
    reference = _reference()
    return M303Exonerado390FilingEvidence(
        applicable=True,
        applicability_reference=reference,
        endpoints=(
            M303Exonerado390EndpointEvidence(
                casilla_id=validated_casilla_id("79", surface="S56 evidence test"),
                value=Decimal("0"),
                evidence_reference=reference,
            ),
        ),
        activity_rows=(
            M303Exonerado390ActivityRowEvidence(
                slot=1, codigo_actividad="A01", epigrafe_iae="4101", evidence_reference=reference
            ),
            M303Exonerado390ActivityRowEvidence(
                slot=2, codigo_actividad="A02", epigrafe_iae="4102", evidence_reference=reference
            ),
            M303Exonerado390ActivityRowEvidence(
                slot=3, codigo_actividad="A03", epigrafe_iae="4103", evidence_reference=reference
            ),
            M303Exonerado390ActivityRowEvidence(
                slot=4, codigo_actividad="A04", epigrafe_iae="4104", evidence_reference=reference
            ),
            M303Exonerado390ActivityRowEvidence(
                slot=5, codigo_actividad="A05", epigrafe_iae="4105", evidence_reference=reference
            ),
            M303Exonerado390ActivityRowEvidence(
                slot=6, codigo_actividad="A06", epigrafe_iae="4106", evidence_reference=reference
            ),
        ),
        operaciones_terceros_declarables=False,
        operaciones_terceros_reference=reference,
    )


@pytest.mark.parametrize(
    "replacement_slots",
    (
        (1, 2, 4, 5, 6),
        (1, 2, 3, 4, 5, 5),
        (2, 1, 3, 4, 5, 6),
        (1, 2, 3, 4, 5, 6, 7),
    ),
)
def test_applicable_evidence_refuses_gapped_duplicate_reordered_or_over_capacity_rows(
    replacement_slots: tuple[int, ...],
) -> None:
    payload = _applicable_evidence().model_dump(mode="python")
    payload["activity_rows"] = tuple(
        {**payload["activity_rows"][min(index, 5)], "slot": slot} for index, slot in enumerate(replacement_slots)
    )

    with pytest.raises(ValidationError):
        M303Exonerado390FilingEvidence.model_validate(payload)


def test_non_applicable_evidence_requires_explicit_empty_rows_and_null_modelo_347_decision() -> None:
    payload = _applicable_evidence().model_dump(mode="python")
    payload.update(
        applicable=False,
        endpoints=(),
        activity_rows=(),
        operaciones_terceros_declarables=None,
        operaciones_terceros_reference=None,
    )

    assert M303Exonerado390FilingEvidence.model_validate(payload).applicable is False

    payload["activity_rows"] = _applicable_evidence().activity_rows
    with pytest.raises(ValidationError, match="must not carry annual facts"):
        M303Exonerado390FilingEvidence.model_validate(payload)

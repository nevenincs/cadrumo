"""Cross-period evidence cannot report clean on identities that could not exist.

``CrossPeriodDependencyEvidence`` IS the clean-state verdict's evidence: a
requirement whose evidence carries no blockers is reported ``clean``, and a
filing proceeds on that answer. Its identity and provenance fields were bare
strings, so evidence naming an observation source outside the closed taxonomy,
filing-record and calculation-revision references that are not the canonical
hex-64 identities, and an external-evidence kind naming no known evidence all
validated — and the enclosing verdict still reported ``clean=True``, because
nothing had put a blocker on it.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from ....core.casilla_id import validated_casilla_id
from ....core.period import Period
from ....domain.modelos.filing_record import ExternalEvidenceKind
from ..cross_period_models import (
    CrossPeriodDependencyEvidence,
    CrossPeriodDependencyOrigin,
    CrossPeriodDependencyRequirement,
)
from ..observations_repository import ObservationSourceKind

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_VALID_FILING_RECORD_ID = "a" * 64
_VALID_CALCULATION_REVISION_ID = "b" * 64


def _requirement() -> CrossPeriodDependencyRequirement:
    return CrossPeriodDependencyRequirement(
        source_modelo="303",
        filing_year=2026,
        period=Period.from_year_and_code(2026, "1T"),
        source_casilla_ids=(validated_casilla_id("71", surface="test casilla id"),),
        origin=CrossPeriodDependencyOrigin.PREVIOUS_FILING_BINDING,
        origin_ids=("modelo-303-compensacion-pendiente-anteriores",),
        legal_refs=("ley-37-1992:art-99",),
        source_refs=("aeat-iva-2025",),
    )


def _valid_fields() -> dict[str, object]:
    return {
        "requirement": _requirement(),
        "observation_source_kind": ObservationSourceKind.AEAT_SEDE_JUSTIFICANTE,
        "filing_record_id": _VALID_FILING_RECORD_ID,
        "calculation_revision_id": _VALID_CALCULATION_REVISION_ID,
        "external_evidence_kind": ExternalEvidenceKind.AEAT_JUSTIFICANTE_PDF,
    }


def test_canonical_evidence_is_admitted_and_clean() -> None:
    """The positive control: real identities validate and carry no blockers."""
    evidence = CrossPeriodDependencyEvidence.model_validate(_valid_fields())

    assert evidence.clean
    assert evidence.observation_source_kind is ObservationSourceKind.AEAT_SEDE_JUSTIFICANTE
    assert evidence.external_evidence_kind is ExternalEvidenceKind.AEAT_JUSTIFICANTE_PDF


def test_stored_string_tokens_lift_to_their_closed_taxonomies() -> None:
    """Upstream readers hand stored tokens through as text; they lift, not pass through.

    The strict model config does not coerce ``str`` to ``StrEnum``, so the
    lifting is explicit — and an unknown token raises there rather than
    surviving as free-form provenance.
    """
    evidence = CrossPeriodDependencyEvidence.model_validate(
        {
            **_valid_fields(),
            "observation_source_kind": "aeat_sede_justificante",
            "external_evidence_kind": "aeat_justificante_pdf",
        },
    )

    assert evidence.observation_source_kind is ObservationSourceKind.AEAT_SEDE_JUSTIFICANTE
    assert evidence.external_evidence_kind is ExternalEvidenceKind.AEAT_JUSTIFICANTE_PDF


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("observation_source_kind", "bogus"),
        ("observation_source_kind", ""),
        ("external_evidence_kind", "bogus"),
        ("external_evidence_kind", ""),
        ("filing_record_id", "bad"),
        ("filing_record_id", "A" * 64),
        ("filing_record_id", "a" * 63),
        ("calculation_revision_id", "bad2"),
        ("calculation_revision_id", "b" * 65),
        ("member_filing_record_ids", ("bad",)),
        ("member_calculation_revision_ids", ("bad2",)),
    ],
)
def test_evidence_that_could_not_exist_is_refused(field: str, value: object) -> None:
    """Malformed evidence is refused at construction, never reported clean.

    Every one of these validated before, and an enclosing verdict built from
    them answered ``clean=True`` — a filing decision resting on references no
    part of the system could have minted.
    """
    fields = _valid_fields()
    fields[field] = value

    with pytest.raises(ValidationError):
        CrossPeriodDependencyEvidence.model_validate(fields)


def test_absent_evidence_stays_representable() -> None:
    """A requirement with nothing observed yet is still constructible.

    Typing the fields must not force a caller to invent an identity for
    evidence it has not observed; ``None`` remains the honest absent value.
    """
    evidence = CrossPeriodDependencyEvidence(requirement=_requirement())

    assert evidence.filing_record_id is None
    assert evidence.calculation_revision_id is None
    assert evidence.observation_source_kind is None
    assert evidence.external_evidence_kind is None

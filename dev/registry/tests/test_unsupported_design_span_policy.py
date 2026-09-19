"""Unsafe design spans stay visible while remaining unavailable for filing."""

from __future__ import annotations

import pytest

from cadrumo.core.authority_grade import RegistryAuthorityGrade
from cadrumo.domain.calculations.registry.errors import RegistryFailureCondition, RegistryValidationError
from cadrumo.domain.calculations.registry.schema import ModeloRevision
from dev.registry.compiler.authority import compiled_bundled_authority

from ._revision_span_boundary_support import _boundaries_for
from ._revision_span_design_support import _declared_revisions, _filing_revisions

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

#: Spans that declare design boundaries while their own authority_grade keeps
#: them off the filing path: modelos 126 and 128 at 'calculation', both modelo
#: 308 eras and modelo 345's 2023 era at 'applicability'.
#:
#: Modelo 200's 2024 revision belongs here on grade -- it declares 'calculation'
#: too -- and is absent only because a span needs boundaries to be counted, and
#: that revision currently has no export fragments at all while its tree awaits
#: regeneration. It returns to this set with them, and it is listed here in
#: prose so its reappearance reads as the tree coming back rather than as a new
#: regression.
_KNOWN_UNSUPPORTED_SPANS = frozenset(
    {
        ("126", "2019-y-siguientes"),
        ("128", "2019-y-siguientes"),
        ("308", "2009-2011-junio"),
        ("308", "2011-julio-2015"),
        ("345", "2023"),
    },
)


def _requestable_filing_year(revision: ModeloRevision, *, floor: int) -> int | None:
    """The earliest year this revision declares that the support envelope also admits.

    A span kept off the filing path is often a historical era, and the envelope
    floor refuses a request below it before the grade is ever consulted. Asking
    for such a year would exercise the envelope's refusal rather than the grade
    boundary this gate is about, so a span with no admissible year is passed
    over instead of being asserted on.
    """
    selector = revision.period_selector
    if selector.years:
        admissible = [year for year in selector.years if year >= floor]
        return min(admissible) if admissible else None
    if selector.year_from is None:
        return None
    year = max(selector.year_from, floor)
    if selector.year_to is not None and year > selector.year_to:
        return None
    return year


def _unsupported_spans() -> set[tuple[str, str]]:
    filing = {(modelo.id, revision_id) for modelo, revision_id, _revision in _filing_revisions()}
    return {
        (modelo.id, revision_id)
        for modelo, revision_id, revision in _declared_revisions()
        if (modelo.id, revision_id) not in filing and _boundaries_for(modelo.id, revision)
    }


def test_known_unsupported_spans_remain_detectable_and_pinned() -> None:
    """A grade correction may remove support, never erase the evidence backlog."""
    assert _unsupported_spans() == _KNOWN_UNSUPPORTED_SPANS


def test_a_below_filing_span_refuses_a_filing_request_at_the_authority_boundary() -> None:
    """A span kept off the filing path must fail before any filing bytes exist.

    The subject is DERIVED from the spans pinned above rather than named. The
    revision this was written for -- modelo 200's 2025 era -- has since been
    promoted to filing grade, and a gate anchored on one revision id reports a
    promotion as a broken refusal while the refusal itself is untested. Asking
    the pinned set for a span that is still below filing grade survives the next
    promotion and still fails loudly if nothing is left to refuse.
    """
    authority = compiled_bundled_authority()
    below_filing = sorted(
        (modelo.id, revision_id, revision)
        for modelo, revision_id, revision in _declared_revisions()
        if (modelo.id, revision_id) in _KNOWN_UNSUPPORTED_SPANS
    )
    assert below_filing, "no pinned unsupported span resolved, so no refusal is exercised"

    floor = authority.supported_filing_years().floor
    requestable = [
        (modelo_id, revision_id, revision, year)
        for modelo_id, revision_id, revision in below_filing
        if (year := _requestable_filing_year(revision, floor=floor)) is not None
    ]
    assert requestable, (
        "every pinned unsupported span lies below the support envelope, so the grade boundary "
        "is never reached and this gate exercises the envelope refusal instead"
    )

    modelo_id, revision_id, revision, filing_year = requestable[0]
    declared = revision.effective_authority_grade
    assert declared is not RegistryAuthorityGrade.FILING, (
        f"{modelo_id}/{revision_id} is pinned as unsupported but declares {declared}"
    )
    period = revision.period_selector.periods[0]

    with pytest.raises(RegistryValidationError) as exc_info:
        authority.snapshot(
            modelo_id,
            filing_year=filing_year,
            period=period,
            revision_id=revision_id,
            grade=RegistryAuthorityGrade.FILING,
        )

    error = exc_info.value
    assert str(error) == (
        f"modelo {modelo_id} revision {revision_id} declares {declared.value!r} authority grade, "
        "which cannot satisfy the requested 'filing' snapshot authority."
    )
    failure = error.registry_failure
    assert failure is not None
    assert failure.condition is RegistryFailureCondition.SNAPSHOT_AUTHORITY_GRADE_SUFFICIENT
    assert failure.facts == {
        "modelo": modelo_id,
        "revision_id": revision_id,
        "requested_authority_grade": "filing",
        "declared_authority_grade": declared.value,
        "authority_grade_declared": True,
    }

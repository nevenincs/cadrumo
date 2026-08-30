"""A profile with no declared NIF must not lose its filed obligations from the calendar.

contract: the calendar's evidence matchers compare the operator's NIF against
the authenticated identity recorded on each filed artefact. Every one of them
fails OPEN on an empty expected value and CLOSED on a non-empty mismatching one
— absence is deliberately not a filter, a wrong identity deliberately is.

The taxpayer projection substitutes a synthetic placeholder NIF for an absent
identity. Feeding that into these matchers inverts their design: the placeholder
is non-empty and matches no real filed declaration, so an operator who has not
yet declared a NIF would have every genuinely filed obligation dropped and
redisplayed as unfiled — and the remedy an operator would reach for on a
"missed" deadline is to file it a second time.

These drive the real ``calendar_filing_evidence_from_sources`` over a real
``FiledDeclaracionObservation``; nothing is stubbed.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from ....adapters.outbound.aeat.sede.schema import FiledDeclaracionArtefact, FiledDeclaracionObservation
from ....application.overview.calendar_evidence import calendar_filing_evidence_from_sources
from ....application.user_profile.projections import projection_for_taxpayer
from ....core import Period
from ....tests.aeat_literal_fixtures import FILED_ARTEFACT_PATH_FIXTURE, aeat_url

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_REAL_NIF = "12345678Z"
_PERIOD = Period.from_year_and_code(2024, "1T")


def _filed_observation() -> FiledDeclaracionObservation:
    """One genuinely filed Modelo 303 declaration, authenticated as the real NIF."""
    return FiledDeclaracionObservation(
        modelo="303",
        ejercicio=2024,
        period=_PERIOD,
        expediente_id="20243031T000001",
        status="ALTA",
        presented_at=datetime(2024, 4, 15, 10, 0, tzinfo=UTC),
        authenticated_identity=_REAL_NIF,
        artefacts=(
            FiledDeclaracionArtefact(
                kind="register_row",
                source_url=aeat_url("sede", FILED_ARTEFACT_PATH_FIXTURE),
                content_type="text/html",
                byte_count=2048,
                sha256="a" * 64,
                captured_at=datetime(2024, 4, 15, 10, 5, tzinfo=UTC),
            ),
        ),
    )


def _evidence_for(expected_tax_id: str | None) -> tuple[object, ...]:
    return calendar_filing_evidence_from_sources(
        filed_declaration_observations=(_filed_observation(),),
        expected_tax_id=expected_tax_id,
    )


def test_the_declared_matching_nif_keeps_the_filed_obligation() -> None:
    """POSITIVE CONTROL: the ordinary case still matches and is retained."""
    assert _evidence_for(_REAL_NIF), "a matching declared NIF must retain its filed evidence"


def test_an_undeclared_nif_keeps_the_filed_obligation() -> None:
    """Absence must not filter: an empty expected identity leaves the evidence intact.

    This is the behaviour the fix restores. The matchers were written to fail
    open here, and passing the declared identity (empty when undeclared) is what
    lets them.
    """
    assert _evidence_for(""), "an undeclared NIF must not drop genuinely filed evidence"
    assert _evidence_for(None), "a None expected identity must not drop filed evidence either"


def test_a_wrong_declared_nif_still_filters_the_obligation() -> None:
    """The guard must keep working: a genuinely different NIF is still filtered.

    Without this, "stop dropping evidence" could be satisfied by disabling the
    identity check altogether, which would show one taxpayer another's filings.
    """
    assert not _evidence_for("87654321X"), "a mismatching declared NIF must still filter"


def test_the_projection_placeholder_would_have_dropped_the_filed_obligation() -> None:
    """The defect, stated against the real projection rather than a copied literal.

    Asserts the placeholder the projection actually produces for an empty profile
    behaves as a wrong NIF here — so if that placeholder ever changes, this test
    keeps describing the real hazard instead of a stale constant.
    """
    placeholder = projection_for_taxpayer({}).tax_id

    assert placeholder, "the projection is expected to substitute a non-empty placeholder"
    assert placeholder != _REAL_NIF
    assert not _evidence_for(placeholder), (
        "the placeholder matches no real filed declaration, so feeding it to the calendar "
        "silently drops filed obligations — this is why the declared identity is read instead"
    )

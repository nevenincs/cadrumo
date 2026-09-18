"""Temporal and deadline ownership proofs for Modelo 182."""

from __future__ import annotations

from datetime import date

import pytest

from cadrumo.domain.calculations.registry.errors import (
    FilingYearOutsideSupportEnvelopeError,
    RegistrySnapshotError,
    RegistryValidationError,
)

from ..compiler.authority import compiled_bundled_authority
from ._gate_support import assert_deadline_window_for_filing_year, assert_edition_opens_at_filing_year

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

#: Wide enough to cross the support floor in both directions, and to reach past
#: the last filing year any edition declares a window for.
_SCANNED_FILING_YEARS = range(2018, 2028)


def test_modelo_182_deadline_is_owned_only_by_the_evidenced_2025_revision() -> None:
    authority = compiled_bundled_authority()
    modelo = authority.modelo("182")
    revision = modelo.revisions["2025"]

    assert revision.valid_from == date(2025, 1, 1)
    # Open-ended by its own grounding: Orden HAC/1430/2025 disposicion final
    # unica leaves the design in force until a later orden replaces it, so the
    # edition carries no valid_to and its selector no upper year.
    assert revision.valid_to is None
    assert_edition_opens_at_filing_year(revision, 2025)
    assert_deadline_window_for_filing_year(revision, 2025, "modelo-182-2025-0a")

    window = next(item for item in revision.deadline_windows if item.filing_year == 2025)
    assert (window.filing_year, window.period.registry_token) == (2025, "0A")
    snapshot = authority.snapshot("182", filing_year=2025, period="0A", grade=revision.effective_authority_grade)
    assert snapshot.revision.id == "2025"
    assert tuple(item[2].id for item in authority.deadline_windows(2025, modelos=("182",))) == (window.id,)


def test_modelo_182_refuses_a_filing_grade_snapshot_and_projects_no_unauthored_deadline() -> None:
    """Every year refuses, and each refusal names its own cause.

    The years split across the support floor, and the two halves are refused
    for unrelated reasons: below it the envelope turns the request away before
    the corpus is consulted at all, and above it every authored edition stands
    at applicability grade, which cannot satisfy a filing-grade snapshot.
    Asserting one type for both would pass while saying the wrong thing about
    half the range.

    The deadline half is derived from what the editions actually declare rather
    than from a frozen year list: a window is returned for exactly the filing
    years an edition authors one for, and for no other year. That keeps the
    real claim -- no deadline is invented for an unauthored year -- while an
    open-ended edition is free to carry the next year's window.
    """
    authority = compiled_bundled_authority()
    support = authority.catalogues.require_supported_filing_years()
    authored_window_years = {
        window.filing_year
        for revision in authority.modelo("182").revisions.values()
        for window in revision.deadline_windows
    }

    for filing_year in _SCANNED_FILING_YEARS:
        expected: type[RegistrySnapshotError | RegistryValidationError] = (
            RegistryValidationError
            if support.admits_filing_year(filing_year)
            else FilingYearOutsideSupportEnvelopeError
        )
        with pytest.raises(expected):
            authority.snapshot("182", filing_year=filing_year, period="0A")
        windows = authority.deadline_windows(filing_year, modelos=("182",))
        assert bool(windows) is (filing_year in authored_window_years), filing_year

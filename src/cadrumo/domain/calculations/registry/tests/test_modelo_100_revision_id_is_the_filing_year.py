"""Gate the modelo 100 coincidence three production domain reads depend on.

Three domain modules read modelo 100 parameters directly and name the revision
by ``str(filing_year)``: the rental tier resolver, the rental amortisation
ledger, and the maternidad computation. Those reads are legitimate -- the
registry package is itself domain, and each goes through the validated
authority -- but the way they name a revision is not a mechanism. It works only
because modelo 100's revision directories happen to BE the years, and because
its parameter ids happen to be year-suffixed.

That is a coincidence of one modelo's naming, and modelo 303 already broke the
same assumption: its 2024 filing year is served by TWO revisions split at the
RD-ley boundary, so no year-to-id derivation could ever be right there. The day
modelo 100 splits the same way, those three reads would stop resolving -- and
today the first sign of it would be a resolution error in front of an operator.

These tests convert that into a loud failure at test time instead. They do not
move the reads (the accepted placement decision leaves them where they are, and
relocating them is a separate question with its own cost); they make the
precondition those reads silently rely on explicit and checked.
"""

from __future__ import annotations

import re
from datetime import date

import pytest

from ..authority import ValidatedRegistryAuthority, bundled_authority
from ..temporal import select_revision

pytestmark = [pytest.mark.integration, pytest.mark.hex_core]

_YEAR_ID = re.compile(r"^\d{4}$")

#: The period token modelo 100 files under (annual).
_ANNUAL_PERIOD = "0A"


@pytest.fixture(scope="session")
def registry_authority() -> ValidatedRegistryAuthority:
    """The bundled validated authority."""
    return bundled_authority()


def _modelo_100_years(authority: ValidatedRegistryAuthority) -> tuple[int, ...]:
    """Every filing year modelo 100 declares a revision for."""
    return tuple(sorted(int(rid) for rid in authority.modelo("100").revisions if _YEAR_ID.match(rid)))


def test_every_modelo_100_revision_id_is_a_bare_four_digit_year(
    registry_authority: ValidatedRegistryAuthority,
) -> None:
    """A non-year id would break ``str(filing_year)`` at the three reading sites."""
    ids = sorted(registry_authority.modelo("100").revisions)
    offenders = [rid for rid in ids if not _YEAR_ID.match(rid)]
    assert not offenders, (
        f"modelo 100 declares revision id(s) {offenders} that are not a bare year. "
        "Three domain modules name a modelo 100 revision by str(filing_year); they "
        "cannot reach these. Pass the selected revision in from the application "
        "boundary instead of deriving an id from a year."
    )


def test_every_modelo_100_revision_spans_exactly_its_own_calendar_year(
    registry_authority: ValidatedRegistryAuthority,
) -> None:
    """A revision narrower than its year means the year needs more than one.

    This is the shape of the modelo 303 mid-year split, caught before the id
    itself changes: the split revision's window shrinks first.
    """
    for revision_id, revision in sorted(registry_authority.modelo("100").revisions.items()):
        year = int(revision_id)
        assert revision.valid_from == date(year, 1, 1), (
            f"modelo 100 revision {revision_id} starts {revision.valid_from}, not 1 January. "
            "A mid-year start means the filing year is served by more than one revision."
        )
        assert revision.valid_to == date(year, 12, 31), (
            f"modelo 100 revision {revision_id} ends {revision.valid_to}, not 31 December. "
            "A mid-year end means the filing year is served by more than one revision."
        )


def test_canonical_selection_returns_the_revision_named_by_the_filing_year(
    registry_authority: ValidatedRegistryAuthority,
) -> None:
    """The load-bearing assertion: ``str(year)`` IS what canonical selection returns.

    The two tests above check the declaration's shape. This one checks the thing
    the reading sites actually depend on -- that deriving the id from the year
    and asking the canonical resolver agree -- so a split that somehow preserved
    the naming would still be caught.
    """
    modelo = registry_authority.modelo("100")
    for year in _modelo_100_years(registry_authority):
        selected = select_revision(modelo, filing_year=year, period=_ANNUAL_PERIOD, on=None)
        assert selected.id == str(year), (
            f"modelo 100 filing year {year} canonically selects revision {selected.id!r}, "
            f"but three domain modules would read revision {str(year)!r}. They now "
            "disagree; the reads must take the selected revision rather than derive one."
        )


def test_every_modelo_100_parameter_id_carries_its_own_revision_year(
    registry_authority: ValidatedRegistryAuthority,
) -> None:
    """The second half of the coincidence: the reads build ``renta-<year>-<slug>``.

    A parameter declared without the year prefix is unreachable from those call
    sites even when the revision id resolves perfectly.
    """
    for revision_id, revision in sorted(registry_authority.modelo("100").revisions.items()):
        prefix = f"renta-{revision_id}-"
        offenders = [parameter.id for parameter in revision.parameters if not parameter.id.startswith(prefix)]
        assert not offenders, (
            f"modelo 100 revision {revision_id} declares parameter(s) {offenders[:5]} without "
            f"the {prefix!r} prefix the three domain reads construct."
        )


def test_the_gate_is_not_vacuous_because_modelo_303_already_violates_it(
    registry_authority: ValidatedRegistryAuthority,
) -> None:
    """TEETH, from the live tree rather than a fixture.

    Modelo 303's 2024 filing year is served by two revisions split at the RD-ley
    boundary, so at least one of its revision ids is NOT a bare year and at
    least one window is not a whole calendar year. If modelo 303 ever satisfied
    the modelo 100 property, every assertion above would be passing vacuously
    and this test says so.
    """
    revisions = registry_authority.modelo("303").revisions
    non_year_ids = [rid for rid in revisions if not _YEAR_ID.match(rid)]
    assert non_year_ids, (
        "modelo 303 now declares only bare-year revision ids, so the modelo 100 "
        "assertions above no longer distinguish anything. Re-ground this gate."
    )
    partial_year = [
        rid
        for rid, revision in revisions.items()
        if revision.valid_to is not None
        and (revision.valid_from.month, revision.valid_from.day, revision.valid_to.month, revision.valid_to.day)
        != (1, 1, 12, 31)
    ]
    assert partial_year, "modelo 303 no longer splits a filing year; re-ground this gate."

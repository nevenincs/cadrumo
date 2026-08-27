"""The authority refuses consuming reads for a filing year it does not declare supported.

A registry snapshot consumed at calculation or filing grade is an authority
claim about a year: it says the corpus can compute and file that year. When the
year is outside the one writable supported-year declaration, that claim is
unfounded, and answering anyway hands a taxpayer figures computed under a corpus
nobody asserted covers their ejercicio.

Scheduling stays readable. An applicability-grade read asks when a modelo is due
and to whom it applies -- the very question an operator asks ABOUT an
unsupported year -- so refusing there would make the surface unable to answer it.

Every proof here runs against the process-wide bundled authority AFTER it has
already served a read, so the refusal is measured in the warm regime with the
snapshot cache populated, not on a first cold load where a different code path
could be doing the work.
"""

from __future__ import annotations

import pytest

from .....core import RegistryAuthorityGrade
from .....core.time import today_madrid
from ..authority import bundled_authority
from ..errors import RegistryValidationError

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_M303 = "303"
_QUARTER = "1T"


def _warm_authority() -> tuple[object, tuple[int, ...]]:
    """Return the bundled authority after a successful read, plus its declared years."""
    authority = bundled_authority()
    declaration = authority.catalogues.supported_filing_years
    assert declaration is not None, "the bundled registry declares no supported filing years"
    years = tuple(declaration.years)
    # Serve one supported read first: everything below must be measured warm.
    authority.snapshot(_M303, filing_year=max(years), period=_QUARTER, grade=RegistryAuthorityGrade.FILING)
    return authority, years


@pytest.mark.parametrize(
    "grade",
    [RegistryAuthorityGrade.FILING, RegistryAuthorityGrade.CALCULATION],
    ids=lambda grade: grade.value,
)
def test_a_consuming_read_refuses_an_undeclared_filing_year_under_a_warm_load(
    grade: RegistryAuthorityGrade,
) -> None:
    """Both consuming rungs refuse, and the refusal names the year and the declaration."""
    authority, years = _warm_authority()
    undeclared = min(years) - 1

    with pytest.raises(RegistryValidationError) as excinfo:
        authority.snapshot(_M303, filing_year=undeclared, period=_QUARTER, grade=grade)

    message = str(excinfo.value)
    assert str(undeclared) in message, "the refusal must name the year it refused"
    assert "supported-filing-years.toml" in message, (
        "the refusal must name the declaration that would admit the year; a refusal an operator "
        "cannot act on is an outage rather than a guard"
    )
    assert grade.value in message


def test_the_scheduling_rung_is_not_refused_by_the_supported_year_guard() -> None:
    """An applicability read must not raise the supported-year refusal.

    It may still fail for a real reason -- no revision governs that year -- and
    that is the answer the operator asked for. What it must never be is the
    supported-year guard, which would make the scheduling surface unable to
    speak about an out-of-scope year at all.
    """
    authority, years = _warm_authority()
    undeclared = min(years) - 1

    try:
        authority.snapshot(
            _M303,
            filing_year=undeclared,
            period=_QUARTER,
            grade=RegistryAuthorityGrade.APPLICABILITY,
        )
    except RegistryValidationError as error:  # pragma: no cover - defended below
        assert "not declared supported" not in str(error), (
            "the supported-year guard fired on the applicability rung; scheduling must stay readable"
        )
    except Exception as error:
        assert "not declared supported" not in str(error)


def test_every_declared_year_is_admitted_at_filing_grade() -> None:
    """Anti-tautology: the guard must not be refusing everything.

    A guard that refused every year would pass the refusal assertions above
    while making the product unusable, so the admitted side is proven too.
    """
    authority, years = _warm_authority()

    admitted = 0
    for year in years:
        try:
            authority.snapshot(_M303, filing_year=year, period=_QUARTER, grade=RegistryAuthorityGrade.FILING)
        except RegistryValidationError as error:
            assert "not declared supported" not in str(error), (
                f"the guard refused declared year {year}, which the declaration admits"
            )
        except Exception:  # noqa: S110 - a revision gap is not this guard's concern
            pass
        else:
            admitted += 1
    assert admitted, "no declared year produced a filing-grade snapshot; the admitted side is unproven"


def test_the_current_filing_year_from_the_clock_authority_is_declared_supported() -> None:
    """The year the product is actually operating in must be admitted.

    Read through the one clock authority rather than a literal, so this stays
    true as the calendar moves and reds the moment the declared window stops
    covering today.
    """
    _authority, years = _warm_authority()
    current = today_madrid().year

    assert current in years, (
        f"the current filing year {current} is not in the declared supported window {list(years)}; "
        "every consuming registry read for this year now refuses"
    )

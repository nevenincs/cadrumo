"""Building a filing draft refuses a year the registry does not declare supported.

The guard sits at the production consumption boundary, not on the shared
snapshot accessor, and the distinction is the whole design. The corpus
deliberately ships historical revisions -- 37 of the 58 bundled modelos carry
years outside the declared window, some reaching back to 2003 -- and inspecting
those revisions is legitimate registry work. Placing a supported-year refusal on
the accessor refuses that inspection too, which is how an earlier attempt at
this produced 36 refusals across the registry suite from tests that were
correctly reading revisions the registry genuinely ships.

What is not legitimate is BUILDING A FILING for a year outside the hard gates of
what the product declares. That is one call site, it is this one, and no
structural inspection passes through it.

Only the hard gates refuse here. The declaration is bounded rather than
enumerated, and its two ends differ: below the floor is outside the product's
claim, while above the horizon the newest declared revision carries forward, so
the year is answerable and the guard admits it. A declared hard ceiling closes
that open end.
"""

from __future__ import annotations

import pytest

from ....core.period import Period
from ....domain.calculations.registry.authority import bundled_authority
from ..draft_construction import _refuse_unsupported_filing_year
from ..errors import ModeloApplicationError

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _declared_years() -> tuple[int, ...]:
    declaration = bundled_authority().catalogues.supported_filing_years
    assert declaration is not None, "the bundled registry declares no supported filing years"
    return tuple(declaration.years)


def test_every_declared_year_is_admitted() -> None:
    """Anti-tautology: a guard that refused everything would pass the refusal proof below."""
    for year in _declared_years():
        _refuse_unsupported_filing_year(Period.from_year_and_code(year, "1T"))


def test_a_year_below_the_declared_window_refuses() -> None:
    """The year before the window opens is refused."""
    undeclared = min(_declared_years()) - 1

    with pytest.raises(ModeloApplicationError) as excinfo:
        _refuse_unsupported_filing_year(Period.from_year_and_code(undeclared, "1T"))

    context = excinfo.value.context or {}
    assert context.get("filing_year") == str(undeclared), context
    assert "supported-filing-years.toml" in str(context.get("declaration", "")), (
        "the refusal must name the declaration that would admit the year; a refusal an operator "
        "cannot act on is an outage rather than a guard"
    )


def test_a_year_above_the_horizon_is_admitted_while_no_hard_ceiling_is_declared() -> None:
    """The two ends of the declaration do not carry the same force.

    Below the floor is outside what the product claims. Above the horizon is
    not: no revision names such a year, but the newest declared one carries
    forward into it, so the year stays answerable and this guard lets it
    through. Whether a revision actually resolves is the resolver's question,
    asked with the modelo and period in hand; refusing it here would only name
    the earlier of two reasons.
    """
    declaration = bundled_authority().catalogues.supported_filing_years
    assert declaration is not None
    assert declaration.hard_ceiling is None, "this proof assumes the bundled span is open above its horizon"

    _refuse_unsupported_filing_year(Period.from_year_and_code(declaration.horizon + 1, "1T"))


def test_a_declared_hard_ceiling_closes_the_span_above_the_horizon() -> None:
    """The open end is a consequence of an absent ceiling, not of the guard ignoring the top."""
    declaration = bundled_authority().catalogues.supported_filing_years
    assert declaration is not None
    closed = declaration.model_copy(update={"hard_ceiling": declaration.horizon + 1})

    assert closed.admits_filing_year(closed.horizon + 1)
    assert not closed.admits_filing_year(closed.horizon + 2)


def test_the_refusal_names_the_span_it_would_accept() -> None:
    """An operator must be able to see what the product does support."""
    undeclared = min(_declared_years()) - 1

    with pytest.raises(ModeloApplicationError) as excinfo:
        _refuse_unsupported_filing_year(Period.from_year_and_code(undeclared, "1T"))

    listed = str((excinfo.value.context or {}).get("supported_filing_years", ""))
    assert str(min(_declared_years())) in listed, (
        f"the refusal must name the floor it would accept from; got {listed!r}"
    )
    assert "later" in listed, (
        "an open span must say so rather than enumerating years it does not bound; "
        f"got {listed!r}"
    )


def test_registry_inspection_of_an_undeclared_year_is_untouched() -> None:
    """The guard must not reach revisions the corpus legitimately ships for older years.

    This is the failure mode of the earlier placement: Modelo 100 ships 2020 and
    2021 revisions that structural tests read. Loading and inspecting them must
    stay possible, because the guard governs FILING, not reading.
    """
    modelo_100 = bundled_authority().modelo("100")
    declared = set(_declared_years())

    historical = [revision for revision in modelo_100.revisions.values() if revision.valid_from.year not in declared]

    assert historical, "Modelo 100 ships no revision outside the declared window; the case is unproven"
    for revision in historical:
        assert revision.casillas, f"revision {revision.id} inspected empty; the guard reached the read path"

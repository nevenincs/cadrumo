"""Building a filing draft refuses a year the registry does not declare supported.

The guard sits at the production consumption boundary, not on the shared
snapshot accessor, and the distinction is the whole design. The corpus
deliberately ships historical revisions -- 37 of the 58 bundled modelos carry
years outside the declared window, some reaching back to 2003 -- and inspecting
those revisions is legitimate registry work. Placing a supported-year refusal on
the accessor refuses that inspection too, which is how an earlier attempt at
this produced 36 refusals across the registry suite from tests that were
correctly reading revisions the registry genuinely ships.

What is not legitimate is BUILDING A FILING for a year nobody declared the
product supports. That is one call site, it is this one, and no structural
inspection passes through it: measured across the filing suite, every
``build_draft`` call uses a year inside the declared window.
"""

from __future__ import annotations

import pytest

from ....core.period import Period
from ....core.resources._boundary import bundled_path
from ....domain.calculations.registry.loader import load_registry_tree
from .._draft_construction import _refuse_unsupported_filing_year
from ..errors import ModeloApplicationError

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _declared_years() -> tuple[int, ...]:
    _modelos, catalogues = load_registry_tree(bundled_path("registry", "aeat"))
    declaration = catalogues.supported_filing_years
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


def test_a_year_above_the_declared_window_refuses() -> None:
    """The year after the window closes is refused too, not only the year before it."""
    undeclared = max(_declared_years()) + 1

    with pytest.raises(ModeloApplicationError):
        _refuse_unsupported_filing_year(Period.from_year_and_code(undeclared, "1T"))


def test_the_refusal_names_the_years_it_would_accept() -> None:
    """An operator must be able to see what the product does support."""
    undeclared = min(_declared_years()) - 1

    with pytest.raises(ModeloApplicationError) as excinfo:
        _refuse_unsupported_filing_year(Period.from_year_and_code(undeclared, "1T"))

    listed = str((excinfo.value.context or {}).get("supported_filing_years", ""))
    for year in _declared_years():
        assert str(year) in listed, f"declared year {year} absent from the refusal's accepted set"


def test_registry_inspection_of_an_undeclared_year_is_untouched() -> None:
    """The guard must not reach revisions the corpus legitimately ships for older years.

    This is the failure mode of the earlier placement: Modelo 100 ships 2020 and
    2021 revisions that structural tests read. Loading and inspecting them must
    stay possible, because the guard governs FILING, not reading.
    """
    modelos, _catalogues = load_registry_tree(bundled_path("registry", "aeat"))
    modelo_100 = next(modelo for modelo in modelos if modelo.id == "100")
    declared = set(_declared_years())

    historical = [revision for revision in modelo_100.revisions.values() if revision.valid_from.year not in declared]

    assert historical, "Modelo 100 ships no revision outside the declared window; the case is unproven"
    for revision in historical:
        assert revision.casillas, f"revision {revision.id} inspected empty; the guard reached the read path"

"""The declaration-result casilla is read from the registry, or not at all."""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal

import pytest

from ....core.casilla_id import CasillaId
from ....domain.calculations.registry.tests.authored_editions import filing_year_envelope, newest_authored_edition
from ....domain.calculations.registry.tests.published_authority import published_snapshot
from ....domain.modelos.codes import ModeloCode
from ..settlement_casilla import (
    DECLARATION_RESULT_SEMANTIC_ROLES,
    SETTLEMENT_SEMANTIC_ROLES,
    AmbiguousDeclarationResultError,
    DeclarationResultCasillas,
    declaration_result_casilla_id,
    declaration_result_casillas,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("operation")]


_YEAR = filing_year_envelope().horizon
_M100_YEAR = newest_authored_edition("100")


def _revision(modelo: str, year: int, period: str):
    return published_snapshot(modelo, filing_year=year, period=period).revision


def test_the_result_role_is_a_strict_subset_of_the_settlement_roles() -> None:
    """Both cells settle; only one is the result, and conflating them is the bug.

    Modelo 100 declares `irpf_cuota_resultante_autoliquidacion` (0595) for the
    liability BEFORE pagos a cuenta and `irpf_resultado_declaracion` (0670) for
    what the declaration settles. The advisory rightly watches both, because
    both must be computed before filing. A reader that wants "the result" must
    take only the second -- a first version of the resolver matched the whole
    settlement set and would have raised ambiguity on the one modelo it covers.
    """
    assert DECLARATION_RESULT_SEMANTIC_ROLES < SETTLEMENT_SEMANTIC_ROLES


def test_modelo_100_resolves_to_its_declared_result_casilla() -> None:
    """Read against the REAL bundled registry, not a fixture.

    A fixture would prove the matching logic and nothing about whether the
    shipped registry actually declares the role -- which is the fact the
    surface depends on.
    """
    revision = _revision("100", _M100_YEAR, "0A")
    assert declaration_result_casilla_id(revision) == "0670"


@pytest.mark.parametrize(("modelo", "period"), [("303", "3T"), ("130", "3T")])
def test_an_unmodelled_modelo_yields_nothing_rather_than_a_guess(modelo: str, period: str) -> None:
    """Absence is the honest answer for a modelo whose settlement is not modelled.

    303's casillas carry positional roles such as `dr303_23`, which name no
    meaning. Returning a plausible-looking cell for them would put a number
    under "result" that no authority supports, which is worse on a
    filing-facing list than showing nothing.
    """
    assert declaration_result_casilla_id(_revision(modelo, _YEAR, period)) is None


def test_two_casillas_claiming_the_result_role_is_refused() -> None:
    """A declaration with two results has none, so this refuses rather than picks.

    Driven through a stub carrying the shape the resolver reads, because the
    shipped registry does not contain this defect -- and the point of the
    refusal is to catch a registry that later does.
    """

    class _Casilla:
        def __init__(self, casilla_id: str) -> None:
            self.id = casilla_id
            self.semantic_role = "irpf_resultado_declaracion"

    class _Revision:
        id = "rev-with-two-results"
        casillas = (_Casilla("0670"), _Casilla("0671"))

    with pytest.raises(AmbiguousDeclarationResultError, match="cannot have two results"):
        declaration_result_casilla_id(_Revision())


def test_an_unknown_result_never_becomes_a_number_in_the_projection() -> None:
    """Four distinct unknowns reach `settled_result`, and none of them is a zero.

    `None` is returned when no reader is bound, when the declaration has no
    current calculation, when the modelo declares no result role, and when the
    calculation has not computed that cell. They are the same rendering -- "not
    available" -- but the projection must never turn any of them into a figure,
    because a zero in a result column is a filing-grade claim that the
    taxpayer owes nothing.
    """
    from ....core.period import Period
    from ..declarations_workspace import settled_result

    class _Unit:
        modelo = ModeloCode("100")
        filing_year = _M100_YEAR
        period = Period.from_year_and_code(_M100_YEAR, "0A")
        current_calculation_revision_id: str | None = "a" * 64

    class _Revision:
        casilla_values: Mapping[CasillaId, Decimal] = {"0670": Decimal("1234.56")}

    unit = _Unit()
    revisions = {"a" * 64: _Revision()}

    assert settled_result(unit, revisions, None) is None, "no reader bound is unknown"
    assert settled_result(unit, revisions, lambda *_: None) is None, "no declared role is unknown"
    assert settled_result(unit, {}, lambda *_: "0670") is None, "a missing revision is unknown"
    assert settled_result(unit, revisions, lambda *_: "9999") is None, "an uncomputed cell is unknown"

    without_calculation = _Unit()
    without_calculation.current_calculation_revision_id = None
    assert settled_result(without_calculation, revisions, lambda *_: "0670") is None

    assert settled_result(unit, revisions, lambda *_: "0670") == "1234.56", (
        "a grounded, computed result must reach the projection"
    )


def test_the_declared_type_rule_names_the_result_where_the_modelo_declares_one() -> None:
    """Modelo 130's "tipo de declaración" is read from box 19, so its result is box 19 by that rule."""
    selected = declaration_result_casillas("130", _revision("130", _YEAR, "1T"))

    assert selected == DeclarationResultCasillas(casilla_ids=("19",), by_declared_type=True)


def test_modelo_100_names_its_result_by_its_declared_type_rule() -> None:
    """The Modelo 100 record reads "tipo de declaración" from box 0670, the box its role also names."""
    selected = declaration_result_casillas("100", _revision("100", _M100_YEAR, "0A"))

    assert selected == DeclarationResultCasillas(casilla_ids=("0670",), by_declared_type=True)


def test_an_informative_modelo_has_no_result() -> None:
    assert declaration_result_casillas("349", _revision("349", _YEAR, "1T")) is None


def test_a_declared_result_box_the_revision_lacks_is_not_named() -> None:
    """Only the declared boxes the revision defines count; without them the registry's role decides.

    A stub carries a Modelo 130 revision without box 19, a defect the shipped
    registry does not have, to show the rule never names a box the revision
    does not define.
    """

    class _Casilla:
        def __init__(self, casilla_id: str, role: str | None) -> None:
            self.id = casilla_id
            self.semantic_role = role

    class _Revision:
        id = "rev-without-box-19"
        casillas = (_Casilla("18", None), _Casilla("0670", "irpf_resultado_declaracion"))

    class _Bare:
        id = "rev-without-any-result"
        casillas = (_Casilla("18", None),)

    assert declaration_result_casillas("130", _Revision()) == DeclarationResultCasillas(
        casilla_ids=("0670",), by_declared_type=False
    )
    assert declaration_result_casillas("130", _Bare()) is None

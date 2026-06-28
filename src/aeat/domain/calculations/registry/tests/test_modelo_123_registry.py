"""Modelo 123 registry behaviour for quarterly capital-income withholding filings."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from .....core.resources import bundled_path
from .. import (
    CasillaId,
    RegistrySnapshot,
    RegistryValidator,
    build_snapshot,
    calculate_registry_snapshot,
    load_registry_tree,
    validated_casilla_id,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_REGISTRY_ROOT = bundled_path("registry", "aeat")


def _casilla_id(value: object) -> CasillaId:
    try:
        return validated_casilla_id(value, surface="test casilla id")
    except ValueError as exc:
        raise AssertionError(f"M123 registry test casilla key {value!r} is not a CasillaId") from exc


_M123_RENTAS_DIVIDENDOS_CASILLA: CasillaId = _casilla_id("01")
_M123_RENTAS_RESTO_CASILLA: CasillaId = _casilla_id("02")
_M123_RENTAS_TOTAL_CASILLA: CasillaId = _casilla_id("03")
_M123_BASE_DIVIDENDOS_CASILLA: CasillaId = _casilla_id("04")
_M123_BASE_RESTO_CASILLA: CasillaId = _casilla_id("05")
_M123_BASE_TOTAL_CASILLA: CasillaId = _casilla_id("06")
_M123_RETENCIONES_DIVIDENDOS_CASILLA: CasillaId = _casilla_id("07")
_M123_RETENCIONES_RESTO_CASILLA: CasillaId = _casilla_id("08")
_M123_PREVIOUS_RESULT_CASILLA: CasillaId = _casilla_id("10")
_M123_PREVIOUS_PERIOD_WITHHELD_CASILLA: CasillaId = _casilla_id("11")
_M123_A_INGRESAR_CASILLA: CasillaId = _casilla_id("13")
_M123_2019_2023_NPERCEPTORES_CASILLA: CasillaId = _casilla_id("01-legacy")
_M123_2019_2023_BASE_CASILLA: CasillaId = _casilla_id("02-legacy")
_M123_2019_2023_RETENCIONES_CASILLA: CasillaId = _casilla_id("03-legacy")
_M123_2019_2023_REGULARIZACION_CASILLA: CasillaId = _casilla_id("04-legacy")
_M123_2019_2023_PREVIOUS_RESULT_CASILLA: CasillaId = _casilla_id("05-legacy")
_M123_2019_2023_RESULTADO_CASILLA: CasillaId = _casilla_id("06-legacy")
_M123_2019_2023_INGRESO_CASILLA: CasillaId = _casilla_id("07-legacy")


def _load_modelo(modelo_id: str):
    modelos, catalogues = load_registry_tree(_REGISTRY_ROOT)
    modelo = next(item for item in modelos if item.id == modelo_id)
    return modelo, catalogues


@pytest.mark.parametrize(
    ("filing_year", "required_surfaces"),
    [
        (
            2023,
            {
                "calculation",
                "filing",
                "export",
                "verification",
                "review",
                "approval",
                "reconciliation",
                "extractor",
                "portal",
                "workflow",
            },
        ),
        (
            2026,
            {
                "calculation",
                "filing",
                "export",
                "verification",
                "review",
                "approval",
                "reconciliation",
                "extractor",
                "portal",
                "deadline",
                "workflow",
            },
        ),
    ],
)
def test_modelo_123_validated_snapshot_owns_workflow_surfaces(
    filing_year: int,
    required_surfaces: set[str],
) -> None:
    modelo, catalogues = _load_modelo("123")

    RegistryValidator(catalogues, source_root=bundled_path()).validate_modelo(modelo)
    snapshot = build_snapshot(
        modelo,
        catalogues,
        source_root=bundled_path(),
        filing_year=filing_year,
        period="1T",
    )

    construct = snapshot.revision.constructs[0]
    linked_by_surface = {
        link.surface: link for link in snapshot.revision.application_links if link.id in construct.application_links
    }
    assert required_surfaces <= set(linked_by_surface)
    assert all(link.requires_snapshot for link in linked_by_surface.values())


# ---------------------------------------------------------------------------
# Casilla 06 arithmetic oracle (Aitor #211)
#
# Authority: Orden HAC/56/2024 Anexo II + form text citation
# "Base de retenciones e ingresos a cuenta. Totales [06]" = [04] + [05].
# Casilla 06 must equal the sum of the two base sub-totals only.
# Perceptor counts (casillas 01, 02, 03) must NOT contribute to casilla 06.
# ---------------------------------------------------------------------------


def _snapshot_2024(filing_year: int = 2024):
    modelo, catalogues = _load_modelo("123")
    return build_snapshot(
        modelo,
        catalogues,
        source_root=bundled_path(),
        filing_year=filing_year,
        period="1T",
    )


def _calculate_2024(
    snapshot: RegistrySnapshot,
    *,
    nperceptores_dividendos: int,
    nperceptores_resto: int,
    base_dividendos: Decimal,
    base_resto: Decimal,
):
    """Drive calculate_registry_snapshot with M123 2024+ manual inputs.

    All retenciones, periodificacion, and liquidacion inputs are zeroed so
    only casilla 06 (base_total = [04] + [05]) varies under test.
    """
    return calculate_registry_snapshot(
        snapshot,
        inputs={
            _M123_RENTAS_DIVIDENDOS_CASILLA: Decimal(nperceptores_dividendos),
            _M123_RENTAS_RESTO_CASILLA: Decimal(nperceptores_resto),
            _M123_BASE_DIVIDENDOS_CASILLA: base_dividendos,
            _M123_BASE_RESTO_CASILLA: base_resto,
            _M123_RETENCIONES_DIVIDENDOS_CASILLA: Decimal("0"),
            _M123_RETENCIONES_RESTO_CASILLA: Decimal("0"),
            _M123_PREVIOUS_RESULT_CASILLA: Decimal("0"),
            _M123_PREVIOUS_PERIOD_WITHHELD_CASILLA: Decimal("0"),
            _M123_A_INGRESAR_CASILLA: Decimal("0"),
        },
        date_context={"filing_period": date(2024, 12, 31)},
    )


def test_m123_casilla_06_equals_base_dividendos_plus_base_resto() -> None:
    """Casilla 06 = [04] + [05] (base total).

    Oracle authority: Orden HAC/56/2024 form text, field label
    "Base de retenciones e ingresos a cuenta. Totales [06]".

    With base_dividendos=42000 and base_resto=0, casilla 06 must be 42000.
    The perceptor count (nperceptores=7 split as 01=4, 02=3) must not
    contribute to casilla 06.
    """
    snapshot = _snapshot_2024()
    result = _calculate_2024(
        snapshot,
        nperceptores_dividendos=4,
        nperceptores_resto=3,
        base_dividendos=Decimal("42000.00"),
        base_resto=Decimal("0.00"),
    )
    casilla_03 = result.values[_M123_RENTAS_TOTAL_CASILLA]
    casilla_06 = result.values[_M123_BASE_TOTAL_CASILLA]
    assert casilla_03 == Decimal("7"), f"precondition: casilla 03 (total count) should be 7, got {casilla_03}"
    assert casilla_06 == Decimal("42000.00"), (
        f"casilla 06 (base total) should be 42000.00 (= base_dividendos + base_resto), "
        f"got {casilla_06}; if this is 42007 the formula incorrectly includes perceptor count"
    )


def test_m123_casilla_06_base_resto_only() -> None:
    """Casilla 06 = base_dividendos + base_resto also holds when base is in base_resto.

    Oracle: nperceptores=1 (01=1, 02=0), base=5000 in casilla 05 (base_resto).
    Casilla 06 must be 5000, not 5001.
    """
    snapshot = _snapshot_2024()
    result = _calculate_2024(
        snapshot,
        nperceptores_dividendos=1,
        nperceptores_resto=0,
        base_dividendos=Decimal("0.00"),
        base_resto=Decimal("5000.00"),
    )
    casilla_03 = result.values[_M123_RENTAS_TOTAL_CASILLA]
    casilla_06 = result.values[_M123_BASE_TOTAL_CASILLA]
    assert casilla_03 == Decimal("1"), f"precondition: casilla 03 should be 1, got {casilla_03}"
    assert casilla_06 == Decimal("5000.00"), (
        f"casilla 06 must be 5000.00, got {casilla_06}; if 5001 then perceptor count is leaking into casilla 06"
    )


def test_m123_casilla_06_invariant_to_nperceptores() -> None:
    """Changing nperceptores must NOT change casilla 06 (anti-tautology).

    Authority: perceptor counts (casillas 01, 02) feed only casilla 03
    (numero_rentas_total). They have no path into casilla 06 (base_total).
    With base fixed at 42000 in casilla 04, casilla 06 must remain 42000
    regardless of whether nperceptores is 1, 7, or 100.
    """
    snapshot = _snapshot_2024()
    base_fixed = Decimal("42000.00")
    results = [
        _calculate_2024(
            snapshot,
            nperceptores_dividendos=n,
            nperceptores_resto=0,
            base_dividendos=base_fixed,
            base_resto=Decimal("0.00"),
        ).values[_M123_BASE_TOTAL_CASILLA]
        for n in (1, 7, 100)
    ]
    assert results[0] == results[1] == results[2] == base_fixed, (
        f"casilla 06 must be invariant to nperceptores; got {results}"
    )


# ---------------------------------------------------------------------------
# 2019-2023 revision: casilla 06-legacy semantic is different
# ("Suma de retenciones y regularizacion" = [03-legacy] + [05-legacy]).
# Perceptor count (01-legacy) and base (02-legacy) must NOT contribute.
# ---------------------------------------------------------------------------


def test_m123_legacy_casilla_06_invariant_to_nperceptores_and_base() -> None:
    """2019-2023 revision: casilla 06-legacy is retenciones+regularizacion, not base.

    Authority: 2019-2023 form text citation "[03] + [05]".
    Inputs 01-legacy (nperceptores) and 02-legacy (base retenciones) are
    manual pass-through casillas with no formula; they must not affect
    casilla 06-legacy (Suma de retenciones y regularizacion = [03-legacy] + [05-legacy]).
    """
    modelo, catalogues = _load_modelo("123")
    snapshot = build_snapshot(
        modelo,
        catalogues,
        source_root=bundled_path(),
        filing_year=2022,
        period="1T",
    )
    result = calculate_registry_snapshot(
        snapshot,
        inputs={
            _M123_2019_2023_NPERCEPTORES_CASILLA: Decimal("7"),
            _M123_2019_2023_BASE_CASILLA: Decimal("42000.00"),
            _M123_2019_2023_RETENCIONES_CASILLA: Decimal("100.00"),
            _M123_2019_2023_REGULARIZACION_CASILLA: Decimal("0.00"),
            _M123_2019_2023_PREVIOUS_RESULT_CASILLA: Decimal("0.00"),
            _M123_2019_2023_INGRESO_CASILLA: Decimal("0.00"),
        },
        date_context={"filing_period": date(2022, 12, 31)},
    )
    casilla_06 = result.values[_M123_2019_2023_RESULTADO_CASILLA]
    assert casilla_06 == Decimal("100.00"), (
        f"casilla 06-legacy (suma retenciones+regularizacion = [03]+[05]) "
        f"should be 100.00 (= retenciones + 0), got {casilla_06}; "
        f"nperceptores (01-legacy=7) and base (02-legacy=42000) must not contribute"
    )

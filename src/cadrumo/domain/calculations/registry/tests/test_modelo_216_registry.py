"""Tests for the committed Modelo 216 IRNR retención registry foundation.

Modelo 216 is the quarterly IRNR withholding autoliquidación (retenciones e
ingresos a cuenta) approved by Orden EHA/3290/2008 (BOE-A-2008-18497), with the
current form layout carried by Orden HAC/56/2024. The trimestral filing plazo is
grounded in Orden EHA/3290/2008 art 4: the first twenty natural days of April,
July, October and January for the immediately preceding natural quarter.

See Also:
    :func:`~domain.calculations.registry.tests._registry_schema_support._committed_modelo`
        Test loader for the committed registry definition and legal catalogue.
    :class:`~domain.calculations.registry._validate.RegistryValidator`
        Registry validator that checks the authored legal/source references.
    :func:`~domain.calculations.registry._authority.bundled_authority`
        Authority facade used to resolve the trimestral deadline windows.
    :func:`~domain.calculations.registry._snapshot.build_snapshot`
        Snapshot builder feeding the Modelo 216 formula runtime proof.
    :func:`~domain.calculations.registry._formula_runtime.calculate_registry_snapshot`
        Formula evaluator used to verify the retained-total arithmetic.
    :class:`~domain.calculations.registry._ids.CasillaId`
        Typed casilla identifier used for the Modelo 216 calculation inputs.
    :class:`~core.TaxDomain`
        Closed tax-family enum whose IRNR member classifies the registration.
    :data:`~core.UNMODELED_OBLIGATIONS`
        Former recognized-unmodeled set reduced by the Modelo 216 promotion.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from .....core import CasillaId, validated_casilla_id
from .....core.resources import bundled_path
from .._authority import bundled_authority
from .._formula_runtime import calculate_registry_snapshot
from .._snapshot import build_snapshot
from .._validate import RegistryValidator
from ._registry_schema_support import _committed_modelo

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_BASE_DINERARIA: CasillaId = validated_casilla_id("08", surface="_BASE_DINERARIA")
_BASE_ESPECIE: CasillaId = validated_casilla_id("09", surface="_BASE_ESPECIE")
_BASE_TOTAL: CasillaId = validated_casilla_id("10", surface="_BASE_TOTAL")
_RET_DINERARIA: CasillaId = validated_casilla_id("11", surface="_RET_DINERARIA")
_RET_ESPECIE: CasillaId = validated_casilla_id("12", surface="_RET_ESPECIE")
_RET_TOTAL: CasillaId = validated_casilla_id("13", surface="_RET_TOTAL")
_ANTERIORES: CasillaId = validated_casilla_id("20", surface="_ANTERIORES")
_RESULTADO: CasillaId = validated_casilla_id("21", surface="_RESULTADO")


def _load_modelo_216():
    return _committed_modelo("216")


def test_modelo_216_validator_accepts_committed_definition() -> None:
    modelo, catalogues = _load_modelo_216()
    assert modelo.id == "216"
    assert modelo.revisions, "216 must declare at least one revision"
    RegistryValidator(catalogues, source_root=bundled_path()).validate_modelo(modelo)


def test_modelo_216_formulas_owned_by_construct() -> None:
    modelo, _ = _load_modelo_216()
    revision = modelo.revisions["2024-y-siguientes"]
    owned = set().union(*(set(c.formulas) for c in revision.constructs))
    assert {"modelo-216-base-total", "modelo-216-retenciones-total", "modelo-216-resultado"} <= owned


def test_modelo_216_deadline_provision_is_orden_eha_3290_2008_art_4() -> None:
    """Every trimestral window cites the binding Orden EHA/3290/2008 art 4 plazo."""
    modelo, catalogues = _load_modelo_216()
    revision = modelo.revisions["2024-y-siguientes"]
    assert revision.deadline_windows, "216 must declare quarterly deadline windows"
    for window in revision.deadline_windows:
        assert window.period_kind == "quarterly"
        assert "orden-eha-3290-2008:art-4" in window.legal_refs
    # The plazo article resolves in the shared legal catalogue as legal authority,
    # cross-checked against the bundled BOE corpus at build.
    plazo = catalogues.legal["orden-eha-3290-2008:art-4"]
    assert plazo.evidence_tier == "legal_authority"
    assert plazo.document_id == "BOE-A-2008-18497"


def test_modelo_216_trimestral_windows_open_and_close_on_day_20() -> None:
    """Orden EHA/3290/2008 art 4: first twenty natural days of Apr/Jul/Oct/Jan.

    Derived strictly from the statutory plazo (the immediately preceding natural
    quarter, filed in the first 20 natural days of the following opening month),
    not copied from engine output.
    """
    authority = bundled_authority()
    windows = {w.id: w for _, _, w in authority.deadline_windows(2025, modelos=("216",))}
    expected = {
        "modelo-216-2025-1t": (date(2025, 4, 1), date(2025, 4, 20)),
        "modelo-216-2025-2t": (date(2025, 7, 1), date(2025, 7, 20)),
        "modelo-216-2025-3t": (date(2025, 10, 1), date(2025, 10, 20)),
        "modelo-216-2025-4t": (date(2026, 1, 1), date(2026, 1, 20)),
    }
    assert set(expected) <= set(windows)
    for window_id, (opens, closes) in expected.items():
        assert windows[window_id].opens_on == opens
        assert windows[window_id].closes_on == closes


def test_modelo_216_resultado_is_retenciones_total_minus_anteriores() -> None:
    """Casilla 21 = casilla 13 (total retenciones) - casilla 20 (anteriores).

    Base total (10) = 08 + 09, retenciones total (13) = 11 + 12, resultado a
    ingresar (21) = 13 - 20, per the AEAT Modelo 216 instructions' own printed
    total rows.
    """
    modelo, catalogues = _load_modelo_216()
    snapshot = build_snapshot(modelo, catalogues, source_root=bundled_path(), filing_year=2025, period="1T")
    result = calculate_registry_snapshot(
        snapshot,
        inputs={
            _BASE_DINERARIA: Decimal("1000.00"),
            _BASE_ESPECIE: Decimal("500.00"),
            _RET_DINERARIA: Decimal("190.00"),
            _RET_ESPECIE: Decimal("95.00"),
            _ANTERIORES: Decimal("40.00"),
        },
        date_context={"filing_period": date(2025, 3, 31)},
    )
    assert result.values[_BASE_TOTAL] == Decimal("1500.00")
    assert result.values[_RET_TOTAL] == Decimal("285.00")
    assert result.values[_RESULTADO] == Decimal("245.00")

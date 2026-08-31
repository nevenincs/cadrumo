"""Unit tests for the codified per-modelo amendment-kind regime.

Expected boundaries are taken from the bundled official AEAT Diseño de
Registros and manual corpus (an external authority, not a re-run of the
function under test):

- M303: the diseño "ejercicio 2024 a partir de periodos 09 y 3T y siguientes"
  introduces the ``autoliq_rectificativa`` fichero fields; the prior diseño
  "ejercicio 2024 hasta periodos 08 y 2T" carries none. Boundary: filing_year
  2024, period 09 (monthly) or 3T (quarterly) onward.
- M100: Manual Práctico de Renta 2025 states the rectificativa is the general
  IRPF correction mechanism "para los períodos impositivos 2024 y
  siguientes"; the registry's 2024 revision carries the rectificativa
  discrepancia-de-criterio casilla (0669).
- M200: the 2024 registry revision carries rectificativa
  casillas throughout its "rectificativa" sections.
- M130/M131: the bundled diseño de registros carries no rectificativa fields
  at all (stops at "ejercicios 2019 y siguientes"); no bundled AEAT source
  grounds an adoption period, so the regime never reports rectificativa
  support for these modelos.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from ..amendment_kind_regime import (
    AmendmentLiabilityDirection,
    classify_amendment_liability_direction,
    modelo_has_codified_amendment_regime,
    permitted_amendment_kind_values,
    resolve_amendment_kind_regime,
)
from ..modelo import Modelo
from ..period import Period

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_COMPLEMENTARIA = "complementaria"
_SUSTITUTIVA = "sustitutiva"
_RECTIFICATIVA = "rectificativa"
_RectificativaBoundaryCase = tuple[str, str, int, str, bool]
_LiabilityDirectionCase = tuple[str, Decimal, Decimal, AmendmentLiabilityDirection]

_RECTIFICATIVA_BOUNDARY_CASES: tuple[_RectificativaBoundaryCase, ...] = (
    # M303: 2T 2024 predates the diseño's rectificativa fichero fields.
    ("m303-2t-2024-pre-boundary", Modelo.M303, 2024, "2T", False),
    # M303: period 08 (August, monthly) is the last pre-boundary month.
    ("m303-08-2024-pre-boundary", Modelo.M303, 2024, "08", False),
    # M303: 3T 2024 is the diseño's stated boundary quarter.
    ("m303-3t-2024-post-boundary", Modelo.M303, 2024, "3T", True),
    # M303: period 09 (September, monthly) is the diseño's stated boundary month.
    ("m303-09-2024-post-boundary", Modelo.M303, 2024, "09", True),
    # M303: every later period stays post-boundary.
    ("m303-1t-2026-post-boundary", Modelo.M303, 2026, "1T", True),
    # M303: an earlier filing year is pre-boundary.
    ("m303-4t-2023-pre-boundary", Modelo.M303, 2023, "4T", False),
    # M100: annual period; 2023 is pre-boundary, 2024 onward is post.
    ("m100-0a-2023-pre-boundary", Modelo.M100, 2023, "0A", False),
    ("m100-0a-2024-post-boundary", Modelo.M100, 2024, "0A", True),
    ("m100-0a-2026-post-boundary", Modelo.M100, 2026, "0A", True),
    # M200: annual period; 2023 is pre-boundary, 2024 onward is post.
    ("m200-0a-2023-pre-boundary", Modelo.M200, 2023, "0A", False),
    ("m200-0a-2024-post-boundary", Modelo.M200, 2024, "0A", True),
    # M130: no bundled rectificativa grounding at any period.
    ("m130-1t-2026-no-codified-regime", Modelo.M130, 2026, "1T", False),
    ("m130-4t-2030-no-codified-regime", Modelo.M130, 2030, "4T", False),
    # M131: same conservative scoping as M130.
    ("m131-1t-2026-no-codified-regime", Modelo.M131, 2026, "1T", False),
)

_LIABILITY_DIRECTION_CASES: tuple[_LiabilityDirectionCase, ...] = (
    ("increase", Decimal("100.00"), Decimal("150.00"), AmendmentLiabilityDirection.INCREASE),
    ("decrease", Decimal("100.00"), Decimal("50.00"), AmendmentLiabilityDirection.DECREASE),
    ("unchanged", Decimal("100.00"), Decimal("100.00"), AmendmentLiabilityDirection.UNCHANGED),
    # A more negative credit position raises the taxpayer's declared
    # liability under the signed-result convention (a bigger credit
    # position filed as a smaller credit raises what is due).
    ("credit-shrinks-is-increase", Decimal("-200.00"), Decimal("-50.00"), AmendmentLiabilityDirection.INCREASE),
    ("credit-grows-is-decrease", Decimal("-50.00"), Decimal("-200.00"), AmendmentLiabilityDirection.DECREASE),
)


def test_rectificativa_effective_boundary() -> None:
    for case_id, modelo, year, code, expect_rectificativa_effective in _RECTIFICATIVA_BOUNDARY_CASES:
        period = Period.from_year_and_code(year, code)
        regime = resolve_amendment_kind_regime(modelo, period)
        assert regime.rectificativa_effective is expect_rectificativa_effective, case_id


def test_pre_rectificativa_permits_only_complementaria_and_sustitutiva() -> None:
    period = Period.from_year_and_code(2024, "2T")
    permitted = permitted_amendment_kind_values(Modelo.M303, period)
    assert permitted == frozenset({_COMPLEMENTARIA, _SUSTITUTIVA})
    assert _RECTIFICATIVA not in permitted


def test_post_rectificativa_permits_only_rectificativa_and_sustitutiva() -> None:
    period = Period.from_year_and_code(2024, "3T")
    permitted = permitted_amendment_kind_values(Modelo.M303, period)
    assert permitted == frozenset({_RECTIFICATIVA, _SUSTITUTIVA})
    assert _COMPLEMENTARIA not in permitted


def test_modelo_with_no_codified_regime_never_permits_rectificativa() -> None:
    """M130 has zero bundled rectificativa grounding at any period tested."""
    for year, code in ((2024, "1T"), (2026, "4T"), (2030, "0A")):
        permitted = permitted_amendment_kind_values(Modelo.M130, Period.from_year_and_code(year, code))
        assert _RECTIFICATIVA not in permitted, f"{year} {code}"
        assert permitted == frozenset({_COMPLEMENTARIA, _SUSTITUTIVA})


def test_modelo_has_codified_amendment_regime_probe() -> None:
    assert modelo_has_codified_amendment_regime(Modelo.M303) is True
    assert modelo_has_codified_amendment_regime(Modelo.M100) is True
    assert modelo_has_codified_amendment_regime(Modelo.M200) is True
    assert modelo_has_codified_amendment_regime(Modelo.M130) is False
    assert modelo_has_codified_amendment_regime(Modelo.M131) is False


def test_uncodified_modelo_defaults_to_pre_rectificativa_never_asserted() -> None:
    """A modelo entirely absent from the table (M390) is never asserted rectificativa-effective."""
    regime = resolve_amendment_kind_regime(Modelo.M390, Period.from_year_and_code(2026, "0A"))
    assert regime.rectificativa_effective is False
    assert regime.permitted_kinds == frozenset({_COMPLEMENTARIA, _SUSTITUTIVA})


def test_classify_amendment_liability_direction() -> None:
    for case_id, baseline, corrected, expected in _LIABILITY_DIRECTION_CASES:
        result = classify_amendment_liability_direction(baseline_result=baseline, corrected_result=corrected)
        assert result == expected, case_id

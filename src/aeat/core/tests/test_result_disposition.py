"""Unit tests for the codified per-modelo result-disposition mapping.

Expected disposition codes are taken from the bundled official AEAT Diseños de
Registros "Tipo de declaración" notes (an external authority, not a re-run of the
function under test):

- M303: C/D/G/I/N/V/U/X — credit → C.
- M130/M131: I/U/G/N/B — credit → B (resultado a deducir).
- M111/M115/M123: I/U/G/N — no credit code; non-positive → N.
- M200/M202 (IS): not codified here (final-result casilla + devolución/renuncia
  elections need IS-domain grounding) → derivation returns None.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from .. import ResultDisposition, derive_result_disposition, modelo_has_codified_disposition

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def _values(casilla: str, amount: str) -> dict[str, Decimal]:
    return {casilla: Decimal(amount)}


def test_disposition_codes_match_the_official_diseno_letters() -> None:
    """Each member value is the single-character code AEAT's fichero expects."""
    assert ResultDisposition.COMPENSACION.value == "C"
    assert ResultDisposition.DEVOLUCION.value == "D"
    assert ResultDisposition.CUENTA_CORRIENTE_INGRESO.value == "G"
    assert ResultDisposition.INGRESO.value == "I"
    assert ResultDisposition.NEGATIVA.value == "N"
    assert ResultDisposition.CUENTA_CORRIENTE_DEVOLUCION.value == "V"
    assert ResultDisposition.DOMICILIACION.value == "U"
    assert ResultDisposition.DEVOLUCION_TRANSFERENCIA_EXTRANJERO.value == "X"
    assert ResultDisposition.RESULTADO_A_DEDUCIR.value == "B"
    assert ResultDisposition.RENUNCIA_DEVOLUCION.value == "R"


def test_m303_credit_is_compensacion_not_ingreso() -> None:
    """The headline regression: an IVA credit must map to C, never silently I."""
    disp = derive_result_disposition("303", _values("71", "-210.00"))
    assert disp is ResultDisposition.COMPENSACION
    assert disp is not ResultDisposition.INGRESO


def test_m303_positive_is_ingreso_and_zero_is_negativa() -> None:
    assert derive_result_disposition("303", _values("71", "357.00")) is ResultDisposition.INGRESO
    assert derive_result_disposition("303", _values("71", "0")) is ResultDisposition.NEGATIVA


def test_m130_credit_is_resultado_a_deducir_not_compensacion() -> None:
    """IRPF pago fraccionado uses B (resultado a deducir) for a negative result, not C."""
    assert derive_result_disposition("130", _values("19", "-50.00")) is ResultDisposition.RESULTADO_A_DEDUCIR
    assert derive_result_disposition("130", _values("19", "120.00")) is ResultDisposition.INGRESO
    assert derive_result_disposition("130", _values("19", "0")) is ResultDisposition.NEGATIVA
    # M131 (módulos variant) shares the code set; result casilla 15.
    assert derive_result_disposition("131", _values("15", "-50.00")) is ResultDisposition.RESULTADO_A_DEDUCIR


def test_retenciones_positive_is_ingreso_else_negativa() -> None:
    """Retenciones (111/115/123) have no compensar/deducir code: non-positive → N."""
    assert derive_result_disposition("111", _values("30", "500.00")) is ResultDisposition.INGRESO
    assert derive_result_disposition("111", _values("30", "0")) is ResultDisposition.NEGATIVA
    assert derive_result_disposition("115", _values("05", "0")) is ResultDisposition.NEGATIVA
    assert derive_result_disposition("123", _values("14", "12.00")) is ResultDisposition.INGRESO


def test_missing_result_casilla_defaults_to_negativa() -> None:
    """An absent result casilla is treated as zero → N (never silently ingreso)."""
    assert derive_result_disposition("303", {}) is ResultDisposition.NEGATIVA


def test_m200_credit_is_devolucion_not_compensacion() -> None:
    """IS annual uses D (solicitud de devolución) for a negative result, not C.

    Result casilla DP200014B:00599 (semantic_role is_resultado_ingresar_o_devolver),
    signed. A refund (negative) → D, a payment (positive) → I, zero → N.
    """
    assert derive_result_disposition("200", _values("DP200014B:00599", "-1000.00")) is ResultDisposition.DEVOLUCION
    assert derive_result_disposition("200", _values("DP200014B:00599", "5000.00")) is ResultDisposition.INGRESO
    assert derive_result_disposition("200", _values("DP200014B:00599", "0")) is ResultDisposition.NEGATIVA
    # Key-scheme robust: the bare number also resolves.
    assert derive_result_disposition("200", _values("00599", "5000.00")) is ResultDisposition.INGRESO


def test_m202_active_modality_result_drives_ingreso_or_negativa() -> None:
    """IS pago fraccionado: only I/N. The active modality's a-ingresar casilla
    (40.2 -> 03, 40.3 -> 34, exactly one non-zero) drives the disposition."""
    assert derive_result_disposition("202", _values("34", "900.00")) is ResultDisposition.INGRESO  # 40.3 active
    assert derive_result_disposition("202", _values("03", "750.00")) is ResultDisposition.INGRESO  # 40.2 active
    assert derive_result_disposition("202", {"03": Decimal("0"), "34": Decimal("0")}) is ResultDisposition.NEGATIVA


def test_uncodified_modelo_returns_none_not_a_guess() -> None:
    """A modelo without a codified spec returns None so the caller applies a
    documented fallback rather than a guessed disposition."""
    assert derive_result_disposition("390", _values("71", "-1000.00")) is None
    assert modelo_has_codified_disposition("303") is True
    assert modelo_has_codified_disposition("200") is True
    assert modelo_has_codified_disposition("202") is True
    assert modelo_has_codified_disposition("390") is False


def test_credit_and_debit_diverge_per_modelo() -> None:
    """Anti-regression: a debit and a credit of equal magnitude never share a code."""
    assert derive_result_disposition("303", _values("71", "210")) is not derive_result_disposition(
        "303", _values("71", "-210")
    )
    assert derive_result_disposition("130", _values("19", "50")) is not derive_result_disposition(
        "130", _values("19", "-50")
    )

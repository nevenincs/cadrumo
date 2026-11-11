"""Arithmetic and boundary refusals of one payer's suffered-withholding record.

Expected figures are worked by hand from LIRPF art. 99.6 and art. 79.e: the
credit is the retención plus the whole ingreso a cuenta, and a repercusión
changes only the income side.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from ....core.retencion_soportada import RetencionSoportadaCantidad, RetencionSoportadaClase
from ...calculations.registry.tests.authored_editions import filing_year_envelope
from ..retencion_soportada import RetencionSoportadaOrigen, RetencionSoportadaRecord

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_PAYER_REF = "a" * 64
_FINGERPRINT = "b" * 64


def _payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "ejercicio": filing_year_envelope().horizon,
        "payer_tax_id": "B00010082",
        "payer_legal_name": "Pagador Sintetico SL",
        "payer_ref": _PAYER_REF,
        "income_class": "trabajo",
        "importe_integro_dinerario": "20000.00",
        "valoracion_especie": "1000.00",
        "retencion": "1200.00",
        "ingreso_a_cuenta": "300.00",
        "ingreso_a_cuenta_repercutido": "300.00",
        "origin": "payer_certificate",
        "evidence_fingerprint": _FINGERPRINT,
        "captured_at": datetime(1980, 4, 2, 9, 0, tzinfo=UTC).isoformat(),
    }
    payload.update(overrides)
    return payload


def _record(**overrides: object) -> RetencionSoportadaRecord:
    """Read a record the way storage reads one: from its JSON payload."""
    return RetencionSoportadaRecord.model_validate_json(json.dumps(_payload(**overrides)))


def test_a_repercutido_ingreso_a_cuenta_still_credits_in_full() -> None:
    record = _record()
    assert record.pago_a_cuenta == Decimal("1500.00")
    assert record.quantity(RetencionSoportadaCantidad.PAGO_A_CUENTA) == Decimal("1500.00")


def test_repercusion_moves_only_the_income_side() -> None:
    repercutido = _record()
    not_repercutido = _record(ingreso_a_cuenta_repercutido="0.00")
    # 20.000,00 + 1.000,00 + 300,00 - 300,00 and the same without the deduction.
    assert repercutido.importe_integro == Decimal("21000.00")
    assert not_repercutido.importe_integro == Decimal("21300.00")
    assert repercutido.pago_a_cuenta == not_repercutido.pago_a_cuenta == Decimal("1500.00")


def test_each_quantity_reads_its_own_figure() -> None:
    record = _record(ingreso_a_cuenta_repercutido="100.00")
    assert record.quantity(RetencionSoportadaCantidad.RETENCION) == Decimal("1200.00")
    assert record.quantity(RetencionSoportadaCantidad.INGRESO_A_CUENTA) == Decimal("300.00")
    assert record.quantity(RetencionSoportadaCantidad.INGRESO_A_CUENTA_REPERCUTIDO) == Decimal("100.00")
    assert record.quantity(RetencionSoportadaCantidad.IMPORTE_INTEGRO) == Decimal("21200.00")


def test_a_record_survives_a_json_round_trip() -> None:
    record = _record()
    assert RetencionSoportadaRecord.model_validate_json(record.model_dump_json()) == record
    assert record.income_class is RetencionSoportadaClase.TRABAJO
    assert record.origin is RetencionSoportadaOrigen.PAYER_CERTIFICATE


def test_an_unknown_income_class_is_refused_at_the_record() -> None:
    with pytest.raises(ValidationError):
        _record(income_class="rendimiento_desconocido")


@pytest.mark.parametrize(
    "overrides",
    [
        {"ingreso_a_cuenta_repercutido": "300.01"},
        {"retencion": "-1.00"},
        {"retencion": "1.001"},
        {"origin": "payer_certificate", "evidence_fingerprint": None},
        {"payer_ref": "not-a-digest"},
    ],
)
def test_the_record_refuses_each_isolated_defect(overrides: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        _record(**overrides)


def test_a_correction_may_name_the_certificate_it_rests_on_as_the_one_it_replaces() -> None:
    record = _record(replaces_evidence_fingerprint=_FINGERPRINT)
    assert record.replaces_evidence_fingerprint == record.evidence_fingerprint == _FINGERPRINT
    assert RetencionSoportadaRecord.model_validate_json(record.model_dump_json()) == record


def test_an_operator_declaration_needs_no_certificate() -> None:
    record = _record(origin="operator_declaration", evidence_fingerprint=None)
    assert record.evidence_fingerprint is None

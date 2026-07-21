"""Export -> fichero-BOE -> parse -> strict-equality round-trip CI gate.

A computed modelo draft is exported to the
AEAT fixed-width register (fichero-BOE), the exported bytes are parsed back
through the registry export layout, and every parser-covered casilla is asserted
identical to the source draft (strict per-casilla Decimal equality across the
boundary).

Real adapters only, no test doubles: the real registry schema provider, the real
:func:`export_draft` serialiser, and the real
:func:`cadrumo.domain.calculations.registry.parse_export_payload` /
:func:`verify_export` deserialiser drive every assertion. Non-default, mutually
distinct casilla values are populated so a save-drops-field or field-swap
regression is visible at the boundary. Each modelo also carries an anti-tautology
proof: one exported casilla is mutated on disk and the round-trip is asserted to
surface the divergence (``DRIFT`` plus the mutated casilla in
``mismatched_casilla_ids``), so a green ``MATCH`` cannot be a vacuous pass.

Modelos covered: 130 (pago fraccionado IRPF estimación directa), 303 (IVA
autoliquidación, refund variant so the full DR303 envelope including the
cuenta-devolución page round-trips), and 390 (IVA resumen anual).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

import pytest

from ....core import Period
from ....core.decimal import coerce_decimal
from ....domain.calculations.registry import (
    CasillaFieldKind,
    CasillaId,
    parse_export_payload,
    validated_casilla_id,
)
from ....domain.filing import ModeloDraft, ModeloInputs
from ....domain.submission import ModeloDraftStatus
from .. import (
    DeclaracionVerifyVerdict,
    ModeloOperatorProfile,
    build_draft,
    export_draft,
    verify_export,
)
from ..runtime import RegistrySchemaAccessor
from ._export_support import _field_slice, _schema_provider

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_CENTS = Decimal("0.01")
_PROFILE = ModeloOperatorProfile(tax_id="12345678Z", display_name="Round-trip test")


def _cid(value: str) -> CasillaId:
    return validated_casilla_id(value, surface="test_fichero_boe_export_roundtrip")


@dataclass(frozen=True)
class _RoundtripCase:
    """One modelo's export -> parse round-trip fixture."""

    modelo: str
    period: Period
    provider_factory: Callable[[], RegistrySchemaAccessor]
    inputs: ModeloInputs
    headers: dict[str, str]
    output_name: str
    # Input casillas that MUST round-trip through the parser-covered set with a
    # non-zero value: the load-bearing economic inputs of the filing.
    key_casillas: tuple[CasillaId, ...]


def _modelo_130_case() -> _RoundtripCase:
    return _RoundtripCase(
        modelo="130",
        period=Period.from_year_and_code(2026, "1T"),
        provider_factory=lambda: _schema_provider(modelos=("130",)),
        inputs={
            _cid("01"): Decimal("10000.00"),
            _cid("02"): Decimal("4000.00"),
            _cid("05"): Decimal("0"),
            _cid("06"): Decimal("0"),
            _cid("08"): Decimal("0"),
            _cid("10"): Decimal("0"),
            "irpf.previous_year_economic_activity_net_income": Decimal("13000"),
            "modelo-130-pagos-fraccionados-anteriores": Decimal("0"),
            "modelo-130-resultados-negativos-anteriores": Decimal("0"),
            _cid("16"): Decimal("0"),
            _cid("18"): Decimal("0"),
        },
        headers={
            "declaration_type": "I",
            "surnames": "GARCIA LOPEZ",
            "name": "JUAN",
            "program_version": "A001",
            "presenter_nif": "12345678Z",
        },
        output_name="modelo-130-roundtrip.txt",
        key_casillas=(_cid("01"), _cid("02")),
    )


def _modelo_303_case() -> _RoundtripCase:
    return _RoundtripCase(
        modelo="303",
        period=Period.from_year_and_code(2025, "1T"),
        provider_factory=lambda: _schema_provider(modelos=("303",)),
        inputs={
            _cid("07"): Decimal("10000.00"),
            "iva.repercutido.general": Decimal("2100.00"),
            "modelo-303-compensacion-pendiente-anteriores": Decimal("0"),
        },
        # Refund disposition ("D") so the cuenta-devolución (DID) page is emitted
        # and the full DR303 envelope round-trips through the parser.
        headers={
            "declaration_type": "D",
            "surnames": "GARCIA LOPEZ",
            "full_name": "GARCIA LOPEZ JUAN",
            "program_version": "A001",
            "presenter_nif": "12345678Z",
            "redeme": "1",
            "iban": "ES9121000418450200051332",
            "sepa_marca": "1",
        },
        output_name="modelo-303-roundtrip.txt",
        key_casillas=(_cid("07"), _cid("09")),
    )


def _modelo_390_case() -> _RoundtripCase:
    return _RoundtripCase(
        modelo="390",
        period=Period.from_year_and_code(2025, "0A"),
        provider_factory=lambda: _schema_provider(filing_year=2025, period="0A", modelos=("390",)),
        inputs={
            _cid("iva.anual.repercutido.general"): Decimal("18000.00"),
            _cid("iva.anual.repercutido.reducido"): Decimal("2100.50"),
            _cid("iva.anual.repercutido.super-reducido"): Decimal("420.00"),
            _cid("iva.anual.soportado.interiores"): Decimal("9800.25"),
            _cid("iva.anual.soportado.importaciones"): Decimal("650.00"),
            _cid("iva.anual.autorepercutido.intracomunitaria"): Decimal("300.00"),
            _cid("iva.anual.repercutido.recargo.general"): Decimal("1248.00"),
            _cid("iva.anual.repercutido.recargo.reducido"): Decimal("624.00"),
            _cid("iva.anual.compensacion-ultimo-periodo-97"): Decimal("0.00"),
            _cid("iva.anual.compensacion-generada-ejercicio-no-97"): Decimal("0.00"),
        },
        headers={
            "declaration_type": "I",
            "surnames": "GARCIA LOPEZ",
            "name": "JUAN",
            "program_version": "A001",
            "presenter_nif": "12345678Z",
        },
        output_name="modelo-390-roundtrip.txt",
        key_casillas=(_cid("iva.anual.repercutido.general"), _cid("iva.anual.cuota-devengada-total")),
    )


_ROUNDTRIP_CASES = (
    pytest.param(_modelo_130_case, id="modelo-130"),
    pytest.param(_modelo_303_case, id="modelo-303"),
    pytest.param(_modelo_390_case, id="modelo-390"),
)


def _build_approved_draft(case: _RoundtripCase, provider: RegistrySchemaAccessor) -> ModeloDraft:
    draft = build_draft(
        modelo=case.modelo,
        period=case.period,
        profile=_PROFILE,
        inputs=case.inputs,
        schema_provider=provider,
    )
    return draft.model_copy(update={"status": ModeloDraftStatus.APROBADO})


def _draft_casilla_values(draft: ModeloDraft) -> dict[CasillaId, Decimal]:
    return {
        value.casilla_id: coerce_decimal(value.value, default=Decimal("0")) or Decimal("0") for value in draft.values
    }


def _parsed_currency_casillas(
    case: _RoundtripCase,
    provider: RegistrySchemaAccessor,
    payload: bytes,
) -> dict[CasillaId, Decimal]:
    layout = provider.get_subview(case.modelo).export_layouts[0]
    parsed = parse_export_payload(
        layout,
        payload,
        source_root=provider.source_root,
        sources=provider.sources,
    )
    covered: dict[CasillaId, Decimal] = {}
    for value in parsed.casillas:
        if value.casilla_id is None or not isinstance(value.value, Decimal):
            continue
        covered[value.casilla_id] = value.value
    return covered


@pytest.mark.parametrize("case_factory", _ROUNDTRIP_CASES)
def test_export_roundtrip_preserves_every_covered_casilla(
    tmp_path: Path,
    case_factory: Callable[[], _RoundtripCase],
) -> None:
    """Exported bytes parse back to casilla values identical to the source draft."""
    case = case_factory()
    provider = case.provider_factory()
    draft = _build_approved_draft(case, provider)
    expected = _draft_casilla_values(draft)

    output = tmp_path / case.output_name
    receipt = export_draft(draft, output_path=output, headers=case.headers, schema_provider=provider)
    payload = output.read_bytes()
    assert receipt.byte_size == len(payload)

    covered = _parsed_currency_casillas(case, provider, payload)

    # The parser must re-read real values, not vacuously match an empty set: the
    # load-bearing economic inputs must round-trip non-zero, and the covered set
    # must carry at least two mutually distinct non-zero magnitudes so a
    # field-swap or save-drops-field regression cannot hide behind a uniform 0.
    assert covered, f"modelo {case.modelo}: parser re-read no currency casillas"
    for casilla_id in case.key_casillas:
        assert casilla_id in covered, f"modelo {case.modelo}: key casilla {casilla_id!r} dropped on round-trip"
        assert covered[casilla_id] != Decimal("0"), (
            f"modelo {case.modelo}: key casilla {casilla_id!r} round-tripped as zero"
        )
    distinct_non_zero = {value.quantize(_CENTS) for value in covered.values() if value != Decimal("0")}
    assert len(distinct_non_zero) >= 2, (
        f"modelo {case.modelo}: round-trip carries < 2 distinct non-zero casillas; "
        "a field-swap regression would be invisible"
    )

    # Strict equality across the boundary: every parser-covered casilla equals the
    # source draft's value to the cent.
    for casilla_id, parsed_value in covered.items():
        assert casilla_id in expected, f"modelo {case.modelo}: parsed casilla {casilla_id!r} absent from source draft"
        assert parsed_value.quantize(_CENTS) == expected[casilla_id].quantize(_CENTS), (
            f"modelo {case.modelo}: casilla {casilla_id!r} round-trip drift — "
            f"draft={expected[casilla_id]} parsed={parsed_value}"
        )

    # The production verify path (export -> parse -> compare) agrees: MATCH, no drift.
    verdict = verify_export(draft, file_path=output, schema_provider=provider)
    assert verdict.verdict is DeclaracionVerifyVerdict.MATCH
    assert verdict.mismatched_casilla_ids == ()
    assert verdict.file_sha256 == receipt.file_sha256


@pytest.mark.parametrize("case_factory", _ROUNDTRIP_CASES)
def test_export_roundtrip_surfaces_a_mutated_casilla(
    tmp_path: Path,
    case_factory: Callable[[], _RoundtripCase],
) -> None:
    """Anti-tautology proof: a mutated exported casilla breaks the round-trip equality.

    If this test ever passes with the export layout broken, every round-trip
    assertion in this module is tautological.
    """
    case = case_factory()
    provider = case.provider_factory()
    draft = _build_approved_draft(case, provider)
    expected = _draft_casilla_values(draft)
    layout = provider.get_subview(case.modelo).export_layouts[0]

    output = tmp_path / case.output_name
    export_draft(draft, output_path=output, headers=case.headers, schema_provider=provider)

    # Pick the first CASILLA-kind field whose draft value is non-zero and not the
    # sentinel 0.01 we are about to write, so the mutation is guaranteed to be a
    # real value change.
    record, field = next(
        (record, field)
        for record in sorted(layout.records, key=lambda item: item.order)
        for field in record.fields
        if field.kind == CasillaFieldKind.CASILLA
        and field.casilla_id is not None
        and field.casilla_id in expected
        and expected[field.casilla_id] not in (Decimal("0"), Decimal("0.01"))
        and field.length is not None
    )
    mutated_casilla = field.casilla_id
    assert mutated_casilla is not None
    field_length = field.length
    assert field_length is not None

    payload = bytearray(output.read_bytes())
    payload[_field_slice(layout, record.id, field.id)] = ("0" * (field_length - 1) + "1").encode("ascii")
    mutated = tmp_path / f"mutated-{case.output_name}"
    mutated.write_bytes(payload)

    # The production verify path surfaces the divergence as DRIFT on exactly the
    # mutated casilla.
    verdict = verify_export(draft, file_path=mutated, schema_provider=provider)
    assert verdict.verdict is DeclaracionVerifyVerdict.DRIFT
    assert mutated_casilla in verdict.mismatched_casilla_ids

    # And a direct re-parse no longer reconstructs the source value for it.
    reparsed = _parsed_currency_casillas(case, provider, bytes(payload))
    assert reparsed[mutated_casilla].quantize(_CENTS) != expected[mutated_casilla].quantize(_CENTS)

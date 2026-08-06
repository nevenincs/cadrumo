"""Shared helpers for fichero-BOE round-trip tests."""

from __future__ import annotations

from decimal import Decimal
from functools import cache
from pathlib import Path
from typing import TYPE_CHECKING, NamedTuple

from .......core import Period
from .......domain.calculations.registry import CasillaId, validated_casilla_id
from .._record_spec import FieldKind, SignedMode, record_field, validate_record_specs

if TYPE_CHECKING:
    from .......application.filing.runtime import RegistrySchemaAccessor

_AMOUNT_CASILLA: CasillaId = validated_casilla_id("01", surface="_AMOUNT_CASILLA")
_M130_INGRESOS_CASILLA: CasillaId = validated_casilla_id("01", surface="_M130_INGRESOS_CASILLA")
_M130_GASTOS_CASILLA: CasillaId = validated_casilla_id("02", surface="_M130_GASTOS_CASILLA")
_M130_PAGOS_FRACCIONADOS_CASILLA: CasillaId = validated_casilla_id("05", surface="_M130_PAGOS_FRACCIONADOS_CASILLA")
_M130_RETENCIONES_CASILLA: CasillaId = validated_casilla_id("06", surface="_M130_RETENCIONES_CASILLA")
_M130_AGRARIAN_VOLUME_CASILLA: CasillaId = validated_casilla_id("08", surface="_M130_AGRARIAN_VOLUME_CASILLA")
_M130_AGRARIAN_WITHHELD_CASILLA: CasillaId = validated_casilla_id("10", surface="_M130_AGRARIAN_WITHHELD_CASILLA")
_M130_HOME_DEDUCTION_CASILLA: CasillaId = validated_casilla_id("16", surface="_M130_HOME_DEDUCTION_CASILLA")
_M130_PRIOR_RETURN_CASILLA: CasillaId = validated_casilla_id("18", surface="_M130_PRIOR_RETURN_CASILLA")
_M303_BASE_GENERAL_CASILLA: CasillaId = validated_casilla_id("07", surface="_M303_BASE_GENERAL_CASILLA")
_M303_CUOTA_GENERAL_CASILLA: CasillaId = validated_casilla_id(
    "iva.repercutido.general", surface="_M303_CUOTA_GENERAL_CASILLA"
)


@cache
def _schema_provider(modelo: str) -> RegistrySchemaAccessor:
    from .......application.filing import build_runtime_schema_provider

    return build_runtime_schema_provider(modelos=(modelo,))


def _wire_body(payload: bytes) -> bytes:
    return payload[: -len(b"\r\n")] if payload.endswith(b"\r\n") else payload


def _currency_specs(*, signed_mode: SignedMode = SignedMode.UNSIGNED):
    specs = (
        record_field(
            offset=1,
            length=12,
            field_id="AMOUNT",
            casilla_id=_AMOUNT_CASILLA,
            kind=FieldKind.CURRENCY,
            signed_mode=signed_mode,
        ),
    )
    validate_record_specs(specs, total_length=specs[-1].offset - 1 + specs[-1].length)
    return specs


def _money_bytes(amount: Decimal, *, signed: bool = False) -> bytes:
    cents = int(abs(amount * 100))
    if amount < 0:
        return ("N" + str(cents).zfill(16)).encode("latin-1")
    if signed:
        return (" " + str(cents).zfill(16)).encode("latin-1")
    return str(cents).zfill(17).encode("latin-1")


class _ExportedPayload(NamedTuple):
    payload: bytes
    receipt_byte_size: int
    receipt_file_sha256: str | None


def _m303_headers(*, declaration_type: str, redeme: str, **extra_headers: str) -> dict[str, str]:
    return {
        "declaration_type": declaration_type,
        "surnames": "GARCIA LOPEZ",
        "full_name": "GARCIA LOPEZ JUAN",
        "program_version": "A001",
        "presenter_nif": "12345678Z",
        "redeme": redeme,
        **extra_headers,
    }


def _export_approved_303_fichero(
    tmp_path: Path,
    *,
    filename: str,
    headers: dict[str, str],
) -> _ExportedPayload:
    from .......application.filing import (
        ModeloDraftStatus,
        ModeloOperatorProfile,
        build_draft,
        export_draft,
    )

    provider = _schema_provider("303")
    draft = build_draft(
        modelo="303",
        period=Period.from_year_and_code(2025, "1T"),
        profile=ModeloOperatorProfile(
            tax_id="12345678Z",
            display_name="Golden test IVA",
        ),
        inputs={
            _M303_BASE_GENERAL_CASILLA: Decimal("10000.00"),
            _M303_CUOTA_GENERAL_CASILLA: Decimal("2100.00"),
            "modelo-303-compensacion-pendiente-anteriores": Decimal("0"),
        },
        schema_provider=provider,
    )
    draft = draft.model_copy(update={"status": ModeloDraftStatus.APROBADO})

    output = tmp_path / filename
    receipt = export_draft(
        draft,
        output_path=output,
        headers=headers,
        schema_provider=provider,
    )
    return _ExportedPayload(
        payload=output.read_bytes(),
        receipt_byte_size=receipt.byte_size,
        receipt_file_sha256=receipt.file_sha256,
    )

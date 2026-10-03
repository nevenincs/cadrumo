"""Reviewed Modelo 190 signed reintegro and incapacity context validation."""

from __future__ import annotations

from collections.abc import Mapping

from ...domain.calculations.export_field_kind import CasillaFieldKind
from ...domain.calculations.registry.export_value_policy import ExportValuePolicy
from ...domain.calculations.registry.schema_exports import ExportFieldDefinition, ExportRecordDefinition
from ...domain.filing.errors import FilingExportValidationError

_M190_SIGNED_PAIRS = (
    (
        "modelo-190-perc-signo-percepcion-dineraria",
        "modelo-190-perc-percepcion-dineraria",
        "modelo-190-perceptor-row-percibido-dinerario",
        81,
        82,
        95,
        None,
    ),
    (
        "modelo-190-perc-signo-percepcion-especie",
        "modelo-190-perc-percepcion-especie",
        "modelo-190-perceptor-row-percibido-especie",
        108,
        109,
        122,
        None,
    ),
    (
        "modelo-190-perc-signo-incapacidad-dineraria",
        "modelo-190-perc-incapacidad-dineraria-percepcion",
        "modelo-190-perceptor-row-incapacidad-dineraria-percepcion",
        255,
        256,
        269,
        "a-or-b01",
    ),
    (
        "modelo-190-perc-signo-incapacidad-especie",
        "modelo-190-perc-incapacidad-especie-valoracion",
        "modelo-190-perceptor-row-incapacidad-especie-valoracion",
        282,
        283,
        296,
        "a-only",
    ),
)


_M190_REVIEWED_SOURCES = {
    "aeat-dr-190-2020": "4cefd924a7dda3ac5159582f728a72f6f162d3344b8e87f2d17900e6fdcf3b32",
    "aeat-dr-190-2023": "430daf439ed645155ffc6096b65c4da5b26dd2e6c16b8e4781f9be145b3792cb",
    "aeat-dr-190-2024": "20bc8086525ce850063b9ae8644b8514483e5c34f90c8e47cfadc6c52cf7390e",
    "aeat-dr-190-2025": "a7d1092f78620431812354e560a5146a3ae244e0aed69d9d58c353370ba0134d",
}


_M190_CONTEXT_FIELDS = (
    ("modelo-190-perc-clave", 78, 1),
    ("modelo-190-perc-subclave", 79, 2),
    ("modelo-190-perc-ejercicio-devengo", 148, 4),
    ("modelo-190-perc-retenciones-practicadas", 95, 13),
    ("modelo-190-perc-ingresos-a-cuenta", 122, 13),
    ("modelo-190-perc-incapacidad-dineraria-retenciones", 269, 13),
    ("modelo-190-perc-incapacidad-especie-ingresos-a-cuenta", 296, 13),
)


def _m190_reviewed_source_ref(signed: ExportFieldDefinition, source_digests: Mapping[str, str] | None) -> str:
    refs = tuple(map(str, signed.source_refs))
    if len(refs) != 1:
        raise FilingExportValidationError("modelo 190 signed components lack their exact reviewed source digest")
    source_ref = refs[0]
    if source_digests is None or source_digests.get(source_ref) != _M190_REVIEWED_SOURCES.get(source_ref):
        raise FilingExportValidationError("modelo 190 signed components lack their exact reviewed source digest")
    return source_ref


def _require_m190_reviewed_context(by_id: Mapping[str, ExportFieldDefinition], refs: tuple[str, ...]) -> None:
    for identifier, offset, length in _M190_CONTEXT_FIELDS:
        context_field = by_id.get(identifier)
        if (
            context_field is None
            or (context_field.offset, context_field.length) != (offset, length)
            or tuple(map(str, context_field.source_refs)) != refs
        ):
            raise FilingExportValidationError("modelo 190 signed condition context differs from reviewed source")


def _m190_component_shape_matches(
    sign: ExportFieldDefinition, amount: ExportFieldDefinition, sign_offset: int, amount_offset: int
) -> bool:
    return (
        sign.value_policy is ExportValuePolicy.SIGNED_COMPONENT_SIGN
        and amount.value_policy is ExportValuePolicy.SIGNED_COMPONENT_MAGNITUDE
        and sign.offset == sign_offset
        and amount.offset == amount_offset
        and sign.length == 1
        and amount.length == 13
        and sign.kind is CasillaFieldKind.BINDING
        and amount.kind is CasillaFieldKind.BINDING
    )


def _m190_component_binding_matches(sign: ExportFieldDefinition, amount: ExportFieldDefinition, binding: str) -> bool:
    return (
        str(sign.binding) == binding
        and sign.binding == amount.binding
        and sign.casilla_id is None
        and amount.casilla_id is None
    )


def _m190_component_sources_match(sign: ExportFieldDefinition, amount: ExportFieldDefinition, source_ref: str) -> bool:
    return tuple(map(str, sign.source_refs)) == (source_ref,) and tuple(map(str, amount.source_refs)) == (source_ref,)


def _require_m190_component_declaration(
    by_id: Mapping[str, ExportFieldDefinition],
    pair: tuple[str, str, str, int, int, int, str | None],
    source_ref: str,
) -> tuple[ExportFieldDefinition, ExportFieldDefinition]:
    sign_id, amount_id, binding, sign_offset, amount_offset, _, _ = pair
    sign, amount = by_id.get(sign_id), by_id.get(amount_id)
    if sign is None or amount is None:
        raise FilingExportValidationError("modelo 190 signed component declaration is incomplete or changed")
    if not _m190_component_shape_matches(sign, amount, sign_offset, amount_offset):
        raise FilingExportValidationError("modelo 190 signed component declaration is incomplete or changed")
    if not _m190_component_binding_matches(sign, amount, binding):
        raise FilingExportValidationError("modelo 190 signed component declaration is incomplete or changed")
    if not _m190_component_sources_match(sign, amount, source_ref):
        raise FilingExportValidationError("modelo 190 signed component declaration is incomplete or changed")
    return sign, amount


def _require_m190_component_wire(wire: str, sign_offset: int, amount_offset: int) -> tuple[str, str]:
    marker = wire[sign_offset - 1]
    magnitude = wire[amount_offset - 1 : amount_offset + 12]
    if not magnitude.isascii() or not magnitude.isdigit() or marker not in {" ", "N"}:
        raise FilingExportValidationError("modelo 190 signed component has invalid wire bytes")
    return marker, magnitude


def _require_m190_incapacity_context(*, occupied: bool, restricted: str | None, key: str, subkey: str) -> None:
    if occupied and restricted == "a-or-b01" and not (key == "A" or (key == "B" and subkey == "01")):
        raise FilingExportValidationError("modelo 190 incapacity monetary amount requires key A or B.01")
    if occupied and restricted == "a-only" and key != "A":
        raise FilingExportValidationError("modelo 190 incapacity in-kind amount requires key A")


def _m190_prior_year_is_valid(filing_year: str, devengo_year: str) -> bool:
    return (
        filing_year.isascii()
        and filing_year.isdigit()
        and devengo_year.isascii()
        and devengo_year.isdigit()
        and 0 < int(devengo_year) < int(filing_year)
    )


def _require_m190_reintegro_context(
    wire: str,
    *,
    marker: str,
    magnitude: str,
    retention_offset: int,
    filing_year: str,
    devengo_year: str,
) -> None:
    if marker != "N":
        return
    if magnitude == "0" * 13:
        raise FilingExportValidationError("modelo 190 negative reintegro requires a nonzero magnitude")
    retention = wire[retention_offset - 1 : retention_offset + 12]
    if not _m190_prior_year_is_valid(filing_year, devengo_year) or retention != "0" * 13:
        raise FilingExportValidationError(
            "modelo 190 reintegro requires an earlier devengo year and zero associated withholding"
        )


def require_m190_signed_reintegro_context(
    record: ExportRecordDefinition, wire: str, *, source_digests: Mapping[str, str] | None = None
) -> None:
    """Enforce the source's prior-year, zero-withholding and incapacity conditions."""
    if str(record.id) != "modelo-190-perceptor":
        return
    by_id = {str(field.id): field for field in record.fields}
    signed = by_id.get(_M190_SIGNED_PAIRS[0][0])
    if signed is None or signed.value_policy is not ExportValuePolicy.SIGNED_COMPONENT_SIGN:
        return  # Superseded manually authored layouts do not claim this contract.
    if len(wire) != 500:
        raise FilingExportValidationError("modelo 190 signed perceptor record is incomplete")
    refs = tuple(map(str, signed.source_refs))
    source_ref = _m190_reviewed_source_ref(signed, source_digests)
    _require_m190_reviewed_context(by_id, refs)
    key, subkey = wire[77], wire[78:80]
    filing_year, devengo_year = wire[4:8], wire[147:151]
    for pair in _M190_SIGNED_PAIRS:
        _, _, _, sign_offset, amount_offset, retention_offset, restricted = pair
        _require_m190_component_declaration(by_id, pair, source_ref)
        marker, magnitude = _require_m190_component_wire(wire, sign_offset, amount_offset)
        occupied = marker == "N" or any(char != "0" for char in magnitude)
        _require_m190_incapacity_context(occupied=occupied, restricted=restricted, key=key, subkey=subkey)
        _require_m190_reintegro_context(
            wire,
            marker=marker,
            magnitude=magnitude,
            retention_offset=retention_offset,
            filing_year=filing_year,
            devengo_year=devengo_year,
        )

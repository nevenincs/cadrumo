"""Reviewed Modelo 190 signed reintegro and incapacity context validation."""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal

from ...domain.calculations.export_field_kind import CasillaFieldKind
from ...domain.calculations.registry.errors import RegistryValidationError
from ...domain.calculations.registry.export_value_policy import (
    ExportValuePolicy,
    export_value_policy_wire_length,
    project_export_value,
    validate_export_wire_value,
)
from ...domain.calculations.registry.schema_exports import ExportFieldDefinition, ExportRecordDefinition
from ...domain.filing.errors import FilingExportValidationError
from ...domain.modelos.perceptor_clave_scope import PerceptorClaveScope

_M190_SIGNED_PAIRS = (
    (
        "modelo-190-perc-signo-percepcion-dineraria",
        "modelo-190-perc-percepcion-dineraria",
        "modelo-190-perceptor-row-percibido-dinerario",
        "modelo-190-perc-retenciones-practicadas",
        None,
    ),
    (
        "modelo-190-perc-signo-percepcion-especie",
        "modelo-190-perc-percepcion-especie",
        "modelo-190-perceptor-row-percibido-especie",
        "modelo-190-perc-ingresos-a-cuenta",
        None,
    ),
    (
        "modelo-190-perc-signo-incapacidad-dineraria",
        "modelo-190-perc-incapacidad-dineraria-percepcion",
        "modelo-190-perceptor-row-incapacidad-dineraria-percepcion",
        "modelo-190-perc-incapacidad-dineraria-retenciones",
        "perc.incapacidad-dineraria-percepcion",
    ),
    (
        "modelo-190-perc-signo-incapacidad-especie",
        "modelo-190-perc-incapacidad-especie-valoracion",
        "modelo-190-perceptor-row-incapacidad-especie-valoracion",
        "modelo-190-perc-incapacidad-especie-ingresos-a-cuenta",
        "perc.incapacidad-especie-valoracion",
    ),
)
_M190_CLAVE_ID = "modelo-190-perc-clave"
_M190_SUBCLAVE_ID = "modelo-190-perc-subclave"
_M190_FILING_YEAR_ID = "modelo-190-perc-year"
_M190_DEVENGO_YEAR_ID = "modelo-190-perc-ejercicio-devengo"


_M190_REVIEWED_SOURCES = {
    "aeat-dr-190-2020": "4cefd924a7dda3ac5159582f728a72f6f162d3344b8e87f2d17900e6fdcf3b32",
    "aeat-dr-190-2023": "430daf439ed645155ffc6096b65c4da5b26dd2e6c16b8e4781f9be145b3792cb",
    "aeat-dr-190-2024": "20bc8086525ce850063b9ae8644b8514483e5c34f90c8e47cfadc6c52cf7390e",
    "aeat-dr-190-2025": "a7d1092f78620431812354e560a5146a3ae244e0aed69d9d58c353370ba0134d",
}


_M190_CONTEXT_FIELD_IDS = (
    _M190_CLAVE_ID,
    _M190_SUBCLAVE_ID,
    _M190_FILING_YEAR_ID,
    _M190_DEVENGO_YEAR_ID,
    *(pair[3] for pair in _M190_SIGNED_PAIRS),
)
_M190_NEGATIVE_SIGN = project_export_value(ExportValuePolicy.SIGNED_COMPONENT_SIGN, Decimal(-1))


def _span(field: ExportFieldDefinition) -> tuple[int, int]:
    """Return the field's one-based start and exclusive end as the layout declares them."""
    if field.offset is None or field.length is None:
        raise FilingExportValidationError("modelo 190 signed component declaration is incomplete or changed")
    return field.offset, field.offset + field.length


def _field_wire(wire: str, field: ExportFieldDefinition) -> str:
    start, end = _span(field)
    return wire[start - 1 : end - 1]


def _m190_reviewed_source_ref(signed: ExportFieldDefinition, source_digests: Mapping[str, str] | None) -> str:
    refs = tuple(map(str, signed.source_refs))
    if len(refs) != 1:
        raise FilingExportValidationError("modelo 190 signed components lack their exact reviewed source digest")
    source_ref = refs[0]
    if source_digests is None or source_digests.get(source_ref) != _M190_REVIEWED_SOURCES.get(source_ref):
        raise FilingExportValidationError("modelo 190 signed components lack their exact reviewed source digest")
    return source_ref


def _require_m190_reviewed_context(by_id: Mapping[str, ExportFieldDefinition], refs: tuple[str, ...]) -> None:
    for identifier in _M190_CONTEXT_FIELD_IDS:
        context_field = by_id.get(identifier)
        if context_field is None or tuple(map(str, context_field.source_refs)) != refs:
            raise FilingExportValidationError("modelo 190 signed condition context differs from reviewed source")


def _m190_component_shape_matches(
    sign: ExportFieldDefinition, amount: ExportFieldDefinition, retention: ExportFieldDefinition
) -> bool:
    return (
        sign.value_policy is ExportValuePolicy.SIGNED_COMPONENT_SIGN
        and amount.value_policy is ExportValuePolicy.SIGNED_COMPONENT_MAGNITUDE
        and sign.length == export_value_policy_wire_length(ExportValuePolicy.SIGNED_COMPONENT_SIGN)
        and amount.offset == _span(sign)[1]
        and amount.length == retention.length
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
    pair: tuple[str, str, str, str, str | None],
    source_ref: str,
) -> tuple[ExportFieldDefinition, ExportFieldDefinition, ExportFieldDefinition]:
    sign_id, amount_id, binding, retention_id, _ = pair
    sign, amount, retention = by_id.get(sign_id), by_id.get(amount_id), by_id.get(retention_id)
    if sign is None or amount is None or retention is None:
        raise FilingExportValidationError("modelo 190 signed component declaration is incomplete or changed")
    if not _m190_component_shape_matches(sign, amount, retention):
        raise FilingExportValidationError("modelo 190 signed component declaration is incomplete or changed")
    if not _m190_component_binding_matches(sign, amount, binding):
        raise FilingExportValidationError("modelo 190 signed component declaration is incomplete or changed")
    if not _m190_component_sources_match(sign, amount, source_ref):
        raise FilingExportValidationError("modelo 190 signed component declaration is incomplete or changed")
    return sign, amount, retention


def _require_m190_component_wire(
    wire: str, sign: ExportFieldDefinition, amount: ExportFieldDefinition
) -> tuple[str, str]:
    marker = _field_wire(wire, sign)
    magnitude = _field_wire(wire, amount)
    try:
        validate_export_wire_value(ExportValuePolicy.SIGNED_COMPONENT_SIGN, marker)
    except RegistryValidationError as exc:
        raise FilingExportValidationError("modelo 190 signed component has invalid wire bytes") from exc
    if not magnitude.isascii() or not magnitude.isdigit():
        raise FilingExportValidationError("modelo 190 signed component has invalid wire bytes")
    return marker, magnitude


def _require_m190_incapacity_context(
    *,
    occupied: bool,
    scoped_casilla: str | None,
    key: str,
    subkey: str,
    clave_scope: PerceptorClaveScope,
) -> None:
    if occupied and scoped_casilla is not None and not clave_scope.admits(scoped_casilla, key, subkey):
        raise FilingExportValidationError(f"modelo 190 {scoped_casilla} amount is outside the keys it applies to")


def _m190_prior_year_is_valid(filing_year: str, devengo_year: str) -> bool:
    return (
        filing_year.isascii()
        and filing_year.isdigit()
        and devengo_year.isascii()
        and devengo_year.isdigit()
        and 0 < int(devengo_year) < int(filing_year)
    )


def _require_m190_reintegro_context(
    *,
    marker: str,
    magnitude: str,
    retention: str,
    filing_year: str,
    devengo_year: str,
) -> None:
    if marker != _M190_NEGATIVE_SIGN:
        return
    if magnitude == "0" * len(magnitude):
        raise FilingExportValidationError("modelo 190 negative reintegro requires a nonzero magnitude")
    if not _m190_prior_year_is_valid(filing_year, devengo_year) or retention != "0" * len(retention):
        raise FilingExportValidationError(
            "modelo 190 reintegro requires an earlier devengo year and zero associated withholding"
        )


def require_m190_signed_reintegro_context(
    record: ExportRecordDefinition,
    wire: str,
    *,
    clave_scope: PerceptorClaveScope | None,
    source_digests: Mapping[str, str] | None = None,
) -> None:
    """Enforce the source's prior-year, zero-withholding and incapacity conditions."""
    if record.id != "modelo-190-perceptor":
        return
    by_id = {field.id: field for field in record.fields}
    signed = by_id.get(_M190_SIGNED_PAIRS[0][0])
    if signed is None or signed.value_policy is not ExportValuePolicy.SIGNED_COMPONENT_SIGN:
        return  # Superseded manually authored layouts do not claim this contract.
    if len(wire) != max(_span(field)[1] - 1 for field in record.fields):
        raise FilingExportValidationError("modelo 190 signed perceptor record is incomplete")
    if clave_scope is None:
        raise FilingExportValidationError("modelo 190 signed perceptor record needs its clave scope")
    refs = tuple(map(str, signed.source_refs))
    source_ref = _m190_reviewed_source_ref(signed, source_digests)
    _require_m190_reviewed_context(by_id, refs)
    key = _field_wire(wire, by_id[_M190_CLAVE_ID])
    subkey = _field_wire(wire, by_id[_M190_SUBCLAVE_ID])
    filing_year = _field_wire(wire, by_id[_M190_FILING_YEAR_ID])
    devengo_year = _field_wire(wire, by_id[_M190_DEVENGO_YEAR_ID])
    for pair in _M190_SIGNED_PAIRS:
        scoped_casilla = pair[4]
        sign, amount, retention = _require_m190_component_declaration(by_id, pair, source_ref)
        marker, magnitude = _require_m190_component_wire(wire, sign, amount)
        occupied = marker == _M190_NEGATIVE_SIGN or any(char != "0" for char in magnitude)
        _require_m190_incapacity_context(
            occupied=occupied,
            scoped_casilla=scoped_casilla,
            key=key,
            subkey=subkey,
            clave_scope=clave_scope,
        )
        _require_m190_reintegro_context(
            marker=marker,
            magnitude=magnitude,
            retention=_field_wire(wire, retention),
            filing_year=filing_year,
            devengo_year=devengo_year,
        )

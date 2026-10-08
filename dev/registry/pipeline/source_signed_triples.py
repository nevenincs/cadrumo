"""Exact M165/M280 source rows that split signed amounts into three leaves."""

from __future__ import annotations

from hashlib import sha256
from typing import Final

from cadrumo.domain.calculations.export_field_kind import CasillaFieldKind
from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.export_value_policy import ExportValuePolicy

from .joined_record_design import JoinedRecordDesignField

_PINS: Final[dict[tuple[str, str], tuple[str, str, str, tuple[tuple[str, int, int, int, str], ...]]]] = {
    ("165", "2016"): (
        "aeat-dr-165-2016-2022",
        "2f5f6dfd277c094a494d2ed8bc95c663ac24813b271a88a8f4f1a4d848b663c5",
        "importe-fondos-propios",
        (
            (
                "modelo-165-t1-importe-fondos-propios-sign",
                160,
                168,
                1,
                "2eb26e2658defeb4994e09b843aac2ce57b3c41bd9d09b73d2b52c4aef1e4a2b",
            ),
            (
                "modelo-165-t1-importe-fondos-propios-component-169",
                184,
                169,
                13,
                "c816029d3c073ec5edb932c1545af6aff16deeb40a68f594ba08a36d385638fe",
            ),
            (
                "modelo-165-t1-importe-fondos-propios-component-182",
                187,
                182,
                2,
                "4e779190dcb7dd0866e3926d62a96c3c11cc440f407c1280b8ad8fb4587b8ac0",
            ),
        ),
    ),
    ("165", "2023"): (
        "aeat-dr-165-2026",
        "bcc94b07d695703cfa66a3d8cbbb176841906ebf8cef57e2acd3e3fee452a263",
        "importe-fondos-propios",
        (
            (
                "modelo-165-t1-importe-fondos-propios-sign",
                153,
                168,
                1,
                "2eb26e2658defeb4994e09b843aac2ce57b3c41bd9d09b73d2b52c4aef1e4a2b",
            ),
            (
                "modelo-165-t1-importe-fondos-propios-component-169",
                176,
                169,
                13,
                "c816029d3c073ec5edb932c1545af6aff16deeb40a68f594ba08a36d385638fe",
            ),
            (
                "modelo-165-t1-importe-fondos-propios-component-182",
                179,
                182,
                2,
                "4e779190dcb7dd0866e3926d62a96c3c11cc440f407c1280b8ad8fb4587b8ac0",
            ),
        ),
    ),
    ("280", "2022"): (
        "aeat-dr-280-2022",
        "45cab8f0880dfc4094d6cc8905ae37efba0c10a568d49e8648e1c9a20b2a5701",
        "rendimientos-negativos-imputables",
        (
            (
                "modelo-280-t2-rendimientos-negativos-imputables-sign",
                522,
                176,
                1,
                "163a8020802be9a772375026fcbe0feb601876a05f3cac76f9b0129f475a57d7",
            ),
            (
                "modelo-280-t2-rendimientos-negativos-imputables-component-177",
                547,
                177,
                8,
                "403ace5e0f0ffae03a85ab3af16a9717bccb2e6ce7aedd73448ae7b0d636b124",
            ),
            (
                "modelo-280-t2-rendimientos-negativos-imputables-component-185",
                550,
                185,
                2,
                "ec438a7e209c32fe50a3c13a2449321e0e942c56fdf09263bce535e5fddcbb5c",
            ),
        ),
    ),
}


def signed_triple_policy_for(
    joined_field: JoinedRecordDesignField, *, modelo: str, epoch: str, source_ref: str, source_sha256: str
) -> ExportValuePolicy | None:
    """Recognise a child only under its exact PDF bytes, endpoint and geometry."""
    entry = joined_field.semantic_entry
    field_id = str(entry.export_field_id)
    if not _is_signed_triple_field(field_id):
        return None

    casilla_id, members = _reviewed_signed_triple_members(
        modelo, epoch, source_ref=source_ref, source_sha256=source_sha256
    )
    member_index, member = _reviewed_member(members, field_id)
    if not _matches_reviewed_signed_triple(joined_field, modelo, casilla_id, member):
        raise RegistryValidationError("signed triple source part, geometry or casilla differs from reviewed evidence")
    return _signed_component_policy(modelo, member_index)


def _is_signed_triple_field(field_id: str) -> bool:
    """Identify only the two source families with a reviewed signed triple."""
    return field_id.startswith(
        ("modelo-165-t1-importe-fondos-propios-", "modelo-280-t2-rendimientos-negativos-imputables-")
    )


def _reviewed_signed_triple_members(
    modelo: str, epoch: str, *, source_ref: str, source_sha256: str
) -> tuple[str, tuple[tuple[str, int, int, int, str], ...]]:
    """Require the exact reviewed source identity and return its casilla members."""
    pin = _PINS.get((modelo, epoch))
    if pin is None or (source_ref, source_sha256) != pin[:2]:
        raise RegistryValidationError("signed triple source identity is unreviewed or stale")
    return pin[2], pin[3]


def _reviewed_member(
    members: tuple[tuple[str, int, int, int, str], ...], field_id: str
) -> tuple[int, tuple[str, int, int, int, str]]:
    """Select a field only when its id is one of the three pinned members."""
    for index, member in enumerate(members):
        if field_id == member[0]:
            return index, member
    raise RegistryValidationError("signed triple source field identity is unreviewed")


def _matches_reviewed_signed_triple(
    joined_field: JoinedRecordDesignField,
    modelo: str,
    casilla_id: str,
    member: tuple[str, int, int, int, str],
) -> bool:
    """Compare the parser evidence, physical source geometry, and casilla pin."""
    field = joined_field.parser_field
    entry = joined_field.semantic_entry
    _, row, offset, length, digest = member
    material = "\x1f".join((field.normalized_description, field.content or "", field.aeat_type))
    expected_sheet = (
        "Tipo 1 - Registro De Declarante Posic  Naturaleza Descripción De Los Campos"
        if modelo == "165"
        else "Tipo 2 - Registro De Declarado"
    )
    return not (
        field.sheet != expected_sheet
        or field.record_identity != expected_sheet
        or (field.source_row, field.offset, field.length) != (row, offset, length)
        or sha256(material.encode()).hexdigest() != digest
        or entry.kind is not CasillaFieldKind.CASILLA
        or str(entry.casilla_id) != casilla_id
    )


def _signed_component_policy(modelo: str, member_index: int) -> ExportValuePolicy:
    """Map the pinned member position to its fixed signed-component policy."""
    if member_index == 0:
        return (
            ExportValuePolicy.SIGNED_COMPONENT_SIGN if modelo == "165" else ExportValuePolicy.SIGNED_COMPONENT_ZERO_SIGN
        )
    if member_index == 1:
        return ExportValuePolicy.SIGNED_COMPONENT_INTEGER_PART
    return ExportValuePolicy.SIGNED_COMPONENT_FRACTIONAL_DIGITS

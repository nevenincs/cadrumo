"""Exact source-pinned literal readings for exceptional official PDF anchors."""

from __future__ import annotations

from typing import Final

from cadrumo.domain.calculations.registry.errors import RegistryValidationError

from .joined_record_design import JoinedRecordDesignField
from .record_design_intermediate import RecordDesignIntermediateField
from .render_profile_model import RenderProfile
from .render_profile_model_base import RenderProfileDesignIdentity

_M349_PROSE_CONSTANTS: Final[dict[tuple[str, int, int, int], tuple[str, str]]] = {
    ("modelo-349-op-record-type", 229, 1, 1): ('Numérico de una posición Constante "2" (Dos)', "2"),
    ("modelo-349-op-modelo", 232, 2, 3): ('Numérico de 3 posiciones Constante "349"', "349"),
    ("modelo-349-rect-record-type", 452, 1, 1): ('Numérico de una posición Constante "2" (Dos)', "2"),
    ("modelo-349-rect-modelo", 455, 2, 3): ('Numérico de 3 posiciones Constante "349"', "349"),
}


_M190_TRANSPORT_ROWS: Final[dict[str, int]] = {"2020": 91, "2023": 98, "2024": 100, "2025": 102}


_M190_TRANSPORT_SHAS: Final[dict[str, str]] = {
    "2020": "4cefd924a7dda3ac5159582f728a72f6f162d3344b8e87f2d17900e6fdcf3b32",
    "2023": "430daf439ed645155ffc6096b65c4da5b26dd2e6c16b8e4781f9be145b3792cb",
    "2024": "20bc8086525ce850063b9ae8644b8514483e5c34f90c8e47cfadc6c52cf7390e",
    "2025": "a7d1092f78620431812354e560a5146a3ae244e0aed69d9d58c353370ba0134d",
}


def _source_pinned_341_pdf_constant(
    joined_field: JoinedRecordDesignField, render_profile: RenderProfile, official_content: str
) -> str | None:
    """Adjudicate two exact historical PDF constants with unusual print spelling."""
    entry = joined_field.semantic_entry
    decisions = {
        "modelo-341-historical-modelo": (4, "1", 1, 3, "Constante ' 341 '", "341"),
        "modelo-341-historical-tipo-declaracion": (5, "2", 4, 1, "Constante D (Reintegro compens.)", "D"),
    }
    expected = decisions.get(str(entry.export_field_id))
    if expected is None:
        return None
    if not _m341_source_identity_matches(render_profile) or not _m341_field_matches(
        joined_field,
        expected,
        official_content,
    ):
        raise RegistryValidationError("modelo 341 historical PDF constant lacks its exact source adjudication")
    return expected[5]


def _m341_source_identity_matches(render_profile: RenderProfile) -> bool:
    identity = render_profile.design_identity
    return (
        str(identity.modelo) == "341"
        and identity.design_epoch == "2005"
        and str(identity.source_ref) == "aeat-dr-341-2005-2015"
        and identity.source_sha256 == "c1c59a317be87dbb4898c017ace8f6327e9df340648808fb6d1831a0c7295c3d"
    )


def _m341_field_matches(
    joined_field: JoinedRecordDesignField,
    expected: tuple[int, str, int, int, str, str],
    official_content: str,
) -> bool:
    field = joined_field.parser_field
    return (
        field.sheet == "PDF record design"
        and field.record_identity == "PDF record design"
        and field.source_row == expected[0]
        and field.ordinal == expected[1]
        and field.source_cell is None
        and field.offset == expected[2]
        and field.length == expected[3]
        and official_content == expected[4]
        and joined_field.semantic_entry.literal == expected[5]
    )


def _source_pinned_349_constant(
    joined_field: JoinedRecordDesignField, render_profile: RenderProfile, official_content: str
) -> str | None:
    """Read four exact PDF prose constants without admitting a general prose grammar."""
    field = joined_field.parser_field
    entry = joined_field.semantic_entry
    if str(render_profile.design_identity.source_ref) != "aeat-dr-349-2020-current":
        return None
    if (
        render_profile.design_identity.source_sha256
        != "874db49c9aff4d9c024bdee52f869123a9815c09272a0066cf81421ace1a8335"
    ):
        return None
    evidence = _M349_PROSE_CONSTANTS.get((str(entry.export_field_id), field.source_row, field.offset, field.length))
    if evidence is None:
        return None
    expected_content, expected_literal = evidence
    if official_content != expected_content or entry.literal != expected_literal:
        raise RegistryValidationError("modelo 349 prose constant no longer matches its source-pinned declaration")
    return expected_literal


def _source_pinned_190_transport_constant(
    joined_field: JoinedRecordDesignField, render_profile: RenderProfile, official_content: str
) -> str | None:
    """Read the sole T code stated at four exact M190 transport rows."""
    entry = joined_field.semantic_entry
    if str(entry.export_field_id) != "modelo-190-decl-tipo-soporte":
        return None
    field = joined_field.parser_field
    identity = render_profile.design_identity
    epoch = identity.design_epoch
    if not _m190_source_identity_matches(identity, epoch) or not _m190_transport_field_matches(
        field,
        entry.literal,
        official_content,
        epoch,
    ):
        raise RegistryValidationError("modelo 190 telematic constant differs from its sole source-listed code")
    return "T"


def _m190_source_identity_matches(identity: RenderProfileDesignIdentity, epoch: str) -> bool:
    return (
        str(identity.modelo) == "190"
        and str(identity.source_ref) == f"aeat-dr-190-{epoch}"
        and identity.source_sha256 == _M190_TRANSPORT_SHAS.get(epoch)
    )


def _m190_transport_field_matches(
    field: RecordDesignIntermediateField,
    literal: str | None,
    official_content: str,
    epoch: str,
) -> bool:
    return (
        field.sheet == "Tipo 1 - Registro De Declarante"
        and field.record_identity == field.sheet
        and field.source_row == _M190_TRANSPORT_ROWS.get(epoch)
        and field.ordinal == "6"
        and (field.offset, field.length) == (58, 1)
        and official_content == "Se cumplimentará una de las siguientes claves: ‘T’: Transmisión telemática."
        and literal == "T"
    )


def _source_pinned_345_transport_constant(
    joined_field: JoinedRecordDesignField, render_profile: RenderProfile, official_content: str
) -> str | None:
    """Read M345's single printed telematic code at its exact PDF anchor."""
    entry = joined_field.semantic_entry
    if str(entry.export_field_id) != "modelo-345-t1-tipo-soporte":
        return None
    field = joined_field.parser_field
    identity = render_profile.design_identity
    if not _m345_source_identity_matches(identity) or not _m345_transport_field_matches(
        field,
        entry.literal,
        official_content,
    ):
        raise RegistryValidationError("modelo 345 telematic constant differs from its sole source-listed code")
    return "T"


def _m345_source_identity_matches(identity: RenderProfileDesignIdentity) -> bool:
    return (
        str(identity.modelo) == "345"
        and identity.design_epoch == "2025"
        and str(identity.source_ref) == "aeat-dr-345-2025"
        and identity.source_sha256 == "fb0faaf68f8b0de29316bdc65eaeb3ba0dcb8a441eea4d5415d0cb4517c287fd"
    )


def _m345_transport_field_matches(
    field: RecordDesignIntermediateField,
    literal: str | None,
    official_content: str,
) -> bool:
    return (
        field.sheet == "PDF record design"
        and field.record_identity == "PDF record design"
        and field.source_row == 55
        and field.ordinal == "6"
        and (field.offset, field.length) == (58, 1)
        and field.aeat_type == "Alfabético"
        and official_content == "Se cumplimentará la siguiente clave: 'T': Transmisión telemática."
        and literal == "T"
    )


def _source_pinned_270_transport_constant(
    joined_field: JoinedRecordDesignField, render_profile: RenderProfile, official_content: str
) -> str | None:
    """Read M270's single printed telematic code at its exact PDF anchor."""
    entry = joined_field.semantic_entry
    if str(entry.export_field_id) != "modelo-270-decl-tipo-soporte":
        return None
    field = joined_field.parser_field
    identity = render_profile.design_identity
    if not _m270_source_identity_matches(identity) or not _m270_transport_field_matches(
        field,
        entry.literal,
        official_content,
    ):
        raise RegistryValidationError("modelo 270 telematic constant differs from its sole source-listed code")
    return "T"


def _m270_source_identity_matches(identity: RenderProfileDesignIdentity) -> bool:
    return (
        str(identity.modelo) == "270"
        and identity.design_epoch == "2023"
        and str(identity.source_ref) == "aeat-dr-270-2023"
        and identity.source_sha256 == "d845cc47e3b60d01128d27dddcc3cffd2cf64bd6dfb24e0cd0d0467d66f95a92"
    )


def _m270_transport_field_matches(
    field: RecordDesignIntermediateField,
    literal: str | None,
    official_content: str,
) -> bool:
    return (
        field.sheet == "Tipo 1 - Registro De Declarante"
        and field.record_identity == field.sheet
        and field.source_row == 81
        and field.ordinal == "6"
        and (field.offset, field.length) == (58, 1)
        and field.aeat_type == "Alfabético"
        and official_content == "Se cumplimentará: “T”: transmisión telemática."
        and literal == "T"
    )


def _source_pinned_165_transport_constant(
    joined_field: JoinedRecordDesignField, render_profile: RenderProfile, official_content: str
) -> str | None:
    """Read the sole T code from M165's two exact official PDF editions."""
    entry = joined_field.semantic_entry
    if str(entry.export_field_id) != "modelo-165-t1-tipo-soporte":
        return None
    field = joined_field.parser_field
    identity = render_profile.design_identity
    pins = {
        "2016": ("aeat-dr-165-2016-2022", "2f5f6dfd277c094a494d2ed8bc95c663ac24813b271a88a8f4f1a4d848b663c5", 64),
        "2023": ("aeat-dr-165-2026", "bcc94b07d695703cfa66a3d8cbbb176841906ebf8cef57e2acd3e3fee452a263", 60),
    }
    pin = pins.get(identity.design_epoch)
    if not _m165_source_identity_matches(identity, field, pin) or not _m165_transport_field_matches(
        field,
        entry.literal,
        official_content,
    ):
        raise RegistryValidationError("modelo 165 telematic constant differs from its sole source-listed code")
    return "T"


def _m165_source_identity_matches(
    identity: RenderProfileDesignIdentity,
    field: RecordDesignIntermediateField,
    pin: tuple[str, str, int] | None,
) -> bool:
    return (
        str(identity.modelo) == "165"
        and pin is not None
        and (str(identity.source_ref), identity.source_sha256, field.source_row) == pin
    )


def _m165_transport_field_matches(
    field: RecordDesignIntermediateField,
    literal: str | None,
    official_content: str,
) -> bool:
    return (
        field.sheet == "Tipo 1 - Registro De Declarante Posic  Naturaleza Descripción De Los Campos"
        and field.record_identity == field.sheet
        and field.ordinal == "6"
        and (field.offset, field.length, field.aeat_type) == (58, 1, "Alfabético")
        and field.normalized_description == "TIPO DE SOPORTE"
        and official_content == 'Se cumplimentará: "T": Transmisión telemática'
        and literal == "T"
    )


def _source_pinned_280_transport_without_parsed_content(
    joined_field: JoinedRecordDesignField, render_profile: RenderProfile
) -> str | None:
    """Adjudicate a PDF page-break row whose following printed lines say T only.

    The parser leaves row 71's Contenido empty. The enrolled PDF's extracted
    lines 89-90 immediately after `58 TIPO DE SOPORTE` state the sole code
    `'T': Transmisión telemática.`; the exact PDF SHA anchors that reading.
    """
    entry = joined_field.semantic_entry
    if str(entry.export_field_id) != "modelo-280-t1-tipo-soporte":
        return None
    field = joined_field.parser_field
    identity = render_profile.design_identity
    if not _m280_source_identity_matches(identity) or not _m280_transport_field_matches(field, entry.literal):
        raise RegistryValidationError("modelo 280 PDF page-break transport fact differs from exact source")
    return "T"


def _m280_source_identity_matches(identity: RenderProfileDesignIdentity) -> bool:
    return (
        str(identity.modelo) == "280"
        and identity.design_epoch == "2022"
        and str(identity.source_ref) == "aeat-dr-280-2022"
        and identity.source_sha256 == "45cab8f0880dfc4094d6cc8905ae37efba0c10a568d49e8648e1c9a20b2a5701"
    )


def _m280_transport_field_matches(field: RecordDesignIntermediateField, literal: str | None) -> bool:
    return (
        field.sheet == "Tipo 1 - Registro De Declarante"
        and field.record_identity == field.sheet
        and field.source_row == 71
        and field.ordinal is None
        and (field.offset, field.length, field.aeat_type) == (58, 1, "Alfabético")
        and field.normalized_description == "TIPO DE SOPORTE"
        and field.content is None
        and literal == "T"
    )

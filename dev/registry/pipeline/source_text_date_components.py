"""Source-pinned 4+2+2 numeric dates fed by exact TEXT8 casillas."""

from __future__ import annotations

from hashlib import sha256
from typing import Final

from cadrumo.domain.calculations.export_field_kind import CasillaFieldKind
from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.export_value_policy import ExportValuePolicy

from .joined_record_design import JoinedRecordDesignField

_YEAR_165 = "7603b33a53741d0cac9355acb9d56016eff5fb3e8c197b3757dcb79f80a6a0fc"
_MONTH_165 = "41ad05d6aed438fa4dba7b25e5101da6dc27dd3a0e51ae04cde67f8db722e745"
_DAY_165 = "9baa7a7a36119a7c17522c16808d37262fab1298de38064bcb9cc5463a522b25"
_YEAR_280 = "07d53a12193696c91d20982bc3d52f4b6dc389db2a91d1cb7ea6fd528cffdd6c"
_MONTH_280 = "e31979d9f95448f3da3448d8386cf8c6647966903a13e62d62bafb58344fd9f1"
_DAY_280_OPEN = "3e9fe00ae3ba273565784488f7b337509a083464c6449b11c6da71d380558ed8"
_DAY_280_CLOSE = "86eccf1d751c6451dafbacabdabc20db8f412889deaef86dd752b4b4e8a3a539"

_PINS: Final[dict[tuple[str, str], tuple[str, str, tuple[tuple[str, str, tuple[tuple[int, int, str], ...]], ...]]]] = {
    ("165", "2016"): (
        "aeat-dr-165-2016-2022",
        "2f5f6dfd277c094a494d2ed8bc95c663ac24813b271a88a8f4f1a4d848b663c5",
        (
            (
                "modelo-165-t1-fecha-constitucion",
                "fecha-constitucion",
                ((157, 160, _YEAR_165), (158, 164, _MONTH_165), (159, 166, _DAY_165)),
            ),
            (
                "modelo-165-t2-fecha-adquisicion",
                "fecha-adquisicion",
                ((274, 89, _YEAR_165), (275, 93, _MONTH_165), (276, 95, _DAY_165)),
            ),
        ),
    ),
    ("165", "2023"): (
        "aeat-dr-165-2026",
        "bcc94b07d695703cfa66a3d8cbbb176841906ebf8cef57e2acd3e3fee452a263",
        (
            (
                "modelo-165-t1-fecha-constitucion",
                "fecha-constitucion",
                ((150, 160, _YEAR_165), (151, 164, _MONTH_165), (152, 166, _DAY_165)),
            ),
            (
                "modelo-165-t2-fecha-adquisicion",
                "fecha-adquisicion",
                ((277, 89, _YEAR_165), (278, 93, _MONTH_165), (279, 95, _DAY_165)),
            ),
        ),
    ),
    ("280", "2022"): (
        "aeat-dr-280-2022",
        "45cab8f0880dfc4094d6cc8905ae37efba0c10a568d49e8648e1c9a20b2a5701",
        (
            (
                "modelo-280-t2-fecha-apertura",
                "fecha-apertura",
                ((278, 102, _YEAR_280), (279, 106, _MONTH_280), (280, 108, _DAY_280_OPEN)),
            ),
            (
                "modelo-280-t2-fecha-extincion",
                "fecha-extincion",
                ((452, 138, _YEAR_280), (453, 142, _MONTH_280), (454, 144, _DAY_280_CLOSE)),
            ),
        ),
    ),
}

_DATE_POLICIES: Final[tuple[ExportValuePolicy, ...]] = (
    ExportValuePolicy.YYYYMMDD_TEXT_YEAR,
    ExportValuePolicy.YYYYMMDD_TEXT_MONTH,
    ExportValuePolicy.YYYYMMDD_TEXT_DAY,
)


def text_date_component_policy_for(
    joined_field: JoinedRecordDesignField, *, modelo: str, epoch: str, source_ref: str, source_sha256: str
) -> ExportValuePolicy | None:
    """Recognise only the six reviewed dates' exact source leaves and casillas."""
    field = joined_field.parser_field
    entry = joined_field.semantic_entry
    field_id = str(entry.export_field_id)
    if not (modelo in {"165", "280"} and "-fecha-" in field_id and "-component-" in field_id):
        return None
    pin = _PINS.get((modelo, epoch))
    if pin is None or (source_ref, source_sha256) != pin[:2]:
        raise RegistryValidationError("text date component source identity is unreviewed or stale")
    matched = next(
        (
            (casilla_id, index, row, offset, digest)
            for prefix, casilla_id, parts in pin[2]
            for index, (row, offset, digest) in enumerate(parts)
            if field_id == f"{prefix}-component-{offset}"
        ),
        None,
    )
    if matched is None:
        raise RegistryValidationError("text date component field identity is unreviewed")
    casilla_id, index, row, offset, digest = matched
    material = "\x1f".join((field.normalized_description, field.content or "", field.aeat_type))
    expected_sheet = (
        "Tipo 1 - Registro De Declarante Posic  Naturaleza Descripción De Los Campos"
        if modelo == "165" and "-t1-" in field_id
        else "Tipo 2 - Registro De Socios O Partícipes"
        if modelo == "165"
        else "Tipo 2 - Registro De Declarado"
    )
    if (
        field.sheet != expected_sheet
        or field.record_identity != expected_sheet
        or (field.source_row, field.offset, field.length) != (row, offset, (4, 2, 2)[index])
        or sha256(material.encode()).hexdigest() != digest
        or entry.kind is not CasillaFieldKind.CASILLA
        or str(entry.casilla_id) != casilla_id
    ):
        raise RegistryValidationError("text date component source, geometry or casilla differs from reviewed evidence")
    return _DATE_POLICIES[index]

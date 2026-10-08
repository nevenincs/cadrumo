"""Exact numeric readings of the five independently pinned M714 workbooks."""

from __future__ import annotations

from typing import Final

from cadrumo.domain.calculations.registry.errors import RegistryValidationError

from .joined_record_design import JoinedRecordDesignField
from .render_profile_model_base import RenderProfileDesignIdentity

_M714_PINS: Final[dict[str, tuple[str, str]]] = {
    "aeat-dr-714-2021": ("2021", "4c8409b0a213bc2c450428939c60eb0791fba40de70ebc82d4cb3c07c43faf4f"),
    "aeat-dr-714-2022": ("2022", "b24b9ee856a9b4ea665e61ccbbe000fd8d50e4d70d48b34b5eeacbe74778b925"),
    "aeat-dr-714-2023": ("2023", "b51178affa2a64ec2d538657136e807c11802457922f97e9333018d414c66299"),
    "aeat-dr-714-2024": ("2024", "d70ce59786aa88cc91ad67197bf7f6a6630676abe087b7d66a64a0bf74a72aa5"),
    "aeat-dr-714-2025": ("2025", "660e2ce1f4cea1405e27b4251231036e75b78aef33512afc22dec8081c7cb4d3"),
}


def m714_checkbox_for(joined_field: JoinedRecordDesignField, identity: RenderProfileDesignIdentity) -> bool:
    """Recognize the six source-pinned checkboxes, not arbitrary zero/one codes."""
    if not _reviewed_m714_source(identity):
        return False
    field = joined_field.parser_field
    anchors = {
        ("714-01 Patrimonio", 49, "A49", "44", 663, "identificacion-1"),
        ("714-01 Patrimonio", 50, "A50", "45", 664, "identificacion-2"),
        ("714-01 Patrimonio", 52, "A52", "47", 667, "identificacion-4"),
        ("714-01 Patrimonio", 57, "A57", "52", 704, "identificacion-10"),
        ("714-01 Patrimonio", 66, "A66", "61", 816, "identificacion-12"),
        ("714-Ingreso o Devolución", 20, "A20", "15", 139, "declaracion-negativa"),
    }
    return (
        field.aeat_type == "Num"
        and field.length == 1
        and field.content == '"1" o "0"'
        and field.sheet == field.record_identity
        and (
            field.record_identity,
            field.source_row,
            field.source_cell,
            field.ordinal,
            field.offset,
            str(joined_field.semantic_entry.casilla_id),
        )
        in anchors
    )


def _reviewed_m714_source(identity: RenderProfileDesignIdentity) -> bool:
    pin = _M714_PINS.get(str(identity.source_ref))
    if pin is None:
        return False
    epoch, digest = pin
    if str(identity.modelo) != "714" or identity.design_epoch != epoch or identity.source_sha256 != digest:
        raise RegistryValidationError("M714 numeric source reading is unreviewed or stale")
    return True


def m714_numeric_values_for(
    joined_field: JoinedRecordDesignField, identity: RenderProfileDesignIdentity
) -> tuple[str, ...] | None:
    """Return a printed closed domain, or an empty tuple for unscaled codes.

    COMAUTO.TXT supplies semantic membership, not an implied decimal scale.
    The two exact Num/2 rows state its code or zero; their representation is
    two right-aligned, zero-filled digits. This reading makes no claim to have
    loaded that external table. Existing typed CCAA producers retain membership
    responsibility. Every other dictionary reference still refuses normally.

    The exact C1 situation cell prints 5 twice. Its distinct alternatives are
    still precisely 0 through 5: no missing value is inferred and no arbitrary
    duplicate enumeration is admitted. The raw duplicate survives in provenance.
    """
    if not _reviewed_m714_source(identity):
        return None
    field = joined_field.parser_field
    if field.aeat_type != "Num":
        return None
    anchor = (field.record_identity, field.source_row, field.source_cell, field.ordinal, field.offset, field.length)
    if anchor == ("714-01 Patrimonio", 37, "A37", "32", 318, 2) and field.content == 'De "01" a "52"':
        return tuple(str(value) for value in range(1, 53))
    if (
        anchor
        in {
            ("714-01 Patrimonio", 51, "A51", "46", 665, 2),
            ("714-01 Patrimonio", 56, "A56", "51", 702, 2),
        }
        and field.content == "Incluido en el fichero COMAUTO.TXT,  o ceros"
        and str(joined_field.semantic_entry.casilla_id) in {"identificacion-3", "identificacion-8"}
    ):
        return ()
    if anchor == ("714-03 Patrimonio", 27, "A27", "22", 147, 1) and field.content == "0, 1 , 2, 3, 4 o 5 o 5":
        return ("0", "1", "2", "3", "4", "5")
    return None

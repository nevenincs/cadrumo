"""Slot-width validation for export fields bound to typed fixed-width sources.

The slot-semantics sibling of the byte-range overlap check in
:mod:`cadrumo.domain.calculations.registry._export`. Overlap asks whether two
fields claim the same bytes; this asks whether the bytes one field claims can
hold what that field supplies. Neither can check that a slot's MEANING matches
AEAT's published record design -- that cross-check needs the design itself --
but a width contradiction is detectable without consulting the design at all.

Split out of the export section validator rather than kept beside it because the
ruling table and its rationale are most of the volume, and the section validator
is held to a reviewability ceiling. It stays ONE authority: the export field
validator calls :func:`validate_draft_field_slot_width` on every field it
already walks, so there is no second traversal and no second dispatch.

See Also:
    :func:`cadrumo.domain.calculations.registry._validate_exports.validate_export_layout_section`
        The registry-build export validator that invokes this check per field.
"""

from __future__ import annotations

from collections.abc import Mapping

from ....core.identity import SPANISH_TAX_ID_WIDTH
from ._schema import CasillaFieldKind, ExportFieldDefinition

#: Canonical character width of every export ``draft_attribute`` whose value is
#: supplied by a typed, fixed-width domain source, keyed by the attribute token
#: :class:`~cadrumo.domain.calculations.registry.ExportFieldDefinition` declares.
#:
#: A ``None`` entry means "deliberately not width-gated", which is a different
#: claim from "not considered": the mapping is required to be TOTAL over the
#: declarable attributes, so adding an attribute without ruling on its width
#: fails validation rather than passing silently. That totality is what keeps the
#: check keyed on the property instead of on the fields that happen to exist now.
DRAFT_ATTRIBUTE_CANONICAL_WIDTHS: Mapping[str, int | None] = {
    # Every value routes through validate_spanish_tax_id, which refuses any
    # identifier that is not exactly this wide, so a slot of a different width
    # cannot be holding the declarant's own identifier. A WIDER AEAT slot at some
    # offset is the tell that the slot belongs to a different party: Modelo 200's
    # page 001B position 141 is 15 wide because it holds the foreign tax
    # identification number of a mercantile group's ultimate parent company, and
    # binding the declarant there declares the filer to be its own parent.
    "profile_tax_id": SPANISH_TAX_ID_WIDTH,
    # The remaining attributes abstain, and each abstention has its own reason
    # rather than a shared "these vary" claim. Recorded per attribute because an
    # abstention that cites the wrong reason is worse than none: it reads as a
    # ruling that the slot widths are legitimately diverse when at least one of
    # them is not.
    #
    # No declaration in the registry binds either of these, so no width is
    # observable to gate against and any value chosen here would be invented.
    "modelo": None,
    "period": None,
    # ABSTAINS OVER A KNOWN DIVERGENCE, not over legitimate variability. The
    # source is str(period.filing_year), always 4 characters, and the registry
    # binds 4 in every declaration but one: Modelo 200's page-000 envelope-open
    # record binds it to a 17-character slot. 17 is the width of the whole
    # envelope-open tag, which the sibling modelos compose from a literal "<T",
    # the modelo code, a page digit, the year, the period token and a literal
    # "0000>" -- six or seven fields, not one. That declaration is suspected
    # wrong, and gating this attribute at 4 would refuse the registry build until
    # it is restructured, which needs its own decision and its own byte-level
    # verification of the emitted tag. Until then the gate is deliberately
    # silent HERE, so the divergence must stay recorded elsewhere to be found.
    "filing_year": None,
    # Uniform at 2 across every declaration, so this one is gateable on the
    # evidence; it abstains only because the token's width has not been
    # established against the published diseños, and a period token is the axis
    # where a per-period-kind width difference would be plausible.
    "period_code": None,
}


def validate_draft_field_slot_width(
    failures: list[str],
    *,
    prefix: str,
    field: ExportFieldDefinition,
) -> None:
    """Append a failure when a draft field's slot width contradicts its typed source.

    When the attribute's source is a typed value of fixed width, a slot of some
    other width is holding a different value than the attribute yields. That is
    the shape of a real defect: Modelo 200 bound the declarant's own
    :data:`~core.identity.SubjectTaxId` into a 15-wide slot the diseño reserves
    for a group parent's foreign tax identification number, and every export
    right-padded the filer's identifier into another entity's field.

    Args:
        failures: Accumulator the caller reports; this validator never raises, so
            one build surfaces every offending field rather than the first.
        prefix: Diagnostic prefix naming the modelo and revision under validation.
        field: The
            :class:`~cadrumo.domain.calculations.registry.ExportFieldDefinition`
            to check. Non-draft fields and logical-only fields return unchecked.
    """
    if field.kind != CasillaFieldKind.DRAFT or field.draft_attribute is None:
        return
    if field.draft_attribute not in DRAFT_ATTRIBUTE_CANONICAL_WIDTHS:
        failures.append(
            f"{prefix}: export field {field.id!r} binds draft attribute {field.draft_attribute!r}, "
            "which declares no canonical-width ruling; give it a width or record it as "
            "explicitly not width-gated",
        )
        return
    canonical_width = DRAFT_ATTRIBUTE_CANONICAL_WIDTHS[field.draft_attribute]
    if canonical_width is None or field.length is None:
        return
    if field.length != canonical_width:
        failures.append(
            f"{prefix}: export field {field.id!r} binds draft attribute {field.draft_attribute!r}, "
            f"whose typed source is exactly {canonical_width} characters, to a slot of length "
            f"{field.length}; a slot of that width holds a different value than the attribute "
            "supplies, so either the slot belongs to another party or the binding is wrong",
        )

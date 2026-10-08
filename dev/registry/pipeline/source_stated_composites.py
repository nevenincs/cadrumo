"""Complete, exact source readings of signed monetary fields."""

from __future__ import annotations

from typing import Final

from cadrumo.core.hashing import sha256_hex
from cadrumo.domain.calculations.registry.errors import RegistryValidationError

from .record_design_intermediate import RecordDesignIntermediateField, RecordDesignIntermediateSource
from .render_profile_model_base import RenderProfileDesignIdentity

_M720_SOURCE_SHA256: Final[str] = "ac324b935b690f0b6fe12dc8351c324cc804170750f483b0768d6417dd4976b7"

# Sheet, ordinal, offset, complete width, whole digits, exact description/content/nature digest.
# The complete official prose declares one alphabetic blank/N sign, no comma,
# the printed whole range and two fractional digits. Detail prose also states
# the valuation meaning and explicitly forbids proration: no calculation or
# valuation rule is inferred by this representation reader.
_M720_COMPOSITES: Final[dict[int, tuple[str, str, int, int, int, str]]] = {
    161: (
        "Tipo 1 - Registro De Declarante",
        "12",
        145,
        18,
        15,
        "bf62b333e703796d0a14b9fd39d3d29ea16914d0306df8e0f5e2cd7f54b1a91e",
    ),
    196: (
        "Tipo 1 - Registro De Declarante",
        "13",
        163,
        18,
        15,
        "4c4a8125e000c8b26a082797c608d33585de251f15dea860f88b69b384ea16f5",
    ),
    720: (
        "Tipo 2 - Registro De Detalle",
        "25",
        432,
        15,
        12,
        "c1098d2f3ff12edbf4f14959f54ea8ce94dc86011a04ad2b429b85af274bb835",
    ),
    785: (
        "Tipo 2 - Registro De Detalle",
        "26",
        447,
        15,
        12,
        "0bb5f401286c706ed847e01c81794510b27d5a36474a5f3abd31967451a361f9",
    ),
}

# M194 type 2: position 157 is blank/N; 158-169 is twelve magnitude
# digits in euro cents (ten whole digits). The complete text includes the
# origin-D accrued-coupon exception and page furniture. Its valuation prose
# does not establish a general subtraction formula; this reading only admits
# the explicitly stated signed representation.
_SOURCE_READINGS: Final = {
    "aeat-dr-720": ("720", "2013", _M720_SOURCE_SHA256, _M720_COMPOSITES),
    "aeat-dr-194-2019": (
        "194",
        "2019",
        "792cd3ab3f1e94ce7afd62a6fa37710253aec7b801e3097ad27741f90a657d5a",
        {
            641: (
                "Tipo 2 - Registro De Perceptor",
                "19",
                157,
                13,
                10,
                "106ba645250037c9302a08551ce816adb0df0855f5803a6b4a61c999512be78f",
            )
        },
    ),
    "aeat-dr-194-2023": (
        "194",
        "2023",
        "83cd9a332e0016607e87332bea8c3e5d33f0b0f8373ec56f820d82414ca76a7b",
        {
            604: (
                "Tipo 2 - Registro De Perceptor",
                "19",
                157,
                13,
                10,
                "2518107164cfb91cbd6f2c2a960860e5411a1af93b4101ab1c5fd359f00e92e9",
            )
        },
    ),
    "aeat-dr-194-2024": (
        "194",
        "2024",
        "4a738a126ddb465aac236b687aa25441b7cb71ec4b0ef6ea940096a3747b2651",
        {
            605: (
                "Tipo 2 - Registro De Perceptor",
                "19",
                157,
                13,
                10,
                "617b0552e1f625ae0b01fe6554cbaf1e51e3aac0a66cd8d11ad732973bdc470a",
            )
        },
    ),
}


def source_stated_composite_anchor_keys_for(
    source: RecordDesignIntermediateSource,
) -> frozenset[tuple[str, int, str | None, str | None, str, int | None]]:
    """Require every enrolled source amount even if a profile omits its rule."""
    selected = _SOURCE_READINGS.get(str(source.source_ref))
    if selected is None:
        return frozenset[tuple[str, int, str | None, str | None, str, int | None]]()
    _modelo, epoch, digest, readings = selected
    if source.design_epoch != epoch or source.source_sha256 != digest:
        raise RegistryValidationError("signed monetary composite source reading is unreviewed or stale")
    keys: set[tuple[str, int, str | None, str | None, str, int | None]] = set()
    for row, reading in readings.items():
        sheet, ordinal, _offset, _length, _digits, _digest = reading
        keys.add((sheet, row, None, ordinal, sheet, None))
    return frozenset(keys)


def source_stated_composite_integer_digits_for(
    field: RecordDesignIntermediateField, identity: RenderProfileDesignIdentity
) -> int | None:
    """Read only complete source-pinned clauses the generic grammar cannot express.

    Exact prose, natureza, geometry and source identity must all agree. Any
    future PDF/parser change requires renewed review rather than an inferred
    reading; unrelated designs retain the canonical complete prose grammar.
    """
    selected = _SOURCE_READINGS.get(str(identity.source_ref))
    if selected is None:
        return None
    modelo, epoch, digest, readings = selected
    if str(identity.modelo) != modelo or identity.design_epoch != epoch or identity.source_sha256 != digest:
        raise RegistryValidationError("signed monetary composite source reading is unreviewed or stale")
    reading = readings.get(field.source_row)
    if reading is None:
        return None
    sheet, ordinal, offset, length, whole_digits, text_digest = reading
    anchor = (
        field.sheet,
        field.record_identity,
        field.source_cell,
        field.ordinal,
        field.offset,
        field.length,
        field.aeat_type,
        field.semantic_part_offset,
    )
    expected = (sheet, sheet, None, ordinal, offset, length, "Alfanumérico", None)
    text = "\x1f".join((field.normalized_description, field.content or "", field.aeat_type))
    if anchor != expected or sha256_hex(text.encode("utf-8")) != text_digest:
        raise RegistryValidationError("signed monetary composite source anchor or complete prose changed")
    return whole_digits

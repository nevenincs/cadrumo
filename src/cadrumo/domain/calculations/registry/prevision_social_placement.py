"""Where a Modelo 100 revision places each Modelo 345 clave and subclave of a pension contribution.

A contribution certificate states the official Modelo 345 clave and subclave of
what was paid. The Modelo 100 casilla it reaches depends on the edition, and no
official text maps one to the other: a row is admitted only where the 345
subclave wording and the Modelo 100 casilla wording name the same instrument and
payer, and each admitted row quotes both texts::

    [[revisions."2022".prevision_social_placements]]
    id = "a-01"
    clave = "A"
    subclave = "01"
    casilla_id = "0465"
    design_citation = { source_ref = "boe-modelo-345-base-order", required_text = ["..."] }
    casilla_citation = { source_ref = "aeat-dr-100-2022-dictionary", required_text = ["..."] }

A pair whose casilla fits only by analogy, or that no text places, is declared
with its refusal instead of a casilla, quoting the design text that defines it,
so the classification of every pair an edition's design defines lives here and
none is ever filed under a box by analogy. Where the casilla depends on whether
the employer contributed to the same plan, the pair takes one row per answer.

Members are hydrated and closed at the loader boundary. The rules that need the
rest of the revision -- the casilla belongs to the edition, one row per key -- are
:func:`prevision_social_placement_revision_failures`, run at registry build.
"""

from __future__ import annotations

from collections import Counter
from typing import TYPE_CHECKING, Annotated, Final, Self

from pydantic import BeforeValidator, Field, model_validator

from ....core.casilla_id import CasillaId
from ....core.errors.hierarchy import pydantic_validation_boundary
from ....core.prevision_social import (
    PrevisionSocialClave,
    PrevisionSocialPlacementRefusal,
    PrevisionSocialSubclave,
    is_defined_clave_pair,
)
from .errors import RegistryValidationError
from .schema_base import RegistryModel, SourceCitation, coerce_enum_member

if TYPE_CHECKING:
    from .schema import ModeloRevision

__all__ = [
    "DECLARABLE_REFUSALS",
    "PrevisionSocialPlacement",
    "PrevisionSocialPlacementKey",
    "placement_id",
    "prevision_social_placement_revision_failures",
]

DECLARABLE_REFUSALS: Final = frozenset(
    {PrevisionSocialPlacementRefusal.UNPLACED_CLAVE, PrevisionSocialPlacementRefusal.INDIRECT_MATCH}
)
"""The refusals a row may declare; the others depend on the record or the edition, not on a pair."""

type PrevisionSocialPlacementKey = tuple[PrevisionSocialClave, PrevisionSocialSubclave | None, bool | None]
"""The ``(clave, subclave, employer contributed to the same plan)`` one row answers."""


def placement_id(
    clave: PrevisionSocialClave,
    subclave: PrevisionSocialSubclave | None,
    employer_contributed_to_same_plan: bool | None,
) -> str:
    """Return the canonical row id of one key, the identity a successor edition inherits it by."""
    parts = [clave.value.lower()]
    if subclave is not None:
        parts.append(subclave.value)
    if employer_contributed_to_same_plan is not None:
        parts.append("employer-same-plan" if employer_contributed_to_same_plan else "no-employer-same-plan")
    return "-".join(parts)


class PrevisionSocialPlacement(RegistryModel):
    """The casilla one Modelo 345 clave and subclave reaches in an edition, or why it reaches none."""

    id: str = Field(min_length=1, max_length=64, pattern=r"^[a-m](?:-0[1-4])?(?:-(?:no-)?employer-same-plan)?$")
    clave: Annotated[PrevisionSocialClave, BeforeValidator(coerce_enum_member(PrevisionSocialClave))]
    subclave: Annotated[
        PrevisionSocialSubclave | None, BeforeValidator(coerce_enum_member(PrevisionSocialSubclave))
    ] = None
    employer_contributed_to_same_plan: bool | None = None
    """Set where the casilla depends on whether the employer contributed to the same plan; one row per answer."""
    casilla_id: CasillaId | None = None
    refusal: Annotated[
        PrevisionSocialPlacementRefusal | None,
        BeforeValidator(coerce_enum_member(PrevisionSocialPlacementRefusal)),
    ] = None
    design_citation: SourceCitation
    """The Modelo 345 design text defining the clave and subclave."""
    casilla_citation: SourceCitation | None = None
    """The Modelo 100 text naming the same instrument and payer for the casilla; required with a casilla."""

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _pair_is_defined(self) -> Self:
        if not is_defined_clave_pair(self.clave, self.subclave):
            raise RegistryValidationError(
                f"prevision social placement {self.id!r}: the Modelo 345 designs define no subclave "
                f"{self.subclave!r} under clave {self.clave.value!r}"
            )
        return self

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _id_is_the_key(self) -> Self:
        expected = placement_id(self.clave, self.subclave, self.employer_contributed_to_same_plan)
        if self.id != expected:
            raise RegistryValidationError(f"prevision social placement {self.id!r} must be named {expected!r}")
        return self

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _places_or_refuses(self) -> Self:
        if (self.casilla_id is None) == (self.refusal is None):
            raise RegistryValidationError(
                f"prevision social placement {self.id!r} names exactly one of a casilla and a refusal"
            )
        if self.refusal is not None and self.refusal not in DECLARABLE_REFUSALS:
            raise RegistryValidationError(
                f"prevision social placement {self.id!r} declares refusal {self.refusal.value!r}, "
                "which depends on the record or the edition rather than on the clave"
            )
        if self.casilla_id is not None and self.casilla_citation is None:
            raise RegistryValidationError(
                f"prevision social placement {self.id!r} places casilla {self.casilla_id!r} without "
                "quoting the Modelo 100 text that names it"
            )
        if self.casilla_citation is not None and self.casilla_citation.source_ref == self.design_citation.source_ref:
            raise RegistryValidationError(
                f"prevision social placement {self.id!r} quotes one source for both the design and the casilla"
            )
        return self

    @property
    def key(self) -> PrevisionSocialPlacementKey:
        """Return the key this row answers."""
        return (self.clave, self.subclave, self.employer_contributed_to_same_plan)


def prevision_social_placement_revision_failures(revision: ModeloRevision) -> tuple[str, ...]:
    """Return every way the revision's placements disagree with the rest of the revision.

    A placed casilla must be one of the edition's casillas; a key is declared
    once; and a pair split on the same-plan answer declares both answers and no
    unsplit row, so no record falls between them.
    """
    failures: list[str] = []
    casilla_ids = {str(casilla.id) for casilla in revision.casillas}
    for row in revision.prevision_social_placements:
        if row.casilla_id is not None and str(row.casilla_id) not in casilla_ids:
            failures.append(
                f"prevision social placement {row.id!r} places casilla {row.casilla_id!r}, "
                f"which revision {revision.id!r} does not declare"
            )
    key_counts = Counter(row.key for row in revision.prevision_social_placements)
    failures.extend(
        f"prevision social placement key {placement_id(*key)!r} is declared {count} times"
        for key, count in sorted(key_counts.items(), key=lambda item: placement_id(*item[0]))
        if count > 1
    )
    splits_by_pair: dict[tuple[PrevisionSocialClave, PrevisionSocialSubclave | None], set[bool | None]] = {}
    for clave, subclave, split in key_counts:
        splits_by_pair.setdefault((clave, subclave), set()).add(split)
    for (clave, subclave), splits in sorted(splits_by_pair.items(), key=lambda item: placement_id(*item[0], None)):
        if splits not in ({None}, {True, False}):
            failures.append(
                f"prevision social placement pair {placement_id(clave, subclave, None)!r} must declare "
                "both same-plan answers and no unsplit row"
            )
    return tuple(failures)

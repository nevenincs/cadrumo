"""An edition's authored statement that it restates a family in full.

A delta edition states only what changed and inherits the rest from its
predecessor, family by family. That inheritance is the right reading whenever
the successor's silence about a member means "unchanged". It is the wrong
reading when the official structure the successor was drawn from states the
family differently end to end: the members the successor does not repeat are
not unchanged, they are gone, and inheriting them would carry into the
successor rows nobody established for it.

A restatement declaration is the edition saying so. It names the family, the
cause, and the reason somebody wrote, and it means: this edition states this
family in full here; the merge does not inherit it on this edge. Absence cannot
carry that claim -- an edition that inherits and an edition that meant to
restate look identical from the successor's files alone -- so the claim is
authored rather than inferred from a member count or a diff.

The family is closed to :data:`INHERITED_FAMILIES`, because restating a family
the merge never inherits withdraws nothing and would read as though it did.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Final

from pydantic import BeforeValidator, Field, field_validator

from ....core.errors.hierarchy import pydantic_validation_boundary
from .errors import RegistryValidationError
from .keyed_families import (
    CASILLAS_FAMILY,
)
from .keyed_families import (
    INHERITED_FAMILIES as CANONICAL_INHERITED_FAMILIES,
)
from .keyed_families import (
    RESTATABLE_FAMILIES as CANONICAL_RESTATABLE_FAMILIES,
)
from .schema_base import RegistryModel, coerce_enum_member

__all__ = (
    "INHERITED_FAMILIES",
    "RESTATABLE_FAMILIES",
    "RestatedFamilyCause",
    "RestatedFamilyCauseField",
    "RestatedFamilyDeclaration",
)


#: Every family the predecessor merge carries forward, and so the only families
#: a successor can meaningfully decline to inherit.
#:
#: ``casillas`` inherit through the loader's own casilla pass; the rest are the
#: loader's keyed families, which inherit by member identity. The set is
#: projected from the domain-owned policy table so the authored claim and the
#: merge are closed on one vocabulary.
#:
#: A family absent here is not inherited, so it has nothing to decline; whether
#: a family is inherited is read from the policy table and never restated here,
#: because a second list of examples goes stale the moment one is enrolled.
#: Enrolling a family is an inheritance judgement made on that table, not a
#: consequence of wanting to restate it.
INHERITED_FAMILIES: Final[frozenset[str]] = CANONICAL_INHERITED_FAMILIES
RESTATABLE_FAMILIES: Final[frozenset[str]] = CANONICAL_RESTATABLE_FAMILIES


#: Inherited, but through the loader's casilla pass rather than the keyed merge,
#: which is the only pass that consults ``restated_families``. A restatement of
#: this family would validate and withdraw nothing, so it is refused until the
#: casilla pass honours the declaration.
class RestatedFamilyCause(StrEnum):
    """Why an edition states a family in full instead of inheriting it.

    One member today. ``official_structure_differs`` is the only cause that
    makes inheritance wrong rather than merely redundant: the successor's
    governing document lays the family out end to end, so the predecessor's
    unrepeated members are withdrawn by that document and not by an editorial
    choice. Spelled as an enumerated field rather than assumed, so a second,
    differently-grounded cause is an added member reviewed on its own instead of
    a reinterpretation of every reason string already written.
    """

    OFFICIAL_STRUCTURE_DIFFERS = "official_structure_differs"


RestatedFamilyCauseField = Annotated[RestatedFamilyCause, BeforeValidator(coerce_enum_member(RestatedFamilyCause))]


class RestatedFamilyDeclaration(RegistryModel):
    """One family this edition states in full, with its cause and authored reason."""

    family: str = Field(min_length=1)
    cause: RestatedFamilyCauseField
    reason: str = Field(min_length=1, max_length=1024)

    @field_validator("family")
    @classmethod
    @pydantic_validation_boundary
    def _family_is_inherited(cls, value: str) -> str:
        """Refuse a family the merge never inherits, typo or otherwise.

        Closed here rather than at the revision, because the answer does not
        depend on the edition: a name outside the merge vocabulary declines
        nothing on any edge, and reading as though it declined something is the
        whole hazard.
        """
        if value not in INHERITED_FAMILIES:
            raise RegistryValidationError(
                f"restated family {value!r} is not inherited along a predecessor chain, so this edition "
                f"declines nothing by restating it; inherited families are {sorted(INHERITED_FAMILIES)!r}",
            )
        if value not in RESTATABLE_FAMILIES:
            if value == CASILLAS_FAMILY:
                raise RegistryValidationError(
                    "restated family 'casillas' is not honoured: casillas inherit through the loader's own casilla "
                    "pass, which does not read restated_families, so the declaration would validate while the merge "
                    "still inherits and reorders the rows; keep casillas out of restated_families until the casilla "
                    "pass honours it",
                )
            raise RegistryValidationError(
                f"restated family {value!r} is not eligible for a keyed restatement declaration",
            )
        return value

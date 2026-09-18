"""An edition's authored statement that it takes none of a family from its predecessor.

A delta edition inherits what it does not restate, family by family. Two
declarations decline that, and they decline different amounts. A restatement
says "I state this family in full here"; the members are the successor's own
and the predecessor's are simply not consulted. A clearance says the stronger
thing: this edition has NONE of this family, and the predecessor's members do
not carry into it.

The clearance is the stronger claim and so needs at least as much behind it.
It names the family, the cause, and the reason somebody wrote. Absence cannot
carry it: an edition that inherits and an edition that meant to take nothing
look identical from the successor's files alone, which is precisely why the
loader refuses an undecided scoped family rather than resolving it.

The cause matters more here than it does for a restatement, because two very
different situations empty a family and only one of them is a statement about
the law. Recording which one keeps an unfinished surface from reading as a
legal withdrawal.

The family is closed to :data:`CLEARABLE_FAMILIES`: a clearance is applied by
the keyed merge, so naming a family that merge never carries declines nothing
while reading as though it did.
"""

from __future__ import annotations

from collections.abc import Iterable
from enum import StrEnum
from typing import Annotated, Final, cast

from pydantic import BeforeValidator, Field, field_validator

from ....core.errors.hierarchy import pydantic_validation_boundary
from ....core.type_guards import is_object_mapping
from .errors import RegistryValidationError
from .keyed_families import CASILLAS_FAMILY
from .keyed_families import KEYED_FAMILY_SPECS as _CANONICAL_KEYED_FAMILY_SPECS
from .schema_base import RegistryModel, coerce_enum_member

__all__ = (
    "CLEARABLE_FAMILIES",
    "ClearedFamilyCause",
    "ClearedFamilyCauseField",
    "ClearedFamilyDeclaration",
    "cleared_family_names",
)


#: Every family the keyed merge carries by member identity, and so the only
#: families a clearance can empty.
#:
#: ``casillas`` inherit through the loader's own casilla pass, which does not
#: read this declaration; a clearance naming them would validate while the merge
#: still carried every row. The set is projected from the domain-owned policy
#: table so the authored claim and the merge stay closed on one vocabulary.
CLEARABLE_FAMILIES: Final[frozenset[str]] = frozenset(spec.section for spec in _CANONICAL_KEYED_FAMILY_SPECS)


def cleared_family_names(declarations: object) -> frozenset[str]:
    """Return the families a ``cleared_families`` value withdraws.

    Compilation, the delta signal and the migration assessment all need the
    same answer from the same value, and they hold it at different stages: the
    loader sees raw TOML tables, later consumers may hold typed declarations.
    Reading both shapes here keeps one answer rather than a membership test per
    consumer, which is how a bare-string reading survived in three places at
    once.

    Nothing is validated. An entry that is neither shape, or one naming no
    family, contributes nothing and is refused by
    :class:`ClearedFamilyDeclaration` itself, so a reading that recognises
    nothing declines nothing and lets the edition be refused with the schema's
    error rather than a consumer's.
    """
    if isinstance(declarations, str) or not isinstance(declarations, Iterable):
        return frozenset[str]()
    entries = cast("Iterable[object]", declarations)
    names: set[str] = set()
    for declaration in entries:
        family = declaration.get("family") if is_object_mapping(declaration) else getattr(declaration, "family", None)
        if isinstance(family, str):
            names.add(family)
    return frozenset(names)


class ClearedFamilyCause(StrEnum):
    """Why an edition takes none of a family from its predecessor.

    The two members are not degrees of the same thing. One is a claim about the
    governing document, the other is a claim about this repository's authoring
    state, and collapsing them would let unfinished work read as law.
    """

    #: The document governing this edition no longer lays the family out: the
    #: predecessor's members are withdrawn BY that document, so carrying them
    #: would assert a structure the edition's own authority contradicts.
    OFFICIAL_STRUCTURE_WITHDRAWS = "official_structure_withdraws"
    #: Nobody has authored this edition's own members yet, and the
    #: predecessor's are not adopted in their place. This is an acknowledged
    #: capability gap, not a legal statement: it says the registry has nothing
    #: here, and says it where a reader and a coverage report can both see it.
    #: A family genuinely outside the modelo's legal requirements is a family
    #: disposition instead, which is a claim about the law and is validated
    #: against the predecessor chain as one.
    NOT_AUTHORED_FOR_THIS_EDITION = "not_authored_for_this_edition"


ClearedFamilyCauseField = Annotated[ClearedFamilyCause, BeforeValidator(coerce_enum_member(ClearedFamilyCause))]


class ClearedFamilyDeclaration(RegistryModel):
    """One family this edition takes none of, with its cause and authored reason."""

    family: str = Field(min_length=1)
    cause: ClearedFamilyCauseField
    reason: str = Field(min_length=1, max_length=1024)

    @field_validator("family")
    @classmethod
    @pydantic_validation_boundary
    def _family_is_clearable(cls, value: str) -> str:
        """Refuse a family the keyed merge never carries, typo or otherwise.

        Closed here rather than at the revision, because the answer does not
        depend on the edition: a name outside the merge vocabulary empties
        nothing on any edge, and reading as though it emptied something is the
        whole hazard.
        """
        if value in CLEARABLE_FAMILIES:
            return value
        if value == CASILLAS_FAMILY:
            raise RegistryValidationError(
                "cleared family 'casillas' is not honoured: casillas inherit through the loader's own casilla "
                "pass, which does not read cleared_families, so the declaration would validate while the merge "
                "still carried every row; withdraw casillas through their continuity evolutions instead",
            )
        raise RegistryValidationError(
            f"cleared family {value!r} is not carried by the keyed predecessor merge, so this edition empties "
            f"nothing by clearing it; clearable families are {sorted(CLEARABLE_FAMILIES)!r}",
        )

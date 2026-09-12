"""The first filing year a modelo answers for, and why it answers no earlier.

A modelo with no revision for a requested year gives no reason for the absence,
and two opposite situations produce that same silence: the modelo did not exist
yet, or it existed and nobody has authored the edition. The first is the product
declaring its scope; the second is debt. Refusing both identically is correct;
reporting both identically is not, because only one of them is work.

Nothing derives this from the corpus. The earliest authored revision is the same
in both cases, which is exactly why it cannot be the evidence. Grounding a
modelo's inception is an authoring act, and this declaration is where the author
records which of the two situations holds.

The two arms mirror the ``predecessor`` mechanism in
:mod:`~cadrumo.domain.calculations.registry.revision_contracts`: a positive
claim, or a single grounding table stating what absence cannot say.

    inception = { filing_year = 2023, legal_refs = ["orden-hfp-886-2023:art-1"] }
    inception = { unauthored = { earliest_authored = 2025, reason = "..." } }

Both refuse a request below them. Neither permits a later edition to be carried
backwards into a year the modelo did not answer for: applying a design to a
period that predates it is wrong as law whether or not anybody has noticed.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Annotated, Final

from pydantic import (
    BeforeValidator,
    Discriminator,
    Field,
    SerializerFunctionWrapHandler,
    Tag,
    model_serializer,
)

from ....core.filing_year import FilingYear
from .errors import RegistryValidationError
from .ids import LegalRefId, SourceRefId
from .schema_base import LegalRefs, RegistryModel

__all__ = (
    "DeclaredInception",
    "ModeloInceptionField",
    "UnauthoredBefore",
)

_UNAUTHORED_KEY: Final = "unauthored"
_DECLARED_INCEPTION_TAG: Final = "declared"
_INCEPTION_KIND_REFUSAL: Final = (
    "inception must declare a filing_year with the authority that created the modelo, "
    "or a single 'unauthored' table stating that earlier years exist in law and are not "
    "yet authored"
)


class DeclaredInception(RegistryModel):
    """The modelo began here in law; earlier years are outside the product's reach.

    A refusal below this year is final and carries no worklist entry: nothing is
    owed for a year in which the modelo did not exist. ``legal_refs`` names the
    authority that created it, because a claim about when a modelo began is a
    claim about law and cannot rest on the corpus's own shape.
    """

    filing_year: FilingYear
    legal_refs: LegalRefs
    source_refs: tuple[SourceRefId, ...] = ()


class UnauthoredBefore(RegistryModel):
    """The modelo existed earlier; those editions are simply not authored yet.

    A refusal below ``earliest_authored`` is equally final, and equally a
    refusal, but it stays on the worklist. This is the arm that keeps a gap
    visible as debt instead of letting it read as scope.
    """

    earliest_authored: FilingYear
    reason: str = Field(min_length=1, max_length=1024)
    legal_refs: tuple[LegalRefId, ...] = ()
    source_refs: tuple[SourceRefId, ...] = ()

    @model_serializer(mode="wrap")
    def _serialise_as_authored(self, handler: SerializerFunctionWrapHandler) -> dict[str, object]:
        return {_UNAUTHORED_KEY: handler(self)}


def _inception_declaration_kind(value: object) -> str | None:
    """Tag a normalised declaration by the field that identifies its arm."""
    if isinstance(value, DeclaredInception):
        return _DECLARED_INCEPTION_TAG
    if isinstance(value, UnauthoredBefore):
        return _UNAUTHORED_KEY
    if isinstance(value, Mapping):
        if "earliest_authored" in value:
            return _UNAUTHORED_KEY
        if "filing_year" in value:
            return _DECLARED_INCEPTION_TAG
    return None


def _normalise_inception(value: object) -> object:
    """Unwrap the authored ``unauthored`` table and refuse every other shape.

    Unwrapping happens before discrimination rather than inside a union member:
    the discriminator has to see the payload's own fields, and a validator
    attached to one arm runs too late for that.
    """
    if value is None:
        return value
    if isinstance(value, Mapping) and set(value) == {_UNAUTHORED_KEY}:
        value = value[_UNAUTHORED_KEY]
    if _inception_declaration_kind(value) is None:
        raise RegistryValidationError(_INCEPTION_KIND_REFUSAL)
    return value


ModeloInceptionField = Annotated[
    Annotated[DeclaredInception, Tag(_DECLARED_INCEPTION_TAG)] | Annotated[UnauthoredBefore, Tag(_UNAUTHORED_KEY)],
    Discriminator(_inception_declaration_kind),
    BeforeValidator(_normalise_inception),
]
"""A modelo's declared first answerable filing year, in either of its two arms."""

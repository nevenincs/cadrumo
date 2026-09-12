"""Authored retirement and replacement of identifier-keyed declarations across editions.

A family whose members carry a stable, edition-free identifier inherits across editions:
an unmentioned member is inherited, a restated member supersedes in place, and a
withdrawal must be declared. This module is the declaration shape for that withdrawal,
shared by every identifier-keyed family. A ``retired`` evolution ends the chain at the
withdrawing edition; a ``replaced`` evolution ends it and names the successor identifier.
Omission is never a withdrawal.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Literal

from pydantic import Field, model_validator

from .errors import RegistryValidationError
from .ids import RevisionId
from .schema_base import LegalRefs, RegistryModel, SourceRefs

__all__ = [
    "IdentifierEvolution",
    "IdentifierEvolutionKind",
    "ReplacedIdentifierEvolution",
    "RetiredIdentifierEvolution",
]

DeclarationIdentifier = Annotated[str, Field(min_length=1, max_length=128)]
FamilyName = Annotated[str, Field(min_length=1, max_length=64, pattern=r"^[a-z][a-z0-9_]*$")]


class IdentifierEvolutionKind(StrEnum):
    """How an identifier-keyed declaration leaves the inheritance chain."""

    RETIRED = "retired"
    REPLACED = "replaced"


class RetiredIdentifierEvolution(RegistryModel):
    """The declaration named by ``identifier`` is withdrawn from ``to_revision`` onward."""

    kind: Literal["retired"] = "retired"
    family: FamilyName
    identifier: DeclarationIdentifier
    to_revision: RevisionId
    legal_refs: LegalRefs
    source_refs: SourceRefs


class ReplacedIdentifierEvolution(RegistryModel):
    """The declaration named by ``identifier`` is superseded by ``replaced_by`` from ``to_revision``."""

    kind: Literal["replaced"] = "replaced"
    family: FamilyName
    identifier: DeclarationIdentifier
    replaced_by: DeclarationIdentifier
    to_revision: RevisionId
    legal_refs: LegalRefs
    source_refs: SourceRefs

    @model_validator(mode="after")
    def _validate_distinct_identifiers(self) -> ReplacedIdentifierEvolution:
        if self.identifier == self.replaced_by:
            raise RegistryValidationError(
                f"identifier evolution {self.identifier!r} cannot be replaced by itself",
            )
        return self


IdentifierEvolution = Annotated[
    RetiredIdentifierEvolution | ReplacedIdentifierEvolution,
    Field(discriminator="kind"),
]
"""Closed union of authored chain-ending statements for one identifier-keyed family."""

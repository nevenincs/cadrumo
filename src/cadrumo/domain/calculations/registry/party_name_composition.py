"""The composition rule a record design states for a party-name field.

AEAT designs give a declarado, operador or perceptor one fixed-width name field
and prescribe how it is filled: for a natural person "el primer apellido, un
espacio, el segundo apellido, un espacio y el nombre completo, necesariamente en
este mismo orden", for an entity "la razón social o la denominación completa de
la entidad". The order and the separator are that design's own rule, so they are
carried on the export field the design defines, reviewed against the design's
text when the layout is generated, and read from the hydrated layout at export.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated

from pydantic import BeforeValidator, Field, model_validator

from ....core.errors.hierarchy import pydantic_validation_boundary
from .errors import RegistryValidationError
from .schema_base import RegistryModel, coerce_enum_member


class PartyNameComponent(StrEnum):
    """A part of a stated party name the design names."""

    PRIMER_APELLIDO = "primer_apellido"
    SEGUNDO_APELLIDO = "segundo_apellido"
    NOMBRE = "nombre"
    RAZON_SOCIAL = "razon_social"


PartyNameComponentField = Annotated[PartyNameComponent, BeforeValidator(coerce_enum_member(PartyNameComponent))]

#: The parts a design names for a natural person; the design orders them.
NATURAL_PERSON_COMPONENTS: frozenset[PartyNameComponent] = frozenset(
    {PartyNameComponent.PRIMER_APELLIDO, PartyNameComponent.SEGUNDO_APELLIDO, PartyNameComponent.NOMBRE},
)


class PartyNameComposition(RegistryModel):
    """How one party-name field is composed from the parts the operator stated.

    Attributes:
        natural_person: The natural-person parts in the order the design states.
        separator: What the design puts between two parts ("un espacio").
        entity: The entity parts; a design asks for the razón social alone.
    """

    natural_person: tuple[PartyNameComponentField, ...] = Field(min_length=1)
    separator: str = Field(min_length=1)
    entity: tuple[PartyNameComponentField, ...] = Field(min_length=1)

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _parts_belong_to_their_branch(self) -> PartyNameComposition:
        if len(set(self.natural_person)) != len(self.natural_person) or set(self.natural_person) != (
            NATURAL_PERSON_COMPONENTS
        ):
            raise RegistryValidationError(
                "a natural-person party name composes primer_apellido, segundo_apellido and nombre, each once",
            )
        if self.entity != (PartyNameComponent.RAZON_SOCIAL,):
            raise RegistryValidationError("an entity party name is its razon_social alone")
        return self


__all__ = [
    "NATURAL_PERSON_COMPONENTS",
    "PartyNameComponent",
    "PartyNameComposition",
]

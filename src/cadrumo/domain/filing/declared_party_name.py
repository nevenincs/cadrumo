"""The operator-declared filing name of a party named in an informative return.

AEAT record designs give a third party's name one fixed-width field and prescribe
its content: for a natural person "el primer apellido, un espacio, el segundo
apellido, un espacio y el nombre completo, necesariamente en este mismo orden";
for an entity "la razón social o la denominación completa de la entidad, sin
anagramas". No design gives a rule for shortening it. The operator therefore
states the name in the parts the design names, and states any shorter rendering
for a narrower field themselves; the application never derives, splits,
reorders, abbreviates or truncates it. The order and separators belong to the
registry layout of each design, not to this module.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field, field_validator, model_validator

from ...core.models import STRICT_FROZEN_CONFIG


class DeclaredPartyKind(StrEnum):
    """Which branch of the design's name rule a party falls under."""

    NATURAL_PERSON = "natural_person"
    ENTITY = "entity"


def _stated_text(value: str | None) -> str | None:
    if value is None:
        return None
    if value != value.strip() or not value or "  " in value:
        raise ValueError("a stated name part is written without leading, trailing or doubled spaces")
    if any(not character.isprintable() for character in value):
        raise ValueError("a stated name part holds printable characters only")
    return value


class DeclaredPartyNameRendering(BaseModel):
    """A shorter rendering the operator states for a field narrower than the full name.

    It is the operator's own words for one width, never produced by the
    application. A field uses it only when the full name does not fit and the
    rendering does.
    """

    model_config = STRICT_FROZEN_CONFIG

    width: int = Field(gt=0)
    text: str = Field(min_length=1)

    @field_validator("text")
    @classmethod
    def _text_is_stated(cls, value: str) -> str:
        _stated_text(value)
        return value

    @model_validator(mode="after")
    def _fits_its_width(self) -> DeclaredPartyNameRendering:
        if len(self.text) > self.width:
            raise ValueError("a rendering is stated for a width it fits")
        return self


class DeclaredPartyFilingName(BaseModel):
    """The name a party is filed under, in the parts the record designs name.

    Attributes:
        kind: Natural person or entity; decides which parts are stated.
        primer_apellido: A natural person's first surname.
        segundo_apellido: A natural person's second surname. ``None`` only
            together with ``no_second_surname``; a blank is never read as absence.
        no_second_surname: The operator's explicit statement that the person has
            one surname. No design states how to compose the field then, so an
            export refuses such a name until an official source grounds it.
        nombre: A natural person's full given name.
        razon_social: An entity's complete razón social or denominación.
        renderings: Shorter renderings the operator stated, one per width.
    """

    model_config = STRICT_FROZEN_CONFIG

    kind: DeclaredPartyKind
    primer_apellido: str | None = None
    segundo_apellido: str | None = None
    no_second_surname: bool = False
    nombre: str | None = None
    razon_social: str | None = None
    renderings: tuple[DeclaredPartyNameRendering, ...] = ()

    @field_validator("primer_apellido", "segundo_apellido", "nombre", "razon_social")
    @classmethod
    def _parts_are_stated(cls, value: str | None) -> str | None:
        return _stated_text(value)

    @model_validator(mode="after")
    def _parts_match_kind(self) -> DeclaredPartyFilingName:
        if self.kind is DeclaredPartyKind.ENTITY:
            self._require_entity_parts()
        else:
            self._require_natural_person_parts()
        widths = [rendering.width for rendering in self.renderings]
        if len(widths) != len(set(widths)):
            raise ValueError("one rendering per width")
        return self

    def _require_entity_parts(self) -> None:
        """An entity files its razón social alone."""
        if self.razon_social is None:
            raise ValueError("an entity states its razón social")
        if any(part is not None for part in (self.primer_apellido, self.segundo_apellido, self.nombre)):
            raise ValueError("an entity states no surnames or given name")
        if self.no_second_surname:
            raise ValueError("an entity states no surnames")

    def _require_natural_person_parts(self) -> None:
        """A natural person files surnames and a given name, never a razón social."""
        if self.razon_social is not None:
            raise ValueError("a natural person states no razón social")
        if self.primer_apellido is None or self.nombre is None:
            raise ValueError("a natural person states the first surname and the given name")
        if (self.segundo_apellido is None) != self.no_second_surname:
            raise ValueError("a natural person states a second surname or that there is none")


__all__ = [
    "DeclaredPartyFilingName",
    "DeclaredPartyKind",
    "DeclaredPartyNameRendering",
]

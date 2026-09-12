"""Which tax a taxpayer pays, and — for a legal entity — under which form.

:class:`EntityType` is the axis that selects the tax itself: IRPF for a
persona física, Impuesto sobre Sociedades for a legal entity, and the
régimen de atribución de rentas for an entity without legal personality.
The tax then selects the modelos, the calendar, and the rate schedule.

The pair lives in a module of its own, and deliberately not beside the
deadline records that first needed it: every Impuesto sobre Sociedades
surface reads this axis, so a home under the taxpayer package keeps that
dependency honest. Following :mod:`domain.contribuyente.ccaa`, the module
carries no import-time chain of its own, so a caller may reference the
token types without pulling in the rest of the package.
"""

from __future__ import annotations

from datetime import date
from typing import Self

from pydantic import GetCoreSchemaHandler
from pydantic_core import CoreSchema, core_schema

from ...core.errors.hierarchy import CoreValidationError


class EntityType(str):
    """Opaque taxpayer entity-type token projected from the facts registry."""

    __slots__ = ()

    def __new__(cls, value: str, *, _registry_validated: bool = False) -> Self:
        if not _registry_validated:
            raise TypeError("EntityType tokens must be projected from the facts registry")
        if not isinstance(value, str) or not value:
            raise ValueError("EntityType token must be a non-empty string")
        return str.__new__(cls, value)

    @classmethod
    def _from_registry(cls, value: str) -> Self:
        return cls(value, _registry_validated=True)

    @classmethod
    def _require_registry_token(cls, value: object) -> Self:
        if isinstance(value, cls):
            return value
        raise CoreValidationError("EntityType must be a registry-projected token")

    @classmethod
    def __get_pydantic_core_schema__(
        cls,
        _source_type: object,
        _handler: GetCoreSchemaHandler,
    ) -> CoreSchema:
        return core_schema.no_info_plain_validator_function(
            cls._require_registry_token,
            json_schema_input_schema=core_schema.str_schema(),
            serialization=core_schema.to_string_ser_schema(),
        )

    @property
    def value(self) -> str:
        return str(self)

    @property
    def name(self) -> str:
        return str(self)


def require_entity_type(value: object, *, effective_date: date | None = None) -> EntityType:
    """Resolve an entity-type token through the dated facts authority."""
    from ..calculations.registry.entity_type import require_entity_type as _require

    return _require(value, effective_date=effective_date)


def require_legal_entity_form(value: object, *, effective_date: date | None = None) -> LegalEntityForm:
    """Resolve a legal-form token through the dated facts authority."""
    from ..calculations.registry.entity_type import require_legal_entity_form as _require

    return _require(value, effective_date=effective_date)


def entity_type_tokens(*, effective_date: date | None = None) -> tuple[EntityType, ...]:
    """Return the ordered registry-declared entity-type choices."""
    from ..calculations.registry.entity_type import entity_type_tokens as _tokens

    return _tokens(effective_date=effective_date)


def legal_entity_form_tokens(*, effective_date: date | None = None) -> tuple[LegalEntityForm, ...]:
    """Return the ordered registry-declared legal-form choices."""
    from ..calculations.registry.entity_type import legal_entity_form_tokens as _tokens

    return _tokens(effective_date=effective_date)


def entity_type_natural_person_token(*, effective_date: date | None = None) -> EntityType:
    from ..calculations.registry.entity_type import entity_type_natural_person_token as _token

    return _token(effective_date=effective_date)


def entity_type_legal_entity_token(*, effective_date: date | None = None) -> EntityType:
    from ..calculations.registry.entity_type import entity_type_legal_entity_token as _token

    return _token(effective_date=effective_date)


def entity_type_attribution_entity_token(*, effective_date: date | None = None) -> EntityType:
    from ..calculations.registry.entity_type import entity_type_attribution_entity_token as _token

    return _token(effective_date=effective_date)


def legal_entity_form_sin_fines_lucrativos_token(*, effective_date: date | None = None) -> LegalEntityForm:
    from ..calculations.registry.entity_type import legal_entity_form_sin_fines_lucrativos_token as _token

    return _token(effective_date=effective_date)


class LegalEntityForm(str):
    """The recognised legal form of an Impuesto sobre Sociedades entity.

    Only meaningful when :class:`EntityType` is ``LEGAL_ENTITY``; the
    sub-form drives the IS rate schedule (LIS Art. 29). Grounded in the
    AEAT distinction between sociedades civiles and comunidades de
    bienes and the project registry ``legal/is.toml``.

    The selected vocabulary and each form's legal semantics are owned by the
    dated taxpayer entity fact; this type deliberately carries no member list.
    """

    __slots__ = ()

    def __new__(cls, value: str, *, _registry_validated: bool = False) -> Self:
        if not _registry_validated:
            raise TypeError("LegalEntityForm tokens must be projected from the facts registry")
        if not isinstance(value, str) or not value:
            raise ValueError("LegalEntityForm token must be a non-empty string")
        return str.__new__(cls, value)

    @classmethod
    def _from_registry(cls, value: str) -> Self:
        return cls(value, _registry_validated=True)

    @classmethod
    def _require_registry_token(cls, value: object) -> Self:
        if isinstance(value, cls):
            return value
        raise CoreValidationError("LegalEntityForm must be a registry-projected token")

    @classmethod
    def __get_pydantic_core_schema__(
        cls,
        _source_type: object,
        _handler: GetCoreSchemaHandler,
    ) -> CoreSchema:
        return core_schema.no_info_plain_validator_function(
            cls._require_registry_token,
            json_schema_input_schema=core_schema.str_schema(),
            serialization=core_schema.to_string_ser_schema(),
        )

    @property
    def value(self) -> str:
        return str(self)

    @property
    def name(self) -> str:
        return str(self)

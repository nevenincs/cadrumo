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

from ...core.registry_token import StrictRegistryToken


class EntityType(StrictRegistryToken):
    """Opaque taxpayer entity-type token projected from the facts registry."""

    __slots__ = ()


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


def legal_entity_form_choice_description_tokens(*, effective_date: date | None = None) -> tuple[LegalEntityForm, ...]:
    """Return legal-form choices whose registry metadata enables choice copy."""
    from ..calculations.registry.entity_type import (
        legal_entity_form_choice_description_tokens as _tokens,
    )

    return _tokens(effective_date=effective_date)


def entity_type_natural_person_token(*, effective_date: date | None = None) -> EntityType:
    """Return the registry-declared natural-person entity token."""
    from ..calculations.registry.entity_type import entity_type_natural_person_token as _token

    return _token(effective_date=effective_date)


def entity_type_legal_entity_token(*, effective_date: date | None = None) -> EntityType:
    """Return the registry-declared legal-entity token."""
    from ..calculations.registry.entity_type import entity_type_legal_entity_token as _token

    return _token(effective_date=effective_date)


def entity_type_attribution_entity_token(*, effective_date: date | None = None) -> EntityType:
    """Return the registry-declared attribution-entity token."""
    from ..calculations.registry.entity_type import entity_type_attribution_entity_token as _token

    return _token(effective_date=effective_date)


def legal_entity_form_sin_fines_lucrativos_token(*, effective_date: date | None = None) -> LegalEntityForm:
    """Return the registry-declared non-profit legal-form token."""
    from ..calculations.registry.entity_type import legal_entity_form_sin_fines_lucrativos_token as _token

    return _token(effective_date=effective_date)


class LegalEntityForm(StrictRegistryToken):
    """The recognised legal form of an Impuesto sobre Sociedades entity.

    Only meaningful when :class:`EntityType` is ``LEGAL_ENTITY``; the
    sub-form drives the IS rate schedule (LIS Art. 29). Grounded in the
    AEAT distinction between sociedades civiles and comunidades de
    bienes and the project registry ``legal/is.toml``.

    The selected vocabulary and each form's legal semantics are owned by the
    dated taxpayer entity fact; this type deliberately carries no member list.
    """

    __slots__ = ()

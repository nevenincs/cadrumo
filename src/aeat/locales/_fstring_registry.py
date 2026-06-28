"""Explicit registration surface for bounded f-string locale key patterns.

The locale scaffold's AST scanner emits namespace markers for f-string
``tr()`` call sites (e.g. ``wizard.setup.*``) but cannot enumerate the
concrete keys those sites produce at runtime. This module declares every
bounded f-string pattern whose value space is fully known at import time
so the scaffold can expand them into concrete placeholder entries.

Every f-string ``tr()`` call site with a known enumeration source must be
registered here as a :class:`FStringKeyRegistration`. Open-ended patterns
(e.g. ``profile.keys.{profile_key}`` or ``sheets.detalle.headers.{row_field}``)
remain namespace-marker only because their value spaces are not bounded at
import time.

Adding a new enum value without updating the matching registration here
will cause scaffold to omit the required locale entries, which the
registration coverage test will surface immediately. The expanded key set
is exposed through :func:`get_registered_keys` for :class:`LocaleManager`
scaffold and parity checks.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class FStringKeyRegistration:
    """A bounded f-string locale key pattern with its enumeration source.

    ``description`` is used only in error and diagnostic messages.
    ``key_factory`` maps a single string value from ``values`` to the
    dotted locale key that the runtime will pass to ``tr()``.
    ``values`` is the complete bounded value set.
    """

    description: str
    key_factory: Callable[[str], str]
    values: tuple[str, ...]


def _hyphen(v: str) -> str:
    """Replace underscores with hyphens — the transform used by wizard choice labels."""
    return v.replace("_", "-")


# The service-capability CONFIRM question ids (hyphenated, matching the catalogue
# question ids in :mod:`aeat.application.wizard._catalogue`). Their prompt and
# CLI-flag-help keys are f-string-built, so they are enumerated here for scaffold.
_CAPABILITY_QUESTION_IDS: tuple[str, ...] = (
    "cloud-evidence-upload",
    "llm-vision",
    "google-export",
)


def _build_registrations() -> tuple[FStringKeyRegistration, ...]:
    """Construct the registration tuple at import time.

    Imports are deferred into this function so the module-level surface
    stays import-error-safe. If a domain import fails, ``get_registered_keys``
    will propagate the error with full context rather than a silent empty set.
    """
    from ..application.wizard import WIZARD_FLOWS
    from ..core.i18n import SUPPORTED_OUTPUT_LANGUAGES
    from ..domain.contribuyente._ccaa import CCAA
    from ..domain.deadlines._models import (
        EntityType,
        FiscalResidency,
        IrpfEstimationRegime,
        IrpfIncomeCategory,
        IrpfSpecialRegime,
        LegalEntityForm,
    )

    return (
        FStringKeyRegistration(
            description="wizard.setup.taxpayer-type.entity-type.choices.*.label",
            key_factory=lambda v: f"wizard.setup.taxpayer-type.entity-type.choices.{_hyphen(v)}.label",
            values=tuple(m.value for m in EntityType),
        ),
        FStringKeyRegistration(
            description="wizard.setup.taxpayer-type.legal-entity-form.choices.*.label",
            key_factory=lambda v: f"wizard.setup.taxpayer-type.legal-entity-form.choices.{_hyphen(v)}.label",
            values=tuple(m.value for m in LegalEntityForm),
        ),
        FStringKeyRegistration(
            description="wizard.setup.taxpayer-type.irpf-income-categories.choices.*.label",
            key_factory=lambda v: f"wizard.setup.taxpayer-type.irpf-income-categories.choices.{_hyphen(v)}.label",
            values=tuple(m.value for m in IrpfIncomeCategory),
        ),
        FStringKeyRegistration(
            description="wizard.setup.obligations.irpf-estimation-regime.choices.*.label",
            key_factory=lambda v: f"wizard.setup.obligations.irpf-estimation-regime.choices.{_hyphen(v)}.label",
            values=tuple(m.value for m in IrpfEstimationRegime),
        ),
        FStringKeyRegistration(
            description="wizard.setup.obligations.irpf-special-regime.choices.*.label",
            key_factory=lambda v: f"wizard.setup.obligations.irpf-special-regime.choices.{_hyphen(v)}.label",
            values=tuple(m.value for m in IrpfSpecialRegime),
        ),
        FStringKeyRegistration(
            description="wizard.setup.residence.fiscal-residency.choices.*.label",
            key_factory=lambda v: f"wizard.setup.residence.fiscal-residency.choices.{_hyphen(v)}.label",
            values=tuple(m.value for m in FiscalResidency),
        ),
        FStringKeyRegistration(
            description="wizard.setup.residence.ccaa.choices.*.label",
            key_factory=lambda v: f"wizard.setup.residence.ccaa.choices.{v}.label",
            values=tuple(m.value for m in CCAA),
        ),
        FStringKeyRegistration(
            description="wizard.setup.profile.output-language.choices.*.label",
            key_factory=lambda v: f"wizard.setup.profile.output-language.choices.{v}.label",
            values=tuple(sorted(SUPPORTED_OUTPUT_LANGUAGES)),
        ),
        FStringKeyRegistration(
            description="wizard.*.description (registered wizard flow IDs)",
            key_factory=lambda v: f"wizard.{v}.description",
            values=tuple(flow.id for flow in WIZARD_FLOWS),
        ),
        FStringKeyRegistration(
            description="wizard.setup.capabilities.*.prompt (service-capability CONFIRM questions)",
            key_factory=lambda v: f"wizard.setup.capabilities.{v}.prompt",
            values=_CAPABILITY_QUESTION_IDS,
        ),
        FStringKeyRegistration(
            description="wizard.setup.flags.*.help (service-capability CLI flags)",
            key_factory=lambda v: f"wizard.setup.flags.{v}.help",
            values=_CAPABILITY_QUESTION_IDS,
        ),
    )


def get_registered_keys() -> set[str]:
    """Expand all registered f-string patterns into concrete dotted locale keys.

    Each registration iterates its bounded value set and applies the
    ``key_factory`` to produce one concrete key per value. The result is
    the full set of locale keys that the runtime can build from the
    registered f-string patterns.
    """
    registrations = _build_registrations()
    keys: set[str] = set()
    for registration in registrations:
        for value in registration.values:
            keys.add(registration.key_factory(value))
    return keys


def get_registrations() -> tuple[FStringKeyRegistration, ...]:
    """Return the current registration tuple for inspection and testing.

    Returns:
        A tuple of every :class:`FStringKeyRegistration` built at import
        time by :func:`_build_registrations`.
    """
    return _build_registrations()


__all__ = [
    "FStringKeyRegistration",
    "get_registered_keys",
    "get_registrations",
]

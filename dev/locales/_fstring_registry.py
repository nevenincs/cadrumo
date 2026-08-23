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
is exposed through :func:`get_registered_keys` for
:class:`locales.manager.LocaleManager`
scaffold and parity checks.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol, get_args

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable
    from enum import Enum


class _FlowLike(Protocol):
    """The one attribute the flow-description registration reads."""

    @property
    def id(self) -> str: ...


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
# question ids in :mod:`application.wizard._catalogue`). Their prompt and
# CLI-flag-help keys are f-string-built, so they are enumerated here for scaffold.
_CAPABILITY_QUESTION_IDS: tuple[str, ...] = (
    "cloud-evidence-upload",
    "llm-vision",
    "google-export",
)

_LEY_49_2002_QUESTION_IDS: tuple[str, ...] = (
    "ley-49-2002-option-declared",
    "ley-49-2002-option-date",
    "ley-49-2002-renunciation-declared",
    "ley-49-2002-renunciation-date",
)

# The `cli.config.google.errors.*` refusal-frame suffixes
# `_GOOGLE_ERROR_KEY_SUFFIX` (`entrypoints.cli._config._google_errors`) maps
# each concrete `GoogleAuthError` subclass name to. The map's values are the
# complete bounded enumeration; the dynamic `f"cli.config.google.errors.{suffix}"`
# build site is not otherwise visible to the static AST scanner.
_GOOGLE_ERROR_SUFFIXES: tuple[str, ...] = (
    "validation",
    "client_not_registered",
    "client_revoked",
    "token_revoked",
    "token_expired",
    "scope_insufficient",
    "network",
    "loopback_bind",
    "browser_open",
    "non_interactive",
    "unsecured_mode",
    "keychain_locked",
    "profile_unbound",
    "adc_unavailable",
    "adc_stale",
    "impersonation_refused",
    "storage",
    "auth_failed",
)

# The `cli.config.profile.bundle_flow.*` copy slots referenced by the profile
# bundle interactive flow (`entrypoints.cli._config._profile_bundle_flow`).
# The references are CopyRef string literals resolved by the flow substrate's
# render-time copy assembler, so the static AST scanner cannot see them; this
# bounded enumeration is what keeps scaffold from stripping the entries.
_PROFILE_BUNDLE_FLOW_COPY_SLOTS: tuple[str, ...] = (
    "export_section_title",
    "import_section_title",
    "transport_prompt",
    "transport_encrypted_label",
    "transport_encrypted_description",
    "transport_cleartext_label",
    "transport_cleartext_description",
)

# Text-mode storage reports choose these labels through ``_label(name, ...)``;
# the scanner can see neither the helper argument nor its nested notice prefix.
# They are a closed CLI presentation vocabulary, not user- or data-derived keys.
_STORAGE_LABEL_SUFFIXES: tuple[str, ...] = (
    "already_present",
    "area",
    "areas",
    "checked_areas",
    "created",
    "detail",
    "entries",
    "entry_count",
    "footprint",
    "healthy",
    "issues",
    "lifecycle",
    "no",
    "occupancy",
    "path",
    "reclaimable",
    "removed_entries",
    "resolved_paths",
    "retained_entries",
    "storage_root",
    "targets",
    "yes",
    "notice_info",
    "notice_warning",
)


def _build_registrations() -> tuple[FStringKeyRegistration, ...]:
    """Construct the registration tuple at import time.

    Imports are deferred into this function so the module-level surface
    stays import-error-safe. If a domain import fails, ``get_registered_keys``
    will propagate the error with full context rather than a silent empty set.
    """
    from cadrumo.application.storage_management import StorageAreaDisposition, StorageOccupancy
    from cadrumo.application.wizard import WIZARD_FLOWS
    from cadrumo.core import StorageArea
    from cadrumo.core.errors._registry import ErrorCategory
    from cadrumo.core.i18n import SUPPORTED_OUTPUT_LANGUAGES
    from cadrumo.domain.contribuyente import CCAA
    from cadrumo.domain.deadlines import (
        EntityType,
        FiscalResidency,
        IrpfEstimationRegime,
        IrpfIncomeCategory,
        IrpfSpecialRegime,
        LegalEntityForm,
    )
    from cadrumo.domain.user_profile import ProfileSetupState

    return (
        *_wizard_choice_label_registrations(
            entity_type=EntityType,
            legal_entity_form=LegalEntityForm,
            irpf_income_category=IrpfIncomeCategory,
            irpf_estimation_regime=IrpfEstimationRegime,
            irpf_special_regime=IrpfSpecialRegime,
            fiscal_residency=FiscalResidency,
            ccaa=CCAA,
            output_languages=SUPPORTED_OUTPUT_LANGUAGES,
        ),
        *_wizard_choice_description_registrations(
            entity_type=EntityType,
            irpf_income_category=IrpfIncomeCategory,
            irpf_estimation_regime=IrpfEstimationRegime,
            fiscal_residency=FiscalResidency,
        ),
        *_wizard_question_registrations(wizard_flows=WIZARD_FLOWS),
        *_surface_registrations(profile_setup_state=ProfileSetupState),
        *_storage_registrations(
            storage_area=StorageArea,
            storage_area_disposition=StorageAreaDisposition,
            storage_occupancy=StorageOccupancy,
        ),
        *_modelo_review_filter_registrations(),
        *_generated_docs_registrations(),
        FStringKeyRegistration(
            description="errors.prefix.* (ErrorCategory)",
            key_factory=lambda v: f"errors.prefix.{v}",
            values=tuple(c.value.lower() for c in ErrorCategory),
        ),
    )


def _modelo_review_filter_registrations() -> tuple[FStringKeyRegistration, ...]:
    """Register every closed value used by the modelo-review facet labels."""
    from cadrumo.application.modelo import ModeloWorkOriginAnomaly
    from cadrumo.core import BindingSourceKind, EstadoCasillaOficial, OperatorActionAxis
    from cadrumo.domain.calculations.registry import InputKind, RelationConsumptionChannel
    from cadrumo.domain.filing import ModeloValueKind
    from cadrumo.domain.modelos import ModeloVerificationFindingKind, ModeloVerificationFindingSeverity

    axes = (
        ("input_kind", tuple(member.value for member in InputKind)),
        ("binding_source", tuple(member.value for member in BindingSourceKind)),
        ("realised_kind", tuple(member.value for member in ModeloValueKind)),
        ("origin_anomaly", tuple(member.value for member in ModeloWorkOriginAnomaly)),
        ("estado_casilla_oficial", tuple(member.value for member in EstadoCasillaOficial)),
        ("operator_action", tuple(member.value for member in OperatorActionAxis)),
        ("finding_kind", tuple(member.value for member in ModeloVerificationFindingKind)),
        ("finding_severity", tuple(member.value for member in ModeloVerificationFindingSeverity)),
        ("relation_channel", get_args(RelationConsumptionChannel)),
    )
    return tuple(
        FStringKeyRegistration(
            description=f"flows.modelo_review.filter.option.{axis}.*",
            key_factory=lambda value, axis=axis: f"flows.modelo_review.filter.option.{axis}.{value}",
            values=values,
        )
        for axis, values in axes
    )


def _generated_docs_registrations() -> tuple[FStringKeyRegistration, ...]:
    """Registrations for generated-docs display copy whose tail is an enum value.

    The generated casilla reference names every string it renders with a full
    literal key at the call site, so the regex scan sees them directly. Five
    families are the exception: their tail is an ``InputKind`` /
    ``BindingSourceKind`` / ``data_type`` / ``cadence`` / ``sign`` member, and
    the surface derives them from those closed sets rather than writing 62 keys
    out - the derivation is what makes a new enum member fail loudly instead of
    rendering blank.

    Those f-strings would otherwise emit a ``docs.casilla.<family>.*`` namespace
    marker and need no registration, but :func:`_is_dynamic_translation_prefix`
    only admits a marker whose root is in ``_DYNAMIC_TRANSLATION_ROOTS``, and
    ``docs`` is not among them. Until that root is admitted, this registration
    is what keeps scaffold from pruning the families as stale.
    """
    from ..docs.casilla_reference import display_locale_keys

    return (
        FStringKeyRegistration(
            description="docs.casilla.* (generated casilla-reference display copy)",
            key_factory=lambda v: v,
            values=display_locale_keys(),
        ),
        # The CLI reference classifies every parameter on every command page as one of
        # exactly four things -- argument or option, required or optional. The renderer
        # derives the key from those two booleans rather than writing four literals, so
        # a fifth classification would fail loudly instead of rendering blank.
        FStringKeyRegistration(
            description="docs.cli.param.* (CLI-reference parameter classification)",
            key_factory=lambda v: f"docs.cli.param.{v}",
            values=(
                "argument_required",
                "argument_optional",
                "option_required",
                "option_optional",
            ),
        ),
    )


def _wizard_choice_label_registrations(
    *,
    entity_type: type[Enum],
    legal_entity_form: type[Enum],
    irpf_income_category: type[Enum],
    irpf_estimation_regime: type[Enum],
    irpf_special_regime: type[Enum],
    fiscal_residency: type[Enum],
    ccaa: type[Enum],
    output_languages: Iterable[str],
) -> tuple[FStringKeyRegistration, ...]:
    """Registrations for the wizard's closed-choice option labels.

    Every entry expands one enum's members into the per-choice locale keys the
    wizard renders. The enums arrive as parameters because the caller already
    deferred their imports to keep this module import-error-safe.
    """
    return (
        FStringKeyRegistration(
            description="wizard.setup.taxpayer-type.entity-type.choices.*.label",
            key_factory=lambda v: f"wizard.setup.taxpayer-type.entity-type.choices.{_hyphen(v)}.label",
            values=tuple(m.value for m in entity_type),
        ),
        FStringKeyRegistration(
            description="wizard.setup.taxpayer-type.legal-entity-form.choices.*.label",
            key_factory=lambda v: f"wizard.setup.taxpayer-type.legal-entity-form.choices.{_hyphen(v)}.label",
            values=tuple(m.value for m in legal_entity_form),
        ),
        FStringKeyRegistration(
            description="wizard.setup.taxpayer-type.irpf-income-categories.choices.*.label",
            key_factory=lambda v: f"wizard.setup.taxpayer-type.irpf-income-categories.choices.{_hyphen(v)}.label",
            values=tuple(m.value for m in irpf_income_category),
        ),
        FStringKeyRegistration(
            description="wizard.setup.obligations.irpf-estimation-regime.choices.*.label",
            key_factory=lambda v: f"wizard.setup.obligations.irpf-estimation-regime.choices.{_hyphen(v)}.label",
            values=tuple(m.value for m in irpf_estimation_regime),
        ),
        FStringKeyRegistration(
            description="wizard.setup.obligations.irpf-special-regime.choices.*.label",
            key_factory=lambda v: f"wizard.setup.obligations.irpf-special-regime.choices.{_hyphen(v)}.label",
            values=tuple(m.value for m in irpf_special_regime),
        ),
        FStringKeyRegistration(
            description="wizard.setup.residence.fiscal-residency.choices.*.label",
            key_factory=lambda v: f"wizard.setup.residence.fiscal-residency.choices.{_hyphen(v)}.label",
            values=tuple(m.value for m in fiscal_residency),
        ),
        FStringKeyRegistration(
            description="wizard.setup.residence.ccaa.choices.*.label",
            key_factory=lambda v: f"wizard.setup.residence.ccaa.choices.{v}.label",
            values=tuple(m.value for m in ccaa),
        ),
        FStringKeyRegistration(
            description="wizard.setup.profile.output-language.choices.*.label",
            key_factory=lambda v: f"wizard.setup.profile.output-language.choices.{v}.label",
            values=tuple(sorted(output_languages)),
        ),
    )


def _wizard_choice_description_registrations(
    *,
    entity_type: type[Enum],
    irpf_income_category: type[Enum],
    irpf_estimation_regime: type[Enum],
    fiscal_residency: type[Enum],
) -> tuple[FStringKeyRegistration, ...]:
    """Registrations for the longer explanatory copy under each wizard choice.

    Only some choice sets carry descriptions — a legal-entity-form subset is
    curated rather than exhaustive — so this group is deliberately not a
    mirror of the label group.
    """
    return (
        FStringKeyRegistration(
            description="wizard.setup.taxpayer-type.entity-type.choices.*.description",
            key_factory=lambda v: f"wizard.setup.taxpayer-type.entity-type.choices.{_hyphen(v)}.description",
            values=tuple(m.value for m in entity_type),
        ),
        FStringKeyRegistration(
            description="wizard.setup.taxpayer-type.irpf-income-categories.choices.*.description",
            key_factory=lambda v: f"wizard.setup.taxpayer-type.irpf-income-categories.choices.{_hyphen(v)}.description",
            values=tuple(m.value for m in irpf_income_category),
        ),
        FStringKeyRegistration(
            description="wizard.setup.obligations.irpf-estimation-regime.choices.*.description",
            key_factory=lambda v: f"wizard.setup.obligations.irpf-estimation-regime.choices.{_hyphen(v)}.description",
            values=tuple(m.value for m in irpf_estimation_regime),
        ),
        FStringKeyRegistration(
            description="wizard.setup.residence.fiscal-residency.choices.*.description",
            key_factory=lambda v: f"wizard.setup.residence.fiscal-residency.choices.{_hyphen(v)}.description",
            values=tuple(m.value for m in fiscal_residency),
        ),
        FStringKeyRegistration(
            description="wizard.setup.taxpayer-type.legal-entity-form.choices.*.description (curated subset)",
            key_factory=lambda v: f"wizard.setup.taxpayer-type.legal-entity-form.choices.{_hyphen(v)}.description",
            values=("sl", "sin_fines_lucrativos"),
        ),
    )


def _wizard_question_registrations(*, wizard_flows: Iterable[_FlowLike]) -> tuple[FStringKeyRegistration, ...]:
    """Registrations for wizard flow descriptions and per-question prompt/help copy.

    Unlike the choice group these expand id tuples declared in this module
    (the service-capability and Ley 49/2002 question ids) rather than enums,
    because their sources are catalogue question ids with no enum home.
    """
    return (
        FStringKeyRegistration(
            description="wizard.*.description (registered wizard flow IDs)",
            key_factory=lambda v: f"wizard.{v}.description",
            values=tuple(flow.id for flow in wizard_flows),
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
        FStringKeyRegistration(
            description="wizard.setup.taxpayer-type Ley 49/2002 question prompts",
            key_factory=lambda v: f"wizard.setup.taxpayer-type.{v}.prompt",
            values=_LEY_49_2002_QUESTION_IDS,
        ),
        FStringKeyRegistration(
            description="wizard.setup.taxpayer-type Ley 49/2002 question help",
            key_factory=lambda v: f"wizard.setup.taxpayer-type.{v}.help",
            values=_LEY_49_2002_QUESTION_IDS,
        ),
        FStringKeyRegistration(
            description="wizard.setup.flags Ley 49/2002 CLI flags",
            key_factory=lambda v: f"wizard.setup.flags.{v}.help",
            values=_LEY_49_2002_QUESTION_IDS,
        ),
    )


def _surface_registrations(*, profile_setup_state: type[Enum]) -> tuple[FStringKeyRegistration, ...]:
    """Registrations for operator-surface copy built outside the wizard.

    The Google refusal frames, the status-page lifecycle labels, and the
    profile-bundle flow's CopyRef slots are all resolved at render time, so the
    static AST scanner cannot see their build sites.
    """
    return (
        FStringKeyRegistration(
            description="cli.config.google.errors.* (_GOOGLE_ERROR_KEY_SUFFIX refusal frames)",
            key_factory=lambda v: f"cli.config.google.errors.{v}",
            values=_GOOGLE_ERROR_SUFFIXES,
        ),
        FStringKeyRegistration(
            description="flows.status.profiles.status.* (status-page profile setup-state labels)",
            key_factory=lambda v: f"flows.status.profiles.status.{v}",
            values=tuple(m.value for m in profile_setup_state),
        ),
        FStringKeyRegistration(
            description="cli.config.profile.bundle_flow.* (profile bundle interactive-flow CopyRef copy)",
            key_factory=lambda v: f"cli.config.profile.bundle_flow.{v}",
            values=_PROFILE_BUNDLE_FLOW_COPY_SLOTS,
        ),
    )


def _storage_registrations(
    *,
    storage_area: type[Enum],
    storage_area_disposition: type[Enum],
    storage_occupancy: type[Enum],
) -> tuple[FStringKeyRegistration, ...]:
    """Register every bounded key built by the storage CLI's display helpers."""
    return (
        FStringKeyRegistration(
            description="cli.config.storage.labels.* (text-mode storage report labels)",
            key_factory=lambda v: f"cli.config.storage.labels.{v}",
            values=_STORAGE_LABEL_SUFFIXES,
        ),
        FStringKeyRegistration(
            description="cli.config.storage.values.area.* (StorageArea)",
            key_factory=lambda v: f"cli.config.storage.values.area.{v}",
            values=tuple(member.value for member in storage_area),
        ),
        FStringKeyRegistration(
            description="cli.config.storage.values.lifecycle.* (StorageAreaDisposition)",
            key_factory=lambda v: f"cli.config.storage.values.lifecycle.{v}",
            values=tuple(member.value for member in storage_area_disposition),
        ),
        FStringKeyRegistration(
            description="cli.config.storage.values.occupancy.* (StorageOccupancy)",
            key_factory=lambda v: f"cli.config.storage.values.occupancy.{v}",
            values=tuple(member.value for member in storage_occupancy),
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

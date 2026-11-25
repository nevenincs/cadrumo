"""Bounded f-string locale registrations for the setup wizard's choices and questions."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from .fstring_registry import FStringKeyRegistration

if TYPE_CHECKING:
    from collections.abc import Iterable


class _ChoiceLike(Protocol):
    @property
    def value(self) -> str: ...

    @property
    def description(self) -> object: ...


class _QuestionLike(Protocol):
    @property
    def id(self) -> str: ...

    @property
    def profile_key(self) -> str | None: ...

    @property
    def choices(self) -> Iterable[_ChoiceLike]: ...


class _SectionLike(Protocol):
    @property
    def questions(self) -> Iterable[_QuestionLike]: ...


class WizardFlowLike(Protocol):
    """The one attribute the flow-description registration reads."""

    @property
    def id(self) -> str:
        """The flow identifier."""
        ...

    @property
    def sections(self) -> Iterable[_SectionLike]:
        """The flow's sections, each holding its questions."""
        ...


def _hyphen(v: str) -> str:
    """Replace underscores with hyphens — the transform used by wizard choice labels."""
    return v.replace("_", "-")


# The service-capability CONFIRM question ids (hyphenated, matching the catalogue
# question ids in :mod:`application.wizard.catalogue`). Their prompt and
# CLI-flag-help keys are f-string-built, so they are enumerated here for scaffold.
_CAPABILITY_QUESTION_IDS: tuple[str, ...] = (
    "cloud-evidence-upload",
    "llm-vision",
    "google-export",
)


def flow_choice_values(flow: WizardFlowLike, question_id: str, *, described: bool = False) -> tuple[str, ...]:
    """Return the canonical choice values declared by one wizard question."""
    for section in flow.sections:
        for question in section.questions:
            if question.id != question_id:
                continue
            return tuple(choice.value for choice in question.choices if not described or choice.description is not None)
    raise LookupError(f"wizard flow has no question {question_id!r}")


def wizard_choice_label_registrations(
    *,
    entity_type: Iterable[str],
    legal_entity_form: Iterable[str],
    irpf_income_category: Iterable[str],
    irpf_estimation_regime: Iterable[str],
    irpf_special_regime: Iterable[str],
    fiscal_residency: Iterable[str],
    ccaa: Iterable[str],
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
            values=tuple(entity_type),
        ),
        FStringKeyRegistration(
            description="wizard.setup.taxpayer-type.legal-entity-form.choices.*.label",
            key_factory=lambda v: f"wizard.setup.taxpayer-type.legal-entity-form.choices.{_hyphen(v)}.label",
            values=tuple(legal_entity_form),
        ),
        FStringKeyRegistration(
            description="wizard.setup.taxpayer-type.irpf-income-categories.choices.*.label",
            key_factory=lambda v: f"wizard.setup.taxpayer-type.irpf-income-categories.choices.{_hyphen(v)}.label",
            values=tuple(irpf_income_category),
        ),
        FStringKeyRegistration(
            description="wizard.setup.obligations.irpf-estimation-regime.choices.*.label",
            key_factory=lambda v: f"wizard.setup.obligations.irpf-estimation-regime.choices.{_hyphen(v)}.label",
            values=tuple(irpf_estimation_regime),
        ),
        FStringKeyRegistration(
            description="wizard.setup.obligations.irpf-special-regime.choices.*.label",
            key_factory=lambda v: f"wizard.setup.obligations.irpf-special-regime.choices.{_hyphen(v)}.label",
            values=tuple(irpf_special_regime),
        ),
        FStringKeyRegistration(
            description="wizard.setup.residence.fiscal-residency.choices.*.label",
            key_factory=lambda v: f"wizard.setup.residence.fiscal-residency.choices.{_hyphen(v)}.label",
            values=tuple(fiscal_residency),
        ),
        FStringKeyRegistration(
            description="wizard.setup.residence.ccaa.choices.*.label",
            key_factory=lambda v: f"wizard.setup.residence.ccaa.choices.{v}.label",
            values=tuple(ccaa),
        ),
        FStringKeyRegistration(
            description="wizard.setup.profile.output-language.choices.*.label",
            key_factory=lambda v: f"wizard.setup.profile.output-language.choices.{v}.label",
            values=tuple(sorted(output_languages)),
        ),
    )


def wizard_choice_description_registrations(
    *,
    entity_type: Iterable[str],
    legal_entity_form: Iterable[str],
    irpf_income_category: Iterable[str],
    irpf_estimation_regime: Iterable[str],
    fiscal_residency: Iterable[str],
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
            values=tuple(entity_type),
        ),
        FStringKeyRegistration(
            description="wizard.setup.taxpayer-type.irpf-income-categories.choices.*.description",
            key_factory=lambda v: f"wizard.setup.taxpayer-type.irpf-income-categories.choices.{_hyphen(v)}.description",
            values=tuple(irpf_income_category),
        ),
        FStringKeyRegistration(
            description="wizard.setup.obligations.irpf-estimation-regime.choices.*.description",
            key_factory=lambda v: f"wizard.setup.obligations.irpf-estimation-regime.choices.{_hyphen(v)}.description",
            values=tuple(irpf_estimation_regime),
        ),
        FStringKeyRegistration(
            description="wizard.setup.residence.fiscal-residency.choices.*.description",
            key_factory=lambda v: f"wizard.setup.residence.fiscal-residency.choices.{_hyphen(v)}.description",
            values=tuple(fiscal_residency),
        ),
        FStringKeyRegistration(
            description="wizard.setup.taxpayer-type.legal-entity-form.choices.*.description (curated subset)",
            key_factory=lambda v: f"wizard.setup.taxpayer-type.legal-entity-form.choices.{_hyphen(v)}.description",
            values=tuple(legal_entity_form),
        ),
    )


def wizard_question_registrations(*, wizard_flows: Iterable[WizardFlowLike]) -> tuple[FStringKeyRegistration, ...]:
    """Registrations for wizard flow descriptions and per-question prompt/help copy.

    Unlike the choice group these expand id tuples declared in this module
    (the service-capability question ids) rather than enums, because their
    sources are catalogue question ids with no enum home.
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
    )

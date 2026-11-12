"""Choose which families of earlier-ejercicio carries one statement of absence states.

The work form serves one statement per family that still has an open carry. A
filer who has not chosen a family is answered only while exactly one family is
open: stating several at once by default would record an absence nobody made.
A choice that leaves an open family out, or no choice while two or more are
open, is refused before anything is staged, naming every open family and the
one command that states each of them by name.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import TYPE_CHECKING, Final

from ...core.external_constants import OutputLanguage
from ...core.i18n.render import tr
from ...domain.calculations.registry.binding_absence_attestation import PRIOR_CARRY_FAMILIES, AbsenceAttestationFamily
from ...domain.calculations.registry.ids import BindingId
from ...domain.modelos.errors import ModeloError
from ..operations.next_step import OperationNextStepErrorMixin, OperationNextStepWording, OperationOpenWorkStepV1
from .edit_models import ModeloEditBaselineV1, ModeloEditBindingIntentKind, ModeloEditSubmissionV1
from .work_form_models import ModeloFormCarryAttestation
from .work_form_service import modelo_form_snapshot
from .work_form_wording import modelo_number, period_words

if TYPE_CHECKING:
    from ...domain.calculations.registry.authority import PinnedAuthorityOperation

_FAMILY_NOTHING_OPEN_MESSAGE_KEY: Final[str] = "application.modelo.errors.prior_carries_family_nothing_open"
_FAMILY_CHOICE_REQUIRED_MESSAGE_KEY: Final[str] = "application.modelo.errors.prior_carries_family_choice_required"
_OPEN_WORK_LOCALE_KEY: Final[str] = "application.modelo.projection_words.next_step.open_work"
_COMMAND_WORDS: Final[str] = "aeat app modelo work attest-prior-carries"


def open_declaration_step(baseline: ModeloEditBaselineV1) -> OperationNextStepWording:
    """Offer opening the declaration, where its form serves the statements and their carries."""

    def worded(language: OutputLanguage) -> OperationOpenWorkStepV1:
        return OperationOpenWorkStepV1(
            work_unit_id=baseline.work_unit_id,
            words=tr(
                _OPEN_WORK_LOCALE_KEY,
                modelo=modelo_number(str(baseline.modelo), language),
                period=period_words(baseline.period, language),
                locale=language.value,
            ),
        )

    return worded


def family_door(work_unit_id: str, families: Iterable[AbsenceAttestationFamily]) -> str:
    """The command that states exactly these families, each named by its own ``--family``."""
    flags = " ".join(f"--family {family.value}" for family in families)
    return f"{_COMMAND_WORDS} {work_unit_id} {flags}"


class ModeloPriorCarryFamilyNothingOpenError(OperationNextStepErrorMixin, ModeloError):
    """The family the filer chose holds no carry the statement could answer. Nothing was staged."""

    def __init__(
        self, *, baseline: ModeloEditBaselineV1, family: AbsenceAttestationFamily, next_step: OperationNextStepWording
    ) -> None:
        """Name the declaration and the family the filer asked about."""
        super().__init__(
            translated_message=_FAMILY_NOTHING_OPEN_MESSAGE_KEY,
            context={"modelo": str(baseline.modelo), "filing_year": baseline.filing_year, "family": family.value},
            next_step=next_step,
        )


class ModeloPriorCarryFamilyChoiceRequiredError(OperationNextStepErrorMixin, ModeloError):
    """The choice leaves a family with open carries unstated. Nothing was staged.

    One statement covers every open family: the calculation the statement leads
    to refuses while any family stays unstated, so a statement of only some
    families could never be applied. The refusal names the open families the
    choice leaves out, and the one command that names every open family.
    """

    def __init__(
        self,
        *,
        baseline: ModeloEditBaselineV1,
        open_families: tuple[AbsenceAttestationFamily, ...],
        missing_families: tuple[AbsenceAttestationFamily, ...],
        next_step: OperationNextStepWording,
    ) -> None:
        """Name the open families, those the choice leaves out, and the door that names every one."""
        work_unit_id = str(baseline.work_unit_id)
        super().__init__(
            translated_message=_FAMILY_CHOICE_REQUIRED_MESSAGE_KEY,
            context={
                "modelo": str(baseline.modelo),
                "filing_year": baseline.filing_year,
                "families": ", ".join(family.value for family in open_families),
                "missing": ", ".join(family.value for family in missing_families),
                "family_door": family_door(work_unit_id, open_families),
            },
            next_step=next_step,
        )


def select_prior_carry_attestations(
    baseline: ModeloEditBaselineV1,
    attestations: Iterable[ModeloFormCarryAttestation],
    *,
    families: Iterable[AbsenceAttestationFamily],
) -> tuple[ModeloFormCarryAttestation, ...]:
    """The statements the filer's choice states, refused before anything is staged when it is not one.

    Each named family must have an open carry on the form, and together they must
    cover every open family, because a statement that leaves one out could never be
    applied. With none named, the open carries are stated only while exactly one family
    has them. Only the families of ``PRIOR_CARRY_FAMILIES`` can be stated through this door; any other
    family is refused as having nothing open. An empty result means nothing is open at all, which the submission
    builder refuses in its own words.
    """
    open_statements = tuple(statement for statement in attestations if statement.family in PRIOR_CARRY_FAMILIES)
    chosen = tuple(dict.fromkeys(families))
    open_families = tuple(sorted({statement.family for statement in open_statements}, key=lambda each: each.value))
    _require_chosen_open(baseline, chosen, open_families)
    missing = tuple(family for family in open_families if family not in chosen)
    if missing and (chosen or len(open_families) > 1):
        raise ModeloPriorCarryFamilyChoiceRequiredError(
            baseline=baseline,
            open_families=open_families,
            missing_families=missing,
            next_step=open_declaration_step(baseline),
        )
    return open_statements


def _require_chosen_open(
    baseline: ModeloEditBaselineV1,
    chosen: tuple[AbsenceAttestationFamily, ...],
    open_families: tuple[AbsenceAttestationFamily, ...],
) -> None:
    """Refuse the first chosen family that has no open carry on the form."""
    for family in chosen:
        if family not in open_families:
            raise ModeloPriorCarryFamilyNothingOpenError(
                baseline=baseline, family=family, next_step=open_declaration_step(baseline)
            )


_CARRY_STATEMENT_KINDS: Final[frozenset[ModeloEditBindingIntentKind]] = frozenset(
    {
        ModeloEditBindingIntentKind.ATTEST_NO_AMOUNT,
        ModeloEditBindingIntentKind.SET_OVERRIDE_VALUE,
        ModeloEditBindingIntentKind.ATTEST_PRIOR_VALUE,
    }
)


def prior_carry_binding_ids(
    operation: PinnedAuthorityOperation, submission: ModeloEditSubmissionV1
) -> frozenset[BindingId]:
    """The bindings of a prior-carry family in the revision ``submission``'s declaration is worked under.

    Read only when the submission states a binding the way a carry is stated;
    otherwise no carry statement is being checked and the set is empty.
    """
    if not any(intent.kind in _CARRY_STATEMENT_KINDS for intent in submission.binding_intents):
        return frozenset[BindingId]()
    baseline = submission.baseline
    snapshot = modelo_form_snapshot(
        operation, baseline.modelo, baseline.filing_year, baseline.period, baseline.law_selected_revision_id
    )
    return frozenset(
        binding.id for binding in snapshot.revision.bindings if binding.absence_attestation in PRIOR_CARRY_FAMILIES
    )


__all__ = [
    "ModeloPriorCarryFamilyChoiceRequiredError",
    "ModeloPriorCarryFamilyNothingOpenError",
    "family_door",
    "open_declaration_step",
    "prior_carry_binding_ids",
    "select_prior_carry_attestations",
]

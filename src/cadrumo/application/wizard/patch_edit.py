"""Atomic application judge for a scripted wizard profile patch."""

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Protocol

from pydantic import BaseModel

from ...core.operator_action_enums import ActionEvidenceProvenance, NoRecoveryOutcome
from ...domain.user_profile.values import ProfileSetupState, UserProfileFact, UserProfileRecord
from ..user_profile.capsule_record import ProfileRecordConflictError
from ..user_profile.fact_write import ProfileFactWriteDoor, apply_profile_fact_changes
from ..user_profile.filing_baseline import missing_filing_baseline_flag_groups
from ..user_profile.profile_record_repository import ProfileRecordRepository
from ..user_profile.projections import record_to_path_values
from .errors import WizardMissingFlagError, WizardPreconditionCondition, wizard_no_action_verdict
from .models import WizardFlow
from .persistence import profile_values_from_patch, project_answers, serialise_answers

if TYPE_CHECKING:
    from ...domain.calculations.registry.authority import PinnedAuthorityOperation


class WizardPatchPersister(Protocol):
    """The command's application-owned patch route, including an installed runtime route."""

    def __call__(
        self,
        *,
        profile_id: str,
        supplied: Mapping[str, str],
        colegio_concertado: bool | None,
    ) -> tuple[dict[str, str], bool]:
        """Persist the named patch and return values plus whether it changed."""
        ...


def format_missing_flags(missing: tuple[str, ...]) -> str:
    """Render missing question ids as the actual ``--flag`` spellings."""
    return " ".join(f"--{question_id}" for question_id in missing)


def missing_filing_baseline_flag_groups_for_flow(
    flow: WizardFlow, answers: BaseModel
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Return missing filing flags split into identity and Modelo groups."""
    profile_path_flags = {
        question.profile_key: question.id
        for section in flow.sections
        for question in section.questions
        if question.profile_key is not None
    }
    return missing_filing_baseline_flag_groups(serialise_answers(flow, answers), profile_path_flags=profile_path_flags)


def require_filing_baseline(flow: WizardFlow, answers: BaseModel) -> None:
    """Refuse a complete-profile candidate lacking its filing baseline."""
    identity_missing, conditional_missing = missing_filing_baseline_flag_groups_for_flow(flow, answers)
    missing = (*identity_missing, *conditional_missing)
    if not missing:
        return
    raise WizardMissingFlagError(
        translated_message=(
            "application.wizard.errors.edit_missing_filing_baseline"
            if identity_missing
            else "application.wizard.errors.edit_missing_modelo_requirements"
        ),
        context={"flow_id": flow.id, "missing": missing, "missing_flags": format_missing_flags(missing)},
        precondition_verdict=wizard_no_action_verdict(
            condition=WizardPreconditionCondition.FILING_BASELINE_COMPLETE,
            facts={"filing_baseline_complete": False, "missing_flag_count": len(missing)},
            provenance=ActionEvidenceProvenance.RUNTIME_OBSERVATION,
            outcome=NoRecoveryOutcome.OPERATOR_DECISION,
        ),
    )


def refuse_foral_ccaa(
    canonical: Mapping[str, str],
    explicit_flags: Mapping[str, str],
    *,
    operation: PinnedAuthorityOperation,
) -> None:
    """Reject foral CCAA tokens before persistence or prompting."""
    ccaa_token = canonical.get("tax-residence-ccaa") or explicit_flags.get("tax-residence-ccaa")
    if ccaa_token is None:
        return
    from ...core.text_fold import fold_diacritics
    from ...domain.calculations.registry.ccaa_catalogue import resolve_ccaa_catalogue
    from ...domain.contribuyente.errors import ForalRegimeError

    normalized = fold_diacritics(ccaa_token.strip().casefold().replace(" ", "_").replace("-", "_"))
    if resolve_ccaa_catalogue(authority=operation).is_foral_alias(normalized):
        raise ForalRegimeError(ccaa_token)


def cleared_profile_paths(flow: WizardFlow, supplied: Mapping[str, str]) -> tuple[str, ...]:
    """Retain explicit blank optional answers as clear operations."""
    questions = {question.id: question for section in flow.sections for question in section.questions}
    return tuple(
        question.profile_key
        for question_id, raw in supplied.items()
        if (question := questions.get(question_id)) is not None and question.profile_key is not None and not raw.strip()
    )


def validate_profile_patch(
    *,
    flow: WizardFlow,
    current_values: Mapping[str, str],
    setup_state: ProfileSetupState,
    supplied: Mapping[str, str],
    colegio_concertado: bool | None,
    operation: PinnedAuthorityOperation,
) -> tuple[UserProfileFact, ...]:
    """Judge a proposed patch against authorized facts without opening storage.

    Frontends may use this for immediate diagnostics. The authoritative writer
    repeats the same judge against its CAS-checked record before publication.
    """
    refuse_foral_ccaa(supplied, supplied, operation=operation)
    patched_values = profile_values_from_patch(flow, supplied)
    if colegio_concertado is not None:
        patched_values["withholding.colegio_concertado"] = "true" if colegio_concertado else "false"
    cleared_paths = cleared_profile_paths(flow, supplied)
    merged_values = dict(current_values)
    merged_values.update(patched_values)
    for path in cleared_paths:
        merged_values.pop(path, None)
    if setup_state is not ProfileSetupState.INCOMPLETE:
        require_filing_baseline(flow, project_answers(flow, merged_values))
    return (
        *(UserProfileFact(path=path, value=value) for path, value in patched_values.items()),
        *(UserProfileFact(path=path, value=None) for path in cleared_paths),
    )


def apply_profile_patch(
    *,
    flow: WizardFlow,
    profile_id: str,
    expected_revision: int,
    expected_content_digest: str,
    supplied: Mapping[str, str],
    colegio_concertado: bool | None,
    operation: PinnedAuthorityOperation,
) -> UserProfileRecord:
    """Validate and CAS-publish one exact patch through the shared fact writer."""
    profile_decode_context = operation.profile_decode_context()
    current = ProfileRecordRepository.for_current_session(
        profile_id, profile_decode_context=profile_decode_context
    ).load(profile_id)
    if current.record_revision != expected_revision or current.content_digest != expected_content_digest:
        raise ProfileRecordConflictError("wizard profile patch baseline is stale")
    changes = validate_profile_patch(
        flow=flow,
        current_values=record_to_path_values(current),
        setup_state=current.setup_state,
        supplied=supplied,
        colegio_concertado=colegio_concertado,
        operation=operation,
    )
    return apply_profile_fact_changes(
        profile_id=profile_id,
        changes=changes,
        door=ProfileFactWriteDoor.PATCH,
        expected_record=current,
        profile_decode_context=profile_decode_context,
    )


__all__ = [
    "WizardPatchPersister",
    "apply_profile_patch",
    "cleared_profile_paths",
    "format_missing_flags",
    "missing_filing_baseline_flag_groups_for_flow",
    "refuse_foral_ccaa",
    "require_filing_baseline",
    "validate_profile_patch",
]

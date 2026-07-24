"""Persistence adapter for wizard answers.

Serialises a typed answers model back to canonical-token strings, then
persists profile facts through canonical user-profile orchestration.
The reverse projection (``project_answers``) builds the typed answers
model from a raw canonical-token dict.

``persist_answers`` distinguishes the two wizard verbs. ``create``
registers a fresh profile from the full answer set. ``edit`` is a true
patch: only the questions the operator explicitly supplied on the
command line are written, so editing one field never reverts the rest
of a populated profile to its descriptor defaults.
"""

from __future__ import annotations

from collections.abc import Collection, Mapping
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from pydantic import BaseModel

if TYPE_CHECKING:
    from ...domain.contribuyente import DescendantInfo
    from ...domain.user_profile import UserProfileRecord

from ...core.flows import REPEATING_INSTANCE_SEPARATOR
from ...core.parsing import parse_iso8601_date
from ...core.setup_answers import register_project_answers as _register_project_answers
from ...core.time import today_madrid
from ..user_profile import (
    register_active_profile,
    set_active_fields,
)
from ..workflow import WorkflowInputMismatchError, WorkflowState
from ._descendant_group import (
    DESCENDANT_PAGE_IDS,
    DESCENDANTS_COUNT_PAGE_ID,
    DESCENDANTS_GROUP_ID,
)
from ._models import WizardFlow, WizardQuestion

WizardPersistMode = Literal["create", "edit"]
"""Which wizard verb is persisting — ``create`` registers a new profile,
``edit`` upserts facts on an existing one. The verb is the authority for
the create-vs-edit branch; it is never re-derived at runtime."""


def _canonicalise(question: WizardQuestion, value: object) -> str:
    """Render ``value`` as the canonical token used by the persistence layer."""
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, int):
        return str(value)
    return str(value)


def _question_by_id(flow: WizardFlow) -> Mapping[str, WizardQuestion]:
    table: dict[str, WizardQuestion] = {}
    for section in flow.sections:
        for question in section.questions:
            table[question.id] = question
    return table


def _field_to_question(flow: WizardFlow) -> Mapping[str, WizardQuestion]:
    """Build ``answers_model`` field name → ``WizardQuestion`` map."""
    table: dict[str, WizardQuestion] = {}
    for section in flow.sections:
        for question in section.questions:
            field_name = question.id.replace("-", "_")
            table[field_name] = question
    return table


def serialise_answers(
    flow: WizardFlow,
    answers: BaseModel,
    *,
    only_question_ids: Collection[str] | None = None,
) -> dict[str, str]:
    """Project a typed answers model into the canonical-token dict.

    Only profile-bound questions contribute a key. When
    ``only_question_ids`` is supplied, the projection is restricted to
    those question ids — the patch behaviour the ``edit`` verb relies
    on so an unsupplied field is never written back at its default.
    """
    typed = answers.model_dump()
    mapping = _field_to_question(flow)
    result: dict[str, str] = {}
    for field_name, value in typed.items():
        question = mapping.get(field_name)
        if question is None or question.profile_key is None:
            continue
        if only_question_ids is not None and question.id not in only_question_ids:
            continue
        result[question.profile_key] = _canonicalise(question, value)
    return result


def persist_answers(
    flow: WizardFlow,
    answers: BaseModel,
    *,
    state: WorkflowState,
    profile_name: str,
    profile_id: str,
    mode: WizardPersistMode,
    supplied_question_ids: Collection[str] | None = None,
    routing_profile_id: str | None = None,
) -> WorkflowState:
    """Persist ``answers`` into the profile bucket and return updated state.

    ``profile_id`` is the immutable UUID profile identity; ``profile_name``
    is the operator-chosen display label.

    ``mode`` is the create-vs-edit discriminator and is the wizard verb
    itself, not a runtime-detected fact. ``"create"`` routes to
    :func:`register_active_profile`, which delegates the whole
    cross-store create — bucket directory, manifest, encrypted record,
    and the active-profile pointer — to :class:`ProfileRepository` as
    one unit of work and refuses a label already carried by a live
    profile. ``"edit"`` routes to :func:`set_active_fields`, which
    upserts facts on the active profile.

    ``supplied_question_ids`` names the questions the operator
    explicitly supplied on the command line. On the ``"edit"`` path it
    scopes the write to exactly those questions: ``edit`` is a patch,
    so a field the operator did not name is left untouched. It must be
    supplied for ``"edit"``; it is ignored for ``"create"``, which
    always registers the full set.

    Returns the updated :class:`WorkflowState` after persisting the answers.
    """
    from ...domain.user_profile import UserProfileFact

    if mode == "create":
        canonical = serialise_answers(flow, answers)
        facts = tuple(UserProfileFact(path=path, value=value) for path, value in canonical.items() if value)
        return register_active_profile(
            state,
            profile_id=profile_id,
            display_name=profile_name,
            facts=facts,
            routing_profile_id=routing_profile_id,
        )

    if supplied_question_ids is None:
        raise WorkflowInputMismatchError(
            translated_message="application.wizard.errors.persist_answers_edit_requires_supplied_question_ids",
        )
    canonical = serialise_answers(flow, answers, only_question_ids=supplied_question_ids)
    facts = tuple(UserProfileFact(path=path, value=value) for path, value in canonical.items() if value)
    return set_active_fields(state, facts)


def profile_values_from_patch(flow: WizardFlow, supplied: Mapping[str, str]) -> dict[str, str]:
    """Project a non-interactive edit patch to schema-path keyed values."""
    from ._widgets import validate_widget_answer

    questions = _question_by_id(flow)
    values: dict[str, str] = {}
    for question_id, raw in supplied.items():
        question = questions.get(question_id)
        if question is None:
            raise WorkflowInputMismatchError(
                translated_message="application.wizard.errors.persist_patch_unknown_question_id",
                context={"question_id": question_id},
            )
        if question.profile_key is None:
            continue
        validated = validate_widget_answer(question, raw)
        if not validated:
            continue
        values[question.profile_key] = validated
    return values


def persist_patch(
    flow: WizardFlow,
    supplied: Mapping[str, str],
    *,
    state: WorkflowState,
) -> WorkflowState:
    """Patch the active profile with only the explicitly supplied flags and return the updated :class:`WorkflowState`.

    ``supplied`` is the canonical-token dict keyed by *question id*,
    carrying exactly the flags the operator named on a non-interactive
    ``edit`` (``--quiet`` / ``--accept-defaults``). This is the true
    patch path: it never constructs the full :class:`SetupAnswers`
    model — which would demand every required field — and never seeds a
    descriptor default for an unsupplied question. Each supplied value
    is re-validated through its widget validator, mapped to its
    ``profile_key``, and upserted via :func:`set_active_fields`. A
    question with no ``profile_key`` is not a profile fact and is
    skipped.
    """
    from ...domain.user_profile import UserProfileFact

    facts = tuple(
        UserProfileFact(path=path, value=value) for path, value in profile_values_from_patch(flow, supplied).items()
    )
    return set_active_fields(state, facts)


def project_answers(flow: WizardFlow, values: Mapping[str, str]) -> BaseModel:
    """Reverse projection: build the typed answers model from canonical tokens.

    Values absent from ``values`` fall back to the descriptor's default
    or the answers model's own field default; the answers model then
    runs its strict validation.
    """
    questions = _question_by_id(flow)
    typed: dict[str, object] = {}
    for question in questions.values():
        canonical = _resolve_canonical(question, values)
        if canonical is None:
            continue
        field_name = question.id.replace("-", "_")
        typed[field_name] = _parse_canonical(question, canonical)
    return flow.answers_model.model_validate(typed)


def _resolve_canonical(question: WizardQuestion, values: Mapping[str, str]) -> str | None:
    """Resolve the canonical token to project for ``question``."""
    if question.profile_key is not None:
        candidate = values.get(question.profile_key)
        if candidate is not None:
            return candidate
    return question.default


def _parse_canonical(question: WizardQuestion, raw: str) -> object:
    """Parse a canonical token into the question's declared answer type.

    For an optional CONFIRM, a blank canonical projects to the empty
    string (the undeclared three-state arm of the answers-model union),
    never to ``False``. Collapsing blank onto ``False`` here would
    erase the distinction between "the operator did not declare this
    fact" and "the operator positively declined", and would defeat the
    persistence-layer's drop-blank filter — the projected ``False``
    would round-trip to a stored ``"false"`` token and reload as a
    declared decline.
    """
    answer_type = question.answer_type
    if answer_type is bool:
        if raw == "" and not (question.required and question.visible_when is None):
            return ""
        return raw == "true"
    if answer_type is int:
        return int(raw) if raw else 0
    if answer_type is Path:
        return Path(raw) if raw else Path()
    return raw


def _instance_count(raw: str) -> int:
    """Parse the descendant count answer, clamping malformed input to zero."""
    try:
        return max(0, int(raw)) if raw else 0
    except ValueError:
        return 0


def _discapacidad_grade(raw: str) -> Literal[0, 33, 65] | None:
    """Narrow a discapacidad answer token to the closed grade set."""
    match raw:
        case "0":
            return 0
        case "33":
            return 33
        case "65":
            return 65
        case _:
            return None


def _safe_adoption_date(birth_raw: str, adoption_raw: str | None) -> str | None:
    """Return the adoption token only when it is a valid pair with birth.

    A cross-field adoption invariant (adoption >= birth, adoption <= today)
    is surfaced as a review verdict before submit, but the checkpoint
    (save-and-exit) persist path runs no flow validators, so an out-of-order
    adoption date could still reach this projection. Dropping the invalid
    optional token here keeps the checkpoint write from raising a raw
    ``DescendantInfo`` model error; the review verdict still blocks the final
    submit until the operator corrects it.
    """
    if not adoption_raw:
        return None
    birth = parse_iso8601_date(birth_raw) if birth_raw else None
    adoption = parse_iso8601_date(adoption_raw)
    if birth is None or adoption is None or adoption < birth or adoption > today_madrid():
        return None
    return adoption_raw


def _descendant_from_row(row: Mapping[str, str]) -> DescendantInfo:
    """Reconstruct one ``DescendantInfo`` from an instance's canonical answers.

    Blank optional answers fall back to the record's own defaults
    (convivencia defaults to cohabiting, custodia to sole custody, the
    integer supplements to zero); the ISO date strings are coerced by the
    record's own field validators. An out-of-order adoption date is dropped
    (see :func:`_safe_adoption_date`) so a checkpoint save never raw-raises.
    """
    from ...domain.contribuyente import DescendantInfo

    meses = row.get("meses-madre-trabajo") or ""
    gastos = row.get("gastos-guarderia") or ""
    return DescendantInfo(
        birth_date=row["birth-date"],
        adoption_date=_safe_adoption_date(row["birth-date"], row.get("adoption-date")),
        discapacidad_grado=_discapacidad_grade(row.get("discapacidad", "")),
        convive_con_contribuyente=row.get("convivencia", "") != "false",
        custodia_compartida=row.get("custodia-compartida", "") == "true",
        meses_madre_trabajo_2024=int(meses) if meses else 0,
        gastos_guarderia_euros=int(gastos) if gastos else 0,
        nif=row.get("nif") or None,
    )


def descendant_facts_from_answers(answers: Mapping[str, str]) -> list[tuple[str, str]]:
    """Project the descendant repeating-group answers into profile facts.

    The setup flow's descendant repeating group keys each instance answer
    as ``descendientes#<index>.<page-id>``. This reads the live instance
    count from the count page, reconstructs one
    :class:`~cadrumo.domain.contribuyente.DescendantInfo` per index, and
    delegates to
    :func:`~cadrumo.domain.contribuyente.descendant_facts_from_list` so the
    emitted ``renta_family.descendiente.{n}.*`` paths and the derived
    aggregates are the single canonical projection the
    ``_minimo_descendientes_facts`` injector and the registry selectors
    consume. Returns an empty list when the group was never reached (the
    count page carries no answer), so a descendant-free profile writes no
    descendant fact.
    """
    if DESCENDANTS_COUNT_PAGE_ID not in answers:
        return []
    from ...domain.contribuyente import descendant_facts_from_list

    count = _instance_count(answers.get(DESCENDANTS_COUNT_PAGE_ID, ""))
    descendientes: list[DescendantInfo] = []
    for index in range(count):
        prefix = f"{DESCENDANTS_GROUP_ID}{REPEATING_INSTANCE_SEPARATOR}{index}"
        row = {page_id: answers.get(f"{prefix}.{page_id}", "") for page_id in DESCENDANT_PAGE_IDS}
        if not row["birth-date"]:
            continue
        descendientes.append(_descendant_from_row(row))
    return descendant_facts_from_list(descendientes)


def descendant_answers_from_record(record: UserProfileRecord | None) -> dict[str, str]:
    """Re-project a record's descendant facts into repeating-group answers.

    The inverse of :func:`descendant_facts_from_answers`: reads the
    ``renta_family.descendiente.{n}.*`` facts a record carries, reconstructs
    each :class:`~cadrumo.domain.contribuyente.DescendantInfo` through the
    canonical :func:`~cadrumo.domain.contribuyente.descendant_list_from_facts`,
    and emits the ``descendientes-count`` answer plus one
    ``descendientes#<index>.<page-id>`` answer per populated field. This is the
    exact page-keyed shape :func:`~cadrumo.application.flows.resume_flow`
    re-walks to re-instantiate the group: the count answer commits first (the
    familia section orders the count page before the group), revealing the
    instance pages the remaining answers then seed against the current
    definition. Returns an empty map when the record declares no descendants,
    so a childless profile seeds no group.

    The per-field emission mirrors :func:`_descendant_from_row` exactly, so a
    save-then-resume round-trip through
    :func:`~cadrumo.application.wizard._checkpoint_store.checkpoint_facts_from_answers`
    reconstructs an identical fact set: an absent optional field stays absent
    on both legs, never coerced to a stored default.
    """
    if record is None:
        return {}
    from ...domain.contribuyente import descendant_list_from_facts
    from ..user_profile import record_to_path_values

    descendientes = descendant_list_from_facts(record_to_path_values(record))
    if not descendientes:
        return {}
    answers: dict[str, str] = {DESCENDANTS_COUNT_PAGE_ID: str(len(descendientes))}
    for index, descendant in enumerate(descendientes):
        prefix = f"{DESCENDANTS_GROUP_ID}{REPEATING_INSTANCE_SEPARATOR}{index}"
        answers[f"{prefix}.birth-date"] = descendant.birth_date.isoformat()
        if descendant.adoption_date is not None:
            answers[f"{prefix}.adoption-date"] = descendant.adoption_date.isoformat()
        if descendant.discapacidad_grado is not None:
            answers[f"{prefix}.discapacidad"] = str(descendant.discapacidad_grado)
        answers[f"{prefix}.convivencia"] = "true" if descendant.convive_con_contribuyente else "false"
        answers[f"{prefix}.custodia-compartida"] = "true" if descendant.custodia_compartida else "false"
        if descendant.meses_madre_trabajo_2024 > 0:
            answers[f"{prefix}.meses-madre-trabajo"] = str(descendant.meses_madre_trabajo_2024)
        if descendant.gastos_guarderia_euros > 0:
            answers[f"{prefix}.gastos-guarderia"] = str(descendant.gastos_guarderia_euros)
        if descendant.nif is not None:
            answers[f"{prefix}.nif"] = descendant.nif
    return answers


_register_project_answers(project_answers)

__all__ = [
    "WizardPersistMode",
    "descendant_answers_from_record",
    "descendant_facts_from_answers",
    "persist_answers",
    "persist_patch",
    "profile_values_from_patch",
    "project_answers",
    "serialise_answers",
]

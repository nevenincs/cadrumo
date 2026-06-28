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
from typing import Literal

from pydantic import BaseModel

from ...core.setup_answers import register_project_answers as _register_project_answers
from ..user_profile._orchestration import register_active_profile, set_active_fields
from ..workflow._errors import WorkflowInputMismatchError
from ..workflow._models import WorkflowState
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
    from ._widgets import validate_widget_answer

    questions = _question_by_id(flow)
    facts: list[UserProfileFact] = []
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
        facts.append(UserProfileFact(path=question.profile_key, value=validated))
    return set_active_fields(state, tuple(facts))


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


_register_project_answers(project_answers)

__all__ = [
    "WizardPersistMode",
    "persist_answers",
    "persist_patch",
    "project_answers",
    "serialise_answers",
]

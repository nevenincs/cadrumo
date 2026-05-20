"""Persistence adapter for wizard answers.

Serialises a typed answers model back to canonical-token strings, then
persists profile facts through canonical user-profile orchestration.
The reverse projection (``project_answers``) builds the typed answers
model from a raw canonical-token dict.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from pydantic import BaseModel

from ..user_profile._orchestration import register_active_profile, set_active_fields
from ..workflow._models import WorkflowState
from ._models import WizardFlow, WizardQuestion


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


def serialise_answers(flow: WizardFlow, answers: BaseModel) -> dict[str, str]:
    """Project a typed answers model into the canonical-token dict.

    Only profile-bound questions contribute a key.
    """

    typed = answers.model_dump()
    mapping = _field_to_question(flow)
    result: dict[str, str] = {}
    for field_name, value in typed.items():
        question = mapping.get(field_name)
        if question is None or question.profile_key is None:
            continue
        result[question.profile_key] = _canonicalise(question, value)
    return result


def persist_answers(
    flow: WizardFlow,
    answers: BaseModel,
    *,
    state: WorkflowState,
    profile_name: str,
    profile_existed: bool,
) -> WorkflowState:
    """Persist ``answers`` into the profile bucket and return updated state.

    Each profile-bound question contributes one canonical-token entry to
    the profile bucket.

    ``profile_existed`` is the create-vs-edit discriminator. It MUST be
    captured by the caller BEFORE any pointer or manifest write — once
    the wizard pre-writes the active-profile pointer (the engine-URL
    load-order requirement), a re-derived check inside this function
    can no longer tell a first-run create from an edit. ``False``
    routes to :func:`register_active_profile` (which refuses a
    duplicate name); ``True`` routes to the edit path.
    """

    from ...domain.user_profile import ProfileNotFoundError, UserProfileFact

    canonical = serialise_answers(flow, answers)
    facts = tuple(UserProfileFact(path=path, value=value) for path, value in canonical.items() if value)
    if not profile_existed:
        return register_active_profile(
            state,
            profile_id=profile_name,
            display_name=profile_name,
            facts=facts,
        )
    try:
        return set_active_fields(state, facts)
    except ProfileNotFoundError:
        return register_active_profile(
            state,
            profile_id=profile_name,
            display_name=profile_name,
            facts=facts,
        )


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
    """Parse a canonical token into the question's declared answer type."""

    answer_type = question.answer_type
    if answer_type is bool:
        return raw == "true"
    if answer_type is int:
        return int(raw) if raw else 0
    if answer_type is Path:
        return Path(raw) if raw else Path()
    return raw


__all__ = [
    "persist_answers",
    "project_answers",
    "serialise_answers",
]

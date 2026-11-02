"""Help for profile fields, remapped from the setup wizard's question copy.

The setup wizard is where the product already explains each profile field.
Every question names the profile path it writes (``profile_key``), carries a
prompt, may carry a help text, and describes the choices that need a
description. This module joins that copy onto the path, so every surface that
shows a field -- the terminal manager, the desktop profile page and any other
reader of the overview stream -- shows the words the wizard uses, from one
producer, and none of them keeps a help catalogue of its own.

The join is exact: a path has help when a wizard question writes it, and its
help is that question's copy and nothing else. A field no question writes has
no help here; its surface falls back to the schema's own description.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel

from ...core.i18n.render import tr
from ...core.models import STRICT_FROZEN_CONFIG

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping

    from ...domain.user_profile.values import UserProfileFact
    from ..wizard.models import WizardFlow, WizardQuestion


class ProfileFieldEjercicioStatement(BaseModel):
    """What one stored fact states for the ejercicio its window starts in."""

    model_config = STRICT_FROZEN_CONFIG

    ejercicio: int
    value: str


class ProfileFieldEjercicioAnswer(BaseModel):
    """The wizard questions a field stated per ejercicio is answered through, and what it states so far.

    A surface submits these two questions in one profile patch, so a dated
    answer takes the route every other wizard answer takes.
    """

    model_config = STRICT_FROZEN_CONFIG

    question_id: str
    year_question_id: str
    statements: tuple[ProfileFieldEjercicioStatement, ...] = ()


def profile_field_help(flow: WizardFlow, *, locale: str | None = None) -> Mapping[str, tuple[str, ...]]:
    """Return the wizard's copy for every profile path a question writes.

    Args:
        flow: The setup flow built for the caller's pinned authority, so the
            choices carry the vocabulary the same generation validates.
        locale: Language code; the active output language when ``None``.

    Returns:
        One entry per profile path a question writes. Each entry holds, in
        order, the question's prompt, its help text when it has one, and one
        ``label: description`` line for each choice that carries a description.
    """
    return {
        question.profile_key: _question_help(question, locale=locale)
        for section in flow.sections
        for question in section.questions
        if question.profile_key is not None
    }


def profile_field_ejercicio_answers(
    flow: WizardFlow, facts: Iterable[UserProfileFact]
) -> Mapping[str, ProfileFieldEjercicioAnswer]:
    """Return, per path the setup flow states per ejercicio, its questions and its stored statements."""
    from ...domain.user_profile.setup_answers import EJERCICIO_STATED_PROFILE_PATHS
    from ..wizard.imputation_election import YEAR_QUESTION_ID

    stored = tuple(facts)
    return {
        question.profile_key: ProfileFieldEjercicioAnswer(
            question_id=question.id,
            year_question_id=YEAR_QUESTION_ID,
            statements=_ejercicio_statements(question.profile_key, stored),
        )
        for section in flow.sections
        for question in section.questions
        if question.profile_key in EJERCICIO_STATED_PROFILE_PATHS
    }


def _ejercicio_statements(path: str, facts: tuple[UserProfileFact, ...]) -> tuple[ProfileFieldEjercicioStatement, ...]:
    statements: list[ProfileFieldEjercicioStatement] = []
    for fact in facts:
        if fact.path == path and fact.valid_from is not None and fact.value is not None:
            statements.append(ProfileFieldEjercicioStatement(ejercicio=fact.valid_from.year, value=_token(fact.value)))
    return tuple(sorted(statements, key=lambda statement: statement.ejercicio))


def _token(value: object) -> str:
    return ("true" if value else "false") if isinstance(value, bool) else str(value)


def _question_help(question: WizardQuestion, *, locale: str | None) -> tuple[str, ...]:
    lines = [tr(question.prompt, locale=locale)]
    if question.help is not None:
        lines.append(tr(question.help, locale=locale))
    lines.extend(
        f"{tr(choice.label, locale=locale)}: {tr(choice.description, locale=locale)}"
        for choice in question.choices
        if choice.description is not None
    )
    return tuple(lines)


__all__ = ["profile_field_help"]

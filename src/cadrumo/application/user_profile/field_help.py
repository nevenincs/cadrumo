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

from ...core.i18n.render import tr

if TYPE_CHECKING:
    from collections.abc import Mapping

    from ..wizard.models import WizardFlow, WizardQuestion


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

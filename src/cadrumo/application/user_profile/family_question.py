"""The household questions a profile answers beside its rows, in the words setup asks them.

A single-parent family unit is asked whether the taxpayer lives with the father
or mother of a child in the unit (Art. 84.2.4º LIRPF), because the joint
taxation reduction does not apply while they do. The question, its wording and
the moment it is relevant all belong to the setup flow, so this projection
reads them from that flow rather than keeping a copy: it serves the question
only while the flow would ask it, and a question the flow does not ask is not
served at all.

The saved answer is three-valued. ``"true"`` and ``"false"`` are stated answers;
``None`` means nothing is stated, which is not a "no". A surface draws the three
apart and never fills the third with either of the others.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Final, Literal

from pydantic import BaseModel

from ...core.models import STRICT_FROZEN_CONFIG
from ..wizard.catalogue import build_setup_flow
from .overview import ProfileFieldChoice
from .question_view import profile_question_items

if TYPE_CHECKING:
    from ...domain.calculations.registry.authority import PinnedAuthorityOperation

#: The setup question that asks whether a single parent lives with the child's other parent.
CONVIVE_CON_OTRO_PROGENITOR_QUESTION_ID: Final = "family-convive-con-otro-progenitor"


class ProfileViewFamilyQuestionItem(BaseModel):
    """One household question with the answer the profile states for it, if any."""

    model_config = STRICT_FROZEN_CONFIG

    kind: Literal["family_question"] = "family_question"
    question_id: str
    path: str
    prompt: str
    help: str | None
    #: ``"true"`` or ``"false"`` when stated, ``None`` when the profile states nothing.
    saved_value: Literal["true", "false"] | None
    choices: tuple[ProfileFieldChoice, ...]


def family_question_items(
    values: Mapping[str, str],
    *,
    operation: PinnedAuthorityOperation,
) -> tuple[ProfileViewFamilyQuestionItem, ...]:
    """Return the household questions the setup flow asks of this profile now, in a fixed order."""
    served = {item.question_id: item for item in profile_question_items(build_setup_flow(operation), values)}
    asked = served.get(CONVIVE_CON_OTRO_PROGENITOR_QUESTION_ID)
    if asked is None or asked.visibility != "visible":
        return ()
    stated = asked.saved_value.strip().lower() if asked.saved_value is not None else None
    return (
        ProfileViewFamilyQuestionItem(
            question_id=asked.question_id,
            path=asked.path,
            prompt=asked.prompt,
            help=asked.help,
            saved_value="true" if stated == "true" else "false" if stated == "false" else None,
            choices=tuple(ProfileFieldChoice(value=choice.value, label=choice.label) for choice in asked.choices),
        ),
    )


__all__ = [
    "CONVIVE_CON_OTRO_PROGENITOR_QUESTION_ID",
    "ProfileViewFamilyQuestionItem",
    "family_question_items",
]

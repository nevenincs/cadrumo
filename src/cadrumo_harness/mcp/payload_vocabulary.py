"""What a described operation's payload may name, where its request schema cannot enumerate it.

A request schema states the shape of a payload. Some payloads also name things
out of a vocabulary that is not a fixed list: the profile patch names its
answers by question id, and the questions are built from the published tax
authority. The command line offers each one as an option of its own, so a
person reads them in its help. A described contract carries the same list here,
built from the same flow the command is built from.
"""

from __future__ import annotations

from typing import Any, Final

from cadrumo.application.user_profile.profile_operation_contracts import PROFILE_PATCH_OPERATION_DEFINITION_ID
from cadrumo.domain.calculations.registry.authority_store import AuthorityStoreError
from cadrumo.domain.calculations.registry.errors import RegistryError

from .protocol_contract import refusal_code

PAYLOAD_VOCABULARY_MEMBER: Final = "payload_vocabulary"
"""The member of a ``describe`` reply that carries a payload's vocabulary."""

_PROFILE_ANSWER_PATH: Final = "values[].question_id"


def _profile_questions() -> dict[str, Any]:
    """List every profile answer a patch may set, as the command line's own options name them.

    Imported on use, so that describing any other operation loads none of it.
    """
    from cadrumo.application.wizard.catalogue import build_setup_flow
    from cadrumo.core.i18n.render import tr
    from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority

    with bundled_indexed_authority().operation() as operation:
        flow = build_setup_flow(operation)
        questions = [
            {
                "question_id": question.id,
                "meaning": tr(question.prompt),
                "required": question.required,
                **(
                    {"choices": [{"value": choice.value, "meaning": tr(choice.label)} for choice in question.choices]}
                    if question.choices
                    else {}
                ),
            }
            for section in flow.sections
            for question in section.questions
            # A question that stores nothing is asked only to route the interactive flow.
            if question.profile_key is not None
        ]
        return {
            "path": _PROFILE_ANSWER_PATH,
            "logical_generation": operation.generation.logical_generation,
            "questions": questions,
        }


def payload_vocabulary(definition_id: str) -> dict[str, Any] | None:
    """Return the vocabulary one operation's payload names, or ``None`` where its schema says everything.

    A vocabulary that cannot be read does not withhold the contract: the
    reply then names the path and why its values are not listed.
    """
    if definition_id != PROFILE_PATCH_OPERATION_DEFINITION_ID:
        return None
    try:
        return _profile_questions()
    except (AuthorityStoreError, RegistryError) as error:
        return {"path": _PROFILE_ANSWER_PATH, "unavailable": refusal_code(error)}

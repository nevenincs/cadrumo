"""What a described operation's payload may name, where its request schema cannot enumerate it.

A request schema states the shape of a payload. Some payloads also name things
out of a vocabulary that is not a fixed list: the profile patch names its
answers by question id, and the questions are built from the published tax
authority. The command line offers each one as an option of its own, so a
person reads them in its help. A described contract points to saved profile
questions, with optional bounded catalogue pages built from the same flow.
"""

from __future__ import annotations

from typing import Any, Final

from cadrumo.application.user_profile.profile_operation_contracts import PROFILE_PATCH_OPERATION_DEFINITION_ID
from cadrumo.core.hashing import canonical_json_bytes
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
    from cadrumo.application.reference_catalogue import read_pinned_reference
    from cadrumo.application.wizard.catalogue import build_setup_flow
    from cadrumo.core.i18n.render import tr

    flow = read_pinned_reference(build_setup_flow)
    questions = [
        {
            "question_id": question.id,
            "profile_path": question.profile_key,
            "meaning": tr(question.prompt),
            **({"help": tr(question.help)} if question.help is not None else {}),
            "required": question.required,
            **(
                {"choices": [{"value": choice.value, "meaning": tr(choice.label)} for choice in question.choices]}
                if question.choices
                else {}
            ),
        }
        for section in flow.report.sections
        for question in section.questions
        # A question that stores nothing is asked only to route the interactive flow.
        if question.profile_key is not None
    ]
    return {
        "path": _PROFILE_ANSWER_PATH,
        "logical_generation": flow.generation.logical_generation,
        "questions": questions,
    }


def payload_vocabulary(definition_id: str, *, limit: int = 0, cursor: int = 0) -> dict[str, Any] | None:
    """Return the vocabulary one operation's payload names, or ``None`` where its schema says everything.

    A vocabulary that cannot be read does not withhold the contract: the
    reply then names the path and why its values are not listed.
    """
    if definition_id != PROFILE_PATCH_OPERATION_DEFINITION_ID:
        return None
    # Most callers already have the relevant IDs from the saved profile questions.
    # Do not bury the mutation schema beneath the entire setup catalogue.
    source = {"definition_id": "user-profile.view", "page_kind": "questions"}
    if limit == 0:
        return {"path": _PROFILE_ANSWER_PATH, "saved_answers_source": source, "next_cursor": cursor}
    try:
        catalogue = _profile_questions()
        questions = catalogue.pop("questions")
        page: list[dict[str, Any]] = []
        for question in questions[cursor : cursor + min(limit, 20)]:
            if len(canonical_json_bytes([*page, question])) > 8_000:
                break
            page.append(question)
        next_cursor = cursor + len(page)
        return {
            **catalogue,
            "saved_answers_source": source,
            "questions": page,
            "total": len(questions),
            "next_cursor": next_cursor if page and next_cursor < len(questions) else None,
            **({"unavailable": "question_exceeds_page_limit"} if not page and cursor < len(questions) else {}),
        }
    except (AuthorityStoreError, RegistryError) as error:
        return {"path": _PROFILE_ANSWER_PATH, "unavailable": refusal_code(error)}

"""Describing the profile patch names every answer it may set, as the command line's help does.

The patch's request schema says only that a question id is text. The ids are
the questions of the setup flow, which is built from the published tax
authority, and the command line turns each one into an option. The vocabulary
a described contract carries is held here to that same flow and to the patch's
own reading of an answer, and the contracts described are the real registered
ones.
"""

from __future__ import annotations

from contextlib import suppress
from typing import Any, NoReturn, cast
from uuid import UUID, uuid4

import pytest

from cadrumo.application.auth.auth_read_contracts import AUTH_READ_OPERATION_DEFINITION_ID
from cadrumo.application.auth.read_operation import build_auth_read_definition, build_auth_read_registration
from cadrumo.application.operations.registry import (
    OperationFrontendProjection,
    OperationPublicDefinitionDescriptionV1,
    OperationRegistry,
)
from cadrumo.application.user_profile.operations import (
    USER_PROFILE_OPERATION_DEFINITIONS,
    build_user_profile_operation_registrations,
)
from cadrumo.application.user_profile.profile_operation_contracts import (
    PROFILE_FIELD_MUTATION_OPERATION_DEFINITION_ID,
    PROFILE_PATCH_OPERATION_DEFINITION_ID,
)
from cadrumo.application.wizard import catalogue as wizard_catalogue
from cadrumo.application.wizard.catalogue import build_setup_flow
from cadrumo.application.wizard.errors import WizardValidationError
from cadrumo.application.wizard.persistence import profile_values_from_patch
from cadrumo.application.workflow.errors import WorkflowInputMismatchError
from cadrumo.core.config import override_settings
from cadrumo.core.hashing import canonical_json_bytes
from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority
from cadrumo.domain.calculations.registry.errors import RegistryError
from cadrumo_client.transport.frontend_client import FrontendClient

from .. import payload_vocabulary as vocabulary_module
from ..payload_vocabulary import payload_vocabulary
from ..protocol_contract import MCP_TOOL_CATALOGUE
from ..runtime_adapter import RuntimeMcpAdapter

pytestmark = [pytest.mark.integration, pytest.mark.hex_core]


def _unused_ports(*_args: object, **_kwargs: object) -> NoReturn:
    raise AssertionError("a contract description must not construct executor ports")


class _DescribingClient:
    """An admitted lease whose runtime describes the real profile operations and one plain read."""

    def __init__(self, profile_id: UUID) -> None:
        auth = build_auth_read_definition(_unused_ports)
        self._registry = OperationRegistry(
            definitions=(auth, *USER_PROFILE_OPERATION_DEFINITIONS),
            public_registrations=(
                build_auth_read_registration(auth),
                *build_user_profile_operation_registrations(USER_PROFILE_OPERATION_DEFINITIONS),
            ),
        )
        self.profile_id = profile_id
        self.frontend = OperationFrontendProjection.EXTERNAL_CLIENT
        self.session_id = uuid4()

    def describe(self, definition_id: str, *, deadline: float) -> OperationPublicDefinitionDescriptionV1:
        assert deadline > 0
        return self._registry.describe_public_definition(definition_id)

    def close(self) -> None:
        return None


async def _describe(definition_id: str, **options: int) -> dict[str, Any]:
    client = _DescribingClient(uuid4())
    adapter = RuntimeMcpAdapter(profile_id=client.profile_id, client=cast(FrontendClient, client))
    try:
        with override_settings(cadrumo_output_language="en"):
            return await adapter.call("describe", {"definition_id": definition_id, **options})
    finally:
        await adapter.close()


@pytest.mark.anyio
async def test_default_description_keeps_the_patch_schema_visible_without_dumping_the_catalogue() -> None:
    patch = await _describe(PROFILE_PATCH_OPERATION_DEFINITION_ID)
    field = await _describe(PROFILE_FIELD_MUTATION_OPERATION_DEFINITION_ID)
    read = await _describe(AUTH_READ_OPERATION_DEFINITION_ID)

    assert patch["outcome"] == field["outcome"] == read["outcome"] == "described"
    assert "payload_vocabulary" not in field and "payload_vocabulary" not in read
    vocabulary = patch["payload_vocabulary"]
    assert vocabulary["path"] == "values[].question_id"
    assert vocabulary["saved_answers_source"] == {"definition_id": "user-profile.view", "page_kind": "questions"}
    assert "questions" not in vocabulary
    assert len(canonical_json_bytes(patch)) < 8_000
    # The schema itself still says only that the id is text, which is why the list rides beside it.
    question_id = patch["description"]["request_json_schema"]["$defs"]["ProfilePatchValue"]["properties"]["question_id"]
    assert "enum" not in question_id
    schema = patch["description"]["request_json_schema"]
    assert "values" in schema["properties"]
    assert {"profile_id", "expected_revision", "expected_content_digest"} <= set(schema["required"])


@pytest.mark.anyio
async def test_optional_vocabulary_pages_retain_complete_question_meanings_and_choices() -> None:
    questions: dict[str, Any] = {}
    cursor = 0
    generation = None
    while True:
        patch = await _describe(PROFILE_PATCH_OPERATION_DEFINITION_ID, vocabulary_limit=20, vocabulary_cursor=cursor)
        vocabulary = patch["payload_vocabulary"]
        assert len(canonical_json_bytes(vocabulary["questions"])) <= 8_000
        assert len(canonical_json_bytes(patch)) < 16_000
        assert "unavailable" not in vocabulary
        assert generation is None or generation == vocabulary["logical_generation"]
        generation = vocabulary["logical_generation"]
        for question in vocabulary["questions"]:
            assert question["question_id"] not in questions
            questions[question["question_id"]] = question
        if vocabulary["next_cursor"] is None:
            break
        assert vocabulary["next_cursor"] > cursor
        cursor = vocabulary["next_cursor"]
    assert len(questions) == vocabulary["total"] > 20
    for question in questions.values():
        assert question["meaning"].strip() and isinstance(question["required"], bool)
        # A meaning is the sentence a person reads, never the key it is looked up by.
        assert not question["meaning"].startswith("wizard.")
    assert questions["tax-id"]["meaning"] and "choices" not in questions["tax-id"]
    regime = questions["iva-regime"]["choices"]
    assert len(regime) > 1 and all(choice["value"] and choice["meaning"].strip() for choice in regime)


def test_the_vocabulary_is_the_flow_the_command_line_is_built_from_and_the_patch_reads_answers_by() -> None:
    with override_settings(cadrumo_output_language="en"):
        listed: list[str] = []
        cursor = 0
        while True:
            vocabulary = payload_vocabulary(PROFILE_PATCH_OPERATION_DEFINITION_ID, limit=20, cursor=cursor)
            assert vocabulary is not None and "unavailable" not in vocabulary
            listed.extend(question["question_id"] for question in vocabulary["questions"])
            if vocabulary["next_cursor"] is None:
                break
            assert vocabulary["next_cursor"] > cursor
            cursor = vocabulary["next_cursor"]

    with bundled_indexed_authority().operation() as operation:
        flow = build_setup_flow(operation)
        assert vocabulary["logical_generation"] == operation.generation.logical_generation
        stored = {
            question.id
            for section in flow.sections
            for question in section.questions
            if (question.profile_key is not None and question.profile_key)
        }
        asked_only = {
            question.id
            for section in flow.sections
            for question in section.questions
            if not (question.profile_key is not None and question.profile_key)
        }
        # The patch's own reading of an answer knows every listed id, and refuses one that is not a question.
        for question_id in listed:
            # A blank may be refused as a value for that question; it is never refused as an unknown one.
            with suppress(WizardValidationError):
                profile_values_from_patch(flow, {question_id: ""})
        with pytest.raises(WorkflowInputMismatchError):
            profile_values_from_patch(flow, {"synthetic-not-a-question": "x"})

    assert set(listed) == stored and len(listed) == len(stored)
    assert not asked_only & set(listed)


@pytest.mark.anyio
async def test_a_vocabulary_that_cannot_be_read_does_not_withhold_the_contract(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def unpublished(_operation: object) -> NoReturn:
        raise RegistryError("synthetic: the published authority cannot be read")

    # Only the flow fails to build, so the contract itself is still described.
    monkeypatch.setattr(wizard_catalogue, "build_setup_flow", unpublished)

    patch = await _describe(PROFILE_PATCH_OPERATION_DEFINITION_ID, vocabulary_limit=10)

    assert patch["outcome"] == "described" and patch["description"]["request_json_schema"]
    assert patch["payload_vocabulary"] == {
        "path": "values[].question_id",
        "unavailable": "published_authority_invalid",
    }
    assert vocabulary_module.payload_vocabulary(AUTH_READ_OPERATION_DEFINITION_ID) is None


def test_the_describe_tool_says_where_the_question_ids_are() -> None:
    (described,) = [description for name, description, _schema in MCP_TOOL_CATALOGUE if name == "describe"]

    assert "payload_vocabulary" in described and PROFILE_PATCH_OPERATION_DEFINITION_ID in described


def test_oversized_question_preserves_the_bound_without_a_nonadvancing_cursor(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        vocabulary_module,
        "_profile_questions",
        lambda: {"path": "values[].question_id", "logical_generation": "test", "questions": [{"help": "x" * 9_000}]},
    )
    page = payload_vocabulary(PROFILE_PATCH_OPERATION_DEFINITION_ID, limit=20)
    assert page is not None
    assert page["questions"] == [] and page["next_cursor"] is None
    assert page["unavailable"] == "question_exceeds_page_limit"
    assert page["saved_answers_source"]["definition_id"] == "user-profile.view"

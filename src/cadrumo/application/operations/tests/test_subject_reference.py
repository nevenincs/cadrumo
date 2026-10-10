"""A definition declares the one form its subject takes, and the contract digest binds it."""

from __future__ import annotations

from uuid import UUID

import pytest
from pydantic import BaseModel, ValidationError

from ....core.models import STRICT_FROZEN_CONFIG
from ..capabilities import RECORDED_IDEMPOTENT_SECURE_INPUT_UPDATE_CAPABILITIES
from ..operation_definition import OperationDefinition, build_single_phase_definition
from ..owner import OperationExecutorContext
from ..registry import (
    OperationFrontendProjection,
    OperationPublicDefinitionContractV1,
    OperationPublicDefinitionRegistrationV1,
)
from ..subject_reference import OperationSubjectKind, OperationSubjectReferenceV1, expected_operation_subject

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PROFILE_ID = UUID("5aa00000-0000-4000-8000-0000000000aa")
_PROFILE_SUBJECT = "profile:5aa00000-0000-4000-8000-0000000000aa"
_WORK_UNIT = "a" * 64
_NESTED_WORK_UNIT = "b" * 64
_REVISION = "c" * 64


class _Baseline(BaseModel):
    model_config = STRICT_FROZEN_CONFIG

    work_unit_id: str
    profile_id: UUID


class _Request(BaseModel):
    model_config = STRICT_FROZEN_CONFIG

    work_unit_id: str
    selected_work_unit_id: str | None
    calculation_revision_id: str
    baseline: _Baseline
    earlier_baseline: _Baseline | None
    attempt: int


class _Result(BaseModel):
    model_config = STRICT_FROZEN_CONFIG

    name: str


class _Executor:
    async def execute(self, request: object, context: OperationExecutorContext) -> str | None:
        del request, context
        return None


def _request(*, selected_work_unit_id: str | None = None) -> _Request:
    return _Request(
        work_unit_id=_WORK_UNIT,
        selected_work_unit_id=selected_work_unit_id,
        calculation_revision_id=_REVISION,
        baseline=_Baseline(work_unit_id=_NESTED_WORK_UNIT, profile_id=_PROFILE_ID),
        earlier_baseline=None,
        attempt=1,
    )


def _definition(subject_reference: OperationSubjectReferenceV1) -> OperationDefinition:
    return build_single_phase_definition(
        definition_id="test.subject",
        request_type=_Request,
        subject_reference=subject_reference,
        result_type=_Result,
        executor_type=_Executor,
        build=_Executor,
        capabilities=RECORDED_IDEMPOTENT_SECURE_INPUT_UPDATE_CAPABILITIES,
        permitted_frontends=frozenset({OperationFrontendProjection.TUI}),
    )


def _contract(subject_reference: OperationSubjectReferenceV1) -> OperationPublicDefinitionContractV1:
    return OperationPublicDefinitionRegistrationV1.compose_request_only(
        definition=_definition(subject_reference),
        request_schema_id="test.subject.request",
    ).contract


def test_each_constructor_declares_only_what_its_kind_reads() -> None:
    assert OperationSubjectReferenceV1.profile().model_dump(mode="json") == {
        "kind": "profile",
        "payload_path": [],
        "literal": None,
    }
    assert OperationSubjectReferenceV1.payload_field("baseline", "work_unit_id").model_dump(mode="json") == {
        "kind": "payload_field",
        "payload_path": ["baseline", "work_unit_id"],
        "literal": None,
    }
    assert OperationSubjectReferenceV1.payload_field_or_profile("work_unit_id").model_dump(mode="json") == {
        "kind": "payload_field_or_profile",
        "payload_path": ["work_unit_id"],
        "literal": None,
    }
    assert OperationSubjectReferenceV1.stored_work_unit("calculation_revision_id").model_dump(mode="json") == {
        "kind": "stored_work_unit",
        "payload_path": ["calculation_revision_id"],
        "literal": None,
    }
    assert OperationSubjectReferenceV1.fixed("local-reader:runtime").model_dump(mode="json") == {
        "kind": "fixed",
        "payload_path": [],
        "literal": "local-reader:runtime",
    }


@pytest.mark.parametrize(
    ("kind", "payload_path", "literal"),
    [
        (OperationSubjectKind.PROFILE, ("work_unit_id",), None),
        (OperationSubjectKind.PROFILE, (), "profile:active"),
        (OperationSubjectKind.PAYLOAD_FIELD, (), None),
        (OperationSubjectKind.PAYLOAD_FIELD, ("work_unit_id",), "fixed"),
        (OperationSubjectKind.PAYLOAD_FIELD_OR_PROFILE, (), None),
        (OperationSubjectKind.STORED_WORK_UNIT, (), None),
        (OperationSubjectKind.STORED_WORK_UNIT, ("calculation_revision_id",), "fixed"),
        (OperationSubjectKind.FIXED, (), None),
        (OperationSubjectKind.FIXED, ("work_unit_id",), "fixed"),
    ],
)
def test_a_declaration_whose_members_contradict_its_kind_is_refused(
    kind: OperationSubjectKind, payload_path: tuple[str, ...], literal: str | None
) -> None:
    with pytest.raises(ValidationError):
        OperationSubjectReferenceV1(kind=kind, payload_path=payload_path, literal=literal)


@pytest.mark.parametrize("step", ["", "Work-Unit", "work unit", "work_unit_id.nested"])
def test_a_path_step_that_is_not_one_field_name_is_refused(step: str) -> None:
    with pytest.raises(ValidationError):
        OperationSubjectReferenceV1.payload_field(step)


def test_a_declaration_has_no_defaults_to_fall_back_on() -> None:
    with pytest.raises(ValidationError):
        OperationSubjectReferenceV1.model_validate({"kind": OperationSubjectKind.PROFILE})


@pytest.mark.parametrize(
    ("reference", "expected"),
    [
        (OperationSubjectReferenceV1.profile(), _PROFILE_SUBJECT),
        (OperationSubjectReferenceV1.fixed("local-reader:runtime"), "local-reader:runtime"),
        (OperationSubjectReferenceV1.payload_field("work_unit_id"), _WORK_UNIT),
        (OperationSubjectReferenceV1.payload_field("baseline", "work_unit_id"), _NESTED_WORK_UNIT),
        (OperationSubjectReferenceV1.payload_field("baseline", "profile_id"), "5aa00000-0000-4000-8000-0000000000aa"),
        (OperationSubjectReferenceV1.payload_field_or_profile("selected_work_unit_id"), _PROFILE_SUBJECT),
        (OperationSubjectReferenceV1.stored_work_unit("calculation_revision_id"), None),
    ],
)
def test_the_typed_request_and_its_json_object_render_the_same_subject(
    reference: OperationSubjectReferenceV1, expected: str | None
) -> None:
    request = _request()

    assert expected_operation_subject(reference, profile_id=_PROFILE_ID, payload=request) == expected
    assert (
        expected_operation_subject(reference, profile_id=_PROFILE_ID, payload=request.model_dump(mode="json"))
        == expected
    )


def test_a_field_that_falls_back_to_the_profile_is_the_subject_when_it_is_set() -> None:
    reference = OperationSubjectReferenceV1.payload_field_or_profile("selected_work_unit_id")
    request = _request(selected_work_unit_id=_NESTED_WORK_UNIT)

    assert expected_operation_subject(reference, profile_id=_PROFILE_ID, payload=request) == _NESTED_WORK_UNIT
    assert (
        expected_operation_subject(reference, profile_id=_PROFILE_ID, payload={"selected_work_unit_id": _WORK_UNIT})
        == _WORK_UNIT
    )
    assert expected_operation_subject(reference, profile_id=_PROFILE_ID, payload={}) == _PROFILE_SUBJECT


@pytest.mark.parametrize(
    ("reference", "payload"),
    [
        (OperationSubjectReferenceV1.payload_field("work_unit_id"), {}),
        (OperationSubjectReferenceV1.payload_field("work_unit_id"), {"work_unit_id": None}),
        (OperationSubjectReferenceV1.payload_field("baseline", "work_unit_id"), {"baseline": {}}),
        (OperationSubjectReferenceV1.payload_field("baseline", "work_unit_id"), {"baseline": _WORK_UNIT}),
        (OperationSubjectReferenceV1.payload_field("attempt"), {"attempt": 1}),
        (OperationSubjectReferenceV1.payload_field("baseline"), {"baseline": {"work_unit_id": _WORK_UNIT}}),
    ],
)
def test_a_payload_that_does_not_carry_its_subject_field_is_refused(
    reference: OperationSubjectReferenceV1, payload: dict[str, object]
) -> None:
    with pytest.raises(ValueError, match="subject field"):
        expected_operation_subject(reference, profile_id=_PROFILE_ID, payload=payload)


@pytest.mark.parametrize(
    "reference",
    [
        OperationSubjectReferenceV1.profile(),
        OperationSubjectReferenceV1.fixed("local-reader:runtime"),
        OperationSubjectReferenceV1.payload_field("work_unit_id"),
        OperationSubjectReferenceV1.payload_field("baseline", "profile_id"),
        OperationSubjectReferenceV1.payload_field_or_profile("selected_work_unit_id"),
        OperationSubjectReferenceV1.stored_work_unit("baseline", "work_unit_id"),
    ],
)
def test_a_definition_carries_a_declaration_its_request_type_can_honour(
    reference: OperationSubjectReferenceV1,
) -> None:
    assert _definition(reference).subject_reference == reference


@pytest.mark.parametrize(
    ("reference", "message"),
    [
        (OperationSubjectReferenceV1.payload_field("unit_id"), "does not declare"),
        (OperationSubjectReferenceV1.payload_field("baseline", "unit_id"), "does not declare"),
        (OperationSubjectReferenceV1.stored_work_unit("revision_id"), "does not declare"),
        (OperationSubjectReferenceV1.payload_field("selected_work_unit_id"), "may be absent exactly when"),
        (OperationSubjectReferenceV1.stored_work_unit("selected_work_unit_id"), "may be absent exactly when"),
        (OperationSubjectReferenceV1.payload_field_or_profile("work_unit_id"), "may be absent exactly when"),
        (OperationSubjectReferenceV1.payload_field("work_unit_id", "nested"), "not one nested model"),
        (OperationSubjectReferenceV1.payload_field("earlier_baseline", "work_unit_id"), "not one nested model"),
    ],
)
def test_a_definition_refuses_a_declaration_its_request_type_cannot_honour(
    reference: OperationSubjectReferenceV1, message: str
) -> None:
    with pytest.raises(ValidationError, match=message):
        _definition(reference)


def test_the_public_contract_states_the_declaration_and_its_digest_binds_it() -> None:
    profile = _contract(OperationSubjectReferenceV1.profile())
    field = _contract(OperationSubjectReferenceV1.payload_field("work_unit_id"))
    nested = _contract(OperationSubjectReferenceV1.payload_field("baseline", "work_unit_id"))
    stored = _contract(OperationSubjectReferenceV1.stored_work_unit("calculation_revision_id"))

    assert field.subject_reference == OperationSubjectReferenceV1.payload_field("work_unit_id")
    assert field.model_dump(mode="json")["subject_reference"] == {
        "kind": "payload_field",
        "payload_path": ["work_unit_id"],
        "literal": None,
    }
    digests = {item.definition_contract_digest for item in (profile, field, nested, stored)}
    assert len(digests) == 4
    assert _contract(OperationSubjectReferenceV1.profile()).definition_contract_digest == (
        profile.definition_contract_digest
    )
    restated = {name: getattr(field, name) for name in OperationPublicDefinitionContractV1.model_fields}
    restated["subject_reference"] = OperationSubjectReferenceV1.profile()
    with pytest.raises(ValidationError, match="digest does not reproduce"):
        OperationPublicDefinitionContractV1.model_validate(restated)

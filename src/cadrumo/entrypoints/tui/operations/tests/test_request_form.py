"""The request form is derived from the public request contract and validated by the request model.

The subject a form derives is held, for every registered operation, to what
its contract's subject reference declares: the admitted profile, a fixed
literal, the request field it names, or the work unit a person names because
only the store knows it.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from uuid import UUID

import pytest

from .....application.operations.subject_reference import OperationSubjectKind, OperationSubjectReferenceV1
from .....core.errors.error_codes import build_error_envelope
from .....core.operations import profile_operation_subject
from .....core.period import PeriodError
from ....operation_composition import build_production_operation_registry
from ..catalogue import OperationCatalogueEntryV1, OperationCatalogueV1, build_operation_catalogue
from ..request_form import (
    RequestFieldKind,
    RequestFieldProblem,
    RequestFieldV1,
    derived_subject,
    field_texts,
    request_document,
    request_fields,
    subject_is_entered,
    validate_request,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_PROFILE_ID = UUID("7b1d5a52-3f0e-4c1e-9d55-0f3a2f6c8e11")
_SUBJECT_VALUE = "c0ffee00-0000-4000-8000-00000000beef"
_VIEW = "user-profile.view"


@lru_cache(maxsize=1)
def _catalogue() -> OperationCatalogueV1:
    return build_operation_catalogue(build_production_operation_registry())


def _entry(definition_id: str) -> OperationCatalogueEntryV1:
    entry = _catalogue().entry(definition_id)
    assert entry is not None
    return entry


def _fields(definition_id: str) -> tuple[RequestFieldV1, ...]:
    return request_fields(_entry(definition_id).input_json_schema, profile_id=_PROFILE_ID)


def _with_subject_field(reference: OperationSubjectReferenceV1, document: dict[str, object]) -> dict[str, object]:
    """Return ``document`` with the field its subject is read from set to a reference."""
    filled = dict(document)
    holder = filled
    for name in reference.payload_path[:-1]:
        current = holder.get(name)
        nested: dict[str, object] = (
            {str(key): value for key, value in current.items()} if isinstance(current, dict) else {}
        )
        holder[name] = nested
        holder = nested
    if reference.payload_path:
        holder[reference.payload_path[-1]] = _SUBJECT_VALUE
    return filled


def _declared_subject(reference: OperationSubjectReferenceV1, *, field_set: bool, entered: str | None) -> str | None:
    """Say what a submission's subject must be, from the declared form alone."""
    profile = profile_operation_subject(str(_PROFILE_ID))
    if reference.kind is OperationSubjectKind.PROFILE:
        return profile
    if reference.kind is OperationSubjectKind.FIXED:
        return reference.literal
    if reference.kind is OperationSubjectKind.PAYLOAD_FIELD:
        return _SUBJECT_VALUE if field_set else None
    if reference.kind is OperationSubjectKind.PAYLOAD_FIELD_OR_PROFILE:
        return _SUBJECT_VALUE if field_set else profile
    return entered


def test_every_registered_operation_yields_a_form_over_exactly_its_request_fields() -> None:
    for entry in _catalogue().entries:
        fields = request_fields(entry.input_json_schema, profile_id=_PROFILE_ID)
        properties = entry.input_json_schema.get("properties", {})
        assert isinstance(properties, dict)
        assert [field.name for field in fields] == list(properties), entry.definition_id
        assert [field.name for field in fields] == list(entry.input_type.model_fields), entry.definition_id
        for field in fields:
            if field.kind is RequestFieldKind.JSON and field.initial:
                json.loads(field.initial)
            if field.kind is RequestFieldKind.ENUM:
                assert field.choices, (entry.definition_id, field.name)


def test_the_profile_field_is_filled_with_the_session_profile_and_never_entered() -> None:
    fixed = 0
    for entry in _catalogue().entries:
        for field in request_fields(entry.input_json_schema, profile_id=_PROFILE_ID):
            if field.name == "profile_id" and field.kind is RequestFieldKind.UUID:
                assert field.session_fixed, entry.definition_id
                assert field.initial == str(_PROFILE_ID)
                fixed += 1
            else:
                assert not field.session_fixed, (entry.definition_id, field.name)
    assert fixed > 200


def test_the_derived_subject_is_what_the_contract_declares_for_every_operation() -> None:
    kinds: set[OperationSubjectKind] = set()
    for entry in _catalogue().entries:
        if entry.typed_operator_input:
            continue
        reference = entry.contract.subject_reference
        kinds.add(reference.kind)
        fields = request_fields(entry.input_json_schema, profile_id=_PROFILE_ID)
        untouched, _problems = request_document(fields, {field.name: field.initial for field in fields})
        documents = ((False, untouched), (True, _with_subject_field(reference, untouched)))
        for field_set, document in documents:
            for entered in (None, "unit-entered-by-a-person"):
                derived = derived_subject(
                    reference, profile_id=_PROFILE_ID, document=document, entered=entered, typed_operator_input=False
                )
                expected = _declared_subject(reference, field_set=field_set, entered=entered)
                assert derived == expected, (entry.definition_id, field_set, entered)
    assert kinds == set(OperationSubjectKind)


def test_a_person_names_the_subject_only_where_nothing_else_can() -> None:
    for entry in _catalogue().entries:
        reference = entry.contract.subject_reference
        expected = entry.typed_operator_input or reference.kind is OperationSubjectKind.STORED_WORK_UNIT
        assert subject_is_entered(reference, typed_operator_input=entry.typed_operator_input) is expected
        if entry.typed_operator_input:
            assert (
                derived_subject(reference, profile_id=_PROFILE_ID, document={}, entered=None, typed_operator_input=True)
                is None
            )
            assert (
                derived_subject(
                    reference, profile_id=_PROFILE_ID, document={}, entered=" unit-7 ", typed_operator_input=True
                )
                == "unit-7"
            )


def test_scalar_fields_are_typed_and_a_nested_field_is_edited_as_json() -> None:
    by_name = {field.name: field for field in _fields(_VIEW)}

    assert by_name["page_kind"].kind is RequestFieldKind.ENUM
    assert by_name["page_kind"].required
    assert "facts" in by_name["page_kind"].choice_labels
    assert by_name["cursor"].kind is RequestFieldKind.INTEGER
    assert by_name["cursor"].initial == "0"
    assert by_name["expected_revision"].kind is RequestFieldKind.INTEGER
    assert not by_name["expected_revision"].required
    assert by_name["page_kind"].description

    kinds = {
        field.kind
        for entry in _catalogue().entries
        for field in request_fields(entry.input_json_schema, profile_id=_PROFILE_ID)
    }
    assert kinds >= {
        RequestFieldKind.TEXT,
        RequestFieldKind.INTEGER,
        RequestFieldKind.BOOLEAN,
        RequestFieldKind.ENUM,
        RequestFieldKind.DATE,
        RequestFieldKind.UUID,
        RequestFieldKind.PATH,
        RequestFieldKind.JSON,
    }


def test_a_valid_request_is_the_request_model_the_operation_registers() -> None:
    entry = _entry(_VIEW)
    fields = _fields(_VIEW)
    texts = {field.name: field.initial for field in fields} | {"page_kind": "facts", "limit": "5"}

    document, problems = request_document(fields, texts)
    validation = validate_request(entry.input_type, document)

    assert problems == {}
    assert validation.payload is not None
    assert type(validation.payload) is entry.input_type
    assert json.loads(validation.payload.model_dump_json()) == {
        "profile_id": str(_PROFILE_ID),
        "page_kind": "facts",
        "cursor": 0,
        "limit": 5,
        "expected_revision": None,
        "expected_content_digest": None,
        "output_language": "es",
    }


def test_the_request_model_s_refusals_are_reported_against_their_fields_without_the_entered_value() -> None:
    entry = _entry(_VIEW)
    fields = _fields(_VIEW)
    rejected_digest = "not-a-digest-" + "9" * 20
    texts = {field.name: field.initial for field in fields} | {
        "limit": "4096",
        "expected_content_digest": rejected_digest,
    }

    document, problems = request_document(fields, texts)
    validation = validate_request(entry.input_type, document)

    assert problems == {}
    assert validation.payload is None
    assert set(validation.field_errors) == {"page_kind", "limit", "expected_content_digest"}
    assert validation.general_errors == ()
    rendered = json.dumps(validation.field_errors)
    assert rejected_digest not in rendered
    assert "4096" not in rendered


def test_a_registered_refusal_a_validator_raises_is_shown_in_the_words_the_command_line_prints() -> None:
    entry = _entry("modelo.bindings.list")
    document: dict[str, object] = {
        "profile_id": str(_PROFILE_ID),
        "modelo": "210",
        "year": 2025,
        "period_code": "evento",
        "missing": True,
    }

    validation = validate_request(entry.input_type, document)
    # The command builds this same request, and prints the error it raises through this envelope.
    with pytest.raises(PeriodError) as raised:
        entry.input_type.model_validate(document | {"profile_id": _PROFILE_ID})
    printed = build_error_envelope(raised.value).message

    assert "EVENT-N" in printed
    assert (validation.payload, dict(validation.field_errors)) == (None, {})
    assert validation.general_errors == (printed,)


def test_text_that_is_not_the_value_its_field_calls_for_is_reported_and_left_out() -> None:
    fields = _fields(_VIEW)

    document, problems = request_document(fields, {"profile_id": str(_PROFILE_ID), "cursor": "three", "page_kind": "x"})

    assert problems == {"cursor": RequestFieldProblem.INTEGER, "page_kind": RequestFieldProblem.CHOICE}
    assert document == {"profile_id": str(_PROFILE_ID)}


def test_json_number_and_boolean_fields_convert_or_report() -> None:
    nested = RequestFieldV1("rows", RequestFieldKind.JSON, "", True, (), "[]", False)
    number = RequestFieldV1("ratio", RequestFieldKind.NUMBER, "", False, (), "", False)
    flag = RequestFieldV1("dry_run", RequestFieldKind.BOOLEAN, "", False, (), "", False)
    amount = RequestFieldV1("amount", RequestFieldKind.DECIMAL, "", False, (), "", False)
    fields = (nested, number, flag, amount)

    document, problems = request_document(
        fields, {"rows": '[{"a": 1}]', "ratio": "0.5", "dry_run": "true", "amount": " 1234.50 "}
    )
    assert problems == {}
    assert document == {"rows": [{"a": 1}], "ratio": 0.5, "dry_run": True, "amount": "1234.50"}

    _document, problems = request_document(fields, {"rows": "[", "ratio": "true", "dry_run": "yes"})
    assert problems == {
        "rows": RequestFieldProblem.JSON,
        "ratio": RequestFieldProblem.NUMBER,
        "dry_run": RequestFieldProblem.CHOICE,
    }


def test_a_file_path_is_typed_as_a_path_and_sent_absolute() -> None:
    field = RequestFieldV1("source_path", RequestFieldKind.PATH, "", True, (), "", False)

    document, problems = request_document((field,), {"source_path": "statements/2026.csv"})

    assert problems == {}
    sent = Path(str(document["source_path"]))
    assert sent.is_absolute()
    assert sent == (Path.cwd() / "statements" / "2026.csv").resolve()


def test_the_whole_request_round_trips_between_its_fields_and_its_json() -> None:
    fields = _fields(_VIEW)
    texts = {field.name: field.initial for field in fields} | {"page_kind": "issues", "limit": "7"}
    document, _problems = request_document(fields, texts)

    restored = field_texts(fields, json.loads(json.dumps(document)))

    assert request_document(fields, restored)[0] == document
    assert restored["page_kind"] == "issues"
    assert restored["expected_revision"] == ""

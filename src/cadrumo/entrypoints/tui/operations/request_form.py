"""Derive one operation's request form from its public request schema.

Nothing here draws a widget. A field is classified from the JSON schema the
registry publishes for the request, its text is converted to the JSON value the
schema calls for, and the assembled document is validated by the operation's
own request model, which is also what encodes the payload that is submitted.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import cast
from uuid import UUID

from pydantic import BaseModel, ValidationError

from ....application.operations.subject_reference import (
    OperationSubjectKind,
    OperationSubjectReferenceV1,
    expected_operation_subject,
)

type _Schema = Mapping[str, object]

_SKELETON_DEPTH = 4
_PROFILE_FIELD = "profile_id"
_PATH_FORMATS = frozenset({"path", "file-path", "directory-path"})
_TEXT_TYPES = frozenset({"string", "integer", "number"})


class RequestFieldKind(StrEnum):
    """How one request field is entered."""

    TEXT = "text"
    INTEGER = "integer"
    NUMBER = "number"
    DECIMAL = "decimal"
    DATE = "date"
    DATETIME = "datetime"
    UUID = "uuid"
    PATH = "path"
    BOOLEAN = "boolean"
    ENUM = "enum"
    JSON = "json"


class RequestFieldProblem(StrEnum):
    """Why a field's text is not the kind of value its schema calls for."""

    INTEGER = "integer"
    NUMBER = "number"
    JSON = "json"
    CHOICE = "choice"


@dataclass(frozen=True, slots=True)
class RequestFieldV1:
    """One top-level field of an operation's request, as the form enters it."""

    name: str
    kind: RequestFieldKind
    description: str
    required: bool
    choices: tuple[object, ...]
    initial: str
    session_fixed: bool

    @property
    def choice_labels(self) -> tuple[str, ...]:
        """Return the text each enumerated value is offered and entered as."""
        return tuple(_scalar_text(choice) for choice in self.choices)


def _scalar_text(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False)


def _definitions(schema: _Schema) -> _Schema:
    definitions = schema.get("$defs")
    return cast("_Schema", definitions) if isinstance(definitions, Mapping) else {}


def _resolved(node: object, definitions: _Schema) -> _Schema:
    """Follow one local reference, keeping what the referring node says beside it."""
    if not isinstance(node, Mapping):
        return {}
    current = cast("_Schema", node)
    reference = current.get("$ref")
    if isinstance(reference, str) and reference.startswith("#/$defs/"):
        target = definitions.get(reference.removeprefix("#/$defs/"))
        if isinstance(target, Mapping):
            merged = dict(cast("_Schema", target))
            merged.update({key: value for key, value in current.items() if key != "$ref"})
            return merged
    return current


def _alternatives(node: _Schema, definitions: _Schema) -> tuple[_Schema, ...]:
    """Return what a field may be once the absent value is set aside."""
    members = node.get("anyOf")
    if not isinstance(members, list):
        return (node,)
    resolved = tuple(_resolved(member, definitions) for member in cast("list[object]", members))
    return tuple(member for member in resolved if member.get("type") != "null")


def _scalar_kind(node: _Schema) -> RequestFieldKind:
    kind = node.get("type")
    if kind == "integer":
        return RequestFieldKind.INTEGER
    if kind == "number":
        return RequestFieldKind.NUMBER
    if kind == "boolean":
        return RequestFieldKind.BOOLEAN
    if kind != "string":
        return RequestFieldKind.JSON
    text_format = node.get("format")
    if text_format == "uuid":
        return RequestFieldKind.UUID
    if text_format == "date":
        return RequestFieldKind.DATE
    if text_format == "date-time":
        return RequestFieldKind.DATETIME
    if text_format in _PATH_FORMATS:
        return RequestFieldKind.PATH
    return RequestFieldKind.TEXT


def _classified(node: _Schema, definitions: _Schema) -> tuple[RequestFieldKind, tuple[object, ...]]:
    alternatives = _alternatives(node, definitions)
    if len(alternatives) == 1:
        only = alternatives[0]
        if "const" in only:
            return RequestFieldKind.ENUM, (only["const"],)
        choices = only.get("enum")
        if isinstance(choices, list):
            return RequestFieldKind.ENUM, tuple(cast("list[object]", choices))
        return _scalar_kind(only), ()
    kinds = {member.get("type") for member in alternatives}
    if alternatives and kinds <= _TEXT_TYPES:
        # A number offered beside its own text form is an exact decimal: the text keeps every digit.
        return (RequestFieldKind.DECIMAL if "number" in kinds else RequestFieldKind.TEXT), ()
    return RequestFieldKind.JSON, ()


def json_skeleton(node: object, definitions: _Schema, *, depth: int = _SKELETON_DEPTH) -> object:
    """Return the smallest document shaped like ``node``, for a person to fill in."""
    resolved = _resolved(node, definitions)
    if "default" in resolved:
        return resolved["default"]
    if "const" in resolved:
        return resolved["const"]
    choices = resolved.get("enum")
    if isinstance(choices, list) and choices:
        return cast("list[object]", choices)[0]
    members = resolved.get("anyOf")
    if isinstance(members, list):
        alternatives = _alternatives(resolved, definitions)
        if len(alternatives) != len(cast("list[object]", members)) or not alternatives:
            return None
        return json_skeleton(alternatives[0], definitions, depth=depth)
    kind = resolved.get("type")
    if kind == "object":
        properties = resolved.get("properties")
        required = resolved.get("required")
        if depth <= 0 or not isinstance(properties, Mapping) or not isinstance(required, list):
            return {}
        fields = cast("_Schema", properties)
        return {
            name: json_skeleton(fields.get(name), definitions, depth=depth - 1)
            for name in cast("list[object]", required)
            if isinstance(name, str)
        }
    if kind == "array":
        return []
    if kind == "string":
        return ""
    if kind in {"integer", "number"}:
        return 0
    if kind == "boolean":
        return False
    return None


def _initial_text(kind: RequestFieldKind, node: _Schema, definitions: _Schema, *, required: bool) -> str:
    if kind is RequestFieldKind.JSON:
        if "default" in node:
            return json.dumps(node["default"], ensure_ascii=False, indent=2)
        return json.dumps(json_skeleton(node, definitions), ensure_ascii=False, indent=2) if required else ""
    return _scalar_text(node.get("default"))


def request_fields(schema: _Schema, *, profile_id: UUID) -> tuple[RequestFieldV1, ...]:
    """Return the form's fields, in the order the request schema declares them.

    A request's own ``profile_id`` is the profile the session is admitted for,
    so it is filled and not entered.
    """
    definitions = _definitions(schema)
    properties = schema.get("properties")
    if not isinstance(properties, Mapping):
        return ()
    declared_required = schema.get("required")
    required_names = (
        frozenset(name for name in cast("list[object]", declared_required) if isinstance(name, str))
        if isinstance(declared_required, list)
        else frozenset[str]()
    )
    fields: list[RequestFieldV1] = []
    for name, raw in cast("_Schema", properties).items():
        node = _resolved(raw, definitions)
        kind, choices = _classified(node, definitions)
        required = name in required_names
        session_fixed = name == _PROFILE_FIELD and kind is RequestFieldKind.UUID
        description = node.get("description")
        if not isinstance(description, str):
            only = _alternatives(node, definitions)
            nested = only[0].get("description") if len(only) == 1 else None
            description = nested if isinstance(nested, str) else ""
        fields.append(
            RequestFieldV1(
                name=name,
                kind=kind,
                description=" ".join(description.split()),
                required=required,
                choices=choices,
                initial=(
                    str(profile_id) if session_fixed else _initial_text(kind, node, definitions, required=required)
                ),
                session_fixed=session_fixed,
            )
        )
    return tuple(fields)


def _field_value(field: RequestFieldV1, text: str) -> object:
    """Return the JSON value ``text`` stands for, or the problem that prevents reading it."""
    stripped = text.strip()
    kind = field.kind
    if kind is RequestFieldKind.INTEGER:
        try:
            return int(stripped)
        except ValueError:
            return RequestFieldProblem.INTEGER
    if kind is RequestFieldKind.NUMBER:
        try:
            number = json.loads(stripped)
        except ValueError:
            return RequestFieldProblem.NUMBER
        if isinstance(number, bool) or not isinstance(number, (int, float)):
            return RequestFieldProblem.NUMBER
        return number
    if kind is RequestFieldKind.BOOLEAN:
        return stripped == "true" if stripped in {"true", "false"} else RequestFieldProblem.CHOICE
    if kind is RequestFieldKind.ENUM:
        for choice, label in zip(field.choices, field.choice_labels, strict=True):
            if label == stripped:
                return choice
        return RequestFieldProblem.CHOICE
    if kind is RequestFieldKind.JSON:
        try:
            return json.loads(text)
        except ValueError:
            return RequestFieldProblem.JSON
    if kind is RequestFieldKind.PATH:
        # A relative path means what it means on the command line: relative to
        # where this process runs, which is not where the profile worker runs.
        return str(Path(stripped).expanduser().resolve())
    if kind is RequestFieldKind.TEXT:
        return text
    return stripped


def request_document(
    fields: tuple[RequestFieldV1, ...], texts: Mapping[str, str]
) -> tuple[dict[str, object], dict[str, RequestFieldProblem]]:
    """Assemble the request document from the entered texts.

    A field left empty is left out, so the request model applies its default or
    reports it missing. A text that is not the kind of value its field calls
    for is reported against that field and left out.
    """
    document: dict[str, object] = {}
    problems: dict[str, RequestFieldProblem] = {}
    for field in fields:
        text = texts.get(field.name, "")
        if not text.strip():
            continue
        value = _field_value(field, text)
        if isinstance(value, RequestFieldProblem):
            problems[field.name] = value
        else:
            document[field.name] = value
    return document, problems


def field_texts(fields: tuple[RequestFieldV1, ...], document: Mapping[str, object]) -> dict[str, str]:
    """Return the text each field shows for the values ``document`` carries."""
    texts: dict[str, str] = {}
    for field in fields:
        if field.name not in document:
            texts[field.name] = ""
        elif field.kind is RequestFieldKind.JSON:
            texts[field.name] = json.dumps(document[field.name], ensure_ascii=False, indent=2)
        else:
            texts[field.name] = _scalar_text(document[field.name])
    return texts


@dataclass(frozen=True, slots=True)
class RequestValidationV1:
    """The validated request, or what its own model refused and where."""

    payload: BaseModel | None
    field_errors: Mapping[str, tuple[str, ...]]
    general_errors: tuple[str, ...]


def validate_request(input_type: type[BaseModel], document: Mapping[str, object]) -> RequestValidationV1:
    """Validate ``document`` with the operation's own request model.

    The document is validated as the JSON the runtime decodes, so a value is
    accepted here exactly when the runtime accepts it. An error names its field
    and the model's reason, never the value that was entered.
    """
    try:
        encoded = json.dumps(document, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
    except (TypeError, ValueError):
        return RequestValidationV1(payload=None, field_errors={}, general_errors=(RequestFieldProblem.JSON.value,))
    try:
        return RequestValidationV1(payload=input_type.model_validate_json(encoded), field_errors={}, general_errors=())
    except ValidationError as error:
        by_field: dict[str, list[str]] = {}
        general: list[str] = []
        for item in error.errors(include_url=False, include_context=False, include_input=False):
            location = tuple(str(part) for part in item["loc"])
            message = item["msg"]
            if not location:
                general.append(message)
                continue
            nested = ".".join(location[1:])
            by_field.setdefault(location[0], []).append(f"{nested}: {message}" if nested else message)
        return RequestValidationV1(
            payload=None,
            field_errors={name: tuple(messages) for name, messages in by_field.items()},
            general_errors=tuple(general),
        )


def subject_is_entered(reference: OperationSubjectReferenceV1, *, typed_operator_input: bool) -> bool:
    """Report whether a person names the subject because nothing else can.

    Only the store knows which work unit owns a stored record, and a typed
    operator input is not the registered request the subject is read from.
    """
    return typed_operator_input or reference.kind is OperationSubjectKind.STORED_WORK_UNIT


def derived_subject(
    reference: OperationSubjectReferenceV1,
    *,
    profile_id: UUID,
    document: Mapping[str, object],
    entered: str | None,
    typed_operator_input: bool,
) -> str | None:
    """Return the subject one submission names, or ``None`` while the request does not yet say.

    The subject comes from the contract's subject reference, the admitted
    profile and the request document. ``entered`` is used only where
    :func:`subject_is_entered` says a person names it.
    """
    if not typed_operator_input:
        try:
            derived = expected_operation_subject(reference, profile_id=profile_id, payload=document)
        except ValueError:
            return None
        if derived is not None:
            # A skeleton leaves the subject field blank; a blank is not yet a subject.
            return derived if derived.strip() else None
    if entered is None or not entered.strip():
        return None
    return entered.strip()


__all__ = [
    "RequestFieldKind",
    "RequestFieldProblem",
    "RequestFieldV1",
    "RequestValidationV1",
    "derived_subject",
    "field_texts",
    "json_skeleton",
    "request_document",
    "request_fields",
    "subject_is_entered",
    "validate_request",
]

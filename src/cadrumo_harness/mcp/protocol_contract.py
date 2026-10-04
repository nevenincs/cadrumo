"""Canonical MCP tool schemas and wire-value contracts."""

from __future__ import annotations

from collections.abc import Mapping
from enum import Enum
from typing import Any, NotRequired, TypedDict, cast

from pydantic import BaseModel, ValidationError

from cadrumo.adapters.local_runtime.frontend_client_contracts import RuntimeFrontendRefusedError
from cadrumo.application.corpus_search.errors import CorpusSearchError
from cadrumo.application.operations.frontend_requests import OperationResultProjectionRefusalV1
from cadrumo.application.runtime.contracts import RuntimeRefusalError
from cadrumo.application.runtime.projection_pages import ProjectionPage
from cadrumo.application.user_profile.automation_custody_port import AutomationCustodyError
from cadrumo.core.hashing import canonical_json_bytes, sha256_hex
from cadrumo.domain.calculations.registry.authority_store import AuthorityStoreError
from cadrumo.domain.calculations.registry.errors import (
    AuthorityDescriptorUnavailableError,
    RegistryError,
    RegistryValidationError,
)


class _FieldSchema(TypedDict):
    """One supported JSON Schema property declaration."""

    type: str
    enum: NotRequired[list[str]]
    minimum: NotRequired[int]
    maximum: NotRequired[int]


class _ToolSchema(TypedDict):
    """The stable object schema advertised for one tool."""

    type: str
    additionalProperties: bool
    properties: dict[str, _FieldSchema]
    required: list[str]


def _schema(required: Mapping[str, _FieldSchema], optional: Mapping[str, _FieldSchema] | None = None) -> _ToolSchema:
    fields = dict(required)
    fields.update(optional or {})
    return {"type": "object", "additionalProperties": False, "properties": fields, "required": list(required)}


_TEXT: _FieldSchema = {"type": "string"}
_DOC: _FieldSchema = {"type": "object"}
MCP_TOOL_CATALOGUE = (
    ("status", "Current exact-profile authorization and availability", _schema({})),
    (
        "authorization_prepare",
        "Prepare enrollment, or an own-grant change using a protected credential reference",
        _schema({}, {"credential_reference": _TEXT}),
    ),
    ("authorization_request", "Submit a proposal for the prepared destination", _schema({"proposal": _DOC})),
    ("authorization_poll", "Inspect or complete this connection's pending authorization", _schema({})),
    (
        "authenticate",
        "Admit this connection using a protected credential reference",
        _schema({"credential_reference": _TEXT}),
    ),
    (
        "authority",
        "Query one pinned published tax authority generation",
        _schema(
            {
                "query": {
                    "type": "string",
                    "enum": ["modelos", "support", "describe", "casillas", "casilla", "formulas", "bindings"],
                }
            },
            {"modelo": _TEXT, "filing_year": {"type": "integer"}, "period": _TEXT, "casilla": _TEXT, "as_of": _TEXT},
        ),
    ),
    (
        "corpus_search",
        "Search the bundled BOE/AEAT legal corpus and approved tax terminology; "
        "an exact citation id resolves to its published verbatim text",
        _schema({"query": _TEXT}, {"limit": {"type": "integer", "minimum": 1, "maximum": 50}}),
    ),
    (
        "search",
        "Rank currently permitted registered operations by relevance to a query; without one, list them",
        _schema({}, {"query": _TEXT}),
    ),
    ("describe", "Read one current registered operation contract and input schema", _schema({"definition_id": _TEXT})),
    (
        "execute",
        "Submit one registered operation under current profile authority",
        _schema(
            {"definition_id": _TEXT, "subject_ref": _TEXT, "payload": _DOC},
            {"idempotency_key": _TEXT, "start": {"type": "boolean"}},
        ),
    ),
    ("observe", "Read a currently authorized operation observation", _schema({"observation": _DOC})),
    ("result", "Read a settled registered result with fresh disclosure checks per page", _schema({"result": _DOC})),
    (
        "result_page",
        "Read one bounded settled result page with fresh disclosure checks",
        _schema({"result": _DOC, "page": _DOC}),
    ),
    ("review", "Read a currently authorized review projection", _schema({"review": _DOC})),
    (
        "respond",
        "Inspect, apply, or reject a pending review owned by this admitted session",
        _schema(
            {
                "action": {"type": "string", "enum": ["inspect", "apply", "reject"]},
                "operation_id": _TEXT,
                "interaction_id": _TEXT,
                "revision": {"type": "integer", "minimum": 0},
            },
            {"reason_code": _TEXT},
        ),
    ),
    (
        "control",
        "Start, resume, cancel, or detach a registered operation",
        _schema(
            {"action": {"type": "string", "enum": ["start", "resume", "cancel", "detach"]}, "operation_id": _TEXT},
            {"expected_revision": {"type": "integer", "minimum": 0}},
        ),
    ),
)
_TOOL_SCHEMAS = {name: schema for name, _description, schema in MCP_TOOL_CATALOGUE}
MCP_TOOL_NAMES = frozenset(_TOOL_SCHEMAS)


def _field_matches(kind: str, value: object, declaration: _FieldSchema) -> bool:
    if not _field_type_matches(kind, value, declaration):
        return False
    return _enum_value_matches(value, declaration)


def _field_type_matches(kind: str, value: object, declaration: _FieldSchema) -> bool:
    if kind == "string":
        return isinstance(value, str)
    if kind == "object":
        return isinstance(value, dict)
    if kind == "boolean":
        return isinstance(value, bool)
    if kind == "integer":
        return _integer_value_matches(value, declaration)
    return True


def _integer_value_matches(value: object, declaration: _FieldSchema) -> bool:
    if not isinstance(value, int) or isinstance(value, bool):
        return False
    return value >= declaration.get("minimum", 0) and ("maximum" not in declaration or value <= declaration["maximum"])


def _enum_value_matches(value: object, declaration: _FieldSchema) -> bool:
    if "enum" not in declaration:
        return True
    return isinstance(value, str) and value in declaration["enum"]


def validate_tool_arguments(name: str, args: dict[str, object]) -> None:
    """Reject unknown, absent, or mistyped fields at the MCP wire boundary."""
    schema = _TOOL_SCHEMAS[name]
    properties = schema["properties"]
    if set(args) - set(properties) or set(schema["required"]) - set(args):
        raise ValueError("unknown or missing tool field")
    for key, value in args.items():
        declaration = properties[key]
        if not _field_matches(declaration["type"], value, declaration):
            raise ValueError("invalid tool field")


def public_value(value: object) -> Any:
    """Return one public JSON value for a typed model or an existing wire value."""
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    return value


def parse_model[M: BaseModel](model: type[M], value: object) -> M:
    """Parse one MCP object through the model's canonical JSON contract."""
    return model.model_validate_json(canonical_json_bytes(value))


def refusal_code(error: Exception) -> str:
    """Map a typed runtime failure to the stable non-secret MCP refusal code."""
    if isinstance(error, (RuntimeFrontendRefusedError, RuntimeRefusalError, AutomationCustodyError)):
        reason = error.reason
        return str(reason.value) if isinstance(reason, Enum) else str(reason)
    if isinstance(error, CorpusSearchError):
        return error.reason
    if isinstance(error, AuthorityDescriptorUnavailableError):
        return "published_authority_unavailable"
    if isinstance(error, RegistryValidationError):
        return "published_authority_query_refused"
    if isinstance(error, (AuthorityStoreError, RegistryError)):
        return "published_authority_invalid"
    if isinstance(error, (ValidationError, ValueError, TypeError, KeyError)):
        return "invalid_request"
    return "runtime_unavailable"


def _result_object(value: object) -> dict[str, Any] | None:
    """Narrow an adapter-owned JSON result to its object shape."""
    if not isinstance(value, dict):
        return None
    return cast(dict[str, Any], value)


def _page_contains_canonical_refusal(page: dict[str, Any]) -> bool:
    try:
        released = ProjectionPage.model_validate(page)
        if released.offset:
            return False
        encoded = released.decode()
        if len(encoded) != released.total_bytes or sha256_hex(encoded) != released.document_digest:
            return False
        refusal = OperationResultProjectionRefusalV1.model_validate_json(encoded)
        return canonical_json_bytes(refusal.model_dump(mode="json")) == encoded
    except (ValueError, TypeError):
        return False


def _reply_contains_refusal(reply: dict[str, Any]) -> bool:
    if reply.get("kind") == "access_refusal":
        return True
    for key in ("observation", "document"):
        envelope = _result_object(reply.get(key))
        if envelope is not None and envelope.get("outcome") == "refused":
            return True
    return False


def has_refusal(value: dict[str, Any]) -> bool:
    """Classify only explicit wire refusals and complete canonical refusal pages."""
    if value.get("outcome") in {"refused", "unresolved"}:
        return True
    start = _result_object(value.get("start"))
    if start is not None and start.get("outcome") == "unresolved":
        return True
    if value.get("outcome") != "reply":
        return False
    reply = _result_object(value.get("reply"))
    if reply is not None and _reply_contains_refusal(reply):
        return True
    document = _result_object(value.get("document"))
    if document is not None:
        return str(document.get("outcome")) == "refused"
    page = _result_object(value.get("page"))
    return page is not None and _page_contains_canonical_refusal(page)

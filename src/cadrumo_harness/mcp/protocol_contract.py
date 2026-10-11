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
from cadrumo.core.errors.hierarchy import InternalInvariantError
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
    format: NotRequired[str]
    writeOnly: NotRequired[bool]
    items: NotRequired[dict[str, str]]


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
# Marked so a client that follows the schema keeps the value out of its own logs and echoes.
_SECRET: _FieldSchema = {"type": "string", "format": "password", "writeOnly": True}
_TEXTS: _FieldSchema = {"type": "array", "items": {"type": "string"}}
_FLAG: _FieldSchema = {"type": "boolean"}
SEARCH_PAGE_DEFAULT = 50
SEARCH_PAGE_MAX = 200
MCP_TOOL_CATALOGUE = (
    (
        "status",
        "Current exact-profile authorization and availability. A notice member carries the runtime's lifecycle "
        "notice: upgrade_pending says an update is ready and the runtime restarts for it once idle, after which "
        "the next call re-establishes the session",
        _schema({}),
    ),
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
        "Rank currently permitted registered operations by relevance to a query; without one, list them. "
        "Results come in pages: pass a returned next_cursor as cursor for the next page, and family to narrow "
        "to one definition family. Each row is the operation's contract; its subject_reference says what the "
        "operation's subject is",
        _schema(
            {},
            {
                "query": _TEXT,
                "family": _TEXT,
                "limit": {"type": "integer", "minimum": 1, "maximum": SEARCH_PAGE_MAX},
                "cursor": _TEXT,
            },
        ),
    ),
    (
        "describe",
        "Read one current registered operation contract and input schema. The contract's subject_reference says "
        "what the operation's subject is: the admitted profile, the payload field its payload_path names, a fixed "
        "literal, or the work unit that owns the stored record its payload_path names. A contract that declares "
        "a transient_financial_operand is described with operator_input_json_schema, the typed input execute "
        "submits for it",
        _schema({"definition_id": _TEXT}),
    ),
    (
        "execute",
        "Submit one registered operation under current profile authority. Leave subject_ref out: it is derived "
        "from the contract's subject_reference, the admitted profile and the payload. Only a stored_work_unit "
        "operation needs it, as the id of the work unit that owns the record its payload_path names. "
        "An operation whose contract says ephemeral_secret_required takes that secret as text in secret, and no "
        "other operation accepts one: it travels to the runtime on the protected secret frame, apart from the "
        "payload, and no reply repeats it. An operation whose contract declares a transient_financial_operand "
        "takes its typed operator input as payload, with subject_ref and without idempotency_key",
        _schema(
            {"definition_id": _TEXT, "payload": _DOC},
            {"subject_ref": _TEXT, "idempotency_key": _TEXT, "start": {"type": "boolean"}, "secret": _SECRET},
        ),
    ),
    ("observe", "Read a currently authorized operation observation", _schema({"observation": _DOC})),
    (
        "result",
        "Read a settled registered result with fresh disclosure checks per page; "
        "the result object needs only operation_id, and the runtime supplies the other identifying values",
        _schema({"result": _DOC}),
    ),
    (
        "result_page",
        "Read one bounded settled result page with fresh disclosure checks; "
        "the result object needs only operation_id, and the runtime supplies the other identifying values",
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
    (
        "session",
        "Act on a profile's sessions as the command line does. Under the held session: list them, lock this "
        "session or the one target_session_id names, deny_automation of the given kind (a key or a grant named "
        "by target_id, all automation, or the whole profile), or sign_out the person. Without one: sign_in with "
        "the profile password in secret (store keeps the sign-in for every frontend and selects the profile; "
        "method api_key takes a raw key instead), sign_in_status, resume a locked profile with the password in "
        "secret and the grants to reactivate, reset_password with the recovery code in secret and the new "
        "password in new_secret and new_secret_confirmation, change_password with the current password in secret "
        "and the new one in the same two fields, and delete_profile for the profile named, which only reports "
        "what would be destroyed unless confirm is true. Each secret travels on the runtime's protected secret "
        "frame and no reply repeats it",
        _schema(
            {
                "action": {
                    "type": "string",
                    "enum": [
                        "list",
                        "lock",
                        "deny_automation",
                        "sign_out",
                        "sign_in",
                        "sign_in_status",
                        "resume",
                        "reset_password",
                        "change_password",
                        "delete_profile",
                    ],
                }
            },
            {
                "target_session_id": _TEXT,
                "kind": {"type": "string", "enum": ["key", "grant", "all", "profile_lock"]},
                "target_id": _TEXT,
                "profile": _TEXT,
                "method": {"type": "string", "enum": ["password", "api_key"]},
                "store": _FLAG,
                "grants": _TEXTS,
                "confirm": _FLAG,
                "secret": _SECRET,
                "new_secret": _SECRET,
                "new_secret_confirmation": _SECRET,
            },
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
    if kind == "array":
        return isinstance(value, list) and all(isinstance(item, str) for item in value)
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
    if isinstance(error, InternalInvariantError):
        # A port this process failed to compose is a defect here, not an absent runtime.
        return "internal_error"
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
    for step in ("secret_delivery", "start"):
        taken = _result_object(value.get(step))
        if taken is not None and taken.get("outcome") in {"refused", "unresolved"}:
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

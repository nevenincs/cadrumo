"""Canonical MCP tool schemas and wire-value contracts."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum
from types import MappingProxyType
from typing import Any, Final, NotRequired, TypedDict, cast

from pydantic import BaseModel, ValidationError

from cadrumo.application.corpus_search.errors import CorpusSearchError
from cadrumo.application.operations.frontend_requests import OperationResultProjectionRefusalV1
from cadrumo.application.user_profile.access_contracts import DISCLOSURE_PAGE_ENTRIES, AccessDenialCode
from cadrumo.application.user_profile.automation_custody_port import AutomationCustodyCode, AutomationCustodyError
from cadrumo.application.user_profile.sign_in_refusals import SignInRefusal
from cadrumo.core.errors.hierarchy import InternalInvariantError
from cadrumo.core.hashing import canonical_json_bytes, sha256_hex
from cadrumo.core.operations import OperationEffect, OperationLifecycle
from cadrumo.domain.calculations.registry.authority_store import AuthorityStoreError
from cadrumo.domain.calculations.registry.errors import (
    AuthorityDescriptorUnavailableError,
    RegistryError,
    RegistryValidationError,
)
from cadrumo.domain.calculations.registry.schema_input_kind import InputKind
from cadrumo.domain.portals.categories import PortalCategory
from cadrumo_client.contracts.contracts import RefusalError
from cadrumo_client.contracts.projection_pages import ProjectionPage
from cadrumo_client.transport.frontend_client_contracts import FrontendRefusedError


class _FieldSchema(TypedDict):
    """One supported JSON Schema property declaration."""

    type: str
    enum: NotRequired[list[str]]
    minimum: NotRequired[int]
    maximum: NotRequired[int]
    minLength: NotRequired[int]
    maxLength: NotRequired[int]
    pattern: NotRequired[str]
    format: NotRequired[str]
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
_FLAG: _FieldSchema = {"type": "boolean"}
SEARCH_PAGE_DEFAULT = 10
"""How many operations a search page holds when the call names no limit: few, so a page is cheap to read."""
SEARCH_PAGE_MAX = 200

_SIGN_IN_REFUSAL: Final = (
    "A call refused because the runtime would not sign this connection in answers with the runtime's code and, "
    "where the runtime gave them, the facts the command line reports with it: sign_in_reason, why the sign-in "
    "was refused (absent, expired_idle, throttled and so on); sign_in_binding, why a stored sign-in no longer "
    "counts here (generation_changed after a sign-out or lock elsewhere, login_mismatch when it was made at "
    "another login); sign_in_keychain, why this server's logon cannot use the protected credential store that "
    "holds a stored sign-in (logon_without_credentials when the Windows logon holds no credentials; "
    "no_backend; refused); and seconds, how long a throttled sign-in waits before the "
    "password is tried again. status reports the same facts beside denial"
)

SIGN_IN_REMEDY: Final = (
    "Nobody is signed in to Cadrumo for this profile, and no key the person configured admits this server. "
    "Ask the person to sign in to Cadrumo, then call again. You cannot sign in, and you never ask for a password, "
    "a key or any other secret"
)
"""What a call refused for want of a live sign-in or a configured key tells the agent to do."""

KEYCHAIN_REMEDY: Final = (
    "This server runs in a Windows logon without credentials, so it cannot use the protected credential store "
    "and no sign-in can be followed from it. Ask the person to sign in at the desktop and run Cadrumo and this "
    "agent from that desktop sign-in. You cannot change this, and you never ask for a password, a key or any "
    "other secret"
)
"""What a refusal tells the agent when this server's logon cannot reach the store a stored sign-in needs."""

PERSON_ACT_REMEDY: Final = (
    "Ask the person to do this in Cadrumo. Signing in or out, locking, passwords, recovery, keys and their grants, "
    "and anything outside this profile are the person's acts, and you never ask for a password, a key or any "
    "other secret"
)
"""What a call refused as the person's own act tells the agent to do."""

PROFILE_CHANGED_REMEDY: Final = (
    "The person is now signed in to another profile than the one this agent session served, so this session is "
    "over and nothing of either profile is reachable through it. Ask the person to start a new agent session "
    "in Cadrumo"
)
"""What a call refused because the signed-in profile changed under a bound connection tells the agent to do."""

_ADMISSION_REFUSALS: Final = frozenset(
    {*(code.value for code in AccessDenialCode), *(code.value for code in AutomationCustodyCode)}
) - {AccessDenialCode.PERSON_ACT_REQUIRED.value, AccessDenialCode.SUBJECT_BUSY.value}


def sign_in_remedy(code: str, facts: Mapping[str, Any] | None = None) -> str | None:
    """Return what to tell the agent when nothing admits the server and the runtime refused with ``code``.

    Only a refusal of admission sends the agent to the person; a runtime that
    is not running or is draining, or a malformed call, says something else.
    A profile other than the connection's being the one signed in to ends the
    agent session, which only a new one started by the person replaces.
    """
    if code == AccessDenialCode.PROFILE_MISMATCH.value:
        return PROFILE_CHANGED_REMEDY
    if (facts is not None and facts) and "sign_in_keychain" in facts:
        # No sign-in can be followed from this logon, so signing in again would change nothing.
        return KEYCHAIN_REMEDY
    return SIGN_IN_REMEDY if code in _ADMISSION_REFUSALS else None


_UNKNOWN_OUTCOME: Final = (
    "An answer whose outcome is unresolved is not an error: it says the effect is not known, and its "
    "unknown_outcome member says how to read what happened. Do not repeat a call that answered so"
)


@dataclass(frozen=True, slots=True)
class ToolHints:
    """What the widest call of one tool can do, as the protocol's tool annotations state it.

    They are hints for a host's own presentation and consent, and decide
    nothing here: the runtime admits or refuses every call on its own
    evidence. A tool is described by what it can do on the widest surface.
    """

    title: str
    read_only: bool
    """No call changes a record, a session, a stored credential or a file, and none starts work that could."""
    destructive: bool
    """Some call can delete or overwrite; false only where every change adds."""
    idempotent: bool
    """Repeating a call with the same arguments changes nothing further."""
    open_world: bool
    """Some call can contact a host other than this machine."""


def _reads(title: str) -> ToolHints:
    """Hints for a tool that only reads what this machine holds."""
    return ToolHints(title=title, read_only=True, destructive=False, idempotent=True, open_world=False)


def _acts(title: str, *, destructive: bool, open_world: bool) -> ToolHints:
    """Hints for a tool some call of which changes something; no such tool promises that a repeat is harmless."""
    return ToolHints(title=title, read_only=False, destructive=destructive, idempotent=False, open_world=open_world)


_DECLARED_TOOLS: Final[tuple[tuple[str, str, _ToolSchema, ToolHints], ...]] = (
    (
        "status",
        "Current exact-profile authorization and availability. You work only inside the one profile the person "
        "signed in to in Cadrumo, or the one a key the person configured is for, and every tool but this one "
        "needs that: with neither, each answers refused, and remedy says to ask the person to sign in to Cadrumo. "
        "You never sign in, and never ask for a password, a key or any other secret. A notice member carries the "
        "runtime's lifecycle notice: upgrade_pending says an update is ready and the runtime restarts for it once "
        f"idle, after which the next call re-establishes the session. {_SIGN_IN_REFUSAL} "
        "The status's effective_scope counts the disclosures the session may release: disclosure_count, "
        "disclosure_summary with the count in each category, and disclosure_digest. For the entries themselves "
        "pass disclosures, an object with offset, starting at 0, and expected_digest, the disclosure_digest: "
        f"the reply then carries disclosure_page, with at most {DISCLOSURE_PAGE_ENTRIES} entries and a "
        "next_offset to pass for the next page until it is null. A list that changed since its digest, or an "
        "offset past its end, is refused with operation_unavailable; read status again and start over",
        _schema({}, {"disclosures": _DOC}),
        _reads("Session and profile status"),
    ),
    (
        "authority",
        "Read bundled public reference data from one pinned published tax authority generation, with the content "
        "the command line prints as JSON. modelos lists the registry's modelos (filing_year and domain narrow it); "
        "support is the per-modelo capability matrix; describe, casillas, casilla (named by casilla) and formulas "
        "read one modelo: give period alone for its latest revision, or filing_year with period to compose an exact "
        "one (as_of needs the exact form); casillas narrows by input_kind, required, form_number and casilla_number; "
        "bindings lists a modelo's bindings for a filing_year; categories lists the spending and IRPF category "
        "vocabularies; portals lists the AEAT portal catalogue (narrow it by category or modelo, not both) and "
        "portal reads one by id; auth_providers lists the sign-in providers; apoderado_scopes lists the "
        "representative scopes. A ceded autonomic tax such as 600 or 650 is answered with its regional redirect",
        _schema(
            {
                "query": {
                    "type": "string",
                    "enum": [
                        "modelos",
                        "support",
                        "describe",
                        "casillas",
                        "casilla",
                        "formulas",
                        "bindings",
                        "categories",
                        "portals",
                        "portal",
                        "auth_providers",
                        "apoderado_scopes",
                    ],
                }
            },
            {
                "modelo": _TEXT,
                "filing_year": {"type": "integer"},
                "period": _TEXT,
                "casilla": _TEXT,
                "as_of": _TEXT,
                "domain": _TEXT,
                "input_kind": {"type": "string", "enum": [kind.value for kind in InputKind]},
                "required": _FLAG,
                "form_number": _TEXT,
                "casilla_number": _TEXT,
                "category": {"type": "string", "enum": [category.value for category in PortalCategory]},
                "portal": _TEXT,
            },
        ),
        _reads("Read published tax reference data"),
    ),
    (
        "corpus_search",
        "Search the bundled BOE/AEAT legal corpus and approved tax terminology; "
        "an exact citation id resolves to its published verbatim text",
        _schema({"query": _TEXT}, {"limit": {"type": "integer", "minimum": 1, "maximum": 50}}),
        _reads("Search the bundled legal corpus"),
    ),
    (
        "search",
        "Rank currently permitted registered operations by relevance to a query; without one, list them. "
        "Each row is a summary: the operation's definition_id, a one-line description, the kind of subject it "
        "acts on, the effects it may have, the interactions it may ask for and whether it takes a secret, which "
        "makes it the person's act and not one execute submits. "
        "The contract and the request schema are not in a row: pass a small limit, then describe the operation "
        f"you pick. A page holds {SEARCH_PAGE_DEFAULT} rows when limit is omitted and at most {SEARCH_PAGE_MAX}: "
        "pass a returned next_cursor as cursor for the next page, and family to narrow to one definition "
        "family. The rows cover the operations in this session's scope",
        _schema(
            {},
            {
                "query": _TEXT,
                "family": _TEXT,
                "limit": {"type": "integer", "minimum": 1, "maximum": SEARCH_PAGE_MAX},
                "cursor": _TEXT,
            },
        ),
        _reads("Find operations"),
    ),
    (
        "describe",
        "Read one current registered operation contract and input schema. The contract's subject_reference says "
        "what the operation's subject is: the admitted profile, the payload field its payload_path names, a fixed "
        "literal, or the work unit that owns the stored record its payload_path names. A contract that declares "
        "a transient_financial_operand is described with operator_input_json_schema, the typed input execute "
        "submits for it. A contract whose payload names values its schema cannot enumerate is described with "
        "payload_vocabulary: for user-profile.patch, every question_id it may set, with its meaning and, where "
        "the answer is a choice, the values it takes, as the command line lists them in its help",
        _schema({"definition_id": _TEXT}),
        _reads("Describe an operation"),
    ),
    (
        "execute",
        "Submit one registered operation under current profile authority. Leave subject_ref out: it is derived "
        "from the contract's subject_reference, the admitted profile and the payload. Only a stored_work_unit "
        "operation needs it, as the id of the work unit that owns the record its payload_path names. "
        "An operation whose contract says ephemeral_secret_required is the person's own act and is refused "
        f"here: {PERSON_ACT_REMEDY}. An operation whose contract "
        "declares a transient_financial_operand takes its typed operator input as payload, with subject_ref and "
        "without idempotency_key. A payload the operation's request model refuses is answered refused with "
        "code invalid, and faults names each reason by location, type and message: a missing field, a field "
        "the request does not have, or the rule a value broke. The message is the validator's own, the text the "
        "command line shows for the same refusal, with any guidance it gives, such as the values that are "
        "accepted; it may quote the value it refused. A fault with an empty location and a registered error "
        "code as its type refuses the whole request, with the message the command line prints for that error. "
        "No fault attaches the refused input itself. "
        "A refusal with code subject_busy means an earlier operation of this definition on the same subject has "
        "not settled, and holder_operation_id names it; signing in again changes nothing, so report it to the "
        "person with that id rather than retrying. "
        "Every call submits a new operation, so two identical calls run twice. "
        "idempotency_key is optional, and giving one makes a repeat safe: a repeat with the same key, operation "
        f"and payload answers with the operation already recorded and submits nothing. {_UNKNOWN_OUTCOME} "
        "unless it carried an idempotency_key, and then repeat it only with that same key",
        _schema(
            {"definition_id": _TEXT, "payload": _DOC},
            {
                "subject_ref": _TEXT,
                "idempotency_key": _TEXT,
                "start": {"type": "boolean"},
            },
        ),
        # Some registered operation deletes records, and some reads a remote host.
        _acts("Run an operation", destructive=True, open_world=True),
    ),
    (
        "observe",
        "Read a currently authorized operation observation. A read that a registered error stops, here or in "
        "result, result_page, review or respond with action inspect, is answered refused with code invalid, and "
        "faults carries that error's code as its type and the message the command line prints for it",
        _schema({"observation": _DOC}),
        _reads("Observe an operation"),
    ),
    (
        "result",
        "Read a settled registered result with fresh disclosure checks per page; "
        "the result object needs only operation_id, and the runtime supplies the other identifying values. "
        "An operation that settled refused or failed has no result: its document says operation_not_successful, "
        "and error_detail beside it carries what the operation recorded about why, which is the registered "
        "error code, the message key, the context and any precondition verdict the command line prints",
        _schema({"result": _DOC}),
        _reads("Read an operation's result"),
    ),
    (
        "result_page",
        "Read one bounded settled result page with fresh disclosure checks; "
        "the result object needs only operation_id, and the runtime supplies the other identifying values",
        _schema({"result": _DOC, "page": _DOC}),
        _reads("Read one page of a result"),
    ),
    (
        "review",
        "Read a currently authorized review projection",
        _schema({"review": _DOC}),
        # Reading a review applies nothing: the same projection read that serves a result.
        _reads("Read a pending review"),
    ),
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
        # Applying lets the reviewed operation commit, whatever that operation does.
        _acts("Answer a pending review", destructive=True, open_world=True),
    ),
    (
        "control",
        "Start, resume, cancel, or detach a registered operation",
        _schema(
            {"action": {"type": "string", "enum": ["start", "resume", "cancel", "detach"]}, "operation_id": _TEXT},
            {"expected_revision": {"type": "integer", "minimum": 0}},
        ),
        # Starting an operation lets it do whatever execute could have started.
        _acts("Control an operation", destructive=True, open_world=True),
    ),
)
MCP_TOOL_CATALOGUE = tuple((name, description, schema) for name, description, schema, _hints in _DECLARED_TOOLS)
"""Each tool as it is advertised: its name, its description and the schema of its arguments."""

MCP_TOOL_HINTS: Final[Mapping[str, ToolHints]] = MappingProxyType(
    {name: hints for name, _description, _arguments, hints in _DECLARED_TOOLS}
)
"""Each tool's hints, declared beside it in the catalogue."""

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
    if isinstance(error, (FrontendRefusedError, RefusalError, AutomationCustodyError)):
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


def sign_in_refusal_facts(sign_in: SignInRefusal | None) -> dict[str, Any]:
    """Return a sign-in refusal's public facts by the names the command line reports them under.

    They are the typed reason, the receipt binding when the sign-in no longer
    belongs to this login or generation, and the seconds a throttle has left.
    None is a secret or an identifier.
    """
    if sign_in is None:
        return {}
    facts: dict[str, Any] = {"sign_in_reason": str(sign_in.reason)}
    if sign_in.binding is not None:
        facts["sign_in_binding"] = sign_in.binding.value
    if sign_in.keychain is not None:
        facts["sign_in_keychain"] = sign_in.keychain.value
    if sign_in.remaining_seconds is not None:
        facts["seconds"] = sign_in.remaining_seconds
    return facts


def refusal_facts(error: Exception) -> dict[str, Any]:
    """Return the public facts a refusal carries beside its code, so no sign-in refusal collapses to it.

    A busy subject also names the unsettled operation that holds it, for the person to follow.
    """
    if isinstance(error, FrontendRefusedError):
        facts = sign_in_refusal_facts(error.sign_in)
        if error.holder_operation_id is not None:
            facts["holder_operation_id"] = error.holder_operation_id
        return facts
    return {}


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


_EXECUTE_STEPS: Final = ("start",)
"""The steps an execute reply reports beside its receipt, each with an outcome of its own."""

UNKNOWN_OUTCOME_MEMBER: Final = "unknown_outcome"
"""The member that tells the caller an effect is not known, not to repeat the call, and how to read it."""

_NOT_KNOWN: Final = "The outcome is not known, which is not a failure: the effect may have been committed"
_NEVER_REPEAT: Final = "Do not repeat this call"


def _observed_projection(value: dict[str, Any]) -> dict[str, Any] | None:
    """Return the operation projection of a successful observation reply, if that is what this is."""
    reply = _result_object(value.get("reply"))
    observation = None if reply is None else _result_object(reply.get("observation"))
    return None if observation is None else _result_object(observation.get("projection"))


def unknown_outcome_instruction(value: dict[str, Any]) -> str | None:
    """Say what to do about a reply whose effect is not known, or ``None`` where the reply settles it.

    A repeat of a call that may already have committed can commit it twice,
    so each sentence names what the reply kept to read the outcome by
    instead: the operation, or the request alone.
    """
    if value.get("outcome") == "unresolved":
        if "operation_id" in value:
            return (
                f"{_NOT_KNOWN}. {_NEVER_REPEAT}: read the operation named by operation_id with observe, and with "
                "result once it has settled."
            )
        if "definition_id" in value:
            return (
                f"{_NOT_KNOWN}: the reply that carried the operation's id was lost, and request_id and "
                f"definition_id identify what was sent. {_NEVER_REPEAT}, because a repeat submits a second "
                "operation, unless it carried an idempotency_key: then a repeat with the same key, operation and "
                "payload answers with the operation already recorded. Otherwise read the records the operation "
                "writes to learn whether it ran, and tell the person the outcome is not known."
            )
        return f"{_NOT_KNOWN}. {_NEVER_REPEAT}, and tell the person the outcome is not known."
    unsettled = [
        step
        for step in _EXECUTE_STEPS
        if (taken := _result_object(value.get(step))) is not None and taken.get("outcome") == "unresolved"
    ]
    if unsettled:
        return (
            f"The operation was recorded under receipt.operation_id, and whether {' and '.join(unsettled)} took "
            f"effect is not known. {_NEVER_REPEAT}, because a repeat submits a second operation: read this one "
            "with observe, and with result once it has settled, before any control action."
        )
    projection = _observed_projection(value)
    if projection is None:
        return None
    if projection.get("lifecycle") == OperationLifecycle.SETTLING.value:
        return (
            "The operation is settling and its outcome is not known yet. Do not submit it again: observe it "
            "again until it is terminal, then read it with result."
        )
    if projection.get("effect") == OperationEffect.UNKNOWN.value:
        return (
            "The operation recorded that the extent of its effect is not known, which is not a failure and not "
            "proof that nothing changed. Do not submit it again: read the records it writes, and tell the person "
            "the outcome is not known."
        )
    return None


def has_refusal(value: dict[str, Any]) -> bool:
    """Classify only explicit wire refusals and complete canonical refusal pages.

    An outcome that is not known is no refusal: marking it as an error
    invites the caller to repeat a call that may already have committed.
    """
    if value.get("outcome") == "refused":
        return True
    for step in _EXECUTE_STEPS:
        taken = _result_object(value.get(step))
        if taken is not None and taken.get("outcome") == "refused":
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

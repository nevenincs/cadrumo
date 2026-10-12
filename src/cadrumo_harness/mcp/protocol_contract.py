"""Canonical MCP tool schemas and wire-value contracts."""

from __future__ import annotations

from collections.abc import Collection, Mapping
from dataclasses import dataclass
from enum import Enum
from types import MappingProxyType
from typing import Any, Final, NotRequired, TypedDict, cast

from pydantic import BaseModel, ValidationError

from cadrumo.adapters.local_runtime.frontend_client_contracts import RuntimeFrontendRefusedError
from cadrumo.application.corpus_search.errors import CorpusSearchError
from cadrumo.application.operations.frontend_requests import OperationResultProjectionRefusalV1
from cadrumo.application.runtime.contracts import RuntimeRefusalError
from cadrumo.application.runtime.installation_requests import (
    INSTALLATION_ACT_CONTRACTS,
    InstallationAct,
    InstallationActContract,
)
from cadrumo.application.runtime.projection_pages import ProjectionPage
from cadrumo.application.user_profile.automation_custody_port import AutomationCustodyError
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

from .held_secrets import HOLD_OPTION, ONCE_OPTION


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
# Names a secret the person entered at a terminal of their own; the reference itself is no secret.
_SECRET_REFERENCE: _FieldSchema = {"type": "string", "format": "uuid"}
_TEXTS: _FieldSchema = {"type": "array", "items": {"type": "string"}}
_FLAG: _FieldSchema = {"type": "boolean"}
SEARCH_PAGE_DEFAULT = 10
"""How many operations a search page holds when the call names no limit: few, so a page is cheap to read."""
SEARCH_PAGE_MAX = 200

BY_REFERENCE_SUFFIX: Final = "_reference"
"""What a secret argument's name gains to name the argument that takes the same secret by reference."""

_SECRET_FORMS: Final = (
    "Each secret argument has a sibling ending in _reference, and a call gives one of the two, never both. "
    "Text in the secret argument has already passed through this conversation and the host's transcript before "
    "it reaches this server. The reference form keeps the secret out of the conversation: the person runs "
    f"`cadrumo-mcp {HOLD_OPTION}` in a terminal of their own, types the secret there unseen, and gives you only "
    "the reference it prints. Prefer the reference and ask the person for one. A secret held that way stays "
    "until the person deletes it, so the same reference serves again after a lock or an expiry; one held with "
    f"{ONCE_OPTION} is spent by the first call that sends it, whatever that call then answers, and a send that "
    "then fails does not give it back; a call refused before it is sent, or made while no runtime is running, "
    "leaves it held. "
    "The reference of a secret a tool handed to the person, such as a recovery code, is accepted too, and "
    "using it neither shows the secret nor deletes it"
)

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


INSTALLATION_CONFIRM_ARGUMENT: Final = "confirm"
"""The tool argument that carries a request's confirmation, named as the session tool names it."""

INSTALLATION_CONFIRMED_MEMBER: Final = "confirmed"
"""The request member that argument fills."""

_INSTALLATION_COORDINATES: Final = frozenset({"request_id", "frontend", "action"})
_INSTALLATION_OWN_ARGUMENTS: Final = frozenset(
    {"secret", f"secret{BY_REFERENCE_SUFFIX}", INSTALLATION_CONFIRM_ARGUMENT}
)
_CARRIED_CONSTRAINTS: Final = ("enum", "minimum", "maximum", "minLength", "maxLength", "pattern", "format")
_INSTALLATION_PURPOSE: Final = (
    "Do work that needs no profile and no sign-in, as the command line does it: the storage tree (inventory, "
    "check, init, reclaim), the reset of all profiles, the profile list, profile archive inspect and import, "
    "recovery enrolment, repair, and verification of review packages and calculation reports. The runtime does "
    "the work, so it must be running. A file is named by its absolute path on this machine. An argument written "
    "with ? is optional. An action that takes confirm changes nothing unless confirm is true: without it the "
    "action answers with what it would do, or with a refusal that says so, as the command does without its "
    "confirmation flag. A completed action answers with its typed reply in reply; a refusal carries the "
    "runtime's code and, where the runtime recorded one, error_detail; an action that may have changed "
    "records before its outcome was lost answers unresolved and, where another action reads that outcome, "
    f"names it in outcome_read_by. {_UNKNOWN_OUTCOME}"
)
_INSTALLATION_PROTECTED_INPUT: Final = (
    "An action listed with secret takes the profile password, as text in secret or by reference in "
    "secret_reference: it travels to the runtime on the protected secret frame, apart from the other arguments, "
    f"and no reply repeats it. {_SECRET_FORMS}"
)
_INSTALLATION_HANDOVER: Final = (
    "An action that hands a secret to the person never returns it: one copy is held in this machine's "
    "protected credential store until the person has read it at a terminal of their own and confirmed they kept "
    "it, and the reply carries only secret_reference and, in secret_retrieval, how the person reads it. A "
    "reference a reply carries may be given wherever a secret is taken by reference, so a recovery code can "
    "be used before the person has read it: that sends the code to the runtime, shows it to nobody, and "
    "leaves it held until the person reads it or deletes it"
)
_INSTALLATION_TITLE: Final = "Manage the installation"


def _installation_argument(declaration: Mapping[str, Any], definitions: Mapping[str, Any]) -> _FieldSchema:
    """Reduce one request member's schema to the declaration a tool argument advertises.

    An optional member is advertised in its present form and is left out
    when unset; a named type is advertised as what it resolves to.
    """
    options = declaration.get("anyOf")
    if options is not None:
        present = [option for option in options if option.get("type") != "null"]
        if len(present) != 1:
            raise InternalInvariantError("an installation act argument has one present form")
        declaration = present[0]
    reference = declaration.get("$ref")
    if reference is not None:
        declaration = definitions[str(reference).rpartition("/")[2]]
    if declaration.get("type") not in {"string", "boolean", "integer"}:
        raise InternalInvariantError("an installation act argument is text, a flag or a whole number")
    carried = {key: declaration[key] for key in _CARRIED_CONSTRAINTS if key in declaration}
    return cast(_FieldSchema, {"type": declaration["type"], **carried})


def installation_act_arguments(contract: InstallationActContract) -> dict[str, tuple[_FieldSchema, bool]]:
    """Return the arguments one act takes on the tool, each with its declaration and whether it is required.

    They are the members of the act's request other than the coordinates the
    server supplies, so a request that gains a member gains the argument.
    """
    schema = contract.request.model_json_schema()
    definitions, required = schema.get("$defs", {}), set(schema.get("required", ()))
    arguments: dict[str, tuple[_FieldSchema, bool]] = {}
    for member, declaration in schema["properties"].items():
        if member in _INSTALLATION_COORDINATES:
            continue
        if member in _INSTALLATION_OWN_ARGUMENTS:
            raise InternalInvariantError("an installation request member takes the name of a tool argument")
        name = INSTALLATION_CONFIRM_ARGUMENT if member == INSTALLATION_CONFIRMED_MEMBER else member
        arguments[name] = (_installation_argument(declaration, definitions), member in required)
    return arguments


def _opening_sentence(model: type[BaseModel]) -> str:
    """Return the sentence a model's documentation opens with, as plain text."""
    text = " ".join((model.__doc__ or "").split()).replace("``", "")
    return text.partition(". ")[0].rstrip(".")


def installation_tool(acts: Collection[InstallationAct]) -> tuple[str, str, _ToolSchema]:
    """Build the ``installation`` tool for the acts given, from the act table and each act's models.

    Its action list, its arguments and the line that describes each action
    are read from the table, so an act the table gains is offered without
    being typed here. A surface that narrows passes only the acts it allows.
    """
    offered = [contract for act, contract in INSTALLATION_ACT_CONTRACTS.items() if act in acts]
    properties: dict[str, _FieldSchema] = {}
    actions: list[str] = []
    for contract in offered:
        takes: list[str] = []
        for name, (declaration, required) in installation_act_arguments(contract).items():
            if properties.setdefault(name, declaration) != declaration:
                raise InternalInvariantError("two installation acts declare one argument differently")
            takes.append(name if required else f"{name}?")
        if contract.takes_secret:
            takes.append("secret or secret_reference")
        handover = "; hands a secret to the person" if contract.delivers_secret else ""
        actions.append(
            f"{contract.act.value}({', '.join(takes)}{handover}): {_opening_sentence(contract.request)}. "
            f"Returns: {_opening_sentence(contract.reply)}"
        )
    sentences = [_INSTALLATION_PURPOSE]
    if any(contract.takes_secret for contract in offered):
        properties["secret"] = _SECRET
        properties[f"secret{BY_REFERENCE_SUFFIX}"] = _SECRET_REFERENCE
        sentences.append(_INSTALLATION_PROTECTED_INPUT)
    if any(contract.delivers_secret for contract in offered):
        sentences.append(_INSTALLATION_HANDOVER)
    action: _FieldSchema = {"type": "string", "enum": [contract.act.value for contract in offered]}
    return ("installation", ". ".join((*sentences, "Actions", *actions)), _schema({"action": action}, properties))


def _installation_hints() -> ToolHints:
    """Read the installation tool's hints from the act table: what any act in it can do."""
    facts = [contract.facts for contract in INSTALLATION_ACT_CONTRACTS.values()]
    if not any(fact.changes_records for fact in facts):
        return _reads(_INSTALLATION_TITLE)
    # An act that changes records includes the reset of every profile, so the change is not only additive.
    return _acts(_INSTALLATION_TITLE, destructive=True, open_world=any(fact.reaches_network for fact in facts))


_DECLARED_TOOLS: Final[tuple[tuple[str, str, _ToolSchema, ToolHints], ...]] = (
    (
        "status",
        "Current exact-profile authorization and availability. Finding and describing operations needs neither "
        "a sign-in nor a running Cadrumo: search and describe answer either way, as authority and corpus_search "
        "do, so what can be run is readable first. A notice member carries the runtime's lifecycle "
        "notice: upgrade_pending says an update is ready and the runtime restarts for it once idle, after which "
        "the next call re-establishes the session",
        _schema({}),
        _reads("Session and profile status"),
    ),
    (
        "authorization_prepare",
        "Prepare enrollment, or an own-grant change using a protected credential reference",
        _schema({}, {"credential_reference": _TEXT}),
        # A grant change can rotate a key, which replaces the one stored.
        _acts("Prepare an authorization request", destructive=True, open_world=False),
    ),
    (
        "authorization_request",
        "Submit a proposal for the prepared destination",
        _schema({"proposal": _DOC}),
        _acts("Submit an authorization proposal", destructive=True, open_world=False),
    ),
    (
        "authorization_poll",
        "Inspect or complete this connection's pending authorization",
        _schema({}),
        _acts("Check the pending authorization", destructive=True, open_world=False),
    ),
    (
        "authenticate",
        "Admit this connection using a protected credential reference",
        _schema({"credential_reference": _TEXT}),
        # Admission adds a session and takes nothing away.
        _acts("Authenticate with an enrolled key", destructive=False, open_world=False),
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
        "acts on, the effects it may have, the interactions it may ask for and whether it takes a secret. "
        "The contract and the request schema are not in a row: pass a small limit, then describe the operation "
        f"you pick. A page holds {SEARCH_PAGE_DEFAULT} rows when limit is omitted and at most {SEARCH_PAGE_MAX}: "
        "pass a returned next_cursor as cursor for the next page, and family to narrow to one definition "
        "family. It needs neither a sign-in nor a running Cadrumo: with no session the reply "
        "says session none and covers every registered operation on this connection's surface, where a session "
        "covers those in its scope",
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
        "the answer is a choice, the values it takes, as the command line lists them in its help. It needs "
        "neither a sign-in nor a running Cadrumo: with no session it answers with the same contract, schema and "
        "vocabulary, and the reply says session none",
        _schema({"definition_id": _TEXT}),
        _reads("Describe an operation"),
    ),
    (
        "execute",
        "Submit one registered operation under current profile authority. Leave subject_ref out: it is derived "
        "from the contract's subject_reference, the admitted profile and the payload. Only a stored_work_unit "
        "operation needs it, as the id of the work unit that owns the record its payload_path names. "
        "An operation whose contract says ephemeral_secret_required takes that secret, as text in secret or by "
        "reference in secret_reference, and no other operation accepts one: it travels to the runtime on the "
        "protected secret frame, apart from the payload, and no reply repeats it. An operation whose contract "
        "declares a transient_financial_operand takes its typed operator input as payload, with subject_ref and "
        "without idempotency_key. A payload the operation's request model refuses is answered refused with "
        "code invalid, and faults names each reason the model gave by location, type and message: a missing "
        "field, a field the request does not have, or the rule a value broke. It never repeats a value. "
        "Every call submits a new operation, so two identical calls run twice. "
        "idempotency_key is optional, and giving one makes a repeat safe: a repeat with the same key, operation "
        f"and payload answers with the operation already recorded and submits nothing. {_UNKNOWN_OUTCOME} "
        f"unless it carried an idempotency_key, and then repeat it only with that same key. {_SECRET_FORMS}",
        _schema(
            {"definition_id": _TEXT, "payload": _DOC},
            {
                "subject_ref": _TEXT,
                "idempotency_key": _TEXT,
                "start": {"type": "boolean"},
                "secret": _SECRET,
                f"secret{BY_REFERENCE_SUFFIX}": _SECRET_REFERENCE,
            },
        ),
        # Some registered operation deletes records, and some reads a remote host.
        _acts("Run an operation", destructive=True, open_world=True),
    ),
    (
        "observe",
        "Read a currently authorized operation observation",
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
    (
        "session",
        "Act on a profile's sessions as the command line does. Under the held session: list them, lock this "
        "session or the one target_session_id names, deny_automation of the given kind (a key or a grant named "
        "by target_id, all automation, or the whole profile), or sign_out the person. Without one: sign_in with "
        "the profile password in secret (store keeps the sign-in for every frontend and selects the profile; "
        "method api_key takes a raw key instead), sign_in_status, resume a locked profile with the password in "
        "secret and the grants to reactivate, reset_password with the recovery code in secret and the new "
        "password in new_secret and new_secret_confirmation, change_password with the current password in secret "
        "and the new one in the same two fields, delete_profile for the profile named, which only reports "
        "what would be destroyed unless confirm is true, and enable_recovery with the profile password in secret, "
        "for the profile named or else the selected one, which answers as the installation tool's recovery_enroll "
        "does: one copy of the recovery code is held in this machine's protected credential store until the "
        "person has read it at a terminal of their own and confirmed they kept it, and the reply carries only "
        "secret_reference and, in secret_retrieval, how the person reads it. Each secret travels on the runtime's "
        "protected secret frame and no reply repeats it. Wherever an action takes secret, new_secret or "
        "new_secret_confirmation it takes secret_reference, new_secret_reference or "
        "new_secret_confirmation_reference in its place; new_secret_reference and "
        "new_secret_confirmation_reference may name the same held secret. reset_password's secret_reference "
        "also takes the secret_reference enable_recovery answered with: the held recovery code is used without "
        f"being shown, and stays held until the person reads it or deletes it. {_SECRET_FORMS}. {_UNKNOWN_OUTCOME}",
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
                        "enable_recovery",
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
                f"secret{BY_REFERENCE_SUFFIX}": _SECRET_REFERENCE,
                f"new_secret{BY_REFERENCE_SUFFIX}": _SECRET_REFERENCE,
                f"new_secret_confirmation{BY_REFERENCE_SUFFIX}": _SECRET_REFERENCE,
            },
        ),
        # Deleting a profile destroys it; every act stays on this machine.
        _acts("Manage profile sessions", destructive=True, open_world=False),
    ),
    (*installation_tool(tuple(INSTALLATION_ACT_CONTRACTS)), _installation_hints()),
)
MCP_TOOL_CATALOGUE = tuple((name, description, schema) for name, description, schema, _hints in _DECLARED_TOOLS)
"""Each tool as it is advertised: its name, its description and the schema of its arguments."""

MCP_TOOL_HINTS: Final[Mapping[str, ToolHints]] = MappingProxyType(
    {name: hints for name, _description, _arguments, hints in _DECLARED_TOOLS}
)
"""Each tool's hints, declared beside it in the catalogue."""

_TOOL_SCHEMAS = {name: schema for name, _description, schema in MCP_TOOL_CATALOGUE}
MCP_TOOL_NAMES = frozenset(_TOOL_SCHEMAS)


def tool_catalogue(installation_acts: Collection[InstallationAct]) -> tuple[tuple[str, str, _ToolSchema], ...]:
    """Return the catalogue as one connection advertises it, offering only these installation acts."""
    narrowed = installation_tool(installation_acts)
    return tuple(narrowed if entry[0] == narrowed[0] else entry for entry in MCP_TOOL_CATALOGUE)


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


_EXECUTE_STEPS: Final = ("secret_delivery", "start")
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
    instead: the operation, the act that reads it, or the request alone.
    """
    if value.get("outcome") == "unresolved":
        if "act" in value:
            reader = (
                f"read it with the installation action {value['outcome_read_by']}"
                if "outcome_read_by" in value
                else "no action reads it directly, so read what the action changes with the installation tool's "
                "reading actions before deciding anything"
            )
            return f"{_NOT_KNOWN}. {_NEVER_REPEAT}: {reader}, and tell the person the outcome is not known."
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
        return (
            f"{_NOT_KNOWN}. {_NEVER_REPEAT}: request_id identifies what was sent, and authorization_poll reads "
            "where it stands."
        )
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

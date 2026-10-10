"""The recorded MCP decision of every registered operation, held to the live registry.

Listing the MCP frontend on a definition opens that operation to an MCP
client. The recorded decisions say which operations may be opened, and this
census makes the record and the live production registry answer for each
other: an operation with no decision, a decision for an operation that is not
registered, and a definition whose frontends contradict its decision are each
a finding.

A frontend list is a declaration. Several access resolvers compare the
frontend themselves, so a listed frontend is also put to each operation's real
resolver wherever a request can be built from its registered schema alone.

Like the exposure census beside it, this file passes on membership and shape
and never on a count.
"""

from __future__ import annotations

import ast
import json
import re
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, replace
from functools import cache
from typing import Any
from uuid import UUID

import pytest
from pydantic import BaseModel

from cadrumo_harness.mcp.protocol_contract import MCP_TOOL_CATALOGUE

from ...application.operations.access_resolution import OperationAccessContext, resolve_operation_access
from ...application.operations.capabilities import OperationOwnedResource
from ...application.operations.mcp_admission import (
    MCP_ADMISSION_DECISIONS,
    MCP_OVER_DECLARED_EFFECTS,
    McpAdmissionDecision,
    McpAdmissionPrerequisite,
    McpExclusionReason,
    McpRuling,
    mcp_admission_decision,
)
from ...application.operations.models import OperationRequest
from ...application.operations.registry import OperationFrontendProjection, OperationPublicDefinitionRegistrationV1
from ...application.user_profile.access_contracts import (
    AccessAction,
    AccessDenialCode,
    Availability,
    OperationAccessRequest,
)
from ...application.user_profile.access_errors import ProfileAccessRefusedError
from ...core.errors.hierarchy import CadrumoError
from ...core.operations import OperationEffect, profile_operation_subject
from ...core.period import Period
from ...domain.calculations.registry.remote_state_guard import AEAT_WRITE_FORBIDDEN_VERB_TOKENS
from .test_operation_catalogue import _parsed, _production_sources, _registry

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_MCP = OperationFrontendProjection.MCP
_COMMITTED_EFFECTS = frozenset({OperationEffect.UPDATED, OperationEffect.PARTIAL})
_LOCAL_COMMIT_EXTENTS = frozenset({"none", "updated", "partial", "unknown"})
"""The only extents an operation may declare: how much of its own local work committed."""


def _registrations() -> tuple[OperationPublicDefinitionRegistrationV1, ...]:
    return _registry().public_registrations


def _lists_mcp(registration: OperationPublicDefinitionRegistrationV1) -> bool:
    return _MCP in registration.contract.permitted_frontends


def _decision(registration: OperationPublicDefinitionRegistrationV1) -> McpAdmissionDecision:
    return mcp_admission_decision(registration.contract.definition_id)


def _ids_where(predicate: Callable[[OperationPublicDefinitionRegistrationV1], bool]) -> list[str]:
    return sorted(item.contract.definition_id for item in _registrations() if predicate(item))


def _findings(check: Callable[[OperationPublicDefinitionRegistrationV1], str | None]) -> dict[str, str]:
    """What a rule finds wrong, by definition id, across the whole live registry."""
    found: dict[str, str] = {}
    for item in _registrations():
        finding = check(item)
        if finding is not None:
            found[item.contract.definition_id] = finding
    return found


def _mcp_listed_ids() -> list[str]:
    return _ids_where(_lists_mcp)


def test_every_registered_operation_has_exactly_one_recorded_decision() -> None:
    """The record and the registry name the same operations, both directions."""
    registered = {item.contract.definition_id for item in _registrations()}
    recorded = [decision.definition_id for decision in MCP_ADMISSION_DECISIONS]
    assert len(set(recorded)) == len(recorded)
    undecided = sorted(registered - set(recorded))
    unregistered = sorted(set(recorded) - registered)
    assert not undecided, f"registered operations with no recorded MCP decision: {undecided}"
    assert not unregistered, f"recorded MCP decisions for operations that are not registered: {unregistered}"


def _listing_finding(decision: McpAdmissionDecision, *, lists_mcp: bool) -> str | None:
    """Say how a definition's MCP listing contradicts its recorded decision, if it does."""
    if decision.ruling is McpRuling.EXCLUDED:
        return "is excluded but lists the MCP frontend" if lists_mcp else None
    if decision.ruling is McpRuling.ADMITTED_BEHIND_APPROVAL:
        # Whether a sensitive act is listed follows from whether the person's
        # approval reaches it, which a frontend list cannot show.
        return None
    if decision.prerequisites and lists_mcp:
        outstanding = sorted(item.value for item in decision.prerequisites)
        return f"lists the MCP frontend with a prerequisite outstanding: {outstanding}"
    if not decision.prerequisites and not lists_mcp:
        return "is admitted with nothing outstanding but does not list the MCP frontend"
    return None


def test_every_definition_lists_mcp_as_its_recorded_decision_says() -> None:
    """An excluded or still-gated operation is closed; an admitted one with nothing outstanding is open."""
    findings = _findings(lambda item: _listing_finding(_decision(item), lists_mcp=_lists_mcp(item)))
    assert not findings, f"definitions whose MCP listing contradicts their recorded decision: {findings}"


def test_the_listing_rule_detects_each_contradiction() -> None:
    """The rule fails an open exclusion, an open gated admission and a closed clear admission."""
    excluded = McpAdmissionDecision(
        definition_id="domain.thing.administer",
        ruling=McpRuling.EXCLUDED,
        changes_records=True,
        reaches_network=False,
        exclusion_reason=McpExclusionReason.ACCESS_ADMINISTRATION,
    )
    gated = McpAdmissionDecision(
        definition_id="domain.thing.import",
        ruling=McpRuling.ADMITTED,
        changes_records=True,
        reaches_network=False,
        prerequisites=frozenset({McpAdmissionPrerequisite.FILE_EXCHANGE}),
    )
    clear = replace(gated, definition_id="domain.thing.read", prerequisites=frozenset())
    sensitive = replace(clear, definition_id="domain.thing.remove", ruling=McpRuling.ADMITTED_BEHIND_APPROVAL)
    open_while_gated = "lists the MCP frontend with a prerequisite outstanding: ['file_exchange']"
    closed_while_clear = "is admitted with nothing outstanding but does not list the MCP frontend"

    assert _listing_finding(excluded, lists_mcp=True) == "is excluded but lists the MCP frontend"
    assert _listing_finding(excluded, lists_mcp=False) is None
    assert _listing_finding(gated, lists_mcp=True) == open_while_gated
    assert _listing_finding(gated, lists_mcp=False) is None
    assert _listing_finding(clear, lists_mcp=False) == closed_while_clear
    assert _listing_finding(clear, lists_mcp=True) is None
    assert _listing_finding(sensitive, lists_mcp=True) is None
    assert _listing_finding(sensitive, lists_mcp=False) is None


def _is_runnable_but_recorded_as_not(registration: OperationPublicDefinitionRegistrationV1) -> bool:
    runnable = registration.access_resolver is not None and not registration.contract.ephemeral_secret_required
    return runnable and _decision(registration).exclusion_reason is McpExclusionReason.NOT_RUNNABLE


def test_every_not_runnable_exclusion_is_still_not_runnable() -> None:
    """A definition that gained a resolver and needs no typed secret is no longer excluded on that ground."""
    stale = _ids_where(_is_runnable_but_recorded_as_not)
    assert not stale, f"recorded as not runnable, but resolvable and needing no typed secret: {stale}"


def test_every_agent_facing_sibling_is_registered_and_lists_mcp() -> None:
    """A person's projection stays excluded only while an open sibling serves its content."""
    listed = set(_mcp_listed_ids())
    unserved: dict[str, str] = {}
    for decision in MCP_ADMISSION_DECISIONS:
        sibling = decision.agent_facing_sibling
        if sibling is not None and sibling not in listed:
            unserved[decision.definition_id] = sibling
    assert not unserved, f"excluded projections whose agent-facing sibling is not open to MCP: {unserved}"


def _effect_finding(
    decision: McpAdmissionDecision, *, permitted: frozenset[OperationEffect], over_declared: bool
) -> str | None:
    """Say how the recorded change fact contradicts what the definition permits, if it does."""
    permits_commit = not permitted.isdisjoint(_COMMITTED_EFFECTS)
    if decision.changes_records:
        if over_declared:
            return "is recorded as changing records and also as over-declaring its effects"
        return None if permits_commit else "is recorded as changing records but permits no committed effect"
    if permits_commit and not over_declared:
        return "is recorded as not changing records but permits a committed effect"
    if over_declared and not permits_commit:
        return "no longer permits a committed effect and must leave the over-declared record"
    return None


def _registered_effect_finding(registration: OperationPublicDefinitionRegistrationV1) -> str | None:
    return _effect_finding(
        _decision(registration),
        permitted=registration.contract.permitted_effects,
        over_declared=registration.contract.definition_id in MCP_OVER_DECLARED_EFFECTS,
    )


def test_the_recorded_change_fact_agrees_with_every_definitions_permitted_effects() -> None:
    """A read may not permit a committed effect unless it is named as over-declared, and that list only shrinks."""
    registered = {item.contract.definition_id for item in _registrations()}
    unknown = sorted(set(MCP_OVER_DECLARED_EFFECTS) - registered)
    assert not unknown, f"over-declared record names operations that are not registered: {unknown}"
    unexplained = sorted(key for key, reason in MCP_OVER_DECLARED_EFFECTS.items() if not reason.strip())
    assert not unexplained, f"over-declared record states no reason: {unexplained}"
    findings = _findings(_registered_effect_finding)
    assert not findings, f"recorded change facts that contradict the definition: {findings}"


def test_the_change_rule_detects_each_contradiction() -> None:
    """The rule fails an unlisted over-declaration, a stale listing and an unbacked change."""
    read = McpAdmissionDecision(
        definition_id="domain.thing.list", ruling=McpRuling.ADMITTED, changes_records=False, reaches_network=False
    )
    write = replace(read, definition_id="domain.thing.set", changes_records=True)
    reading = frozenset({OperationEffect.NONE, OperationEffect.UNKNOWN})
    updating = reading | {OperationEffect.UPDATED}
    partial = reading | {OperationEffect.PARTIAL}

    assert _effect_finding(read, permitted=reading, over_declared=False) is None
    assert _effect_finding(read, permitted=updating, over_declared=True) is None
    assert _effect_finding(write, permitted=updating, over_declared=False) is None
    assert _effect_finding(write, permitted=partial, over_declared=False) is None
    assert _effect_finding(read, permitted=updating, over_declared=False) is not None
    assert _effect_finding(read, permitted=partial, over_declared=False) is not None
    assert _effect_finding(read, permitted=reading, over_declared=True) is not None
    assert _effect_finding(write, permitted=reading, over_declared=False) is not None
    assert _effect_finding(write, permitted=updating, over_declared=True) is not None


def _owns_a_process_but_is_recorded_as_local(registration: OperationPublicDefinitionRegistrationV1) -> bool:
    owns_process = OperationOwnedResource.PROCESS in registration.contract.owned_resources
    return owns_process and not _decision(registration).reaches_network


def test_every_definition_that_owns_a_process_is_recorded_as_reaching_the_network() -> None:
    """The one resource a definition declares for a remote read is its browser process."""
    unrecorded = _ids_where(_owns_a_process_but_is_recorded_as_local)
    assert not unrecorded, f"definitions that own a browser process but are recorded as local: {unrecorded}"


def test_every_mcp_listed_definition_has_an_access_resolver() -> None:
    """Without a resolver every access is refused, so the listing would promise nothing."""
    unresolvable = _ids_where(lambda item: _lists_mcp(item) and item.access_resolver is None)
    assert not unresolvable, f"definitions that list MCP and have no access resolver: {unresolvable}"


# ---------------------------------------------------------------------------
# The real resolver, put to the MCP frontend
# ---------------------------------------------------------------------------

_PROBE_PROFILE = UUID("5aa00000-0000-4000-8000-0000000000aa")
_PROBE_DESTINATION = UUID("5aa00000-0000-4000-8000-0000000000bb")
_PROBE_PERIOD = Period.from_year_and_code(2025, "1T")
_RESOLVED = "resolved"
_FRONTEND_REFUSAL = f"refused:{AccessDenialCode.FRONTEND_DENIED.value}"

_PATTERN_SAMPLES: tuple[str, ...] = (
    str(_PROBE_PROFILE),
    "0" * 64,
    f"sha256:{'0' * 64}",
    "0" * 10,
    "303",
    "2025",
    "1T",
    "es",
    "ES",
    "EUR",
    "a",
    "0",
)
"""Texts tried against a schema pattern; a pattern none of them fits has no generic sample."""


@dataclass(frozen=True, slots=True)
class _SampleChoice:
    """How one sample fills what a schema leaves open.

    A schema does not carry the rules a request model checks in code, so one
    fixed filling is refused by many models. Each choice is a different
    uniform filling; none of them knows which operation it is for.
    """

    text: str
    whole_number: int
    alternative: int


_SAMPLE_CHOICES: tuple[_SampleChoice, ...] = tuple(
    _SampleChoice(text=text, whole_number=whole_number, alternative=alternative)
    for alternative in range(8)
    for whole_number in (0, 2025)
    for text in ("0", "1T", "x", "0" * 12)
)


class _NoGenericSampleError(Exception):
    """The schema asks for a value that cannot be chosen without knowing the operation."""


def _string_sample(schema: Mapping[str, Any], choice: _SampleChoice) -> str:
    text_format = schema.get("format")
    if text_format == "uuid":
        return str(_PROBE_PROFILE)
    if text_format == "date":
        return "2025-01-01"
    if text_format == "date-time":
        return "2025-01-01T00:00:00Z"
    minimum = int(schema.get("minLength", 0))
    maximum = schema.get("maxLength")
    pattern = schema.get("pattern")
    if pattern is None:
        limit = max(minimum, len(choice.text)) if maximum is None else int(maximum)
        return (choice.text * max(1, minimum))[:limit]
    for candidate in _PATTERN_SAMPLES:
        fits_length = len(candidate) >= minimum and (maximum is None or len(candidate) <= int(maximum))
        if fits_length and re.fullmatch(str(pattern), candidate) is not None:
            return candidate
    raise _NoGenericSampleError(str(pattern))


def _number_sample(schema: Mapping[str, Any], choice: _SampleChoice) -> int:
    floor = int(schema["exclusiveMinimum"]) + 1 if "exclusiveMinimum" in schema else int(schema.get("minimum", 0))
    value = max(floor, choice.whole_number)
    if "exclusiveMaximum" in schema:
        value = min(value, int(schema["exclusiveMaximum"]) - 1)
    return min(value, int(schema["maximum"])) if "maximum" in schema else value


def _object_sample(schema: Mapping[str, Any], definitions: Mapping[str, Any], choice: _SampleChoice) -> dict[str, Any]:
    properties: Mapping[str, Mapping[str, Any]] = schema.get("properties", {})
    required = set(schema.get("required", ()))
    # A fixed member is what tells one shape of a union from another, so it is
    # written even where the schema lets it default.
    return {
        name: _schema_sample(declaration, definitions, choice)
        for name, declaration in properties.items()
        if name in required or "const" in declaration
    }


def _schema_sample(schema: Mapping[str, Any], definitions: Mapping[str, Any], choice: _SampleChoice) -> Any:
    """Build the smallest document a JSON schema admits: required and fixed members only."""
    if "$ref" in schema:
        return _schema_sample(definitions[str(schema["$ref"]).rsplit("/", 1)[-1]], definitions, choice)
    if "const" in schema:
        return schema["const"]
    if "enum" in schema:
        return schema["enum"][choice.alternative % len(schema["enum"])]
    for union in ("anyOf", "oneOf", "allOf"):
        branches = [branch for branch in schema.get(union, ()) if branch.get("type") != "null"]
        if branches:
            return _schema_sample(branches[0], definitions, choice)
    kind = schema.get("type")
    if kind == "object":
        return _object_sample(schema, definitions, choice)
    if kind == "array":
        items = schema.get("items", {})
        return [_schema_sample(items, definitions, choice) for _ in range(int(schema.get("minItems", 0)))]
    if kind == "string":
        return _string_sample(schema, choice)
    if kind in {"integer", "number"}:
        return _number_sample(schema, choice)
    if kind == "boolean":
        return False
    if kind == "null":
        return None
    raise _NoGenericSampleError(str(kind))


def _sample_text(schema: Mapping[str, Any], definitions: Mapping[str, Any], choice: _SampleChoice) -> str | None:
    try:
        return json.dumps(_schema_sample(schema, definitions, choice), sort_keys=True)
    except (_NoGenericSampleError, LookupError):
        return None


def _decoded_request(definition_id: str, sample: str) -> OperationRequest[BaseModel] | None:
    """Admit one sample through the registry's own decoder, or report that the model refuses it."""
    try:
        return OperationRequest(
            definition_id=definition_id,
            subject_ref=profile_operation_subject(str(_PROBE_PROFILE)),
            payload=_registry().decode_request_payload(definition_id, sample),
        )
    except (CadrumoError, ValueError, LookupError):
        return None


@cache
def _probe_requests(definition_id: str) -> tuple[OperationRequest[BaseModel], ...]:
    """Every distinct request the operation's own registered schema and decoder accept.

    Each sample is built from the registered request schema alone and admitted
    through the registry's own decoder, so a request that comes back is one the
    operation would accept. A model whose rules need operation-specific
    knowledge accepts none, and that operation is then not proven here.
    """
    schema = _registry().describe_public_definition(definition_id).request_json_schema
    declared = schema.get("$defs", {})
    definitions: Mapping[str, Any] = declared if isinstance(declared, dict) else {}
    texts = (_sample_text(schema, definitions, choice) for choice in _SAMPLE_CHOICES)
    samples = dict.fromkeys(text for text in texts if text is not None)
    decoded = (_decoded_request(definition_id, sample) for sample in samples)
    return tuple(request for request in decoded if request is not None)


def _probe_contexts(
    registration: OperationPublicDefinitionRegistrationV1, frontend: OperationFrontendProjection
) -> Iterable[tuple[str, OperationAccessContext]]:
    """The host positions a resolver can be asked from without stored records.

    A fresh submission needs no earlier state. Observing an admitted
    submission replays its admitted scope, which is how a resolver that would
    otherwise read the addressed record's period can still be asked.
    """
    submit = OperationAccessContext(
        profile_id=_PROBE_PROFILE,
        destination_id=_PROBE_DESTINATION,
        action=AccessAction.SUBMIT,
        frontend=frontend,
        contract=registration.contract,
        published_authority=Availability.AVAILABLE,
    )
    yield "submit", submit
    replayed_scopes: tuple[tuple[str, frozenset[Period]], ...] = (
        ("observe-whole-profile", frozenset[Period]()),
        ("observe-one-period", frozenset({_PROBE_PERIOD})),
    )
    for label, periods in replayed_scopes:
        admitted = OperationAccessRequest(
            profile_id=_PROBE_PROFILE,
            definition_id=registration.contract.definition_id,
            action=AccessAction.SUBMIT,
            frontend=frontend,
            periods=periods,
            period_independent=not periods,
            destination_id=_PROBE_DESTINATION,
        )
        yield label, replace(submit, action=AccessAction.OBSERVE, admitted_request=admitted)


def _resolution(request: OperationRequest[BaseModel], context: OperationAccessContext) -> str:
    """Ask the registered resolver and name what it answered."""
    try:
        resolve_operation_access(registry=_registry(), request=request, context=context)
    except ProfileAccessRefusedError as refused:
        return f"refused:{refused.reason.value}"
    except (CadrumoError, ValueError, LookupError) as error:
        return f"undecided:{type(error).__name__}"
    return _RESOLVED


@cache
def _resolutions(definition_id: str) -> Mapping[str, Mapping[OperationFrontendProjection, str]]:
    """Every probe's answer for each frontend the definition lists; empty without a request."""
    registration = _registry().lookup_public_registration(definition_id)
    answers: dict[str, dict[OperationFrontendProjection, str]] = {}
    for index, request in enumerate(_probe_requests(definition_id)):
        for frontend in sorted(registration.contract.permitted_frontends):
            for position, context in _probe_contexts(registration, frontend):
                answers.setdefault(f"request {index}, {position}", {})[frontend] = _resolution(request, context)
    return answers


def _resolves_for_mcp(definition_id: str) -> bool:
    return any(answers.get(_MCP) == _RESOLVED for answers in _resolutions(definition_id).values())


_MCP_RESOLUTION_NOT_PROVEN: frozenset[str] = frozenset(
    {
        "ledger.actividad-asset.claim",
        "ledger.actividad-asset.correct",
        "ledger.actividad-asset.create",
        "ledger.invoice.add",
        "ledger.invoice.update",
        "ledger.split.review",
        "modelo.aggregate.capture_received_invoice_retencion",
        "modelo.reconcile.pull",
        "overview.calendar",
        "overview.explain",
        "overview.prepare",
        "user-profile.censo-review",
    }
)
"""Operations that list MCP whose resolver could not be brought to admit it here.

Their request model checks rules a schema does not carry, so no generic sample
passes its decoder, or the resolver refuses every generic sample that does.
Every other listed operation is admitted by its real resolver in this file. An
operation leaves this set as soon as a probe admits it, and none joins it
without that admission having been attempted."""


def test_no_resolver_treats_the_mcp_frontend_differently_from_the_others_it_lists() -> None:
    """A resolver that compares the frontend itself must agree with the definition's list."""
    refused: list[tuple[str, str]] = []
    divergent: list[tuple[str, str, dict[str, str]]] = []
    for definition_id in _mcp_listed_ids():
        for label, answers in _resolutions(definition_id).items():
            if answers[_MCP] == _FRONTEND_REFUSAL:
                refused.append((definition_id, label))
            if len(set(answers.values())) > 1:
                divergent.append((definition_id, label, {key.value: value for key, value in answers.items()}))
    assert not refused, f"definitions that list MCP and whose resolver refuses that frontend: {refused}"
    assert not divergent, f"resolvers that answer the MCP frontend differently from another listed one: {divergent}"


def test_every_mcp_listed_definition_is_admitted_by_its_real_resolver() -> None:
    """Listing is a claim; admission through the resolver is the proof, and the gaps are named."""
    listed = set(_mcp_listed_ids())
    unproven = {definition_id for definition_id in listed if not _resolves_for_mcp(definition_id)}
    newly_unproven = {item: dict(_resolutions(item)) for item in sorted(unproven - _MCP_RESOLUTION_NOT_PROVEN)}
    assert not newly_unproven, f"definitions that list MCP but that no probe of their resolver admits: {newly_unproven}"
    stale = sorted(_MCP_RESOLUTION_NOT_PROVEN - unproven)
    assert not stale, f"named as unproven, but now admitted or no longer listed, and must be removed: {stale}"
    # The proof must rest on real admissions, or naming every operation a gap would pass.
    assert listed - unproven


def test_every_admission_the_probe_reports_is_refused_for_another_profile() -> None:
    """The admissions above are decisions: the same resolvers refuse the same requests for a foreign profile."""
    registry = _registry()
    foreign_profile = UUID("5aa00000-0000-4000-8000-0000000000cc")
    admitted = 0
    unrefused: list[tuple[str, str]] = []
    for definition_id in _mcp_listed_ids():
        registration = registry.lookup_public_registration(definition_id)
        for request in _probe_requests(definition_id)[:1]:
            for position, context in _probe_contexts(registration, _MCP):
                if _resolution(request, context) != _RESOLVED:
                    continue
                admitted += 1
                foreign = _resolution(request, replace(context, profile_id=foreign_profile))
                if not foreign.startswith("refused:"):
                    unrefused.append((definition_id, position))
    assert admitted
    assert not unrefused, f"resolvers that admit a request addressed to another profile: {unrefused}"


def test_the_schema_sample_keeps_to_required_members_and_declared_shapes() -> None:
    """The sampler writes only required and fixed members, and gives up on an unknown pattern."""
    schema: dict[str, Any] = {
        "type": "object",
        "required": ["profile_id", "digest", "mode", "count", "label", "nested"],
        "properties": {
            "profile_id": {"type": "string", "format": "uuid"},
            "digest": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
            "mode": {"enum": ["preview", "apply"]},
            "count": {"type": "integer", "exclusiveMinimum": 0, "maximum": 50},
            "label": {"type": "string", "minLength": 3},
            "nested": {"$ref": "#/$defs/Nested"},
            "kind": {"const": "thing", "default": "thing"},
            "optional": {"type": "string"},
        },
        "$defs": {"Nested": {"type": "object", "required": ["flag"], "properties": {"flag": {"type": "boolean"}}}},
    }
    fixed = {"profile_id": str(_PROBE_PROFILE), "digest": "0" * 64, "nested": {"flag": False}, "kind": "thing"}

    first = _schema_sample(schema, schema["$defs"], _SampleChoice(text="0", whole_number=0, alternative=0))
    second = _schema_sample(schema, schema["$defs"], _SampleChoice(text="1T", whole_number=2025, alternative=1))

    assert first == {**fixed, "mode": "preview", "count": 1, "label": "000"}
    assert second == {**fixed, "mode": "apply", "count": 50, "label": "1T1"}
    with pytest.raises(_NoGenericSampleError):
        _schema_sample({"type": "string", "pattern": "^never-[a-z]{40}-matches$"}, {}, _SAMPLE_CHOICES[0])


# ---------------------------------------------------------------------------
# No operation and no tool declares a submission to the tax agency
# ---------------------------------------------------------------------------

_LIVE_WRITE = "live_write"


def _declares_no_live_write(value: ast.expr) -> bool:
    """Whether a declared value is the literal refusal or forwards an existing declaration."""
    if isinstance(value, ast.Constant):
        return value.value is False
    if isinstance(value, ast.Attribute):
        return value.attr == _LIVE_WRITE
    return isinstance(value, ast.Name) and value.id == _LIVE_WRITE


def _binds_live_write(target: ast.expr) -> bool:
    if isinstance(target, ast.Name):
        return target.id == _LIVE_WRITE
    return isinstance(target, ast.Attribute) and target.attr == _LIVE_WRITE


def _live_write_values(tree: ast.AST) -> Iterable[ast.expr]:
    """Every value a tree gives the command policy's live-write declaration."""
    for node in ast.walk(tree):
        if (
            (isinstance(node, ast.keyword) and node.arg == _LIVE_WRITE)
            or (isinstance(node, ast.AnnAssign) and node.value is not None and _binds_live_write(node.target))
            or (isinstance(node, ast.Assign) and any(_binds_live_write(target) for target in node.targets))
        ):
            yield node.value
        elif isinstance(node, ast.arguments):
            positional = [*node.posonlyargs, *node.args]
            defaulted = positional[len(positional) - len(node.defaults) :]
            for argument, default in zip(defaulted, node.defaults, strict=True):
                if argument.arg == _LIVE_WRITE:
                    yield default
            for argument, keyword_default in zip(node.kwonlyargs, node.kw_defaults, strict=True):
                if argument.arg == _LIVE_WRITE and keyword_default is not None:
                    yield keyword_default


def test_no_command_policy_in_the_source_tree_declares_a_live_write() -> None:
    """The one declaration a command has for a submission is never set anywhere."""
    declared = [(path, value) for path in _production_sources() for value in _live_write_values(_parsed(path))]
    # The scan must reach the declarations it judges, or it would pass on nothing.
    assert declared
    offenders = sorted((path, value.lineno) for path, value in declared if not _declares_no_live_write(value))
    assert not offenders, f"a command policy declares a live write to the tax agency: {offenders}"


def test_the_live_write_scan_detects_every_way_of_declaring_one() -> None:
    """A keyword, a default and an assignment are all read; a forwarded declaration is not one."""
    source = (
        "policy = ExecutionPolicySpec(capabilities=frozenset(), live_write=True)\n"
        "class Policy:\n"
        "    live_write: bool = True\n"
        "def build(*, live_write=True): ...\n"
        "spec.live_write = enabled\n"
        "safe = ExecutionPolicySpec(live_write=False)\n"
        "projected = Metadata(live_write=declared.live_write)\n"
    )
    verdicts = [_declares_no_live_write(value) for value in _live_write_values(ast.parse(source))]
    # Four declarations set or could set a live write; the last two lines of the source do not.
    assert sorted(verdicts) == [False, False, False, False, True, True]


def _name_words(name: str) -> frozenset[str]:
    """The words of a dotted, dashed or underscored identifier."""
    return frozenset(word for word in re.split(r"[^a-z0-9]+", name.casefold()) if isinstance(word, str) and word)


def _write_verbs(names: Iterable[str]) -> frozenset[str]:
    """The tax agency's write verbs that appear as whole words in these names."""
    return frozenset(word for name in names for word in _name_words(name)) & AEAT_WRITE_FORBIDDEN_VERB_TOKENS


_NETWORK_READS_NAMED_LIKE_A_WRITE: Mapping[str, str] = {
    "live.verify.tgvi": "reads whether a tax id is registered for intra-community operations; it sends nothing",
}
"""Operations that reach the network and whose name carries a write verb of the tax agency.

Each is a read whose name collides with the verb list. The entry must keep
answering a live collision, so a renamed or removed operation fails here."""


def test_every_operation_permits_only_local_extents_of_commit() -> None:
    """No definition declares an effect other than how much of its own local work committed."""
    foreign = {
        item.contract.definition_id: sorted(effect.value for effect in item.contract.permitted_effects)
        for item in _registrations()
        if not {effect.value for effect in item.contract.permitted_effects} <= _LOCAL_COMMIT_EXTENTS
    }
    assert not foreign, f"definitions that declare an effect outside the local commit extents: {foreign}"


def test_no_operation_that_reaches_the_network_is_named_for_a_tax_agency_write() -> None:
    """An operation that can contact a host never carries a submission verb in its id or phases."""
    collisions: dict[str, list[str]] = {}
    for definition in _registry().definitions:
        verbs = _write_verbs((definition.definition_id, *definition.phase_codes))
        if verbs and mcp_admission_decision(definition.definition_id).reaches_network:
            collisions[definition.definition_id] = sorted(verbs)
    undeclared = {key: verbs for key, verbs in collisions.items() if key not in _NETWORK_READS_NAMED_LIKE_A_WRITE}
    assert not undeclared, f"operations that reach the network and are named for a tax agency write: {undeclared}"
    stale = sorted(set(_NETWORK_READS_NAMED_LIKE_A_WRITE) - set(collisions))
    assert not stale, f"named as a read that collides with a write verb, but no longer collides: {stale}"
    unexplained = sorted(key for key, reason in _NETWORK_READS_NAMED_LIKE_A_WRITE.items() if not reason.strip())
    assert not unexplained, f"a declared name collision states no reason: {unexplained}"


def _tool_vocabulary(schema: Mapping[str, object]) -> tuple[str, ...]:
    """Every value a tool's input schema enumerates."""
    properties = schema.get("properties")
    values: list[str] = []
    if isinstance(properties, Mapping):
        for declaration in properties.values():
            enumerated = declaration.get("enum") if isinstance(declaration, Mapping) else None
            if isinstance(enumerated, (list, tuple)):
                values.extend(str(value) for value in enumerated)
    return tuple(values)


def test_no_mcp_tool_is_named_for_a_tax_agency_write() -> None:
    """No tool name, and no action a tool enumerates, is a submission verb."""
    tools = list(MCP_TOOL_CATALOGUE)
    assert tools
    named: dict[str, list[str]] = {}
    for name, _description, schema in tools:
        verbs = _write_verbs((name, *_tool_vocabulary(schema)))
        if verbs:
            named[name] = sorted(verbs)
    assert not named, f"MCP tools that name or enumerate a tax agency write: {named}"


def test_the_write_verb_reading_matches_whole_words_only() -> None:
    """A verb is read as a word of the name, never as a fragment of another word."""
    assert _write_verbs(("live.modelo.presentar",)) == frozenset({"presentar"})
    assert _write_verbs(("aeat_submit", "modelo.work.sign-and-send")) == frozenset({"submit", "sign"})
    assert _write_verbs(("ledger.design.assignment", "overview.savepoint")) == frozenset()
    enumerated = _tool_vocabulary({"properties": {"action": {"type": "string", "enum": ["inspect", "submit"]}}})
    assert enumerated == ("inspect", "submit")

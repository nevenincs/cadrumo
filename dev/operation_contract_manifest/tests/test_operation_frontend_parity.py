"""Every registered operation is answered alike on every frontend: the person's and the delegated clients'.

The one exception is the person's own act: a credential or access act, or a
request carrying the person's consent to send a stored document off this
machine. It is answered alike on the person's frontends, and on external client and the
automation host it is either answered the same or refused with the typed
person-act refusal.

No definition declares the frontends it is open to: every registered
operation is open to all of them. What a submission is answered is decided in
two places, the operation's own access resolver and the access policy that
holds the resolved access to the session, and neither may tell the frontends
apart. This file puts both to every registered operation, through the
production registry and with the real policy evaluation.

Each operation is asked on requests built from its registered schema alone
and admitted through its own decoder. Where its resolver admits none of those,
because it reads stored records or its request model checks rules a schema
does not carry, it is asked on the request its executor's conformance scenario
seeds into a real profile. The answer to the command line, the terminal
interface and external client must be the same: admitted with the same policy, or refused
with the same code, for a session of the human kind and for a key session
whose scope holds everything. Requests written out because no generic sample
states what they state are held to the same rule at every position a resolver
can be asked from.

Like the exposure census beside it, this file passes on membership and shape
and never on a count.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, replace
from functools import cache
from pathlib import Path
from typing import Any
from uuid import UUID

import pytest
from pydantic import BaseModel

from cadrumo.application.ledger.invoice_evidence_extract_operation import LedgerEvidenceExtractRequest
from cadrumo.application.operations.access_resolution import OperationAccessContext, resolve_operation_access
from cadrumo.application.operations.models import OperationRequest
from cadrumo.application.operations.operation_definition import OperationDefinition
from cadrumo.application.operations.person_acts import operation_is_persons_act
from cadrumo.application.operations.registry import (
    OperationFrontendProjection,
    OperationPublicDefinitionContractV1,
    OperationPublicDefinitionRegistrationV1,
    OperationRegistry,
)
from cadrumo.application.operations.subject_reference import expected_operation_subject
from cadrumo.application.user_profile.access_contracts import (
    AccessAction,
    AccessDenialCode,
    AccessDenied,
    Availability,
    OperationAccessPolicy,
    OperationAccessRequest,
)
from cadrumo.application.user_profile.access_errors import ProfileAccessRefusedError
from cadrumo.application.user_profile.operation_access_policy import evaluate_operation_access
from cadrumo.core.capabilities import ServiceCapability
from cadrumo.core.config_support import LLMProvider
from cadrumo.core.errors.hierarchy import CadrumoError
from cadrumo.core.operations import profile_operation_subject
from cadrumo.core.period import Period
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation
from cadrumo.entrypoints.tests.registered_executor_case_support import (
    _CloseWitness,
    _model_runtime_for,
    _runtime,
    _seeded_conformance_submission,
)
from cadrumo.entrypoints.tests.test_operation_subject_binding import _REVIEW_DIGEST, _REVIEWED_DECISIONS
from dev.operation_contract_manifest.tests.test_operation_catalogue import _registry
from dev.runtime_lifecycle.tests.test_operation_mcp_surfaces import (
    _ALLOWED,
    _BINDING,
    _CLIENT,
    _context,
    _grant,
    _key,
    _lease,
    _profile,
    human_lease,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_FRONTENDS = tuple(sorted(OperationFrontendProjection))
_CLI = OperationFrontendProjection.CLI
_AUTOMATION_FRONTENDS = frozenset(
    {OperationFrontendProjection.EXTERNAL_CLIENT, OperationFrontendProjection.INSTALLED_SERVICE}
)
"""The delegated clients' frontends, written out here rather than read from the predicate under test."""


def _registrations() -> tuple[OperationPublicDefinitionRegistrationV1, ...]:
    return _registry().public_registrations


def _definition_ids(*, resolved: bool | None = None) -> tuple[str, ...]:
    """Every registered definition id, or only those with, or without, an access resolver."""
    return tuple(
        sorted(
            item.contract.definition_id
            for item in _registrations()
            if resolved is None or (item.access_resolver is not None) is resolved
        )
    )


# ---------------------------------------------------------------------------
# No definition declares a frontend, and the policy admits each from every one
# ---------------------------------------------------------------------------


def _names_a_frontend(model: type[BaseModel]) -> list[str]:
    """The fields of a model whose declared type names the frontend enumeration."""
    return sorted(
        name for name, field in model.model_fields.items() if OperationFrontendProjection.__name__ in repr(field)
    )


def test_neither_a_definition_nor_its_public_contract_declares_the_frontends_it_is_open_to() -> None:
    """A per-definition list is where one frontend could be left out, so neither model carries one."""
    assert not _names_a_frontend(OperationDefinition)
    assert not _names_a_frontend(OperationPublicDefinitionContractV1)
    # The reading finds the enumeration where a model does carry it.
    assert _names_a_frontend(OperationAccessRequest) == ["frontend"]


def _session_answer(
    request: OperationAccessRequest, policy: OperationAccessPolicy, *, human: bool, registry: OperationRegistry
) -> str:
    """Name what the real access policy answers one session kind for one resolved access.

    The session's ceilings hold every operation and action and exactly the
    disclosures the policy makes, and it names no surface, so a refusal is the
    policy's own.
    """
    disclosures = policy.disclosures
    key_lease = _lease(None, disclosures=disclosures)
    decision = evaluate_operation_access(
        request=request.model_copy(update={"profile_id": _BINDING.profile_id}),
        policy=policy,
        registry=registry,
        session=human_lease(key_lease) if human else key_lease,
        ancestors=(),
        grant=None if human else _grant(disclosures),
        key=None if human else _key(disclosures),
        profile=_profile(disclosures),
        context=_context(),
    )
    return decision.code.value if isinstance(decision, AccessDenied) else _ALLOWED


def _widest_submission(
    definition_id: str, frontend: OperationFrontendProjection
) -> tuple[OperationAccessRequest, OperationAccessPolicy]:
    """A period-independent submission and the widest policy an operation could resolve for it."""
    contract = _registry().lookup_public_contract(definition_id)
    request = OperationAccessRequest(
        profile_id=_BINDING.profile_id,
        definition_id=definition_id,
        action=AccessAction.SUBMIT,
        frontend=frontend,
        periods=frozenset(),
        period_independent=True,
        destination_id=_CLIENT,
    )
    policy = OperationAccessPolicy(
        definition_id=definition_id,
        definition_contract_digest=contract.definition_contract_digest,
        actions=frozenset(AccessAction),
        disclosures=frozenset(),
        periods=None,
        allow_period_independent=True,
        backend=Availability.AVAILABLE,
        published_authority=Availability.AVAILABLE,
        provider=Availability.NOT_REQUIRED,
        transaction_authority_required=False,
    )
    return request, policy


def test_every_registered_definition_is_submittable_from_every_frontend_by_either_kind_of_session() -> None:
    """The access policy admits a submission of each operation from each frontend, with no surface named.

    A person's own act is the one exception, and only on an automation's frontend, where it is refused, typed.
    """
    refused: dict[str, str] = {}
    persons_acts: set[str] = set()
    for definition_id in _definition_ids():
        contract = _registry().lookup_public_contract(definition_id)
        persons = operation_is_persons_act(definition_id, ephemeral_secret_required=contract.ephemeral_secret_required)
        for frontend in _FRONTENDS:
            request, policy = _widest_submission(definition_id, frontend)
            for human in (True, False):
                answer = _session_answer(request, policy, human=human, registry=_registry())
                if persons and frontend in _AUTOMATION_FRONTENDS and answer == _PERSON_ACT_REQUIRED:
                    persons_acts.add(definition_id)
                    continue
                if answer != _ALLOWED:
                    refused[f"{definition_id} on {frontend.value}, {'human' if human else 'key'} session"] = answer
    assert not refused, f"submissions the access policy refuses for a frontend: {refused}"
    # The exception is exercised, so a person's act left open to the automation would show here.
    assert persons_acts


def test_every_persons_act_is_refused_on_each_automation_frontend_and_admitted_on_each_persons_frontend() -> None:
    """The door-by-frontend matrix of the registered person's acts, through the production registry and policy.

    Each frontend is on one side: a new one fails here until it is placed.
    """
    persons = frozenset(
        {OperationFrontendProjection.CLI, OperationFrontendProjection.TUI, OperationFrontendProjection.DESKTOP}
    )
    assert persons | _AUTOMATION_FRONTENDS == frozenset(OperationFrontendProjection)
    assert not persons & _AUTOMATION_FRONTENDS
    matrix: dict[tuple[str, str, bool], str] = {}
    expected: dict[tuple[str, str, bool], str] = {}
    for definition_id in _definition_ids():
        contract = _registry().lookup_public_contract(definition_id)
        if not operation_is_persons_act(definition_id, ephemeral_secret_required=contract.ephemeral_secret_required):
            continue
        for frontend in _FRONTENDS:
            request, policy = _widest_submission(definition_id, frontend)
            for human in (True, False):
                cell = (definition_id, frontend.value, human)
                matrix[cell] = _session_answer(request, policy, human=human, registry=_registry())
                expected[cell] = _PERSON_ACT_REQUIRED if frontend in _AUTOMATION_FRONTENDS else _ALLOWED
    assert matrix
    assert matrix == expected, {cell: answer for cell, answer in matrix.items() if answer != expected[cell]}


# ---------------------------------------------------------------------------
# Requests built from the registered schema alone
# ---------------------------------------------------------------------------

_PROBE_PROFILE = UUID("5aa00000-0000-4000-8000-0000000000aa")
_PROBE_DESTINATION = UUID("5aa00000-0000-4000-8000-0000000000bb")
_PROBE_PERIOD = Period.from_year_and_code(2025, "1T")
_RESOLVED = "resolved"

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
# Requests no schema sample reaches
# ---------------------------------------------------------------------------

_SAMPLE_ACCOUNT = "acc-01"
_SAMPLE_IBAN = "ES9121000418450200051332"
"""A published example account number; no account is read while a resolver is asked."""
_FIELD_BASELINE: Mapping[str, Any] = {"expected_revision": 1, "expected_content_digest": "0" * 64}
_SOLICITUD_FACTS: Mapping[str, Any] = {
    "solicitud": {"nivel_calidad_datos": "2", "pais_destino": "FR", "causa_presentacion": "0"},
    "solicitante": {"email": "solicitante@example.es", "establecimiento": {"ambito": "territorio_comun"}},
    "cuenta": {"titular_nombre": "TITULAR PRUEBA", "titular_en_calidad_de": "A", "divisa": "EUR"},
}

_SAMPLE_WORK_UNIT = "0" * 64
_SAMPLE_CALCULATION: Mapping[str, Any] = {"work_unit_id": _SAMPLE_WORK_UNIT, "actor": "synthetic"}

_M303_FILING_FACTS = "ordinary_m303_filing_evidence"
_EXPLICIT_CALCULATION = "explicit"
_CAPABILITY_QUESTIONS = ("google-export", "llm-vision")

_RECORD_ADDRESSED: Mapping[str, str] = {"modelo.work.calculate": "work_unit_id"}
"""Definitions whose written-out request addresses a stored record, by the member that names it.

Such a request carries no profile id and its subject is the record. Nothing is
stored while this file runs, so the resolver answers every frontend for a
record it cannot find, and that answer is still held to be the same on each."""

_SAMPLE_EVIDENCE = "e" * 16
_M145_DRAFT: Mapping[str, Any] = {"communication_year": 2026, "period_token": "comunicacion", "actor": "synthetic"}
_M145_WORKER = {"casilla_id": "perceptor.nif", "value": "12345678Z"}
_LOCAL_OBSERVATION: Mapping[str, Any] = {
    "modelo": "130",
    "period": {"filing_year": _PROBE_PERIOD.filing_year, "code": _PROBE_PERIOD.registry_token},
    "reason": "synthetic",
}

_STATED_FOR_THE_PERSON: Mapping[str, tuple[Mapping[str, Any], ...]] = {
    "ledger.evidence.extract": tuple(
        {"evidence_id": _SAMPLE_EVIDENCE, "off_host_provider": provider.value, "acknowledge_off_host": True}
        for provider in LLMProvider
        if provider is not LLMProvider.LOCAL
    ),
    "ledger.own_account": (
        {"action": "add", "label": "synthetic", "holding": "titular", "iban": _SAMPLE_IBAN},
        {"action": "update", "own_account_id": _SAMPLE_ACCOUNT, "label": "synthetic"},
        {"action": "close", "own_account_id": _SAMPLE_ACCOUNT, "closed_on": "2026-06-30"},
        {"action": "remove", "own_account_id": _SAMPLE_ACCOUNT},
        {"action": "designate", "own_account_id": _SAMPLE_ACCOUNT, "role": "charge"},
        {"action": "undesignate", "role": "charge"},
    ),
    "ledger.rule.apply": ({"reaffirm": True}, {"reaffirm": True, "dry_run": False}),
    "modelo.m145.create": (
        {**_M145_DRAFT, "field_values": [{"casilla_id": "comunicacion.firma-lugar", "value": "Madrid"}]},
        {**_M145_DRAFT, "field_values": [{"casilla_id": "acuse-recibo.tipo-firma", "value": "1"}, _M145_WORKER]},
    ),
    "modelo.m360_solicitud": (
        {"action": "declare", "filing_year": 2025, "own_account_id": _SAMPLE_ACCOUNT, "facts": _SOLICITUD_FACTS},
        {"action": "remove", "filing_year": 2025},
    ),
    "modelo.observation.local": ({**_LOCAL_OBSERVATION, "action": "clear"},),
    "modelo.work.calculate": (
        {**_SAMPLE_CALCULATION, "caller_context": _EXPLICIT_CALCULATION},
        {
            **_SAMPLE_CALCULATION,
            "caller_context": _EXPLICIT_CALCULATION,
            "inputs": {"casilla_overrides": [{"key": "01", "value": "100.00"}]},
        },
        {**_SAMPLE_CALCULATION, _M303_FILING_FACTS: {"joint_return_elected": False}},
        {
            **_SAMPLE_CALCULATION,
            _M303_FILING_FACTS: {
                "joint_return_elected": True,
                "m303_exonerado_390_attachment_id": "0" * 64,
                "m303_exonerado_390_sha256": "0" * 64,
            },
        },
    ),
    "user-profile.field-mutation": tuple(
        {**_FIELD_BASELINE, "path": capability.schema_path, "value": value}
        for capability in ServiceCapability
        for value in ("true", "")
    ),
    "user-profile.patch": tuple(
        {**_FIELD_BASELINE, "values": [{"question_id": question_id, "value": value}]}
        for question_id in _CAPABILITY_QUESTIONS
        for value in ("false", "")
    ),
}
"""Well-formed requests that state what a schema sample never does.

Each states a consent, a signature, an account, a hand-entered figure or a
choice a request can make on the person's behalf. They are written out because
no generic sample reaches them, and each is admitted through the registry's own decoder."""

_ORDINARY_REQUESTS: Mapping[str, tuple[Mapping[str, Any], ...]] = {
    "ledger.evidence.extract": ({"evidence_id": _SAMPLE_EVIDENCE}, {"attachment_id": "0" * 64}),
    "ledger.own_account": ({"action": "list"}, {"action": "show", "own_account_id": _SAMPLE_ACCOUNT}),
    "ledger.rule.apply": ({}, {"reaffirm": False}, {"dry_run": True}, {"dry_run": True, "reaffirm": True}),
    "modelo.m145.create": ({**_M145_DRAFT, "field_values": [_M145_WORKER]},),
    "modelo.m360_solicitud": ({"action": "list"},),
    "modelo.observation.local": (
        {**_LOCAL_OBSERVATION, "action": "record", "casilla_values": [{"casilla_id": "01", "value": "100.00"}]},
    ),
    "user-profile.field-mutation": ({**_FIELD_BASELINE, "path": "preferences.output_language", "value": "es"},),
    "user-profile.patch": (
        {**_FIELD_BASELINE, "values": [{"question_id": "notes", "value": "synthetic"}]},
        {**_FIELD_BASELINE, "colegio_concertado": True},
    ),
}
"""Requests of the same definitions that state none of those things."""


def _sample_request(definition_id: str, document: Mapping[str, Any]) -> OperationRequest[BaseModel]:
    """Admit one written-out document through the registry's own decoder; a stale sample fails here."""
    record_member = _RECORD_ADDRESSED.get(definition_id)
    if record_member is None:
        subject_ref = profile_operation_subject(str(_PROBE_PROFILE))
        document = {"profile_id": str(_PROBE_PROFILE), **document}
    else:
        subject_ref = str(document[record_member])
    return OperationRequest(
        definition_id=definition_id,
        subject_ref=subject_ref,
        payload=_registry().decode_request_payload(definition_id, json.dumps(document, sort_keys=True)),
    )


def _answers_on(
    registration: OperationPublicDefinitionRegistrationV1,
    request: OperationRequest[BaseModel],
    frontend: OperationFrontendProjection,
    authority: PinnedAuthorityOperation | None = None,
) -> dict[str, str]:
    """What the real resolver answers one frontend, at each position it can be asked from.

    The host always holds a pinned authority. A resolver that reads the setup
    catalogue needs it, so the written-out requests are asked under it.
    """
    return {
        position: _resolution(request, replace(context, authority_operation=authority))
        for position, context in _probe_contexts(registration, frontend)
    }


_PERSON_ACT_REQUIRED = AccessDenialCode.PERSON_ACT_REQUIRED.value
_REFUSED_AS_PERSONS_ACT = f"refused:{_PERSON_ACT_REQUIRED}"


def _is_persons_act(request: OperationRequest[BaseModel]) -> bool:
    """Tell whether a request is the person's own act, as the person-acts module and the consent rule name it."""
    contract = _registry().lookup_public_contract(request.definition_id)
    if operation_is_persons_act(request.definition_id, ephemeral_secret_required=contract.ephemeral_secret_required):
        return True
    # The acknowledgement of an off-host read is the person's consent to send the document off this machine.
    payload = request.payload
    return isinstance(payload, LedgerEvidenceExtractRequest) and payload.off_host_provider is not None


def _refused_as_persons_act(automation: object, person: object) -> bool:
    """Tell whether the automation got the person's answer or the typed person-act refusal, wherever they differ."""
    if automation == person:
        return True
    if isinstance(automation, _Decision) and isinstance(person, _Decision):
        if automation.resolution == _REFUSED_AS_PERSONS_ACT:
            return True
        return (
            (automation.resolution, automation.policy, automation.request)
            == (person.resolution, person.policy, person.request)
            and automation.human_session in {person.human_session, _PERSON_ACT_REQUIRED}
            and automation.key_session in {person.key_session, _PERSON_ACT_REQUIRED}
        )
    if isinstance(automation, Mapping) and isinstance(person, Mapping):
        return automation.keys() == person.keys() and all(
            _refused_as_persons_act(automation[key], person[key]) for key in automation
        )
    return automation == _REFUSED_AS_PERSONS_ACT


def _on_the_persons_frontends[AnswerT](
    by_frontend: Mapping[OperationFrontendProjection, AnswerT], request: OperationRequest[BaseModel]
) -> Mapping[OperationFrontendProjection, AnswerT]:
    """Leave the delegated clients' frontends out of the comparison for a person's
    act, once their answers are shown typed.

    An automation is answered either as the person is, where a later door refuses
    it, or with the person-act refusal; never with anything else.
    """
    if not _is_persons_act(request):
        return by_frontend
    for frontend in _AUTOMATION_FRONTENDS:
        automation = by_frontend[frontend]
        assert _refused_as_persons_act(automation, by_frontend[_CLI]), (
            request.definition_id,
            frontend.value,
            automation,
        )
    return {frontend: answer for frontend, answer in by_frontend.items() if frontend not in _AUTOMATION_FRONTENDS}


def _differing(answers: Mapping[OperationFrontendProjection, object]) -> dict[str, object] | None:
    """The answers by frontend where they are not all the same, else ``None``."""
    values = list(answers.values())
    if all(value == values[0] for value in values[1:]):
        return None
    return {frontend.value: answer for frontend, answer in answers.items()}


def test_every_schema_built_request_is_answered_alike_on_every_frontend() -> None:
    """At a fresh submission and at each replayed scope, a resolver's answer does not depend on the frontend."""
    differing: dict[str, object] = {}
    admitted = 0
    for definition_id in _definition_ids(resolved=True):
        registration = _registry().lookup_public_registration(definition_id)
        for index, request in enumerate(_probe_requests(definition_id)):
            by_frontend = {frontend: _answers_on(registration, request, frontend) for frontend in _FRONTENDS}
            admitted += _RESOLVED in by_frontend[_CLI].values()
            found = _differing(_on_the_persons_frontends(by_frontend, request))
            if found is not None:
                differing[f"{definition_id}, request {index}"] = found
    assert not differing, f"resolvers that answer one frontend differently from another: {differing}"
    # The comparison must rest on real admissions, or refusing every frontend everything would agree.
    assert admitted


def test_every_admission_a_schema_built_request_reports_is_refused_for_another_profile() -> None:
    """The admissions above are decisions: the same resolvers refuse the same requests for a foreign profile."""
    registry = _registry()
    foreign_profile = UUID("5aa00000-0000-4000-8000-0000000000cc")
    admitted = 0
    unrefused: list[tuple[str, str, str]] = []
    for definition_id in _definition_ids(resolved=True):
        registration = registry.lookup_public_registration(definition_id)
        for request in _probe_requests(definition_id)[:1]:
            for frontend in _FRONTENDS:
                for position, context in _probe_contexts(registration, frontend):
                    if _resolution(request, context) != _RESOLVED:
                        continue
                    admitted += 1
                    foreign = _resolution(request, replace(context, profile_id=foreign_profile))
                    if not foreign.startswith("refused:"):
                        unrefused.append((definition_id, frontend.value, position))
    assert admitted
    assert not unrefused, f"resolvers that admit a request addressed to another profile: {unrefused}"


def test_every_written_out_request_is_answered_alike_on_every_frontend(operation: PinnedAuthorityOperation) -> None:
    """What a request states for the person changes nothing about which frontend may submit it."""
    differing: dict[str, object] = {}
    unadmitted: dict[str, str] = {}
    asked = 0
    for table in (_STATED_FOR_THE_PERSON, _ORDINARY_REQUESTS):
        for definition_id, documents in table.items():
            registration = _registry().lookup_public_registration(definition_id)
            for document in documents:
                request = _sample_request(definition_id, document)
                asked += 1
                label = f"{definition_id} {json.dumps(document, sort_keys=True)}"
                by_frontend = {
                    frontend: _answers_on(registration, request, frontend, operation) for frontend in _FRONTENDS
                }
                found = _differing(_on_the_persons_frontends(by_frontend, request))
                if found is not None:
                    differing[label] = found
                submitted = by_frontend[_CLI]["submit"]
                if definition_id not in _RECORD_ADDRESSED and submitted != _RESOLVED:
                    unadmitted[label] = submitted
    assert asked
    assert not differing, f"written-out requests one frontend is answered differently for: {differing}"
    assert not unadmitted, f"written-out requests whose submission no longer resolves: {unadmitted}"


# ---------------------------------------------------------------------------
# The request each operation really runs, through its resolver and the access policy
# ---------------------------------------------------------------------------

_JUDGED_ACTIONS = (AccessAction.SUBMIT, AccessAction.START, AccessAction.COMMIT, AccessAction.RESULT)
"""The accesses asked of every operation: its submission, its start, its commit door and its result."""

_WITHOUT_A_RESOLVER = "refused:operation_unavailable"


@dataclass(frozen=True, slots=True)
class _Decision:
    """What one frontend is answered for one access.

    A resolved access carries its policy, its request with the frontend set
    aside, and what the access policy then answers each kind of session.
    """

    resolution: str
    policy: OperationAccessPolicy | None = None
    request: OperationAccessRequest | None = None
    human_session: str | None = None
    key_session: str | None = None


def _decision(
    registry: OperationRegistry, request: OperationRequest[BaseModel], context: OperationAccessContext
) -> _Decision:
    """Ask the registered resolver, then the real access policy for each kind of session."""
    try:
        resolved = resolve_operation_access(registry=registry, request=request, context=context)
    except ProfileAccessRefusedError as refused:
        return _Decision(resolution=f"refused:{refused.reason.value}")
    except (CadrumoError, ValueError, LookupError) as error:
        return _Decision(resolution=f"undecided:{type(error).__name__}")
    assert resolved.request.frontend is context.frontend
    return _Decision(
        resolution=_RESOLVED,
        policy=resolved.policy,
        request=resolved.request.model_copy(update={"frontend": _CLI}),
        human_session=_session_answer(resolved.request, resolved.policy, human=True, registry=registry),
        key_session=_session_answer(resolved.request, resolved.policy, human=False, registry=registry),
    )


def _held_context(
    registry: OperationRegistry,
    definition_id: str,
    *,
    profile_id: UUID,
    frontend: OperationFrontendProjection,
    action: AccessAction,
    operation: PinnedAuthorityOperation,
) -> OperationAccessContext:
    """A fresh access under the host's held authority, as a connected client of this frontend asks it."""
    return OperationAccessContext(
        profile_id=profile_id,
        destination_id=_CLIENT,
        action=action,
        frontend=frontend,
        contract=registry.lookup_public_contract(definition_id),
        published_authority=Availability.AVAILABLE,
        authority_operation=operation,
    )


type _Answers = dict[AccessAction, Mapping[OperationFrontendProjection, _Decision]]


def _answers_at_every_judged_access(
    registry: OperationRegistry,
    request: OperationRequest[BaseModel],
    *,
    profile_id: UUID,
    operation: PinnedAuthorityOperation,
) -> _Answers:
    """What each frontend is answered for one request, at each judged access, the
    automation's apart for a person's act."""
    return {
        action: _on_the_persons_frontends(
            {
                frontend: _decision(
                    registry,
                    request,
                    _held_context(
                        registry,
                        request.definition_id,
                        profile_id=profile_id,
                        frontend=frontend,
                        action=action,
                        operation=operation,
                    ),
                )
                for frontend in _FRONTENDS
            },
            request,
        )
        for action in _JUDGED_ACTIONS
    }


def _unlike(answers: _Answers) -> dict[str, object]:
    """The accesses at which the frontends are not answered alike."""
    return {
        action.value: found for action, by_frontend in answers.items() if (found := _differing(by_frontend)) is not None
    }


def _submission_resolves_somewhere(answers: _Answers) -> bool:
    return any(decision.resolution == _RESOLVED for decision in answers[AccessAction.SUBMIT].values())


@pytest.mark.parametrize("definition_id", sorted(set(_definition_ids()) - _REVIEWED_DECISIONS))
def test_the_real_resolver_and_policy_answer_every_frontend_alike_for_a_request_the_operation_admits(
    tmp_path: Path, definition_id: str, *, operation: PinnedAuthorityOperation
) -> None:
    """Admitted with the same policy or refused with the same code, for a human session and for a key session."""
    probed = [
        _answers_at_every_judged_access(_registry(), request, profile_id=_PROBE_PROFILE, operation=operation)
        for request in _probe_requests(definition_id)
    ]
    for index, answers in enumerate(probed):
        assert not _unlike(answers), (
            f"{definition_id}, schema-built request {index}, answers one frontend differently: {_unlike(answers)}"
        )
    if any(_submission_resolves_somewhere(answers) for answers in probed):
        return

    # No schema-built request is admitted, so the comparison above rests on refusals alone. The
    # request the operation's own scenario seeds into a real profile is one its resolver admits.
    with (
        _model_runtime_for(definition_id),
        _runtime(tmp_path / definition_id, cleanup=_CloseWitness()) as (_driver, registry, profile_id),
    ):
        submission = _seeded_conformance_submission(
            registry.lookup(definition_id), profile_id=profile_id, tmp_path=tmp_path, operation=operation
        )
        request = OperationRequest[BaseModel](
            definition_id=definition_id, subject_ref=submission.subject_ref, payload=submission.registered_payload
        )
        answers = _answers_at_every_judged_access(registry, request, profile_id=profile_id, operation=operation)

    submitted = answers[AccessAction.SUBMIT][_CLI]
    if definition_id in _definition_ids(resolved=False):
        # No resolver is registered, so the shared access path answers every frontend with this refusal.
        assert submitted.resolution == _WITHOUT_A_RESOLVER, submitted
    else:
        assert submitted.resolution == _RESOLVED, (
            f"{definition_id} does not resolve the submission its own scenario seeds: {submitted.resolution}"
        )
    assert not _unlike(answers), f"{definition_id} answers one frontend differently from another: {_unlike(answers)}"


@pytest.mark.parametrize("definition_id", sorted(_REVIEWED_DECISIONS))
def test_a_reviewed_decision_is_answered_alike_on_every_frontend(
    definition_id: str, *, operation: PinnedAuthorityOperation
) -> None:
    """Its resolver needs a request that names a review, which the shared scenario cannot; this one does."""
    registry = _registry()
    definition = registry.lookup(definition_id)
    payload = definition.request_type.model_validate(
        {"profile_id": _PROBE_PROFILE, "request_id": UUID(int=1), "review_digest": _REVIEW_DIGEST}, strict=True
    )
    subject_ref = expected_operation_subject(definition.subject_reference, profile_id=_PROBE_PROFILE, payload=payload)
    assert subject_ref is not None
    request = OperationRequest[BaseModel](definition_id=definition_id, subject_ref=subject_ref, payload=payload)

    answers = _answers_at_every_judged_access(registry, request, profile_id=_PROBE_PROFILE, operation=operation)
    assert answers[AccessAction.SUBMIT][_CLI].resolution == _RESOLVED, answers[AccessAction.SUBMIT][_CLI]
    assert not _unlike(answers), _unlike(answers)


def test_the_definitions_judged_apart_are_registered_and_have_a_resolver() -> None:
    """The named set holds only live, resolvable definitions, so no operation leaves the comparison unnoticed."""
    assert set(_definition_ids(resolved=True)) >= _REVIEWED_DECISIONS

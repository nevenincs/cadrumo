"""A declaration prepared through MCP alone is the declaration the command line prepares.

Two fresh profiles are given the same synthetic inputs. One is worked only
through the MCP tools an agent has: ``search`` and ``describe`` to find and read
each operation, ``execute``, ``observe`` and ``result`` to run it. The other is
worked through the real commands. Each goes from an empty profile to an exported
file: profile facts, ledger rows, their classification, the work unit, the
calculation, the verification and the export.

The runtime, the session authority, the profile worker, the encrypted profile,
the MCP adapter and its SDK transport, and the command tree are the real ones.
The native login the runtime observes, the keychain and the runtime's clock are
ports the fixture holds. Export writes a local file; nothing reaches the tax
agency, and nothing here records a declaration as presented.

What each side is told about its own work is read from its own replies, the
operation results on one side and the command envelopes on the other, and
compared after the two are brought to one shape. Identifiers a profile mints for
itself are named by their role first, and the agent's replies are passed through
the redaction the command line applies to everything it prints. What each side
recorded is compared too: every event of the profile's history with its payload,
and the origin each ledger row's classification is stored with. The notices the
command line prints are compared with the facts the operation results carry
wherever both sides state them.

There are two intended differences, and both follow from who acted. The actor
recorded on each event is the agent's session on one side and the label the
command line was given on the other. The origin of each classified row is
``agent`` on one side and ``person`` on the other. Nothing else is normalised
away.
"""

from __future__ import annotations

import asyncio
import json
import re
import sys
import time
from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path
from typing import Any, Final
from uuid import UUID

import pytest
from click.testing import Result

from cadrumo_harness.mcp.runtime_adapter import RuntimeMcpAdapter
from cadrumo_harness.mcp.server import build_server
from cadrumo_harness.mcp.tests.session import connected_server_and_client_session
from cadrumo_harness.resources import iter_reference_documents

from ...adapters.persistence.storage.custody.tests.enrollment_support import PROFILE_INPUT
from ...adapters.persistence.storage.master_key.active_session import close_active_bucket_session
from ...application.operations.execution_actor import actor_label_is_an_agents
from ...application.runtime.contracts import RuntimeShutdownIncompleteError
from ...application.user_profile.login_session import (
    authenticate_profile_for_invocation,
    resolve_login_target,
)
from ...core.config import override_settings
from ...core.i18n.render import tr
from ...core.redaction.rules import redact_structured_for_cli_output
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...tests.cli_envelope import require_error_document, require_schema_envelope, unwrap_envelope_notices
from ..cli.tests.cli_runner import invoke_cached_cli
from ..cli.tests.command_operation_reference import read_command_operation_reference
from ..ledger_action_composition import compose_ledger_action_ports
from ..runtime.tests.stored_sign_in_runtime import StoredSignInRuntime, stored_sign_in_runtime

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires native Windows worker and protected pipes"),
    pytest.mark.usefixtures("authority_operation"),
]

_PERSON = "Synthetic Person"
"""The label the command line is given for who acts; an agent's session records its own instead."""

_MCP_TOOLS = frozenset({"status", "search", "describe", "execute", "observe", "result"})
"""Every tool the agent uses to prepare a declaration."""

_SETTLE_SECONDS = 600.0
"""How long the agent waits for one operation to settle; the command line waits longer for a calculation."""

_COLD_START_SECONDS = 300.0
"""How long either side keeps asking its first read of a runtime that is still starting.

A profile's worker starts with the first session, and on a busy machine that start can outlast one call's own
deadline. A read changes nothing, so it is safe to ask again. No write is ever repeated.
"""

_CLASSIFY_OPTIONS: Mapping[str, str] = {
    "business_classification": "--classification",
    "taxable_base": "--taxable-base",
    "irpf_category": "--irpf-category",
}
"""Each classification fact as the operation's field, and the command option that carries the same fact."""

_IDENTIFIER = re.compile(r"[0-9a-f]{64}|[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")
"""The shape of every identifier a profile mints for itself: a content digest or a UUID."""

_INVOCATION_NOTICES = frozenset({"config.login.session_not_persisted"})
"""Notices every command prints about being given the profile password for its own process alone."""

_MINTED_PAYLOAD_NAMES = frozenset({"dek_epoch"})
"""Event payload members whose value the profile draws at random when it is created, and which name no content."""

_EXCHANGE_FACTS = frozenset({"operation_id", "effect", "terminal_condition"})
"""What a command adds to a refusal about its own exchange with the runtime, beside the refusal's own detail."""

_ROW_FACTS = (
    "booked_date",
    "amount",
    "currency",
    "direction",
    "counterparty",
    "description",
    "business_classification",
    "business_pct",
    "category_id",
    "taxable_base",
    "iva_rate",
    "iva_amount",
    "irpf_category",
    "lifecycle_state",
    "classified_by",
)
_UNIT_FACTS = ("modelo", "filing_year", "period", "revision_id", "name", "state")


@dataclass(frozen=True, slots=True)
class _Row:
    """One ledger entry and how the taxpayer classifies it."""

    booked_date: str
    amount: str
    direction: str
    description: str
    counterparty: str
    classification: Mapping[str, str]


@dataclass(frozen=True, slots=True)
class _Declaration:
    """Everything either side is given to prepare one declaration."""

    profile: Mapping[str, str]
    rows: Sequence[_Row]
    modelo: str
    year: int
    period: str
    casillas: Mapping[str, str]
    bindings: Mapping[str, str]
    export_name: str
    binding_first_left_out: str | None = None
    """A binding the first calculation is not given, so its verification is refused until it is supplied."""

    def first_bindings(self) -> Mapping[str, str]:
        return {key: value for key, value in self.bindings.items() if key != self.binding_first_left_out}


_QUARTERLY = _Declaration(
    # A consultant in the first quarter of a first year of activity, so no earlier period feeds the quarter.
    profile={
        "entity-type": "natural_person",
        "tax-id": "12345678Z",
        "name": "Daniel",
        "surnames": "Persona",
        "activity": "consultoria",
        "activity-start-date": "2025-01-01",
        "irpf-income-categories": "actividad_economica",
        "irpf-estimation-regime": "directa_simplificada",
        "iva-regime": "GENERAL",
        "tax-residence-jurisdiction-scope": "common_regime",
        "iva-m303-regime-composition": "general",
        "iva-redeme-enrolled": "false",
        "iva-cash-accounting-regime-enrolled": "false",
        "iva-voluntary-sii-enrolled": "false",
        "iva-hydrocarbon-deposit-advance-payment-deduction-entitled": "false",
        "fiscal-residency": "resident_irpf",
        "tax-residence-ccaa": "madrid",
    },
    rows=(
        _Row(
            "2025-02-15",
            "4000.00",
            "INCOMING",
            "Factura consultoria febrero",
            "Cliente SA",
            {"business_classification": "BUSINESS", "taxable_base": "4000", "irpf_category": "actividad_economica"},
        ),
        _Row(
            "2025-03-12",
            "1250.50",
            "INCOMING",
            "Factura consultoria marzo",
            "Cliente SL",
            {"business_classification": "BUSINESS", "taxable_base": "1250.5", "irpf_category": "actividad_economica"},
        ),
        # A private purchase paid from the same account: classified, and so kept out of the activity.
        _Row(
            "2025-03-20",
            "86.40",
            "OUTGOING",
            "Compra supermercado",
            "Mercado SA",
            {"business_classification": "PERSONAL"},
        ),
    ),
    modelo="130",
    year=2025,
    period="1T",
    casillas={},
    bindings={
        "irpf.previous_year_economic_activity_net_income": "0",
        "modelo-130-resultados-negativos-anteriores": "0",
        "modelo-130-pagos-fraccionados-anteriores": "0",
    },
    export_name="modelo-130-2025-1T.txt",
    # Without it the box for earlier instalments cannot be worked out, and nothing may print a silent zero there.
    binding_first_left_out="modelo-130-pagos-fraccionados-anteriores",
)

_ANNUAL = _Declaration(
    # A salaried taxpayer, whose annual return depends on no quarterly declaration.
    profile={
        "entity-type": "natural_person",
        "tax-id": "12345678Z",
        "name": "ANA",
        "surnames": "PEREZ GIL",
        "irpf-income-categories": "trabajo",
        "tax-residence-jurisdiction-scope": "common_regime",
        "tax-residence-ccaa": "madrid",
        "activity": "salaried employment",
        "iva-regime": "GENERAL",
        "iva-m303-regime-composition": "general",
        "iva-redeme-enrolled": "false",
        "iva-cash-accounting-regime-enrolled": "false",
        "iva-voluntary-sii-enrolled": "false",
        "iva-hydrocarbon-deposit-advance-payment-deduction-entitled": "false",
        "taxpayer-birth-date": "1985-06-15",
        "taxpayer-sex": "M",
        "taxpayer-marital-status": "4",
        "taxation-type": "1",
    },
    rows=(
        _Row(
            "2025-03-28",
            "1800.00",
            "INCOMING",
            "Nomina marzo",
            "Empleadora SL",
            {"business_classification": "PERSONAL"},
        ),
        _Row(
            "2025-04-03",
            "640.00",
            "OUTGOING",
            "Alquiler vivienda",
            "Arrendador",
            {"business_classification": "PERSONAL"},
        ),
    ),
    modelo="100",
    year=2025,
    period="0A",
    casillas={"0003": "24000"},
    bindings={
        "renta-certificado-trabajo-retenciones": "2400",
        "renta-base-liquidable-negativa-general-anterior": "0",
    },
    export_name="modelo-100-2025-0A.xml",
)


def _event_payload(event: Mapping[str, Any]) -> dict[str, str]:
    """Read an event's payload: the command prints it as an object, the operation result as named details."""
    if "payload" in event:
        return dict(event["payload"])
    return {detail["name"]: detail["value"] for detail in event["details"]}


@dataclass(slots=True)
class _Prepared:
    """What one side was told about the declaration it prepared, in one shape for both sides."""

    ledger: list[dict[str, Any]] = field(default_factory=list)
    work_unit: dict[str, Any] = field(default_factory=dict)
    refused_verification: dict[str, Any] = field(default_factory=dict)
    casilla_values: dict[str, Any] = field(default_factory=dict)
    provenance: dict[str, dict[str, Any]] = field(default_factory=dict)
    inputs: dict[str, Any] = field(default_factory=dict)
    registry_snapshot: dict[str, Any] = field(default_factory=dict)
    verification: dict[str, Any] = field(default_factory=dict)
    export: dict[str, Any] = field(default_factory=dict)
    exported: bytes = b""
    events: list[dict[str, Any]] = field(default_factory=list)
    actors: list[str] = field(default_factory=list)
    origins: dict[str, str] = field(default_factory=dict)
    """Whose decision each ledger row's classification is, as the profile stored it, by the row's description."""
    notices: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    """What this side states, as notices, about the work of each step."""
    aliases: dict[str, str] = field(default_factory=dict)
    calls: list[str] = field(default_factory=list)

    def named_by_role(self, value: Any) -> Any:
        """Return ``value`` with every identifier this profile minted replaced by the role it plays."""
        if isinstance(value, str):
            for identifier in sorted(self.aliases, key=len, reverse=True):
                value = value.replace(identifier, self.aliases[identifier])
            return value
        if isinstance(value, Mapping):
            return {key: self.named_by_role(item) for key, item in value.items()}
        if isinstance(value, (list, tuple)):
            return [self.named_by_role(item) for item in value]
        return value

    def recorded(self, history: Sequence[Mapping[str, Any]]) -> None:
        """Keep what the profile's history says was recorded, and under whose name.

        Events recorded in the same instant are listed in the order of identifiers the profile minted, so they
        are put in the order of their kinds, which is the same for both profiles. An identifier an event names
        that nothing named before is given the role of the first event that names it, in that order.
        """
        ordered = sorted(history, key=lambda event: (event["occurred_at"], event["event_type"], event["object_type"]))
        self.actors = [event["actor"] for event in ordered]
        for event in ordered:
            payload = _event_payload(event)
            for name in _MINTED_PAYLOAD_NAMES & payload.keys():
                self.aliases.setdefault(payload[name], f"<{name}>")
            for identifier in _IDENTIFIER.findall(json.dumps([event["object_id"], payload])):
                self.aliases.setdefault(identifier, f"<{event['object_type']}:{len(self.aliases)}>")
        self.events = [
            {
                "event_type": event["event_type"],
                "object_type": event["object_type"],
                "object_id": event["object_id"],
                "payload_version": event["payload_version"],
                "payload": _event_payload(event),
            }
            for event in ordered
        ]

    def told(self) -> dict[str, Any]:
        """Everything this side was told that the other side must be told too, with identifiers named by role."""
        return self.named_by_role(
            {
                "ledger": self.ledger,
                "work_unit": self.work_unit,
                "refused_verification": self.refused_verification,
                "casilla_values": self.casilla_values,
                "provenance": self.provenance,
                "inputs": self.inputs,
                "registry_snapshot": self.registry_snapshot,
                "verification": self.verification,
                "export": self.export,
                "events": self.events,
            }
        )


@contextmanager
def _fresh_profile(root: Path, monkeypatch: pytest.MonkeyPatch, *, signed_in: bool) -> Iterator[StoredSignInRuntime]:
    """Serve one new, empty profile from its own runtime and storage, selected as the installation's profile."""
    root.mkdir()
    failure: BaseException | None = None
    try:
        with (
            stored_sign_in_runtime(root, monkeypatch, signed_in=signed_in) as runtime,
            override_settings(cadrumo_active_profile=str(runtime.profile_id)),
        ):
            try:
                yield runtime
            except BaseException as error:
                failure = error
                raise
    except RuntimeShutdownIncompleteError:
        # A runtime stopped while an operation is still running cannot drain, and says so without the
        # failure that left the operation running. That failure is the one to read.
        if failure is None:
            raise
        raise failure from None


def _stored_origins(root: Path, profile_id: UUID, operation: PinnedAuthorityOperation) -> dict[str, str]:
    """Read, from the stopped profile's own store, whose decision each ledger row's classification is.

    No frontend shows it: it is the one recorded fact that tells an agent's classification from a person's.
    """
    close_active_bucket_session()
    with override_settings(cadrumo_local_storage_root=root):
        authenticate_profile_for_invocation(
            name=str(profile_id),
            passphrase_callback=lambda: PROFILE_INPUT,
            profile_decode_context=operation.profile_decode_context(),
        )
        try:
            rows = compose_ledger_action_ports(
                bucket_id=str(profile_id), operation=operation
            ).transaction_repository.load()
            return {
                row.raw.description: row.classification_origin.value
                for row in rows.transactions.values()
                if row.classification_origin is not None
            }
        finally:
            close_active_bucket_session()


# --- What both sides report, brought to one shape ---------------------------------------------------------------


def _row_facts(transaction: Mapping[str, Any], review_status: object) -> dict[str, Any]:
    return {name: transaction[name] for name in _ROW_FACTS} | {"review_status": review_status}


def _scalar(value: object) -> object:
    """Read one calculated value: an operation carries a decimal as a tagged text, a command as the text."""
    if isinstance(value, Mapping) and set(value) == {"decimal"}:
        return value["decimal"]
    return value


def _keyed(entries: object) -> dict[str, Any]:
    """Read a mapping an operation carries as key and value pairs, or a command carries as an object."""
    if isinstance(entries, Mapping):
        return {str(key): _scalar(value) for key, value in entries.items()}
    assert isinstance(entries, list), entries
    return {str(entry["key"]): _scalar(entry["value"]) for entry in entries}


def _observation(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "value": _scalar(row["value"]),
        "formula_id": row["formula_id"],
        "op": row["op"],
        "operand_refs": list(row["operand_refs"]),
        "operand_casilla_refs": list(row["operand_casilla_refs"]),
        "operand_values": [_scalar(value) for value in row["operand_values"]],
        "legal_refs": list(row["legal_refs"]),
        "source_refs": list(row["source_refs"]),
        "absent_by_design": row["absent_by_design"],
    }


def _calculation(prepared: _Prepared, calculation: Mapping[str, Any]) -> None:
    prepared.casilla_values = _keyed(calculation["casilla_values"])
    prepared.provenance = {str(row["casilla_id"]): _observation(row) for row in calculation["observations"]}
    prepared.inputs = _keyed(calculation["input_values_by_casilla_id"])
    prepared.registry_snapshot = dict(calculation["registry_snapshot_ref"])


def _finding(finding: Mapping[str, Any], message: str) -> dict[str, Any]:
    return {
        "kind": finding["kind"],
        "severity": finding["severity"],
        "casilla_id": finding["casilla_id"],
        "legal_refs": list(finding["legal_refs"]),
        "source_refs": list(finding["source_refs"]),
        "message": message,
    }


def _verification(report: Mapping[str, Any], findings: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "granted": report["granted_verificado_completo"],
        "completeness_status": report["completeness_status"],
        "missing_required_casilla_ids": list(report["missing_required_casilla_ids"]),
        "registry_snapshot": dict(report["registry_snapshot_ref"]),
        "findings": findings,
    }


_EVIDENCE_NOTICE: Final = "modelo.export.local_export_not_official_evidence"


def _export_notices(written: Mapping[str, Any]) -> list[dict[str, Any]]:
    """State, from an export's result, the notices the command line prints about the same export."""
    notices: list[dict[str, Any]] = [{"code": _EVIDENCE_NOTICE, "evidence_status": written["evidence_status"]}]
    if written["software_identity_grade"] == "development_mock":
        notices.append({"code": "modelo.export.development_software_identity"})
    if written["completeness"] == "unverified":
        notices.append({"code": "modelo.export.completeness_unverified"})
    return notices


# --- The MCP side -----------------------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class _Settled:
    """One operation's terminal state as ``observe`` and ``result`` report it."""

    condition: str
    code: str | None
    projection: Mapping[str, Any] | None
    error_detail: Mapping[str, Any] | None

    def succeeded(self) -> Mapping[str, Any]:
        assert self.condition == "succeeded" and self.projection is not None, self
        return self.projection


def _started(submitted: Mapping[str, Any]) -> bool:
    """Whether an ``execute`` reply says the operation was submitted and its start acknowledged."""
    start = submitted.get("start", {})
    return bool(submitted["outcome"] == "submitted" and start.get("kind") == "operation_acknowledged")


class _Agent:
    """An agent that holds the MCP tools and nothing else."""

    def __init__(self, sdk: Any, prepared: _Prepared) -> None:
        self._sdk = sdk
        self._prepared = prepared
        self._contracts: dict[str, Mapping[str, Any]] = {}
        (reference,) = (item for item in iter_reference_documents() if item.name == "command-operations.md")
        self._operations_of, _unsubmitted = read_command_operation_reference(reference.read_text(encoding="utf-8"))

    async def _call(self, tool: str, arguments: dict[str, Any]) -> dict[str, Any]:
        self._prepared.calls.append(tool)
        reply = await self._sdk.call_tool(tool, arguments)
        content = reply.structured_content
        assert isinstance(content, dict), (tool, reply)
        return content

    async def session_actor_label(self, runtime: StoredSignInRuntime) -> str:
        """Open the session and return the label the runtime's lease gives an agent's acts under it."""
        deadline = time.monotonic() + _COLD_START_SECONDS
        status = await self._call("status", {})
        while status["session"] != "sign_in" and time.monotonic() < deadline:
            await asyncio.sleep(2)
            status = await self._call("status", {})
        assert status["outcome"] == "status" and status["session"] == "sign_in", status
        (lease,) = (item for item in runtime.leases() if str(item.session_id) == status["status"]["session_id"])
        return f"agent:mcp.{lease.kind.value}.{lease.client_id}"

    async def _contract(self, command: str, definition_id: str) -> Mapping[str, Any]:
        """Go from a command a skill names to one operation's contract: the reference, then search, then describe."""
        assert definition_id in self._operations_of[command], (command, self._operations_of[command])
        if definition_id not in self._contracts:
            family = definition_id.split(".")[0]
            found = await self._call("search", {"query": command, "family": family, "limit": 200})
            assert found["outcome"] == "found", found
            assert definition_id in [operation["definition_id"] for operation in found["operations"]], (command, found)
            described = await self._call("describe", {"definition_id": definition_id})
            assert described["outcome"] == "described", described
            self._contracts[definition_id] = described["description"]
        return self._contracts[definition_id]

    async def run(
        self, command: str, definition_id: str, payload: dict[str, Any], *, work_unit_id: str | None = None
    ) -> _Settled:
        """Run one operation of ``command`` to its end and read what it settled as."""
        description = await self._contract(command, definition_id)
        schema = description["request_json_schema"]
        assert set(schema.get("required", ())) <= set(payload) <= set(schema["properties"]), (definition_id, payload)
        arguments: dict[str, Any] = {"definition_id": definition_id, "payload": payload}
        if description["contract"]["subject_reference"]["kind"] == "stored_work_unit":
            # The one subject the payload cannot yield: the work unit that owns the stored record.
            assert work_unit_id is not None, definition_id
            arguments["subject_ref"] = work_unit_id
        submitted = await self._call("execute", arguments)
        if "updated" not in description["contract"]["permitted_effects"]:
            # A read the runtime did not take in time is submitted again; an operation that can write never is.
            deadline = time.monotonic() + _COLD_START_SECONDS
            while not _started(submitted) and time.monotonic() < deadline:
                await asyncio.sleep(2)
                submitted = await self._call("execute", arguments)
        assert _started(submitted), (definition_id, submitted)
        operation_id = submitted["receipt"]["operation_id"]
        projection = await self._settled_observation(definition_id, operation_id)
        released = await self._call("result", {"result": {"operation_id": operation_id}})
        assert released["outcome"] == "reply", (definition_id, released)
        document = released["document"]
        return _Settled(
            condition=projection["terminal_condition"],
            code=projection["refusal_ref"] or projection["failure_error_code"],
            projection=document["projection"] if document["outcome"] == "success" else None,
            error_detail=released.get("error_detail"),
        )

    async def _settled_observation(self, definition_id: str, operation_id: str) -> Mapping[str, Any]:
        observation = {"operation_id": operation_id, "after_cursor": 0, "page_limit": 32}
        deadline = time.monotonic() + _SETTLE_SECONDS
        while True:
            # Observing is a read, so an observation the runtime could not answer in time is asked again.
            observed = await self._call("observe", {"observation": observation})
            if observed["outcome"] == "reply":
                projection = observed["reply"]["observation"]["projection"]
                if projection["lifecycle"] == "terminal":
                    return projection
            assert time.monotonic() < deadline, (definition_id, observed)
            await asyncio.sleep(0.2)

    async def write_profile(self, profile_id: str, command: str, definition_id: str, **change: Any) -> None:
        """Read the profile revision to write against, then write one change to exactly that revision."""
        viewed = await self.run(command, "user-profile.view", {"profile_id": profile_id, "page_kind": "status"})
        baseline = viewed.succeeded()
        written = await self.run(
            command,
            definition_id,
            {
                "profile_id": profile_id,
                "expected_revision": baseline["record_revision"],
                "expected_content_digest": baseline["content_digest"],
                **change,
            },
        )
        written.succeeded()

    async def calculate(
        self, work_unit_id: str, casillas: Mapping[str, str], bindings: Mapping[str, str]
    ) -> Mapping[str, Any]:
        calculated = await self.run(
            "aeat app modelo work calculate",
            "modelo.work.calculate",
            {
                "work_unit_id": work_unit_id,
                "actor": _PERSON,
                "caller_context": "explicit",
                "inputs": {
                    "casilla_overrides": [{"key": key, "value": value} for key, value in casillas.items()],
                    "binding_overrides": [{"key": key, "value": value} for key, value in bindings.items()],
                },
            },
        )
        return calculated.succeeded()["calculation"]

    async def verify(self, profile_id: str, work_unit_id: str) -> _Settled:
        """Select the calculation the work unit offers for verification, then verify it."""
        selected = await self.run(
            "aeat app modelo work verify",
            "modelo.work.revision",
            {"profile_id": profile_id, "work_unit_id": work_unit_id, "default_for": "verify"},
        )
        return await self.run(
            "aeat app modelo work verify",
            "modelo.work.verify",
            {"calculation_revision_id": selected.succeeded()["calculation_revision_id"], "actor": _PERSON},
            work_unit_id=work_unit_id,
        )

    async def export(self, profile_id: str, work_unit_id: str, output: Path) -> Mapping[str, Any]:
        """Select the calculation the work unit offers for export, then write it to a local file."""
        selected = await self.run(
            "aeat app modelo export",
            "modelo.work.revision",
            {"profile_id": profile_id, "work_unit_id": work_unit_id, "default_for": "export"},
        )
        exported = await self.run(
            "aeat app modelo export",
            "modelo.export",
            {
                "calculation_revision_id": selected.succeeded()["calculation_revision_id"],
                "output_path": str(output),
                "actor": _PERSON,
            },
            work_unit_id=work_unit_id,
        )
        return exported.succeeded()


async def _prepare_through_mcp(
    runtime: StoredSignInRuntime, declaration: _Declaration, output: Path
) -> tuple[_Prepared, str]:
    """Prepare ``declaration`` with the MCP tools only, reading every identifier from an earlier reply.

    Returns what the agent was told, and the label its session records for what it does.
    """
    prepared = _Prepared()
    profile_id = str(runtime.profile_id)
    prepared.aliases[profile_id] = "<profile>"
    adapter = RuntimeMcpAdapter(profile_id=None, client=None, resumes_sign_in=True)
    try:
        async with connected_server_and_client_session(build_server(adapter)) as sdk:
            agent = _Agent(sdk, prepared)
            agent_label = await agent.session_actor_label(runtime)

            answers = [{"question_id": key, "value": value} for key, value in declaration.profile.items()]
            await agent.write_profile(profile_id, "aeat config profile edit", "user-profile.patch", values=answers)
            await agent.write_profile(profile_id, "aeat config profile complete-setup", "user-profile.complete-setup")

            for index, row in enumerate(declaration.rows, start=1):
                added = await agent.run(
                    "aeat app ledger add",
                    "ledger.add",
                    {
                        "profile_id": profile_id,
                        "booked_date": row.booked_date,
                        "amount": row.amount,
                        "direction": row.direction,
                        "description": row.description,
                        "counterparty": row.counterparty,
                        "actor": _PERSON,
                    },
                )
                transaction_id = added.succeeded()["transaction"]["transaction_id"]
                prepared.aliases[transaction_id] = f"<row:{index}>"
                classified = await agent.run(
                    "aeat app ledger classify",
                    "ledger.classify.single",
                    {
                        "profile_id": profile_id,
                        "transaction_id": transaction_id,
                        "patch": dict(row.classification),
                        "patch_fields": sorted(row.classification),
                        "actor": _PERSON,
                    },
                )
                result = classified.succeeded()
                prepared.ledger.append(_row_facts(result["transaction"], result["review_status"]))

            created = await agent.run(
                "aeat app modelo work create",
                "modelo.work.create",
                {
                    "profile_id": profile_id,
                    "modelo": declaration.modelo,
                    "period": {"filing_year": declaration.year, "code": declaration.period},
                    "actor": _PERSON,
                },
            )
            unit = created.succeeded()["outcome"]["unit"]
            prepared.notices["app modelo work create"] = [
                {"code": "modelo.work.create.filing_obligation", "message": tr(key, locale="en")}
                for key in created.succeeded()["outcome"]["advisory_keys"]
            ]
            work_unit_id = unit["work_unit_id"]
            prepared.aliases[work_unit_id] = "<work-unit>"
            prepared.work_unit = {name: unit[name] for name in _UNIT_FACTS}

            if declaration.binding_first_left_out is not None:
                first = await agent.calculate(work_unit_id, declaration.casillas, declaration.first_bindings())
                prepared.aliases[first["calculation_revision_id"]] = "<first-calculation>"
                refused = await agent.verify(profile_id, work_unit_id)
                assert refused.condition == "refused" and refused.error_detail is not None, refused
                detail = refused.error_detail
                facts = {entry["key"]: entry["value"] for entry in detail["context"]}
                assert detail["error_code"] == refused.code
                prepared.refused_verification = {
                    "code": refused.code,
                    "message": tr(detail["message_key"], locale="en", **facts),
                    "facts": facts,
                }

            calculation = await agent.calculate(work_unit_id, declaration.casillas, declaration.bindings)
            prepared.aliases[calculation["calculation_revision_id"]] = "<calculation>"
            _calculation(prepared, calculation)

            verified = await agent.verify(profile_id, work_unit_id)
            report = verified.succeeded()["verification"]["report"]
            prepared.verification = _verification(
                report,
                [
                    _finding(
                        finding, tr(finding["message_locale_key"], locale="en", **_keyed(finding["message_facts"]))
                    )
                    for finding in report["findings"]
                ],
            )

            written = await agent.export(profile_id, work_unit_id, output)
            prepared.aliases[str(output)] = "<export>"
            prepared.aliases[output.name] = "<export-file>"
            prepared.notices["app modelo export"] = _export_notices(written)
            prepared.export = {
                "format": written["export_format"],
                "byte_size": written["byte_size"],
                "file_sha256": written["file_sha256"],
                "evidence_status": written["evidence_status"],
            }

            history = await agent.run("aeat config profile history", "profile.history", {"profile_id": profile_id})
            prepared.recorded(history.succeeded()["events"])
    finally:
        await adapter.close()
    prepared.exported = output.read_bytes()
    return prepared, agent_label


# --- The command-line side --------------------------------------------------------------------------------------


class _CommandLine:
    """The person at the command line, who gives the profile password to every command."""

    def __init__(self, runtime: StoredSignInRuntime, prepared: _Prepared) -> None:
        self._label = resolve_login_target(str(runtime.profile_id)).label
        self._prepared = prepared
        self.notices: list[dict[str, Any]] = []
        """The notices of the last command that succeeded."""

    def _invoke(self, command: Sequence[str]) -> Result:
        path = _command_path(command)
        self._prepared.calls.append(" ".join(("aeat", *path)))
        # The command authenticates through the runtime, so this process holds no open profile of its own.
        close_active_bucket_session()
        with override_settings(cadrumo_cli_reveal_identifiers=True):
            result = invoke_cached_cli(
                ["--language", "en", "--format", "json", "--profile", self._label, "--profile-secrets-stdin", *command],
                input=json.dumps({"profile_passphrase": PROFILE_INPUT}),
            )
        assert PROFILE_INPUT not in result.output
        return result

    def await_the_runtime(self) -> None:
        """Read the profile's history until the command answers, which starts the profile's worker."""
        deadline = time.monotonic() + _COLD_START_SECONDS
        result = self._invoke(("config", "profile", "history"))
        while result.exit_code != 0 and time.monotonic() < deadline:
            time.sleep(2)
            result = self._invoke(("config", "profile", "history"))
        assert result.exit_code == 0, result.output

    def run(self, *command: str) -> dict[str, Any]:
        """Run one command to success and return its result."""
        result = self._invoke(command)
        assert result.exit_code == 0, (command, result.output)
        self.notices = unwrap_envelope_notices(result.output)
        self._prepared.notices[" ".join(_command_path(command))] = self.notices
        return require_schema_envelope(result.output)

    def refused(self, *command: str) -> dict[str, Any]:
        """Run one command the product refuses and return its error."""
        result = self._invoke(command)
        assert result.exit_code != 0, (command, result.output)
        error = require_error_document(result.output)["error"]
        assert isinstance(error, dict), result.output
        return error


def _command_path(command: Sequence[str]) -> Sequence[str]:
    """The words of a command before its first option or identifier."""
    return command[: next(index for index, token in enumerate((*command, "-")) if _is_argument(token))]


def _is_argument(token: str) -> bool:
    """Whether a command-line token is an option or an identifier, and so past the command's own path."""
    return token.startswith("-") or len(token) == 64


def _options(facts: Mapping[str, str]) -> list[str]:
    """Spell profile answers as the command's options: a switch for a yes or no, an option with its value otherwise."""
    options: list[str] = []
    for name, value in facts.items():
        if value in {"true", "false"}:
            options.append(f"--{name}" if value == "true" else f"--no-{name}")
        else:
            options.extend((f"--{name}", value))
    return options


def _calculate_at_the_command_line(
    aeat: _CommandLine, work_unit_id: str, casillas: Mapping[str, str], bindings: Mapping[str, str]
) -> dict[str, Any]:
    return aeat.run(
        "app", "modelo", "work", "calculate", work_unit_id,
        *(token for key, value in casillas.items() for token in ("--casilla", f"{key}={value}")),
        *(token for key, value in bindings.items() for token in ("--binding", f"{key}={value}")),
        "--by", _PERSON,
    )  # fmt: skip


def _prepare_through_the_command_line(
    runtime: StoredSignInRuntime, declaration: _Declaration, output: Path
) -> _Prepared:
    """Prepare ``declaration`` with the real commands, reading every identifier from an earlier envelope."""
    prepared = _Prepared()
    prepared.aliases[str(runtime.profile_id)] = "<profile>"
    aeat = _CommandLine(runtime, prepared)
    aeat.await_the_runtime()

    aeat.run("config", "profile", "edit", "--quiet", *_options(declaration.profile))
    aeat.run("config", "profile", "complete-setup")

    for index, row in enumerate(declaration.rows, start=1):
        added = aeat.run(
            "app", "ledger", "add",
            "--date", row.booked_date,
            "--amount", row.amount,
            "--direction", row.direction,
            "--description", row.description,
            "--counterparty", row.counterparty,
            "--actor", _PERSON,
        )  # fmt: skip
        transaction_id = added["transaction"]["transaction_id"]
        prepared.aliases[transaction_id] = f"<row:{index}>"
        classified = aeat.run(
            "app", "ledger", "classify", transaction_id,
            *(token for name, value in row.classification.items() for token in (_CLASSIFY_OPTIONS[name], value)),
            "--actor", _PERSON,
        )  # fmt: skip
        prepared.ledger.append(_row_facts(classified["transaction"], classified["review_status"]))

    created = aeat.run(
        "app", "modelo", "work", "create",
        "--modelo", declaration.modelo, "--year", str(declaration.year), "--period", declaration.period,
        "--by", _PERSON,
    )  # fmt: skip
    work_unit_id = created["work_unit_id"]
    prepared.aliases[work_unit_id] = "<work-unit>"
    prepared.work_unit = {name: created[name] for name in _UNIT_FACTS}

    verify = ("app", "modelo", "work", "verify", "--work-unit-id", work_unit_id, "--by", _PERSON)
    if declaration.binding_first_left_out is not None:
        first = _calculate_at_the_command_line(aeat, work_unit_id, declaration.casillas, declaration.first_bindings())
        prepared.aliases[first["calculation_revision_id"]] = "<first-calculation>"
        refused = aeat.refused(*verify)
        prepared.refused_verification = {
            "code": refused["code"],
            "message": refused["message"],
            "facts": {key: value for key, value in refused["context"].items() if key not in _EXCHANGE_FACTS},
        }

    calculated = _calculate_at_the_command_line(aeat, work_unit_id, declaration.casillas, declaration.bindings)
    prepared.aliases[calculated["calculation_revision_id"]] = "<calculation>"
    _calculation(prepared, calculated)

    verified = aeat.run(*verify)
    prepared.verification = _verification(
        verified, [_finding(finding, finding["message"]) for finding in verified["findings"]]
    )

    prepared.aliases[str(output)] = "<export>"
    prepared.aliases[output.name] = "<export-file>"
    exported = aeat.run("app", "modelo", "export", work_unit_id, "--output", str(output), "--by", _PERSON)
    (evidence,) = (
        notice["context"]["evidence_status"]
        for notice in aeat.notices
        if notice["code"] == "modelo.export.local_export_not_official_evidence"
    )
    prepared.export = {
        "format": exported["format"],
        "byte_size": exported["byte_size"],
        "file_sha256": exported["file_sha256"],
        "evidence_status": evidence,
    }

    history = aeat.run("config", "profile", "history")
    prepared.recorded(history["events"])
    prepared.exported = output.read_bytes()
    return prepared


# --- The proof --------------------------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class _Twice:
    """One declaration prepared in two fresh profiles from the same inputs."""

    through_mcp: _Prepared
    through_the_command_line: _Prepared
    agent_label: str


def _prepared_twice(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, declaration: _Declaration, operation: PinnedAuthorityOperation
) -> _Twice:
    """Prepare ``declaration`` in two fresh profiles: through MCP alone, then through the command line.

    Each profile's store is read once its runtime has stopped, for the one fact no frontend shows.
    """
    exports = tmp_path / "exports"
    exports.mkdir()
    with _fresh_profile(tmp_path / "through-mcp", monkeypatch, signed_in=True) as runtime:
        through_mcp, agent_label = asyncio.run(
            _prepare_through_mcp(runtime, declaration, exports / f"mcp-{declaration.export_name}")
        )
        mcp_root, mcp_profile = runtime.root, runtime.profile_id
    through_mcp.origins = _stored_origins(mcp_root, mcp_profile, operation)
    with _fresh_profile(tmp_path / "through-the-command-line", monkeypatch, signed_in=False) as runtime:
        through_the_command_line = _prepare_through_the_command_line(
            runtime, declaration, exports / f"command-line-{declaration.export_name}"
        )
        line_root, line_profile = runtime.root, runtime.profile_id
    through_the_command_line.origins = _stored_origins(line_root, line_profile, operation)
    return _Twice(through_mcp, through_the_command_line, agent_label)


def _as_stated(step: str, notices: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Reduce the notices a command printed about its work to the facts the step's operation result states.

    A notice about the invocation itself, which every command prints because its password was given to this
    one process, is about no step's work and is left out.
    """
    notices = [notice for notice in notices if notice["code"] not in _INVOCATION_NOTICES]
    if step == "app modelo export":
        return [
            {"code": notice["code"]}
            | ({"evidence_status": notice["context"]["evidence_status"]} if notice["code"] == _EVIDENCE_NOTICE else {})
            for notice in notices
        ]
    return [{"code": notice["code"], "message": notice["message"]} for notice in notices]


def _assert_the_same_declaration(twice: _Twice, declaration: _Declaration) -> None:
    through_mcp, through_the_command_line = twice.through_mcp, twice.through_the_command_line
    assert set(through_mcp.calls) <= _MCP_TOOLS, sorted(set(through_mcp.calls))
    # The command line prints nothing it has not passed through its output redaction, so the agent's replies
    # are read the way the command line would have printed them.
    as_printed = redact_structured_for_cli_output(through_mcp.told(), reveal_identifiers=True)
    assert isinstance(as_printed, dict)
    printed = through_the_command_line.told()
    for part, told in printed.items():
        if part == "events":
            different = [
                (index, agent, person)
                for index, (agent, person) in enumerate(zip(as_printed[part], told, strict=True))
                if agent != person
            ]
            assert not different, different
        assert as_printed[part] == told, part
    assert through_mcp.exported == through_the_command_line.exported
    assert through_mcp.exported, "the export wrote an empty file"
    assert through_mcp.export["byte_size"] == len(through_mcp.exported)
    assert through_mcp.verification["granted"] is True
    assert through_mcp.export["evidence_status"] == "local_export_not_official_aeat_filing_evidence"
    # No event on either side says a declaration was presented.
    assert not [event for event in through_mcp.events if event["event_type"].startswith("modelo.filed")]

    # The first intended difference: an agent's acts are recorded under its session, a person's under the label
    # the command line supplied. Where neither acted (the profile's own lifecycle) both record the same name.
    assert actor_label_is_an_agents(twice.agent_label) and not actor_label_is_an_agents(_PERSON)
    recorded = list(zip(through_mcp.actors, through_the_command_line.actors, strict=True))
    acted = {(agent, person) for agent, person in recorded if agent != person}
    assert acted == {(twice.agent_label, _PERSON)}
    assert _PERSON not in through_mcp.actors and twice.agent_label not in through_the_command_line.actors

    # The second: every row was classified by the one who acted, so the stored origin of its classification is
    # the agent's on one side and the person's on the other. It is read from the store, which no frontend shows.
    rows = {row.description for row in declaration.rows}
    assert set(through_mcp.origins) == set(through_the_command_line.origins) == rows
    assert set(through_mcp.origins.values()) == {"agent"}
    assert set(through_the_command_line.origins.values()) == {"person"}

    # The notices both sides state about the same step are the same notices. The command line states more of
    # them, in its own words, than an operation result carries; those are listed in the failure of a step
    # whose notices the result does state.
    for step, stated in through_mcp.notices.items():
        printed = _as_stated(step, through_the_command_line.notices.get(step, []))
        assert printed == stated, (step, through_the_command_line.notices.get(step))
    assert through_mcp.notices, "the agent's results stated no notice to compare"


def test_a_quarterly_declaration_prepared_through_mcp_alone_equals_the_command_lines(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, authority_operation: PinnedAuthorityOperation
) -> None:
    twice = _prepared_twice(tmp_path, monkeypatch, _QUARTERLY, authority_operation)

    _assert_the_same_declaration(twice, _QUARTERLY)
    told = twice.through_mcp
    # The inputs reached the calculation: both invoices are the quarter's income, and the private purchase is
    # not an expense of the activity.
    assert Decimal(told.casilla_values["01"]) == Decimal("5250.50")
    assert Decimal(told.casilla_values["02"]) == Decimal("0")
    # The first verification was refused for the box that could not be worked out, and said so to both.
    assert told.refused_verification["code"] == "REFUSED_MODELO_CALCULATION_BLOCKED"
    assert told.refused_verification["facts"]["reason"] == "unresolved_binding"
    assert told.refused_verification["facts"]["box"] == "05"


def test_an_annual_declaration_prepared_through_mcp_alone_equals_the_command_lines(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, authority_operation: PinnedAuthorityOperation
) -> None:
    twice = _prepared_twice(tmp_path, monkeypatch, _ANNUAL, authority_operation)

    _assert_the_same_declaration(twice, _ANNUAL)
    told = twice.through_mcp
    assert Decimal(told.casilla_values["0003"]) == Decimal("24000")
    assert told.export["format"] == "xml-dictionary"
    # The agent is told the taxpayer's own identifier as the calculation holds it. The command line prints the
    # same value as a pseudonym, which is its rule for everything it prints and withholds nothing from the agent.
    tax_id = _ANNUAL.profile["tax-id"]
    assert told.inputs["DPNIF_D"] == tax_id
    assert twice.through_the_command_line.inputs["DPNIF_D"] != tax_id
    assert tax_id.encode() in told.exported

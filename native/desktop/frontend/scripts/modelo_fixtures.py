"""Produce the desktop's Modelo wire types and its scenario envelopes from the Python models.

``src/shell/modeloContract.ts`` is generated from the JSON schema of every
request and result the desktop's admitted ``modelo.*`` definitions register,
plus the edit operator input the financial body carries. The envelopes under
``src/dev/fixtures/modelo/`` are read through the application's own read path
for a synthetic taxpayer in a throwaway profile over the published authority.

``scripts/modelo-fixtures.mjs`` drives this module and formats what it writes;
run that, not this. ``contract`` writes the unformatted module to standard
output; ``envelopes`` writes the envelopes; ``validate`` fails when the host's
admitted list differs from the registered family or a stored envelope no
longer validates against its model. The envelopes carry the day they were
read, so they are validated rather than compared byte for byte.
"""

from __future__ import annotations

import argparse
import ast
import asyncio
import json
import re
import sys
import tempfile
import textwrap
from collections.abc import AsyncIterator, Iterable, Iterator, Mapping
from contextlib import asynccontextmanager, contextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, cast
from uuid import UUID

from pydantic import BaseModel
from pydantic.json_schema import models_json_schema

from cadrumo.entrypoints.operation_composition import build_production_operation_registry

FRONTEND = Path(__file__).resolve().parents[1]
FIXTURES = FRONTEND / "src" / "dev" / "fixtures" / "modelo"

#: The host's closed list of admitted definitions, which the generated mirror is pinned to.
ADMITTED = FRONTEND.parent / "src-tauri" / "src" / "shell" / "modelo" / "admitted.rs"
#: What the host records about each admitted definition, generated from the shipped contracts.
HOST_FACTS = ADMITTED.with_name("relay_contracts.json")
#: The held person's relay, whose request bound an edit body is held to, and where its constants come from.
RELAY_SOURCES: tuple[Path, ...] = (
    FRONTEND.parent / "src-tauri" / "src" / "agent" / "person.rs",
    FRONTEND.parents[1] / "application" / "src" / "person_operations.rs",
)

#: The declarations the envelopes read: modelo, period, and whether it is calculated first.
DECLARATIONS: tuple[tuple[str, str, bool], ...] = (
    ("130", "1T", True),
    ("303", "1T", False),
    ("347", "0A", True),
    ("390", "0A", False),
)
LANGUAGES = ("en", "es", "ca", "hu")
#: The operator the desktop names on requests that take an actor, as src/shell/modelo.ts states it.
ACTOR = "operator:desktop-modelo"
#: What the operator answers for the filed 130: the earlier Renta's activity income and the earlier-filing figures.
FILED_130_ANSWERS: tuple[tuple[str, str], ...] = (
    ("irpf.previous_year_economic_activity_net_income", "13000"),
    ("modelo-130-resultados-negativos-anteriores", "0"),
    ("modelo-130-pagos-fraccionados-anteriores", "0"),
)
#: The boxes whose help card the envelopes carry, by modelo.
#: The quarter's activity income booked for the filled 130s.
INCOME_130 = Decimal("12000.00")
#: When the synthetic AEAT receipt of the filed 130 is imported.
RECEIPT_AT = datetime(2026, 4, 21, 9, 30, tzinfo=UTC)
#: The quarter the AEAT holds a Modelo 130 for that the profile has no declaration of, and when it was filed and seen.
AEAT_ONLY = ("130", "2T")
AEAT_PRESENTED_AT = datetime(2026, 7, 14, 11, 0, tzinfo=UTC)
AEAT_SEEN_AT = datetime(2026, 7, 15, 9, 0, tzinfo=UTC)
#: The seeded profile's tax id, as the modelo-ready baseline states it.
MAIN_TAX_ID = "12345678Z"
HELP_BOXES: Mapping[str, tuple[str, ...]] = {"130": ("01", "03", "07", "19"), "303": ("27", "71")}


# -- wire types ---------------------------------------------------------------


def definitions() -> tuple[str, ...]:
    """Every registered ``modelo.*`` definition: the family the host admits whole."""
    contracts = build_production_operation_registry().public_contract_set.definitions
    return tuple(sorted(item.definition_id for item in contracts if item.definition_id.startswith("modelo.")))


def host_operations() -> dict[str, Any]:
    """What the host records about each admitted definition: its subject, financial body and file fields."""
    return json.loads(HOST_FACTS.read_text("utf-8"))["operations"]


_RUST_CONSTANT = re.compile(r"pub(?:\([a-z]+\))? const ([A-Z_][A-Z0-9_]*): usize =\s*([^;]+);")


def _usize(expression: str, constants: Mapping[str, str]) -> int:
    """Evaluate one Rust ``usize`` constant expression of literals, names, ``+``, ``-`` and ``*``."""

    def value(node: ast.expr) -> int:
        if isinstance(node, ast.Constant) and isinstance(node.value, int):
            return node.value
        if isinstance(node, ast.Name) and node.id in constants:
            return _usize(constants[node.id], constants)
        if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Sub, ast.Mult)):
            left, right = value(node.left), value(node.right)
            return (
                left + right
                if isinstance(node.op, ast.Add)
                else left - right
                if isinstance(node.op, ast.Sub)
                else left * right
            )
        raise SystemExit(f"the relay's request bound is no longer a plain constant expression: {expression!r}")

    return value(ast.parse(_digits(expression), mode="eval").body)


def _digits(expression: str) -> str:
    """Drop Rust digit separators inside number literals only, keeping names whole."""
    return re.sub(r"(?<![A-Za-z_])(\d[\d_]*)", lambda found: found.group(1).replace("_", ""), expression)


def request_limit() -> int:
    """The bound the host holds an edit body to: its relay's ``REQUEST_LIMIT``, evaluated from the Rust sources."""
    constants: dict[str, str] = {}
    for source in RELAY_SOURCES:
        for name, expression in _RUST_CONSTANT.findall(source.read_text("utf-8")):
            constants.setdefault(name, expression.strip())
    if "REQUEST_LIMIT" not in constants:
        raise SystemExit(f"{RELAY_SOURCES[0]} no longer declares REQUEST_LIMIT")
    return _usize(constants["REQUEST_LIMIT"], constants)


def _constant_list(doc: str, name: str, items: Iterable[str]) -> str:
    values = "\n".join(f"  {_literal(item)}," for item in items)
    return f"/** {doc} */\nexport const {name} = [\n{values}\n] as const;"


def admitted_by_host() -> tuple[str, ...]:
    """The ids of the host's closed list, as its Rust constant spells them."""
    table = ADMITTED.read_text("utf-8").split("const ADMITTED", 1)[1].split("];", 1)[0]
    return tuple(sorted(re.findall(r'\(\s*"(modelo\.[^"]+)",', table)))


def _model_roots() -> tuple[list[tuple[str, str, type[BaseModel]]], list[type[BaseModel]]]:
    """Each definition's request, result and review models, and every model the window sends."""
    from cadrumo.application.modelo.edit_operator_input import ModeloEditOperatorInputV2

    registry = build_production_operation_registry()
    roots: list[tuple[str, str, type[BaseModel]]] = []
    sent: list[type[BaseModel]] = [ModeloEditOperatorInputV2]
    for definition_id in definitions():
        contract = registry.lookup_public_contract(definition_id)
        request = registry.lookup_public_schema_binding(contract.request_schema).model_type
        roots.append((definition_id, "request", request))
        if contract.transient_financial_operand is None:
            sent.append(request)
        for role, identity in (("result", contract.result_schema), ("review", contract.review_projection_schema)):
            if identity is not None:
                roots.append((definition_id, role, registry.lookup_public_schema_binding(identity).model_type))
    return roots, sent


def _ts_name(name: str) -> str:
    return name.lstrip("_")


def _refs(node: object) -> Iterator[str]:
    if isinstance(node, dict):
        mapping = cast(dict[str, object], node)
        ref = mapping.get("$ref")
        if isinstance(ref, str):
            yield ref.rsplit("/", 1)[-1]
        for value in mapping.values():
            yield from _refs(value)
    elif isinstance(node, list):
        for value in cast(list[object], node):
            yield from _refs(value)


def _reach(defs: Mapping[str, Any], start: Iterable[str]) -> set[str]:
    seen: set[str] = set()
    pending = list(start)
    while pending:
        name = pending.pop()
        if name in seen:
            continue
        seen.add(name)
        pending.extend(_refs(defs[name]))
    return seen


def _literal(value: object) -> str:
    return json.dumps(value, ensure_ascii=False)


class _Writer:
    """Render JSON-schema definitions as TypeScript types, one per definition."""

    def __init__(self, defs: Mapping[str, Any], *, sent_only: set[str]) -> None:
        self._defs = defs
        self._sent_only = sent_only

    def inlined(self, name: str) -> bool:
        """A private constrained scalar is written where it is used."""
        node = self._defs[name]
        return name.startswith("_") and "properties" not in node and "enum" not in node

    def type_of(self, node: Mapping[str, Any]) -> str:
        if "$ref" in node:
            name = node["$ref"].rsplit("/", 1)[-1]
            return self.type_of(self._defs[name]) if self.inlined(name) else _ts_name(name)
        if "const" in node:
            return _literal(node["const"])
        if "enum" in node:
            return " | ".join(_literal(value) for value in node["enum"])
        for key in ("anyOf", "oneOf"):
            if key in node:
                members: list[str] = []
                for member in node[key]:
                    rendered = self.type_of(member)
                    if rendered not in members:
                        members.append(rendered)
                return " | ".join(members)
        kind = node.get("type")
        if kind == "array":
            if "prefixItems" in node:
                return "[" + ", ".join(self.type_of(item) for item in node["prefixItems"]) + "]"
            item = self.type_of(node.get("items", {}))
            return f"({item})[]" if " | " in item else f"{item}[]"
        if kind == "object":
            values = node.get("additionalProperties")
            value = self.type_of(values) if isinstance(values, dict) else "unknown"
            return f"{{ [key: string]: {value} }}"
        if isinstance(kind, list):
            return " | ".join(self.type_of({"type": each}) for each in cast(list[str], kind))
        return {"string": "string", "integer": "number", "number": "number", "boolean": "boolean", "null": "null"}.get(
            cast(str, kind), "unknown"
        )

    def definition(self, name: str) -> str:
        node = self._defs[name]
        lines = _doc(node.get("description"), indent="")
        if "properties" not in node:
            lines.append(f"export type {_ts_name(name)} = {self.type_of(node)};")
            return "\n".join(lines)
        required = set(node.get("required", ()))
        optional_absent = name in self._sent_only
        lines.append(f"export type {_ts_name(name)} = {{")
        for prop, schema in node["properties"].items():
            lines.extend(_doc(schema.get("description"), indent="  "))
            mark = "?" if optional_absent and prop not in required else ""
            lines.append(f"  {prop}{mark}: {self.type_of(schema)};")
        lines.append("};")
        return "\n".join(lines)


_ROLE = re.compile(r":[a-z]+:`~?\.?([^`]+)`")


def _doc(text: object, *, indent: str) -> list[str]:
    """A Python docstring as a JSDoc block: roles and double backticks read as plain code spans."""
    if not isinstance(text, str) or not text.strip():
        return []
    plain = _ROLE.sub(lambda found: "`" + found.group(1).rsplit(".", 1)[-1] + "`", text).replace("``", "`")
    plain = plain.replace("*/", "*\\/")
    paragraphs = [" ".join(part.split()) for part in plain.strip().split("\n\n") if part.strip()]
    body: list[str] = []
    for index, paragraph in enumerate(paragraphs):
        if index:
            body.append("")
        body.extend(textwrap.wrap(paragraph, width=76 - len(indent)))
    return [f"{indent}/**", *(f"{indent} * {line}".rstrip() for line in body), f"{indent} */"]


_HEADER = """\
// Generated by scripts/modelo_fixtures.py from the JSON schema of the
// registered Python models; do not edit. Regenerate with
// `node scripts/modelo-fixtures.mjs`; `--check` fails when it is stale.
//
// The request and result of every definition the desktop admits, and the
// edit operator input the financial body carries, with field names, nullity
// and closed vocabularies as the application serialises them. A result field
// is always present; a field of what the window sends may be left out where
// the model gives it a default.
"""


def render_contract() -> str:
    """The generated TypeScript module, before the frontend's formatter writes it."""
    roots, sent = _model_roots()
    models = [(model, "serialization") for _, _, model in roots] + [(model, "validation") for model in sent]
    _, schema = models_json_schema(cast(Any, list(dict.fromkeys(models))), ref_template="#/$defs/{model}")
    defs: dict[str, Any] = schema["$defs"]
    received = _reach(defs, (model.__name__ for _, role, model in roots if role != "request"))
    sent_reach = _reach(defs, (model.__name__ for model in sent))
    writer = _Writer(defs, sent_only=sent_reach - received)
    names = sorted((name for name in defs if not writer.inlined(name)), key=_ts_name)
    blocks = [_HEADER, *(writer.definition(name) for name in names)]
    blocks.append(
        _constant_list(
            "The definitions the host admits, mirroring its closed list.", "MODELO_DEFINITIONS", definitions()
        )
    )
    operations = host_operations()
    blocks.append(
        _constant_list(
            "The definitions whose request is the edit's financial body: they are sent\n"
            " * through the raw edit commands, never as a payload.",
            "MODELO_EDIT_DEFINITIONS",
            sorted(key for key, facts in operations.items() if facts["financial"]),
        )
    )
    blocks.append(
        _constant_list(
            "The definitions whose subject is the work unit owning the stored record\n"
            " * their request names; only the store knows it, so the page names it from\n"
            " * the form it read. Every other definition takes no work unit.",
            "MODELO_STORED_SUBJECT_DEFINITIONS",
            sorted(key for key, facts in operations.items() if facts["subject"]["kind"] == "stored_work_unit"),
        )
    )
    blocks.append(
        "/** The longest edit body, in bytes, the host sends on: its relay's request\n"
        " * bound. A longer one is refused with `invalid` before anything is sent;\n"
        " * the page splits the edit. */\n"
        f"export const MODELO_EDIT_BODY_LIMIT = {request_limit()};"
    )
    by_definition: dict[str, list[str]] = {}
    for definition_id, role, model in roots:
        by_definition.setdefault(definition_id, []).append(f"{role}: {_ts_name(model.__name__)};")
    entries = "\n".join(f"  {_literal(key)}: {{ {' '.join(parts)} }};" for key, parts in by_definition.items())
    blocks.append(
        "/** Each admitted definition's registered request, result and review, as the\n"
        " * runtime's contract names them; a request names the profile the host fills. */\n"
        f"export type ModeloContracts = {{\n{entries}\n}};"
    )
    return "\n\n".join(blocks) + "\n"


# -- envelopes ----------------------------------------------------------------


@contextmanager
def _seeded(tmp: Path, *, facts: tuple[Any, ...] = ()) -> Iterator[Any]:
    """One synthetic profile, its first declaration the first the envelopes read, under every session adapter."""
    from cadrumo.entrypoints.adapter_composition import profile_adapter_composition
    from cadrumo.entrypoints.tests.modelo_operator_work_storage import seeded_operator_work

    first, *_ = DECLARATIONS
    with (
        profile_adapter_composition(),
        seeded_operator_work(tmp, modelo=first[0], period_code=first[1], extra_facts=facts) as work,
    ):
        yield work


def _other_declaration(work: Any, modelo: str, period_code: str) -> Any:
    from cadrumo.application.modelo.work_lifecycle import create_work_unit
    from cadrumo.core.period import Period
    from cadrumo.domain.modelos.work_unit import WorkUnit
    from cadrumo.entrypoints.adapter_composition import build_work_lifecycle_ports
    from cadrumo.entrypoints.tests.modelo_operator_work_storage import SEEDED_AT, SeededOperatorWork

    unit = work.work_unit
    period = Period.from_year_and_code(unit.filing_year, period_code)
    revision = work.operation.revision_for_context(modelo, filing_year=unit.filing_year, period=period.registry_token)
    created: WorkUnit = create_work_unit(
        bucket_id=unit.bucket_id,
        modelo=modelo,
        filing_year=unit.filing_year,
        period=period,
        revision_id=str(revision.id),
        ports=build_work_lifecycle_ports(bucket_id=unit.bucket_id),
        clock=SEEDED_AT,
        operation=work.operation,
    )
    return SeededOperatorWork(
        work_unit=created,
        ports=work.ports,
        operation=work.operation,
        receipt_repository_factory=work.receipt_repository_factory,
    )


def _read_ports(bucket_id: str, operation: Any) -> Any:
    from cadrumo.adapters.persistence.profile.modelos_verification_reports import VerificationReportCatalogueRepository
    from cadrumo.application.modelo.workbench_read import ModeloWorkbenchReadPorts
    from cadrumo.entrypoints.adapter_composition import build_calculation_action_ports

    ports = build_calculation_action_ports(bucket_id=bucket_id, operation=operation)
    return ModeloWorkbenchReadPorts(
        work_units=ports.work_unit_repository,
        calculations=ports.calculation_repository,
        verifications=VerificationReportCatalogueRepository(bucket_id=bucket_id),
        bucket_events=ports.bucket_event_repository,
        filings=ports.filing_repository,
    )


def _write(directory: Path, name: str, model: BaseModel) -> None:
    (directory / name).write_text(model.model_dump_json(), "utf-8", newline="\n")
    sys.stdout.write(f"{name}\n")


@dataclass(slots=True)
class _ReadContext:
    """The slice of the supervisor's context an executor uses: phase, effect, operand custody and its commit section."""

    identity: Any
    authority_operation: Any
    typed_financial_operand: Any = None
    results: list[BaseModel] = field(default_factory=list)

    @property
    def events(self) -> _ReadContext:
        return self

    @property
    def operands(self) -> _ReadContext:
        return self

    @property
    def cancellation(self) -> _ReadContext:
        return self

    @asynccontextmanager
    async def irreversible_section(self) -> AsyncIterator[None]:
        yield

    async def phase(self, phase_code: str) -> None:
        del phase_code

    async def effect(self, effect: object) -> None:
        del effect

    async def put(self, operand: BaseModel, *, written_at: object) -> str:
        del written_at
        self.results.append(operand)
        return "0" * 64


def _renew(work: Any, baseline: Any) -> BaseModel:
    """Renew the admitted edit baseline through the modelo.edit.renew executor, as an editor does before review."""
    from cadrumo.application.modelo.edit_baseline_projection import ModeloEditApplyBaselineV1
    from cadrumo.application.modelo.workbench_operations import (
        MODELO_EDIT_RENEW_OPERATION_DEFINITION_ID,
        ModeloEditRenewExecutor,
        ModeloEditRenewRequest,
    )
    from cadrumo.core.external_constants import OutputLanguage

    contracts = build_production_operation_registry().public_contract_set
    executor = ModeloEditRenewExecutor(ports_factory=_read_ports, contracts=lambda: contracts)
    request = ModeloEditRenewRequest(
        profile_id=UUID(work.work_unit.bucket_id),
        baseline=ModeloEditApplyBaselineV1.from_baseline(baseline),
        output_language=OutputLanguage.EN,
    )
    return _run_executor(work, MODELO_EDIT_RENEW_OPERATION_DEFINITION_ID, executor, request)


def _preflight(work: Any, baseline: Any, typed: tuple[tuple[str, str], ...]) -> BaseModel:
    """Preflight entries as the filer typed them, through the production executor and its operand path."""
    from cadrumo.application.modelo.edit_apply_contracts import ModeloEditApplySubmissionV1
    from cadrumo.application.modelo.edit_contract import ModeloEditMutationFamily
    from cadrumo.application.modelo.edit_models import (
        ModeloEditParseRequestV1,
        ModeloEditScalarAddressV1,
        ModeloEditSubmissionV1,
    )
    from cadrumo.application.modelo.edit_operator_input import ModeloEditOperatorInputV2, prepare_modelo_edit_operand
    from cadrumo.application.modelo.edit_transient_operand import modelo_edit_financial_operand
    from cadrumo.application.modelo.workbench_operations import (
        MODELO_EDIT_PREFLIGHT_OPERATION_DEFINITION_ID,
        ModeloEditPreflightExecutor,
    )
    from cadrumo.application.operations.models import OperationIdentity, OperationRequest
    from cadrumo.application.operations.tests.financial_operand_delivery import deliver_financial_operand
    from cadrumo.core.casilla_id import validated_casilla_id
    from cadrumo.core.external_constants import OutputLanguage

    entries = tuple(
        ModeloEditParseRequestV1(
            address=ModeloEditScalarAddressV1(casilla_id=validated_casilla_id(box)),
            entry_locale=OutputLanguage.ES,
            lexeme="",
        )
        for box, _ in typed
    )
    submission = ModeloEditSubmissionV1(
        baseline=baseline, mutation_family=ModeloEditMutationFamily.CALCULATE, lexemes=entries
    )
    # The entries as typed are what a frontend sends; a dump of the model never repeats them.
    document = json.loads(
        ModeloEditOperatorInputV2(
            submission=ModeloEditApplySubmissionV1.from_submission(submission), output_language=OutputLanguage.EN
        ).model_dump_json()
    )
    for entry, (_, text) in zip(document["submission"]["lexemes"], typed, strict=True):
        entry["lexeme"] = text
    definition = MODELO_EDIT_PREFLIGHT_OPERATION_DEFINITION_ID
    prepared = prepare_modelo_edit_operand(
        definition_id=definition,
        profile_id=UUID(work.work_unit.bucket_id),
        subject_ref=work.work_unit_id,
        input_json=json.dumps(document),
    )
    identity = OperationIdentity(operation_id="f" * 64, definition_id=definition, subject_ref=work.work_unit_id)
    executor = ModeloEditPreflightExecutor(ports_factory=_read_ports)
    results: list[BaseModel] = []

    async def run() -> None:
        if prepared.operand is None:
            raise SystemExit("the preflight operand was not prepared")
        try:
            async with deliver_financial_operand(
                identity=identity, declaration=modelo_edit_financial_operand(None), operand=prepared.operand
            ) as access:
                prepared.release()
                context = _ReadContext(
                    identity=identity, authority_operation=work.operation, typed_financial_operand=access
                )
                request = OperationRequest(
                    definition_id=definition, subject_ref=work.work_unit_id, payload=prepared.request
                )
                await executor.execute(request, cast(Any, context))
                results.extend(context.results)
        finally:
            prepared.release()

    asyncio.run(run())
    (result,) = results
    return result


def _write_form(directory: Path, work: Any, name: str, *, with_help: bool = False) -> None:
    """Write one declaration's form envelope in every language, and its help cards where asked."""
    from cadrumo.application.modelo.workbench_operations import ModeloCasillaHelpProjectionV1
    from cadrumo.application.modelo.workbench_projection import project_modelo_workbench_form
    from cadrumo.application.modelo.workbench_read import read_modelo_casilla_help, read_modelo_workbench_form
    from cadrumo.core.casilla_id import validated_casilla_id
    from cadrumo.core.external_constants import OutputLanguage

    contracts = build_production_operation_registry().public_contract_set
    bucket_id = work.work_unit.bucket_id
    profile_id = UUID(bucket_id)
    modelo = str(work.work_unit.modelo)
    for language in LANGUAGES:
        read = read_modelo_workbench_form(
            work.work_unit_id,
            bucket_id=bucket_id,
            ports=_read_ports(bucket_id, work.operation),
            operation=work.operation,
            operation_contracts=contracts,
            language=OutputLanguage(language),
        )
        _write(directory, f"{name}-{language}.json", project_modelo_workbench_form(profile_id, work.work_unit_id, read))
        for box in HELP_BOXES.get(modelo, ()) if with_help else ():
            card = read_modelo_casilla_help(
                work.work_unit_id,
                validated_casilla_id(box),
                bucket_id=bucket_id,
                registry_revision_id=read.registry_revision_id,
                calculation_revision_id=read.calculation_revision_id,
                ports=_read_ports(bucket_id, work.operation),
                operation=work.operation,
                language=OutputLanguage(language),
            )
            _write(
                directory,
                f"help-{modelo}-{box}-{language}.json",
                ModeloCasillaHelpProjectionV1(
                    result_version=1, profile_id=profile_id, work_unit_id=work.work_unit_id, card=card
                ),
            )


def _run_executor(
    work: Any, definition_id: str, executor: Any, payload: BaseModel, *, subject_ref: str | None = None
) -> BaseModel:
    """Run one registered operation's production executor as the supervisor would; its public result.

    The subject is the declaration's work unit unless ``subject_ref`` names another.
    """
    from cadrumo.application.operations.models import OperationIdentity, OperationRequest

    subject = work.work_unit_id if subject_ref is None else subject_ref
    identity = OperationIdentity(operation_id="e" * 64, definition_id=definition_id, subject_ref=subject)
    context = _ReadContext(identity=identity, authority_operation=work.operation)
    request = OperationRequest(definition_id=definition_id, subject_ref=subject, payload=payload)
    asyncio.run(executor.execute(request, cast(Any, context)))
    (result,) = context.results
    return result


def _verify(work: Any) -> Any:
    """Check the declaration's current calculation through the modelo.work.verify executor."""
    from cadrumo.adapters.persistence.storage.certificate_secret_backend import build_certificate_secret_backend
    from cadrumo.adapters.persistence.storage.operator_scope import build_operator_scope_ports
    from cadrumo.application.modelo.operation_definitions import (
        MODELO_WORK_VERIFY_OPERATION_DEFINITION_ID,
        ModeloWorkVerifyExecutor,
        resolve_active_workflow_profile,
    )
    from cadrumo.application.modelo.work_verification_contracts import ModeloWorkVerifyRequest
    from cadrumo.entrypoints.adapter_composition import build_verification_repository_bundle

    executor = ModeloWorkVerifyExecutor(
        certificate_secret_backend_factory=build_certificate_secret_backend,
        profile_resolver=resolve_active_workflow_profile,
        operator_scope_ports=build_operator_scope_ports(),
        verification_repository_bundle_factory=build_verification_repository_bundle,
    )
    request = ModeloWorkVerifyRequest(calculation_revision_id=work.require_head().calculation_revision_id, actor=ACTOR)
    return _run_executor(work, MODELO_WORK_VERIFY_OPERATION_DEFINITION_ID, executor, request)


def _check_clean(work: Any) -> Any:
    """Answer the earlier-filing figures, calculate and check a Modelo 130 cleanly; the check's result.

    A clean check needs the operator's answers to the earlier-filing figures
    and the earlier Renta the 130 reads present as filed AEAT evidence under
    the profile's own tax id.
    """
    from cadrumo.adapters.persistence.profile.tests.cross_period_seeding import seed_clean_cross_period_sources
    from cadrumo.application.modelo.edit_models import (
        ModeloBindingEditIntentV1,
        ModeloEditBindingAddressV1,
        ModeloEditBindingIntentKind,
    )
    from cadrumo.entrypoints.adapter_composition import build_filing_action_ports

    applied = work.apply(
        binding=tuple(
            ModeloBindingEditIntentV1(
                address=ModeloEditBindingAddressV1(binding_id=binding_id),
                kind=ModeloEditBindingIntentKind.SET_OVERRIDE_VALUE,
                value=value,
            )
            for binding_id, value in FILED_130_ANSWERS
        )
    )
    if applied.refusal is not None:
        raise SystemExit(f"the 130's answers were refused: {applied.refusal!r}")
    ports = build_filing_action_ports(bucket_id=work.work_unit.bucket_id, operation=work.operation)
    seed_clean_cross_period_sources(
        work.work_unit,
        work_unit_repository=ports.work_unit_repository,
        calculation_repository=ports.calculation_repository,
        filing_repository=ports.filing_repository,
        bucket_event_repository=ports.bucket_event_repository,
        operation=work.operation,
    )
    work.recalculate()
    checked = _verify(work)
    if not checked.granted_verificado_completo:
        raise SystemExit(f"the 130's check was not complete: {checked.completeness_status}")
    return checked


def _seed_income(work: Any) -> None:
    """Book the quarter's activity income in the profile's ledger, so the 130's boxes carry figures."""
    from cadrumo.adapters.persistence.profile.tests.m130_source_support import seed_m130_income_transaction

    seed_m130_income_transaction(amount=INCOME_130, filing_year=work.work_unit.filing_year, source_key="desktop")


def _record_filed(work: Any) -> None:
    """Check a Modelo 130 cleanly and record it as filed locally, through the registered executors.

    Nothing reaches the AEAT.
    """
    from cadrumo.adapters.persistence.storage.certificate_secret_backend import build_certificate_secret_backend
    from cadrumo.adapters.persistence.storage.operator_scope import build_operator_scope_ports
    from cadrumo.application.modelo.operation_definitions import (
        MODELO_WORK_FILE_OPERATION_DEFINITION_ID,
        ModeloWorkFileExecutor,
        resolve_active_workflow_profile,
    )
    from cadrumo.application.modelo.work_filing_contracts import ModeloWorkFileApproval, ModeloWorkFileRequest
    from cadrumo.entrypoints.adapter_composition import build_filing_action_ports

    checked = _check_clean(work)
    executor = ModeloWorkFileExecutor(
        profile_resolver=resolve_active_workflow_profile,
        operator_scope_ports=build_operator_scope_ports(),
        filing_action_ports_factory=build_filing_action_ports,
        certificate_secret_backend_factory=build_certificate_secret_backend,
    )
    request = ModeloWorkFileRequest(
        approval=ModeloWorkFileApproval(
            calculation_revision_id=checked.calculation_revision_id,
            verification_report_id=checked.verification_report_id,
        ),
        actor=ACTOR,
    )
    _run_executor(work, MODELO_WORK_FILE_OPERATION_DEFINITION_ID, executor, request)


def _import_receipt(work: Any) -> None:
    """Import the recorded 130's AEAT receipt through the external-evidence door, which confirms the filing.

    The receipt is a synthetic justificante stored under the profile's tax id
    with the recorded calculation's own figures, so it matches the pending
    local filing.
    """
    from cadrumo.adapters.persistence.profile.calculation_observations import CalculationObservationRepository
    from cadrumo.adapters.persistence.profile.tests.cross_period_seeding import SEEDED_SOURCE_TAX_ID
    from cadrumo.adapters.persistence.profile.tests.justificante_metadata import persist_justificante_metadata
    from cadrumo.application.modelo.external_import_actions import import_external_filing_evidence
    from cadrumo.domain.modelos.filing_record import ExternalEvidenceKind
    from cadrumo.entrypoints.adapter_composition import build_filing_action_ports

    modelo, period_code, _ = DECLARATIONS[0]
    unit = work.work_unit
    reference = f"CSV{modelo}{unit.filing_year}{period_code}DESKTOP"
    persist_justificante_metadata(
        reference,
        modelo=modelo,
        filing_year=unit.filing_year,
        period=period_code,
        captured_at=RECEIPT_AT,
        tax_id=SEEDED_SOURCE_TAX_ID,
    )
    ports = build_filing_action_ports(bucket_id=unit.bucket_id, operation=work.operation)
    import_external_filing_evidence(
        work_unit_id=work.work_unit_id,
        casilla_values={box: Decimal(value) for box, value in work.require_head().casilla_values.items()},
        evidence_kind=ExternalEvidenceKind.AEAT_JUSTIFICANTE_PDF,
        evidence_reference_id=reference,
        actor=ACTOR,
        work_unit_repository=ports.work_unit_repository,
        calculation_repository=ports.calculation_repository,
        filing_repository=ports.filing_repository,
        bucket_event_repository=ports.bucket_event_repository,
        observation_repository=CalculationObservationRepository(),
        expected_tax_id=SEEDED_SOURCE_TAX_ID,
        clock=RECEIPT_AT,
        operation=work.operation,
    )


def _export_file(work: Any, destination: Path) -> None:
    """Write the checked calculation's file for the AEAT to a local path through the registered export executor."""
    from cadrumo.adapters.outbound.calculation_summary_pdf.summary_container import write_calculation_summary_pdf
    from cadrumo.adapters.persistence.profile.review_package_signing import (
        build_review_package_signing_keypair_capability,
    )
    from cadrumo.application.modelo.operation_definitions import (
        MODELO_EXPORT_OPERATION_DEFINITION_ID,
        ModeloExportExecutor,
        resolve_active_workflow_profile,
    )
    from cadrumo.application.modelo.work_export_contracts import ModeloExportRequest
    from cadrumo.entrypoints.adapter_composition import build_modelo_export_ports

    executor = ModeloExportExecutor(
        profile_resolver=resolve_active_workflow_profile,
        export_ports_factory=build_modelo_export_ports,
        signing_keypair_capability_factory=build_review_package_signing_keypair_capability,
        calculation_summary_pdf_writer=write_calculation_summary_pdf,
    )
    request = ModeloExportRequest(
        calculation_revision_id=work.require_head().calculation_revision_id,
        output_path=str(destination),
        actor=ACTOR,
    )
    _run_executor(work, MODELO_EXPORT_OPERATION_DEFINITION_ID, executor, request)


def _income_categories_fact() -> Any:
    """The profile's IRPF income categories: economic activity, as the pinned registry names it.

    The filing calendar needs them to say which obligations apply.
    """
    from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority
    from cadrumo.domain.calculations.registry.irpf_income_categories import (
        irpf_income_category_actividad_economica_token,
    )
    from cadrumo.domain.user_profile.values import UserProfileFact

    with bundled_indexed_authority().operation() as operation:
        token = irpf_income_category_actividad_economica_token(authority=operation).value
    return UserProfileFact(path="taxpayer_type.irpf_income_categories", value=token)


def _observe_at_aeat(work: Any) -> None:
    """Store a Modelo 130 the AEAT holds for a quarter the profile has no declaration for.

    It is what reading the AEAT's register of filed declarations stores: a
    register row and its observation, through the profile's filed-declaration
    store. Nothing is read from or sent to the AEAT.
    """
    import hashlib

    from pydantic import AnyHttpUrl

    from cadrumo.adapters.outbound.aeat.sede.observation_store import FiledDeclaracionObservationStore
    from cadrumo.adapters.outbound.aeat.sede.schema import FiledDeclaracionArtefact, FiledDeclaracionObservation
    from cadrumo.core.config import Settings, load_settings
    from cadrumo.core.period import Period

    modelo, period_code = AEAT_ONLY
    year = work.work_unit.filing_year
    period = Period.from_year_and_code(year, period_code)
    aeat = Settings.external_constants().aeat
    body = f"{modelo}{year}{period_code}-register-row".encode()
    store = FiledDeclaracionObservationStore(load_settings().cadrumo_filed_declarations_dir)
    expediente = f"{year}1001{modelo}DESKTOPA"
    artefact = store.persist_artefact(
        (modelo, year, period, expediente),
        FiledDeclaracionArtefact(
            kind="register_row",
            source_url=AnyHttpUrl(f"{aeat.domains.www6}{aeat.sede_paths.declarations_listing}"),
            content_type="text/plain",
            byte_count=len(body),
            sha256=hashlib.sha256(body).hexdigest(),
            captured_at=AEAT_SEEN_AT,
        ),
        body,
    )
    store.persist_observation(
        FiledDeclaracionObservation(
            modelo=modelo,
            ejercicio=year,
            period=period,
            expediente_id=expediente,
            status="ALTA",
            presented_at=AEAT_PRESENTED_AT,
            authenticated_identity=MAIN_TAX_ID,
            artefacts=(artefact,),
            casillas=(),
            extraction_coverage={"register_row": 1.0},
            registry_snapshot_ref=work.operation.snapshot(modelo, filing_year=year, period=period_code).snapshot_ref,
        )
    )


def _write_list(directory: Path, work: Any, name: str) -> None:
    """Write the declarations list of the work's profile in every language, read through the list executor."""
    from cadrumo.application.modelo.declarations_list_operation import (
        MODELO_DECLARATIONS_LIST_OPERATION_DEFINITION_ID,
        ModeloDeclarationsListExecutor,
        ModeloDeclarationsListRequest,
    )
    from cadrumo.core.external_constants import OutputLanguage
    from cadrumo.core.operations import profile_operation_subject
    from cadrumo.entrypoints.workbench_generation_composition import compose_secure_declaration_list_reader

    bucket_id = work.work_unit.bucket_id
    lister = ModeloDeclarationsListExecutor(
        lambda profile_id, operation: compose_secure_declaration_list_reader(profile_id=profile_id, operation=operation)
    )
    for language in LANGUAGES:
        listed = _run_executor(
            work,
            MODELO_DECLARATIONS_LIST_OPERATION_DEFINITION_ID,
            lister,
            ModeloDeclarationsListRequest(profile_id=UUID(bucket_id), output_language=OutputLanguage(language)),
            subject_ref=profile_operation_subject(bucket_id),
        )
        _write(directory, f"{name}-{language}.json", listed)


def write_envelopes(directory: Path) -> None:
    """Read every envelope the scenario host answers through the application's read path."""
    from cadrumo.adapters.persistence.profile.tests.cross_period_seeding import SEEDED_SOURCE_TAX_ID
    from cadrumo.application.modelo.edit_models import ModeloEditAdmittedV1
    from cadrumo.domain.user_profile.values import UserProfileFact

    directory.mkdir(parents=True, exist_ok=True)
    income = (_income_categories_fact(),)
    with tempfile.TemporaryDirectory() as tmp, _seeded(Path(tmp), facts=income) as first:
        works = {DECLARATIONS[0][0]: first}
        for modelo, period_code, _ in DECLARATIONS[1:]:
            works[modelo] = _other_declaration(first, modelo, period_code)
        for modelo, _, calculated in DECLARATIONS:
            if calculated:
                works[modelo].recalculate()
        for modelo, period_code, _ in DECLARATIONS:
            _write_form(directory, works[modelo], f"modelo-{modelo}-{period_code}", with_help=True)
        _observe_at_aeat(first)
        _write_list(directory, first, "declarations")
        admission = first.admit()
        if not isinstance(admission, ModeloEditAdmittedV1):
            raise SystemExit(f"modelo {first.work_unit.modelo} was refused edit admission")
        _write(
            directory, "preflight-130.json", _preflight(first, admission.baseline, (("06", "1.234,56"), ("01", "doce")))
        )
        _write(directory, "renew-130.json", _renew(first, admission.baseline))
        # Checked after everything above was read, so those envelopes stay unchecked.
        _verify(first)
        _write_form(directory, first, "modelo-130-1T-checked")
    # Its own profile: recording needs the earlier Renta filed under the profile's tax id.
    facts = (*income, UserProfileFact(path="identity.tax_id", value=SEEDED_SOURCE_TAX_ID))
    with tempfile.TemporaryDirectory() as tmp, _seeded(Path(tmp), facts=facts) as filed:
        _seed_income(filed)
        _record_filed(filed)
        _write_form(directory, filed, "modelo-130-1T-filed")
        # Nothing was ever read from the AEAT in this profile, so its list is incomplete.
        _write_list(directory, filed, "declarations-incomplete")
        _import_receipt(filed)
        _write_form(directory, filed, "modelo-130-1T-receipt")
    # Its own profile: the file for the AEAT is written, then the declaration changes and is checked again.
    with tempfile.TemporaryDirectory() as tmp, _seeded(Path(tmp), facts=facts) as stale:
        _check_clean(stale)
        _export_file(stale, Path(tmp) / "modelo-130.txt")
        _seed_income(stale)
        stale.recalculate()
        _verify(stale)
        _write_form(directory, stale, "modelo-130-1T-stale")


# -- check --------------------------------------------------------------------


def _fixture_models() -> list[tuple[str, type[BaseModel]]]:
    from cadrumo.application.modelo.declarations_list_operation import ModeloDeclarationsListProjectionV1
    from cadrumo.application.modelo.workbench_operations import (
        ModeloCasillaHelpProjectionV1,
        ModeloEditPreflightProjectionV1,
        ModeloEditRenewalProjectionV1,
    )
    from cadrumo.application.modelo.workbench_projection import ModeloWorkbenchFormProjectionV1

    return [
        ("modelo-*.json", ModeloWorkbenchFormProjectionV1),
        ("help-*.json", ModeloCasillaHelpProjectionV1),
        ("declarations-*.json", ModeloDeclarationsListProjectionV1),
        ("preflight-*.json", ModeloEditPreflightProjectionV1),
        ("renew-*.json", ModeloEditRenewalProjectionV1),
    ]


def validate() -> int:
    """Whether the host's admitted list and every stored envelope still match the registered models."""
    failures: list[str] = []
    registered, admitted = definitions(), admitted_by_host()
    if registered != admitted:
        failures.append(
            "the host's admitted list differs from the registered modelo family: "
            f"unadmitted {sorted(set(registered) - set(admitted))}, "
            f"unregistered {sorted(set(admitted) - set(registered))}"
        )
    for pattern, model in _fixture_models():
        paths = sorted(FIXTURES.glob(pattern))
        if not paths:
            failures.append(f"no fixture matches {pattern}")
        for path in paths:
            try:
                model.model_validate_json(path.read_bytes())
            except ValueError as invalid:
                failures.append(f"{path.name} no longer validates as {model.__name__}: {str(invalid)[:200]}")
    sys.stderr.writelines(f"{failure}\n" for failure in failures)
    return 1 if failures else 0


def main() -> int:
    """Run one step for scripts/modelo-fixtures.mjs."""
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("step", choices=("contract", "envelopes", "validate"))
    parser.add_argument("directory", nargs="?", type=Path, default=FIXTURES, help="Where `envelopes` writes.")
    args = parser.parse_args()
    if args.step == "contract":
        sys.stdout.write(render_contract())
        return 0
    if args.step == "envelopes":
        write_envelopes(args.directory)
        return 0
    return validate()


if __name__ == "__main__":
    sys.exit(main())

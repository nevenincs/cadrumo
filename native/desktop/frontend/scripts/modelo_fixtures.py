"""Produce the desktop's Modelo wire types and its scenario envelopes from the Python models.

``src/shell/modeloContract.ts`` is generated from the JSON schema of every
request and result the desktop's admitted ``modelo.*`` definitions register,
plus the edit operator input the financial body carries.
``src/shell/relayBounds.ts`` is generated from the host's relay bounds, as the
Rust sources state them. The envelopes under
``src/dev/fixtures/modelo/`` are read through the application's own read path
for a synthetic taxpayer in a throwaway profile over the published authority.

``scripts/modelo-fixtures.mjs`` drives this module and formats what it writes;
run that, not this. ``contract`` writes the unformatted module to standard
output; ``bounds`` writes the unformatted relay bounds module; ``envelopes``
writes the envelopes, stored compactly and the Modelo 100 forms as patches;
``pack`` stores the envelopes already on disk that way; ``validate`` fails when the host's admitted list differs
from the registered family or a stored envelope no longer validates against
its model. The envelopes carry the day they were
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
from collections.abc import AsyncGenerator, Generator, Iterable, Iterator, Mapping
from contextlib import asynccontextmanager, contextmanager, nullcontext
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from functools import cache
from pathlib import Path
from typing import Any, cast
from uuid import UUID

from dev.temporary_output import prepare_temp_root
from pydantic import BaseModel
from pydantic.json_schema import models_json_schema

from cadrumo.application.modelo.amendment_context_operation import ModeloWorkAmendmentContextProjection
from cadrumo.application.operations.registry import OperationRegistry
from cadrumo.core.operations import OperationEffect
from cadrumo.domain.calculations.registry.tests.authored_editions import newest_authored_edition
from cadrumo.entrypoints.operation_composition import build_production_operation_registry

FRONTEND = Path(__file__).resolve().parents[1]
FIXTURES = FRONTEND / "src" / "dev" / "fixtures" / "modelo"

#: The host's closed list of admitted definitions, which the generated mirror is pinned to.
ADMITTED = FRONTEND.parent / "src-tauri" / "src" / "shell" / "modelo" / "admitted.rs"
#: The host's modelo shell module, whose result path keys say what the window is shown of a file's place.
MODELO_SHELL = ADMITTED.with_name("mod.rs")
#: What the host records about each admitted definition, generated from the shipped contracts.
HOST_FACTS = ADMITTED.with_name("relay_contracts.json")
#: The host's relay and held session, whose bounds the window keeps to, and where their constants come from.
RELAY_SOURCES: tuple[Path, ...] = (
    FRONTEND.parent / "src-tauri" / "src" / "shell" / "relay.rs",
    FRONTEND.parent / "src-tauri" / "src" / "agent" / "person.rs",
    FRONTEND.parents[1] / "application" / "src" / "person_operations.rs",
    FRONTEND.parents[1] / "application" / "src" / "person_operations" / "protocol.rs",
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
#: The earlier Renta's activity income, which a clean check reads from that Renta as filed rather than as an answer.
FILED_RENTA_BINDING = "irpf.previous_year_economic_activity_net_income"
#: What the operator answers for the cleanly checked 130: the earlier-filing figures no filed source states.
#: An answer differing from a filed source's figure would block the check until it was resolved.
CLEAN_130_ANSWERS: tuple[tuple[str, str], ...] = tuple(
    answer for answer in FILED_130_ANSWERS if answer[0] != FILED_RENTA_BINDING
)
#: The quarter's activity income booked for the calculated-only 130.
INCOME_130 = Decimal("12000.00")
#: The boxes whose help card the envelopes carry, by modelo.
#: When the synthetic AEAT receipt of the filed 130 is imported.
RECEIPT_AT = datetime(2026, 4, 21, 9, 30, tzinfo=UTC)
#: The quarter the AEAT holds a Modelo 130 for that the profile has no declaration of, and when it was filed and seen.
AEAT_ONLY = ("130", "2T")
AEAT_PRESENTED_AT = datetime(2026, 7, 14, 11, 0, tzinfo=UTC)
AEAT_SEEN_AT = datetime(2026, 7, 15, 9, 0, tzinfo=UTC)
#: The seeded profile's tax id, as the modelo-ready baseline states it.
MAIN_TAX_ID = "12345678Z"
#: The value the edit scenarios type over a Modelo 130 box, as the desktop stages it.
EDIT_130: tuple[tuple[str, str], ...] = (("06", "1234.56"),)
#: The box and figure the correction of the recorded 130 states, as the filer types it.
CORRECTED_130 = ("06", "150.00")
#: The Modelo 303 box the edit scenarios type over, as the filer types it and as the desktop stages it.
TYPED_303: tuple[tuple[str, str], ...] = (("42", "1234.56"),)
EDIT_303: tuple[tuple[str, str], ...] = (("42", "1234.56"),)
#: The changes the filer stages on the rebase scenario's earlier read: a clear, and two typed values.
REBASE_STAGED: tuple[tuple[str, str], ...] = (("06", "clear"), ("16", "set"), ("18", "set"))
#: The typed values the filer stages there, as the desktop sends them.
REBASE_TYPED: tuple[tuple[str, str], ...] = (("16", "250"), ("18", "75"))
#: Boxes 16 and 18 admit scalar entries; the activity's source-fed boxes 08 and 10 do not.
#: How the declaration moves under them: box 06's typed value is taken back and a figure typed into box 16.
REBASE_RESTORED: tuple[str, ...] = ("06",)
REBASE_MOVE: tuple[tuple[str, str], ...] = (("16", "500"),)
#: How it moves once more, after the window read it again, and again after the next read.
REBASE_MOVE_AGAIN: tuple[tuple[str, str], ...] = (("16", "40"),)
REBASE_MOVE_ONCE_MORE: tuple[tuple[str, str], ...] = (("18", "30"),)
#: What the filer types into the first-quarter 130, as typed, and an entry over a box that takes none.
TYPED_130: tuple[tuple[str, str], ...] = (("06", "1234.56"),)
#: That figure as each language's filer types it; the window's own language reads it.
TYPED_FIGURE: dict[str, dict[str, str]] = {
    "1234.56": {"en": "1,234.56", "es": "1.234,56", "ca": "1.234,56", "hu": "1 234,56"},
}
UNWRITABLE_130: tuple[str, str] = ("01", "doce")
#: The change the window holds once that value is staged.
STAGED_130: tuple[tuple[str, str], ...] = (("06", "set"),)
STAGED_303: tuple[tuple[str, str], ...] = (("42", "set"),)
#: The entries the rebase scenario types, as typed.
REBASE_TYPED_ENTRIES: tuple[tuple[str, str], ...] = (("16", "250"), ("18", "75"))
#: The declaration whose apply waits on filings this profile does not hold.
PREREQUISITE_130 = ("130", "3T")
#: A declaration whose file design carries no completeness manifest, and which checks cleanly when empty.
UNVERIFIED_EXPORT = ("165", "0A")
#: An entry the typed-entry path cannot read as a figure.
UNREADABLE_ENTRY = "doce"
#: Why the correction is made, as the filer says it.
CORRECTION_REASON = "A deductible expense was left out."
#: A synthetic AEAT justificante for a Modelo 130 of the first quarter of 2026.
JUSTIFICANTE_130 = ("tests", "fixtures", "justificantes", "modelo_130_2026Q1.pdf")
HELP_BOXES: Mapping[str, tuple[str, ...]] = {
    "130": ("01", "03", "07", "19"),
    "303": ("27", "71"),
    "100": ("0596", "0670"),
}

#: The tax year and period of the Renta the envelopes read: the first exercise of the newest edition the registry
#: authors, so the scenarios follow the registry when an edition is authored.
RENTA_YEAR = newest_authored_edition("100")
RENTA_PERIOD = "0A"
#: What the filer answers for that Renta: the earlier year's negative general base, the negative general base
#: still pending at the start of each of the three years before, and whether direct estimation is normal. The
#: calculation refuses without all of them.
RENTA_ANSWERS: tuple[tuple[str, str], ...] = (
    ("renta-base-liquidable-negativa-general-anterior", "0"),
    ("renta-base-liquidable-negativa-general-em4-pendiente-inicio", "0"),
    ("renta-base-liquidable-negativa-general-em3-pendiente-inicio", "0"),
    ("renta-base-liquidable-negativa-general-em2-pendiente-inicio", "0"),
    ("renta-modelo-100-estimacion-directa-es-normal", "1"),
)
#: The boxes a salaried filer states: the cash remuneration and the Social Security contributions, as typed.
RENTA_SALARY_BOXES: tuple[str, str] = ("0003", "0013")
#: A synthetic payer whose withholding certificate the register holds.
RENTA_PAYER_TAX_ID = "B12345674"
#: The quarter whose calculated Modelo 130 a projected filer holds, and the region the filers' profiles state as their
#: tax residence, which the projection takes when it is not named.
RENTA_QUARTER = "1T"
RENTA_CCAA = "madrid"
#: A day within the Renta's filing period, which closes on 30 June of the year after.
RENTA_FILING_PERIOD_DAY = datetime(RENTA_YEAR + 1, 5, 20, 9, 0, tzinfo=UTC)


# -- wire types ---------------------------------------------------------------


def definitions() -> tuple[str, ...]:
    """Every registered ``modelo.*`` definition: the family the host admits whole."""
    contracts = build_production_operation_registry().public_contract_set.definitions
    return tuple(sorted(item.definition_id for item in contracts if item.definition_id.startswith("modelo.")))


def host_operations() -> dict[str, Any]:
    """What the host records about each admitted definition: its subject, financial body and file fields."""
    return json.loads(HOST_FACTS.read_text("utf-8"))["operations"]


_RUST_CONSTANT = re.compile(r"(?:pub(?:\([a-z]+\))? )?const ([A-Z_][A-Z0-9_]*): usize =\s*([^;]+);")


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
        raise SystemExit(f"the relay's payload bound is no longer a plain constant expression: {expression!r}")

    # A constant another module defines is named by its path; its name alone resolves it.
    unqualified = re.sub(r"\b(?:[a-z_][a-z0-9_]*::)+", "", expression)
    return value(ast.parse(_digits(unqualified), mode="eval").body)


def _digits(expression: str) -> str:
    """Drop Rust digit separators inside number literals only, keeping names whole."""
    return re.sub(r"(?<![A-Za-z_])(\d[\d_]*)", lambda found: found.group(1).replace("_", ""), expression)


def relay_bound(name: str) -> int:
    """One of the host's relay bounds, evaluated from the Rust sources that state it."""
    constants: dict[str, str] = {}
    for source in RELAY_SOURCES:
        for constant, expression in _RUST_CONSTANT.findall(source.read_text("utf-8")):
            # rustfmt wraps a long expression over lines, which Python cannot parse as one.
            constants.setdefault(constant, " ".join(expression.split()))
    if name not in constants:
        raise SystemExit(f"no relay source declares {name}")
    return _usize(constants[name], constants)


_BOUNDS_HEADER = """\
// Generated by scripts/modelo_fixtures.py from the host's Rust relay sources;
// do not edit. Regenerate with `node scripts/modelo-fixtures.mjs --contract`;
// `--check` fails when it is stale.
"""


def render_bounds() -> str:
    """The generated relay bounds module, before the frontend's formatter writes it."""
    return "\n".join(
        (
            _BOUNDS_HEADER,
            "/** The longest payload or edit body, in bytes of compact JSON, the host\n"
            " * sends to the relay: the document the relay carries, less a margin for\n"
            " * number spellings. A longer one is refused before anything is sent; the\n"
            " * page splits it. */",
            f"export const RELAY_PAYLOAD_LIMIT = {relay_bound('PAYLOAD_LIMIT')};",
            "",
            "/** The longest request, in bytes, the host's held session takes: the\n"
            " * relay's document and one runtime frame around it. */",
            f"export const RELAY_REQUEST_LIMIT = {relay_bound('REQUEST_LIMIT')};",
            "",
        )
    )


def _constant_list(doc: str, name: str, items: Iterable[str]) -> str:
    values = "\n".join(f"  {_literal(item)}," for item in items)
    return f"/** {doc} */\nexport const {name} = [\n{values}\n] as const;"


def admitted_by_host() -> tuple[str, ...]:
    """The ids of the host's closed list, as its Rust constant spells them."""
    table = ADMITTED.read_text("utf-8").split("const ADMITTED", 1)[1].split("];", 1)[0]
    return tuple(sorted(str(found) for found in re.findall(r'\(\s*"(modelo\.[^"]+)",', table)))


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
def _seeded(tmp: Path, *, facts: tuple[Any, ...] = ()) -> Generator[Any]:
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
    from cadrumo.entrypoints.adapter_composition_work_ports import build_work_lifecycle_ports
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
    from cadrumo.entrypoints.adapter_composition_work_ports import build_calculation_action_ports

    ports = build_calculation_action_ports(bucket_id=bucket_id, operation=operation)
    return ModeloWorkbenchReadPorts(
        work_units=ports.work_unit_repository,
        calculations=ports.calculation_repository,
        verifications=VerificationReportCatalogueRepository(bucket_id=bucket_id),
        bucket_events=ports.bucket_event_repository,
        filings=ports.filing_repository,
        credit_resolutions=ports.credit_resolution_reader,
    )


def _write(directory: Path, name: str, model: BaseModel) -> None:
    """Write an envelope as the host hands it to the window, with every file's place reduced to its name."""
    shown = _host_view(json.loads(model.model_dump_json()), _result_path_keys(), _FILE_FOLDERS)
    text = json.dumps(shown, ensure_ascii=False, separators=(",", ":"))
    (directory / name).write_text(text, "utf-8", newline="\n")
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
    async def irreversible_section(self) -> AsyncGenerator[None]:
        yield

    async def phase(self, phase_code: str) -> None:
        del phase_code

    async def effect(self, effect: object) -> None:
        del effect

    async def put(self, operand: BaseModel, *, written_at: object) -> str:
        del written_at
        self.results.append(operand)
        return "0" * 64


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
    from cadrumo.application.modelo.operation_definitions import ModeloWorkVerifyExecutor
    from cadrumo.application.modelo.operation_shared import (
        MODELO_WORK_VERIFY_OPERATION_DEFINITION_ID,
        resolve_active_workflow_profile,
    )
    from cadrumo.application.modelo.work_verification_contracts import ModeloWorkVerifyRequest
    from cadrumo.entrypoints.adapter_composition_work_ports import build_verification_repository_bundle

    executor = ModeloWorkVerifyExecutor(
        certificate_secret_backend_factory=build_certificate_secret_backend,
        profile_resolver=resolve_active_workflow_profile,
        operator_scope_ports=build_operator_scope_ports(),
        verification_repository_bundle_factory=build_verification_repository_bundle,
    )
    request = ModeloWorkVerifyRequest(calculation_revision_id=work.require_head().calculation_revision_id, actor=ACTOR)
    return _run_executor(work, MODELO_WORK_VERIFY_OPERATION_DEFINITION_ID, executor, request)


def _check_refused_on_divergence(work: Any) -> None:
    """Check a declaration whose typed box replaced a different figure its source resolved; the check refuses.

    The typed value is used by the calculation, but a filed figure resting on a
    value that replaced a different source figure is withheld until the sources
    agree, so the form read afterwards carries the open divergence.
    """
    from cadrumo.application.modelo.calculation_note_gate import ModeloCalculationBlockedError

    try:
        _verify(work)
    except ModeloCalculationBlockedError as refused:
        reasons = str((refused.context or {}).get("reasons", "")).split(",")
        if "precedence_tier_divergence" not in reasons:
            raise
        return
    raise SystemExit("the check over a typed box that replaced a different source figure was not refused")


def _check_clean(work: Any) -> Any:
    """Answer the earlier-filing figures, calculate and check a Modelo 130 cleanly; the check's result.

    A clean check needs the operator's answers to the earlier-filing figures
    and the earlier Renta the 130 reads present as filed AEAT evidence under
    the profile's own tax id. That Renta's activity income is read from it, not
    answered: an answer differing from the filed figure is a divergence the
    check refuses. The profile books no activity in its ledger:
    the bank-dated income, expense and retención boxes are capped below
    filing grade, so only their proven zero lets the check pass.
    """
    from cadrumo.adapters.persistence.profile.tests.cross_period_seeding import seed_clean_cross_period_sources
    from cadrumo.application.modelo.edit_models import (
        ModeloBindingEditIntentV1,
        ModeloEditBindingAddressV1,
        ModeloEditBindingIntentKind,
    )
    from cadrumo.entrypoints.adapter_composition_work_ports import build_filing_action_ports

    applied = work.apply(
        binding=tuple(
            ModeloBindingEditIntentV1(
                address=ModeloEditBindingAddressV1(binding_id=binding_id),
                kind=ModeloEditBindingIntentKind.SET_OVERRIDE_VALUE,
                value=value,
            )
            for binding_id, value in CLEAN_130_ANSWERS
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
    """Book the quarter's activity income in the profile's ledger, so the 130's boxes carry figures.

    The boxes it feeds are capped below filing grade: only a profile that is
    calculated and never checked, exported or filed may hold it.
    """
    from cadrumo.adapters.persistence.profile.tests.m130_source_support import seed_m130_income_transaction

    seed_m130_income_transaction(amount=INCOME_130, filing_year=work.work_unit.filing_year, source_key="desktop")


def _record_filed(work: Any) -> BaseModel:
    """Check a Modelo 130 cleanly and record it as filed locally, through the registered executors.

    Nothing reaches the AEAT.
    """
    from cadrumo.adapters.persistence.storage.certificate_secret_backend import build_certificate_secret_backend
    from cadrumo.adapters.persistence.storage.operator_scope import build_operator_scope_ports
    from cadrumo.application.modelo.operation_definitions import ModeloWorkFileExecutor
    from cadrumo.application.modelo.operation_shared import (
        MODELO_WORK_FILE_OPERATION_DEFINITION_ID,
        resolve_active_workflow_profile,
    )
    from cadrumo.application.modelo.work_filing_contracts import ModeloWorkFileApproval, ModeloWorkFileRequest
    from cadrumo.entrypoints.adapter_composition_work_ports import build_filing_action_ports

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
    return _run_executor(work, MODELO_WORK_FILE_OPERATION_DEFINITION_ID, executor, request)


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
    from cadrumo.entrypoints.adapter_composition_work_ports import build_filing_action_ports

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


def _export_file(work: Any, destination: Path) -> BaseModel:
    """Write the checked calculation's file for the AEAT to a local path through the registered export executor."""
    from cadrumo.adapters.outbound.calculation_summary_pdf.summary_container import write_calculation_summary_pdf
    from cadrumo.adapters.persistence.profile.review_package_signing import (
        build_review_package_signing_keypair_capability,
    )
    from cadrumo.application.modelo.export_operation import ModeloExportExecutor
    from cadrumo.application.modelo.operation_shared import (
        MODELO_EXPORT_OPERATION_DEFINITION_ID,
        resolve_active_workflow_profile,
    )
    from cadrumo.application.modelo.work_export_contracts import ModeloExportRequest
    from cadrumo.entrypoints.adapter_composition_ports import build_modelo_export_ports

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
    _FILE_FOLDERS.append(str(destination.parent))
    settled = _run_executor(work, MODELO_EXPORT_OPERATION_DEFINITION_ID, executor, request)
    return _published(MODELO_EXPORT_OPERATION_DEFINITION_ID, settled, work.work_unit_id)


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
    from cadrumo.core.config import Settings
    from cadrumo.core.period import Period
    from cadrumo.core.storage_taxonomy import StorageCategory
    from cadrumo.core.storage_taxonomy_locations import storage_path

    modelo, period_code = AEAT_ONLY
    year = work.work_unit.filing_year
    period = Period.from_year_and_code(year, period_code)
    aeat = Settings.external_constants().aeat
    body = f"{modelo}{year}{period_code}-register-row".encode()
    store = FiledDeclaracionObservationStore(storage_path(StorageCategory.FILED_DECLARATIONS))
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


# -- the Renta ------------------------------------------------------------------
#
# The 2025 Modelo 100 of synthetic filers, each its own profile, calculated with the two answers the calculation
# refuses without. Nothing is cut: every form is read whole, and a box the application cannot work out stays
# unresolved in it. The declarations are data: a change to what a filer states, or a new filer, is one line here.


@dataclass(frozen=True, slots=True)
class RentaFiler:
    """One synthetic filer of the 2025 Renta and what the profile holds for the declaration."""

    #: The envelope's name after ``modelo-100-0A``; empty for the declaration the scenarios open.
    envelope: str
    #: The IRPF income categories the profile declares, comma separated as the setup answer states them.
    categories: str
    #: The cash remuneration and the Social Security contributions typed into the form, where the filer is salaried.
    salary: tuple[str, str] | None = None
    #: The withholding the payer's certificate states and the register holds, where there is a certificate.
    certified: Decimal | None = None
    #: Activity income booked in the profile's ledger for the year.
    ledger_income: Decimal | None = None
    #: Whether the profile also holds the year's calculated first-quarter Modelo 130, which the projection of the
    #: annual return from the quarters reads; the projection is read for the filer only then.
    quarter_130: bool = False
    #: The day the filer's profile is read on, where it matters: the filing period of the return runs to the end
    #: of June of the year after, and a result to pay is offered in two instalments only within it. ``None`` reads
    #: on today's date.
    read_on: datetime | None = None
    #: What the profile states of the household, by name (see ``_household_facts``).
    household: str = "single"
    #: Whether the declaration is calculated; the comparison of the filing modes is refused for one that is not.
    calculated: bool = True
    #: The filing modes compared, recorded for this filer when it is named: the comparison is read in every
    #: language, and a refusal as a stopped executor's detail is recorded.
    compared: bool = False
    #: Whether the comparison is also recorded for the states the filer's own income does not reach.
    compared_states: bool = False
    #: The filing year of the declaration; the Renta the scenarios open is ``RENTA_YEAR``'s.
    year: int = RENTA_YEAR
    #: The income classes the filer attests no payer withheld on, as the register records the attestation: a class
    #: with neither a certificate nor an attestation stays unresolved, which is not the same as none.
    attested_none: tuple[str, ...] = ()


RENTA_FILERS: tuple[RentaFiler, ...] = (
    # Salaried, with income from savings and a capital gain declared, and no certificate in the register:
    # the three withholding credits and the totals that read them stay unresolved.
    RentaFiler("", "trabajo,capital_mobiliario,ganancias_patrimoniales", salary=("30000", "1900"), compared=True),
    # Salaried, one certificate in the register: a credit smaller than the tax, so the result is to pay.
    RentaFiler("pay", "trabajo", salary=("30000", "1900"), certified=Decimal("2000.00")),
    # The same income with a certificate stating more than the tax: the result is to refund.
    RentaFiler("refund", "trabajo", salary=("30000", "1900"), certified=Decimal("6000.00")),
    # Self-employed, with the year's activity income booked in the ledger.
    RentaFiler("activity", "actividad_economica", ledger_income=Decimal("40000.00")),
    # Salaried and self-employed, the year's first quarter calculated, and no certificate in the register: the
    # projection from the quarter names the employment credit and the totals that read it as unresolved.
    RentaFiler(
        "projected",
        "trabajo,actividad_economica",
        salary=("30000", "1900"),
        ledger_income=Decimal("40000.00"),
        quarter_130=True,
    ),
    # The same filer with a certificate in the register, and the attestation that no payer withheld on the rental
    # activity the register would otherwise leave unresolved: the projection resolves every credit.
    RentaFiler(
        "credited",
        "trabajo,actividad_economica",
        salary=("30000", "1900"),
        certified=Decimal("2000.00"),
        ledger_income=Decimal("40000.00"),
        quarter_130=True,
        attested_none=("arrendamiento_inmueble_urbano_actividad",),
    ),
    # The salaried filer with a certificate that leaves a result to pay, read within the filing period: the
    # result may be paid at once or in two instalments, and the split states both amounts as advisory.
    RentaFiler(
        "instalment",
        "trabajo",
        salary=("30000", "1900"),
        certified=Decimal("2000.00"),
        read_on=RENTA_FILING_PERIOD_DAY,
    ),
    # A married couple whose profile states the spouse, one certificate in the register: the filing modes can be
    # compared, and joint filing comes out lower.
    RentaFiler(
        "married",
        "trabajo",
        salary=("30000", "1900"),
        certified=Decimal("2000.00"),
        household="married",
        compared=True,
        compared_states=True,
    ),
    # The same couple with no certificate in the register: the credits the results read have no value, so the
    # comparison names those boxes instead of comparing.
    RentaFiler("uncredited", "trabajo", salary=("30000", "1900"), household="married", compared=True),
    # A married filer whose profile does not state the spouse.
    RentaFiler(
        "spouseless",
        "trabajo",
        salary=("30000", "1900"),
        certified=Decimal("2000.00"),
        household="married-no-spouse",
        compared=True,
    ),
    # A single filer with no child in the household, who has no family unit to file jointly.
    RentaFiler(
        "alone",
        "trabajo",
        salary=("30000", "1900"),
        certified=Decimal("2000.00"),
        household="alone",
        compared=True,
    ),
    # A married couple whose return was never calculated.
    RentaFiler("uncalculated", "trabajo", household="married", calculated=False, compared=True),
    # A single parent who has not said whether they live with the child's other parent: the joint reduction
    # depends on it, so the comparison names the box it leaves without a value.
    RentaFiler(
        "parent", "trabajo", salary=("30000", "1900"), certified=Decimal("2000.00"), household="parent", compared=True
    ),
    # The same parent stating that they do not live with the child's other parent: the comparison is made.
    RentaFiler(
        "parentapart",
        "trabajo",
        salary=("30000", "1900"),
        certified=Decimal("2000.00"),
        household="parent-apart",
        compared=True,
    ),
)


def renta_years() -> tuple[int, ...]:
    """The filing years the registry supports, which are the years whose Modelo 100 the product serves.

    The registry declares the span as bounds, and a year without an authored edition is projected from the nearest
    one, so the years are read from it and no list is kept here.
    """
    from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority

    with bundled_indexed_authority().operation() as operation:
        return tuple(operation.supported_filing_years().years)


def renta_year_filer(year: int) -> RentaFiler:
    """The married couple with a certificate in the register, whose Modelo 100 is the one of ``year``.

    Its form is read in every language, and its comparison and settlement as the application serves them for that
    year, so each year's own capability is what the envelopes state.
    """
    return RentaFiler(
        f"y{year}",
        "trabajo",
        salary=("30000", "1900"),
        certified=Decimal("2000.00"),
        household="married",
        compared=True,
        year=year,
    )


#: The tax id the profile states for a married filer's spouse.
RENTA_SPOUSE_TAX_ID = "98765432M"


def _household_facts(name: str) -> tuple[Any, ...]:
    """What the profile states of the taxpayer's household, by the name a filer gives it.

    ``single`` is one unmarried taxpayer who states nothing of a family situation. ``married`` is a married couple
    that states the spouse and the family situation; ``married-no-spouse`` leaves the spouse out. ``alone`` is an
    unmarried taxpayer who states a family situation with no child in the household. ``parent`` is an unmarried
    taxpayer with a minor child in the household who has not said whether they live with the child's other parent,
    and ``parent-apart`` is the same taxpayer stating that they do not.
    """
    from datetime import date

    from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority
    from cadrumo.domain.contribuyente.renta_codes import RentaDeclaracionType, RentaMaritalStatus
    from cadrumo.domain.user_profile.tests.general_regime_facts import RENTA_UNMARRIED_TAXPAYER_FACTS
    from cadrumo.domain.user_profile.values import UserProfileFact

    # The form codes the profile stores are the registry's own, read under a pinned authority.
    with bundled_indexed_authority().operation():
        married_code = RentaMaritalStatus.CASADO.code
        single_code = RentaMaritalStatus.SOLTERO.code
        individual_code = RentaDeclaracionType.INDIVIDUAL.code
    if name == "single":
        return RENTA_UNMARRIED_TAXPAYER_FACTS
    if name == "alone":
        stated = UserProfileFact(path="renta_family.situacion_familiar", value="soltero")
        return (*RENTA_UNMARRIED_TAXPAYER_FACTS, stated)
    married = (
        UserProfileFact(path="renta_taxpayer.birth_date", value=date(1980, 3, 15)),
        UserProfileFact(path="renta_taxpayer.marital_status", value=married_code),
        UserProfileFact(path="renta_taxpayer.marriage_full_year", value=True),
        UserProfileFact(path="renta_taxpayer.marriage_month_start", value=Decimal("1")),
        UserProfileFact(path="renta_taxpayer.marriage_month_end", value=Decimal("12")),
        UserProfileFact(path="renta_filing.declaration_type", value=individual_code),
        UserProfileFact(path="renta_family.situacion_familiar", value="casado"),
        UserProfileFact(path="renta_family.minor_children_in_unit", value=False),
    )
    if name == "married":
        return (*married, UserProfileFact(path="renta_spouse.tax_id", value=RENTA_SPOUSE_TAX_ID))
    if name == "married-no-spouse":
        return married
    if name in {"parent", "parent-apart"}:
        parent = (
            UserProfileFact(path="renta_taxpayer.birth_date", value=date(1980, 3, 15)),
            UserProfileFact(path="renta_taxpayer.marital_status", value=single_code),
            UserProfileFact(path="renta_filing.declaration_type", value=individual_code),
            UserProfileFact(path="renta_family.situacion_familiar", value="soltero"),
            UserProfileFact(path="renta_family.minor_children_in_unit", value=True),
        )
        if name == "parent":
            return parent
        return (*parent, UserProfileFact(path="renta_family.convive_con_otro_progenitor", value=False))
    raise SystemExit(f"no household is named {name}")


@contextmanager
def _renta_seeded(tmp: Path, filer: RentaFiler) -> Generator[Any]:
    """One synthetic profile whose first declaration is the filer's Modelo 100 of its year, not yet calculated."""
    from cadrumo.domain.user_profile.values import UserProfileFact
    from cadrumo.entrypoints.adapter_composition import profile_adapter_composition
    from cadrumo.entrypoints.tests.modelo_operator_work_storage import seeded_operator_work

    facts = (
        UserProfileFact(path="taxpayer_type.irpf_income_categories", value=filer.categories),
        UserProfileFact(path="tax_residence.ccaa", value=RENTA_CCAA),
        *_household_facts(filer.household),
    )
    with (
        profile_adapter_composition(),
        seeded_operator_work(
            tmp, modelo="100", filing_year=filer.year, period_code=RENTA_PERIOD, extra_facts=facts
        ) as work,
    ):
        yield work


def _record_certificate(work: Any, filer: RentaFiler) -> None:
    """Store the payer's certificate and the filer's attestations in the register, as its write door does."""
    from cadrumo.adapters.persistence.profile.tests.retencion_soportada_seed import (
        seed_absence_attestation,
        seed_payer_certificate,
    )
    from cadrumo.core.retencion_soportada import RetencionSoportadaClase

    for token in filer.attested_none:
        seed_absence_attestation(
            operation=work.operation, ejercicio=filer.year, income_class=RetencionSoportadaClase(token)
        )
    if filer.certified is None or filer.salary is None:
        return
    seed_payer_certificate(
        operation=work.operation,
        taxpayer_tax_id=MAIN_TAX_ID,
        ejercicio=filer.year,
        payer_tax_id=RENTA_PAYER_TAX_ID,
        income_class=RetencionSoportadaClase.TRABAJO,
        retencion=filer.certified,
        importe_integro_dinerario=Decimal(filer.salary[0]),
    )


def _calculate_renta(work: Any, filer: RentaFiler, *, borrador_snapshot_id: str | None = None) -> None:
    """Calculate the filer's declaration through the registered calculation, with the answers it refuses without.

    The filer starts from the answers the latest design asks. Another year's design asks others, which the
    calculation names one at a time as the binding it refuses without; the filer answers each as none, the way
    an operator answers a question the calculation puts, and the calculation is asked again.
    A draft imported earlier is replayed into the calculation when ``borrador_snapshot_id`` names it.
    """
    from cadrumo.application.modelo.work_missing_input import ModeloWorkMissingInputError

    answers = list(RENTA_ANSWERS)
    while True:
        try:
            _calculate_renta_with(work, filer, tuple(answers), borrador_snapshot_id=borrador_snapshot_id)
        except ModeloWorkMissingInputError as missing:
            if any(missing.binding_id == key for key, _ in answers):
                raise
            answers.append((missing.binding_id, "0"))
        else:
            return


def _calculate_renta_with(
    work: Any, filer: RentaFiler, answers: tuple[tuple[str, str], ...], *, borrador_snapshot_id: str | None
) -> None:
    """Calculate the filer's declaration once, answering the bindings in ``answers``."""
    from cadrumo.application.modelo.calculation_operation import ModeloWorkCalculateExecutor
    from cadrumo.application.modelo.calculation_request_fields import (
        ModeloCalculationInputFieldsV1,
        ModeloCalculationOverride,
    )
    from cadrumo.application.modelo.operation_shared import MODELO_WORK_CALCULATE_OPERATION_DEFINITION_ID
    from cadrumo.application.modelo.work_calculation_contracts import (
        ModeloWorkCalculateCallerContext,
        ModeloWorkCalculateRequest,
    )
    from cadrumo.application.operations.models import OperationIdentity, OperationRequest
    from cadrumo.entrypoints.adapter_composition_ports import build_attachment_store

    executor = ModeloWorkCalculateExecutor(
        calculation_action_ports_factory=lambda **_: work.ports,
        attachment_store_factory=build_attachment_store,
    )
    stated = zip(RENTA_SALARY_BOXES, filer.salary, strict=True) if filer.salary is not None else ()
    request = OperationRequest(
        definition_id=MODELO_WORK_CALCULATE_OPERATION_DEFINITION_ID,
        subject_ref=work.work_unit_id,
        payload=ModeloWorkCalculateRequest(
            work_unit_id=work.work_unit_id,
            actor=ACTOR,
            caller_context=ModeloWorkCalculateCallerContext.EXPLICIT,
            inputs=ModeloCalculationInputFieldsV1(
                binding_overrides=tuple(ModeloCalculationOverride(key=key, value=value) for key, value in answers),
                casilla_overrides=tuple(ModeloCalculationOverride(key=box, value=value) for box, value in stated),
                borrador_snapshot_id=borrador_snapshot_id,
            ),
        ),
    )
    identity = OperationIdentity(
        operation_id="e" * 64,
        definition_id=MODELO_WORK_CALCULATE_OPERATION_DEFINITION_ID,
        subject_ref=work.work_unit_id,
    )
    context = _ReadContext(identity=identity, authority_operation=work.operation)
    asyncio.run(executor.execute(request, cast(Any, context)))


def _answer_quarter(work: Any) -> None:
    """Calculate the first-quarter Modelo 130 with the answers to the earlier-filing figures it refuses without."""
    from cadrumo.application.modelo.edit_models import (
        ModeloBindingEditIntentV1,
        ModeloEditBindingAddressV1,
        ModeloEditBindingIntentKind,
    )

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
        raise SystemExit(f"the quarter's answers were refused: {applied.refusal!r}")
    work.recalculate()


def _write_projection(directory: Path, work: Any, name: str) -> None:
    """Read the projection of the filer's annual return from the quarters, as the application words it in each language.

    The application words the projection in the language it is run in, so each is run in its own.
    """
    from cadrumo.application.modelo.projection_operation import ModeloProjectOperationRequest
    from cadrumo.core.config import override_settings

    bucket_id = work.work_unit.bucket_id
    request = ModeloProjectOperationRequest(profile_id=UUID(bucket_id), year=RENTA_YEAR)
    for language in LANGUAGES:
        with override_settings(cadrumo_output_language=language):
            projected = _operate(work, "modelo.project", request, subject_ref=_profile_subject(work))
        _write(directory, f"{name}-{language}.json", projected)


def _write_projection_refusal(directory: Path, work: Any, name: str) -> None:
    """Record why the application refuses to project the profile as it stands, in each language.

    The refusal is the one the projection's executor raises when it is run for the profile, recorded as a stopped
    executor's detail is recorded, with the next step it serves for putting it right.
    """
    from cadrumo.application.modelo.projection_operation import ModeloProjectOperationRequest
    from cadrumo.application.operations.error_detail import build_operation_error_detail
    from cadrumo.core.config import override_settings

    request = ModeloProjectOperationRequest(profile_id=UUID(work.work_unit.bucket_id), year=RENTA_YEAR)
    for language in LANGUAGES:
        with override_settings(cadrumo_output_language=language):
            try:
                _operate(work, "modelo.project", request, subject_ref=_profile_subject(work))
            except Exception as refusal:
                detail = build_operation_error_detail(refusal)
            else:
                raise SystemExit(f"the profile for {name} was projected, not refused")
        if detail is None:
            raise SystemExit("the projection's refusal records no error detail")
        _write(directory, f"refusal-{name}-{language}.json", detail)


def _write_taxation_comparison(directory: Path, work: Any, name: str) -> None:
    """Read the comparison of joint and individual filing of the filer's declaration, in each language.

    The application words the comparison in the language it is run in, so each is run in its own. A comparison
    the application refuses is recorded as a stopped executor's detail is, with its served sentence.
    """
    from cadrumo.application.modelo.taxation_comparison import TaxationComparisonError
    from cadrumo.application.modelo.taxation_comparison_operation import ModeloTaxationComparisonRequest
    from cadrumo.application.operations.error_detail import build_operation_error_detail
    from cadrumo.core.config import override_settings

    request = ModeloTaxationComparisonRequest(profile_id=UUID(work.work_unit.bucket_id), work_unit_id=work.work_unit_id)
    for language in LANGUAGES:
        with override_settings(cadrumo_output_language=language):
            try:
                compared = _operate(work, "modelo.work.compare_taxation", request, subject_ref=_profile_subject(work))
            except TaxationComparisonError as refusal:
                detail = build_operation_error_detail(refusal)
                if detail is None:
                    raise SystemExit("the comparison's refusal records no error detail") from refusal
                _write(directory, f"refusal-compare-{name}-{language}.json", detail)
            else:
                _write(directory, f"compare-{name}-{language}.json", compared)


#: The salary and contributions of a household too small for either filing mode to owe tax on.
RENTA_SMALL_SALARY: tuple[str, str] = ("5000", "300")
#: What a comparison that recommends individual filing states, as amounts in euros: the joint result, the individual
#: one, and the cuota resultante of each. No household of these synthetic filers reaches it.
INDIVIDUAL_LOWER = ("2400.00", "2100.00", "3000.00", "2700.00")


#: The refusals of the comparison that no declaration of these synthetic profiles reaches: one on a form that
#: declares no filing mode, which no supported year's Modelo 100 is, one on a form the authority no longer selects,
#: and one on a calculation saved before the entries were recorded.
UNREACHED_COMPARISON_REFUSALS: tuple[str, ...] = ("not_declared", "revision_outdated", "entries_unknown")


def _write_unreached_comparison_refusals(directory: Path) -> None:
    """Record the comparison refusals the profiles above cannot reach, as the executor raises them, in each language.

    A form that declares no filing mode, a work unit made on an older revision, or a calculation saved before
    entries were recorded, cannot be made through the current application. The error is the one the comparison
    raises for it, recorded as a stopped executor's detail is, with its served sentence.
    """
    from cadrumo.application.modelo.taxation_comparison import TaxationComparisonError, TaxationComparisonRefusal
    from cadrumo.application.operations.error_detail import build_operation_error_detail
    from cadrumo.core.config import override_settings

    for refusal in UNREACHED_COMPARISON_REFUSALS:
        error = TaxationComparisonError(TaxationComparisonRefusal(refusal))
        for language in LANGUAGES:
            with override_settings(cadrumo_output_language=language):
                detail = build_operation_error_detail(error)
            if detail is None:
                raise SystemExit("the comparison's refusal records no error detail")
            _write(directory, f"refusal-compare-100-{RENTA_PERIOD}-{refusal.replace('_', '-')}-{language}.json", detail)


def _write_comparison_states(directory: Path, work: Any, filer: RentaFiler) -> None:
    """Record the comparison states the filer's own income does not reach, in each language.

    The same household is calculated again on an income too small for either mode to owe tax on, so the results do
    not differ, and read through the registered comparison. A comparison that recommends individual filing cannot be
    reached by the single-earner household the application models, so the real projection and its served words
    state one built from amounts: the application's own result, projected and worded as any comparison is.
    """
    from dataclasses import replace

    from cadrumo.application.modelo.taxation_comparison import (
        TaxationComparisonResult,
        TaxationRecommendation,
        TaxationRecommendationReason,
    )
    from cadrumo.application.modelo.taxation_comparison_operation import ModeloTaxationComparisonProjection
    from cadrumo.core.config import override_settings

    _calculate_renta(work, replace(filer, salary=RENTA_SMALL_SALARY))
    _write_taxation_comparison(directory, work, f"100-{RENTA_PERIOD}-{filer.envelope}-small")
    conjunta, individual, conjunta_cuota, individual_cuota = (Decimal(amount) for amount in INDIVIDUAL_LOWER)
    built = TaxationComparisonResult(
        filing_year=RENTA_YEAR,
        modelo="100",
        revision=str(RENTA_YEAR),
        conjunta_cuota_resultante=conjunta_cuota,
        individual_cuota_resultante=individual_cuota,
        conjunta_resultado=conjunta,
        individual_resultado=individual,
        delta_resultado=individual - conjunta,
        recommendation=TaxationRecommendation.INDIVIDUAL,
        recommendation_reason=TaxationRecommendationReason.INDIVIDUAL_LOWER_RESULT,
    )
    for language in LANGUAGES:
        with override_settings(cadrumo_output_language=language):
            projection = ModeloTaxationComparisonProjection.from_comparison(
                built, profile_id=UUID(work.work_unit.bucket_id), work_unit_id=work.work_unit_id
            )
        _write(directory, f"compare-100-{RENTA_PERIOD}-{filer.envelope}-individual-{language}.json", projection)


def _write_projection_steps(directory: Path) -> None:
    """Record the stops from a profile with no quarterly declaration to an estimate, as served.

    The profile is the projected filer's, with its income booked and no quarter yet. Its first quarter is created
    through the registered creation, which the first refusal's step names, and the refusal that follows names the
    declaration just created as the one to calculate. That is calculated through the registered calculation, with
    none of the answers about earlier filings it refuses without, and the estimate is then refused for want of a
    result the quarter does not yet hold: the refusal names the quarter's open boxes from its own form and serves
    the step that opens it. Each refusal is recorded as a stopped executor's detail is, in every language; the two
    results are recorded once.
    """
    from dataclasses import replace

    from cadrumo.adapters.persistence.profile.tests.m130_source_support import seed_m130_income_transaction
    from cadrumo.application.modelo.work_calculation_contracts import ModeloWorkCalculateRequest
    from cadrumo.application.modelo.work_create_operation import ModeloWorkCreateProjection, ModeloWorkCreateRequest
    from cadrumo.application.operations.public_period import PublicPeriod
    from cadrumo.core.time.clock import frozen_clock
    from cadrumo.entrypoints.tests.modelo_operator_work_storage import SEEDED_AT

    projected = next(filer for filer in RENTA_FILERS if filer.envelope == "projected")
    filer = replace(projected, quarter_130=False)
    if filer.ledger_income is None:
        raise SystemExit("the filer of the estimate's steps books no income")
    with (
        tempfile.TemporaryDirectory(dir=prepare_temp_root()) as tmp,
        frozen_clock(SEEDED_AT),
        _renta_seeded(Path(tmp), filer) as work,
    ):
        seed_m130_income_transaction(amount=filer.ledger_income, filing_year=RENTA_YEAR, source_key="synthetic-ledger")
        created = _operate(
            work,
            "modelo.work.create",
            ModeloWorkCreateRequest(
                profile_id=UUID(work.work_unit.bucket_id),
                modelo="130",
                period=PublicPeriod(filing_year=RENTA_YEAR, code=RENTA_QUARTER),
                actor=ACTOR,
            ),
            subject_ref=_profile_subject(work),
        )
        if not isinstance(created, ModeloWorkCreateProjection) or created.outcome.kind != "success":
            raise SystemExit("the first quarter's declaration was not created")
        _write(directory, "create-130.json", created)
        _write_projection_refusal(directory, work, "project-no-calculation")
        quarter = created.outcome.unit.work_unit_id
        _write(
            directory,
            "calculate-130.json",
            _operate(
                work,
                "modelo.work.calculate",
                ModeloWorkCalculateRequest(work_unit_id=quarter, actor=ACTOR),
                subject_ref=quarter,
            ),
        )
        _write_projection_refusal(directory, work, "project-quarter-incomplete")


def _write_renta_filer(directory: Path, filer: RentaFiler, *, first: bool) -> None:
    """Read one filer's 2025 Modelo 100 in every language, with the projection and settlement states it has.

    The first filer is also the one whose declarations list, help cards and refused projection are read.
    """
    from cadrumo.adapters.persistence.profile.tests.m130_source_support import seed_m130_income_transaction
    from cadrumo.core.time.clock import frozen_clock

    with (
        tempfile.TemporaryDirectory(dir=prepare_temp_root()) as tmp,
        frozen_clock(filer.read_on) if filer.read_on is not None else nullcontext(),
        _renta_seeded(Path(tmp), filer) as work,
    ):
        _record_certificate(work, filer)
        if filer.ledger_income is not None:
            seed_m130_income_transaction(
                amount=filer.ledger_income, filing_year=filer.year, source_key="synthetic-ledger"
            )
        if filer.quarter_130:
            _answer_quarter(_other_declaration(work, "130", RENTA_QUARTER))
        if filer.calculated:
            _calculate_renta(work, filer)
        suffix = f"-{filer.envelope}" if filer.envelope else ""
        _write_form(directory, work, f"modelo-100-{RENTA_PERIOD}{suffix}", with_help=first)
        if filer.compared:
            _write_taxation_comparison(directory, work, f"100-{RENTA_PERIOD}{suffix}")
        if filer.compared_states:
            _write_comparison_states(directory, work, filer)
        if filer.quarter_130:
            _write_projection(directory, work, f"project-100-{RENTA_PERIOD}{suffix}")
        if first:
            _write_list(directory, work, "declarations-renta")
            _write_projection_refusal(directory, work, "project-no-quarters")
            _write_settlement_states(directory, work, SETTLEMENT_STATES)
        elif filer.year != RENTA_YEAR:
            _write_settlement_states(directory, work, SETTLEMENT_STATES[:1], prefix=f"{filer.envelope}-")


#: The filer whose profile holds the Borrador drafts: a salaried filer with one certificate in the register.
BORRADOR_FILER = RentaFiler("borrador", "trabajo", salary=("30000", "1900"), certified=Decimal("2000.00"))
#: The boxes an AEAT draft prints as results, which no binding owns: they are kept only to be compared. The draft
#: prints what the calculation works out for each, except the last, which it prints a euro and a quarter higher.
BORRADOR_PRINTED_RESULTS: tuple[str, ...] = ("0505", "0545", "0546", "0585", "0586")
BORRADOR_PRINTED_OFF = ("0585", Decimal("1.25"))
#: Boxes the draft prints that its import does not read: the cash remuneration, stated lower than the filer typed,
#: and the Social Security contributions, stated as typed.
BORRADOR_PRINTED_EXTRA: tuple[tuple[str, str], ...] = (("0003", "29500.00"), ("0013", "1900.00"))
#: When a draft the rules refuse was stored, when the first draft was imported and when the second was.
BORRADOR_REFUSED_AT = datetime(RENTA_YEAR + 1, 4, 2, 10, 0, tzinfo=UTC)
BORRADOR_FIRST_AT = datetime(RENTA_YEAR + 1, 4, 3, 10, 0, tzinfo=UTC)
BORRADOR_SECOND_AT = datetime(RENTA_YEAR + 1, 4, 5, 10, 0, tzinfo=UTC)


def _borrador_comparison(work: Any, language: str) -> BaseModel:
    """The comparison of the year's AEAT draft with the saved calculation, as the registered read serves it."""
    from cadrumo.application.live.borrador_100_comparison_operation import Borrador100CompareRequest
    from cadrumo.core.external_constants import OutputLanguage

    request = Borrador100CompareRequest(
        profile_id=UUID(work.work_unit.bucket_id), filing_year=RENTA_YEAR, output_language=OutputLanguage(language)
    )
    return _operate(
        work, "live.borrador.100.compare", request, subject_ref=_profile_subject(work), effect=OperationEffect.NONE
    )


def _write_borrador_comparison(directory: Path | None, work: Any, state: str) -> None:
    """Write the comparison in each language; nowhere when no directory is given."""
    if directory is None:
        return
    for language in LANGUAGES:
        _write(directory, f"borrador-100-{RENTA_PERIOD}-{state}-{language}.json", _borrador_comparison(work, language))


def _import_borrador(
    work: Any, tmp: Path, *, captured_at: datetime, results: Mapping[str, Decimal], shift: Decimal = Decimal(0)
) -> str:
    """Read a synthetic draft PDF through the real parser and keep it in the profile's encrypted custody.

    The printed ``results`` are kept as comparison-only observations, with the printed boxes the import does not
    read. ``shift`` moves every printed result, so a second draft differs from the first.
    """
    from cadrumo.application.live.borrador_100 import Borrador100PrintedObservation, Borrador100SnapshotService
    from cadrumo.application.live.borrador_100_import import prepare_borrador_100_import
    from cadrumo.core.period import Period
    from cadrumo.entrypoints.adapter_composition_ports import build_borrador_100_snapshot_repository
    from cadrumo.entrypoints.live_borrador_operation_composition import build_borrador_100_operation_ports
    from cadrumo.tests.fixtures.borrador.generate import render_borrador_pdf

    bucket = work.work_unit.bucket_id
    period = Period.from_year_and_code(RENTA_YEAR, RENTA_PERIOD)
    printed = {box: value + shift for box, value in results.items()}
    source = tmp / "borrador.pdf"
    source.write_bytes(render_borrador_pdf(RENTA_YEAR, printed))
    ports = build_borrador_100_operation_ports(profile_id=UUID(bucket), operation=work.operation)
    prepared = prepare_borrador_100_import(
        source,
        filing_year=RENTA_YEAR,
        period=period,
        operation=work.operation,
        parser=ports.parser,
        profile_tax_id=ports.profile_tax_id,
    )
    extra = tuple(
        Borrador100PrintedObservation(casilla_id=box, continuidad_id=None, value=Decimal(value))
        for box, value in BORRADOR_PRINTED_EXTRA
    )
    repository = build_borrador_100_snapshot_repository(bucket_id=bucket)
    return (
        Borrador100SnapshotService(bucket_id=bucket, repository=repository)
        .capture(
            filing_year=RENTA_YEAR,
            period=period,
            captured_at=captured_at,
            source_url=prepared.source_url,
            binding_values=prepared.binding_values,
            printed_observations=(*prepared.printed_observations, *extra),
            operation=work.operation,
        )
        .snapshot_id
    )


def _store_refused_borrador(work: Any) -> None:
    """Store a draft the pinned rules refuse: it names a box key no binding owns, so it can be named and never read."""
    from cadrumo.application.live.borrador_100 import Borrador100Snapshot, derive_borrador_100_snapshot_id
    from cadrumo.application.live.snapshot_base import SnapshotLifecycleState
    from cadrumo.core.period import Period
    from cadrumo.entrypoints.adapter_composition_ports import build_borrador_100_snapshot_repository

    bucket = work.work_unit.bucket_id
    period = Period.from_year_and_code(RENTA_YEAR, RENTA_PERIOD)
    reference = work.operation.snapshot("100", filing_year=RENTA_YEAR, period=RENTA_PERIOD).snapshot_ref
    values: dict[str, Decimal | str] = {"casilla.0596": Decimal("15.25")}
    source_url = "file-import:sha256:" + "b" * 64
    build_borrador_100_snapshot_repository(bucket_id=bucket).save(
        Borrador100Snapshot(
            snapshot_id=derive_borrador_100_snapshot_id(
                filing_year=RENTA_YEAR,
                period=period,
                registry_snapshot_ref=reference,
                source_url=source_url,
                binding_values=values,
            ),
            bucket_id=bucket,
            modelo="100",
            filing_year=RENTA_YEAR,
            period=period,
            registry_snapshot_ref=reference,
            captured_at=BORRADOR_REFUSED_AT,
            source_url=source_url,
            state=SnapshotLifecycleState.ACTIVE,
            binding_values=values,
        )
    )


def _borrador_chain(directory: Path | None, results: Mapping[str, Decimal]) -> dict[str, Decimal]:
    """Take one salaried filer's profile through the stages a draft and a calculation reach, in order.

    Each stage is read through the registered comparison and written in every language where a directory is given:
    nothing imported, a draft the rules refuse, a readable draft with no calculation, the calculation that replays
    it, and a second draft imported after the calculation. What the calculation holds for each box the draft prints
    as a result is returned.
    """
    with (
        tempfile.TemporaryDirectory(dir=prepare_temp_root()) as tmp,
        _renta_seeded(Path(tmp), BORRADOR_FILER) as work,
    ):
        _record_certificate(work, BORRADOR_FILER)
        _write_borrador_comparison(directory, work, "no-capture")
        _store_refused_borrador(work)
        _write_borrador_comparison(directory, work, "capture-refused")
        first = _import_borrador(work, Path(tmp), captured_at=BORRADOR_FIRST_AT, results=results)
        _write_borrador_comparison(directory, work, "no-calculation")
        _calculate_renta(work, BORRADOR_FILER, borrador_snapshot_id=first)
        _write_borrador_comparison(directory, work, "compared")
        compared = json.loads(_borrador_comparison(work, LANGUAGES[0]).model_dump_json())
        _import_borrador(work, Path(tmp), captured_at=BORRADOR_SECOND_AT, results=results, shift=Decimal(7))
        _write_borrador_comparison(directory, work, "stale")
    calculated = {
        row["casilla_id"]: Decimal(row["calculation_value"]["decimal"])
        for row in compared["rows"]
        if isinstance(row["calculation_value"], dict)
    }
    return {box: calculated[box] for box in BORRADOR_PRINTED_RESULTS}


def _write_borrador_comparisons(directory: Path) -> None:
    """Read the AEAT draft against the saved calculation at each stage a profile reaches, in each language.

    A first pass reads what the calculation holds for the boxes a draft prints as results; the draft then prints
    those figures, one of them a little higher, so the comparison has boxes that agree and one that differs.
    """
    calculated = _borrador_chain(None, dict.fromkeys(BORRADOR_PRINTED_RESULTS, Decimal(0)))
    box, off = BORRADOR_PRINTED_OFF
    printed = {key: value + (off if key == box else Decimal(0)) for key, value in calculated.items()}
    _borrador_chain(directory, printed)


def _write_renta(directory: Path) -> None:
    """Read every filer's 2025 Modelo 100 in every language, and the declarations list of the first filer.

    The married couple is also read for each other supported year, whose own design and registry edition, or the
    edition it is projected from, decide what the form offers.

    A filer with a calculated first quarter is also read for its projection of the annual return. The profile that
    holds the Borrador drafts is read for its comparison of each draft with the calculation.
    """
    for number, filer in enumerate(RENTA_FILERS):
        _write_renta_filer(directory, filer, first=number == 0)
    for year in renta_years():
        if year != RENTA_YEAR:
            _write_renta_filer(directory, renta_year_filer(year), first=False)
    _write_projection_steps(directory)
    _write_unreached_comparison_refusals(directory)
    _write_borrador_comparisons(directory)


#: The settlement states a result can be in that the filers above do not reach, by name: the result's amount and
#: what the box the declaration settles holds, the days left in the filing period, and whether it corrects an
#: earlier filing. Each is built by the real form builder and offered by the real export offer.
SETTLEMENT_STATES: tuple[tuple[str, str, str | None, int, bool], ...] = (
    # Within the period, an amount that splits: the second instalment is a cent more than nothing.
    ("least", "0.02", None, 30, False),
    # Within the period, an amount whose second instalment would be nothing.
    ("nothing", "0.01", None, 30, False),
    # Within the period, a result to pay of which the whole is suspended, so nothing remains to settle.
    ("unsupported", "500.00", "0", 30, False),
    # The period has ended.
    ("overdue", "1000.00", None, -5, False),
    # A corrective return.
    ("amendment", "1000.00", None, 30, True),
)
#: The day the settlement states are read on.
SETTLEMENT_DAY = RENTA_FILING_PERIOD_DAY.date()


def _write_settlement_states(
    directory: Path,
    work: Any,
    states: tuple[tuple[str, str, str | None, int, bool], ...],
    *,
    prefix: str = "",
) -> None:
    """Write the export offer of each settlement state in every language, as the real offer states it.

    The offer is the one of the work's own filing year, named after ``prefix`` where it is not the Renta's.
    """
    from cadrumo.application.modelo.settlement_casilla import declaration_settlement_casilla_id
    from cadrumo.application.modelo.tests.work_form_fixture import built_form, form_snapshot
    from cadrumo.application.modelo.work_form_declaration_facts import ModeloFormDeadline
    from cadrumo.application.modelo.work_form_export_offer import form_export_offer
    from cadrumo.core.external_constants import OutputLanguage
    from cadrumo.domain.deadlines.festivos import DeadlineHolidayCoverage

    operation = work.operation
    year = work.work_unit.filing_year
    snapshot = form_snapshot(operation, "100", year, RENTA_PERIOD)
    blank = built_form(operation, "100", year, RENTA_PERIOD, entered=frozenset())
    if blank.result is None:
        raise SystemExit(f"the {year} Modelo 100 names no result box")
    settling = declaration_settlement_casilla_id("100", snapshot.revision)
    for name, result, settled, days, amended in states:
        held: dict[str, Decimal | str] = {str(blank.result.casilla_id): Decimal(result)}
        if settling is not None and settling != blank.result.casilla_id:
            held[str(settling)] = Decimal(result if settled is None else settled)
        closes = SETTLEMENT_DAY + timedelta(days=days)
        form = built_form(operation, "100", year, RENTA_PERIOD, held=held, entered=frozenset()).model_copy(
            update={
                "calculation_revision_id": "c" * 64,
                "deadline": ModeloFormDeadline(
                    closes_on=closes,
                    nominal_closes_on=closes,
                    holiday_coverage=DeadlineHolidayCoverage.NATIONAL_ONLY,
                    reference_on=SETTLEMENT_DAY,
                    days_remaining=days if days >= 0 else None,
                    days_overdue=-days if days < 0 else None,
                ),
            }
        )
        for language in LANGUAGES:
            offer = form_export_offer(
                "100", snapshot, OutputLanguage(language), form=form, verified=False, filed=False, amended=amended
            )
            _write(directory, f"settlement-100-{RENTA_PERIOD}-{prefix}{name}-{language}.json", offer)


# -- writes ---------------------------------------------------------------------


@cache
def _registry() -> OperationRegistry:
    """The production operation registry: its executors and their public result projectors."""
    return build_production_operation_registry()


def _published(
    definition_id: str, result: BaseModel, subject_ref: str, *, effect: OperationEffect = OperationEffect.UPDATED
) -> BaseModel:
    """A settled result as the runtime publishes it: through its registered projector, where it has one."""
    from cadrumo.application.operations.models import OperationIdentity, OperationTerminalReceipt
    from cadrumo.core.operations import OperationTerminalCondition
    from cadrumo.core.time.clock import now

    projector = _registry().lookup_public_registration(definition_id).result_projector
    if projector is None:
        return result
    receipt = OperationTerminalReceipt(
        identity=OperationIdentity(operation_id="e" * 64, definition_id=definition_id, subject_ref=subject_ref),
        revision=1,
        condition=OperationTerminalCondition.SUCCEEDED,
        effect=effect,
        settled_at=now(),
        result_ref="f" * 64,
    )
    return projector(result, receipt)


def _operate(
    work: Any,
    definition_id: str,
    payload: BaseModel,
    *,
    subject_ref: str | None = None,
    effect: OperationEffect = OperationEffect.UPDATED,
) -> BaseModel:
    """Run one registered operation through its production executor, as the supervisor would; its public result."""
    subject = work.work_unit_id if subject_ref is None else subject_ref
    executor = _registry().lookup(definition_id).executor_factory.create()
    return _published(
        definition_id,
        _run_executor(work, definition_id, executor, payload, subject_ref=subject),
        subject,
        effect=effect,
    )


def _profile_subject(work: Any) -> str:
    from cadrumo.core.operations import profile_operation_subject

    return profile_operation_subject(work.work_unit.bucket_id)


def _edit_document(
    baseline: Any,
    *,
    typed: tuple[tuple[str, str], ...] = (),
    intents: tuple[tuple[str, str], ...] = (),
    restored: tuple[str, ...] = (),
    held: list[dict[str, Any]] | None = None,
    language: str = "en",
) -> dict[str, Any]:
    """An edit's operator input as the desktop sends it: entries as typed, or scalar intents setting typed values.

    ``baseline`` is the admitted or renewed baseline in its wire form.
    """
    from cadrumo.application.modelo.edit_baseline_projection import ModeloEditApplyBaselineV1

    wire = (
        baseline
        if isinstance(baseline, ModeloEditApplyBaselineV1)
        else ModeloEditApplyBaselineV1.from_baseline(baseline)
    )
    sent = wire.model_dump(mode="json")
    return {
        "input_version": 2,
        "output_language": language,
        "submission": {
            "baseline": sent,
            "mutation_family": sent["mutation_family"],
            "scalar_intents": [
                *(
                    {"address": {"kind": "scalar", "casilla_id": box}, "kind": "set_typed_value", "value": value}
                    for box, value in intents
                ),
                *(
                    {"address": {"kind": "scalar", "casilla_id": box}, "kind": "restore_source_value"}
                    for box in restored
                ),
            ],
            # The changes the review holds, as each box stood when it was staged.
            **({"held": held} if held is not None else {}),
            "binding_intents": [],
            "lexemes": [
                {"address": {"kind": "scalar", "casilla_id": box}, "entry_locale": language, "lexeme": text}
                for box, text in typed
            ],
        },
    }


def _edit(work: Any, definition_id: str, document: dict[str, Any], *, operation_id: str = "f" * 64) -> Any:
    """Run a preflight or an apply through the production executor and the financial operand path.

    Returns the public result, or the refusal the executor raised.
    """
    from cadrumo.application.modelo.edit_operator_input import prepare_modelo_edit_operand
    from cadrumo.application.modelo.edit_transient_operand import modelo_edit_financial_operand
    from cadrumo.application.operations.models import OperationIdentity, OperationRequest
    from cadrumo.application.operations.tests.financial_operand_delivery import deliver_financial_operand
    from cadrumo.core.errors.hierarchy import CadrumoError

    prepared = prepare_modelo_edit_operand(
        definition_id=definition_id,
        profile_id=UUID(work.work_unit.bucket_id),
        subject_ref=work.work_unit_id,
        input_json=json.dumps(document),
    )
    identity = OperationIdentity(operation_id=operation_id, definition_id=definition_id, subject_ref=work.work_unit_id)
    executor = _registry().lookup(definition_id).executor_factory.create()
    results: list[BaseModel] = []

    async def run() -> None:
        if prepared.operand is None:
            raise SystemExit(f"the {definition_id} operand was not prepared")
        try:
            async with deliver_financial_operand(
                identity=identity,
                declaration=modelo_edit_financial_operand(work.receipt_repository_factory),
                operand=prepared.operand,
            ) as access:
                prepared.release()
                context = _ReadContext(
                    identity=identity, authority_operation=work.operation, typed_financial_operand=access
                )
                request = OperationRequest(
                    definition_id=definition_id, subject_ref=work.work_unit_id, payload=prepared.request
                )
                await executor.execute(request, cast(Any, context))
                results.extend(context.results)
        finally:
            prepared.release()

    try:
        asyncio.run(run())
    except CadrumoError as refused:
        return refused
    (result,) = results
    return _published(definition_id, result, work.work_unit_id)


def _admitted(work: Any, *, issued_at: datetime | None = None) -> Any:
    from cadrumo.application.modelo.edit_models import ModeloEditAdmittedV1

    admission = work.admit(issued_at=issued_at)
    if not isinstance(admission, ModeloEditAdmittedV1):
        raise SystemExit(f"modelo {work.work_unit.modelo} was refused edit admission")
    return admission.baseline


# -- the window's edits, on the baseline of the form it holds -------------------------
#
# The window sends every check, apply and renewal on the baseline the form it
# shows admitted. Each edit envelope is therefore read on the baseline of one
# written form, and named after that form: ``preflight-<form>-entry-<boxes>-<language>``
# reads entries as typed in that language on that language's form, ``preflight-<form>-review`` and
# ``preflight-<form>-stale`` check the staged changes with the changes the
# window holds, ``apply-<form>`` applies them and ``renew-<form>`` renews the
# form's baseline.


def _form_envelope(directory: Path, form: str, language: str = "en") -> dict[str, Any]:
    """The written envelope of ``form`` in ``language``, as the window holds it."""
    return cast(dict[str, Any], json.loads((directory / f"modelo-{form}-{language}.json").read_text("utf-8")))


def _form_baseline(directory: Path, form: str, language: str = "en") -> Any:
    """The baseline the read of ``form`` in ``language`` admitted, as the window holds it from that envelope."""
    from cadrumo.application.modelo.edit_baseline_projection import ModeloEditApplyBaselineV1

    admitted = _form_envelope(directory, form, language).get("admitted_baseline")
    if admitted is None:
        raise SystemExit(f"the form {form} admitted no edit baseline")
    return ModeloEditApplyBaselineV1.model_validate_json(json.dumps(admitted))


def _held(directory: Path, form: str, changes: tuple[tuple[str, str], ...]) -> list[dict[str, Any]]:
    """The changes a window staged on ``form``, as it holds them: each box, its kind, the box's state then."""
    fields = {field["box"]: field for field in _form_fields(_form_envelope(directory, form)) if field.get("box")}
    return [
        {
            "address": {"kind": "scalar", "casilla_id": fields[box]["address"]["casilla_id"]},
            "kind": kind,
            "held_state": fields[box]["state_digest"],
        }
        for box, kind in changes
    ]


def _write_entries(directory: Path, work: Any, form: str, *typed: tuple[tuple[str, str], ...]) -> None:
    """Read entries as typed into boxes of ``form``, one check per boxes and language, as the window sends each."""
    from cadrumo.application.modelo.workbench_operations import MODELO_EDIT_PREFLIGHT_OPERATION_DEFINITION_ID

    for entries in typed:
        boxes = "-".join(box for box, _ in entries)
        for language in LANGUAGES:
            lexemes = tuple((box, TYPED_FIGURE.get(text, {}).get(language, text)) for box, text in entries)
            read = _edit(
                work,
                MODELO_EDIT_PREFLIGHT_OPERATION_DEFINITION_ID,
                _edit_document(_form_baseline(directory, form, language), typed=lexemes, language=language),
            )
            _write(directory, f"preflight-{form}-entry-{boxes}-{language}.json", _expect_model(read))


def _write_check(
    directory: Path,
    work: Any,
    form: str,
    *,
    staged_on: str,
    staged: tuple[tuple[str, str], ...],
    intents: tuple[tuple[str, str], ...],
    name: str = "review",
) -> BaseModel:
    """Check the changes staged on ``staged_on`` on the baseline of ``form``, holding them as they were staged.

    A review is written once per set of held changes, named by them and by
    the form they were staged on, so the window's answer is the one the
    application gave for exactly the changes it holds, as it holds them.
    """
    from cadrumo.application.modelo.workbench_operations import MODELO_EDIT_PREFLIGHT_OPERATION_DEFINITION_ID

    document = _edit_document(
        _form_baseline(directory, form), intents=intents, held=_held(directory, staged_on, staged)
    )
    checked = _expect_model(_edit(work, MODELO_EDIT_PREFLIGHT_OPERATION_DEFINITION_ID, document))
    held = "".join(f"-{box}{kind}" for box, kind in sorted(staged)) + f"-from-{staged_on}" if name == "review" else ""
    _write(directory, f"preflight-{form}-{name}{held}.json", checked)
    return checked


def _stale_refusal(checked: BaseModel) -> None:
    """Refuse a check that was not answered as stale, or that said what became of the held changes."""
    refusal = getattr(getattr(checked, "outcome", None), "refusal", None)
    if getattr(refusal, "kind", None) != "stale_edit_baseline" or getattr(checked, "rebase", ()):
        raise SystemExit(f"the check was not a stale refusal saying nothing of the held changes: {checked!r}")


def _write_renewal(directory: Path, work: Any, form: str) -> BaseModel:
    """Renew the baseline of ``form`` through the registered renewal, as the window asks for it."""
    from cadrumo.application.modelo.workbench_operations import MODELO_EDIT_RENEW_OPERATION_DEFINITION_ID

    renewal = _operate(
        work,
        MODELO_EDIT_RENEW_OPERATION_DEFINITION_ID,
        _request(
            MODELO_EDIT_RENEW_OPERATION_DEFINITION_ID,
            {
                "profile_id": work.work_unit.bucket_id,
                "baseline": _form_baseline(directory, form).model_dump(mode="json"),
                "output_language": "en",
            },
        ),
    )
    _write(directory, f"renew-{form}.json", renewal)
    return renewal


def _write_apply(directory: Path, work: Any, form: str, intents: tuple[tuple[str, str], ...]) -> Any:
    """Apply the staged changes on the baseline of ``form``; its public result, or the refusal it raised."""
    from cadrumo.application.modelo.operation_shared import MODELO_EDIT_APPLY_OPERATION_DEFINITION_ID

    return _edit(
        work,
        MODELO_EDIT_APPLY_OPERATION_DEFINITION_ID,
        _edit_document(_form_baseline(directory, form), intents=intents),
        operation_id="d" * 64,
    )


def _write_main_edits(directory: Path, first: Any) -> None:
    """The main profile's first-quarter 130: its typed entries, its review, and a renewal of its baseline."""
    form = "130-1T"
    _write_entries(directory, first, form, (*TYPED_130, UNWRITABLE_130), TYPED_130)
    _write_check(directory, first, form, staged_on=form, staged=STAGED_130, intents=EDIT_130)
    _write_renewal(directory, first, form)


def _write_renewal_flow(directory: Path, work: Any, started: datetime) -> None:
    """A first-quarter 130 whose form was read half an hour ago, reviewed now, renewed and read again.

    What was typed then was read while the form's baseline was current; the
    review now finds it stale, the renewal re-admits it with nothing but its
    lifetime changed, and the form read again admits a fresh baseline, on
    which the review is checked. The profile's whole timeline runs on a
    frozen clock before ``started``, as a replay does: it was seeded and
    calculated forty minutes before, the form read half an hour before, and
    the review twenty minutes before.
    """
    from cadrumo.core.time.clock import frozen_clock

    read, renewed = "130-1T-expiring", "130-1T-renewed"
    with frozen_clock(started - timedelta(minutes=30)):
        _write_form(directory, work, f"modelo-{read}")
        _write_entries(directory, work, read, TYPED_130)
    with frozen_clock(started - timedelta(minutes=20)):
        _stale_refusal(
            _write_check(directory, work, read, staged_on=read, staged=STAGED_130, intents=EDIT_130, name="stale")
        )
        if getattr(_write_renewal(directory, work, read), "renewed_baseline", None) is None:
            raise SystemExit("the expired baseline was not renewed")
        _write_form(directory, work, f"modelo-{renewed}")
        _write_check(directory, work, renewed, staged_on=read, staged=STAGED_130, intents=EDIT_130)


def _write_edits(directory: Path, work: Any) -> None:
    """Type, review and apply a value on the checked, exported 130, and read it again after the apply."""
    form = "130-1T-exported"
    _write_entries(directory, work, form, TYPED_130)
    _write_check(directory, work, form, staged_on=form, staged=STAGED_130, intents=EDIT_130)
    _write(directory, f"apply-{form}.json", _expect_model(_write_apply(directory, work, form, EDIT_130)))
    _write_form(directory, work, "modelo-130-1T-applied")
    _write_disagreement_answers(directory, work, "130-1T-applied")


#: Why the operator accepts the typed figure over the ledger's, as the filer says it.
DISAGREEMENT_REASON = "The ledger figure misses an invoice booked after the quarter closed."
#: A revision the stored acceptance was never at, as a window holding an older read would send it.
STALE_RESOLUTION_REVISION = "0" * 64


def _resolve(work: Any, definition_id: str, document: dict[str, Any]) -> BaseModel:
    """Run one disagreement operation in the language the request names; see :func:`_resolve_in_worker`.

    The worker renders a refusal's sentence in its own catalogue language, which
    the host runs in the window's language, so the worker's language is the one
    the request names.
    """
    from cadrumo.core.config import override_settings

    with override_settings(cadrumo_output_language=str(document["output_language"])):
        return _resolve_in_worker(work, definition_id, document)


def _resolve_in_worker(work: Any, definition_id: str, document: dict[str, Any]) -> BaseModel:
    """Run one disagreement operation through its production executor; its public result or typed refusal.

    A refusal settles with the registered refusal detail its definition
    declares, which the host hands the window as the refusal's detail; it is
    published through the same projector a refused receipt releases it with.
    """
    from cadrumo.application.operations.models import (
        OperationIdentity,
        OperationRequest,
        OperationTerminalReceipt,
    )
    from cadrumo.application.operations.refusal_evidence import OperationRefusalEvidence
    from cadrumo.core.operations import OperationTerminalCondition
    from cadrumo.core.time.clock import now

    request = _request(definition_id, {"profile_id": work.work_unit.bucket_id, **document})
    subject = work.work_unit_id
    identity = OperationIdentity(operation_id="e" * 64, definition_id=definition_id, subject_ref=subject)
    context = _ReadContext(identity=identity, authority_operation=work.operation)
    executor = _registry().lookup(definition_id).executor_factory.create()
    settled = asyncio.run(
        executor.execute(
            OperationRequest(definition_id=definition_id, subject_ref=subject, payload=request), cast(Any, context)
        )
    )
    (result,) = context.results
    if not isinstance(settled, OperationRefusalEvidence):
        effect = OperationEffect.NONE if definition_id == "modelo.work.disagreements" else OperationEffect.UPDATED
        return _published(definition_id, result, subject, effect=effect)
    projector = _registry().lookup_public_registration(definition_id).result_projector
    if projector is None:
        raise SystemExit(f"{definition_id} publishes no refusal detail")
    receipt = OperationTerminalReceipt(
        identity=identity,
        revision=1,
        condition=OperationTerminalCondition.REFUSED,
        effect=OperationEffect.NONE,
        settled_at=now(),
        refusal_ref=settled.refusal_code,
        refusal_detail_ref="f" * 64,
    )
    return projector(result, receipt)


def _outcome(result: BaseModel, expected: str, reason: str | None = None) -> BaseModel:
    """``result``, after checking it came to ``expected`` and, for a refusal, for ``reason``."""
    outcome = getattr(result, "outcome", None)
    refusal = getattr(result, "refusal", None)
    if outcome != expected or (reason is not None and getattr(refusal, "reason", None) != reason):
        raise SystemExit(f"a disagreement answer came to {outcome} ({refusal!r}), not {expected} {reason or ''}")
    return result


def _write_disagreements(directory: Path, work: Any, revision_id: str, form: str) -> list[Any]:
    """Write the answers the declaration holds as read beside ``form``, in every language; the rows."""
    rows: list[Any] = []
    for language in LANGUAGES:
        listed = _resolve(
            work,
            "modelo.work.disagreements",
            {"calculation_revision_id": revision_id, "output_language": language},
        )
        _write(directory, f"disagreements-{form}-{language}.json", listed)
        rows = list(getattr(listed, "resolutions", ()))
    return rows


def _write_disagreement_answers(directory: Path, work: Any, form: str) -> None:
    """Accept the disagreement the form's check offers to accept, then take the acceptance back.

    The form's box 06 holds a typed figure over a different ledger figure, so
    its check line states a tier disagreement and offers to accept it. The
    acceptance is written, the form and the answers held are read again, and a
    second acceptance and a revocation at a revision the acceptance was never
    at are refused in every language; the acceptance is then revoked at the
    revision it is stored at and the form read once more, so the declaration
    leaves as it came: its disagreement open and withholding the check.
    """
    envelope = _form_envelope(directory, form)
    offered = [line for line in envelope["issue_lines"] if line.get("resolution_answer") == "accept"]
    if len(offered) != 1:
        raise SystemExit(f"the form {form} offers {len(offered)} disagreements to accept, not one")
    finding_id = offered[0]["finding_id"]
    revision_id = envelope["calculation_revision_id"]
    target = {"calculation_revision_id": revision_id, "finding_id": finding_id}
    accepted, revoked = "130-1T-accepted", "130-1T-revoked"
    _write_disagreements(directory, work, revision_id, form)
    accept = {**target, "reason": DISAGREEMENT_REASON}
    _write(
        directory,
        f"accept-{form}.json",
        _outcome(_resolve(work, "modelo.work.accept_disagreement", {**accept, "output_language": "en"}), "accepted"),
    )
    _write_form(directory, work, f"modelo-{accepted}")
    (row,) = _write_disagreements(directory, work, revision_id, accepted)
    for language in LANGUAGES:
        again = _resolve(work, "modelo.work.accept_disagreement", {**accept, "output_language": language})
        _write(directory, f"accept-{accepted}-refused-{language}.json", _outcome(again, "refused", "already_resolved"))
        stale = _resolve(
            work,
            "modelo.work.revoke_disagreement",
            {**target, "expected_revision_id": STALE_RESOLUTION_REVISION, "output_language": language},
        )
        _write(directory, f"revoke-{accepted}-stale-{language}.json", _outcome(stale, "refused", "stale_revision"))
    revoke = {**target, "expected_revision_id": row.revision_id, "output_language": "en"}
    _write(
        directory,
        f"revoke-{accepted}.json",
        _outcome(_resolve(work, "modelo.work.revoke_disagreement", revoke), "revoked"),
    )
    _write_form(directory, work, f"modelo-{revoked}")
    _write_disagreements(directory, work, revision_id, revoked)


def _write_prerequisite(directory: Path, first: Any) -> None:
    """Apply a typed value on a third-quarter 130 whose earlier quarters were never filed; read what it waits on.

    Its earlier instalments come from the filings of the quarters before it,
    which this profile does not hold, so the apply is refused and the worker
    holds that prerequisite for the apply's operation, which the prerequisite
    read then names.
    """
    from cadrumo.application.modelo.workbench_operations import (
        MODELO_EDIT_APPLY_PREREQUISITE_OPERATION_DEFINITION_ID,
        ModeloEditApplyPrerequisiteRequest,
    )
    from cadrumo.core.errors.hierarchy import CadrumoError
    from cadrumo.core.external_constants import OutputLanguage

    modelo, period_code = PREREQUISITE_130
    work = _other_declaration(first, modelo, period_code)
    form = f"{modelo}-{period_code}-prerequisite"
    _write_form(directory, work, f"modelo-{form}")
    _write_entries(directory, work, form, TYPED_130)
    _write_check(directory, work, form, staged_on=form, staged=STAGED_130, intents=EDIT_130)
    if not isinstance(_write_apply(directory, work, form, EDIT_130), CadrumoError):
        raise SystemExit("the apply without the earlier filings was not refused")
    baseline = _form_baseline(directory, form)
    prerequisite = _operate(
        work,
        MODELO_EDIT_APPLY_PREREQUISITE_OPERATION_DEFINITION_ID,
        ModeloEditApplyPrerequisiteRequest(
            profile_id=UUID(work.work_unit.bucket_id),
            work_unit_id=work.work_unit_id,
            apply_operation_id="d" * 64,
            baseline_id=baseline.baseline_id,
            calculation_revision_id=baseline.current_calculation_revision_id,
            registry_revision_id=work.work_unit.revision_id,
            output_language=OutputLanguage.EN,
        ),
    )
    if getattr(prerequisite, "prerequisite", None) is None:
        raise SystemExit("the refused apply holds no prerequisite")
    _write(directory, f"apply-prerequisite-{form}.json", prerequisite)


def _write_303_edits(directory: Path, work: Any) -> None:
    """Read a typed figure on the Modelo 303 and review it as staged, on the baseline its form admitted."""
    form = "303-1T"
    _write_entries(directory, work, form, TYPED_303)
    _write_check(directory, work, form, staged_on=form, staged=STAGED_303, intents=EDIT_303)


def _write_rebase(directory: Path, work: Any) -> None:
    """Check changes staged on an earlier read after the declaration moved under them, as the window recovers.

    The filer staged on the form as it was read: clearing
    the value typed into one box and typing into two others. The declaration
    then moved under those changes, as another session's apply would move it:
    the cleared box's typed value was taken back, so it no longer takes a
    clear, and a figure was typed into one of the typed boxes. The review's
    check on the baseline the window holds is refused as stale, saying
    nothing of the held changes; renewing that baseline is refused, since
    more than its lifetime moved; the form read again admits a fresh
    baseline, and the check on it reports one dropped, one changed and one
    kept.
    """
    from cadrumo.application.modelo.operation_shared import MODELO_EDIT_APPLY_OPERATION_DEFINITION_ID

    staged_on, moved = "130-1T-rebase", "130-1T-rebased"
    _write_form(directory, work, f"modelo-{staged_on}")
    _write_entries(directory, work, staged_on, *((entry,) for entry in REBASE_TYPED_ENTRIES))
    _expect_model(
        _edit(
            work,
            MODELO_EDIT_APPLY_OPERATION_DEFINITION_ID,
            _edit_document(_admitted(work), intents=REBASE_MOVE, restored=REBASE_RESTORED),
        )
    )
    _stale_refusal(
        _write_check(
            directory, work, staged_on, staged_on=staged_on, staged=REBASE_STAGED, intents=REBASE_TYPED, name="stale"
        )
    )
    renewal = _write_renewal(directory, work, staged_on)
    if getattr(renewal, "renewed_baseline", None) is not None or getattr(renewal, "refusal", None) is None:
        raise SystemExit(f"renewing the baseline the declaration moved under was not refused: {renewal!r}")
    _write_form(directory, work, f"modelo-{moved}")
    reviewed = _write_check(directory, work, moved, staged_on=staged_on, staged=REBASE_STAGED, intents=REBASE_TYPED)
    outcomes = sorted(entry.outcome.value for entry in getattr(reviewed, "rebase", ()))
    if outcomes != ["changed", "dropped", "kept"]:
        raise SystemExit(f"the review did not keep, change and drop one held change each: {outcomes}")
    # The window lets the dropped change go and stages the others again against the boxes as they now stand,
    # then checks them as it holds them now.
    still = tuple(change for change in REBASE_STAGED if change[1] != "clear")
    _write_check(directory, work, moved, staged_on=moved, staged=still, intents=REBASE_TYPED)
    # Still changing: each time the window reads it again after a refused renewal, it moves once more before
    # the check. Asked to check again, the window renews and reads once more, and finds it moved again.
    previous = staged_on
    for read, move in (("130-1T-moving", REBASE_MOVE_AGAIN), ("130-1T-moving-again", REBASE_MOVE_ONCE_MORE)):
        if previous != staged_on:
            renewal = _write_renewal(directory, work, previous)
            if getattr(renewal, "renewed_baseline", None) is not None:
                raise SystemExit(f"renewing {previous} after the declaration moved was not refused")
        _write_form(directory, work, f"modelo-{read}")
        _expect_model(
            _edit(
                work,
                MODELO_EDIT_APPLY_OPERATION_DEFINITION_ID,
                _edit_document(_admitted(work), intents=move),
            )
        )
        _stale_refusal(
            _write_check(
                directory, work, read, staged_on=staged_on, staged=REBASE_STAGED, intents=REBASE_TYPED, name="stale"
            )
        )
        previous = read


def _expect_model(answer: Any) -> BaseModel:
    if not isinstance(answer, BaseModel):
        raise SystemExit(f"an edit operation was refused: {answer!r}")
    return answer


def _request(definition_id: str, document: dict[str, Any]) -> BaseModel:
    """A definition's registered request, from the document a frontend sends."""
    return _registry().lookup(definition_id).request_type.model_validate_json(json.dumps(document))


def _write_filing_reads(directory: Path, work: Any, name: str) -> Any:
    """Write the unit a correction of a recorded declaration is read from; the unit, as the metadata read states it.

    Its history is not written: an imported receipt's event quotes the file's
    place, which the host cuts to the file's name and the history model then
    refuses, so no stored history could be validated as what the window is
    shown.
    """
    definition_id = "modelo.work.metadata"
    read = _operate(
        work,
        definition_id,
        _request(definition_id, {"profile_id": work.work_unit.bucket_id, "work_unit_id": work.work_unit_id}),
        subject_ref=_profile_subject(work),
    )
    _write(directory, f"metadata-{name}.json", read)
    return getattr(read, "unit", None)


def _write_receipt_import(directory: Path, work: Any) -> None:
    """Import a justificante PDF against the recorded 130 through the reconciliation import."""
    import cadrumo

    source = Path(cadrumo.__file__).resolve().parent.joinpath(*JUSTIFICANTE_130)
    _FILE_FOLDERS.append(str(source.parent))
    document = {
        "profile_id": work.work_unit.bucket_id,
        "work_unit_id": work.work_unit_id,
        "calculation_revision_id": work.require_head().calculation_revision_id,
        "source_kind": "justificante",
        "source_path": str(source),
        "actor": ACTOR,
    }
    definition_id = "modelo.reconcile.import"
    imported = _operate(work, definition_id, _request(definition_id, document), subject_ref=_profile_subject(work))
    _write(directory, f"reconcile-{work.work_unit.modelo}.json", imported)


def _write_correction(directory: Path, work: Any, filing_record_id: str) -> None:
    """Read what correcting the recorded, receipt-confirmed 130 offers, check a corrected figure, and correct it.

    The corrected figure is checked through the canonical typed-entry path as
    the desktop sends it, once as a figure and once as words it cannot read.
    """
    from cadrumo.application.modelo.workbench_operations import MODELO_EDIT_PREFLIGHT_OPERATION_DEFINITION_ID

    modelo = str(work.work_unit.modelo)
    definition_id = "modelo.work.amendment_context"
    context = _operate(
        work,
        definition_id,
        _request(
            definition_id,
            {"profile_id": work.work_unit.bucket_id, "filing_record_id": filing_record_id, "output_language": "en"},
        ),
        subject_ref=_profile_subject(work),
    )
    _write(directory, f"amendment-context-{modelo}.json", context)
    if not isinstance(context, ModeloWorkAmendmentContextProjection):
        raise SystemExit("the amendment context read did not publish its projection")
    correction = context.correction
    if correction is None or not correction.rows or not correction.kinds:
        raise SystemExit("the recorded 130 offers no correction")
    row = next((row for row in correction.rows if row.casilla_id == CORRECTED_130[0]), correction.rows[0])
    form = "130-1T-receipt"
    baseline = _form_baseline(directory, form).model_dump(mode="json")
    for suffix, lexeme in (("", CORRECTED_130[1]), ("-refused", UNREADABLE_ENTRY)):
        document = {
            "input_version": 2,
            "output_language": "en",
            "submission": {
                "baseline": baseline,
                "mutation_family": baseline["mutation_family"],
                "lexemes": [
                    {"address": row.edit_address.model_dump(mode="json"), "entry_locale": "en", "lexeme": lexeme}
                ],
            },
        }
        checked = _edit(work, MODELO_EDIT_PREFLIGHT_OPERATION_DEFINITION_ID, document)
        _write(directory, f"preflight-{form}-correction{suffix}.json", _expect_model(checked))
    (parsed,) = [entry for entry in checked_entries(directory, form) if entry["address"]["kind"] == "correction"]
    definition_id = "modelo.work.amend"
    amended = _operate(
        work,
        definition_id,
        _request(
            definition_id,
            {
                "baseline": {"from_filing_record_id": correction.filed.filing_record_id},
                "amendment_kind": correction.kinds[0].kind.value,
                "overrides": [{"casilla_id": row.casilla_id, "value": str(parsed["value"])}],
                "reason": CORRECTION_REASON,
                "m303_rectificativa_motive": None,
                "actor": ACTOR,
            },
        ),
    )
    _write(directory, f"amend-{modelo}.json", amended)


def checked_entries(directory: Path, form: str) -> list[dict[str, Any]]:
    """The entries the correction's figure check on ``form`` read, as it wrote them."""
    return json.loads((directory / f"preflight-{form}-correction.json").read_text("utf-8"))["parsed"]


def _write_unverified_export(directory: Path, first: Any, destination: Path) -> None:
    """Export a declaration whose file design carries no completeness manifest; the export cannot vouch for it."""
    modelo, period_code = UNVERIFIED_EXPORT
    work = _other_declaration(first, modelo, period_code)
    work.recalculate()
    if not _verify(work).granted_verificado_completo:
        raise SystemExit(f"modelo {modelo} did not check cleanly")
    exported = _export_file(work, destination)
    if getattr(exported, "completeness", None) != "unverified":
        raise SystemExit(f"modelo {modelo}'s export is not unverified: {exported!r}")
    _write(directory, f"export-{modelo}-unverified.json", exported)


# -- what the host hands the window ----------------------------------------------

#: The folders of the files the envelopes' writes picked or saved, which the host knows as the person's own.
_FILE_FOLDERS: list[str] = []


def _result_path_keys() -> frozenset[str]:
    """The result fields the host reduces to a file name, as its modelo shell module states them."""
    found = re.search(r"const RESULT_PATH_KEYS: \[&str; \d+\] = \[(.*?)\];", MODELO_SHELL.read_text("utf-8"), re.S)
    if found is None:
        raise SystemExit(f"{MODELO_SHELL} no longer states RESULT_PATH_KEYS as a list")
    return frozenset(str(name) for name in re.findall(r'"([^"]+)"', found.group(1)))


def _named(text: str) -> str:
    """An absolute path reduced to its file name, as the host reduces one; any other text unchanged."""
    if re.match(r"^(?:[A-Za-z]:[\\/]|file:|[\\/])", text, re.IGNORECASE):
        return str(re.split(r"[\\/]", text)[-1])
    return text


def _host_view(value: Any, keys: frozenset[str], folders: list[str]) -> Any:
    """A document as the host shows it to the window.

    Every path a result names under one of the host's path keys becomes its
    file name, and a folder of a file the person picked or saved, quoted
    anywhere else, is cut to the file's name, as ``shell/settle.rs`` does.
    """

    def strip(text: str) -> str:
        for folder in sorted(folders, key=len, reverse=True):
            if folder in text:
                text = text.replace(f"{folder}\\", "").replace(f"{folder}/", "")
                text = text.replace(folder, re.split(r"[\\/]", folder)[-1])
        return text

    def walk(node: Any, key: str | None) -> Any:
        if isinstance(node, dict):
            return {name: walk(field, name) for name, field in node.items()}
        if isinstance(node, list):
            return [walk(item, key) for item in node]
        if isinstance(node, str):
            return strip(_named(node) if key in keys else node)
        return node

    return walk(value, None)


_ABSOLUTE_PATH = re.compile(r"(?:^|[\s\"'(=:,])(?:[A-Za-z]:[\\/]|\\\\[^\\\s]|file:/)|^/[^\s/]+/", re.IGNORECASE)


def _paths_in(path: Path) -> list[str]:
    """Every string in an envelope that names an absolute path, a drive or a file URI."""
    found: list[str] = []

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            for field in node.values():
                walk(field)
        elif isinstance(node, list):
            for item in node:
                walk(item)
        elif isinstance(node, str) and _ABSOLUTE_PATH.search(node):
            found.append(node[:80])

    walk(stored_envelope(path.parent, path.stem))
    return found


def _form_fields(envelope: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Every field of a written form envelope, in the order its pages hold them."""
    found: list[dict[str, Any]] = []

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            if "held_zero" in node and "address" in node:
                found.append(node)
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(envelope["form"]["form"]["pages"])
    return found


def _refusals() -> tuple[tuple[str, BaseException], ...]:
    """The refusals the scenarios settle, each as its executor raises it."""
    from cadrumo.application.modelo.action_errors import ModeloDomiciliationPastCutoffError
    from cadrumo.application.modelo.calculation_note_gate import ModeloCalculationBlockedError
    from cadrumo.application.modelo.calculation_notes import CALCULATION_SCREEN_OUTDATED_REASON
    from cadrumo.application.modelo.calculation_screen import calculation_screen_outdated_message_key

    return (
        (
            "report-outdated",
            ModeloCalculationBlockedError(
                translated_message=calculation_screen_outdated_message_key(),
                context={
                    "action": "report",
                    "calculation_revision_id": "c" * 64,
                    "reason": CALCULATION_SCREEN_OUTDATED_REASON,
                    "reasons": CALCULATION_SCREEN_OUTDATED_REASON,
                },
            ),
        ),
        (
            "domiciliation-past-cutoff",
            ModeloDomiciliationPastCutoffError(
                translated_message="errors.refused.refused_modelo_domiciliation_past_cutoff",
                context={
                    "calculation_revision_id": "c" * 64,
                    "modelo": "130",
                    "filing_year": "2026",
                    "period": "1T",
                    "payment_cutoff_on": "2026-04-15",
                    "payment_cutoff_source": "filing_window",
                    "payment_cutoff_legal_refs": "Orden HAC/3625/2003, art. 3",
                    "export_on": "2026-04-16",
                },
            ),
        ),
    )


def write_refusals(directory: Path) -> None:
    """Record each scenario refusal's detail as a stopped executor's detail is recorded, in every language."""
    from cadrumo.application.operations.error_detail import build_operation_error_detail
    from cadrumo.core.config import override_settings

    directory.mkdir(parents=True, exist_ok=True)
    for language in LANGUAGES:
        with override_settings(cadrumo_output_language=language):
            for name, error in _refusals():
                detail = build_operation_error_detail(error)
                if detail is None:
                    raise SystemExit(f"{name} records no error detail")
                _write(directory, f"refusal-{name}-{language}.json", detail)


def _write_iva_wallet(directory: Path) -> None:
    """Real local balance operations in an isolated profile, without a sealed 303."""
    from cadrumo.application.modelo.iva_wallet_balance_operation import (
        MODELO_IVA_WALLET_BALANCE_OPERATION_DEFINITION_ID,
        ModeloIvaWalletBalanceRequest,
    )
    from cadrumo.application.modelo.iva_wallet_correction_operation import (
        MODELO_IVA_WALLET_CORRECTION_OPERATION_DEFINITION_ID,
        ModeloIvaWalletCorrectionRequest,
    )
    from cadrumo.application.modelo.iva_wallet_override_operation import (
        MODELO_IVA_WALLET_OVERRIDE_OPERATION_DEFINITION_ID,
        ModeloIvaWalletOverrideRequest,
    )
    from cadrumo.application.modelo.iva_wallet_seed_operation import (
        MODELO_IVA_WALLET_SEED_OPERATION_DEFINITION_ID,
        ModeloIvaWalletSeedRequest,
    )
    from cadrumo.application.operations.public_period import PublicPeriod

    with tempfile.TemporaryDirectory(dir=prepare_temp_root()) as tmp, _seeded(Path(tmp)) as work:
        iva = _other_declaration(work, "303", "1T")
        _write_list(directory, work, "declarations-wallet")
        profile_id = UUID(work.work_unit.bucket_id)
        source = PublicPeriod(filing_year=2024, code="4T")
        subject = _profile_subject(work)

        def balance(stage: str) -> None:
            # Read the same declaration after each register write; never recalculate it.
            _write_form(directory, iva, f"modelo-303-1T-wallet-{stage}")
            _write(
                directory,
                f"iva-wallet-balance-{stage}.json",
                _operate(
                    work,
                    MODELO_IVA_WALLET_BALANCE_OPERATION_DEFINITION_ID,
                    ModeloIvaWalletBalanceRequest(profile_id=profile_id, as_of_year=2026),
                    subject_ref=subject,
                    effect=OperationEffect.NONE,
                ),
            )

        balance("empty")
        for name, definition, request in (
            (
                "seed",
                MODELO_IVA_WALLET_SEED_OPERATION_DEFINITION_ID,
                ModeloIvaWalletSeedRequest(profile_id=profile_id, period=source, amount="1200.50"),
            ),
            (
                "correct",
                MODELO_IVA_WALLET_CORRECTION_OPERATION_DEFINITION_ID,
                ModeloIvaWalletCorrectionRequest(
                    profile_id=profile_id,
                    period=source,
                    amount="900.25",
                    reason="Correct the recorded opening balance.",
                ),
            ),
            (
                "override",
                MODELO_IVA_WALLET_OVERRIDE_OPERATION_DEFINITION_ID,
                ModeloIvaWalletOverrideRequest(
                    profile_id=profile_id,
                    period=PublicPeriod(filing_year=2026, code="1T"),
                    amount="850.00",
                    reason="Use the taxpayer's reviewed carry balance.",
                    evidence_locator="fixture:reviewed-iva-balance-2026-1T",
                ),
            ),
        ):
            _write(directory, f"iva-wallet-{name}.json", _operate(work, definition, request, subject_ref=subject))
            balance(name)


def write_envelopes(directory: Path) -> None:
    """Read every envelope the scenario host answers through the application's read path."""
    from cadrumo.adapters.persistence.profile.tests.cross_period_seeding import SEEDED_SOURCE_TAX_ID
    from cadrumo.core.time.clock import frozen_clock, now
    from cadrumo.domain.user_profile.values import UserProfileFact

    directory.mkdir(parents=True, exist_ok=True)
    write_refusals(directory)
    _write_iva_wallet(directory)
    income = (_income_categories_fact(),)
    with (
        tempfile.TemporaryDirectory(dir=prepare_temp_root()) as tmp,
        _seeded(Path(tmp), facts=income) as first,
    ):
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
        _write_main_edits(directory, first)
        # Checked after everything above was read, so those envelopes stay unchecked.
        _verify(first)
        _write_form(directory, first, "modelo-130-1T-checked")
        _write_prerequisite(directory, first)
        _write_303_edits(directory, works["303"])
        _write_unverified_export(directory, first, Path(tmp) / "modelo-165.txt")
    # Its own profile: recording needs the earlier Renta filed under the profile's tax id.
    facts = (*income, UserProfileFact(path="identity.tax_id", value=SEEDED_SOURCE_TAX_ID))
    with (
        tempfile.TemporaryDirectory(dir=prepare_temp_root()) as tmp,
        _seeded(Path(tmp), facts=facts) as filed,
    ):
        _write(directory, "file-130.json", _record_filed(filed))
        _write_form(directory, filed, "modelo-130-1T-filed")
        _write_receipt_import(directory, filed)
        # Nothing was ever read from the AEAT in this profile, so its list is incomplete.
        _write_list(directory, filed, "declarations-incomplete")
        _import_receipt(filed)
        _write_form(directory, filed, "modelo-130-1T-receipt")
        unit = _write_filing_reads(directory, filed, "130-receipt")
        _write_correction(directory, filed, unit.current_filing_record_id)
    # Its own profile: the quarter's income is booked and the declaration is calculated, never checked or filed.
    with (
        tempfile.TemporaryDirectory(dir=prepare_temp_root()) as tmp,
        _seeded(Path(tmp), facts=income) as booked,
    ):
        _seed_income(booked)
        booked.recalculate()
        _write_form(directory, booked, "modelo-130-1T-income")
    # Its own profile, on a frozen timeline: a review half an hour after the form was read, and its renewal.
    started = now()
    with (
        tempfile.TemporaryDirectory(dir=prepare_temp_root()) as tmp,
        frozen_clock(started - timedelta(minutes=40)),
        _seeded(Path(tmp), facts=income) as renewing,
    ):
        renewing.recalculate()
        _write_renewal_flow(directory, renewing, started)
    # Its own profile: the file is written, then a conflicting edit makes it stale and blocks verification.
    with (
        tempfile.TemporaryDirectory(dir=prepare_temp_root()) as tmp,
        _seeded(Path(tmp), facts=facts) as stale,
    ):
        _check_clean(stale)
        _write(directory, "export-130.json", _export_file(stale, Path(tmp) / "modelo-130.txt"))
        # Checked, its file made and current: what recording the filing starts from.
        _write_form(directory, stale, "modelo-130-1T-exported")
        _write_edits(directory, stale)
        # The typed box 06 replaced the ledger's own figure, so checking again is refused on that divergence.
        _check_refused_on_divergence(stale)
        _write_form(directory, stale, "modelo-130-1T-stale")
        _write_rebase(directory, stale)
    _write_renta(directory)
    pack_envelopes(directory)


# -- stored envelopes -----------------------------------------------------------
#
# The 2025 Modelo 100 forms are over three megabytes each, and the filers and languages read of it differ in
# a few hundred words. They are stored as a patch of the form they differ from: the filer's form in the
# language's words, or the first filer's form in another language. A patch is the envelope's name and the
# values that differ, the way ``src/dev/modeloEnvelopePatch.ts`` reads it. Every other envelope is stored whole.

#: The forms stored as patches, by modelo.
PACKED_MODELOS: tuple[str, ...] = ("100",)
#: A stored envelope that is a patch of another names it under this key.
PATCH_OF = "patch_of"
PATCH_CHANGES = "changes"
_PACKED_NAME = re.compile(
    r"^(?P<form>modelo-(?P<modelo>[0-9]+)-[0-9A-Z]+)(?P<filer>(?:-[a-z][a-z0-9]*)?)-(?P<language>[a-z]{2})$"
)


def _compact(value: Any) -> str:
    """An envelope as it is stored: no indentation, in the order the application served it."""
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _differences(base: Any, target: Any) -> Any | None:
    """What turns ``base`` into ``target``, or nothing where they are the same.

    An object is the differences by key or by position, and a one-element array is the value that replaces
    what stood there: whole where the two differ in kind, in keys or in length.
    """
    if isinstance(base, dict) and isinstance(target, dict) and list(base) == list(target):
        pairs = {key: _differences(base[key], target[key]) for key in base}
        changes = {key: found for key, found in pairs.items() if found is not None}
        return changes or None
    if isinstance(base, list) and isinstance(target, list) and len(base) == len(target):
        pairs = {str(position): _differences(each, target[position]) for position, each in enumerate(base)}
        changes = {key: found for key, found in pairs.items() if found is not None}
        return changes or None
    return None if type(base) is type(target) and base == target else [target]


def _patched(base: Any, changes: Any) -> Any:
    """``base`` with ``changes`` applied, as ``_differences`` states them; ``base`` itself is left as it is."""
    if isinstance(changes, list):
        return changes[0]
    if isinstance(base, list):
        copied = list(base)
        for key, found in changes.items():
            copied[int(key)] = _patched(copied[int(key)], found)
        return copied
    copied_object = dict(base)
    for key, found in changes.items():
        copied_object[key] = _patched(copied_object[key], found)
    return copied_object


def _is_patch(value: Any) -> bool:
    return isinstance(value, dict) and set(value) == {PATCH_OF, PATCH_CHANGES}


def stored_envelope(directory: Path, name: str) -> Any:
    """The envelope stored as ``name``, whole, whether it is stored whole or as a patch."""
    stored = json.loads((directory / f"{name}.json").read_text("utf-8"))
    if not _is_patch(stored):
        return stored
    return _patched(stored_envelope(directory, stored[PATCH_OF]), stored[PATCH_CHANGES])


_YEAR_FILER = re.compile(r"^-y(?P<year>[0-9]+)$")


def _patch_base(name: str, names: Iterable[str] = ()) -> str | None:
    """The form a Modelo 100 form is stored as a patch of, or none for the one that is stored whole.

    A filer's form is a patch of the first filer's in the same language. A form of another filing year is a patch
    of its own English form in the other languages, and its English form is a patch of the form of the year beside
    it on the way to the Renta's own, whose designs differ least: the couple's form of the Renta's year, which is
    where the years above it start from as well.
    """
    found = _PACKED_NAME.match(name)
    if found is None or found["modelo"] not in PACKED_MODELOS:
        return None
    form, filer, language = found["form"], found["filer"], found["language"]
    year = _YEAR_FILER.match(filer)
    if year is None:
        if filer:
            return f"{form}-{language}"
        return None if language == LANGUAGES[0] else f"{form}-{LANGUAGES[0]}"
    if language != LANGUAGES[0]:
        return f"{form}{filer}-{LANGUAGES[0]}"
    held = {
        int(other_year["year"])
        for other in names
        if (other_name := _PACKED_NAME.match(other)) is not None
        and other_name["form"] == form
        and (other_year := _YEAR_FILER.match(other_name["filer"])) is not None
    }
    toward = int(year["year"]) + (1 if int(year["year"]) < RENTA_YEAR else -1)
    if toward in held:
        return f"{form}-y{toward}-{LANGUAGES[0]}"
    return f"{form}-married-{LANGUAGES[0]}"


def pack_envelopes(directory: Path) -> None:
    """Store every envelope in ``directory`` as the next regeneration stores it: compact, forms as patches.

    It reads each envelope whole, so a directory already stored this way is left as it is.
    """
    names = sorted(path.stem for path in directory.glob("*.json"))
    whole = {name: stored_envelope(directory, name) for name in names}
    for name, value in whole.items():
        base = _patch_base(name, names)
        if base is None:
            text = _compact(value)
        else:
            changes = _differences(whole[base], value) or {}
            if _compact(_patched(whole[base], changes)) != _compact(value):
                raise SystemExit(f"{name} is not what its patch of {base} makes")
            text = _compact({PATCH_OF: base, PATCH_CHANGES: changes})
        (directory / f"{name}.json").write_text(text, "utf-8", newline="\n")


# -- check --------------------------------------------------------------------


def _fixture_models() -> list[tuple[str, type[BaseModel]]]:
    from cadrumo.application.live.borrador_100_comparison import Borrador100ComparisonProjection
    from cadrumo.application.modelo.declarations_list_operation import ModeloDeclarationsListProjectionV1
    from cadrumo.application.modelo.work_form_export_offer import ModeloFormExportOffer
    from cadrumo.application.modelo.workbench_operations import (
        ModeloCasillaHelpProjectionV1,
        ModeloEditPreflightProjectionV1,
        ModeloEditRenewalProjectionV1,
    )
    from cadrumo.application.modelo.workbench_projection import ModeloWorkbenchFormProjectionV1
    from cadrumo.application.operations.error_detail import OperationErrorDetailV1

    return [
        ("refusal-*.json", OperationErrorDetailV1),
        ("borrador-*.json", Borrador100ComparisonProjection),
        ("compare-*.json", _result_model("modelo.work.compare_taxation")),
        ("modelo-*.json", ModeloWorkbenchFormProjectionV1),
        ("help-*.json", ModeloCasillaHelpProjectionV1),
        ("declarations-*.json", ModeloDeclarationsListProjectionV1),
        ("preflight-*.json", ModeloEditPreflightProjectionV1),
        ("renew-*.json", ModeloEditRenewalProjectionV1),
        ("project-*.json", _result_model("modelo.project")),
        ("settlement-*.json", ModeloFormExportOffer),
        *((pattern, _result_model(definition_id)) for pattern, definition_id in _WRITE_ENVELOPES),
    ]


#: Operation envelopes by file pattern, with the definition whose public result each one is.
_WRITE_ENVELOPES: tuple[tuple[str, str], ...] = (
    ("create-[0-9]*.json", "modelo.work.create"),
    ("calculate-[0-9]*.json", "modelo.work.calculate"),
    ("iva-wallet-balance-*.json", "modelo.iva-wallet.balance"),
    ("iva-wallet-seed.json", "modelo.iva-wallet.seed"),
    ("iva-wallet-correct.json", "modelo.iva-wallet.correct"),
    ("iva-wallet-override.json", "modelo.iva-wallet.override"),
    ("apply-[0-9]*.json", "modelo.edit.apply"),
    ("apply-prerequisite-*.json", "modelo.edit.apply_prerequisite"),
    ("export-*.json", "modelo.export"),
    ("file-*.json", "modelo.work.file"),
    ("reconcile-*.json", "modelo.reconcile.import"),
    ("metadata-*.json", "modelo.work.metadata"),
    ("amendment-context-*.json", "modelo.work.amendment_context"),
    ("amend-[0-9]*.json", "modelo.work.amend"),
    ("disagreements-*.json", "modelo.work.disagreements"),
    ("accept-*.json", "modelo.work.accept_disagreement"),
    ("revoke-*.json", "modelo.work.revoke_disagreement"),
)


def _result_model(definition_id: str) -> type[BaseModel]:
    """The public result model a definition's contract registers."""
    registry = _registry()
    schema = registry.lookup_public_contract(definition_id).result_schema
    if schema is None:
        raise SystemExit(f"{definition_id} registers no result")
    return registry.lookup_public_schema_binding(schema).model_type


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
                model.model_validate_json(_compact(stored_envelope(path.parent, path.stem)))
            except ValueError as invalid:
                failures.append(f"{path.name} no longer validates as {model.__name__}: {str(invalid)[:200]}")
            # The window is never handed a file's place; neither is an envelope.
            failures.extend(f"{path.name} names a place on a machine: {text}" for text in _paths_in(path))
    sys.stderr.writelines(f"{failure}\n" for failure in failures)
    return 1 if failures else 0


def main() -> int:
    """Run one step for scripts/modelo-fixtures.mjs."""
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("step", choices=("contract", "bounds", "envelopes", "pack", "validate"))
    parser.add_argument(
        "directory", nargs="?", type=Path, default=FIXTURES, help="Where `envelopes` writes and `pack` stores."
    )
    args = parser.parse_args()
    if args.step == "contract":
        sys.stdout.write(render_contract())
        return 0
    if args.step == "bounds":
        sys.stdout.write(render_bounds())
        return 0
    if args.step == "envelopes":
        write_envelopes(args.directory)
        return 0
    if args.step == "pack":
        pack_envelopes(args.directory)
        return 0
    return validate()


if __name__ == "__main__":
    sys.exit(main())

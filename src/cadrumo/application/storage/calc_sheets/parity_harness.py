"""Per-modelo backend-spreadsheet parity harness.

For any `(modelo, period, year)` plus a synthetic operator-input set,
this harness drives the same calculation through three independent
paths and surfaces a per-casilla parity verdict. All three paths start
from the same :class:`RegistrySnapshot` so revision drift between them
is impossible.

1. **AEAT live oracle** (when a scenario file is provided) — the
   authoritative reference. Pre-captured outputs from AEAT's own
   simulator (Renta WEB Open, equivalent surfaces) stored under
   `corpus/parity_replays/...`. This pins the local registry against
   AEAT's truth.
2. **Local Decimal runtime** — `calculate_registry_snapshot` against
   the same registry snapshot. This is the "backend".
3. **Sheets** — the engine-emitted workbook applied to the operator's
   Drive, with operator inputs written into the `Entradas` tab and
   computed values read back from `Cálculos`. This is the
   "spreadsheet".

The harness returns a `ParityReport` summarising:

- `local_vs_aeat` — does the local registry match AEAT for the
  computed casillas the AEAT scenario captures?
- `sheets_vs_local` — does the Sheets workbook match the local
  registry across every computed casilla?
- `sheets_vs_aeat` — transitive proof that operator-facing Sheets
  output matches AEAT.

A clean run returns `verdict="all_match"`. Any divergence surfaces
per casilla so the operator can inspect which formula failed.
"""

from __future__ import annotations

import time
from collections.abc import Mapping
from datetime import date
from decimal import Decimal
from importlib import import_module
from typing import TYPE_CHECKING, Any, Literal, Protocol, cast

if TYPE_CHECKING:
    # The `googleapiclient._apis.*` namespace exists only inside the
    # `google-api-python-client-stubs` distribution. Some type-checkers
    # (pyrefly) only follow the project-local `search_path` and never see
    # site-packages stubs, so the typed forms below collapse to `Any` for
    # those tools while still giving pyrefly / ty / mypy the real shapes.
    from google.auth.credentials import Credentials
    SheetsResource = Any
    BatchUpdateValuesRequest = Any
    ValueRange = Any

from pydantic import BaseModel, Field

from ....core.casilla_id import CasillaId
from ....core.config import load_settings
from ....core.decimal.coercion import coerce_decimal
from ....core.models import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from ....core.period import Period
from ....domain.calculations.registry.casilla_membership import undeclared_casilla_ids
from ....domain.calculations.registry.formula_runtime import calculate_registry_snapshot
from ....domain.calculations.registry.ids import (
    BindingId,
    RelationId,
    RevisionId,
)
from ....domain.calculations.registry.relations import relation_source_requirements
from ....domain.calculations.registry.schema import RegistrySnapshot
from ....domain.calculations.registry.schema_input_kind import InputKind
from ....domain.period import calculation_filing_date
from ._parity_comparison import CasillaParity, collect_parity_rows, resolve_parity_verdict
from .engine import build_export_plan
from .errors import CalcSheetsParityError
from .layout import plan_layout
from .records import (
    OperatorInput,
    OperatorInputs,
    RelationValue,
    RelationValues,
    SheetCellAddress,
    SheetExportPlan,
)


class _SheetsDiscoveryBuilder(Protocol):
    """Typed boundary for the dynamic Sheets discovery factory."""

    def __call__(
        self,
        service_name: Literal["sheets"],
        version: Literal["v4"],
        *,
        credentials: Credentials,
        cache_discovery: bool,
    ) -> SheetsResource: ...


class ParityReport(BaseModel):
    """Aggregate parity verdict across every computed casilla.

    `verdict` collapses the per-casilla flags into a single answer:

    - `all_match` — every pair compared matches; no surface lies.
    - `divergence` — at least one pair disagrees somewhere. The
      `divergences` field lists offending casillas with both values
      for inspection.
    - `inconclusive` — the AEAT oracle is absent so we can only
      compare backend↔Sheets; that pair matches.
    """

    model_config = _STRICT_FROZEN

    modelo_id: str
    revision_id: RevisionId
    period: Period
    filing_year: int
    spreadsheet_id: str
    spreadsheet_url: str
    casillas: tuple[CasillaParity, ...]
    aeat_oracle_present: bool
    verdict: Literal["all_match", "divergence", "inconclusive"]
    divergences: tuple[CasillaParity, ...] = ()


class OperatorInputScenario(BaseModel):
    """Caller-supplied scenario for the parity harness.

    ``inputs_by_casilla_id`` maps canonical registry ``casilla.id`` values to
    input Decimals. ``expected_by_casilla_id`` mirrors that shape for
    AEAT-published expected outputs; an empty mapping is allowed and signals
    "no AEAT oracle available, fall back to backend↔Sheets only".
    """

    model_config = _STRICT_FROZEN

    inputs_by_casilla_id: Mapping[CasillaId, Decimal] = Field(default_factory=dict)
    bindings: Mapping[BindingId, Decimal] = Field(default_factory=dict)
    enum_bindings: Mapping[BindingId, str] = Field(default_factory=dict)
    relation_values: Mapping[RelationId, Decimal] = Field(default_factory=dict)
    expected_by_casilla_id: Mapping[CasillaId, Decimal] = Field(default_factory=dict)
    scenario_label: str = ""


def _build_operator_inputs(
    snapshot: RegistrySnapshot,
    scenario: OperatorInputScenario,
) -> tuple[OperatorInputs, dict[CasillaId, Decimal]]:
    """Translate canonical-id-keyed scenario inputs into sheet input rows."""
    _reject_unknown_scenario_casilla_ids(snapshot, scenario)
    operator_input_records: list[OperatorInput] = []
    inputs_by_id: dict[CasillaId, Decimal] = {}
    for casilla_id, value in scenario.inputs_by_casilla_id.items():
        operator_input_records.append(OperatorInput(casilla_id=casilla_id, value=value))
        inputs_by_id[casilla_id] = value
    return OperatorInputs(values=tuple(operator_input_records)), inputs_by_id


def _reject_unknown_scenario_casilla_ids(
    snapshot: RegistrySnapshot,
    scenario: OperatorInputScenario,
) -> None:
    unknown = (
        *undeclared_casilla_ids(snapshot.revision, scenario.inputs_by_casilla_id),
        *undeclared_casilla_ids(snapshot.revision, scenario.expected_by_casilla_id),
    )
    if unknown:
        raise CalcSheetsParityError(
            "scenario references unknown casilla ids",
            context={"unknown_count": len(unknown), "modelo": snapshot.modelo.id},
            translated_message="application.storage.calc_sheets.parity.errors.unknown_casilla_ids",
        )


def _build_relation_values(snapshot: RegistrySnapshot, scenario: OperatorInputScenario) -> RelationValues:
    relations_by_id = {relation.id: relation for relation in snapshot.revision.relations}
    requirements_by_relation = {
        relation_id: requirement
        for requirement in relation_source_requirements(
            snapshot.revision,
            filing_year=snapshot.filing_year,
            period=snapshot.period,
        )
        for relation_id in requirement.relation_ids
    }
    unknown_relation_ids = sorted(set(scenario.relation_values).difference(relations_by_id))
    if unknown_relation_ids:
        raise CalcSheetsParityError(
            "scenario references unknown relation ids",
            context={"unknown_count": len(unknown_relation_ids), "modelo": snapshot.modelo.id},
        )
    return RelationValues(
        values=tuple(
            RelationValue(
                relation=relation_id,
                value=value,
                source_modelo=(
                    requirements_by_relation[relation_id].source_modelo
                    if relation_id in requirements_by_relation
                    else relations_by_id[relation_id].source_modelo
                ),
                source_filing_year=(
                    requirements_by_relation[relation_id].filing_year
                    if relation_id in requirements_by_relation
                    else None
                ),
                source_periods=(
                    requirements_by_relation[relation_id].periods
                    if relation_id in requirements_by_relation
                    else relations_by_id[relation_id].source_periods
                ),
                source_casilla_ids=(
                    requirements_by_relation[relation_id].source_casilla_ids
                    if relation_id in requirements_by_relation
                    else (relations_by_id[relation_id].source_casilla_id,)
                ),
                legal_refs=(
                    requirements_by_relation[relation_id].legal_refs
                    if relation_id in requirements_by_relation
                    else relations_by_id[relation_id].legal_refs
                ),
                source_refs=(
                    requirements_by_relation[relation_id].source_refs
                    if relation_id in requirements_by_relation
                    else relations_by_id[relation_id].source_refs
                ),
            )
            for relation_id, value in scenario.relation_values.items()
        ),
    )


def _seed_inputs_into_sheet(
    sheets_service: SheetsResource,
    spreadsheet_id: str,
    plan: SheetExportPlan,
    scenario: OperatorInputScenario,
    snapshot: RegistrySnapshot,
) -> None:
    """Write every scenario input + binding value into its target cell.

    Three input families need explicit seeding:

    - Casilla inputs (``scenario.inputs_by_casilla_id``) → `Entradas` rows.
    - Numeric bindings (`scenario.bindings`) → binding rows the engine
      reserves in `Entradas` (one row per binding referenced by the
      revision's formulas).
    - Enum bindings (`scenario.enum_bindings`) → same binding rows,
      written as text (e.g. CCAA codes for `lookup_bracket_by_ccaa`).

    Relations and tariff parameter values are pre-stamped by the
    engine on plan apply, so they need no additional write here.
    """
    address_by_casilla_id = {cell.casilla_id: cell.address for cell in plan.value_cells if cell.casilla_id is not None}
    # Re-derive the binding-row addresses from the layout. The plan
    # carries the addresses on its value_cells but with no back-
    # reference to the binding id; the layout planner is the canonical
    # source for that mapping.
    filing_anchor = (
        calculation_filing_date(snapshot.filing_period)
        if snapshot.filing_period is not None
        else date(snapshot.filing_year, 12, 31)
    )
    layout = plan_layout(snapshot.revision, bracket_filter_date=filing_anchor)

    data: list[ValueRange] = []

    for casilla_id, value in scenario.inputs_by_casilla_id.items():
        data.append(_seed_value_range(address_by_casilla_id.get(casilla_id), format(value, "f"), input_kind="casilla"))
    for binding_id, value in scenario.bindings.items():
        data.append(_seed_value_range(layout.binding_cells.get(binding_id), format(value, "f"), input_kind="binding"))
    for binding_id, text in scenario.enum_bindings.items():
        data.append(_seed_value_range(layout.binding_cells.get(binding_id), text, input_kind="enum_binding"))

    if data:
        batch_body: BatchUpdateValuesRequest = {"valueInputOption": "USER_ENTERED", "data": data}
        sheets_service.spreadsheets().values().batchUpdate(
            spreadsheetId=spreadsheet_id,
            body=batch_body,
        ).execute()


def _seed_value_range(address: SheetCellAddress | None, value_text: str, *, input_kind: str) -> ValueRange:
    """Build the ``valueRange`` for one seed cell, refusing a missing seed anchor."""
    if address is None:
        raise _missing_seed_anchor(input_kind)
    return {"range": address.qualified(), "values": [[value_text]]}


def _missing_seed_anchor(input_kind: str) -> CalcSheetsParityError:
    return CalcSheetsParityError(
        "parity scenario input has no seed cell",
        context={"input_kind": input_kind},
        translated_message="application.storage.calc_sheets.parity.errors.seed_anchor_missing",
    )


def _sheets_recalc_delay_seconds() -> float:
    return load_settings().cadrumo_calc_sheets_recalc_delay_s


def _read_sheets_computed(
    sheets_service: SheetsResource,
    spreadsheet_id: str,
    plan: SheetExportPlan,
) -> dict[CasillaId, Decimal]:
    """Read every formula cell back from `Cálculos` and return its value."""
    if not plan.formula_cells:
        return {}
    # Sort formula cells by row so the resulting range is contiguous.
    sorted_cells = sorted(plan.formula_cells, key=lambda c: c.address.row)
    first_row = sorted_cells[0].address.row
    last_row = sorted_cells[-1].address.row
    column_letters = chr(ord("A") + sorted_cells[0].address.column - 1)
    rng = f"'Cálculos'!{column_letters}{first_row}:{column_letters}{last_row}"
    response = (
        sheets_service.spreadsheets()
        .values()
        .get(
            spreadsheetId=spreadsheet_id,
            range=rng,
            valueRenderOption="UNFORMATTED_VALUE",
        )
        .execute()
    )
    raw_rows = response.get("values", [])
    row_to_value: dict[int, Decimal] = {}
    for offset, row in enumerate(raw_rows):
        row_number = first_row + offset
        if not row:
            continue
        cell_value = row[0]
        if cell_value in (None, ""):
            continue
        coerced = coerce_decimal(cell_value)
        if coerced is None:
            # Sheets returned an error cell ("#ERROR!", "#N/A", ...).
            # Leave the row absent so the caller flags it as a
            # divergence rather than silently coercing.
            continue
        row_to_value[row_number] = coerced
    return {
        cell.casilla_id: row_to_value[cell.address.row] for cell in sorted_cells if cell.address.row in row_to_value
    }


def _compute_local(
    snapshot: RegistrySnapshot,
    inputs_by_id: Mapping[CasillaId, Decimal],
    scenario: OperatorInputScenario,
) -> Mapping[CasillaId, Decimal]:
    revision = snapshot.revision
    # Default every operator-input casilla absent from the scenario
    # to zero so the runtime contract (every non-computed casilla
    # has a value) holds without forcing the caller to enumerate them.
    full_inputs: dict[CasillaId, Decimal] = {}
    for casilla in revision.casillas:
        if casilla.input_kind == InputKind.COMPUTED:
            continue
        if casilla.input_kind == InputKind.INFORMATIONAL:
            continue
        full_inputs[casilla.id] = inputs_by_id.get(casilla.id, Decimal("0"))
    binding_defaults = {binding.id: scenario.bindings.get(binding.id, Decimal("0")) for binding in revision.bindings}
    relation_defaults = {
        relation.id: scenario.relation_values.get(relation.id, Decimal("0")) for relation in revision.relations
    }
    result = calculate_registry_snapshot(
        snapshot,
        inputs=full_inputs,
        date_context={
            "filing_period": (
                calculation_filing_date(snapshot.filing_period)
                if snapshot.filing_period is not None
                else date(snapshot.filing_year, 12, 31)
            ),
        },
        binding_values=binding_defaults,
        enum_binding_values=dict(scenario.enum_bindings),
        relation_values=relation_defaults,
        # The parity harness drives a scenario's operator inputs, not a filing
    )
    return result.values


def verify_modelo_parity(
    snapshot: RegistrySnapshot,
    scenario: OperatorInputScenario,
    *,
    credentials: Credentials,
    root_folder_id: str,
) -> ParityReport:
    """Run the full three-way parity verification for one modelo+period.

    Args:
        snapshot: The :class:`RegistrySnapshot` whose calculation surface is verified.
        scenario: :class:`OperatorInputScenario` supplying operator inputs and
            relation overrides for the run.
        credentials: Google API credentials used by the calc-sheets apply path
            to read/write the per-modelo spreadsheet.
        root_folder_id: Google Drive folder id under which the parity
            spreadsheet is created or updated.

    Returns a :class:`ParityReport`.

    Side effects:
        - Idempotently creates (or updates) a `cadrumo-vault/calc-sheets/
          {modelo}-{period}-{year}/AEAT … {modelo} {period} {year}`
          spreadsheet under the operator's Drive root.
        - Writes the scenario's operator inputs into `Entradas` and
          relations into `Tarifas`.
        - Reads every formula cell back from `Cálculos`.

    Does NOT mutate any local persistence beyond the registry
    snapshot's process-local cache. The local Decimal runtime is
    invoked once and consulted only for comparison.
    """
    from ....adapters.outbound.google.calc_sheets_apply import apply_export_plan

    operator_inputs, inputs_by_id = _build_operator_inputs(snapshot, scenario)
    relation_values = _build_relation_values(snapshot, scenario)

    plan = build_export_plan(
        snapshot,
        operator_inputs=operator_inputs,
        relation_values=relation_values,
    )
    apply_result = apply_export_plan(
        plan,
        credentials=credentials,
        root_folder_id=root_folder_id,
    )

    # The apply adapter writes the value cells the engine carries on
    # the plan, but `Entradas` value cells for non-supplied operator
    # inputs are emitted as blank. We re-write the scenario inputs
    # explicitly to handle the case where another caller had previously
    # set them to stale values.
    # google-api-python-client publishes a large overload set whose generic
    # fallback contains unknowns; this adapter pins the exact service/version
    # contract consumed by the parity harness at the dynamic boundary.
    discovery_module = import_module("googleapiclient.discovery")
    # CAST-RATIONALE-GOOGLE-DISCOVERY-BUILD: discovery is an optional,
    # dynamically imported third-party module; the local protocol above pins
    # the exact Sheets factory contract consumed by this harness.
    # nosemgrep: no-cast-in-domain-application
    discovery_builder = cast(_SheetsDiscoveryBuilder, discovery_module.build)
    sheets_service = discovery_builder("sheets", "v4", credentials=credentials, cache_discovery=False)
    _seed_inputs_into_sheet(sheets_service, apply_result.spreadsheet_id, plan, scenario, snapshot)

    # Give Sheets time to propagate dependent-cell recalculation.
    # Sheets recalcs are synchronous in practice but a small delay
    # keeps the harness honest under network jitter.
    time.sleep(_sheets_recalc_delay_seconds())

    sheets_values = _read_sheets_computed(sheets_service, apply_result.spreadsheet_id, plan)
    local_values = _compute_local(snapshot, inputs_by_id, scenario)

    aeat_present = bool(scenario.expected_by_casilla_id)
    casillas, divergences = collect_parity_rows(
        casillas=snapshot.revision.casillas,
        local_values=local_values,
        sheets_values=sheets_values,
        aeat_values=scenario.expected_by_casilla_id,
        inputs_by_id=inputs_by_id,
    )
    verdict = resolve_parity_verdict(divergences=divergences, aeat_present=aeat_present)

    return ParityReport(
        modelo_id=snapshot.modelo.id,
        revision_id=snapshot.revision.id,
        period=Period.from_year_and_code(snapshot.filing_year, snapshot.period),
        filing_year=snapshot.filing_year,
        spreadsheet_id=apply_result.spreadsheet_id,
        spreadsheet_url=apply_result.spreadsheet_url,
        casillas=tuple(casillas),
        aeat_oracle_present=aeat_present,
        verdict=verdict,
        divergences=tuple(divergences),
    )


__all__ = [
    "OperatorInputScenario",
    "ParityReport",
    "verify_modelo_parity",
]

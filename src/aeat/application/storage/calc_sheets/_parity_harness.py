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
from typing import TYPE_CHECKING, Any, Literal

if TYPE_CHECKING:
    # The `googleapiclient._apis.*` namespace exists only inside the
    # `google-api-python-client-stubs` distribution. Some type-checkers
    # (pyrefly) only follow the project-local `search_path` and never see
    # site-packages stubs, so the typed forms below collapse to `Any` for
    # those tools while still giving pyright / ty / mypy the real shapes.
    SheetsResource = Any
    BatchUpdateValuesRequest = Any
    ValueRange = Any

from pydantic import BaseModel, Field

from ....core import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from ....core.config import load_settings
from ....core.decimal import coerce_decimal
from ....domain.calculations.registry import (
    CasillaDefinition,
    CasillaId,
    InputKind,
    RegistrySnapshot,
    RevisionId,
    calculate_registry_snapshot,
)
from ._engine import build_export_plan
from ._errors import CalcSheetsParityError
from ._layout import plan_layout
from ._records import (
    OperatorInput,
    OperatorInputs,
    RelationValue,
    RelationValues,
    SheetExportPlan,
)


class CasillaParity(BaseModel):
    """Per-casilla parity verdict across three calculation surfaces."""

    model_config = _STRICT_FROZEN

    casilla_id: CasillaId
    casilla_number: str
    label: str
    local: Decimal | None = None
    sheets: Decimal | None = None
    aeat: Decimal | None = None
    sheets_vs_local: bool | None = None
    local_vs_aeat: bool | None = None
    sheets_vs_aeat: bool | None = None


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
    period: str
    filing_year: int
    spreadsheet_id: str
    spreadsheet_url: str
    casillas: tuple[CasillaParity, ...]
    aeat_oracle_present: bool
    verdict: Literal["all_match", "divergence", "inconclusive"]
    divergences: tuple[CasillaParity, ...] = ()


class OperatorInputScenario(BaseModel):
    """Caller-supplied scenario for the parity harness.

    `inputs_by_number` maps casilla *number* (as a string, exactly as
    AEAT writes it — leading zeros preserved) to the input Decimal.
    `expected_by_number` mirrors that shape for AEAT-published
    expected outputs; an empty mapping is allowed and signals "no
    AEAT oracle available, fall back to backend↔Sheets only".
    """

    model_config = _STRICT_FROZEN

    inputs_by_number: Mapping[str, Decimal] = Field(default_factory=dict)
    bindings: Mapping[str, Decimal] = Field(default_factory=dict)
    enum_bindings: Mapping[str, str] = Field(default_factory=dict)
    relation_values: Mapping[str, Decimal] = Field(default_factory=dict)
    expected_by_number: Mapping[str, Decimal] = Field(default_factory=dict)
    scenario_label: str = ""


def _build_operator_inputs(
    snapshot: RegistrySnapshot,
    scenario: OperatorInputScenario,
) -> tuple[OperatorInputs, dict[CasillaId, Decimal]]:
    """Translate casilla-number-keyed scenario inputs into casilla-id-keyed."""
    by_number = {casilla.number: casilla.id for casilla in snapshot.revision.casillas}
    operator_input_records: list[OperatorInput] = []
    inputs_by_id: dict[CasillaId, Decimal] = {}
    unknown: list[str] = []
    for number, value in scenario.inputs_by_number.items():
        casilla_id = by_number.get(number)
        if casilla_id is None:
            unknown.append(number)
            continue
        operator_input_records.append(OperatorInput(casilla=casilla_id, value=value))
        inputs_by_id[casilla_id] = value
    if unknown:
        raise CalcSheetsParityError(
            "scenario references unknown casilla numbers",
            context={"unknown_count": len(unknown), "modelo": snapshot.modelo.id},
            translated_message="application.storage.calc_sheets.parity.errors.unknown_casilla_numbers",
        )
    return OperatorInputs(values=tuple(operator_input_records)), inputs_by_id


def _build_relation_values(scenario: OperatorInputScenario) -> RelationValues:
    return RelationValues(
        values=tuple(RelationValue(relation=key, value=value) for key, value in scenario.relation_values.items()),
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

    - Casilla inputs (`scenario.inputs_by_number`) → `Entradas` rows.
    - Numeric bindings (`scenario.bindings`) → binding rows the engine
      reserves in `Entradas` (one row per binding referenced by the
      revision's formulas).
    - Enum bindings (`scenario.enum_bindings`) → same binding rows,
      written as text (e.g. CCAA codes for `lookup_bracket_by_ccaa`).

    Relations and tariff parameter values are pre-stamped by the
    engine on plan apply, so they need no additional write here.
    """
    by_number = {casilla.number: casilla.id for casilla in snapshot.revision.casillas}
    address_by_casilla = {cell.casilla: cell.address for cell in plan.value_cells if cell.casilla is not None}
    # Re-derive the binding-row addresses from the layout. The plan
    # carries the addresses on its value_cells but with no back-
    # reference to the binding id; the layout planner is the canonical
    # source for that mapping.
    filing_anchor = date(snapshot.filing_year, 12, 31)
    layout = plan_layout(snapshot.revision, bracket_filter_date=filing_anchor)

    data: list[ValueRange] = []

    for number, value in scenario.inputs_by_number.items():
        casilla_id = by_number.get(number)
        if casilla_id is None:
            raise _missing_seed_anchor("casilla")
        address = address_by_casilla.get(casilla_id)
        if address is None:
            raise _missing_seed_anchor("casilla")
        data.append({"range": address.qualified(), "values": [[format(value, "f")]]})

    for binding_id, value in scenario.bindings.items():
        address = layout.binding_cells.get(binding_id)
        if address is None:
            raise _missing_seed_anchor("binding")
        data.append({"range": address.qualified(), "values": [[format(value, "f")]]})

    for binding_id, text in scenario.enum_bindings.items():
        address = layout.binding_cells.get(binding_id)
        if address is None:
            raise _missing_seed_anchor("enum_binding")
        data.append({"range": address.qualified(), "values": [[text]]})

    if data:
        batch_body: BatchUpdateValuesRequest = {"valueInputOption": "USER_ENTERED", "data": data}
        sheets_service.spreadsheets().values().batchUpdate(
            spreadsheetId=spreadsheet_id,
            body=batch_body,
        ).execute()


def _missing_seed_anchor(input_kind: str) -> CalcSheetsParityError:
    return CalcSheetsParityError(
        "parity scenario input has no seed cell",
        context={"input_kind": input_kind},
        translated_message="application.storage.calc_sheets.parity.errors.seed_anchor_missing",
    )


def _sheets_recalc_delay_seconds() -> float:
    return load_settings().aeat_calc_sheets_recalc_delay_s


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
    return {cell.casilla: row_to_value[cell.address.row] for cell in sorted_cells if cell.address.row in row_to_value}


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
        date_context={"filing_period": date(snapshot.filing_year, 12, 31)},
        binding_values=binding_defaults,
        enum_binding_values=dict(scenario.enum_bindings),
        relation_values=relation_defaults,
    )
    return result.values


def verify_modelo_parity(
    snapshot: RegistrySnapshot,
    scenario: OperatorInputScenario,
    *,
    credentials: object,
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
        - Idempotently creates (or updates) a `aeat-vault/calc-sheets/
          {modelo}-{period}-{year}/AEAT … {modelo} {period} {year}`
          spreadsheet under the operator's Drive root.
        - Writes the scenario's operator inputs into `Entradas` and
          relations into `Tarifas`.
        - Reads every formula cell back from `Cálculos`.

    Does NOT mutate any local persistence beyond the registry
    snapshot's process-local cache. The local Decimal runtime is
    invoked once and consulted only for comparison.
    """
    from ....adapters.outbound.google._calc_sheets_apply import apply_export_plan

    operator_inputs, inputs_by_id = _build_operator_inputs(snapshot, scenario)
    relation_values = _build_relation_values(scenario)

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
    from googleapiclient.discovery import build  # local import per project convention

    sheets_service = build("sheets", "v4", credentials=credentials, cache_discovery=False)
    _seed_inputs_into_sheet(sheets_service, apply_result.spreadsheet_id, plan, scenario, snapshot)

    # Give Sheets time to propagate dependent-cell recalculation.
    # Sheets recalcs are synchronous in practice but a small delay
    # keeps the harness honest under network jitter.
    time.sleep(_sheets_recalc_delay_seconds())

    sheets_values = _read_sheets_computed(sheets_service, apply_result.spreadsheet_id, plan)
    local_values = _compute_local(snapshot, inputs_by_id, scenario)

    aeat_present = bool(scenario.expected_by_number)
    casillas, divergences = _collect_parity_rows(
        snapshot=snapshot,
        scenario=scenario,
        local_values=local_values,
        sheets_values=sheets_values,
        inputs_by_id=inputs_by_id,
    )
    verdict = _resolve_parity_verdict(divergences=divergences, aeat_present=aeat_present)

    return ParityReport(
        modelo_id=snapshot.modelo.id,
        revision_id=snapshot.revision.id,
        period=snapshot.period,
        filing_year=snapshot.filing_year,
        spreadsheet_id=apply_result.spreadsheet_id,
        spreadsheet_url=apply_result.spreadsheet_url,
        casillas=tuple(casillas),
        aeat_oracle_present=aeat_present,
        verdict=verdict,
        divergences=tuple(divergences),
    )


def _collect_parity_rows(
    *,
    snapshot: RegistrySnapshot,
    scenario: OperatorInputScenario,
    local_values: Mapping[CasillaId, Decimal],
    sheets_values: Mapping[CasillaId, Decimal],
    inputs_by_id: Mapping[CasillaId, Decimal],
) -> tuple[list[CasillaParity], list[CasillaParity]]:
    """Build (every-casilla parity row list, divergent-only sublist) for the three-way comparison."""
    casillas: list[CasillaParity] = []
    divergences: list[CasillaParity] = []
    for casilla in snapshot.revision.casillas:
        if casilla.input_kind != InputKind.COMPUTED:
            continue
        local = local_values.get(casilla.id)
        sheets_v = sheets_values.get(casilla.id)
        aeat_v = scenario.expected_by_number.get(casilla.number)
        row = _build_casilla_parity_row(casilla, local=local, sheets_v=sheets_v, aeat_v=aeat_v)
        casillas.append(row)
        if _is_parity_divergent(row, sheets_v=sheets_v, local=local, inputs_by_id=inputs_by_id):
            divergences.append(row)
    return casillas, divergences


def _build_casilla_parity_row(
    casilla: CasillaDefinition,
    *,
    local: Decimal | None,
    sheets_v: Decimal | None,
    aeat_v: Decimal | None,
) -> CasillaParity:
    """Build one ``CasillaParity`` row with the three pairwise-equality booleans pre-resolved."""
    sheets_vs_local = sheets_v == local if sheets_v is not None and local is not None else None
    local_vs_aeat = local == aeat_v if aeat_v is not None and local is not None else None
    sheets_vs_aeat = sheets_v == aeat_v if aeat_v is not None and sheets_v is not None else None
    return CasillaParity(
        casilla_id=casilla.id,
        casilla_number=casilla.number,
        label=casilla.label,
        local=local,
        sheets=sheets_v,
        aeat=aeat_v,
        sheets_vs_local=sheets_vs_local,
        local_vs_aeat=local_vs_aeat,
        sheets_vs_aeat=sheets_vs_aeat,
    )


def _is_parity_divergent(
    row: CasillaParity,
    *,
    sheets_v: Decimal | None,
    local: Decimal | None,
    inputs_by_id: Mapping[CasillaId, Decimal],
) -> bool:
    """A parity row is divergent if any pairwise comparison failed, or Sheets failed to compute.

    The two divergence rules: (a) any pairwise comparison evaluated to
    False; (b) the Sheets cell is blank for a non-input casilla while
    the local engine produced a value (a Sheets formula failure the
    operator must investigate).
    """
    if sheets_v is None and local is not None and row.casilla_id not in inputs_by_id:
        return True
    return False in (row.sheets_vs_local, row.local_vs_aeat, row.sheets_vs_aeat)


def _resolve_parity_verdict(
    *,
    divergences: list[CasillaParity],
    aeat_present: bool,
) -> Literal["all_match", "divergence", "inconclusive"]:
    """Resolve the top-level verdict from the divergences list and AEAT-oracle presence."""
    if divergences:
        return "divergence"
    if aeat_present:
        return "all_match"
    return "inconclusive"


__all__ = [
    "CasillaParity",
    "OperatorInputScenario",
    "ParityReport",
    "verify_modelo_parity",
]

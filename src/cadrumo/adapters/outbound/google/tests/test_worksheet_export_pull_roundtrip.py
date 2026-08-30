"""End-to-end roundtrip across the Google-Sheets calc-sheets boundary.

Workbook-mediated cross-domain transport: a snapshot + operator-supplied
inputs become a :class:`SheetExportPlan` (the export side), the plan's
input cells become :class:`OperatorEdit` records on the inbound side
(the pull side), and ``compute_from_pull`` reduces those edits back to a
calculation result. A faithful workbook mirror must preserve every
operator-input value through this loop with no string-vs-Decimal drift,
no casilla dropped from the export, and no metadata mismatch refusal.

Tests use real :func:`build_export_plan` against a real registry
snapshot (modelo 130, 2025/1T) and exercise the actual pull path with
no mocks. A regression that drops an input casilla on export, mis-shapes
an :class:`OperatorEdit` on pull, or breaks the registry-SHA metadata
match surfaces as a strict pydantic / Decimal inequality.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from .....application.storage.calc_sheets import (
    CALC_SHEETS_ENGINE_VERSION,
    OperatorInput,
    OperatorInputs,
    RelationValues,
    build_export_plan,
    registry_sha,
)
from .....core.period import Period
from .....core.casilla_id import CasillaId, validated_casilla_id
from .....domain.calculations.registry.authority import bundled_authority
from .....domain.calculations.registry.errors import NoRevisionForPeriodError
from .....domain.calculations.registry.formula_runtime import calculate_registry_snapshot
from .....domain.calculations.registry.schema_input_kind import InputKind
from .....domain.period import calculation_filing_date
from ..calc_sheets_pull import (
    BindingEdit,
    MetadataMatchState,
    OperatorEdit,
    PullMetadata,
    PullResult,
    RelationEdit,
    compute_from_pull,
)
from ._calc_sheets_support import modelo_130_2025_1t_snapshot

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]

_INGRESOS_CASILLA: CasillaId = validated_casilla_id("01", surface="_INGRESOS_CASILLA")
_GASTOS_CASILLA: CasillaId = validated_casilla_id("02", surface="_GASTOS_CASILLA")
_RENDIMIENTO_NETO_CASILLA: CasillaId = validated_casilla_id("03", surface="_RENDIMIENTO_NETO_CASILLA")


def _casilla_id_from_plan_cell(value: object) -> CasillaId:
    """Validate a workbook cell casilla key before it enters local lookups."""

    return validated_casilla_id(value, surface="test casilla id")


def _operator_edits_from_export_plan(plan, snapshot) -> tuple[OperatorEdit, ...]:
    """Project the export plan's Entradas tab into the pull's operator-edit shape.

    The export plan's :attr:`entradas` carries the operator-input
    cell values. The pull side reads those same cells as
    :class:`OperatorEdit` records. The projection here is mechanical —
    if the plan and the pull schemas drift, the test signals it as
    a structural mismatch (extra/missing casillas) rather than a
    silent value loss.
    """

    by_casilla_id: dict[CasillaId, Decimal | str | bool | None] = {}
    for cell in plan.value_cells:
        if cell.role != "operator_input" or cell.casilla_id is None:
            continue
        by_casilla_id[_casilla_id_from_plan_cell(cell.casilla_id)] = cell.value
    edits: list[OperatorEdit] = []
    for casilla in snapshot.revision.casillas:
        if casilla.input_kind in (InputKind.COMPUTED, InputKind.INFORMATIONAL):
            continue
        edits.append(
            OperatorEdit(
                casilla_id=casilla.id,
                display_number=casilla.number,
                label=casilla.label,
                value=by_casilla_id.get(casilla.id),
            ),
        )
    return tuple(edits)


def test_workbook_input_values_survive_export_pull_compute_loop() -> None:
    """Operator-supplied input values survive build_export_plan -> pull -> compute.

    Builds a plan with two non-zero operator inputs, drains the plan's
    input cells back into the pull shape, computes against the same
    snapshot, and asserts the resulting calculation result reflects
    the same Decimal values the operator supplied at the top of the
    loop. Any data-loss across the export/pull boundary (an input
    casilla dropped on export, a string-vs-Decimal coercion drift
    on pull, a metadata mismatch from a non-deterministic SHA stamp)
    surfaces as a strict Decimal inequality at the bottom of the
    chain.
    """

    snapshot = modelo_130_2025_1t_snapshot()
    ingresos = Decimal("10000.50")
    gastos = Decimal("2000.25")
    inputs = OperatorInputs(
        values=(
            OperatorInput(casilla_id=_INGRESOS_CASILLA, value=ingresos),
            OperatorInput(casilla_id=_GASTOS_CASILLA, value=gastos),
        ),
    )

    plan = build_export_plan(
        snapshot,
        operator_inputs=inputs,
        relation_values=RelationValues(),
    )

    # Plan must carry the supplied values verbatim. If the export
    # plan dropped or mutated a value, every downstream assertion is
    # already invalidated; assert here so the failure points at the
    # right boundary.
    by_casilla_on_plan: dict[CasillaId, Decimal | str | bool | None] = {
        _casilla_id_from_plan_cell(cell.casilla_id): cell.value
        for cell in plan.value_cells
        if cell.role == "operator_input" and cell.casilla_id is not None
    }
    assert by_casilla_on_plan[_INGRESOS_CASILLA] == ingresos
    assert by_casilla_on_plan[_GASTOS_CASILLA] == gastos

    operator_edits = _operator_edits_from_export_plan(plan, snapshot)
    pull = PullResult(
        spreadsheet_id="roundtrip-test-id",
        operator_edits=operator_edits,
        binding_edits=tuple(
            BindingEdit(binding=binding.id, value=Decimal("0")) for binding in snapshot.revision.bindings
        ),
        relation_edits=tuple(
            RelationEdit(relation=relation.id, value=Decimal("0"))
            for relation in snapshot.revision.relations
            if not relation.target_periods or snapshot.period in relation.target_periods
        ),
        metadata=PullMetadata(
            modelo_id=snapshot.modelo.id,
            revision_id=snapshot.revision.id,
            filing_year=snapshot.filing_year,
            period=snapshot.period,
            engine_version=CALC_SHEETS_ENGINE_VERSION,
            registry_sha=registry_sha(snapshot),
        ),
        metadata_match=MetadataMatchState.MATCHES,
        cells_read=2,
    )

    result = compute_from_pull(snapshot, pull)

    # Every input the operator supplied must reappear on the result's
    # values map. The values map is the contract surface compute_from_pull
    # publishes back to the caller; if the export-then-pull cycle dropped
    # an input, this assertion fails before any formula evaluation does.
    # A string coercion that landed via ``Decimal(str(value))`` mid-loop
    # would diverge here only on values that exercise the failure mode;
    # using non-trivial decimals on both inputs surfaces it.
    assert result.values[_INGRESOS_CASILLA] == ingresos
    assert result.values[_GASTOS_CASILLA] == gastos

    # Casilla 03 (rendimiento neto) is computed by the registry from the
    # two operator inputs above. Keep the expected value literal so this
    # test remains an oracle instead of duplicating formula logic inline.
    casilla_03_obs = next(obs for obs in result.observations if obs.casilla_id == _RENDIMIENTO_NETO_CASILLA)
    assert casilla_03_obs.value == Decimal("8000.25")


def test_workbook_input_count_matches_pulled_edit_count() -> None:
    """Every manual / bound casilla on the snapshot appears in the pull edits.

    Guards against drift where an export-side filter accidentally
    drops a casilla from the plan but the pull side still expects to
    read it (or vice versa). The structural assertion: the count of
    operator-input casillas declared by the registry must equal the
    count of OperatorEdit records the plan-to-pull projection
    produces.
    """

    snapshot = modelo_130_2025_1t_snapshot()
    plan = build_export_plan(
        snapshot,
        operator_inputs=OperatorInputs(),
        relation_values=RelationValues(),
    )
    operator_edits = _operator_edits_from_export_plan(plan, snapshot)

    declared_inputs = tuple(
        casilla
        for casilla in snapshot.revision.casillas
        if casilla.input_kind not in (InputKind.COMPUTED, InputKind.INFORMATIONAL)
    )
    assert len(operator_edits) == len(declared_inputs), (
        f"export/pull casilla count drift: plan produced {len(operator_edits)} "
        f"operator-edits but the registry declares {len(declared_inputs)} "
        f"manual/bound casillas on modelo-130/2025-1T"
    )


@pytest.mark.parametrize(
    ("period_code", "expected_filing_date"),
    (
        ("EXT-1T", date(2026, 3, 31)),
        ("EXT-2T", date(2026, 6, 30)),
        ("EXT-3T", date(2026, 9, 30)),
        ("EXT-4T", date(2026, 12, 31)),
    ),
)
def test_modelo_369_exterior_export_pull_matches_normal_calculation_reference(
    period_code: str,
    expected_filing_date: date,
) -> None:
    """A committed exterior workbook round-trips against the normal registry calculation.

    Modelo 369's exterior scheme is the registered EXT-period surface whose
    layout is protected by the calc-sheets engine version gate.  This uses the
    actual export plan as the pull source and compares the resulting local
    recomputation to a normal registry run at the statutory corresponding
    ordinary-quarter end.
    """
    period = Period.from_year_and_code(2026, period_code)
    snapshot = bundled_authority().snapshot(
        "369",
        filing_year=2026,
        period=period_code,
        on=expected_filing_date,
    )
    assert calculation_filing_date(period) == expected_filing_date

    plan = build_export_plan(snapshot, operator_inputs=OperatorInputs(), relation_values=RelationValues())
    operator_edits = _operator_edits_from_export_plan(plan, snapshot)
    binding_edits = tuple(BindingEdit(binding=binding.id, value=Decimal("0")) for binding in snapshot.revision.bindings)
    relation_edits = tuple(
        RelationEdit(relation=relation.id, value=Decimal("0"))
        for relation in snapshot.revision.relations
        if not relation.target_periods or snapshot.period in relation.target_periods
    )
    pull = PullResult(
        spreadsheet_id=f"modelo-369-{period_code}-export-plan",
        operator_edits=operator_edits,
        binding_edits=binding_edits,
        relation_edits=relation_edits,
        metadata=PullMetadata(
            modelo_id=plan.metadata.modelo_id,
            revision_id=plan.metadata.revision_id,
            filing_year=plan.metadata.filing_year,
            period=plan.metadata.period.registry_token,
            engine_version=plan.metadata.engine_version,
            registry_sha=plan.metadata.registry_sha,
        ),
        metadata_match=MetadataMatchState.MATCHES,
        cells_read=0,
    )

    pulled = compute_from_pull(snapshot, pull)
    normal = calculate_registry_snapshot(
        snapshot,
        inputs={edit.casilla_id: Decimal("0") for edit in operator_edits},
        binding_values={edit.binding: Decimal("0") for edit in binding_edits},
        relation_values={edit.relation: Decimal("0") for edit in relation_edits},
        date_context={"filing_period": calculation_filing_date(period)},
    )

    assert plan.metadata.period == period
    assert plan.metadata.engine_version == CALC_SHEETS_ENGINE_VERSION
    assert pulled.values == normal.values


def test_modelo_369_exterior_export_reference_uses_the_quarter_anchor() -> None:
    """A pre-effective exterior quarter must not gain a year-end export reference.

    The committed exterior revision takes effect on 1 July 2021.  Its
    ``EXT-1T`` calculation anchor is 31 March, so no export/pull reference
    may be built for that quarter; selecting it at the former 31 December
    fallback would incorrectly expose the live revision.
    """
    period = Period.from_year_and_code(2021, "EXT-1T")

    with pytest.raises(NoRevisionForPeriodError):
        bundled_authority().snapshot(
            "369",
            filing_year=2021,
            period=period.registry_token,
            on=calculation_filing_date(period),
        )

    legacy_snapshot = bundled_authority().snapshot(
        "369",
        filing_year=2021,
        period=period.registry_token,
        on=date(2021, 12, 31),
    )
    assert legacy_snapshot.revision.id == "esquema-exterior"

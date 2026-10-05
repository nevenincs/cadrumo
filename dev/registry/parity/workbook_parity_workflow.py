"""Coordinate registry-to-workbook comparisons and verification reports."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import TYPE_CHECKING

from cadrumo.core.casilla_id import CasillaId
from cadrumo.domain.calculations.registry.casilla_membership import declared_casilla_ids
from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.formula_runtime import calculate_registry_snapshot
from cadrumo.domain.calculations.registry.ids import (
    BindingId,
    LegalRefId,
    RelationId,
    SourceRefId,
    WorkbookOutputId,
)
from cadrumo.domain.calculations.registry.schema import RegistrySnapshot

from .workbook_parity_execution import _execution_runner_availability, detect_workbook_runner
from .workbook_parity_libreoffice import run_workbook_with_libreoffice
from .workbook_parity_models import (
    SyntheticInputSet,
    WorkbookArtefactReport,
    WorkbookBackendVerificationReport,
    WorkbookCellRef,
    WorkbookParityComparison,
    WorkbookParityRunReport,
    WorkbookRunnerAvailability,
)
from .workbook_parity_output_ids import (
    _missing_or_empty_output_refs,
    _raise_output_id_mismatch,
    _require_matching_output_ids,
    _workbook_output_id_set,
)
from .workbook_parity_scanning import (
    _CELL_REF_VALUE_PATTERN,
    WorkbookScanOptions,
    _build_modelo_coverage,
    assert_workbook_scan_clean,
    discover_workbooks,
    inventory_workbook_coverage,
)
from .workbook_parity_types import (
    ParityStatus,
    WorkbookKind,
    WorkbookScanStatus,
)

if TYPE_CHECKING:
    # Annotation-only: ``from __future__ import annotations`` above makes every
    # annotation a string, so these need not exist at runtime. openpyxl is one of
    # the heaviest third-party imports in the tree and this module is imported
    # eagerly by the registry facade, so the symbols that ARE needed at runtime
    # (``load_workbook``, ``Tokenizer``, and the ``TokenizerError`` /
    # ``InvalidFileException`` handler types) are imported inside the functions
    # that use them -- a taxpayer calculation must not load a spreadsheet engine.
    pass


def run_registry_workbook_parity(
    *,
    snapshot: RegistrySnapshot,
    synthetic_input: SyntheticInputSet,
    workbook_path: Path,
    workbook: WorkbookArtefactReport,
    output_cells: Mapping[WorkbookOutputId, WorkbookCellRef],
    registry_outputs: Mapping[WorkbookOutputId, CasillaId],
    date_context: Mapping[str, date],
    relation_values: Mapping[RelationId, Decimal] | None = None,
    tolerance: Decimal = Decimal("0"),
    executable: str | None = None,
) -> WorkbookParityRunReport:
    """Execute one registry-vs-workbook parity comparison and return a :class:`WorkbookParityRunReport`.

    Args:
        snapshot: The :class:`RegistrySnapshot` providing the registry formulas to compare.
        synthetic_input: :class:`SyntheticInputSet` whose values seed both
            sides of the comparison (operator inputs and registry bindings).
        workbook_path: Path to the AEAT calculation workbook to execute.
        workbook: :class:`WorkbookArtefactReport` describing the workbook
            artefact; must report kind ``FORMULA_FORM``.
        output_cells: Mapping of registry output id to the workbook
            :class:`WorkbookCellRef` carrying its computed value.
        registry_outputs: Mapping of workbook output ids to registry output
            ids, used to align both sides of the comparison.
        date_context: Date-axis context forwarded to the registry formula
            runtime.
        relation_values: Optional resolved registry relation values seeded
            into the registry runtime.
        tolerance: Absolute Decimal tolerance accepted between workbook and
            registry outputs; defaults to ``Decimal("0")``.
        executable: Optional LibreOffice executable override used when
            converting binary XLS workbooks.
    """
    if workbook.workbook_kind != WorkbookKind.FORMULA_FORM:
        raise RegistryValidationError(
            f"workbook {workbook.path!r} is {workbook.workbook_kind!r}, not an executable calculation oracle",
        )
    _require_matching_output_ids("workbook output_cells", output_cells, "registry_outputs", registry_outputs)
    workbook_inputs, registry_inputs, registry_binding_values = _collect_synthetic_inputs(snapshot, synthetic_input)

    workbook_values = run_workbook_with_libreoffice(
        workbook_path,
        inputs=workbook_inputs,
        outputs=output_cells,
        executable=executable,
    )
    registry_result = calculate_registry_snapshot(
        snapshot,
        inputs=registry_inputs,
        date_context=date_context,
        binding_values=registry_binding_values,
        relation_values=relation_values,
    )
    missing_outputs = sorted(set(registry_outputs.values()).difference(registry_result.values))
    if missing_outputs:
        raise RegistryValidationError(f"registry parity outputs are missing calculated casillas: {missing_outputs!r}")
    registry_values: dict[WorkbookOutputId, Decimal | int | str | bool | None] = {
        output_id: registry_result.values[casilla_id] for output_id, casilla_id in registry_outputs.items()
    }
    legal_refs, source_refs = _registry_output_references(snapshot, registry_outputs)
    runner = _execution_runner_availability(executable)
    return compare_registry_to_workbook(
        synthetic_input=synthetic_input,
        workbook=workbook,
        runner=runner,
        expected_workbook_values=workbook_values,
        actual_registry_values=registry_values,
        output_cells=output_cells,
        registry_snapshot_id=(f"{snapshot.modelo.id}:{snapshot.revision.id}:{snapshot.filing_year}:{snapshot.period}"),
        legal_refs=legal_refs,
        source_refs=source_refs,
        tolerance=tolerance,
    )


def _collect_synthetic_inputs(
    snapshot: RegistrySnapshot,
    synthetic_input: SyntheticInputSet,
) -> tuple[
    dict[WorkbookCellRef, Decimal | int | str | bool],
    dict[CasillaId, Decimal],
    dict[BindingId, Decimal],
]:
    workbook_inputs: dict[WorkbookCellRef, Decimal | int | str | bool] = {}
    registry_inputs: dict[CasillaId, Decimal] = {}
    registry_binding_values: dict[BindingId, Decimal] = {}
    casilla_ids = declared_casilla_ids(snapshot.revision)
    binding_ids = {binding.id for binding in snapshot.revision.bindings}
    for value in synthetic_input.values:
        if value.workbook_cell is not None:
            workbook_inputs[value.workbook_cell] = value.value
        if value.registry_binding is None:
            continue
        registry_value = _registry_decimal_value(value.id, value.value)
        if value.registry_binding in casilla_ids:
            registry_inputs[value.registry_binding] = registry_value
        elif value.registry_binding in binding_ids:
            registry_binding_values[value.registry_binding] = registry_value
        else:
            raise RegistryValidationError(
                f"synthetic input {value.id!r} references unknown registry target {value.registry_binding!r}",
            )
    return workbook_inputs, registry_inputs, registry_binding_values


def _registry_output_references(
    snapshot: RegistrySnapshot,
    registry_outputs: Mapping[WorkbookOutputId, CasillaId],
) -> tuple[dict[WorkbookOutputId, tuple[LegalRefId, ...]], dict[WorkbookOutputId, tuple[SourceRefId, ...]]]:
    formulas_by_target = {formula.target_casilla_id: formula for formula in snapshot.revision.formulas}
    casillas_by_id = {casilla.id: casilla for casilla in snapshot.revision.casillas}
    legal_refs: dict[WorkbookOutputId, tuple[LegalRefId, ...]] = {}
    source_refs: dict[WorkbookOutputId, tuple[SourceRefId, ...]] = {}
    for output_id, casilla_id in registry_outputs.items():
        formula = formulas_by_target.get(casilla_id)
        if formula is not None:
            legal_refs[output_id] = tuple(formula.legal_refs)
            source_refs[output_id] = tuple(formula.source_refs)
            continue
        casilla = casillas_by_id.get(casilla_id)
        if casilla is None:
            raise RegistryValidationError(
                f"registry parity output {output_id!r} references unknown casilla {casilla_id!r}",
            )
        legal_refs[output_id] = tuple(casilla.legal_refs)
        source_refs[output_id] = tuple(casilla.source_refs)
    return legal_refs, source_refs


def parse_workbook_cell_ref(value: str, *, default_sheet: str | None = None) -> WorkbookCellRef:
    """Parse a workbook cell reference from registry configuration.

    Returns:
        The parsed :class:`WorkbookCellRef` with sheet and coordinate fields.
    """
    match = _CELL_REF_VALUE_PATTERN.match(value)
    if not match:
        raise RegistryValidationError(f"invalid workbook cell reference {value!r}")
    raw_sheet = match.group("sheet")
    if raw_sheet is None:
        if default_sheet is None:
            raise RegistryValidationError(f"workbook cell reference {value!r} must include a sheet")
        sheet = default_sheet
    else:
        sheet = raw_sheet.strip("'")
    return WorkbookCellRef(sheet=sheet, coordinate=match.group("coordinate").replace("$", ""))


def compare_registry_to_workbook(
    *,
    synthetic_input: SyntheticInputSet,
    workbook: WorkbookArtefactReport,
    runner: WorkbookRunnerAvailability,
    expected_workbook_values: Mapping[WorkbookOutputId, Decimal | int | str | bool | None],
    actual_registry_values: Mapping[WorkbookOutputId, Decimal | int | str | bool | None],
    output_cells: Mapping[WorkbookOutputId, WorkbookCellRef],
    registry_snapshot_id: str | None = None,
    legal_refs: Mapping[WorkbookOutputId, tuple[LegalRefId, ...]] | None = None,
    source_refs: Mapping[WorkbookOutputId, tuple[SourceRefId, ...]] | None = None,
    tolerance: Decimal = Decimal("0"),
) -> WorkbookParityRunReport:
    """Build a deterministic parity comparison report from already-computed values.

    Returns:
        A :class:`WorkbookParityRunReport` comparing registry output to workbook cells.
    """
    expected_ids, legal_ref_map, source_ref_map = _validate_comparison_inputs(
        expected_workbook_values=expected_workbook_values,
        actual_registry_values=actual_registry_values,
        output_cells=output_cells,
        legal_refs=legal_refs,
        source_refs=source_refs,
    )
    comparisons = _build_comparison_records(
        expected_ids=expected_ids,
        expected_workbook_values=expected_workbook_values,
        actual_registry_values=actual_registry_values,
        output_cells=output_cells,
        legal_ref_map=legal_ref_map,
        source_ref_map=source_ref_map,
        tolerance=tolerance,
    )
    run_status: ParityStatus = "match" if all(c.status == "match" for c in comparisons) else "mismatch"
    return WorkbookParityRunReport(
        synthetic_input_id=synthetic_input.id,
        registry_snapshot_id=registry_snapshot_id,
        workbook=workbook,
        runner=runner,
        comparisons=tuple(comparisons),
        status=run_status,
    )


def _validate_comparison_inputs(
    *,
    expected_workbook_values: Mapping[WorkbookOutputId, Decimal | int | str | bool | None],
    actual_registry_values: Mapping[WorkbookOutputId, Decimal | int | str | bool | None],
    output_cells: Mapping[WorkbookOutputId, WorkbookCellRef],
    legal_refs: Mapping[WorkbookOutputId, tuple[LegalRefId, ...]] | None,
    source_refs: Mapping[WorkbookOutputId, tuple[SourceRefId, ...]] | None,
) -> tuple[
    frozenset[WorkbookOutputId],
    Mapping[WorkbookOutputId, tuple[LegalRefId, ...]],
    Mapping[WorkbookOutputId, tuple[SourceRefId, ...]],
]:
    expected_ids = _workbook_output_id_set("expected workbook values", expected_workbook_values)
    actual_ids = _workbook_output_id_set("actual registry values", actual_registry_values)
    if expected_ids != actual_ids:
        _raise_output_id_mismatch(
            "expected workbook values",
            expected_ids,
            "actual registry values",
            actual_ids,
        )
    cell_ids = _workbook_output_id_set("workbook output cells", output_cells)
    if cell_ids != expected_ids:
        _raise_output_id_mismatch("workbook output cells", cell_ids, "compared output values", expected_ids)
    empty_legal_refs: dict[WorkbookOutputId, tuple[LegalRefId, ...]] = {}
    empty_source_refs: dict[WorkbookOutputId, tuple[SourceRefId, ...]] = {}
    legal_ref_map = legal_refs if legal_refs else empty_legal_refs
    source_ref_map = source_refs if source_refs else empty_source_refs
    missing_legal_refs = _missing_or_empty_output_refs(expected_ids, legal_ref_map)
    missing_source_refs = _missing_or_empty_output_refs(expected_ids, source_ref_map)
    if missing_legal_refs:
        raise RegistryValidationError(
            f"workbook parity comparison missing legal_refs for outputs: {missing_legal_refs!r}",
        )
    if missing_source_refs:
        raise RegistryValidationError(
            f"workbook parity comparison missing source_refs for outputs: {missing_source_refs!r}",
        )
    return expected_ids, legal_ref_map, source_ref_map


def _build_comparison_records(
    *,
    expected_ids: frozenset[WorkbookOutputId],
    expected_workbook_values: Mapping[WorkbookOutputId, Decimal | int | str | bool | None],
    actual_registry_values: Mapping[WorkbookOutputId, Decimal | int | str | bool | None],
    output_cells: Mapping[WorkbookOutputId, WorkbookCellRef],
    legal_ref_map: Mapping[WorkbookOutputId, tuple[LegalRefId, ...]],
    source_ref_map: Mapping[WorkbookOutputId, tuple[SourceRefId, ...]],
    tolerance: Decimal,
) -> list[WorkbookParityComparison]:
    comparisons: list[WorkbookParityComparison] = []
    for output_id in sorted(expected_ids):
        expected = expected_workbook_values[output_id]
        actual = actual_registry_values[output_id]
        cell = output_cells.get(output_id)
        if cell is None:
            raise RegistryValidationError(f"missing workbook output cell for {output_id!r}")
        status = _comparison_status(expected, actual, tolerance)
        comparisons.append(
            WorkbookParityComparison(
                output_id=output_id,
                workbook_cell=cell,
                expected_workbook_value=expected,
                actual_registry_value=actual,
                status=status,
                tolerance=tolerance,
                legal_refs=legal_ref_map[output_id],
                source_refs=source_ref_map[output_id],
                detail=None if status == "match" else "registry output differs from workbook output",
            ),
        )
    return comparisons


def verify_workbook_backend(
    root: Path,
    *,
    scan_limit: int | None = None,
    per_file_timeout_seconds: float = 10.0,
    previous_report: WorkbookBackendVerificationReport | None = None,
    fail_on_scan_error: bool = True,
) -> WorkbookBackendVerificationReport:
    """Verify the workbook parity backend and return a :class:`WorkbookBackendVerificationReport`."""
    reports = inventory_workbook_coverage(
        root,
        options=WorkbookScanOptions(per_file_timeout_seconds=per_file_timeout_seconds),
        limit=scan_limit,
        previous_reports=previous_report.reports if previous_report is not None else (),
    )
    runner = detect_workbook_runner()
    resolved_root = root.resolve().as_posix()
    workbook_count = len(discover_workbooks(root)) if root.exists() else 0
    scanned_count, formula_workbook_count, unsupported_xls_count, failed_count = _workbook_verification_counts(reports)
    report = WorkbookBackendVerificationReport(
        root=resolved_root,
        workbook_count=workbook_count,
        scanned_count=scanned_count,
        formula_workbook_count=formula_workbook_count,
        unsupported_xls_count=unsupported_xls_count,
        failed_count=failed_count,
        runner=runner,
        reports=reports,
        modelo_coverage=_build_modelo_coverage(reports),
    )
    if fail_on_scan_error:
        assert_workbook_scan_clean(report)
    return report


def _workbook_verification_counts(
    reports: tuple[WorkbookArtefactReport, ...],
) -> tuple[int, int, int, int]:
    scanned_count = 0
    formula_workbook_count = 0
    unsupported_xls_count = 0
    failed_count = 0
    for report in reports:
        if report.scan_status == WorkbookScanStatus.SCANNED:
            scanned_count += 1
        if report.workbook_kind == WorkbookKind.FORMULA_FORM:
            formula_workbook_count += 1
        if report.workbook_kind == WorkbookKind.UNSUPPORTED_BINARY_XLS:
            unsupported_xls_count += 1
        if report.scan_status in {WorkbookScanStatus.FAILED, WorkbookScanStatus.TIMEOUT}:
            failed_count += 1
    return scanned_count, formula_workbook_count, unsupported_xls_count, failed_count


def _comparison_status(
    expected: Decimal | int | str | bool | None,
    actual: Decimal | int | str | bool | None,
    tolerance: Decimal,
) -> ParityStatus:
    if expected is None or actual is None:
        return "match" if expected is actual else "mismatch"
    if isinstance(expected, Decimal | int) and isinstance(actual, Decimal | int):
        return "match" if abs(Decimal(expected) - Decimal(actual)) <= tolerance else "mismatch"
    return "match" if expected == actual else "mismatch"


def _registry_decimal_value(input_id: str, value: Decimal | int | str | bool) -> Decimal:
    if isinstance(value, bool):
        raise RegistryValidationError(f"synthetic input {input_id!r} cannot feed boolean into registry calculation")
    if isinstance(value, Decimal):
        return value
    if isinstance(value, int):
        return Decimal(value)
    try:
        return Decimal(value)
    except (ArithmeticError, ValueError, TypeError) as exc:
        raise RegistryValidationError(
            f"synthetic input {input_id!r} cannot feed non-decimal value into registry calculation",
        ) from exc

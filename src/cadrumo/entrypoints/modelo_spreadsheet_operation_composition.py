"""Bind canonical spreadsheet algorithms to one immutable profile worker.

Core types: :class:`~cadrumo.domain.calculations.registry.schema.RegistrySnapshot`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from ..adapters.outbound.storage.errors import OutboundStorageConflictError
from ..application.calculations.relation_prefill import resolve_relations_from_local_store
from ..application.modelo.modelo_spreadsheet_observations import (
    project_modelo_spreadsheet_observation,
)
from ..application.modelo.modelo_spreadsheet_operation_contracts import (
    ModeloSpreadsheetCalculateRequest,
    ModeloSpreadsheetOperationPorts,
    ModeloSpreadsheetPullRequest,
    ModeloSpreadsheetVerifyRequest,
    SpreadsheetMutationHandoff,
    SpreadsheetProviderAdmission,
    SpreadsheetSnapshotMismatchRefusal,
    SpreadsheetVerifyAcknowledgement,
)
from ..application.modelo.modelo_spreadsheet_operation_projections import (
    SpreadsheetAssembledGrouping,
    SpreadsheetBindingEdit,
    SpreadsheetCalculateFacts,
    SpreadsheetComputedCasilla,
    SpreadsheetOperatorEdit,
    SpreadsheetPullFacts,
    SpreadsheetPullMetadata,
    SpreadsheetRelationEdit,
    SpreadsheetRowSet,
    SpreadsheetRowSetCell,
    SpreadsheetVerifyDivergence,
    SpreadsheetVerifyFacts,
)
from ..application.storage.calc_sheets.engine import (
    CALC_SHEETS_ENGINE_VERSION,
    RelationResolver,
    build_export_plan,
    registry_sha,
)
from ..application.storage.calc_sheets.parity_harness import (
    CalcSheetsParityApplyResult,
    OperatorInputScenario,
    verify_modelo_parity,
)
from ..application.storage.calc_sheets.records import OperatorInputs, RelationValues, SheetExportPlan
from ..application.storage.calc_sheets.row_set_assembly import assemble_row_sets_for_snapshot
from ..application.user_profile.access_contracts import AccessDenialCode
from ..application.user_profile.access_errors import ProfileAccessRefusedError
from ..core.bucket_pointer import require_active_bucket_id
from ..domain.calculations.registry.authority import PinnedAuthorityOperation
from ..domain.calculations.registry.governed_fact_scope import validating_governed_facts
from ..domain.calculations.registry.schema import RegistrySnapshot

if TYPE_CHECKING:
    from google.auth.credentials import Credentials

    from ..adapters.outbound.google.calc_sheets_pull_records import (
        BindingEdit,
        OperatorEdit,
        PullResult,
        RelationEdit,
        RowSetEdit,
    )


def _pull_facts(result: PullResult, snapshot: RegistrySnapshot, *, assemble_observations: bool) -> SpreadsheetPullFacts:
    """Copy current populated output facts; all ingress algorithms stay canonical."""
    operators, bindings, relations = _populated_spreadsheet_scalar_edits(result)
    row_sets = tuple(row for row in result.row_set_edits if row.cells)
    groupings = _spreadsheet_assembled_groupings(row_sets, snapshot, assemble_observations)
    return SpreadsheetPullFacts(
        spreadsheet_id=result.spreadsheet_id,
        metadata_match=result.metadata_match.value,
        metadata=SpreadsheetPullMetadata(**result.metadata.model_dump(mode="python")),
        cells_read=result.cells_read,
        operator_edits_total=len(result.operator_edits),
        operator_edits_populated=len(operators),
        binding_edits_populated=len(bindings),
        relation_edits_populated=len(relations),
        operator_edits=tuple(
            SpreadsheetOperatorEdit(casilla_id=edit.casilla_id, label=edit.label, value=str(edit.value))
            for edit in operators
        ),
        binding_edits=tuple(SpreadsheetBindingEdit(binding=edit.binding, value=str(edit.value)) for edit in bindings),
        relation_edits=_spreadsheet_relation_edits_facts(relations),
        row_set_edits_populated=len(row_sets),
        row_set_cells_populated=sum(len(row.cells) for row in row_sets),
        row_set_edits=_spreadsheet_row_set_edits_facts(row_sets),
        assembled_groupings=groupings,
        assembled_observation_count=sum(row.observation_count for row in groupings),
    )


def _snapshot_mismatch_refusal(
    error: OutboundStorageConflictError, snapshot: RegistrySnapshot, spreadsheet_id: str
) -> SpreadsheetSnapshotMismatchRefusal:
    """Translate this canonical binding guard, excluding other provider exception data."""
    facts = error.context
    verdict = error.terminal_precondition_verdict
    if (
        error.translated_message != "adapters.google.calc_sheets.errors.workbook_snapshot_mismatch"
        or facts is None
        or facts.get("spreadsheet_id") != spreadsheet_id
        or verdict is None
        or verdict.failed_condition_id != "google.calc_sheets.pull.snapshot_aligned"
    ):
        raise error
    match = facts.get("metadata_match")
    if not isinstance(match, str):
        raise error
    return SpreadsheetSnapshotMismatchRefusal.model_validate(
        {
            "spreadsheet_id": spreadsheet_id,
            "metadata_match": str(match),
            "workbook_modelo": facts.get("workbook_modelo"),
            "snapshot_modelo": snapshot.modelo.id,
            "workbook_revision": facts.get("workbook_revision"),
            "snapshot_revision": snapshot.revision.id,
            "workbook_engine_version": facts.get("workbook_engine_version"),
            "expected_engine_version": CALC_SHEETS_ENGINE_VERSION,
            "workbook_registry_sha": facts.get("workbook_registry_sha"),
            "snapshot_registry_sha": registry_sha(snapshot),
        },
        strict=True,
    )


def build_modelo_spreadsheet_operation_ports(
    *, profile_id: UUID, operation: PinnedAuthorityOperation
) -> ModeloSpreadsheetOperationPorts:
    """Compose lazy ports; never discover providers or credentials at registry build."""

    def require_profile() -> None:
        if require_active_bucket_id() != str(profile_id):
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)

    require_profile()

    def snapshot_for(
        request: ModeloSpreadsheetPullRequest | ModeloSpreadsheetCalculateRequest | ModeloSpreadsheetVerifyRequest,
    ) -> RegistrySnapshot:
        require_profile()
        if request.profile_id != profile_id:
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        period = request.period.to_period()
        return operation.snapshot(request.modelo, filing_year=period.filing_year, period=period.registry_token)

    def credentials_and_root(admit_provider: SpreadsheetProviderAdmission) -> tuple[Credentials, str]:
        from ..adapters.outbound.storage.factory import (
            build_google_credentials,
            require_application_drive_root,
            resolve_required_drive_root_folder_id,
        )

        require_profile()
        # The canonical local root precondition retains its original refusal
        # before any credential/provider discovery or remote dispatch.
        root = resolve_required_drive_root_folder_id(profile=str(profile_id))
        admit_provider()
        require_profile()
        credentials = build_google_credentials(profile=str(profile_id))
        require_profile()
        # A stored root is used only after Drive shows it as a folder this
        # application created.
        admit_provider()
        require_application_drive_root(credentials, root_folder_id=root)
        require_profile()
        return credentials, root

    def read(
        request: ModeloSpreadsheetPullRequest | ModeloSpreadsheetCalculateRequest,
        admit_provider: SpreadsheetProviderAdmission,
    ) -> tuple[RegistrySnapshot, PullResult | SpreadsheetSnapshotMismatchRefusal]:
        from ..adapters.outbound.google.calc_sheets_pull import pull_operator_edits

        snapshot = snapshot_for(request)
        credentials, _root = credentials_and_root(admit_provider)
        admit_provider()
        require_profile()
        try:
            with validating_governed_facts(operation):
                pulled = pull_operator_edits(snapshot, spreadsheet_id=request.spreadsheet_id, credentials=credentials)
        except OutboundStorageConflictError as error:
            require_profile()
            return snapshot, _snapshot_mismatch_refusal(error, snapshot, request.spreadsheet_id)
        require_profile()
        return snapshot, pulled

    def pull(
        request: ModeloSpreadsheetPullRequest, *, admit_provider: SpreadsheetProviderAdmission
    ) -> SpreadsheetPullFacts | SpreadsheetSnapshotMismatchRefusal:
        snapshot, pulled = read(request, admit_provider)
        if isinstance(pulled, SpreadsheetSnapshotMismatchRefusal):
            return pulled
        with validating_governed_facts(operation):
            return _pull_facts(pulled, snapshot, assemble_observations=request.assemble_observations)

    def calculate(
        request: ModeloSpreadsheetCalculateRequest, *, admit_provider: SpreadsheetProviderAdmission
    ) -> SpreadsheetCalculateFacts | SpreadsheetSnapshotMismatchRefusal:
        from ..adapters.outbound.google.calc_sheets_pull import compute_from_pull

        snapshot, pulled = read(request, admit_provider)
        if isinstance(pulled, SpreadsheetSnapshotMismatchRefusal):
            return pulled
        with validating_governed_facts(operation):
            calculated = compute_from_pull(snapshot, pulled)
        metadata_match = pulled.metadata_match.value
        if metadata_match != "matches":
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)
        return SpreadsheetCalculateFacts(
            spreadsheet_id=pulled.spreadsheet_id,
            metadata_match=metadata_match,
            cells_read=pulled.cells_read,
            operator_edits_populated=sum(edit.value is not None for edit in pulled.operator_edits),
            binding_edits_populated=sum(edit.value is not None for edit in pulled.binding_edits),
            relation_edits_populated=sum(edit.value is not None for edit in pulled.relation_edits),
            computed=tuple(
                SpreadsheetComputedCasilla(
                    casilla_id=row.target_casilla_id,
                    value=str(row.value),
                    formula_id=row.formula_id,
                    legal_refs=tuple(row.legal_refs),
                    source_refs=tuple(row.source_refs),
                )
                for row in calculated.entries
            ),
        )

    def verify(
        request: ModeloSpreadsheetVerifyRequest,
        scenario: OperatorInputScenario,
        *,
        admit_provider: SpreadsheetProviderAdmission,
        before_mutation: SpreadsheetMutationHandoff,
    ) -> SpreadsheetVerifyAcknowledgement:
        from ..adapters.outbound.google.calc_sheets_apply import apply_export_plan

        snapshot = snapshot_for(request)
        credentials, root = credentials_and_root(admit_provider)
        write_confirmed = False

        def apply(
            plan: SheetExportPlan, *, credentials: Credentials, root_folder_id: str
        ) -> CalcSheetsParityApplyResult:
            nonlocal write_confirmed
            require_profile()
            before_mutation()
            # No local authorization/custody lock survives this callback.
            applied = apply_export_plan(plan, credentials=credentials, root_folder_id=root_folder_id)
            write_confirmed = (
                applied.value_cells_written
                + applied.formula_cells_written
                + applied.protected_ranges_written
                + applied.row_set_headers_written
                > 0
            )
            return CalcSheetsParityApplyResult(
                spreadsheet_id=applied.spreadsheet_id, spreadsheet_url=applied.spreadsheet_url
            )

        with validating_governed_facts(operation):
            report = verify_modelo_parity(
                snapshot, scenario, credentials=credentials, root_folder_id=root, apply_port=apply
            )
        require_profile()
        if (
            report.modelo_id != request.modelo
            or report.period != request.period.to_period()
            or report.revision_id != snapshot.revision.id
        ):
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)
        return SpreadsheetVerifyAcknowledgement(
            facts=SpreadsheetVerifyFacts(
                spreadsheet_id=report.spreadsheet_id,
                spreadsheet_url=report.spreadsheet_url,
                verdict=report.verdict,
                aeat_oracle_present=report.aeat_oracle_present,
                computed_count=len(report.casillas),
                divergence_count=len(report.divergences),
                divergences=tuple(
                    SpreadsheetVerifyDivergence(
                        casilla_id=row.casilla_id,
                        label=row.label,
                        local=str(row.local) if row.local is not None else None,
                        sheets=str(row.sheets) if row.sheets is not None else None,
                        aeat=str(row.aeat) if row.aeat is not None else None,
                    )
                    for row in report.divergences
                ),
            ),
            remote_write_confirmed=write_confirmed,
        )

    def bound_relation_resolver(snapshot: RegistrySnapshot) -> RelationValues:
        from ..adapters.persistence.profile.calculation_observations import CalculationObservationRepository
        from ..adapters.persistence.storage.runtime_repository import secure_object_repository_for_bucket

        require_profile()
        repository = CalculationObservationRepository(objects=secure_object_repository_for_bucket(str(profile_id)))
        return resolve_relations_from_local_store(snapshot, operation=operation, repository=repository)

    def bound_plan_builder(
        snapshot: RegistrySnapshot,
        *,
        operator_inputs: OperatorInputs,
        relation_values: RelationValues | None = None,
        relation_resolver: RelationResolver | None = None,
    ) -> SheetExportPlan:
        require_profile()
        return build_export_plan(
            snapshot,
            operator_inputs=operator_inputs,
            relation_values=relation_values,
            relation_resolver=bound_relation_resolver if relation_resolver is not None else None,
        )

    def materialize(plan: SheetExportPlan) -> bytes:
        from ..adapters.outbound.workbook.calc_sheets_xlsx import materialize_export_plan

        require_profile()
        return materialize_export_plan(plan)

    return ModeloSpreadsheetOperationPorts(
        profile_id=profile_id,
        operation=operation,
        materialize=materialize,
        plan_builder=bound_plan_builder,
        pull=pull,
        calculate=calculate,
        verify=verify,
    )


__all__ = ["build_modelo_spreadsheet_operation_ports"]


def _populated_spreadsheet_scalar_edits(
    result: PullResult,
) -> tuple[tuple[OperatorEdit, ...], tuple[BindingEdit, ...], tuple[RelationEdit, ...]]:
    """Filter populated operator, binding, and relation edits in workbook order."""
    operators = tuple(edit for edit in result.operator_edits if edit.value is not None)
    bindings = tuple(edit for edit in result.binding_edits if edit.value is not None)
    relations = tuple(edit for edit in result.relation_edits if edit.value is not None)
    return operators, bindings, relations


def _spreadsheet_assembled_groupings(
    row_sets: tuple[RowSetEdit, ...], snapshot: RegistrySnapshot, assemble_observations: bool
) -> tuple[SpreadsheetAssembledGrouping, ...]:
    """Assemble row sets only when requested and retain their strict positional alignment."""
    assembled = assemble_row_sets_for_snapshot(row_sets, snapshot) if assemble_observations else ()
    groupings = (
        tuple(
            SpreadsheetAssembledGrouping(
                grouping=row.grouping,
                source_kind=source_kind,
                observation_count=len(observations),
                observations=tuple(project_modelo_spreadsheet_observation(observation) for observation in observations),
            )
            for row, (source_kind, observations) in zip(row_sets, assembled, strict=True)
        )
        if assemble_observations
        else ()
    )
    return groupings


def _spreadsheet_relation_edits_facts(relations: tuple[RelationEdit, ...]) -> tuple[SpreadsheetRelationEdit, ...]:
    """Copy every populated relation_edits value and its existing provenance fields."""
    return tuple(
        SpreadsheetRelationEdit(
            relation=edit.relation,
            value=str(edit.value),
            provenance=edit.provenance,
            source_modelo=edit.source_modelo,
            source_filing_year=edit.source_filing_year,
            source_periods=edit.source_periods,
            source_casilla_ids=edit.source_casilla_ids,
            legal_refs=edit.legal_refs,
            source_refs=edit.source_refs,
            resolved_at=edit.resolved_at.isoformat() if edit.resolved_at is not None else None,
        )
        for edit in relations
    )


def _spreadsheet_row_set_edits_facts(row_sets: tuple[RowSetEdit, ...]) -> tuple[SpreadsheetRowSet, ...]:
    """Copy every populated row_set_edits value and its existing provenance fields."""
    return tuple(
        SpreadsheetRowSet(
            grouping=row.grouping,
            cells=tuple(
                SpreadsheetRowSetCell(
                    binding=cell.binding,
                    row_index=cell.row_index,
                    value=str(cell.value) if cell.value is not None else None,
                )
                for cell in row.cells
            ),
        )
        for row in row_sets
    )

"""Registered-executor conformance scenarios for the modelo spreadsheet family."""

from __future__ import annotations

import zipfile

from ...application.modelo.modelo_spreadsheet_operation_contracts import (
    MODELO_SPREADSHEET_CALCULATE_OPERATION_DEFINITION_ID,
    MODELO_SPREADSHEET_EXPORT_OPERATION_DEFINITION_ID,
    MODELO_SPREADSHEET_PULL_OPERATION_DEFINITION_ID,
    MODELO_SPREADSHEET_VERIFY_OPERATION_DEFINITION_ID,
    ModeloSpreadsheetCalculateRequest,
    ModeloSpreadsheetExportOutcome,
    ModeloSpreadsheetExportRequest,
    ModeloSpreadsheetPullRequest,
    ModeloSpreadsheetVerifyRequest,
)
from ...application.modelo.modelo_spreadsheet_operation_projections import ModeloSpreadsheetExportProjection
from ...application.operations.public_period import PublicPeriod
from ...application.storage.calc_sheets.records import TabName
from ...core.hashing import sha256_hex
from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from .conformance_family_contract import (
    ConformanceFamily,
    ConformanceFamilyContext,
    ConformanceOutcome,
    ConformancePreparation,
    RegisteredExecutorConformanceCase,
)

_MODELO = "303"
_PERIOD = PublicPeriod(filing_year=2025, code="1T")
_SPREADSHEET_ID = "conformance-spreadsheet"


def _prepare_export(context: ConformanceFamilyContext) -> ConformancePreparation:
    profile_id = context.profile_id
    output = (context.input_root / "modelo-303-2025-1T.xlsx").resolve()
    revision = context.operation.snapshot(_MODELO, filing_year=_PERIOD.filing_year, period=_PERIOD.code).revision.id

    def verify(outcome: ConformanceOutcome) -> None:
        result = outcome.resolve_result(ModeloSpreadsheetExportOutcome)
        assert result.result is not None
        landed = output.read_bytes()
        with zipfile.ZipFile(output) as workbook:
            assert workbook.testzip() is None
        # Coverage is a property of the rendered plan; it has no independent
        # oracle here beyond being non-empty.
        assert result.result.casilla_count > 0
        assert result == ModeloSpreadsheetExportOutcome(
            profile_id=profile_id,
            modelo=_MODELO,
            revision=revision,
            period=_PERIOD,
            outcome="succeeded",
            result=ModeloSpreadsheetExportProjection(
                profile_id=profile_id,
                modelo=_MODELO,
                revision=revision,
                period=_PERIOD,
                output_path=str(output),
                byte_size=len(landed),
                sha256=sha256_hex(landed),
                # Every workbook carries the fixed tab set
                # (application/storage/calc_sheets/workbook_export.py:179).
                tab_names=tuple(tab.value for tab in TabName),
                casilla_count=result.result.casilla_count,
                prefill_relations=False,
            ),
        )

    return ConformancePreparation(
        subject_ref=profile_operation_subject(str(profile_id)),
        request=ModeloSpreadsheetExportRequest(
            profile_id=profile_id, modelo=_MODELO, period=_PERIOD, output_path=str(output)
        ),
        verify=verify,
    )


def _prepare(context: ConformanceFamilyContext) -> ConformancePreparation:
    definition_id = context.definition.definition_id
    profile_id = context.profile_id
    subject_ref = profile_operation_subject(str(profile_id))
    if definition_id == MODELO_SPREADSHEET_EXPORT_OPERATION_DEFINITION_ID:
        return _prepare_export(context)
    if definition_id == MODELO_SPREADSHEET_PULL_OPERATION_DEFINITION_ID:
        return ConformancePreparation(
            subject_ref=subject_ref,
            request=ModeloSpreadsheetPullRequest(
                profile_id=profile_id, modelo=_MODELO, period=_PERIOD, spreadsheet_id=_SPREADSHEET_ID
            ),
        )
    if definition_id == MODELO_SPREADSHEET_CALCULATE_OPERATION_DEFINITION_ID:
        return ConformancePreparation(
            subject_ref=subject_ref,
            request=ModeloSpreadsheetCalculateRequest(
                profile_id=profile_id, modelo=_MODELO, period=_PERIOD, spreadsheet_id=_SPREADSHEET_ID
            ),
        )
    if definition_id == MODELO_SPREADSHEET_VERIFY_OPERATION_DEFINITION_ID:
        return ConformancePreparation(
            subject_ref=subject_ref,
            request=ModeloSpreadsheetVerifyRequest(profile_id=profile_id, modelo=_MODELO, period=_PERIOD),
        )
    raise AssertionError(f"no modelo spreadsheet conformance scenario for {definition_id}")


def _drive_root_refusal(definition_id: str) -> RegisteredExecutorConformanceCase:
    # Pull, calculate and verify all resolve the Drive root before any
    # credential discovery or remote dispatch
    # (entrypoints/modelo_spreadsheet_operation_composition.py:152-158). The
    # isolated profile has none, so the registered OutboundStorageValidationError
    # refuses with nothing dispatched (modelo_spreadsheet_executor.py:163-165).
    return RegisteredExecutorConformanceCase(
        definition_id,
        OperationTerminalCondition.REFUSED,
        OperationEffect.NONE,
        (definition_id,),
        expected_refusal_ref="REFUSED_OUTBOUND_STORAGE_VALIDATION",
    )


# Every definition is single-phase and publishes its own id first
# (application/modelo/modelo_spreadsheet_executor.py:357).
MODELO_SPREADSHEET_CONFORMANCE_FAMILY = ConformanceFamily(
    cases=(
        # Export is a local workbook publication: a confirmed sink write
        # settles UPDATED (modelo_spreadsheet_executor.py:213-216).
        RegisteredExecutorConformanceCase(
            MODELO_SPREADSHEET_EXPORT_OPERATION_DEFINITION_ID,
            OperationTerminalCondition.SUCCEEDED,
            OperationEffect.UPDATED,
            (MODELO_SPREADSHEET_EXPORT_OPERATION_DEFINITION_ID,),
        ),
        _drive_root_refusal(MODELO_SPREADSHEET_PULL_OPERATION_DEFINITION_ID),
        _drive_root_refusal(MODELO_SPREADSHEET_CALCULATE_OPERATION_DEFINITION_ID),
        _drive_root_refusal(MODELO_SPREADSHEET_VERIFY_OPERATION_DEFINITION_ID),
    ),
    prepare=_prepare,
)

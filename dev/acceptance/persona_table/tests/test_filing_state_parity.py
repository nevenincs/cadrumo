"""The filing-state read states what the form read states, at every step a Modelo 100 return takes.

A synthetic persona's Modelo 100 is taken, through the registered operations
the persona table runs, from its calculation through verification, the file
for the AEAT, local filing and the AEAT register confirming the local filing.
At each step both reads run as registered operations, and every field the
filing-state read carries equals the same field of the form read.

Each read's wall time is printed for the record; nothing is asserted on it.
"""

from __future__ import annotations

import time
from pathlib import Path

import pytest

from cadrumo.application.modelo.filing_chain_reconciliation import FilingReconciliationOutcome
from cadrumo.application.modelo.filing_record_import_contracts import (
    MODELO_FILING_RECORD_IMPORT_OPERATION_DEFINITION_ID,
    ModeloFilingRecordImportProjection,
    ModeloFilingRecordImportRequest,
)
from cadrumo.application.modelo.operation_shared import (
    MODELO_EXPORT_OPERATION_DEFINITION_ID,
    MODELO_WORK_CALCULATE_OPERATION_DEFINITION_ID,
    MODELO_WORK_FILE_OPERATION_DEFINITION_ID,
    MODELO_WORK_VERIFY_OPERATION_DEFINITION_ID,
)
from cadrumo.application.modelo.work_calculation_contracts import ModeloWorkCalculatePublicResultV3
from cadrumo.application.modelo.work_export_contracts import ModeloExportRequest
from cadrumo.application.modelo.work_filing_contracts import (
    ModeloWorkFileApproval,
    ModeloWorkFilePublicResultV2,
    ModeloWorkFileRequest,
)
from cadrumo.application.modelo.work_verification_contracts import (
    ModeloWorkVerifyPublicResultV2,
    ModeloWorkVerifyRequest,
)
from cadrumo.application.modelo.workbench_operations import (
    MODELO_WORK_FILING_STATE_OPERATION_DEFINITION_ID,
    MODELO_WORK_FORM_OPERATION_DEFINITION_ID,
    ModeloWorkbenchFormRequest,
    ModeloWorkFilingStateRequest,
)
from cadrumo.application.modelo.workbench_projection import (
    ModeloWorkbenchFormProjectionV1,
    ModeloWorkFilingStateProjectionV1,
)
from cadrumo.core.external_constants import OutputLanguage
from cadrumo.core.modelo_export_artefact import ModeloExportArtefact
from cadrumo.domain.modelos.filing_record import ExternalEvidenceKind
from cadrumo.entrypoints.tests.modelo_filing_state_support import filing_state_of_form
from cadrumo.entrypoints.tests.persona_materialisation import materialised_persona
from cadrumo.entrypoints.tests.persona_operations import run_operation, settle_operation
from cadrumo.entrypoints.tests.persona_world import PERSONA_ACTOR, MaterialisedPersona, PersonaWorld
from cadrumo.tests.personas import read_persona

from ..planner import PreparedReturn, plan_rows, prepare_return, registry_envelope, replay_scope, stated_values
from ..rows import PlannedRow
from ..sweep import run_return

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_PERSONA = "asalariada-familia"
"""A persona whose Modelo 100 the persona table takes through verification, export and local filing."""
_MODELO = "100"


def _reads(world: PersonaWorld, work_unit_id: str, step: str) -> ModeloWorkbenchFormProjectionV1:
    """Run both reads; assert the filing state is the form read's; print each read's wall time."""
    started = time.perf_counter()
    form = run_operation(
        world,
        MODELO_WORK_FORM_OPERATION_DEFINITION_ID,
        ModeloWorkbenchFormRequest(
            profile_id=world.profile_id, work_unit_id=work_unit_id, output_language=OutputLanguage.ES
        ),
        ModeloWorkbenchFormProjectionV1,
        subject=work_unit_id,
    )
    formed = time.perf_counter()
    state = run_operation(
        world,
        MODELO_WORK_FILING_STATE_OPERATION_DEFINITION_ID,
        ModeloWorkFilingStateRequest(
            profile_id=world.profile_id, work_unit_id=work_unit_id, output_language=OutputLanguage.ES
        ),
        ModeloWorkFilingStateProjectionV1,
        subject=work_unit_id,
    )
    stated = time.perf_counter()
    print(f"{step}: modelo.work.form {formed - started:.2f} s, modelo.work.filing_state {stated - formed:.2f} s")
    assert state == filing_state_of_form(form), step
    return form


def _calculate(world: PersonaWorld, prepared: PreparedReturn) -> str:
    calculated = run_operation(
        world,
        MODELO_WORK_CALCULATE_OPERATION_DEFINITION_ID,
        prepared.request,
        ModeloWorkCalculatePublicResultV3,
        subject=prepared.work_unit_id,
    )
    return calculated.calculation_revision_id


def _verify(world: PersonaWorld, work_unit_id: str, revision_id: str) -> str:
    verified = run_operation(
        world,
        MODELO_WORK_VERIFY_OPERATION_DEFINITION_ID,
        ModeloWorkVerifyRequest(calculation_revision_id=revision_id, actor=PERSONA_ACTOR),
        ModeloWorkVerifyPublicResultV2,
        subject=work_unit_id,
    )
    assert verified.granted_verificado_completo
    return verified.verification_report_id


def _export(world: PersonaWorld, work_unit_id: str, revision_id: str, output: Path) -> None:
    settle_operation(
        world,
        MODELO_EXPORT_OPERATION_DEFINITION_ID,
        ModeloExportRequest(
            calculation_revision_id=revision_id,
            output_path=str(output),
            artefact=ModeloExportArtefact.FICHERO_BOE,
            actor=PERSONA_ACTOR,
        ),
        subject=work_unit_id,
    )


def _file(world: PersonaWorld, work_unit_id: str, revision_id: str, report_id: str) -> None:
    run_operation(
        world,
        MODELO_WORK_FILE_OPERATION_DEFINITION_ID,
        ModeloWorkFileRequest(
            approval=ModeloWorkFileApproval(calculation_revision_id=revision_id, verification_report_id=report_id),
            actor=PERSONA_ACTOR,
        ),
        ModeloWorkFilePublicResultV2,
        subject=work_unit_id,
    )


def _confirm_from_register(world: PersonaWorld, work_unit_id: str, form: ModeloWorkbenchFormProjectionV1) -> None:
    """Import the AEAT register's line for the filing: the result box the form states, as filed."""
    result = form.form.form.result
    assert result is not None and result.value is not None
    imported = run_operation(
        world,
        MODELO_FILING_RECORD_IMPORT_OPERATION_DEFINITION_ID,
        ModeloFilingRecordImportRequest(
            profile_id=world.profile_id,
            work_unit_id=work_unit_id,
            evidence_kind=ExternalEvidenceKind.AEAT_CSV_REGISTER,
            evidence_reference_id="synthetic-register-line",
            actor=PERSONA_ACTOR,
            casilla_values=((result.casilla_id, result.value),),
        ),
        ModeloFilingRecordImportProjection,
    )
    assert imported.reconciliation.outcome is FilingReconciliationOutcome.CONFIRMED


def _first_return(materialised: MaterialisedPersona, plans: list[PlannedRow], exports: Path) -> PlannedRow:
    """Run every return the replay owes before the first Modelo 100, as the table does, and give that return.

    The first is the one whose filing window is open at the persona's scenario instant.
    """
    target = next(plan for plan in plans if plan.modelo == _MODELO)
    for plan in plans:
        if plan is target:
            return target
        run_return(materialised, plan, stated_values(materialised.persona, materialised.world.envelope, plan), exports)
    raise AssertionError("the replay owes no Modelo 100")


def test_the_filing_state_read_equals_the_form_read_at_every_filing_step(tmp_path: Path) -> None:
    envelope = registry_envelope()
    persona = read_persona(_PERSONA, envelope=envelope)
    plans, _ = plan_rows(_PERSONA, envelope.horizon)
    exports = tmp_path / "exports"
    exports.mkdir()
    with materialised_persona(_PERSONA, tmp_path, replay_scope(persona), reuse=True) as materialised:
        world = materialised.world
        plan = _first_return(materialised, plans, exports)
        prepared = prepare_return(materialised, plan, stated_values(materialised.persona, world.envelope, plan))
        assert isinstance(prepared, PreparedReturn)
        work_unit_id = prepared.work_unit_id
        revision_id = _calculate(world, prepared)
        calculated = _reads(world, work_unit_id, "calculated")
        assert calculated.header.file is None and calculated.form.form.filing is None

        report_id = _verify(world, work_unit_id, revision_id)
        _reads(world, work_unit_id, "verified")

        _export(world, work_unit_id, revision_id, exports / f"modelo-{_MODELO}-{plan.year}-{plan.period}.txt")
        exported = _reads(world, work_unit_id, "exported")
        assert exported.header.file is not None and exported.header.file.current
        assert exported.export_offer is not None and exported.export_offer.record.available

        _file(world, work_unit_id, revision_id, report_id)
        filed = _reads(world, work_unit_id, "filed locally")
        assert filed.form.form.filing is not None
        assert filed.receipt is not None and not filed.receipt.verified

        _confirm_from_register(world, work_unit_id, filed)
        confirmed = _reads(world, work_unit_id, "receipt verified")
        assert confirmed.receipt is not None and confirmed.receipt.verified

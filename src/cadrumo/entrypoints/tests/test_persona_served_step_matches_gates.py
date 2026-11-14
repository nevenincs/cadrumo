"""The step the form serves agrees with what the check and the export do, on the let-dwelling persona's Modelo 100.

The return is created and stated as an operator states it (the pending carries, the
work-income statement and the let dwelling's pending interest and repairs) through the
production operations, then the form is read, checked and exported. When the check
grants and the export writes, the form must not have served resolving something
first: the served step and the gates read one predicate of what withholds filing.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import timedelta
from pathlib import Path

import pytest

from ...application.modelo.absence_statement_submission import absence_statement_submission
from ...application.modelo.edit_apply_contracts import ModeloEditApplyPublicResultV1, ModeloEditApplySubmissionV1
from ...application.modelo.edit_contract import ModeloEditMutationFamily
from ...application.modelo.edit_models import ModeloEditSubmissionV1
from ...application.modelo.edit_operator_input import ModeloEditOperatorInputV2
from ...application.modelo.export_projection import ModeloExportPublicResultV3
from ...application.modelo.operation_shared import (
    MODELO_EDIT_APPLY_OPERATION_DEFINITION_ID,
    MODELO_EXPORT_OPERATION_DEFINITION_ID,
    MODELO_WORK_CALCULATE_OPERATION_DEFINITION_ID,
    MODELO_WORK_VERIFY_OPERATION_DEFINITION_ID,
)
from ...application.modelo.work_calculation_contracts import (
    ModeloWorkCalculatePublicResultV3,
    ModeloWorkCalculateRequest,
)
from ...application.modelo.work_create_operation import (
    MODELO_WORK_CREATE_OPERATION_DEFINITION_ID,
    ModeloWorkCreateProjection,
    ModeloWorkCreateRequest,
    ModeloWorkCreateSuccess,
)
from ...application.modelo.work_export_contracts import ModeloExportRequest
from ...application.modelo.work_form_next_step import ModeloFormNextAction
from ...application.modelo.work_verification_contracts import ModeloWorkVerifyPublicResultV2, ModeloWorkVerifyRequest
from ...application.modelo.workbench_operations import (
    MODELO_WORK_FORM_OPERATION_DEFINITION_ID,
    ModeloWorkbenchFormRequest,
)
from ...application.modelo.workbench_projection import ModeloWorkbenchFormProjectionV1
from ...application.operations.public_period import PublicPeriod
from ...core.external_constants import OutputLanguage
from ...core.modelo_export_artefact import ModeloExportArtefact
from ...domain.calculations.registry.authority import bundled_indexed_authority
from ...domain.calculations.registry.binding_absence_attestation import AbsenceAttestationFamily
from ...tests.personas import YearToken, read_persona
from .persona_materialisation import (
    PERSONA_ACTOR,
    MaterialisedPersona,
    ReplayScope,
    materialised_persona,
    run_operation,
    scenario_instant,
    settle_operation,
    year_envelope,
)
from .persona_prior_carries import attest_prior_carries
from .persona_rental_carries import attest_pending_rental_carries

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_PERSONA = "arrendador-jubilado"
#: The ejercicio the persona's statements name, so the return they answer.
_EJERCICIO = "horizon-1"


#: How long after the persona's own instant the window read its declarations: past the Modelo 100 deadline.
_AFTER_THE_DEADLINE = timedelta(days=270)


@pytest.fixture(params=["on time", "late"])
def renta_world(
    request: pytest.FixtureRequest, tmp_path_factory: pytest.TempPathFactory
) -> Iterator[MaterialisedPersona]:
    read_on = None
    if request.param == "late":
        with bundled_indexed_authority().operation() as operation:
            envelope = year_envelope(operation)
        read_on = scenario_instant(read_persona(_PERSONA, envelope=envelope), envelope) + _AFTER_THE_DEADLINE
    with materialised_persona(
        _PERSONA, tmp_path_factory.mktemp("persona"), ReplayScope.FULL, read_on=read_on
    ) as materialised:
        yield materialised


def _form(materialised: MaterialisedPersona, work_unit_id: str) -> ModeloWorkbenchFormProjectionV1:
    world = materialised.world
    return run_operation(
        world,
        MODELO_WORK_FORM_OPERATION_DEFINITION_ID,
        ModeloWorkbenchFormRequest(
            profile_id=world.profile_id, work_unit_id=work_unit_id, output_language=OutputLanguage.ES
        ),
        ModeloWorkbenchFormProjectionV1,
        subject=work_unit_id,
    )


def _stated_return(materialised: MaterialisedPersona) -> tuple[str, int]:
    world = materialised.world
    year = YearToken.parse(_EJERCICIO, where="test").resolve(world.envelope)
    created = settle_operation(
        world,
        MODELO_WORK_CREATE_OPERATION_DEFINITION_ID,
        ModeloWorkCreateRequest(
            profile_id=world.profile_id,
            modelo="100",
            period=PublicPeriod(filing_year=year, code="0A"),
            actor=PERSONA_ACTOR,
        ),
    )
    assert isinstance(created, ModeloWorkCreateProjection)
    assert isinstance(created.outcome, ModeloWorkCreateSuccess), created.outcome
    work_unit_id = created.outcome.unit.work_unit_id
    attest_prior_carries(materialised.persona, world, work_unit_id, year)
    request = ModeloWorkCalculateRequest(work_unit_id=work_unit_id, actor=PERSONA_ACTOR)
    # The calculation states the work-income statement the form offers and calculates again.
    run_operation(
        world,
        MODELO_WORK_CALCULATE_OPERATION_DEFINITION_ID,
        request,
        ModeloWorkCalculatePublicResultV3,
        subject=work_unit_id,
    )
    assert attest_pending_rental_carries(materialised.persona, world, work_unit_id, year)
    return work_unit_id, year


def _window_return(materialised: MaterialisedPersona) -> tuple[str, int]:
    """The return as the window states it: the carries in one edit, then the work income and the let dwelling in one."""
    world = materialised.world
    year = YearToken.parse(_EJERCICIO, where="test").resolve(world.envelope)
    created = settle_operation(
        world,
        MODELO_WORK_CREATE_OPERATION_DEFINITION_ID,
        ModeloWorkCreateRequest(
            profile_id=world.profile_id,
            modelo="100",
            period=PublicPeriod(filing_year=year, code="0A"),
            actor=PERSONA_ACTOR,
        ),
    )
    assert isinstance(created, ModeloWorkCreateProjection)
    assert isinstance(created.outcome, ModeloWorkCreateSuccess), created.outcome
    work_unit_id = created.outcome.unit.work_unit_id
    attest_prior_carries(materialised.persona, world, work_unit_id, year)
    read = _form(materialised, work_unit_id)
    assert read.admitted_baseline is not None
    baseline = read.admitted_baseline.to_baseline()
    attestations = read.form.form.carry_attestations
    intents = tuple(
        intent
        for family in (
            AbsenceAttestationFamily.RENTA_TRABAJO_INCOME_NOT_STATED,
            AbsenceAttestationFamily.RENTA_CAPITAL_INMOBILIARIO_GASTOS_PENDIENTES,
        )
        for intent in absence_statement_submission(baseline, attestations, family=family).binding_intents
    )
    submission = ModeloEditSubmissionV1(
        baseline=baseline, mutation_family=ModeloEditMutationFamily.CALCULATE, binding_intents=intents
    )
    staged = ModeloEditOperatorInputV2(
        submission=ModeloEditApplySubmissionV1.from_submission(submission), output_language=OutputLanguage.ES
    )
    run_operation(
        world, MODELO_EDIT_APPLY_OPERATION_DEFINITION_ID, staged, ModeloEditApplyPublicResultV1, subject=work_unit_id
    )
    return work_unit_id, year


@pytest.mark.parametrize("order", ["table", "window"])
def test_the_served_step_does_not_ask_to_resolve_what_the_check_and_the_export_pass(
    renta_world: MaterialisedPersona, tmp_path: Path, order: str
) -> None:
    world = renta_world.world
    work_unit_id, year = _stated_return(renta_world) if order == "table" else _window_return(renta_world)
    served = _form(renta_world, work_unit_id)
    assert served.calculation_revision_id is not None
    assert served.next_step is not None

    verified = run_operation(
        world,
        MODELO_WORK_VERIFY_OPERATION_DEFINITION_ID,
        ModeloWorkVerifyRequest(calculation_revision_id=served.calculation_revision_id, actor=PERSONA_ACTOR),
        ModeloWorkVerifyPublicResultV2,
        subject=work_unit_id,
    )
    exported = settle_operation(
        world,
        MODELO_EXPORT_OPERATION_DEFINITION_ID,
        ModeloExportRequest(
            calculation_revision_id=served.calculation_revision_id,
            output_path=str(tmp_path / f"{_PERSONA}-100-{year}-0A.xml"),
            artefact=ModeloExportArtefact.FICHERO_BOE,
            actor=PERSONA_ACTOR,
        ),
        subject=work_unit_id,
    )

    assert verified.granted_verificado_completo
    assert isinstance(exported, ModeloExportPublicResultV3)
    assert served.next_step.action is ModeloFormNextAction.VERIFY, served.next_step

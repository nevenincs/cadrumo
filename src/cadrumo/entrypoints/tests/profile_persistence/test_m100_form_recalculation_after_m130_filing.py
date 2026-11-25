"""The Modelo 100 form offers a recalculation once the Modelo 130 quarters it lacked are filed.

A Modelo 100 worked out before the year's Modelo 130 quarters are filed cannot
work out casilla 0604: its pagos fraccionados relation has no source, so the box
and the result stay unresolved. Filing the quarters afterwards changes nothing
stored on that calculation, so the form must tell from the stored revision and
the observation store alone that working it out again would now read them,
while a source still missing, or a filing the calculation does not read, keeps
the form asking for what it asked before.

Real encrypted store, real registry authority, real calculation, filing and
workbench reads; nothing stands in for the behaviour under test.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from cadrumo.adapters.persistence.profile.calculation_observations import CalculationObservationRepository
from cadrumo.adapters.persistence.profile.modelos_verification_reports import VerificationReportCatalogueRepository
from cadrumo.adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from cadrumo.adapters.persistence.profile.tests.secure_objects_fixture import secure_objects
from cadrumo.adapters.persistence.storage.sql.secure_objects import SecureObjectRepository
from cadrumo.application.modelo.work_form_next_step import ModeloFormNextAction
from cadrumo.application.modelo.workbench_read import (
    ModeloWorkbenchFilingStateReadV1,
    ModeloWorkbenchFormReadV1,
    ModeloWorkbenchReadPorts,
    read_modelo_workbench_filing_state,
    read_modelo_workbench_form,
)
from cadrumo.core.casilla_id import CasillaId, validated_casilla_id
from cadrumo.core.external_constants import OutputLanguage
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation, bundled_indexed_authority
from cadrumo.domain.calculations.registry.bindings import RegistryModeloObservation
from cadrumo.domain.calculations.registry.tests.registry_observations import registry_grounded_observations
from cadrumo.domain.modelos.calculation_revision import CalculationRevision
from cadrumo.entrypoints.adapter_composition_work_ports import build_calculation_action_ports
from cadrumo.entrypoints.tests.production_operation_registry import production_operation_registry

from .m130_m100_annual_support import (
    BUCKET_ID,
    FILE_AT,
    M130_PRIOR_RETURN_RESULT_CASILLA,
    M130_RESULTADO_FINAL_CASILLA,
    PRIOR_YEAR,
    calculate_revision_from_bucket_aggregation,
    m100_non_relation_zero_bindings,
    seed_prior_year_m100,
)
from .observation_seeding_support import save_stamped_observation
from .test_e2e_ledger_m130_quarters_to_m100_annual import (
    M100_ACTIVITY_KEY,
    M100_ACTIVITY_KEY_CASILLA,
    calculate_and_file_m130_quarter,
    calculate_m100_annual,
    persist_autonoma_style_ledger,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

__all__ = ["secure_objects"]


@pytest.fixture
def bucket_id() -> str:
    return BUCKET_ID


_M100_PAGOS_CASILLA: CasillaId = validated_casilla_id("0604")
_QUARTERS = ("1T", "2T", "3T", "4T")
# The four quarters' casilla 19 for this persona are hand-derived beside the ledger fixture.
# oracle: AEAT-MODELO-130-INSTRUCCIONES casillas 18, 19 y (4) Ingreso; 665 + 532 + 323 + 304 = 1824.00.
_FOLDED_PAGOS = Decimal("1824.00")


def _calculate_m100_before_the_quarters(secure_objects: SecureObjectRepository) -> CalculationRevision:
    """The annual return worked out while no Modelo 130 quarter of the year is filed."""
    persist_autonoma_style_ledger(secure_objects)
    seed_prior_year_m100(secure_objects)
    annual = calculate_m100_annual(secure_objects, text_casilla_inputs={M100_ACTIVITY_KEY_CASILLA: M100_ACTIVITY_KEY})
    assert _M100_PAGOS_CASILLA not in annual.casilla_values
    return annual


def _file_quarters(secure_objects: SecureObjectRepository, quarters: tuple[str, ...]) -> None:
    for period in quarters:
        calculate_and_file_m130_quarter(secure_objects, period=period)


def _recalculate(secure_objects: SecureObjectRepository, work_unit_id: str) -> CalculationRevision:
    """Work the annual return out again with the inputs its first calculation took."""
    return calculate_revision_from_bucket_aggregation(
        work_unit_id,
        text_casilla_inputs={M100_ACTIVITY_KEY_CASILLA: M100_ACTIVITY_KEY},
        binding_values=m100_non_relation_zero_bindings(),
        work_unit_repository=WorkUnitCatalogueRepository(bucket_id=BUCKET_ID, objects=secure_objects),
    ).revision


def _read_ports(operation: PinnedAuthorityOperation) -> ModeloWorkbenchReadPorts:
    ports = build_calculation_action_ports(bucket_id=BUCKET_ID, operation=operation)
    return ModeloWorkbenchReadPorts(
        work_units=ports.work_unit_repository,
        calculations=ports.calculation_repository,
        verifications=VerificationReportCatalogueRepository(bucket_id=BUCKET_ID),
        bucket_events=ports.bucket_event_repository,
        filings=ports.filing_repository,
        observations=ports.observation_repository,
    )


def _filing_state(work_unit_id: str) -> ModeloWorkbenchFilingStateReadV1:
    """The declaration as the window's filing-state read states it."""
    with bundled_indexed_authority().operation() as operation:
        return read_modelo_workbench_filing_state(
            work_unit_id,
            bucket_id=BUCKET_ID,
            ports=_read_ports(operation),
            operation=operation,
            language=OutputLanguage.ES,
        )


def _form_read(work_unit_id: str) -> ModeloWorkbenchFormReadV1:
    """The declaration as the window's form read states it."""
    with bundled_indexed_authority().operation() as operation:
        return read_modelo_workbench_form(
            work_unit_id,
            bucket_id=BUCKET_ID,
            ports=_read_ports(operation),
            operation=operation,
            operation_contracts=production_operation_registry().public_contract_set,
            language=OutputLanguage.ES,
        )


def _next_action(work_unit_id: str) -> ModeloFormNextAction:
    step = _filing_state(work_unit_id).next_step
    assert step is not None
    return step.action


def test_a_source_still_missing_keeps_the_form_asking_for_values(
    secure_objects: SecureObjectRepository,
) -> None:
    """With no quarter filed, or with the last quarter still missing, 0604 has no source and nothing changed."""
    annual = _calculate_m100_before_the_quarters(secure_objects)

    assert _next_action(annual.work_unit_id) is ModeloFormNextAction.FILL
    assert not _filing_state(annual.work_unit_id).load.summary.calculation_out_of_date

    _file_quarters(secure_objects, _QUARTERS[:-1])

    state = _filing_state(annual.work_unit_id)
    assert state.next_step is not None
    assert state.next_step.action is ModeloFormNextAction.FILL
    assert not state.load.summary.calculation_out_of_date


def test_filing_the_quarters_after_the_calculation_offers_recalculation(
    secure_objects: SecureObjectRepository,
) -> None:
    """Every quarter 0604 reads is filed after the calculation lacked them, so both reads offer working it out again."""
    annual = _calculate_m100_before_the_quarters(secure_objects)

    _file_quarters(secure_objects, _QUARTERS)

    state = _filing_state(annual.work_unit_id)
    assert state.next_step is not None
    assert state.next_step.action is ModeloFormNextAction.RECALCULATE, state.next_step
    assert state.load.summary.calculation_out_of_date
    form_read = _form_read(annual.work_unit_id)
    assert form_read.next_step is not None
    assert form_read.next_step.action is ModeloFormNextAction.RECALCULATE
    assert form_read.load.form.calculation_out_of_date
    result = form_read.header.result
    assert result is not None
    assert result.out_of_date_words is not None
    # Reading changes nothing: the stored calculation still lacks 0604 until it is worked out again.
    assert form_read.calculation_revision_id == annual.calculation_revision_id


def test_recalculating_after_the_quarters_are_filed_offers_the_check(
    secure_objects: SecureObjectRepository,
) -> None:
    """Once worked out again 0604 holds the four quarters' payments and the next step is the check."""
    annual = _calculate_m100_before_the_quarters(secure_objects)
    _file_quarters(secure_objects, _QUARTERS)

    recalculated = _recalculate(secure_objects, annual.work_unit_id)

    assert Decimal(recalculated.casilla_values[_M100_PAGOS_CASILLA]) == _FOLDED_PAGOS
    state = _filing_state(annual.work_unit_id)
    assert state.calculation_revision_id == recalculated.calculation_revision_id
    assert not state.load.summary.calculation_out_of_date
    assert state.next_step is not None
    assert state.next_step.action is ModeloFormNextAction.VERIFY, state.next_step


def test_a_filing_the_calculation_does_not_read_offers_no_recalculation(
    secure_objects: SecureObjectRepository,
) -> None:
    """An earlier ejercicio's Modelo 130 is not a source of this year's 0604, so nothing the form asks changes."""
    annual = _calculate_m100_before_the_quarters(secure_objects)

    save_stamped_observation(
        CalculationObservationRepository(objects=secure_objects),
        RegistryModeloObservation(
            modelo="130",
            filing_year=PRIOR_YEAR,
            period=_QUARTERS[-1],
            observations=registry_grounded_observations(
                modelo="130",
                filing_year=PRIOR_YEAR,
                period=_QUARTERS[-1],
                casilla_values={
                    M130_RESULTADO_FINAL_CASILLA: Decimal("250.00"),
                    M130_PRIOR_RETURN_RESULT_CASILLA: Decimal("0"),
                },
            ),
        ),
        source_kind="app_filing",
        captured_at=FILE_AT,
    )

    state = _filing_state(annual.work_unit_id)
    assert state.next_step is not None
    assert state.next_step.action is ModeloFormNextAction.FILL
    assert not state.load.summary.calculation_out_of_date

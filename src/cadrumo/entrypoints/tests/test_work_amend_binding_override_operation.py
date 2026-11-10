"""The registered amendment states the box sources its filed baseline never recorded.

The seeded baseline is an imported Modelo 130 holding casilla values only, so
its filing recorded none of the bindings a correction of casilla 01 reads.
These cases run the real ``modelo.work.amend`` executor through the shared
supervisor, journal and operand custody: the stated bindings reach the
recalculated figures and are kept on the corrected revision, and a binding the
pinned revision does not declare refuses by calculation's own rule.
"""

from __future__ import annotations

import asyncio
from decimal import Decimal
from pathlib import Path

import pytest

from ...adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from ...adapters.persistence.profile.modelos_filing import ModeloRecordCatalogueRepository
from ...application.modelo.calculation_request_fields import ModeloCalculationOverride
from ...application.modelo.work_amend_contracts import ModeloWorkAmendOverride, ModeloWorkAmendRequest
from ...core.operations import OperationEffect, OperationTerminalCondition
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from .registered_executor_case_support import OperationRuntimeCloseWitness, conformance_operation_runtime
from .registered_executor_payload_support import registered_executor_payload

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_UNRECORDED_BINDINGS = {
    "modelo-130-estimacion-directa-modalidad": "directa_normal",
    "modelo-130-actividad-economica-gastos-cumulative": "250.00",
    "modelo-130-retenciones-agrarias": "0",
    "modelo-130-volumen-ingresos-agrario": "0",
    "irpf.previous_year_economic_activity_net_income": "20000.00",
}


def _amend(tmp_path: Path, operation: PinnedAuthorityOperation, bindings: dict[str, str] | None):
    """Submit one casilla-01 correction carrying ``bindings``; return the observation and both records."""
    with conformance_operation_runtime(tmp_path, cleanup=OperationRuntimeCloseWitness()) as (
        driver,
        registry,
        profile_id,
    ):
        definition = registry.lookup("modelo.work.amend")
        subject_ref, seeded, _secret = registered_executor_payload(
            definition, profile_id=profile_id, tmp_path=tmp_path, operation=operation
        )
        assert isinstance(seeded, ModeloWorkAmendRequest)
        payload = seeded.model_copy(
            update={
                "overrides": (ModeloWorkAmendOverride(casilla_id="01", value="1100.00"),),
                "binding_overrides": tuple(
                    ModeloCalculationOverride(key=key, value=value) for key, value in (bindings or {}).items()
                ),
            }
        )
        _submitted, observed = asyncio.run(
            driver.run(definition_id=definition.definition_id, subject_ref=subject_ref, payload=payload)
        )
        records = ModeloRecordCatalogueRepository().load()
        amendment = next(
            (
                record
                for record in records.records.values()
                if record.amends_filing_record_id == payload.baseline.from_filing_record_id
            ),
            None,
        )
        revision = (
            None
            if amendment is None
            else CalculationRevisionCatalogueRepository().load().get(amendment.calculation_revision_id)
        )
        return observed.projection, amendment, revision


def test_the_stated_bindings_let_the_correction_file_and_are_kept(
    tmp_path: Path, *, operation: PinnedAuthorityOperation
) -> None:
    projection, amendment, revision = _amend(tmp_path, operation, _UNRECORDED_BINDINGS)

    assert projection.terminal_condition is OperationTerminalCondition.SUCCEEDED, projection
    assert projection.effect is OperationEffect.UPDATED
    assert amendment is not None
    assert revision is not None
    # Decimal values are kept as their canonical tokens, enum values verbatim.
    assert revision.binding_overrides["modelo-130-estimacion-directa-modalidad"] == "directa_normal"
    assert revision.binding_overrides["modelo-130-actividad-economica-gastos-cumulative"] == "250"
    assert revision.binding_overrides["irpf.previous_year_economic_activity_net_income"] == "20000"
    # The stated expenses reach their bound casilla, and directa normal adds no provision.
    assert revision.casilla_values["gastos-deducibles-previos"] == Decimal("250")
    assert revision.casilla_values["02"] == Decimal("250")


def test_a_binding_the_revision_does_not_declare_refuses_as_on_calculate(
    tmp_path: Path, *, operation: PinnedAuthorityOperation
) -> None:
    projection, amendment, _revision = _amend(
        tmp_path, operation, {**_UNRECORDED_BINDINGS, "modelo-130-no-such-binding": "1"}
    )

    assert projection.terminal_condition is not OperationTerminalCondition.SUCCEEDED
    assert "REFUSED_MODELO_CALCULATE_BINDING_INPUT" in (projection.failure_error_code, projection.refusal_ref)
    assert amendment is None

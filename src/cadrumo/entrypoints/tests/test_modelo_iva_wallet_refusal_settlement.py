"""A blocked IVA wallet settles a 303 calculation refused, effect none, through the production supervisor.

The prior quarter's filed history carries a credit and no AEAT wallet capture
confirms it, so the wallet gate needs the filer's decision before casilla 110
can be filled. The person can supply that decision, so the calculation is a
refusal, not a failure: it settles REFUSED under the wallet code, with no
effect, no new revision, and a door to the declaration's Saldo de IVA in the
recorded error detail another process reads.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ...adapters.persistence.profile.calculation_observations import CalculationObservationRepository
from ...adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from ...adapters.persistence.profile.tests.taxpayer_persona_support import seed_modelo_ready_profile
from ...application.modelo.work_lifecycle import create_work_unit
from ...application.operations.error_detail import OperationErrorDetailV1, operation_error_detail_schema
from ...application.operations.frontend_requests import (
    OperationResultProjectionRequestV1,
    OperationResultProjectionSuccessV1,
)
from ...application.operations.next_step import OperationOpenIvaWalletStepV1
from ...core.operations import OperationEffect, OperationLifecycle, OperationTerminalCondition
from ...core.period import Period
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.calculations.registry.tests.cross_period_seeding import resolved_revision
from ..adapter_composition_work_ports import build_work_lifecycle_ports
from .modelo_operation_test_support import MODELO_OPERATION_TEST_ACTOR
from .profile_persistence.iva_wallet_engine_support import TARGET_YEAR, store_prior_303_compensation
from .registered_executor_case_support import OperationRuntimeCloseWitness, conformance_operation_runtime

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_CALCULATE = "modelo.work.calculate"
_PROFILE_CLOCK = datetime(TARGET_YEAR, 4, 2, 9, 0, tzinfo=UTC)


def test_a_blocked_wallet_settles_refused_with_no_effect_and_a_saldo_de_iva_door(
    tmp_path: Path, *, operation: PinnedAuthorityOperation
) -> None:
    with conformance_operation_runtime(tmp_path / "runtime", cleanup=OperationRuntimeCloseWitness()) as (
        driver,
        registry,
        profile_id,
    ):
        seed_modelo_ready_profile(bucket_id=str(profile_id), at=_PROFILE_CLOCK)
        unit = create_work_unit(
            bucket_id=str(profile_id),
            modelo="303",
            filing_year=TARGET_YEAR,
            period=Period.from_year_and_code(TARGET_YEAR, "2T"),
            revision_id=resolved_revision(modelo="303", filing_year=TARGET_YEAR, period="2T").id,
            actor=MODELO_OPERATION_TEST_ACTOR,
            ports=build_work_lifecycle_ports(bucket_id=str(profile_id)),
            operation=operation,
        )
        store_prior_303_compensation(CalculationObservationRepository(), amount=Decimal("450.00"), period="1T")
        revisions_before = CalculationRevisionCatalogueRepository().load()
        definition = registry.lookup(_CALCULATE)
        payload = definition.request_type.model_validate(
            {
                "work_unit_id": unit.work_unit_id,
                "actor": MODELO_OPERATION_TEST_ACTOR,
                "ordinary_m303_filing_evidence": {"joint_return_elected": False},
            },
            strict=True,
        )

        _submitted, observed = asyncio.run(
            driver.run(definition_id=_CALCULATE, subject_ref=unit.work_unit_id, payload=payload)
        )
        revisions_after = CalculationRevisionCatalogueRepository().load()
        contract = registry.lookup_public_contract(_CALCULATE)
        resolved = asyncio.run(
            driver.services.result.resolve(
                OperationResultProjectionRequestV1(
                    operation_id=observed.projection.operation_id,
                    terminal_revision=observed.projection.revision,
                    definition_contract_digest=contract.definition_contract_digest,
                    result_schema=operation_error_detail_schema(),
                ),
                OperationErrorDetailV1,
            )
        )

    projection = observed.projection
    assert projection.lifecycle is OperationLifecycle.TERMINAL
    assert projection.terminal_condition is OperationTerminalCondition.REFUSED
    assert projection.refusal_ref == "REFUSED_MODELO_IVA_WALLET_RECONCILIATION_BLOCKED"
    assert projection.effect is OperationEffect.NONE
    assert projection.result_ref is None
    assert revisions_after == revisions_before

    assert isinstance(resolved, OperationResultProjectionSuccessV1), resolved
    detail = resolved.projection
    assert isinstance(detail, OperationErrorDetailV1)
    assert detail.error_code == "REFUSED_MODELO_IVA_WALLET_RECONCILIATION_BLOCKED"
    assert detail.refusal_words is not None and detail.refusal_words.strip()
    assert isinstance(detail.next_step, OperationOpenIvaWalletStepV1)
    assert detail.next_step.work_unit_id == unit.work_unit_id
    assert detail.next_step.words.strip()

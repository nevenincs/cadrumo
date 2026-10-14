"""Run a production registered executor through admission, settlement, and result verification."""

from __future__ import annotations

import asyncio
from pathlib import Path

from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation

from ...adapters.persistence.profile.invoices import InvoiceCatalogueRepository
from ...adapters.persistence.profile.iva_compensation_history import IvaCompensationHistoryRepository
from ...adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from ...adapters.persistence.profile.transactions import TransactionCatalogueRepository
from ...application.bucket_event_repository import bucket_event_history_repository
from ...application.invoices.catalogue_read_operation import (
    INVOICE_LIST_OPERATION_DEFINITION_ID,
    INVOICE_VIEW_OPERATION_DEFINITION_ID,
)
from ...application.invoices.catalogue_remove_operation import (
    INVOICE_REMOVE_OPERATION_DEFINITION_ID,
)
from ...application.invoices.catalogue_update_operation import (
    INVOICE_UPDATE_OPERATION_DEFINITION_ID,
)
from ...application.ledger.bulk_classify_operation import (
    LEDGER_BULK_CLASSIFY_OPERATION_DEFINITION_ID,
)
from ...application.ledger.usage_ratio_repository import load_usage_ratio_profile
from ...application.live.iva_wallet_history_operation import (
    IVA_WALLET_HISTORY_OPERATION_DEFINITION_ID,
)
from ...application.modelo.invoice_withholding_capture_contracts import (
    ModeloInvoiceWithholdingCaptureRequest,
)
from ...application.workflow.persistence import workflow_state_repository
from ...application.workflow.resume_operation import WORKFLOW_RESUME_OPERATION_DEFINITION_ID
from ..actividad_asset_composition import build_activity_asset_operation_ports
from ..adapter_composition import (
    build_bienes_inversion_repository,
    build_inventory_service_ports,
    build_prorrata_register_repository,
    build_verification_repository_bundle,
)
from .conformance_family_contract import ConformanceFamily, RegisteredExecutorConformanceCase, closed_model_runtime
from .invoice_withholding_operation_test_support import (
    InvoiceWithholdingConformanceSeed,
    read_invoice_withholding_conformance_case,
)
from .prorrata_bienes_operation_test_support import (
    read_bienes_inversion_operation_conformance_register,
)
from .prorrata_operation_test_support import read_prorrata_operation_conformance_register
from .registered_executor_case_support import (
    _CloseWitness,
    _model_runtime_for,
    _runtime,
    _seeded_conformance_submission,
)
from .registered_executor_outcome_assertions import _assert_registered_executor_conformance_outcome


def _run_registered_executor_conformance_case(
    tmp_path: Path,
    case: RegisteredExecutorConformanceCase,
    *,
    operation: PinnedAuthorityOperation,
    family: ConformanceFamily | None = None,
) -> None:
    """Exercise the actual admitted operation, settlement, review and cleanup owners."""
    definition_id = case.definition_id
    cleanup = _CloseWitness()
    with (
        (
            closed_model_runtime()
            if family is not None and family.closes_model_runtime
            else _model_runtime_for(definition_id)
        ),
        _runtime(tmp_path / case.definition_id, cleanup=cleanup) as (driver, registry, profile_id),
    ):
        definitions = {definition.definition_id: definition for definition in registry.definitions}
        definition = definitions[case.definition_id]
        submission = _seeded_conformance_submission(
            definition, profile_id=profile_id, tmp_path=tmp_path, operation=operation, family=family
        )
        family_preparation = submission.family_preparation
        projection_history_case = submission.projection_history_case
        query_case = submission.query_case
        review_case = submission.review_case
        followup_case = submission.followup_case
        recipient_case = submission.recipient_case
        attachment_case = submission.attachment_case
        lifecycle_case = submission.lifecycle_case
        rule_case = submission.rule_case
        prorrata_case = submission.prorrata_case
        evidence_case = submission.evidence_case
        subject_ref, payload, secret = submission.subject_ref, submission.payload, submission.secret
        bulk_classify_before = (
            (
                TransactionCatalogueRepository(bucket_id=str(profile_id)).load(),
                bucket_event_history_repository(bucket_id=str(profile_id)).load(),
            )
            if case.definition_id == LEDGER_BULK_CLASSIFY_OPERATION_DEFINITION_ID
            else None
        )
        prorrata_before = (
            read_prorrata_operation_conformance_register(
                profile_id, repository_factory=build_prorrata_register_repository, operation=operation
            )
            if prorrata_case is not None
            else None
        )
        withholding_seed = (
            InvoiceWithholdingConformanceSeed(
                request=payload,
                invoice_id=payload.evidence.invoice_id,
                period=payload.command.period.to_period(),
            )
            if isinstance(payload, ModeloInvoiceWithholdingCaptureRequest)
            else None
        )
        if withholding_seed is not None:
            withholding_before = read_invoice_withholding_conformance_case(profile_id, withholding_seed)
            assert withholding_before.generation == 0
            assert withholding_before.observations == ()
        certificate_state_before = (
            workflow_state_repository().load()
            if case.definition_id in {"auth.certificate.source.list", "auth.certificate.source.check"}
            else None
        )
        ratios_before = (
            (
                load_usage_ratio_profile(bucket_id=str(profile_id), operation=operation),
                bucket_event_history_repository(bucket_id=str(profile_id)).load(),
            )
            if case.definition_id.startswith("ledger.ratios.")
            else None
        )
        invoice_catalogue_before = (
            InvoiceCatalogueRepository(bucket_id=str(profile_id)).load()
            if case.definition_id
            in {
                INVOICE_LIST_OPERATION_DEFINITION_ID,
                INVOICE_VIEW_OPERATION_DEFINITION_ID,
                INVOICE_REMOVE_OPERATION_DEFINITION_ID,
                INVOICE_UPDATE_OPERATION_DEFINITION_ID,
            }
            else None
        )
        asset_repository = (
            build_activity_asset_operation_ports(bucket_id=str(profile_id), operation=operation).history_repository
            if case.definition_id.startswith("ledger.actividad-asset.")
            else None
        )
        asset_before = asset_repository.load() if asset_repository is not None else None
        inventory_repository = (
            build_inventory_service_ports(bucket_id=str(profile_id)).inventory_repository_factory(str(profile_id))
            if case.definition_id.startswith("ledger.inventory.")
            else None
        )
        inventory_before = inventory_repository.load() if inventory_repository is not None else None
        bienes_before = (
            read_bienes_inversion_operation_conformance_register(
                profile_id, repository_factory=build_bienes_inversion_repository
            )
            if case.definition_id.startswith("ledger.bienes_inversion.")
            else None
        )
        iva_history_before = (
            IvaCompensationHistoryRepository().list_periods()
            if case.definition_id == IVA_WALLET_HISTORY_OPERATION_DEFINITION_ID
            else None
        )
        resume_revision_catalogue_before = (
            CalculationRevisionCatalogueRepository().load(operation=operation)
            if case.definition_id == WORKFLOW_RESUME_OPERATION_DEFINITION_ID
            else None
        )
        overview_catalogues_before = None
        if case.definition_id == "overview.pipeline":
            overview_bundle = build_verification_repository_bundle(str(profile_id), operation=operation)
            overview_catalogues_before = (
                overview_bundle.transaction.load(),
                overview_bundle.work_unit.load(),
                overview_bundle.calculation.load(operation=operation),
                overview_bundle.filing.load(),
                overview_bundle.verification.load(operation=operation),
            )
        submitted, observed = asyncio.run(
            driver.run(definition_id=definition.definition_id, subject_ref=subject_ref, payload=payload, secret=secret)
        )
        _assert_registered_executor_conformance_outcome(
            asset_before=asset_before,
            asset_repository=asset_repository,
            attachment_case=attachment_case,
            bienes_before=bienes_before,
            bulk_classify_before=bulk_classify_before,
            case=case,
            cleanup=cleanup,
            certificate_state_before=certificate_state_before,
            definition_id=definition_id,
            definition=definition,
            driver=driver,
            evidence_case=evidence_case,
            family_preparation=family_preparation,
            followup_case=followup_case,
            inventory_before=inventory_before,
            inventory_repository=inventory_repository,
            invoice_catalogue_before=invoice_catalogue_before,
            iva_history_before=iva_history_before,
            lifecycle_case=lifecycle_case,
            observed=observed,
            operation=operation,
            overview_catalogues_before=overview_catalogues_before,
            payload=payload,
            profile_id=profile_id,
            projection_history_case=projection_history_case,
            prorrata_before=prorrata_before,
            prorrata_case=prorrata_case,
            query_case=query_case,
            ratios_before=ratios_before,
            recipient_case=recipient_case,
            registry=registry,
            resume_revision_catalogue_before=resume_revision_catalogue_before,
            review_case=review_case,
            rule_case=rule_case,
            submitted=submitted,
            tmp_path=tmp_path,
            withholding_seed=withholding_seed,
        )

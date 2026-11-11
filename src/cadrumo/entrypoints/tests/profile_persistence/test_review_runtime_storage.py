"""Runtime-storage coverage for filing approval review helpers."""

from __future__ import annotations

from pathlib import Path

import pytest

from cadrumo.adapters.persistence.profile.transactions import TransactionCatalogueRepository
from cadrumo.adapters.persistence.storage.errors import StorageValidationError
from cadrumo.adapters.persistence.storage.tests.secure_sql import isolated_runtime_profile
from cadrumo.application.filing.draft_review import (
    ModeloApprovalStaleReason,
    approval_stale_reasons,
    approve_draft,
    compute_current_approval_basis,
)
from cadrumo.application.filing.runtime import build_runtime_schema_provider
from cadrumo.application.filing.tests.filing_support import build_registry_filing_draft_from_decimals
from cadrumo.application.filing.tests.review_runtime_storage_support import review_runtime_transaction
from cadrumo.core.casilla_id import CasillaId, validated_casilla_id
from cadrumo.core.config import override_settings
from cadrumo.core.period import Period
from cadrumo.domain.calculations.registry.authority import (
    PinnedAuthorityOperation,
    bundled_indexed_authority,
)
from cadrumo.domain.filing.schema import ModeloDraft
from cadrumo.domain.submission.models import ModeloDraftStatus
from cadrumo.domain.transactions.models import TransactionCatalogue
from cadrumo.entrypoints.adapter_composition_ports import build_draft_review_ports

from ....domain.calculations.registry.tests.authored_editions import filing_year_envelope

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_BUCKET_ID = "cf394ec1-128f-4d57-b66d-2d57f35aaf35"
_Q1 = Period.from_year_and_code(filing_year_envelope().horizon, "1T")
_M130_INGRESOS_CASILLA: CasillaId = validated_casilla_id("01", surface="_M130_INGRESOS_CASILLA")
_M130_GASTOS_PREVIOS_CASILLA: CasillaId = validated_casilla_id(
    "gastos-deducibles-previos", surface="_M130_GASTOS_PREVIOS_CASILLA"
)
# The normal modality keeps box 02 equal to the supplied expenses, with no art. 30.2.ª provision.
_M130_NORMAL_MODALITY = {"modelo-130-estimacion-directa-modalidad": "directa_normal"}
_M130_PAGOS_PREVIOS_CASILLA: CasillaId = validated_casilla_id("05", surface="_M130_PAGOS_PREVIOS_CASILLA")
_M130_RETENCIONES_CASILLA: CasillaId = validated_casilla_id("06", surface="_M130_RETENCIONES_CASILLA")
_M130_AGRARIAN_VOLUME_CASILLA: CasillaId = validated_casilla_id("08", surface="_M130_AGRARIAN_VOLUME_CASILLA")
_M130_AGRARIAN_WITHHELD_CASILLA: CasillaId = validated_casilla_id("10", surface="_M130_AGRARIAN_WITHHELD_CASILLA")
_M130_HOME_DEDUCTION_CASILLA: CasillaId = validated_casilla_id("16", surface="_M130_HOME_DEDUCTION_CASILLA")
_M130_PRIOR_RETURN_CASILLA: CasillaId = validated_casilla_id("18", surface="_M130_PRIOR_RETURN_CASILLA")
_MODELO_130_CASILLA_INPUTS: dict[CasillaId, str] = {
    _M130_INGRESOS_CASILLA: "12500.00",
    _M130_GASTOS_PREVIOS_CASILLA: "3500.00",
    _M130_PAGOS_PREVIOS_CASILLA: "250.00",
    _M130_RETENCIONES_CASILLA: "100.00",
    _M130_AGRARIAN_VOLUME_CASILLA: "2000.00",
    _M130_AGRARIAN_WITHHELD_CASILLA: "10.00",
    _M130_HOME_DEDUCTION_CASILLA: "0.00",
    _M130_PRIOR_RETURN_CASILLA: "0.00",
}
_MODELO_130_BINDING_INPUTS = {
    "irpf.previous_year_economic_activity_net_income": "13000.00",
    "modelo-130-pagos-fraccionados-anteriores": "250.00",
    "modelo-130-resultados-negativos-anteriores": "0.00",
}


def test_compute_current_approval_basis_refuses_missing_runtime_session(tmp_path: Path) -> None:
    with bundled_indexed_authority().operation() as _authority_operation_for_test:
        schema_provider = build_runtime_schema_provider(modelos=("130",), filing_year=_Q1.filing_year, period=_Q1)
        draft = _ready_modelo_130_draft(operation=_authority_operation_for_test)

        with (
            override_settings(cadrumo_storage_root=tmp_path, cadrumo_active_profile=_BUCKET_ID),
            pytest.raises(StorageValidationError) as refusal,
        ):
            compute_current_approval_basis(
                draft,
                bucket_id=_BUCKET_ID,
                schema_provider=schema_provider,
                ports=build_draft_review_ports(bucket_id=_BUCKET_ID),
                operation=_authority_operation_for_test,
            )

        # The key, not the rendered sentence: the prose alternation this replaced
        # named two older wordings and matched neither once the refusal was localized.
        assert refusal.value.translated_message == "errors.storage.runtime.not_ready"


def test_approval_stale_reasons_reloads_transaction_catalogue_from_runtime_default(tmp_path: Path) -> None:
    with bundled_indexed_authority().operation() as _authority_operation_for_test:
        schema_provider = build_runtime_schema_provider(modelos=("130",), filing_year=_Q1.filing_year, period=_Q1)
        draft = _ready_modelo_130_draft(operation=_authority_operation_for_test)

        with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
            ports = build_draft_review_ports(bucket_id=profile.bucket_id)
            TransactionCatalogueRepository(bucket_id=profile.bucket_id).save(
                TransactionCatalogue.from_transactions((review_runtime_transaction("initial"),)),
            )
            approved = approve_draft(
                draft,
                bucket_id=profile.bucket_id,
                approved_by="operator",
                schema_provider=schema_provider,
                ports=ports,
                operation=_authority_operation_for_test,
            )

            TransactionCatalogueRepository(bucket_id=profile.bucket_id).save(
                TransactionCatalogue.from_transactions((review_runtime_transaction("changed"),)),
            )
            reasons = approval_stale_reasons(
                approved,
                bucket_id=profile.bucket_id,
                schema_provider=schema_provider,
                ports=ports,
                operation=_authority_operation_for_test,
            )

        assert ModeloApprovalStaleReason.TRANSACTION_CATALOGUE_CHANGED in reasons


def _ready_modelo_130_draft(*, operation: PinnedAuthorityOperation) -> ModeloDraft:
    return build_registry_filing_draft_from_decimals(
        modelo="130",
        period=_Q1,
        operation=operation,
        casilla_decimals=_MODELO_130_CASILLA_INPUTS,
        binding_decimals=_MODELO_130_BINDING_INPUTS,
        text_binding_values=_M130_NORMAL_MODALITY,
        status=ModeloDraftStatus.LISTO_PARA_PRESENTAR,
    )

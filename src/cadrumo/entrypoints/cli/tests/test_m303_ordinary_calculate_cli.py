"""Real CLI roundtrip for ordinary Modelo 303 evidence authoring through the profile worker."""

from __future__ import annotations

import sys
from collections.abc import Callable
from contextlib import AbstractContextManager
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from uuid import UUID

import pytest
from click.testing import Result

from cadrumo.domain.calculations.registry.tests.authored_editions import authored_revisions
from cadrumo.domain.invoices.tests.catalogue_support import build_invoice_catalogue

from ....adapters.outbound.fx.tests.recorded_ecb_rates import recorded_ecb_rate_provider
from ....adapters.persistence.profile.calculation_observations import IvaWalletDecisionRepository
from ....adapters.persistence.profile.invoices import InvoiceCatalogueRepository
from ....adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from ....adapters.persistence.profile.transactions import TransactionCatalogueRepository
from ....adapters.persistence.storage.tests.profile_capsule_runtime import (
    bound_test_profile_record,
    open_test_profile_session,
    upsert_test_profile_facts,
)
from ....application.aggregation.tests.ledger_transaction_support import iva_transaction
from ....application.invoices.catalogue_creation import build_catalogue_invoice
from ....application.modelo.metadata_read_operation import MODELO_WORK_METADATA_OPERATION_DEFINITION_ID
from ....application.modelo.operation_definitions import MODELO_WORK_CALCULATE_OPERATION_DEFINITION_ID
from ....application.modelo.revision_selection_operation import MODELO_WORK_REVISION_OPERATION_DEFINITION_ID
from ....application.modelo.tests.profile_fixture_values import MODELO_READY_PROFILE_FACTS
from ....application.modelo.work_create_operation import MODELO_WORK_CREATE_OPERATION_DEFINITION_ID
from ....application.operations.frontend_requests import OPERATION_OBSERVATION_PROJECTION_ID
from ....application.user_profile.access_contracts import (
    AccessAction,
    AccessScope,
    DisclosureCategory,
    DisclosurePermission,
)
from ....application.user_profile.tests.profile_values import complete_profile_facts
from ....core.iva_deduction_fact import IvaDeductionFactKind
from ....core.period import Period
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.tests.published_authority import (
    published_snapshot,
)
from ....domain.invoices.service import link_transaction
from ....domain.iva.classification import InvoiceKind
from ....domain.iva_compensation.reconciliation import IvaCompensationReconciliationDecision
from ....domain.transactions.enums import TransactionDirection
from ....domain.transactions.models import TransactionCatalogue
from ....domain.user_profile.values import ProfileSetupState, UserProfileFact
from ....tests.cli_envelope import require_error_document, unwrap_schema_envelope
from ._m303_ordinary_cli_support import OrdinaryM303SecureEvidence, joint_return_options
from ._modelo_work_ux_support import operator_profile_facts
from .native_api_cli_support import NativeApiCliSession, native_api_cli_session
from .test_runtime_invoice_add import password_profile_session

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires native Windows profile workers"),
]

# The newest exercise the registry authors a closed Modelo 303 design for: every
# quarter of it has an authored window, so both its first and its terminal quarter
# can be authored here.
_EXERCISE = max(revision.valid_from.year for revision in authored_revisions("303") if revision.valid_to is not None)
_PERIOD = Period.from_year_and_code(_EXERCISE, "1T")
_WALLET_DECIDED_AT = datetime(_EXERCISE, 4, 1, 10, tzinfo=UTC)

type _Seed = Callable[[str], str | None]


def _ordinary_m303_profile_facts() -> dict[str, str]:
    """Reuse the application readiness baseline with the CLI's activity fact for the exercise."""
    facts = {
        fact.path: (str(fact.value).lower() if isinstance(fact.value, bool) else str(fact.value))
        for fact in MODELO_READY_PROFILE_FACTS
    }
    facts.update(operator_profile_facts(activity_start_date=f"{_EXERCISE}-01-01"))
    return facts


def _scope(client_id: UUID) -> AccessScope:
    """Grant the Modelo 303 work lifecycle the calculate route submits."""
    operation_ids = frozenset(
        {
            MODELO_WORK_CREATE_OPERATION_DEFINITION_ID,
            MODELO_WORK_METADATA_OPERATION_DEFINITION_ID,
            MODELO_WORK_CALCULATE_OPERATION_DEFINITION_ID,
            MODELO_WORK_REVISION_OPERATION_DEFINITION_ID,
        }
    )
    return AccessScope(
        operations=operation_ids,
        actions=frozenset(
            {
                AccessAction.SUBMIT,
                AccessAction.START,
                AccessAction.RESUME,
                AccessAction.OBSERVE,
                AccessAction.RESULT,
                AccessAction.COMMIT,
                AccessAction.CANCEL,
                AccessAction.DETACH,
            }
        ),
        disclosures=frozenset(
            {
                DisclosurePermission(
                    destination_id=client_id,
                    projection_id=OPERATION_OBSERVATION_PROJECTION_ID,
                    category=DisclosureCategory.OPERATION_METADATA,
                ),
                *(
                    DisclosurePermission(
                        destination_id=client_id,
                        projection_id=f"{definition_id}.result",
                        category=DisclosureCategory.TAX_VALUES,
                    )
                    for definition_id in operation_ids
                ),
            }
        ),
        periods=None,
        allow_period_independent=True,
        allow_delegation=False,
    )


def _no_sources(_bucket_id: str) -> None:
    return None


def _operator_session(
    tmp_path: Path,
    authority_operation: PinnedAuthorityOperation,
    seed: _Seed = _no_sources,
) -> AbstractContextManager[NativeApiCliSession[str | None]]:
    """Complete the ordinary Modelo 303 operator, seed its sources and serve its native worker."""

    def prepare(profile_id: UUID, root: Path) -> str | None:
        facts = complete_profile_facts(
            authority_operation.profile_schema(),
            tuple(UserProfileFact(path=path, value=value) for path, value in _ordinary_m303_profile_facts().items()),
        )
        populated = upsert_test_profile_facts(profile_id, facts, root=root)
        with bound_test_profile_record(profile_id, root=root) as repository:
            ready = repository.complete_setup(
                profile_id,
                expected_revision=populated.record_revision,
                expected_content_digest=populated.content_digest,
            )
        assert ready.setup_state is ProfileSetupState.COMPLETE
        return seed(str(profile_id))

    return native_api_cli_session(tmp_path, scope_for_destination=_scope, prepare_profile=prepare)


def _seed_ledger_and_wallet(bucket_id: str, *, purchase_deduction_fact_kind: str = "domestic_current") -> str:
    """Persist the minimum linked IVA evidence and the canonical zero wallet decision.

    ``purchase_deduction_fact_kind`` exists so one case can declare a deduction
    the purchase cannot bear while every other seeded fact stays identical to the
    passing calculation above it. A separately built fixture would have let the
    two drift, and the assertion is precisely that this one field decides the
    outcome.

    Returns the purchase's ledger id, so a refusal can be attributed to the row
    that caused it rather than to any row.
    """
    purchase_invoice = build_catalogue_invoice(
        bucket_id=bucket_id,
        kind=InvoiceKind.RECEIVED,
        counterparty_name="Proveedor de prueba SL",
        counterparty_tax_id="A58818501",
        counterparty_country="ES",
        invoice_number=f"REC-{_EXERCISE}-1T",
        issued_at=date(_EXERCISE, 2, 15),
        taxable_base=Decimal("50.00"),
        iva_rate=Decimal("21"),
        currency="EUR",
        rate_provider=recorded_ecb_rate_provider(),
    )
    sale = iva_transaction(
        f"ordinary-{_EXERCISE}-sale",
        direction=TransactionDirection.INCOMING,
        amount=Decimal("121.00"),
        taxable_base=Decimal("100.00"),
        iva_amount=Decimal("21.00"),
        booked_date=date(_EXERCISE, 2, 15),
    )
    purchase = iva_transaction(
        f"ordinary-{_EXERCISE}-purchase",
        direction=TransactionDirection.OUTGOING,
        amount=Decimal("60.50"),
        taxable_base=Decimal("50.00"),
        iva_amount=Decimal("10.50"),
        booked_date=date(_EXERCISE, 2, 15),
    ).model_copy(
        update={
            "purchase_invoice_evidence_id": purchase_invoice.invoice_id,
            "invoice_id": purchase_invoice.invoice_id,
            "deduction_fact_kind": IvaDeductionFactKind.from_registry(purchase_deduction_fact_kind),
        }
    )
    invoice_catalogue = link_transaction(
        build_invoice_catalogue((purchase_invoice,)),
        purchase_invoice.invoice_id,
        purchase.transaction_id,
    )
    snapshot_ref = published_snapshot("303", filing_year=_EXERCISE, period="1T").snapshot_ref

    with open_test_profile_session(bucket_id):
        TransactionCatalogueRepository(bucket_id=bucket_id).save(
            TransactionCatalogue.from_transactions((sale, purchase)),
        )
        InvoiceCatalogueRepository(bucket_id=bucket_id).save(invoice_catalogue)
        IvaWalletDecisionRepository().save_decision(
            IvaCompensationReconciliationDecision(
                taxpayer_nif="12345678Z",
                target_year=_EXERCISE,
                target_period=_PERIOD,
                target_registry_snapshot_ref=snapshot_ref,
                source_registry_snapshot_refs=(),
                selected_authority="aeat_wallet",
                selected_amount=Decimal("0.00"),
                wallet_amount=Decimal("0.00"),
                local_recurrence_amount=None,
                override_amount=None,
                divergence="match",
                blocked=False,
                stale_wallet=False,
                reason_identity="first_period_zero_aeat_wallet",
                wallet_captured_at=_WALLET_DECIDED_AT,
                decided_at=_WALLET_DECIDED_AT,
            )
        )
    return purchase.transaction_id


def _create_m303_work_unit(session: NativeApiCliSession[str | None], period: str) -> str:
    created = session.invoke_password(
        "app", "modelo", "work", "create", "--modelo", "303", "--year", str(_EXERCISE), "--period", period
    )
    assert created.exit_code == 0, f"{created.output}\n{session.runtime_failure_observations!r}"
    work_unit_id = unwrap_schema_envelope(created.output)["work_unit_id"]
    assert isinstance(work_unit_id, str)
    return work_unit_id


def _calculate(session: NativeApiCliSession[str | None], work_unit_id: str, *options: str) -> Result:
    return session.invoke_password("app", "modelo", "work", "calculate", work_unit_id, *options)


def test_work_calculate_persists_ordinary_first_quarter_evidence_from_the_joint_return_answer_alone(
    tmp_path: Path, authority_operation: PinnedAuthorityOperation
) -> None:
    """1T asks only the joint-return election, so the CLI persists evidence without any attestation."""
    with _operator_session(tmp_path, authority_operation, _seed_ledger_and_wallet) as session:
        work_unit_id = _create_m303_work_unit(session, "1T")

        calculated = _calculate(session, work_unit_id, *joint_return_options(joint_return_elected=True))
        assert calculated.exit_code == 0, calculated.output
        revision_id = unwrap_schema_envelope(calculated.output)["calculation_revision_id"]
        assert isinstance(revision_id, str)

        with password_profile_session(session.profile_id, authority_operation):
            persisted = CalculationRevisionCatalogueRepository().load().revisions[revision_id]

    evidence = persisted.filing_instance_evidence
    assert evidence is not None
    assert evidence.m303.period == _PERIOD
    assert evidence.m303.joint_return_elected is True
    assert evidence.m303.annual_volume_nonzero is None
    assert evidence.m303.insolvency is None
    assert evidence.m303.exonerado_390 is None
    assert evidence.m303.regimen_simplificado.scope_decision.is_not_claimed is True
    assert evidence.m303.regimen_simplificado.rows.activities == ()
    assert evidence.m303.regimen_simplificado.calculation_result.activities == ()


def test_work_calculate_refuses_a_purchase_whose_declared_deduction_is_inadmissible(
    tmp_path: Path, authority_operation: PinnedAuthorityOperation
) -> None:
    """The same 1T calculation, with the purchase declaring a deduction it cannot bear.

    ``domestic_investment`` names a bien de inversión and requires a reciprocal
    register asset identity the row does not carry, so the deduction has no
    authority. The refusal must name the ledger row and the typed reason: before
    the readiness gate existed this reached the operator as an internal outbound
    payload-boundary defect naming a model class, which says nothing about which
    field to correct.
    """

    def seed(bucket_id: str) -> str:
        return _seed_ledger_and_wallet(bucket_id, purchase_deduction_fact_kind="domestic_investment")

    with _operator_session(tmp_path, authority_operation, seed) as session:
        purchase_id = session.prepared
        work_unit_id = _create_m303_work_unit(session, "1T")

        refused = _calculate(session, work_unit_id, *joint_return_options(joint_return_elected=True))

    assert refused.exit_code == 1, refused.output
    error = require_error_document(refused.output)["error"]
    assert isinstance(error, dict)
    assert error["code"] == "ERROR_MODELO_AGGREGATION_BINDING", refused.output
    context = error["context"]
    assert isinstance(context, dict)
    assert context["reason"] == "inadmissible_deduction_classification", refused.output
    assert context["transaction_id"] == purchase_id
    assert "investment_asset_id" in context["detail"]


def test_work_calculate_refuses_an_attestation_the_period_does_not_ask(
    tmp_path: Path, authority_operation: PinnedAuthorityOperation
) -> None:
    """A 1T calculation that supplies attestation identifiers is refused before custody, not silently ignored."""
    with _operator_session(tmp_path, authority_operation) as session:
        work_unit_id = _create_m303_work_unit(session, "1T")

        refused = _calculate(
            session,
            work_unit_id,
            *OrdinaryM303SecureEvidence(attachment_id="a" * 64, sha256="a" * 64).calculate_options(),
        )

    assert refused.exit_code == 2, refused.output
    assert "exonerado_390_attestation_outside_last_period" in refused.output, refused.output


def test_work_calculate_refuses_the_last_quarter_without_an_attestation(
    tmp_path: Path, authority_operation: PinnedAuthorityOperation
) -> None:
    """4T asks the Modelo 390 exemption, so the joint-return answer alone is refused."""
    with _operator_session(tmp_path, authority_operation) as session:
        work_unit_id = _create_m303_work_unit(session, "4T")

        refused = _calculate(session, work_unit_id, *joint_return_options(joint_return_elected=False))

    assert refused.exit_code == 2, refused.output
    assert "m303_filing_evidence.missing" in refused.output, refused.output
    error = require_error_document(refused.output)["error"]
    assert isinstance(error, dict)
    assert error["code"] == "REFUSED_MODELO_M303_FILING_EVIDENCE"
    context = error["context"]
    assert isinstance(context, dict)
    assert context["period"] == "4T"
    assert context["exonerado_390_attestation_present"] == "false"
    assert context["filing_year"] == str(_EXERCISE)
    assert "attest-m303-exonerado-390" in error["message"]

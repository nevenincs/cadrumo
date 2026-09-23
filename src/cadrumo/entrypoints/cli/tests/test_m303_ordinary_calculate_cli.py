"""Real CLI roundtrip for ordinary 2025 Modelo 303 evidence authoring."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from typing import cast

import pytest

from cadrumo.domain.invoices.tests.catalogue_support import build_invoice_catalogue

from ....adapters.persistence.profile.calculation_observations import IvaWalletDecisionRepository
from ....adapters.persistence.profile.invoices import InvoiceCatalogueRepository
from ....adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from ....adapters.persistence.profile.transactions import TransactionCatalogueRepository
from ....adapters.persistence.storage.tests.profile_capsule_runtime import open_test_profile_session
from ....adapters.persistence.storage.tests.secure_sql import (
    isolated_cli_backend as _isolated_cli_backend,
)
from ....application.aggregation.tests.ledger_transaction_support import iva_transaction
from ....application.invoices.catalogue_creation import build_catalogue_invoice
from ....application.modelo.tests.profile_fixture_values import MODELO_READY_PROFILE_FACTS
from ....core.bucket_pointer import resolve_active_bucket_id
from ....core.period import Period
from ....domain.calculations.registry.tests.published_authority import published_snapshot
from ....domain.invoices.service import link_transaction
from ....domain.iva.classification import InvoiceKind
from ....domain.iva_compensation.reconciliation import IvaCompensationReconciliationDecision
from ....domain.transactions.enums import TransactionDirection
from ....domain.transactions.models import TransactionCatalogue
from ....tests.cli_envelope import unwrap_schema_envelope
from ....tests.recorded_ecb_rates import recorded_ecb_rate_provider
from ._m303_ordinary_cli_support import admit_ordinary_m303_secure_evidence
from ._modelo_work_ux_support import operator_profile_facts
from .cli_runner import invoke_cached_cli
from .modelo_profile_seed import ProfileSeeder, seed_profile
from .test_modelo_work_calculate_loads_profile_once import profile_decrypts

__all__ = ["_isolated_cli_backend"]

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
    pytest.mark.usefixtures("authority_operation"),
]

_PERIOD = Period.from_year_and_code(2025, "1T")
_WALLET_DECIDED_AT = datetime(2025, 4, 1, 10, tzinfo=UTC)


def _ordinary_m303_profile_facts() -> dict[str, str]:
    """Reuse the application readiness baseline with the CLI's 2025 activity fact."""
    facts = {
        fact.path: (str(fact.value).lower() if isinstance(fact.value, bool) else str(fact.value))
        for fact in MODELO_READY_PROFILE_FACTS
    }
    facts.update(operator_profile_facts(activity_start_date="2025-01-01"))
    return facts


def _seed_2025_ledger_and_wallet(bucket_id: str) -> None:
    """Persist the minimum linked IVA evidence and the canonical zero wallet decision."""
    purchase_invoice = build_catalogue_invoice(
        bucket_id=bucket_id,
        kind=InvoiceKind.RECEIVED,
        counterparty_name="Proveedor de prueba SL",
        counterparty_tax_id="A58818501",
        counterparty_country="ES",
        invoice_number="REC-2025-1T",
        issued_at=date(2025, 2, 15),
        taxable_base=Decimal("50.00"),
        iva_rate=Decimal("21"),
        currency="EUR",
        rate_provider=recorded_ecb_rate_provider(),
    )
    sale = iva_transaction(
        "ordinary-2025-sale",
        direction=TransactionDirection.INCOMING,
        amount=Decimal("121.00"),
        taxable_base=Decimal("100.00"),
        iva_amount=Decimal("21.00"),
        booked_date=date(2025, 2, 15),
    )
    purchase = iva_transaction(
        "ordinary-2025-purchase",
        direction=TransactionDirection.OUTGOING,
        amount=Decimal("60.50"),
        taxable_base=Decimal("50.00"),
        iva_amount=Decimal("10.50"),
        booked_date=date(2025, 2, 15),
    ).model_copy(
        update={
            "purchase_invoice_evidence_id": purchase_invoice.invoice_id,
            "invoice_id": purchase_invoice.invoice_id,
        }
    )
    invoice_catalogue = link_transaction(
        build_invoice_catalogue((purchase_invoice,)),
        purchase_invoice.invoice_id,
        purchase.transaction_id,
    )
    snapshot_ref = published_snapshot("303", filing_year=2025, period="1T").snapshot_ref

    with open_test_profile_session(bucket_id):
        TransactionCatalogueRepository(bucket_id=bucket_id).save(
            TransactionCatalogue.from_transactions((sale, purchase)),
        )
        InvoiceCatalogueRepository(bucket_id=bucket_id).save(invoice_catalogue)
        IvaWalletDecisionRepository().save_decision(
            IvaCompensationReconciliationDecision(
                taxpayer_nif="12345678Z",
                target_year=2025,
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


def test_work_calculate_persists_ordinary_2025_m303_evidence_from_secure_attestation(
    request: pytest.FixtureRequest,
) -> None:
    """The installed CLI admits secure evidence then persists its authored envelope once."""
    seeded_profile = cast(ProfileSeeder, request.getfixturevalue(seed_profile.__name__))
    decrypts = cast(list[str], request.getfixturevalue(profile_decrypts.__name__))
    seeded_profile(label="operator", facts=_ordinary_m303_profile_facts())
    bucket_id = resolve_active_bucket_id()
    assert bucket_id is not None
    _seed_2025_ledger_and_wallet(bucket_id)

    admitted = admit_ordinary_m303_secure_evidence()

    created = invoke_cached_cli(
        [
            "--format",
            "json",
            "app",
            "modelo",
            "work",
            "create",
            "--modelo",
            "303",
            "--year",
            "2025",
            "--period",
            "1T",
        ]
    )
    assert created.exit_code == 0, created.output
    work_unit_id = unwrap_schema_envelope(created.output)["work_unit_id"]
    assert isinstance(work_unit_id, str)

    decrypts.clear()
    calculated = invoke_cached_cli(
        [
            "--format",
            "json",
            "app",
            "modelo",
            "work",
            "calculate",
            work_unit_id,
            *admitted.calculate_options(joint_return_elected=True, annual_volume_nonzero=True),
        ]
    )
    assert calculated.exit_code == 0, calculated.output
    assert len(decrypts) == 1, decrypts
    revision_id = unwrap_schema_envelope(calculated.output)["calculation_revision_id"]
    assert isinstance(revision_id, str)

    with open_test_profile_session(bucket_id):
        persisted = CalculationRevisionCatalogueRepository().load().revisions[revision_id]

    evidence = persisted.filing_instance_evidence
    assert evidence is not None
    assert evidence.m303.period == _PERIOD
    assert evidence.m303.joint_return_elected is True
    assert evidence.m303.annual_volume_nonzero is True
    assert evidence.m303.insolvency is None
    exonerado_390 = evidence.m303.exonerado_390
    assert exonerado_390 is not None
    assert exonerado_390.applicable is False
    assert exonerado_390.applicability_reference.reference == (f"attachment:{admitted.attachment_id}:{admitted.sha256}")
    assert evidence.m303.regimen_simplificado.scope_decision.is_not_claimed is True
    assert evidence.m303.regimen_simplificado.rows.activities == ()
    assert evidence.m303.regimen_simplificado.calculation_result.activities == ()

"""CLI roundtrip coverage for source mesh-backed modelo calculation."""

from __future__ import annotations

import json
from collections.abc import Iterator
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from aeat.domain.modelos._calculation_repository import CalculationRevisionCatalogueRepository
from aeat.domain.transactions import (
    BusinessClassification,
    RawProvenance,
    RawTransaction,
    SourceFormat,
    Transaction,
    TransactionCatalogue,
    TransactionCatalogueRepository,
    TransactionDirection,
)
from aeat.tests.cli_runner import invoke_cached_cli
from aeat.tests.secure_sql import isolated_profile_storage_root

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]


@pytest.fixture(autouse=True)
def _isolated_cli_backend(tmp_path: Path) -> Iterator[None]:
    with isolated_profile_storage_root(tmp_path=tmp_path):
        yield


def _create_profile() -> None:
    result = invoke_cached_cli(
        [
            "config",
            "profile",
            "create",
            "operator",
            "--quiet",
            "--accept-defaults",
            "--tax-id",
            "12345678Z",
            "--name",
            "Operator",
            "--activity",
            "design",
        ]
    )
    assert result.exit_code == 0, result.output


def _create_303_work_unit() -> dict[str, object]:
    result = invoke_cached_cli(
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
            "2026",
            "--period",
            "1T",
            "--revision",
            "2009-y-siguientes",
        ]
    )
    assert result.exit_code == 0, result.output
    return json.loads(result.output)


def _raw_transaction(
    provider_id: str,
    *,
    booked_date: date = date(2026, 2, 10),
    amount: Decimal,
) -> RawTransaction:
    return RawTransaction(
        transaction_id=provider_id,
        booked_date=booked_date,
        value_date=booked_date,
        amount=amount,
        currency="EUR",
        counterparty="Cliente o proveedor",
        description=f"ledger row {provider_id}",
        provenance=RawProvenance(
            source_path=Path(__file__),
            source_sha256="f" * 64,
            source_row_index=1,
            source_format=SourceFormat.MANUAL,
            ingested_at=datetime(2026, 2, 11, 12, 0, tzinfo=UTC),
            provider_name="manual-ledger",
        ),
        raw_fields={"source_kind": "ledger_transaction"},
    )


def _transaction(
    provider_id: str,
    *,
    direction: TransactionDirection,
    amount: Decimal,
    taxable_base: Decimal,
    iva_amount: Decimal,
) -> Transaction:
    return Transaction.model_validate(
        {
            "raw": _raw_transaction(provider_id, amount=amount),
            "direction": direction,
            "business_classification": BusinessClassification.BUSINESS,
            "category_id": "test_iva_operation",
            "taxable_base": taxable_base,
            "iva_rate": Decimal("0.21"),
            "iva_amount": iva_amount,
            "classified_at": datetime(2026, 2, 11, 13, 0, tzinfo=UTC),
            "classified_by": "manual",
        }
    )


def test_work_calculate_persists_ledger_source_mesh_observations() -> None:
    from aeat.application.user_profile._orchestration import profile_storage_session

    _create_profile()
    work_unit = _create_303_work_unit()
    bucket_id = str(work_unit["bucket_id"])
    sale = _transaction(
        "sale-general",
        direction=TransactionDirection.INCOMING,
        amount=Decimal("121.00"),
        taxable_base=Decimal("100.00"),
        iva_amount=Decimal("21.00"),
    )
    purchase = _transaction(
        "purchase-general",
        direction=TransactionDirection.OUTGOING,
        amount=Decimal("-60.50"),
        taxable_base=Decimal("50.00"),
        iva_amount=Decimal("10.50"),
    )

    # Seed ledger data and a zero-amount IVA wallet decision via a live
    # profile session.  The CLI runner resets the ContextVar on each
    # invocation exit so direct repository calls that depend on an active
    # bucket session must enter their own session block.
    # The IVA wallet decision is required by the Modelo 303 reconciliation
    # guard: it blocks calculation when ``compensacion-pendiente-anteriores``
    # is supplied without a persisted decision, even when the amount is zero.
    # A local_recurrence decision with selected_amount=0 satisfies the guard
    # while leaving the ledger mesh assertions meaningful.
    with profile_storage_session(bucket_id):
        from datetime import UTC, datetime

        from aeat.application.calculations._iva_wallet_reconciliation import (
            IvaCompensationReconciliationDecision,
        )
        from aeat.application.calculations._observations_repository import IvaWalletDecisionRepository

        TransactionCatalogueRepository(bucket_id=bucket_id).save(
            TransactionCatalogue.from_transactions((sale, purchase))
        )
        decision = IvaCompensationReconciliationDecision(
            taxpayer_nif="12345678Z",
            target_year=2026,
            target_period="1T",
            selected_authority="local_recurrence",
            selected_amount=Decimal("0"),
            wallet_amount=None,
            local_recurrence_amount=Decimal("0"),
            override_amount=None,
            divergence="wallet_missing",
            blocked=False,
            stale_wallet=False,
            reason="test: no prior IVA compensation",
            decided_at=datetime.now(UTC),
        )
        IvaWalletDecisionRepository().save_decision(decision)

    result = invoke_cached_cli(
        [
            "--format",
            "json",
            "app",
            "modelo",
            "work",
            "calculate",
            str(work_unit["work_unit_id"]),
        ]
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    revision_id = payload["calculation_revision_id"]

    with profile_storage_session(bucket_id):
        persisted = CalculationRevisionCatalogueRepository().load().revisions[revision_id]

    assert persisted.source_transaction_ids == tuple(sorted((sale.transaction_id, purchase.transaction_id)))
    assert Decimal(persisted.binding_overrides["modelo-303-iva-repercutido-general-cuota"]) == sale.iva_amount
    assert Decimal(persisted.binding_overrides["modelo-303-iva-soportado-interiores-cuota"]) == purchase.iva_amount
    observations = {observation.casilla_id: observation for observation in persisted.observations}
    output_observation = observations["iva.repercutido.general"]
    input_observation = observations["iva.soportado.interiores"]
    assert output_observation.formula_id is None
    assert input_observation.formula_id is None
    assert output_observation.legal_refs
    assert input_observation.legal_refs
    assert output_observation.source_refs
    assert input_observation.source_refs
    payload_observations = {observation["casilla_id"]: observation for observation in payload["observations"]}
    assert payload_observations["iva.repercutido.general"]["source_refs"] == list(output_observation.source_refs)
    assert payload_observations["iva.soportado.interiores"]["source_refs"] == list(input_observation.source_refs)

"""CLI roundtrip coverage for source mesh-backed modelo calculation."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ....domain.iva import EUMemberState, IvaCategory
from ....domain.modelos._calculation_repository import CalculationRevisionCatalogueRepository
from ....domain.transactions import (
    BusinessClassification,
    RawProvenance,
    RawTransaction,
    SourceFormat,
    Transaction,
    TransactionCatalogue,
    TransactionCatalogueRepository,
    TransactionDirection,
)
from ....tests.cli_runner import invoke_cached_cli
from ....tests.secure_sql import isolated_profile_storage_root
from .envelope_helpers import unwrap_envelope_notices
from .envelope_helpers import unwrap_schema_envelope as _payload

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


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
            "2023-y-siguientes",
        ]
    )
    assert result.exit_code == 0, result.output
    return _payload(result.output)


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
    iva_category: IvaCategory | None = None,
    counterparty_eu_member_state: EUMemberState | None = None,
) -> Transaction:
    fields: dict[str, object] = {
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
    if iva_category is not None:
        fields["iva_category"] = iva_category
    if counterparty_eu_member_state is not None:
        fields["counterparty_eu_member_state"] = counterparty_eu_member_state
    return Transaction.model_validate(fields)


def test_work_calculate_persists_ledger_source_mesh_observations() -> None:
    from ....application.user_profile._orchestration import profile_storage_session
    from ....core import resolve_active_bucket_id

    _create_profile()
    work_unit = _create_303_work_unit()
    # The CLI JSON output redacts ``bucket_id`` to the literal placeholder
    # ``"<bucket-id>"``; that placeholder is not a valid filesystem path
    # segment on Windows (``<`` / ``>`` are reserved). Resolve the real
    # bucket id from the active-profile pointer the freshly-created
    # profile installed.
    resolved = resolve_active_bucket_id()
    assert resolved is not None, "profile create must install an active-profile pointer"
    bucket_id = resolved
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
        amount=Decimal("60.50"),
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

        from ....application.calculations._observations_repository import IvaWalletDecisionRepository
        from ....domain.iva_compensation._reconciliation import (
            IvaCompensationReconciliationDecision,
        )

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
    payload = _payload(result.output)
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


def _seed_zero_iva_wallet_decision(bucket_id: str) -> None:
    """Persist a zero-amount local-recurrence IVA wallet decision for bucket.

    The Modelo 303 reconciliation guard blocks calculation when
    ``compensacion-pendiente-anteriores`` is supplied without a persisted
    decision, even when the amount is zero. A ``local_recurrence`` decision
    with ``selected_amount=0`` satisfies the guard while leaving the source-mesh
    advisory assertions meaningful.
    """
    from ....application.calculations._observations_repository import IvaWalletDecisionRepository
    from ....application.user_profile._orchestration import profile_storage_session
    from ....domain.iva_compensation._reconciliation import IvaCompensationReconciliationDecision

    with profile_storage_session(bucket_id):
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


def test_work_calculate_surfaces_unconsumed_declarable_iva_advisory() -> None:
    """#64: an INTRA_COMMUNITY_SUPPLY sale no M303 binding consumes surfaces as an advisory.

    The M303 ``ledger_iva_aggregation`` bindings select domestic +
    intra-community-acquisition triples only; an ``INTRA_COMMUNITY_SUPPLY``
    repercutido observation is declarable (Ley 37/1992 art. 25) but matches no
    binding selector. The resolver emits a NON-blocking diagnostic; this test
    asserts it survives the threading all the way to the operator-facing CLI in
    BOTH the JSON ``source_advisories`` list AND the human output, so an unrouted
    declarable observation is never silently under-declared
    (no-silent-under-declaration).
    """
    from ....application.user_profile._orchestration import profile_storage_session
    from ....core import resolve_active_bucket_id

    _create_profile()
    work_unit = _create_303_work_unit()
    resolved = resolve_active_bucket_id()
    assert resolved is not None, "profile create must install an active-profile pointer"
    bucket_id = resolved

    # A consumed domestic sale (matches the repercutido-general binding) ...
    domestic_sale = _transaction(
        "sale-general",
        direction=TransactionDirection.INCOMING,
        amount=Decimal("121.00"),
        taxable_base=Decimal("100.00"),
        iva_amount=Decimal("21.00"),
    )
    # ... plus a declarable intra-community supply NO M303 binding selects.
    unrouted_supply = _transaction(
        "intra-community-supply",
        direction=TransactionDirection.INCOMING,
        amount=Decimal("242.00"),
        taxable_base=Decimal("200.00"),
        iva_amount=Decimal("42.00"),
        iva_category=IvaCategory.INTRA_COMMUNITY_SUPPLY,
        counterparty_eu_member_state=EUMemberState.DE,
    )
    with profile_storage_session(bucket_id):
        TransactionCatalogueRepository(bucket_id=bucket_id).save(
            TransactionCatalogue.from_transactions((domestic_sale, unrouted_supply))
        )
    _seed_zero_iva_wallet_decision(bucket_id)

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

    notices = unwrap_envelope_notices(result.output)
    matching = [
        notice
        for notice in notices
        if notice["code"] == "modelo.work.calculate.source_advisory"
        and (notice.get("context") or {}).get("source_kind") == "ledger_iva_aggregation"
        and unrouted_supply.transaction_id in notice["message"]
    ]
    assert len(matching) == 1, notices
    advisory = matching[0]
    assert advisory["severity"] == "warning"
    assert advisory["context"]["reason"] == "source_issue"
    assert IvaCategory.INTRA_COMMUNITY_SUPPLY.value in advisory["message"]

    # The human-readable (default text) rendering carries the same advisory.
    # Re-run in text mode against the same seeded bucket; the calculate verb is
    # idempotent over the ledger substrate (it persists a new draft revision but
    # surfaces the identical unconsumed-IVA advisory).
    text_result = invoke_cached_cli(
        [
            "app",
            "modelo",
            "work",
            "calculate",
            str(work_unit["work_unit_id"]),
        ]
    )
    assert text_result.exit_code == 0, text_result.output
    assert "ADVISORY:" in text_result.output
    assert unrouted_supply.transaction_id in text_result.output
    assert IvaCategory.INTRA_COMMUNITY_SUPPLY.value in text_result.output


def test_work_calculate_emits_no_advisory_when_all_iva_consumed() -> None:
    """#64 converse: an all-consumed IVA observation set surfaces ZERO advisories.

    Anti-tautology guard for the advisory test above: only observations no
    binding selects produce a diagnostic. A domestic sale matched by the
    repercutido-general binding must leave ``source_advisories`` empty and emit
    no ADVISORY line.
    """
    from ....application.user_profile._orchestration import profile_storage_session
    from ....core import resolve_active_bucket_id

    _create_profile()
    work_unit = _create_303_work_unit()
    resolved = resolve_active_bucket_id()
    assert resolved is not None, "profile create must install an active-profile pointer"
    bucket_id = resolved

    domestic_sale = _transaction(
        "sale-general",
        direction=TransactionDirection.INCOMING,
        amount=Decimal("121.00"),
        taxable_base=Decimal("100.00"),
        iva_amount=Decimal("21.00"),
    )
    with profile_storage_session(bucket_id):
        TransactionCatalogueRepository(bucket_id=bucket_id).save(
            TransactionCatalogue.from_transactions((domestic_sale,))
        )
    _seed_zero_iva_wallet_decision(bucket_id)

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

    notices = unwrap_envelope_notices(result.output)
    assert [n for n in notices if n["code"] == "modelo.work.calculate.source_advisory"] == []

    # Text mode emits no ADVISORY line either: only an unrouted declarable
    # observation produces one, and every observation here was consumed.
    text_result = invoke_cached_cli(
        [
            "app",
            "modelo",
            "work",
            "calculate",
            str(work_unit["work_unit_id"]),
        ]
    )
    assert text_result.exit_code == 0, text_result.output
    assert "ADVISORY:" not in text_result.output

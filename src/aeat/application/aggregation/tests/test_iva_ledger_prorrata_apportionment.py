"""Prorrata apportionment regressions for the shared IVA ledger path."""

from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ....adapters.persistence.profile.prorrata_register import ProrrataRegisterRepository
from ....adapters.persistence.profile.transactions import TransactionCatalogueRepository
from ....core import Period, ProrrataProvisionalProvenance, ProrrataRegisterRegime
from ....core.resources import resources
from ....domain.calculations.registry import BindingId
from ....domain.prorrata_register import ProrrataRegister, ProrrataRegisterEntry
from ....domain.transactions import (
    BusinessClassification,
    RawProvenance,
    RawTransaction,
    SourceFormat,
    Transaction,
    TransactionCatalogue,
    TransactionDirection,
)
from ....tests.secure_sql import isolated_runtime_profile
from .. import aggregate_iva_ledger_observations_from_repositories
from .._iva_ledger import resolve_iva_ledger_binding_values

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET_ID = "78787878-7878-4878-8878-787878787878"
_PERIOD = Period.from_year_and_code(2026, "1T")
_DEVENGADO_CUOTA_BINDING: BindingId = "modelo-303-iva-repercutido-general-cuota"
_DEDUCIBLE_BASE_BINDING: BindingId = "modelo-303-iva-soportado-interiores-base"
_DEDUCIBLE_CUOTA_BINDING: BindingId = "modelo-303-iva-soportado-interiores-cuota"


def _raw_transaction(
    provider_id: str,
    *,
    amount: Decimal = Decimal("60.50"),
    counterparty: str = "Proveedor plenamente deducible",
) -> RawTransaction:
    return RawTransaction(
        provider_transaction_id=provider_id,
        booked_date=date(2026, 2, 10),
        value_date=date(2026, 2, 10),
        amount=amount,
        currency="EUR",
        counterparty=counterparty,
        description=f"ledger row {provider_id}",
        provenance=RawProvenance(
            source_path=Path(__file__),
            source_sha256="7" * 64,
            source_row_index=1,
            source_format=SourceFormat.MANUAL,
            ingested_at=datetime(2026, 2, 11, 12, 0, tzinfo=UTC),
            provider_name="manual-ledger",
        ),
        raw_fields={"source_kind": "ledger_transaction"},
    )


def _fully_taxable_purchase(provider_id: str) -> Transaction:
    return Transaction.model_validate(
        {
            "raw": _raw_transaction(provider_id),
            "direction": TransactionDirection.OUTGOING,
            "business_classification": BusinessClassification.BUSINESS,
            "source_jurisdiction": "ES",
            "group_label": None,
            "category_id": "fully_taxable_purchase",
            "taxable_base": Decimal("50.00"),
            "iva_rate": Decimal("0.21"),
            "iva_amount": Decimal("10.50"),
            "classified_at": datetime(2026, 2, 11, 13, 0, tzinfo=UTC),
            "classified_by": "manual",
        },
    )


def _fully_taxable_sale(provider_id: str) -> Transaction:
    return Transaction.model_validate(
        {
            "raw": _raw_transaction(
                provider_id,
                amount=Decimal("121.00"),
                counterparty="Cliente plenamente sujeto",
            ),
            "direction": TransactionDirection.INCOMING,
            "business_classification": BusinessClassification.BUSINESS,
            "source_jurisdiction": "ES",
            "group_label": None,
            "category_id": "fully_taxable_sale",
            "taxable_base": Decimal("100.00"),
            "iva_rate": Decimal("0.21"),
            "iva_amount": Decimal("21.00"),
            "classified_at": datetime(2026, 2, 11, 13, 0, tzinfo=UTC),
            "classified_by": "manual",
        },
    )


def _canonical_binding_bytes(values: Mapping[BindingId, Decimal]) -> bytes:
    return json.dumps(
        {binding_id: str(values[binding_id]) for binding_id in sorted(values)},
        separators=(",", ":"),
        sort_keys=True,
    ).encode()


def test_non_prorrata_register_keeps_fully_taxable_deducible_aggregation_byte_identical(tmp_path: Path) -> None:
    """A taxpayer recorded as no-prorrata keeps the previous full-deduction output."""
    revision = resources().modelos.get("303").revisions["2009-y-siguientes"]
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        objects = profile.repository
        tx_repo = TransactionCatalogueRepository(bucket_id=_BUCKET_ID, objects=objects)
        tx_repo.save(TransactionCatalogue.from_transactions((_fully_taxable_purchase("purchase-full"),)))

        baseline = aggregate_iva_ledger_observations_from_repositories(
            bucket_id=_BUCKET_ID,
            period=_PERIOD,
            transaction_repository=tx_repo,
        )
        baseline_binding_bytes = _canonical_binding_bytes(
            resolve_iva_ledger_binding_values(
                revision,
                baseline.observations,
                prorrata_apportionment=baseline.prorrata_apportionment,
            ),
        )
        baseline_aggregation_bytes = baseline.model_dump_json().encode()

        ProrrataRegisterRepository(bucket_id=_BUCKET_ID, objects=objects).save(
            ProrrataRegister(
                entries=(
                    ProrrataRegisterEntry(
                        ejercicio=2026,
                        regime=ProrrataRegisterRegime.NINGUNA,
                    ),
                ),
            ),
        )
        non_prorrata = aggregate_iva_ledger_observations_from_repositories(
            bucket_id=_BUCKET_ID,
            period=_PERIOD,
            transaction_repository=tx_repo,
        )
        non_prorrata_binding_bytes = _canonical_binding_bytes(
            resolve_iva_ledger_binding_values(
                revision,
                non_prorrata.observations,
                prorrata_apportionment=non_prorrata.prorrata_apportionment,
            ),
        )

    assert non_prorrata.model_dump_json().encode() == baseline_aggregation_bytes
    assert non_prorrata_binding_bytes == baseline_binding_bytes


def test_general_prorrata_register_reduces_deducible_cuota_without_reducing_base(tmp_path: Path) -> None:
    """The active provisional percentage bites only on deducible IVA cuota fields."""
    revision = resources().modelos.get("303").revisions["2009-y-siguientes"]
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        objects = profile.repository
        tx_repo = TransactionCatalogueRepository(bucket_id=_BUCKET_ID, objects=objects)
        tx_repo.save(
            TransactionCatalogue.from_transactions(
                (
                    _fully_taxable_sale("sale-full"),
                    _fully_taxable_purchase("purchase-prorrata"),
                ),
            ),
        )

        baseline = aggregate_iva_ledger_observations_from_repositories(
            bucket_id=_BUCKET_ID,
            period=_PERIOD,
            transaction_repository=tx_repo,
        )
        baseline_values = resolve_iva_ledger_binding_values(
            revision,
            baseline.observations,
            prorrata_apportionment=baseline.prorrata_apportionment,
        )

        ProrrataRegisterRepository(bucket_id=_BUCKET_ID, objects=objects).save(
            ProrrataRegister(
                entries=(
                    ProrrataRegisterEntry(
                        ejercicio=2026,
                        regime=ProrrataRegisterRegime.GENERAL,
                        provisional_percentage=Decimal("80"),
                        provisional_provenance=ProrrataProvisionalProvenance.CARRIED_PRIOR_DEFINITIVA,
                        source_observation_ref="303:2025:4T",
                    ),
                ),
            ),
        )
        apportioned = aggregate_iva_ledger_observations_from_repositories(
            bucket_id=_BUCKET_ID,
            period=_PERIOD,
            transaction_repository=tx_repo,
        )
        apportioned_values = resolve_iva_ledger_binding_values(
            revision,
            apportioned.observations,
            prorrata_apportionment=apportioned.prorrata_apportionment,
        )

    assert baseline.prorrata_apportionment is None
    assert apportioned.prorrata_apportionment is not None
    assert apportioned.prorrata_apportionment.percentage == Decimal("80")
    assert (
        apportioned.prorrata_apportionment.provenance
        is ProrrataProvisionalProvenance.CARRIED_PRIOR_DEFINITIVA
    )
    assert apportioned_values[_DEDUCIBLE_CUOTA_BINDING] < baseline_values[_DEDUCIBLE_CUOTA_BINDING]
    assert apportioned_values[_DEDUCIBLE_BASE_BINDING] == baseline_values[_DEDUCIBLE_BASE_BINDING]
    assert apportioned_values[_DEVENGADO_CUOTA_BINDING] == baseline_values[_DEVENGADO_CUOTA_BINDING]

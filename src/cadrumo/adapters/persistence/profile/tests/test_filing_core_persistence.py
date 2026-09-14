"""Profile-persistence integration coverage for filing approval fingerprints."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from cadrumo.adapters.persistence.profile.transactions import TransactionCatalogueRepository
from cadrumo.adapters.persistence.storage.tests.profile_capsule_runtime import seed_test_profile_record
from cadrumo.adapters.persistence.storage.tests.secure_sql import isolated_runtime_profile
from cadrumo.application.filing.draft_construction import build_draft
from cadrumo.application.filing.draft_review import compute_current_approval_basis
from cadrumo.application.filing.runtime import ModeloOperatorProfile, build_runtime_schema_provider
from cadrumo.application.filing.tests.filing_support import empty_profile_activity_fingerprint
from cadrumo.core.casilla_id import CasillaId, validated_casilla_id
from cadrumo.core.period import Period
from cadrumo.domain.filing.protocols import CasillaSchemaProvider
from cadrumo.domain.filing.schema import ModeloDraft
from cadrumo.domain.transactions.enums import TransactionDirection
from cadrumo.domain.transactions.models import Transaction, TransactionCatalogue
from cadrumo.domain.transactions.raw_transaction import RawProvenance, RawTransaction, SourceFormat
from cadrumo.domain.user_profile.values import ProfileSetupState, UserProfileFact, UserProfileRecord

pytestmark = [pytest.mark.integration, pytest.mark.hex_persistence_adapter]

_BUCKET_ID = "66666666-6666-4666-8666-666666666666"
_PROFILE_SEEDED_AT = datetime(2025, 1, 6, 9, 0, 0, tzinfo=UTC)
_PERIOD = Period.from_year_and_code(2026, "1T")

_M130_CASILLA_01: CasillaId = validated_casilla_id("01", surface="test_filing_persistence.casilla")
_M130_CASILLA_02: CasillaId = validated_casilla_id("02", surface="test_filing_persistence.casilla")
_M130_CASILLA_05: CasillaId = validated_casilla_id("05", surface="test_filing_persistence.casilla")
_M130_CASILLA_06: CasillaId = validated_casilla_id("06", surface="test_filing_persistence.casilla")
_M130_CASILLA_08: CasillaId = validated_casilla_id("08", surface="test_filing_persistence.casilla")
_M130_CASILLA_10: CasillaId = validated_casilla_id("10", surface="test_filing_persistence.casilla")
_M130_CASILLA_16: CasillaId = validated_casilla_id("16", surface="test_filing_persistence.casilla")
_M130_CASILLA_18: CasillaId = validated_casilla_id("18", surface="test_filing_persistence.casilla")


def _profile() -> ModeloOperatorProfile:
    return ModeloOperatorProfile(
        tax_id="12345678Z",
        display_name="Registry boundary persistence test",
    )


def _schema_provider() -> CasillaSchemaProvider:
    return build_runtime_schema_provider(modelos=("130",), filing_year=_PERIOD.filing_year, period=_PERIOD)


def _draft(schema_provider: CasillaSchemaProvider | None = None) -> ModeloDraft:
    return build_draft(
        modelo="130",
        period=_PERIOD,
        profile=_profile(),
        inputs={
            _M130_CASILLA_01: Decimal("12500.00"),
            _M130_CASILLA_02: Decimal("3500.00"),
            _M130_CASILLA_05: Decimal("250"),
            _M130_CASILLA_06: Decimal("100"),
            _M130_CASILLA_08: Decimal("2000"),
            _M130_CASILLA_10: Decimal("10"),
            "irpf.previous_year_economic_activity_net_income": Decimal("13000"),
            "modelo-130-pagos-fraccionados-anteriores": Decimal("250"),
            "modelo-130-resultados-negativos-anteriores": Decimal("0"),
            _M130_CASILLA_16: Decimal("0"),
            _M130_CASILLA_18: Decimal("0"),
        },
        schema_provider=schema_provider or _schema_provider(),
    )


def _transaction(*, provider_id: str, amount: Decimal, description: str) -> Transaction:
    raw = RawTransaction(
        provider_transaction_id=provider_id,
        booked_date=date(2026, 4, 10),
        value_date=date(2026, 4, 10),
        amount=amount,
        currency="EUR",
        counterparty="Supplier SL",
        description=description,
        provenance=RawProvenance(
            source_path=Path(f"/bank/{provider_id}.csv"),
            source_sha256="c" * 64,
            source_row_index=1,
            source_format=SourceFormat.CSV,
            ingested_at=datetime(2026, 4, 14, 9, 30, tzinfo=UTC),
            provider_name="CSV provider",
        ),
        raw_fields={"Concepto": description},
    )
    return Transaction.model_validate(
        {
            "raw": raw,
            "direction": TransactionDirection.OUTGOING,
            "group_label": None,
            "source_jurisdiction": "ES",
        },
    )


def test_approval_basis_reloads_persisted_transaction_catalogue(tmp_path: Path) -> None:
    """Both fingerprints are self-loaded from one provisioned profile capsule."""
    schema_provider = _schema_provider()
    draft = _draft(schema_provider)

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        seed_test_profile_record(
            UserProfileRecord(
                setup_state=ProfileSetupState.COMPLETE,
                profile_id=profile.bucket_id,
                facts=(UserProfileFact(path="identity.tax_id", value="12345678Z"),),
                created_at=_PROFILE_SEEDED_AT,
                updated_at=_PROFILE_SEEDED_AT,
            ),
        )
        repository = TransactionCatalogueRepository(bucket_id=profile.bucket_id)

        repository.save(
            TransactionCatalogue.from_transactions(
                (
                    _transaction(
                        provider_id="first-catalogue-row",
                        amount=Decimal("80.00"),
                        description="First persisted catalogue row",
                    ),
                ),
            ),
        )
        first_basis = compute_current_approval_basis(
            draft,
            bucket_id=profile.bucket_id,
            schema_provider=schema_provider,
        )

        repository.save(
            TransactionCatalogue.from_transactions(
                (
                    _transaction(
                        provider_id="second-catalogue-row",
                        amount=Decimal("125.00"),
                        description="Second persisted catalogue row",
                    ),
                ),
            ),
        )
        second_basis = compute_current_approval_basis(
            draft,
            bucket_id=profile.bucket_id,
            schema_provider=schema_provider,
        )

    assert first_basis.transaction_catalogue_fingerprint != second_basis.transaction_catalogue_fingerprint
    assert first_basis.profile_activity_fingerprint == second_basis.profile_activity_fingerprint
    assert first_basis.profile_activity_fingerprint != empty_profile_activity_fingerprint()

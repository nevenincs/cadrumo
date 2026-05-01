"""Tests for T6 transaction-catalogue casilla aggregation."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterator
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError
from typer.testing import CliRunner

from aeat.adapters.persistence.storage import (
    EncryptedBlobStore,
    EphemeralMasterKeyProvider,
    SecretStore,
    override_master_key_provider,
    override_secret_store,
)
from aeat.application.workflow import FinancialThenJsonInputsProvider, JsonFileInputsProvider
from aeat.entrypoints.cli import SCHEMA_REGISTRY
from aeat.entrypoints.cli import app as root_app
from aeat.domain.deadlines import AutonomoProfile, IVARegime
from aeat.domain.formulas import Engine, FiscalPeriod, Quarter, get_registry
from aeat.domain.modelos import ModeloCode
from aeat.adapters.inbound.financial import RawProvenance, RawTransaction, SourceFormat
from aeat.domain.categories import CATEGORY_PROFILES_2025, SpendingCategory
from aeat.domain.deadlines import PeriodKind as DeadlinePeriodKind
from aeat.domain.transactions import (
    BusinessClassification,
    Transaction,
    TransactionCatalogue,
    TransactionDirection,
    set_classification,
)
from aeat.domain.transactions import TransactionCatalogueRepository
from aeat.application.aggregation import (
    AggregationCasillaMappingError,
    AggregationError,
    AggregationMissingClassificationError,
    AggregationPeriodError,
    AggregationUnsupportedModeloError,
    Period,
    PeriodKind,
    aggregate_catalogue,
)
from aeat.application.aggregation import FinancialFilingInputsProvider

pytestmark = [pytest.mark.unit, pytest.mark.domain_model]

_RUNNER = CliRunner()


def _profile() -> AutonomoProfile:
    return AutonomoProfile(
        tax_id="X1234567L",
        iva_regime=IVARegime.GENERAL,
        has_employees=False,
        pays_professionals_with_retencion=False,
        professional_income_withholding_ge_70pct=False,
        pays_rent_with_retencion=False,
        does_intracomunitario=False,
        third_party_transactions_above_347_threshold=False,
        bienes_extranjero_above_threshold=False,
        notes="T6 aggregation fixture",
    )


@pytest.fixture
def encrypted_store(tmp_path: Path) -> Iterator[Path]:
    provider = EphemeralMasterKeyProvider()
    override_master_key_provider(provider)
    override_secret_store(
        SecretStore(
            store_dir=tmp_path / "secrets",
            blob_store=EncryptedBlobStore(root_dir=tmp_path / "blobs", master_key_provider=provider),
            master_key_provider=provider,
        )
    )
    try:
        yield tmp_path / "tx-store"
    finally:
        override_master_key_provider(None)
        override_secret_store(None)


def _provenance(tmp_path: Path, *, row_index: int) -> RawProvenance:
    source = tmp_path / "bank.csv"
    if not source.exists():
        source.write_text("bank fixture", encoding="utf-8")
    return RawProvenance(
        source_path=source,
        source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
        source_row_index=row_index,
        source_format=SourceFormat.CSV,
        ingested_at=datetime(2025, 4, 1, tzinfo=UTC),
        provider_name="fixture-bank",
    )


def _transaction(
    tmp_path: Path,
    *,
    provider_id: str,
    amount: Decimal,
    booked_date: date,
    row_index: int,
) -> Transaction:
    raw = RawTransaction(
        transaction_id=provider_id,
        booked_date=booked_date,
        value_date=None,
        amount=amount,
        currency="EUR",
        counterparty=None,
        description=provider_id,
        provenance=_provenance(tmp_path, row_index=row_index),
        raw_fields={"id": provider_id, "amount": str(amount)},
    )
    direction = TransactionDirection.INCOMING if amount > 0 else TransactionDirection.OUTGOING
    return Transaction.model_validate({"raw": raw, "direction": direction})


def _classified_catalogue(tmp_path: Path) -> TransactionCatalogue:
    income = _transaction(
        tmp_path,
        provider_id="client-income",
        amount=Decimal("1000.00"),
        booked_date=date(2025, 2, 1),
        row_index=1,
    )
    office = _transaction(
        tmp_path,
        provider_id="office-supplies",
        amount=Decimal("-200.00"),
        booked_date=date(2025, 2, 2),
        row_index=2,
    )
    home = _transaction(
        tmp_path,
        provider_id="home-electricity",
        amount=Decimal("-100.00"),
        booked_date=date(2025, 2, 3),
        row_index=3,
    )
    future = _transaction(
        tmp_path,
        provider_id="q2-expense",
        amount=Decimal("-50.00"),
        booked_date=date(2025, 4, 1),
        row_index=4,
    )
    catalogue = TransactionCatalogue.from_transactions([income, office, home, future])
    catalogue = set_classification(
        catalogue,
        income.transaction_id,
        classification=BusinessClassification.BUSINESS,
        classified_by="manual",
        reason="client payment",
    )
    catalogue = set_classification(
        catalogue,
        office.transaction_id,
        classification=BusinessClassification.BUSINESS,
        category_id=SpendingCategory.MATERIAL_OFICINA.value,
        classified_by="manual",
        reason="office supplies",
    )
    catalogue = set_classification(
        catalogue,
        home.transaction_id,
        classification=BusinessClassification.BUSINESS,
        category_id=SpendingCategory.SUMINISTROS_HOME_OFFICE_LUZ.value,
        classified_by="manual",
        reason="home office supply",
    )
    catalogue = set_classification(
        catalogue,
        future.transaction_id,
        classification=BusinessClassification.BUSINESS,
        category_id=SpendingCategory.MATERIAL_OFICINA.value,
        classified_by="manual",
        reason="outside period",
    )
    return catalogue


def test_period_accepts_quarter_with_dash_and_is_frozen() -> None:
    period = Period.model_validate("2025-Q1")

    assert period.raw == "2025Q1"
    assert period.start == date(2025, 1, 1)
    assert period.end == date(2025, 3, 31)
    with pytest.raises(ValidationError):
        period.year = 2026  # type: ignore[misc]


def test_aggregation_reuses_deadline_period_kind() -> None:
    assert PeriodKind is DeadlinePeriodKind
    assert PeriodKind.QUARTERLY.value == "quarterly"


def test_period_mapping_accepts_legacy_uppercase_kind() -> None:
    period = Period.model_validate({"raw": "2025Q1", "year": 2025, "quarter": "Q1", "kind": "QUARTERLY"})
    assert period.kind is PeriodKind.QUARTERLY


def test_period_rejects_ambiguous_text() -> None:
    with pytest.raises(AggregationPeriodError):
        Period.model_validate("2025-Q5")


def test_modelo_130_aggregation_produces_inputs_and_provenance(tmp_path: Path) -> None:
    aggregation = aggregate_catalogue(_classified_catalogue(tmp_path), modelo="130", period="2025-Q1")

    assert aggregation.modelo == "130"
    assert aggregation.casilla_values == {"01": Decimal("1000.00"), "02": Decimal("230.0000")}
    assert [(row.casilla, row.category_id, row.subtotal) for row in aggregation.provenance] == [
        ("01", None, Decimal("1000.00")),
        ("02", "material_oficina", Decimal("200.00")),
        ("02", "suministros_home_office_luz", Decimal("30.0000")),
    ]


def test_aggregation_outputs_feed_formula_engine(tmp_path: Path) -> None:
    aggregation = aggregate_catalogue(_classified_catalogue(tmp_path), modelo=ModeloCode.MODELO_130, period="2025Q1")
    ruleset = get_registry().resolve(
        modelo=ModeloCode.MODELO_130,
        period=FiscalPeriod(year=2025, quarter=Quarter.Q1),
    )

    ledger = Engine().derive(ruleset=ruleset, inputs=aggregation.casilla_values)

    assert ledger.value("03") == Decimal("770.0000")
    assert ledger.value("04") == Decimal("154.000000")


def test_mixed_transaction_multiplies_business_pct_and_profile_ratio(tmp_path: Path) -> None:
    home = _transaction(
        tmp_path,
        provider_id="mixed-home-electricity",
        amount=Decimal("-100.00"),
        booked_date=date(2025, 2, 3),
        row_index=1,
    )
    catalogue = set_classification(
        TransactionCatalogue.from_transactions([home]),
        home.transaction_id,
        classification=BusinessClassification.MIXED,
        business_pct=Decimal("0.50"),
        category_id=SpendingCategory.SUMINISTROS_HOME_OFFICE_LUZ.value,
        classified_by="manual",
        reason="mixed home office supply",
    )

    aggregation = aggregate_catalogue(catalogue, modelo="130", period="2025-Q1")

    assert aggregation.casilla_values == {"02": Decimal("15.000000")}


def test_modelo_130_refuses_computed_expense_mapping(tmp_path: Path) -> None:
    office = _transaction(
        tmp_path,
        provider_id="office-supplies",
        amount=Decimal("-200.00"),
        booked_date=date(2025, 2, 2),
        row_index=1,
    )
    catalogue = set_classification(
        TransactionCatalogue.from_transactions([office]),
        office.transaction_id,
        classification=BusinessClassification.BUSINESS,
        category_id=SpendingCategory.MATERIAL_OFICINA.value,
        classified_by="manual",
        reason="office supplies",
    )
    profile = CATEGORY_PROFILES_2025[SpendingCategory.MATERIAL_OFICINA]
    computed_mapping = profile.casilla_mappings[0].model_copy(update={"casilla_code": "03"})
    overridden_profile = profile.model_copy(update={"casilla_mappings": (computed_mapping,)})
    profiles = {**CATEGORY_PROFILES_2025, SpendingCategory.MATERIAL_OFICINA: overridden_profile}

    with pytest.raises(AggregationCasillaMappingError):
        aggregate_catalogue(catalogue, modelo="130", period="2025-Q1", category_profiles=profiles)


def test_default_profiles_are_resolved_from_period_year(tmp_path: Path) -> None:
    with pytest.raises(AggregationCasillaMappingError):
        aggregate_catalogue(_classified_catalogue(tmp_path), modelo="130", period="2026-Q1")


def test_category_with_multiple_modelo_130_mappings_is_refused(tmp_path: Path) -> None:
    office = _transaction(
        tmp_path,
        provider_id="office-supplies",
        amount=Decimal("-200.00"),
        booked_date=date(2025, 2, 2),
        row_index=1,
    )
    catalogue = set_classification(
        TransactionCatalogue.from_transactions([office]),
        office.transaction_id,
        classification=BusinessClassification.BUSINESS,
        category_id=SpendingCategory.MATERIAL_OFICINA.value,
        classified_by="manual",
        reason="office supplies",
    )
    profile = CATEGORY_PROFILES_2025[SpendingCategory.MATERIAL_OFICINA]
    alternate_mapping = profile.casilla_mappings[0].model_copy(update={"casilla_code": "05"})
    overridden_profile = profile.model_copy(
        update={"casilla_mappings": (profile.casilla_mappings[0], alternate_mapping)}
    )
    profiles = {**CATEGORY_PROFILES_2025, SpendingCategory.MATERIAL_OFICINA: overridden_profile}

    with pytest.raises(AggregationCasillaMappingError):
        aggregate_catalogue(catalogue, modelo="130", period="2025-Q1", category_profiles=profiles)


def test_unclassified_in_period_transaction_is_refused(tmp_path: Path) -> None:
    transaction = _transaction(
        tmp_path,
        provider_id="pending",
        amount=Decimal("10.00"),
        booked_date=date(2025, 2, 1),
        row_index=1,
    )
    catalogue = TransactionCatalogue.from_transactions([transaction])

    with pytest.raises(AggregationMissingClassificationError):
        aggregate_catalogue(catalogue, modelo="130", period="2025Q1")


def test_m303_is_deferred_until_vat_inputs_exist(tmp_path: Path) -> None:
    with pytest.raises(AggregationUnsupportedModeloError):
        aggregate_catalogue(_classified_catalogue(tmp_path), modelo="303", period="2025Q1")


def test_modelo_130_rejects_monthly_period(tmp_path: Path) -> None:
    with pytest.raises(AggregationError):
        aggregate_catalogue(_classified_catalogue(tmp_path), modelo="130", period="2025-01")


def test_cli_aggregate_json_round_trips(encrypted_store: Path, tmp_path: Path) -> None:
    TransactionCatalogueRepository(store_dir=encrypted_store).save(_classified_catalogue(tmp_path))

    result = _RUNNER.invoke(
        root_app,
        ["financial", "aggregate", "--modelo", "130", "--period", "2025-Q1", "--json"],
        env={
            "AEAT_FINANCIAL_TXS_DIR": str(encrypted_store),
            "AEAT_OUTPUT_LANGUAGE": "en",
        },
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["command"] == "financial aggregate"
    assert payload["result"]["casilla_values"] == {"01": "1000.00", "02": "230.0000"}
    SCHEMA_REGISTRY["financial aggregate"].model_validate_json(json.dumps(payload["result"]))


def test_workflow_inputs_provider_uses_financial_catalogue(
    encrypted_store: Path,
    tmp_path: Path,
) -> None:
    repository = TransactionCatalogueRepository(store_dir=encrypted_store)
    repository.save(_classified_catalogue(tmp_path))
    provider = FinancialThenJsonInputsProvider(
        financial_provider=FinancialFilingInputsProvider(repository=repository),
        fallback_provider=JsonFileInputsProvider(tmp_path / "missing-inputs.json"),
    )

    inputs = provider.load_inputs(modelo="130", period="2025-Q1", profile=_profile())

    assert inputs == {"01": Decimal("1000.00"), "02": Decimal("230.0000")}

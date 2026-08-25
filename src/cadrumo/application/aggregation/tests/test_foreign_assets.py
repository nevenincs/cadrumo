"""Tests for the Modelo 720 foreign-assets aggregator."""

from __future__ import annotations

import hashlib
from datetime import date
from decimal import Decimal

import pytest

from ....core import BindingSourceKind, ForeignAssetObligationGroup, Period
from ....core.aggregation import BindingAggregation, BindingAggregationOp
from ....core.resources import resources
from ....domain.calculations.registry import (
    DataBindingDefinition,
    ModeloRevision,
    PeriodSelector,
    resolve_foreign_asset_binding_row_values,
)
from ..._foreign_asset_thresholds import foreign_asset_declaration_thresholds
from .._foreign_assets import (
    ForeignAssetClass,
    ForeignAssetClassRollup,
    ForeignAssetIngestObservation,
    ForeignAssetsAggregation,
    ForeignAssetsAggregationSourceResolver,
    _registry_observation_from_foreign_asset,
    _registry_observations_from_foreign_assets_aggregation,
    aggregate_foreign_assets_720,
    declarable_asset_classes_720,
    declarable_class,
)
from .._source_mesh import CalculationSourceContext

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_P_2025_ANNUAL = Period.from_year_and_code(2025, "0A")
_M720_LEGAL_REFS = (
    "orden-hap-72-2013:art-1",
    "rd-1065-2007:art-42-bis",
    "rd-1065-2007:art-42-ter",
    "ley-58-2003:art-93",
)
_M720_SOURCE_REFS = ("aeat-dr-720", "aeat-modelo-720-procedure")
_M720_ROW_BINDINGS = (
    ("modelo-720-asset-row-class", "asset_class_code"),
    ("modelo-720-asset-row-country", "country_code"),
    ("modelo-720-asset-row-currency", "currency_code"),
    ("modelo-720-asset-row-identifier", "asset_identifier"),
    ("modelo-720-asset-row-valuation", "valuation_amount"),
    ("modelo-720-asset-row-acquisition-date", "acquisition_date"),
)


def _m720_row_binding(binding_id: str, row_field: str) -> DataBindingDefinition:
    return DataBindingDefinition(
        id=binding_id,
        source=BindingSourceKind.FOREIGN_ASSET,
        selector={
            "fact": "row_field",
            "row_field": row_field,
            "grouping": "per_foreign_asset",
            "record": "bien",
        },
        aggregation=BindingAggregation(op=BindingAggregationOp.ROWS),
        legal_refs=_M720_LEGAL_REFS,
        source_refs=_M720_SOURCE_REFS,
    )


def _m720_revision() -> ModeloRevision:
    return ModeloRevision(
        id="2013-y-siguientes",
        localization_key="test.schema.revision.2013-y-siguientes.label",
        valid_from=date(2013, 1, 1),
        period_selector=PeriodSelector(year_from=2013, periods=("0A",)),
        legal_refs=_M720_LEGAL_REFS,
        source_refs=_M720_SOURCE_REFS,
        parameters=resources()
        .modelos.authority.snapshot(
            "720",
            filing_year=2025,
            period="0A",
        )
        .revision.parameters,
        bindings=tuple(_m720_row_binding(binding_id, row_field) for binding_id, row_field in _M720_ROW_BINDINGS),
    )


def _revision_without_foreign_asset_source() -> ModeloRevision:
    return ModeloRevision(
        id="foreign-asset-empty-test",
        localization_key="test.schema.revision.foreign-asset-empty-test.label",
        valid_from=date(2025, 1, 1),
        period_selector=PeriodSelector(years=(2025,), periods=("1T",)),
        legal_refs=("ley-37-1992:art-1",),
        source_refs=("test-foreign-asset-no-source",),
    )


def _is_ledger(source_kind: BindingSourceKind | str) -> bool:
    """Return whether ``source_kind`` names the ledger-transaction source."""
    return source_kind in (BindingSourceKind.LEDGER_TRANSACTION, BindingSourceKind.LEDGER_TRANSACTION.value)


def ledger_identity(label: str) -> str:
    """Return a stable canonical transaction identity for a readable test label.

    A ledger-sourced observation must carry a real hex-64 transaction identity
    because the resolver copies it into ``source_transaction_ids``, which feeds
    the strict identity field on the persisted calculation revision. Deriving it
    from a label keeps each fixture distinguishable and deterministic without
    hand-writing digests at every call site.
    """
    return hashlib.sha256(label.encode("utf-8")).hexdigest()


def _obs(
    *,
    asset_class: ForeignAssetClass,
    valuation: str,
    asset_external_id: str = "ASSET-001",
    country: str = "AD",
    source_kind: BindingSourceKind | str = BindingSourceKind.LEDGER_TRANSACTION,
    source_id: str = "tx-001",
    held: bool = True,
    acquisition: str = "2023-01-15",
) -> ForeignAssetIngestObservation:
    # source_kind is deliberately BindingSourceKind | str: TestObservationContract
    # exercises both a raw-string coercion (kind.value) and a genuinely-invalid raw
    # string ("invoice") that the field's before-validator must reject. model_validate
    # (not the constructor) keeps that runtime-only distinction static-type-clean.
    return ForeignAssetIngestObservation.model_validate(
        {
            "source_kind": source_kind,
            "source_object_id": ledger_identity(source_id) if _is_ledger(source_kind) else source_id,
            "asset_class": asset_class,
            "asset_external_id": asset_external_id,
            "country": country,
            "valuation_eur": Decimal(valuation),
            "acquisition_date": acquisition,
            "held_at_year_end": held,
        },
    )


class TestObservationContract:
    def test_observation_accepts_canonical_source_kinds(self) -> None:
        expected = {
            BindingSourceKind.LEDGER_TRANSACTION,
            BindingSourceKind.PURCHASE_INVOICE_EVIDENCE,
            BindingSourceKind.PAYABLE_INVOICE,
            BindingSourceKind.COLLECTIBLE_INVOICE,
        }
        observed: set[BindingSourceKind] = set()
        for kind in expected:
            obs = _obs(asset_class=ForeignAssetClass.ACCOUNT, valuation="0", source_kind=kind)
            observed.add(obs.source_kind)
            from_string = _obs(asset_class=ForeignAssetClass.ACCOUNT, valuation="0", source_kind=kind.value)
            assert from_string.source_kind is kind
        assert observed == expected

    def test_bare_invoice_source_kind_rejected(self) -> None:
        from pydantic import ValidationError

        with pytest.raises(ValidationError, match="not a BindingSourceKind"):
            _obs(asset_class=ForeignAssetClass.ACCOUNT, valuation="1000", source_kind="invoice")

    def test_registry_foreign_asset_binding_source_rejected_as_ingest_provenance(self) -> None:
        from pydantic import ValidationError

        with pytest.raises(ValidationError, match="unsupported source_kind"):
            _obs(
                asset_class=ForeignAssetClass.ACCOUNT,
                valuation="1000",
                source_kind=BindingSourceKind.FOREIGN_ASSET,
            )

    def test_lowercase_country_rejected(self) -> None:
        from pydantic import ValidationError

        with pytest.raises(ValidationError, match="uppercase ISO-3166"):
            _obs(asset_class=ForeignAssetClass.ACCOUNT, valuation="1000", country="ad")


class TestAggregateBasic:
    def test_empty_observations_produce_zero_totals(self) -> None:
        result = aggregate_foreign_assets_720((), period=_P_2025_ANNUAL)
        assert result.modelo == "720"
        assert result.rollups == ()
        assert result.total_assets == 0
        assert result.total_valuation_eur == Decimal("0")

    def test_single_observation_creates_one_rollup(self) -> None:
        obs = _obs(asset_class=ForeignAssetClass.ACCOUNT, valuation="12345.67", country="AD")
        result = aggregate_foreign_assets_720((obs,), period=_P_2025_ANNUAL)
        assert len(result.rollups) == 1
        row = result.rollups[0]
        assert row.source_kind is BindingSourceKind.LEDGER_TRANSACTION
        assert row.asset_class is ForeignAssetClass.ACCOUNT
        assert row.assets_count == 1
        assert row.held_at_year_end_count == 1
        assert row.total_valuation_eur == Decimal("12345.67")
        assert row.countries == ("AD",)

    def test_multiple_classes_yield_separate_rollups(self) -> None:
        observations = (
            _obs(asset_class=ForeignAssetClass.ACCOUNT, valuation="10000", asset_external_id="A1"),
            _obs(asset_class=ForeignAssetClass.SECURITY, valuation="20000", asset_external_id="S1"),
            _obs(asset_class=ForeignAssetClass.REAL_ESTATE, valuation="30000", asset_external_id="R1"),
        )
        result = aggregate_foreign_assets_720(observations, period=_P_2025_ANNUAL)
        assert len(result.rollups) == 3
        classes = {row.asset_class for row in result.rollups}
        assert classes == {
            ForeignAssetClass.ACCOUNT,
            ForeignAssetClass.SECURITY,
            ForeignAssetClass.REAL_ESTATE,
        }
        assert result.total_assets == 3
        assert result.total_valuation_eur == Decimal("60000")

    def test_multiple_assets_same_class_sum(self) -> None:
        observations = (
            _obs(asset_class=ForeignAssetClass.ACCOUNT, valuation="20000", asset_external_id="A1", country="AD"),
            _obs(asset_class=ForeignAssetClass.ACCOUNT, valuation="30000", asset_external_id="A2", country="CH"),
        )
        result = aggregate_foreign_assets_720(observations, period=_P_2025_ANNUAL)
        assert len(result.rollups) == 1
        row = result.rollups[0]
        assert row.assets_count == 2
        assert row.total_valuation_eur == Decimal("50000")
        assert row.countries == ("AD", "CH")

    def test_rollups_sort_by_asset_class_value(self) -> None:
        observations = (
            _obs(asset_class=ForeignAssetClass.VIRTUAL_CURRENCY, valuation="1000", asset_external_id="V1"),
            _obs(asset_class=ForeignAssetClass.ACCOUNT, valuation="2000", asset_external_id="A1"),
            _obs(asset_class=ForeignAssetClass.SECURITY, valuation="3000", asset_external_id="S1"),
        )
        result = aggregate_foreign_assets_720(observations, period=_P_2025_ANNUAL)
        values = [row.asset_class.value for row in result.rollups]
        assert values == sorted(values)

    def test_held_count_tracks_year_end_flag(self) -> None:
        observations = (
            _obs(asset_class=ForeignAssetClass.ACCOUNT, valuation="10000", asset_external_id="A1", held=True),
            _obs(asset_class=ForeignAssetClass.ACCOUNT, valuation="10000", asset_external_id="A2", held=False),
            _obs(asset_class=ForeignAssetClass.ACCOUNT, valuation="10000", asset_external_id="A3", held=True),
        )
        result = aggregate_foreign_assets_720(observations, period=_P_2025_ANNUAL)
        row = result.rollups[0]
        assert row.assets_count == 3
        assert row.held_at_year_end_count == 2


class TestThreshold720:
    def test_threshold_is_resolved_from_the_2025_registry_revision(self) -> None:
        thresholds = foreign_asset_declaration_thresholds(modelo="720", filing_year=2025)
        assert thresholds[ForeignAssetObligationGroup.CUENTAS].initial_declaration_floor_eur == Decimal("50000.00")

    def test_declarable_strict_above_50000(self) -> None:
        observations = (_obs(asset_class=ForeignAssetClass.ACCOUNT, valuation="50000.01", asset_external_id="A1"),)
        result = aggregate_foreign_assets_720(observations, period=_P_2025_ANNUAL)
        assert declarable_class(result, asset_class=ForeignAssetClass.ACCOUNT) is True

    def test_not_declarable_at_exactly_50000(self) -> None:
        observations = (_obs(asset_class=ForeignAssetClass.ACCOUNT, valuation="50000.00", asset_external_id="A1"),)
        result = aggregate_foreign_assets_720(observations, period=_P_2025_ANNUAL)
        assert declarable_class(result, asset_class=ForeignAssetClass.ACCOUNT) is False

    def test_not_declarable_below_threshold(self) -> None:
        observations = (_obs(asset_class=ForeignAssetClass.ACCOUNT, valuation="49999.99", asset_external_id="A1"),)
        result = aggregate_foreign_assets_720(observations, period=_P_2025_ANNUAL)
        assert declarable_class(result, asset_class=ForeignAssetClass.ACCOUNT) is False

    def test_security_and_insurance_share_valores_obligation_block_threshold(self) -> None:
        observations = (
            _obs(
                asset_class=ForeignAssetClass.SECURITY,
                valuation="30000.00",
                asset_external_id="LI-SECURITY-001",
                source_id="security-001",
            ),
            _obs(
                asset_class=ForeignAssetClass.INSURANCE,
                valuation="25000.00",
                asset_external_id="CH-INSURANCE-001",
                source_id="insurance-001",
            ),
            _obs(
                asset_class=ForeignAssetClass.ACCOUNT,
                valuation="1000.00",
                asset_external_id="AD-ACCOUNT-001",
                source_id="account-001",
            ),
        )

        result = aggregate_foreign_assets_720(observations, period=_P_2025_ANNUAL)

        assert declarable_asset_classes_720(result) == frozenset(
            {
                ForeignAssetClass.SECURITY,
                ForeignAssetClass.INSURANCE,
            },
        )
        assert declarable_class(result, asset_class=ForeignAssetClass.SECURITY) is True
        assert declarable_class(result, asset_class=ForeignAssetClass.INSURANCE) is True
        assert declarable_class(result, asset_class=ForeignAssetClass.ACCOUNT) is False

    def test_shared_obligation_block_threshold_stays_strict_at_exactly_50000(self) -> None:
        observations = (
            _obs(
                asset_class=ForeignAssetClass.SECURITY,
                valuation="25000.00",
                asset_external_id="LI-SECURITY-001",
                source_id="security-001",
            ),
            _obs(
                asset_class=ForeignAssetClass.INSURANCE,
                valuation="25000.00",
                asset_external_id="CH-INSURANCE-001",
                source_id="insurance-001",
            ),
        )

        result = aggregate_foreign_assets_720(observations, period=_P_2025_ANNUAL)

        assert declarable_asset_classes_720(result) == frozenset()
        assert declarable_class(result, asset_class=ForeignAssetClass.SECURITY) is False
        assert declarable_class(result, asset_class=ForeignAssetClass.INSURANCE) is False


class TestForeignAssetSourceResolver:
    def test_resolver_validates_declarable_m720_rows_against_registry_row_bindings(self) -> None:
        period = Period.from_year_and_code(2025, "0A")
        observations = (
            _obs(
                asset_class=ForeignAssetClass.ACCOUNT,
                valuation="40000.00",
                asset_external_id="AD-ACCOUNT-001",
                country="AD",
                source_kind=BindingSourceKind.LEDGER_TRANSACTION,
                source_id="tx-account-ad",
                acquisition="2020-01-15",
            ),
            _obs(
                asset_class=ForeignAssetClass.ACCOUNT,
                valuation="15000.00",
                asset_external_id="CH-ACCOUNT-002",
                country="CH",
                source_kind=BindingSourceKind.PAYABLE_INVOICE,
                source_id="payable-account-ch",
                acquisition="2021-02-20",
            ),
            _obs(
                asset_class=ForeignAssetClass.SECURITY,
                valuation="1000.00",
                asset_external_id="LI-SECURITY-001",
                country="LI",
                source_kind=BindingSourceKind.COLLECTIBLE_INVOICE,
                source_id="small-security",
            ),
        )
        revision = _m720_revision()

        resolution = ForeignAssetsAggregationSourceResolver(observations=observations).resolve(
            CalculationSourceContext(
                bucket_id="operator",
                modelo="720",
                filing_year=2025,
                period=period,
                revision=revision,
            ),
        )

        assert resolution.owned_sources == (BindingSourceKind.FOREIGN_ASSET,)
        assert resolution.binding_values == {}
        assert resolution.source_transaction_ids == (ledger_identity("tx-account-ad"),)
        # M720 is deliberately grounding-blocked: the resolver emits NO
        # provenance because no upstream carrier id can truthfully stand in for
        # an authoritative persisted identity of the resolved asset. The
        # contributing sources stay visible through source_transaction_ids.
        assert resolution.provenance == ()

        aggregation = aggregate_foreign_assets_720(observations, period=period)
        row_observations = _registry_observations_from_foreign_assets_aggregation(aggregation, observations)
        row_values = resolve_foreign_asset_binding_row_values(revision, row_observations)

        assert len(row_observations) == 2
        assert row_values[("modelo-720-asset-row-class", 1)] == "C"
        assert row_values[("modelo-720-asset-row-country", 1)] == "AD"
        assert row_values[("modelo-720-asset-row-identifier", 1)] == "AD-ACCOUNT-001"
        assert row_values[("modelo-720-asset-row-acquisition-date", 1)] == "2020-01-15"
        assert row_values[("modelo-720-asset-row-valuation", 1)] == Decimal("40000.00")
        assert row_values[("modelo-720-asset-row-class", 2)] == "C"
        assert row_values[("modelo-720-asset-row-country", 2)] == "CH"
        assert row_values[("modelo-720-asset-row-identifier", 2)] == "CH-ACCOUNT-002"
        assert row_values[("modelo-720-asset-row-acquisition-date", 2)] == "2021-02-20"
        assert row_values[("modelo-720-asset-row-valuation", 2)] == Decimal("15000.00")
        assert dict(resolution.row_binding_values) == row_values

    def test_row_projection_uses_official_iic_and_real_estate_codes(self) -> None:
        period = Period.from_year_and_code(2025, "0A")
        observations = (
            _obs(
                asset_class=ForeignAssetClass.COLLECTIVE_INVESTMENT,
                valuation="60000.00",
                asset_external_id="LI-IIC-001",
                country="LI",
                source_id="tx-iic-li",
            ),
            _obs(
                asset_class=ForeignAssetClass.REAL_ESTATE,
                valuation="60000.00",
                asset_external_id="AD-REAL-001",
                country="AD",
                source_id="tx-real-ad",
            ),
        )
        aggregation = aggregate_foreign_assets_720(observations, period=period)
        row_observations = _registry_observations_from_foreign_assets_aggregation(aggregation, observations)

        row_values = resolve_foreign_asset_binding_row_values(_m720_revision(), row_observations)

        assert {observation.asset_class_code for observation in row_observations} == {"I", "B"}
        assert row_values[("modelo-720-asset-row-class", 1)] == "B"
        assert row_values[("modelo-720-asset-row-country", 1)] == "AD"
        assert row_values[("modelo-720-asset-row-identifier", 1)] == "AD-REAL-001"
        assert row_values[("modelo-720-asset-row-class", 2)] == "I"
        assert row_values[("modelo-720-asset-row-country", 2)] == "LI"
        assert row_values[("modelo-720-asset-row-identifier", 2)] == "LI-IIC-001"

    def test_virtual_currency_cannot_be_projected_as_modelo_720_row(self) -> None:
        observations = (
            _obs(
                asset_class=ForeignAssetClass.VIRTUAL_CURRENCY,
                valuation="60000.00",
                asset_external_id="CRYPTO-001",
                source_id="tx-crypto",
            ),
        )
        aggregation = aggregate_foreign_assets_720(observations, period=_P_2025_ANNUAL)

        with pytest.raises(ValueError, match="not a Modelo 720 foreign-asset class"):
            _registry_observations_from_foreign_assets_aggregation(aggregation, observations)

    def test_resolver_silent_when_revision_declares_no_foreign_asset_source(self) -> None:
        resolution = ForeignAssetsAggregationSourceResolver(
            observations=(
                _obs(
                    asset_class=ForeignAssetClass.ACCOUNT,
                    valuation="60000.00",
                    source_id="tx-account",
                ),
            ),
        ).resolve(
            CalculationSourceContext(
                bucket_id="operator",
                modelo="303",
                filing_year=2025,
                period=Period.from_year_and_code(2025, "1T"),
                revision=_revision_without_foreign_asset_source(),
            ),
        )

        assert resolution.binding_values == {}
        assert dict(resolution.row_binding_values) == {}
        assert resolution.diagnostics == ()
        assert resolution.provenance == ()


class TestInvariants:
    def test_aggregation_input_order_invariance(self) -> None:
        observations = (
            _obs(asset_class=ForeignAssetClass.SECURITY, valuation="5000", asset_external_id="S1"),
            _obs(asset_class=ForeignAssetClass.ACCOUNT, valuation="3000", asset_external_id="A1"),
        )
        forward = aggregate_foreign_assets_720(observations, period=_P_2025_ANNUAL)
        reverse = aggregate_foreign_assets_720(tuple(reversed(observations)), period=_P_2025_ANNUAL)
        assert forward.model_dump_json() == reverse.model_dump_json()

    def test_rollup_held_count_cannot_exceed_total(self) -> None:
        from pydantic import ValidationError

        with pytest.raises(ValidationError, match="held_at_year_end_count"):
            ForeignAssetClassRollup(
                source_kind=BindingSourceKind.LEDGER_TRANSACTION,
                asset_class=ForeignAssetClass.ACCOUNT,
                assets_count=2,
                held_at_year_end_count=99,
                total_valuation_eur=Decimal("10000"),
                countries=("AD",),
            )

    def test_aggregation_rejects_duplicate_class_rows(self) -> None:
        from pydantic import ValidationError

        row = ForeignAssetClassRollup(
            source_kind=BindingSourceKind.LEDGER_TRANSACTION,
            asset_class=ForeignAssetClass.ACCOUNT,
            assets_count=1,
            held_at_year_end_count=1,
            total_valuation_eur=Decimal("1000"),
            countries=("AD",),
        )
        with pytest.raises(ValidationError, match="may appear at most once"):
            ForeignAssetsAggregation(
                modelo="720",
                period=_P_2025_ANNUAL,
                rollups=(row, row),
                total_assets=2,
                total_valuation_eur=Decimal("2000"),
            )

    def test_combined_period_string_is_not_coerced(self) -> None:
        from pydantic import ValidationError

        with pytest.raises(ValidationError, match="Period"):
            ForeignAssetsAggregation.model_validate(
                {
                    "modelo": "720",
                    "period": "2025",
                    "rollups": (),
                    "total_assets": 0,
                    "total_valuation_eur": Decimal("0"),
                },
            )

    def test_period_dict_is_not_coerced(self) -> None:
        from pydantic import ValidationError

        with pytest.raises(ValidationError, match="Period"):
            ForeignAssetsAggregation.model_validate(
                {
                    "modelo": "720",
                    "period": {"filing_year": 2025, "code": "0A"},
                    "rollups": (),
                    "total_assets": 0,
                    "total_valuation_eur": Decimal("0"),
                },
            )


from pydantic import TypeAdapter, ValidationError  # noqa: E402

from ....core.identity import TransactionId  # noqa: E402


@pytest.mark.parametrize("impossible", ["2026-99-99", "2026-02-30", "2025-13-01", "0000-00-00"])
def test_impossible_acquisition_dates_are_refused_at_ingestion(impossible: str) -> None:
    """An impossible calendar date is refused before it can reach aggregation.

    ``acquisition_date`` was bounded only by string length, so a ten-character
    non-date passed construction and ``aggregate_foreign_assets_720`` returned
    totals for it exactly as it did for a real date. The refusal only arrived
    later, at the registry adapter that finally parses the value — after the
    declarability decision had already been made from it.
    """
    with pytest.raises(ValidationError):
        _obs(asset_class=ForeignAssetClass.ACCOUNT, valuation="1000", acquisition=impossible)


@pytest.mark.parametrize("malformed", ["20260301", "2026-3-1", "01-03-2026", "2026-03-01T00:00:00"])
def test_non_extended_iso_acquisition_dates_are_refused(malformed: str) -> None:
    """Only the extended ``YYYY-MM-DD`` wire form is admitted."""
    with pytest.raises(ValidationError):
        _obs(asset_class=ForeignAssetClass.ACCOUNT, valuation="1000", acquisition=malformed)


def test_valid_acquisition_date_aggregates_and_reaches_the_registry_row() -> None:
    """The positive control: a real date is admitted and survives to the registry row shape.

    Without this, the refusal assertions above would also hold for a validator
    that refused every value.
    """
    observation = _obs(asset_class=ForeignAssetClass.ACCOUNT, valuation="1000", acquisition="2026-03-01")
    assert observation.acquisition_date == "2026-03-01"

    aggregation = aggregate_foreign_assets_720(
        (observation,),
        period=Period.from_year_and_code(2026, "0A"),
    )
    assert aggregation.total_assets == 1

    row = _registry_observation_from_foreign_asset(observation)
    assert row.acquisition_date == date(2026, 3, 1)


@pytest.mark.parametrize(
    "not_a_transaction_identity",
    ["ledger_transaction-urban-a", "INV-2025-0007", "A" * 64, "a" * 63, "a" * 65],
)
def test_ledger_sourced_observation_requires_the_canonical_transaction_identity(
    not_a_transaction_identity: str,
) -> None:
    """A ledger observation cannot be ingested with an id the revision contract refuses.

    The resolver copies ``source_object_id`` verbatim into
    ``CalculationSourceResolution.source_transaction_ids``, which feeds the
    strict hex-64 transaction-identity field on ``CalculationRevision``. Any
    non-empty string used to be admitted here, so a validly-ingested ledger
    observation could reach calculation persistence carrying an id the canonical
    revision contract can never satisfy — and the refusal surfaced at the
    persistence boundary, far from the row that caused it.
    """
    # Constructed directly: the _obs helper canonicalises ledger labels for
    # convenience, and this test is precisely about the raw declared value.
    with pytest.raises(ValidationError):
        ForeignAssetIngestObservation.model_validate(
            {
                "source_kind": BindingSourceKind.LEDGER_TRANSACTION,
                "source_object_id": not_a_transaction_identity,
                "asset_class": ForeignAssetClass.ACCOUNT,
                "asset_external_id": "AD-ACCOUNT-001",
                "country": "AD",
                "valuation_eur": Decimal("60000.00"),
                "acquisition_date": "2023-01-15",
                "held_at_year_end": True,
            },
        )


def test_non_ledger_sources_keep_their_external_identifiers() -> None:
    """An invoice-sourced observation keeps its external id, in provenance only.

    The identity constraint is scoped to the ledger source kind: an external or
    invoice-like identifier is legitimate provenance and must not be forced into
    the transaction-identity shape.
    """
    observation = _obs(
        asset_class=ForeignAssetClass.ACCOUNT,
        valuation="60000.00",
        source_kind=BindingSourceKind.PAYABLE_INVOICE,
        source_id="INV-2025-0007",
    )

    assert observation.source_object_id == "INV-2025-0007"


def test_resolved_ledger_ids_satisfy_the_revision_identity_contract() -> None:
    """Every id the resolver reports as a transaction id validates as one.

    The end-to-end property the finding names: what reaches
    ``source_transaction_ids`` must be admissible by the persisted revision's
    transaction-identity field, so ingestion and persistence cannot disagree.
    """
    period = _P_2025_ANNUAL
    observations = (
        _obs(
            asset_class=ForeignAssetClass.ACCOUNT,
            valuation="60000.00",
            asset_external_id="AD-ACCOUNT-001",
            country="AD",
            source_kind=BindingSourceKind.LEDGER_TRANSACTION,
            source_id="tx-account-ad",
        ),
        _obs(
            asset_class=ForeignAssetClass.ACCOUNT,
            valuation="15000.00",
            asset_external_id="CH-ACCOUNT-002",
            country="CH",
            source_kind=BindingSourceKind.PAYABLE_INVOICE,
            source_id="INV-2025-0007",
        ),
    )

    resolution = ForeignAssetsAggregationSourceResolver(observations=observations).resolve(
        CalculationSourceContext(
            bucket_id="operator",
            modelo="720",
            filing_year=2025,
            period=period,
            revision=_m720_revision(),
        ),
    )

    assert resolution.source_transaction_ids
    adapter = TypeAdapter(TransactionId)
    for transaction_id in resolution.source_transaction_ids:
        assert adapter.validate_python(transaction_id) == transaction_id
    # The invoice-sourced external id stays out of the identity tuple.
    assert "INV-2025-0007" not in resolution.source_transaction_ids

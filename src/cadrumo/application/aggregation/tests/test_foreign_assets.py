"""Tests for the Modelo 720 foreign-assets aggregator."""

from __future__ import annotations

import hashlib
from datetime import date
from decimal import Decimal

import pytest
from pydantic import TypeAdapter, ValidationError

from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority as _indexed_authority_for_test
from cadrumo.domain.calculations.registry.tests.published_authority import (
    PublishedGovernedFactSource,
    published_snapshot,
)

from ....core.aggregation import BindingAggregation, BindingAggregationOp, BindingSourceKind, ForeignAssetClass
from ....core.foreign_asset_obligation import (
    MODELO_720_FOREIGN_ASSET_CLASS_CODES,
    ForeignAssetObligationGroup,
    M720AssetClassCode,
)
from ....core.identity.transaction_ids import TransactionId
from ....core.period import Period
from ....domain.calculations.registry.detail_record_bindings import Modelo720RowObservation
from ....domain.calculations.registry.errors import RegistryValidationError
from ....domain.calculations.registry.schema import BindingDefinition, ModeloRevision
from ....domain.calculations.registry.schema_references import PeriodSelector
from ....domain.currency.models import EurRateLookup
from ....domain.currency.service import ExchangeRateProvider
from ....domain.currency.tests.fx_lookup import eur_rate_lookup
from ....domain.foreign_assets.record_join import ForeignAssetRecordJoinRefusedError, M720RecordJoinRefusalReason
from ....domain.foreign_assets.register import (
    ForeignAssetDeclarationEntry,
    ForeignAssetRegister,
    ForeignAssetRegisterEntry,
    M720AssetIdentifier,
    M720DeclarantCondition,
    M720IdentifierScheme,
)
from ....domain.foreign_assets.valuation import (
    ForeignAssetValuationRefusedError,
    M720ValuationEvent,
    M720ValuationRefusalReason,
)
from ...foreign_asset_thresholds import foreign_asset_declaration_thresholds
from ..foreign_assets import (
    ForeignAssetClassRollup,
    ForeignAssetIngestObservation,
    ForeignAssetsAggregation,
    ForeignAssetsAggregationSourceResolver,
    _registry_observation_from_foreign_asset,
    aggregate_foreign_assets_720,
    declarable_asset_classes_720,
)
from ..source_mesh import CalculationSourceContext

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("operation")]

_SUPPORT = PublishedGovernedFactSource().supported_filing_years()

_P_2025_ANNUAL = Period.from_year_and_code(2025, "0A")
_M720_LEGAL_REFS = (
    "orden-hap-72-2013:art-1",
    "rd-1065-2007:art-42-bis",
    "rd-1065-2007:art-42-ter",
    "ley-58-2003:art-93",
)
_M720_SOURCE_REFS = ("aeat-dr-720", "aeat-modelo-720-procedure")
_M720_ROW_BINDINGS = (
    ("modelo-720-asset-row-asset-ref", "asset_ref"),
    ("modelo-720-asset-row-valuation-event", "valuation_event"),
    ("modelo-720-asset-row-valuation-event-date", "valuation_event_date"),
    ("modelo-720-asset-row-declarant-condition", "declarant_condition"),
    ("modelo-720-asset-row-class", "asset_class_code"),
    ("modelo-720-asset-row-country", "country_code"),
    ("modelo-720-asset-row-currency", "currency_code"),
    ("modelo-720-asset-row-identifier", "asset_identifier"),
    ("modelo-720-asset-row-valuation", "valuation_amount"),
    ("modelo-720-asset-row-acquisition-date", "acquisition_date"),
)


def _m720_row_binding(binding_id: str, row_field: str) -> BindingDefinition:
    return BindingDefinition(
        id=binding_id,
        provider={
            "kind": "foreign_asset",
            **{
                "fact": "row_field",
                "row_field": row_field,
                "grouping": "per_foreign_asset",
                "record": "bien",
            },
        },
        value={"data_type": "text", "channel": "row_set", "row_grouping": "foreign_asset"},
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
        parameters=published_snapshot(
            "720",
            filing_year=2025,
            period="0A",
        ).revision.parameters,
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


def asset_ref(label: str) -> str:
    """Return a stable register identity for a readable asset label."""
    return "m720a_" + hashlib.sha256(label.encode("utf-8")).hexdigest()[:32]


# 2025-12-31 and 2025-06-13 are ECB publication days; the stub answers only them.
_USD_RATE = Decimal("0.85")
_RATE_SOURCE = "test-reference"


class _UsdRates:
    rate_source_id = _RATE_SOURCE

    def lookup_eur_rate(self, currency: str, rate_date: date) -> EurRateLookup:
        published = currency == "USD" and rate_date in {date(2025, 12, 31), date(2025, 6, 13)}
        return eur_rate_lookup(_USD_RATE if published else None, rate_date=rate_date, source=_RATE_SOURCE)


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
    currency: str = "EUR",
) -> ForeignAssetIngestObservation:
    # source_kind is deliberately BindingSourceKind | str: TestObservationContract
    # exercises both a raw-string coercion (kind.value) and a genuinely-invalid raw
    # string ("invoice") that the field's before-validator must reject. model_validate
    # (not the constructor) keeps that runtime-only distinction static-type-clean.
    return ForeignAssetIngestObservation.model_validate(
        {
            "source_kind": source_kind,
            "source_object_id": ledger_identity(source_id) if _is_ledger(source_kind) else source_id,
            "asset_ref": asset_ref(asset_external_id),
            "asset_class": asset_class,
            "asset_external_id": asset_external_id,
            "country": country,
            "valuation_amount": Decimal(valuation),
            "currency_code": currency,
            "valuation_event": M720ValuationEvent.YEAR_END if held else M720ValuationEvent.EXTINCTION,
            "valuation_event_date": None if held else "2025-06-13",
            "acquisition_date": acquisition,
        },
    )


def _context(revision: ModeloRevision | None = None) -> CalculationSourceContext:
    return CalculationSourceContext(
        bucket_id="operator",
        modelo="720",
        filing_year=2025,
        period=_P_2025_ANNUAL,
        revision=revision or _m720_revision(),
    )


def _registered(
    lot: ForeignAssetIngestObservation | Modelo720RowObservation,
) -> ForeignAssetRegisterEntry:
    """Register the asset a lot names, with the official identifier the lot carries."""
    if isinstance(lot, ForeignAssetIngestObservation):
        code = MODELO_720_FOREIGN_ASSET_CLASS_CODES[lot.asset_class]
        country, identifier = lot.country, lot.asset_external_id
    else:
        code, country, identifier = lot.asset_class_code, lot.country_code, lot.asset_identifier
    if code is M720AssetClassCode.CUENTA:
        scheme = M720IdentifierScheme.ACCOUNT_CODE
    elif code in {M720AssetClassCode.VALOR, M720AssetClassCode.INSTITUCION_INVERSION_COLECTIVA}:
        scheme = M720IdentifierScheme.NO_ISIN_ISSUER_COUNTRY
    else:
        scheme, identifier = M720IdentifierScheme.NONE, ""
    return ForeignAssetRegisterEntry(
        asset_ref=lot.asset_ref,
        asset_class=code,
        subclave=None if code is M720AssetClassCode.INSTITUCION_INVERSION_COLECTIVA else 1,
        country_code=country,
        identifier=M720AssetIdentifier(scheme=scheme, value=identifier),
        description="synthetic asset",
    )


def _declared(asset_ref: str, condition: M720DeclarantCondition = M720DeclarantCondition.TITULAR, pct: str = "100.00"):
    return ForeignAssetDeclarationEntry(asset_ref=asset_ref, condition=condition, participation_pct=Decimal(pct))


def _register_for(*lots: ForeignAssetIngestObservation | Modelo720RowObservation) -> ForeignAssetRegister:
    # A lot of a class Modelo 720 does not declare is refused before any join.
    assets = {
        lot.asset_ref: _registered(lot)
        for lot in lots
        if not isinstance(lot, ForeignAssetIngestObservation) or lot.asset_class in MODELO_720_FOREIGN_ASSET_CLASS_CODES
    }
    return ForeignAssetRegister(
        assets=tuple(assets.values()),
        declarations=tuple(_declared(asset_ref) for asset_ref in assets),
    )


def _resolver(
    *,
    observations: tuple[ForeignAssetIngestObservation, ...] = (),
    row_observations: tuple[Modelo720RowObservation, ...] = (),
    rate_provider: ExchangeRateProvider | None = None,
    register: ForeignAssetRegister | None = None,
) -> ForeignAssetsAggregationSourceResolver:
    """The resolver over these lots, with every asset registered and declared unless told otherwise."""
    resolved_register = register if register is not None else _register_for(*observations, *row_observations)
    return ForeignAssetsAggregationSourceResolver(
        observations=observations,
        row_observations=row_observations,
        rate_provider=rate_provider,
        register_loader=lambda: resolved_register,
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
            _obs(asset_class=ForeignAssetClass.REAL_ESTATE, valuation="1000", asset_external_id="R1"),
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
    @pytest.mark.parametrize("filing_year", _SUPPORT.years)
    def test_threshold_is_resolved_from_the_registry_revision(self, filing_year: int) -> None:
        with _indexed_authority_for_test().operation() as _authority_operation_for_test:
            thresholds = foreign_asset_declaration_thresholds(
                modelo="720", filing_year=filing_year, operation=_authority_operation_for_test
            )
            assert thresholds[
                ForeignAssetObligationGroup.from_registry("cuentas")
            ].initial_declaration_floor_eur == Decimal("50000.00")

    def test_declarable_strict_above_50000(self) -> None:
        observations = (_obs(asset_class=ForeignAssetClass.ACCOUNT, valuation="50000.01", asset_external_id="A1"),)
        result = aggregate_foreign_assets_720(observations, period=_P_2025_ANNUAL)
        assert ForeignAssetClass.ACCOUNT in declarable_asset_classes_720(result)

    def test_not_declarable_at_exactly_50000(self) -> None:
        observations = (_obs(asset_class=ForeignAssetClass.ACCOUNT, valuation="50000.00", asset_external_id="A1"),)
        result = aggregate_foreign_assets_720(observations, period=_P_2025_ANNUAL)
        assert ForeignAssetClass.ACCOUNT not in declarable_asset_classes_720(result)

    def test_not_declarable_below_threshold(self) -> None:
        observations = (_obs(asset_class=ForeignAssetClass.ACCOUNT, valuation="49999.99", asset_external_id="A1"),)
        result = aggregate_foreign_assets_720(observations, period=_P_2025_ANNUAL)
        assert ForeignAssetClass.ACCOUNT not in declarable_asset_classes_720(result)

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
        assert ForeignAssetClass.SECURITY in declarable_asset_classes_720(result)
        assert ForeignAssetClass.INSURANCE in declarable_asset_classes_720(result)
        assert ForeignAssetClass.ACCOUNT not in declarable_asset_classes_720(result)

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
        assert ForeignAssetClass.SECURITY not in declarable_asset_classes_720(result)
        assert ForeignAssetClass.INSURANCE not in declarable_asset_classes_720(result)


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
                asset_external_id="ZLI",
                country="LI",
                source_kind=BindingSourceKind.COLLECTIBLE_INVOICE,
                source_id="small-security",
            ),
        )
        revision = _m720_revision()

        resolution = _resolver(observations=observations).resolve(
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
        # Ledger-side rows carry no primary provenance until the register join
        # grounds it; the contributing sources stay visible through
        # source_transaction_ids.
        assert resolution.provenance == ()

        row_values = dict(resolution.row_binding_values)

        assert {index for _, index in row_values} == {1, 2}
        assert row_values[("modelo-720-asset-row-asset-ref", 1)] == asset_ref("AD-ACCOUNT-001")
        assert row_values[("modelo-720-asset-row-valuation-event", 1)] == "year_end"
        assert row_values[("modelo-720-asset-row-valuation-event-date", 1)] == ""
        assert row_values[("modelo-720-asset-row-currency", 1)] == "EUR"
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

    def test_row_projection_uses_official_iic_and_real_estate_codes(self) -> None:
        period = Period.from_year_and_code(2025, "0A")
        observations = (
            _obs(
                asset_class=ForeignAssetClass.COLLECTIVE_INVESTMENT,
                valuation="60000.00",
                asset_external_id="ZLI",
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
        resolution = _resolver(observations=observations).resolve(
            CalculationSourceContext(
                bucket_id="operator",
                modelo="720",
                filing_year=2025,
                period=period,
                revision=_m720_revision(),
            ),
        )
        row_values = dict(resolution.row_binding_values)

        assert row_values[("modelo-720-asset-row-class", 1)] == "B"
        assert row_values[("modelo-720-asset-row-country", 1)] == "AD"
        assert row_values[("modelo-720-asset-row-identifier", 1)] == "AD-REAL-001"
        assert row_values[("modelo-720-asset-row-class", 2)] == "I"
        assert row_values[("modelo-720-asset-row-country", 2)] == "LI"
        assert row_values[("modelo-720-asset-row-identifier", 2)] == "ZLI"

    def test_virtual_currency_cannot_be_projected_as_modelo_720_row(self) -> None:
        observations = (
            _obs(
                asset_class=ForeignAssetClass.VIRTUAL_CURRENCY,
                valuation="60000.00",
                asset_external_id="CRYPTO-001",
                source_id="tx-crypto",
            ),
        )
        with pytest.raises(ValueError, match="not a Modelo 720 foreign-asset class"):
            aggregate_foreign_assets_720(observations, period=_P_2025_ANNUAL)
        with pytest.raises(ValueError, match="not a Modelo 720 foreign-asset class"):
            _resolver(observations=observations).resolve(_context())

    def test_resolver_silent_when_revision_declares_no_foreign_asset_source(self) -> None:
        resolution = _resolver(
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
                "asset_ref": asset_ref("AD-ACCOUNT-001"),
                "asset_class": ForeignAssetClass.ACCOUNT,
                "asset_external_id": "AD-ACCOUNT-001",
                "country": "AD",
                "valuation_amount": Decimal("60000.00"),
                "currency_code": "EUR",
                "valuation_event": M720ValuationEvent.YEAR_END,
                "acquisition_date": "2023-01-15",
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

    resolution = _resolver(observations=observations).resolve(
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


def _worksheet_row(
    *,
    label: str,
    valuation: str,
    asset_class: str = "C",
    country: str = "CH",
    currency: str = "EUR",
) -> Modelo720RowObservation:
    return Modelo720RowObservation.model_validate(
        {
            "source_id": f"detalle:per_foreign_asset:{label}",
            "asset_ref": asset_ref(label),
            "asset_class_code": M720AssetClassCode(asset_class),
            "country_code": country,
            "currency_code": currency,
            "asset_identifier": label,
            "acquisition_date": date(2022, 5, 1),
            "valuation_amount": Decimal(valuation),
            "valuation_event": M720ValuationEvent.YEAR_END,
        },
    )


class TestEuroValuation:
    def test_a_foreign_currency_account_is_declared_at_its_31_december_euro_value(self) -> None:
        observations = (
            _obs(
                asset_class=ForeignAssetClass.ACCOUNT,
                valuation="100000.00",
                asset_external_id="US-ACCOUNT-001",
                country="US",
                currency="USD",
            ),
        )

        resolution = _resolver(observations=observations, rate_provider=_UsdRates()).resolve(_context())

        row_values = dict(resolution.row_binding_values)
        assert row_values[("modelo-720-asset-row-valuation", 1)] == Decimal("85000.00")
        assert row_values[("modelo-720-asset-row-currency", 1)] == "USD"

    def test_the_block_threshold_reads_the_converted_value_not_the_face_value(self) -> None:
        # 55,000 USD is 46,750 EUR at the 31 December rate: below the 50,000 EUR floor.
        observations = (
            _obs(
                asset_class=ForeignAssetClass.ACCOUNT,
                valuation="55000.00",
                asset_external_id="US-ACCOUNT-002",
                country="US",
                currency="USD",
            ),
        )

        resolution = _resolver(observations=observations, rate_provider=_UsdRates()).resolve(_context())

        assert dict(resolution.row_binding_values) == {}

    def test_the_row_identity_fingerprints_the_rate_it_was_converted_at(self) -> None:
        def resolve_with(rate: Decimal) -> str:
            class _Rates:
                rate_source_id = _RATE_SOURCE

                def lookup_eur_rate(self, currency: str, rate_date: date) -> EurRateLookup:
                    return eur_rate_lookup(rate, rate_date=rate_date, source=_RATE_SOURCE)

            resolution = _resolver(
                observations=(
                    _obs(
                        asset_class=ForeignAssetClass.ACCOUNT,
                        valuation="100000.00",
                        asset_external_id="US-ACCOUNT-003",
                        currency="USD",
                    ),
                ),
                rate_provider=_Rates(),
            ).resolve(_context())
            return resolution.row_source_identities[("modelo-720-asset-row-valuation", 1)].fingerprint

        assert resolve_with(Decimal("0.85")) != resolve_with(Decimal("0.86"))

    def test_an_unconvertible_amount_refuses_the_calculation_naming_the_asset(self) -> None:
        observations = (
            _obs(
                asset_class=ForeignAssetClass.ACCOUNT,
                valuation="100000.00",
                asset_external_id="XX-ACCOUNT-001",
                currency="XYZ",
            ),
        )

        with pytest.raises(ForeignAssetValuationRefusedError) as refused:
            _resolver(observations=observations, rate_provider=_UsdRates()).resolve(_context())

        assert refused.value.asset_ref == asset_ref("XX-ACCOUNT-001")
        assert refused.value.reason is M720ValuationRefusalReason.MISSING_RATE

    def test_aggregation_rollups_sum_euro_values(self) -> None:
        observations = (
            _obs(asset_class=ForeignAssetClass.ACCOUNT, valuation="1000.00", asset_external_id="A1", currency="USD"),
            _obs(asset_class=ForeignAssetClass.ACCOUNT, valuation="1000.00", asset_external_id="A2"),
        )

        result = aggregate_foreign_assets_720(observations, period=_P_2025_ANNUAL, rate_provider=_UsdRates())

        assert result.total_valuation_eur == Decimal("1850.00")


class TestLedgerAndWorksheetSources:
    def test_ledger_and_worksheet_assets_are_declared_together(self) -> None:
        ledger = (
            _obs(
                asset_class=ForeignAssetClass.ACCOUNT,
                valuation="30000.00",
                asset_external_id="AD-ACCOUNT-001",
                source_id="tx-ad",
            ),
        )
        worksheet = (_worksheet_row(label="CH-ACCOUNT-009", valuation="30000.00"),)

        resolution = _resolver(observations=ledger, row_observations=worksheet).resolve(_context())

        row_values = dict(resolution.row_binding_values)
        # Each side alone is under the 50,000 EUR block floor; together they exceed it.
        assert {row_values[("modelo-720-asset-row-asset-ref", index)] for index in (1, 2)} == {
            asset_ref("AD-ACCOUNT-001"),
            asset_ref("CH-ACCOUNT-009"),
        }
        assert resolution.source_transaction_ids == (ledger_identity("tx-ad"),)
        assert [entry.source_ref for entry in resolution.provenance] == [
            "worksheet:detalle:per_foreign_asset:CH-ACCOUNT-009#1",
        ]

    def test_an_asset_from_both_the_ledger_and_the_worksheet_is_refused(self) -> None:
        ledger = (_obs(asset_class=ForeignAssetClass.ACCOUNT, valuation="60000.00", asset_external_id="SAME"),)
        worksheet = (_worksheet_row(label="SAME", valuation="60000.00"),)

        with pytest.raises(RegistryValidationError, match="both the ledger and the worksheet"):
            _resolver(observations=ledger, row_observations=worksheet).resolve(_context())

    def test_two_lots_of_one_asset_from_one_source_are_two_rows(self) -> None:
        worksheet = (
            _worksheet_row(label="ZLI", valuation="40000.00", asset_class="V", country="LI"),
            _worksheet_row(label="ZLI", valuation="40000.00", asset_class="V", country="LI").model_copy(
                update={"source_id": "detalle:per_foreign_asset:lot-2", "acquisition_date": date(2023, 7, 1)},
            ),
        )

        resolution = _resolver(row_observations=worksheet).resolve(_context())

        row_values = dict(resolution.row_binding_values)
        assert [row_values[("modelo-720-asset-row-acquisition-date", index)] for index in (1, 2)] == [
            "2022-05-01",
            "2023-07-01",
        ]


class TestRegisterJoin:
    def test_two_declared_conditions_make_two_records_with_the_full_valuation_on_each(self) -> None:
        lot = _obs(asset_class=ForeignAssetClass.ACCOUNT, valuation="80000.00", asset_external_id="AD-JOINT-001")
        register = _register_for(lot).model_copy(
            update={
                "declarations": (
                    _declared(lot.asset_ref, M720DeclarantCondition.TITULAR, "50.00"),
                    _declared(lot.asset_ref, M720DeclarantCondition.AUTORIZADO, "50.00"),
                ),
            },
        )

        resolution = _resolver(observations=(lot,), register=register).resolve(_context())

        row_values = dict(resolution.row_binding_values)
        assert [row_values[("modelo-720-asset-row-valuation", index)] for index in (1, 2)] == [
            Decimal("80000.00"),
            Decimal("80000.00"),
        ]
        identities = {
            identity.source_row_identity
            for (binding_id, _), identity in resolution.row_source_identities.items()
            if binding_id == "modelo-720-asset-row-valuation"
        }
        source = f"ledger_transaction:{ledger_identity('tx-001')}"
        assert identities == {f"{source}#1", f"{source}#3"}

    def test_an_asset_sorting_first_leaves_every_declaration_on_its_own_asset(self) -> None:
        """Detector teeth for the positional join: a new earlier-sorting asset shifts no declaration."""
        later = _obs(
            asset_class=ForeignAssetClass.ACCOUNT,
            valuation="60000.00",
            asset_external_id="CH-ACC",
            country="CH",
            source_id="tx-ch",
        )
        earlier = _obs(
            asset_class=ForeignAssetClass.ACCOUNT,
            valuation="60000.00",
            asset_external_id="AD-ACC",
            country="AD",
            source_id="tx-ad",
        )

        def declared_condition_of(lots: tuple[ForeignAssetIngestObservation, ...]) -> dict[str, str]:
            register = _register_for(*lots).model_copy(
                update={
                    "declarations": tuple(
                        _declared(
                            lot.asset_ref,
                            M720DeclarantCondition.AUTORIZADO if lot is later else M720DeclarantCondition.TITULAR,
                        )
                        for lot in lots
                    ),
                },
            )
            resolution = _resolver(observations=lots, register=register).resolve(_context())
            values = dict(resolution.row_binding_values)
            indexes = {index for _, index in values}
            return {
                str(values[("modelo-720-asset-row-asset-ref", index)]): str(
                    values[("modelo-720-asset-row-declarant-condition", index)]
                )
                for index in indexes
            }

        assert declared_condition_of((later,))[later.asset_ref] == "3"
        both = declared_condition_of((later, earlier))
        assert both[later.asset_ref] == "3"
        assert both[earlier.asset_ref] == "1"

    @pytest.mark.parametrize(
        ("register_change", "reason"),
        [
            ({"assets": (), "declarations": ()}, M720RecordJoinRefusalReason.UNREGISTERED_ASSET),
            ({"declarations": ()}, M720RecordJoinRefusalReason.UNDECLARED_ASSET),
        ],
    )
    def test_an_unmatched_lot_is_refused_naming_the_asset(
        self, register_change: dict[str, tuple[()]], reason: M720RecordJoinRefusalReason
    ) -> None:
        lot = _obs(asset_class=ForeignAssetClass.ACCOUNT, valuation="60000.00", asset_external_id="AD-ACC-9")
        register = _register_for(lot).model_copy(update=register_change)

        with pytest.raises(ForeignAssetRecordJoinRefusedError) as refused:
            _resolver(observations=(lot,), register=register).resolve(_context())

        assert (refused.value.asset_ref, refused.value.reason) == (lot.asset_ref, reason)

    def test_a_lot_whose_identifier_disagrees_with_the_register_is_refused(self) -> None:
        lot = _obs(asset_class=ForeignAssetClass.ACCOUNT, valuation="60000.00", asset_external_id="AD-ACC-1")
        moved = _obs(asset_class=ForeignAssetClass.ACCOUNT, valuation="60000.00", asset_external_id="AD-ACC-2")
        register = _register_for(moved).model_copy(
            update={
                "assets": (_registered(moved).model_copy(update={"asset_ref": lot.asset_ref}),),
                "declarations": (_declared(lot.asset_ref),),
            },
        )

        with pytest.raises(ForeignAssetRecordJoinRefusedError) as refused:
            _resolver(observations=(lot,), register=register).resolve(_context())

        assert refused.value.reason is M720RecordJoinRefusalReason.REGISTER_MISMATCH

    def test_a_declaration_without_a_lot_stays_visible_as_an_advisory(self) -> None:
        lot = _obs(asset_class=ForeignAssetClass.ACCOUNT, valuation="60000.00", asset_external_id="AD-ACC-3")
        sold = _obs(asset_class=ForeignAssetClass.ACCOUNT, valuation="1.00", asset_external_id="AD-ACC-SOLD")
        dormant = _obs(asset_class=ForeignAssetClass.REAL_ESTATE, valuation="1.00", asset_external_id="AD-FLAT")
        register = _register_for(lot, sold, dormant)

        resolution = _resolver(observations=(lot,), register=register).resolve(_context())

        by_asset = {diagnostic.source_ref: diagnostic for diagnostic in resolution.diagnostics}
        assert set(by_asset) == {
            f"foreign_asset_register:{sold.asset_ref}",
            f"foreign_asset_register:{dormant.asset_ref}",
        }
        assert "cannot be completed" in by_asset[f"foreign_asset_register:{sold.asset_ref}"].message
        assert "not exported" in by_asset[f"foreign_asset_register:{dormant.asset_ref}"].message

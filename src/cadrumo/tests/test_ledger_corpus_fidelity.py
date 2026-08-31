"""Corpus-fidelity gate for the ledger operator-testimonial corpus.

Imports the raw bank-export corpus through the real
:class:`~adapters.inbound.financial.providers.CsvProvider`, applies the
ground-truth oracle classification (``ground-truth.manifest.json``), wires a
corpus-local ECB observation set into :class:`~domain.currency.CurrencyNormalizationService`
for the foreign-currency rows, builds strict :class:`~domain.transactions.Transaction`
records, and runs the real aggregation pipelines.

The oracle states each row's expected typed facts and target bucket; the
pipelines independently route and gate from the typed fields. The assertions
verify routing/gating/normalization (the system under test) against the oracle's
independent expectation -- they do NOT re-compute registry tax formulas
(per ``aeat-quality-gates``).

See Also:
    Fixture corpus
        ``tests/fixtures/financial/ledger-corpus`` contains the raw bank-export
        files and ground-truth manifest consumed by this gate.
    :class:`~domain.transactions.TransactionCatalogue`
        Strict transaction collection passed to the aggregation pipelines.
    :func:`~application.aggregation.aggregate_iva_ledger_observations`
        IVA projection path checked for gating and category/flow fidelity.
    :func:`~application.aggregation.aggregate_renta_income_ledger`
        M130 income projection path checked for trabajo/capital exclusions.

The ledger commits to a raw-corpus-plus-typed-oracle contract, and the ECB
conversion seam grounds every foreign-currency row's normalisation.
"""

from __future__ import annotations

import json
from datetime import UTC, date, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
from typing import Any

import pytest

from ..adapters.inbound.financial.providers._csv import CsvProvider
from ..adapters.outbound.fx._ecb_provider import EcbReferenceRateProvider
from ..application.aggregation import (
    IvaLedgerAggregationIssueReason,
    aggregate_iva_ledger_observations,
    aggregate_renta_income_ledger,
)
from ..core.period import Period
from ..domain.bienes_inversion.register import BienesInversionIvaRegister
from ..domain.currency.models import CurrencyNormalizationStatus, MonetaryAmount
from ..domain.currency.service import CurrencyNormalizationService
from ..domain.iva.flow import IvaFlowDirection
from ..domain.iva.schema import EUMemberState, IvaCategory
from ..domain.transactions.enums import BusinessClassification, TransactionDirection, TransactionLifecycleState
from ..domain.transactions.models import Transaction, TransactionCatalogue
from .ecb_stub import ecb_csv_fetch

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_CORPUS = Path(__file__).parent / "fixtures" / "financial" / "ledger-corpus"
_CENT = Decimal("0.01")
_CLASSIFIED_AT = datetime(2026, 6, 2, 12, 0, tzinfo=UTC)

# Corpus FX oracle, in the ECB's own EUR-base direction. The quotes are chosen so
# their inverses -- the CCY->EUR multipliers the provider returns -- are exactly
# 1.18 EUR per GBP and 0.92 EUR per USD, keeping the manifest's expected EUR
# values exact rather than rounding-dependent.
#
# The rate is deliberately held flat across the whole corpus period: this corpus
# pins classification and aggregation fidelity, so a moving rate would couple its
# expected EUR totals to FX movement it is not testing. Real per-date ECB
# resolution is covered by the provider's own suite. The quote is declared on
# every day of the period rather than on one day, because the provider bounds its
# working-day fallback to a short window and must never reach back a year.
_CORPUS_FX_START = date(2024, 12, 1)
_CORPUS_FX_END = date(2026, 8, 1)
_CORPUS_FLAT_QUOTES = {
    "GBP": Decimal("0.8474576271186440677966101695"),
    "USD": Decimal("1.086956521739130434782608696"),
}
_CORPUS_QUOTES = {
    currency: {
        _CORPUS_FX_START + timedelta(days=offset): quote
        for offset in range((_CORPUS_FX_END - _CORPUS_FX_START).days + 1)
    }
    for currency, quote in _CORPUS_FLAT_QUOTES.items()
}


def _load_manifest() -> dict[str, Any]:
    return json.loads((_CORPUS / "ground-truth.manifest.json").read_text(encoding="utf-8"))


def _match_rule(description: str, rules: list[dict[str, Any]]) -> dict[str, Any] | None:
    for rule in rules:
        if rule["match"] in description:
            return rule
    return None


def _q(value: Decimal) -> Decimal:
    return value.quantize(_CENT, rounding=ROUND_HALF_UP)


def _derive_base_iva(
    rule: dict[str, Any],
    native_amount_abs: Decimal,
) -> tuple[Decimal | None, Decimal | None, Decimal | None]:
    """Return (taxable_base, iva_rate, iva_amount) per the oracle base_mode."""
    mode = rule["base_mode"]
    rate = Decimal(rule["iva_rate"]) if rule.get("iva_rate") else None
    if mode == "gated":
        return (None, None, None)
    if mode == "no_iva":
        return (native_amount_abs, None, None)
    if mode == "gross_includes_iva":
        r = rate or Decimal("0")
        base = _q(native_amount_abs / (Decimal("1") + r))
        return (base, rate, _q(native_amount_abs - base))
    if mode == "net_is_cash":
        base = native_amount_abs
        iva = _q(base * rate) if rate and rate > 0 else Decimal("0.00")
        return (base, rate, iva)
    raise AssertionError(f"unknown base_mode {mode!r}")


def _build_transactions() -> list[tuple[Transaction, dict[str, Any], str]]:
    """Import every corpus row and classify it per the oracle.

    Returns a list of (transaction, rule, currency) triples.
    """
    manifest = _load_manifest()
    rules = manifest["rules"]
    fx = CurrencyNormalizationService(rate_provider=EcbReferenceRateProvider(fetch=ecb_csv_fetch(_CORPUS_QUOTES)))
    provider = CsvProvider()

    built: list[tuple[Transaction, dict[str, Any], str]] = []
    for account in manifest["accounts"]:
        for parsed in provider.ingest(_CORPUS / account["file"]):
            raw = parsed.raw
            rule = _match_rule(raw.description, rules)
            assert rule is not None, f"no oracle rule for {raw.description!r}"

            fx_rate: Decimal | None = None
            value_in_eur: Decimal | None = None
            if raw.currency != "EUR":
                normalized = fx.normalize(
                    MonetaryAmount(amount=raw.amount, currency=raw.currency),
                    raw.value_date or raw.booked_date,
                )
                assert normalized.status is CurrencyNormalizationStatus.NORMALIZED, (
                    f"foreign row failed to normalize: {raw.description!r} -> {normalized.status}"
                )
                fx_rate = normalized.rate
                value_in_eur = abs(normalized.eur_amount)

            taxable_base, iva_rate, iva_amount = _derive_base_iva(rule, abs(raw.amount))

            iva_category = rule.get("iva_category")
            eu_member_state = rule.get("eu_member_state")
            # A non-EU counterparty (export) has no eu_member_state at all, but the
            # export exemption still turns on where the counterparty is ESTABLISHED,
            # so those rules state their own counterparty_country explicitly rather
            # than leaving establishment unset.
            counterparty_country = rule.get("counterparty_country") or (
                eu_member_state.upper() if eu_member_state else None
            )
            payload: dict[str, Any] = {
                "raw": raw,
                "direction": TransactionDirection(rule["direction"]),
                "business_classification": BusinessClassification(rule["classification"]),
                "taxable_base": taxable_base,
                "iva_rate": iva_rate,
                "iva_amount": iva_amount,
                "category_id": rule.get("category_id"),
                "iva_category": IvaCategory(iva_category) if iva_category else None,
                "counterparty_country": counterparty_country,
                "counterparty_identification_state": (
                    EUMemberState(eu_member_state.lower()) if eu_member_state else None
                ),
                "irpf_category": rule.get("irpf_category"),
                "source_jurisdiction": "ES",
                "group_label": None,
                "fx_rate": fx_rate,
                "value_in_eur": value_in_eur,
                "lifecycle_state": TransactionLifecycleState.ACTIVE,
                "classified_at": _CLASSIFIED_AT,
                "classified_by": "manual",
            }
            if rule["classification"] == "MIXED":
                payload["business_pct"] = Decimal(rule["business_pct"])
            built.append((Transaction.model_validate(payload), rule, raw.currency))
    return built


# Build once at import; each row building through the strict pydantic model is
# itself a fidelity assertion (invalid field combinations would raise here).
_BUILT = _build_transactions()
_QUARTERLY_TEST_PERIODS = (
    Period.from_year_and_code(2025, "1T"),
    Period.from_year_and_code(2025, "2T"),
    Period.from_year_and_code(2025, "3T"),
    Period.from_year_and_code(2025, "4T"),
    Period.from_year_and_code(2026, "1T"),
    Period.from_year_and_code(2026, "2T"),
)


def test_corpus_is_operating_scale() -> None:
    assert len(_BUILT) >= 500


def test_foreign_currency_rows_carry_eur_conversion() -> None:
    foreign = [(tx, ccy) for tx, _, ccy in _BUILT if ccy != "EUR"]
    assert foreign, "corpus must contain foreign-currency rows"
    for tx, _ccy in foreign:
        assert tx.fx_rate is not None
        assert tx.value_in_eur is not None


def _catalogue() -> TransactionCatalogue:
    return TransactionCatalogue.from_transactions(tuple(tx for tx, _, _ in _BUILT))


def test_iva_pipeline_gates_transfers_personal_and_nondeclarable() -> None:
    """No gated row may ever surface as an IVA observation, any period."""
    gated_ids = {tx.transaction_id for tx, rule, _ in _BUILT if not rule.get("iva_declarable", False)}
    catalogue = _catalogue()
    emitted: set[str] = set()
    for period in _QUARTERLY_TEST_PERIODS:
        result = aggregate_iva_ledger_observations(
            catalogue,
            period=period,
            ledger_profile_id="corpus-test",
            investment_asset_register=BienesInversionIvaRegister(),
            investment_asset_profile_id="corpus-test",
        )
        emitted.update(o.ledger_id for o in result.observations)
    leaked = emitted & gated_ids
    assert not leaked, f"{len(leaked)} non-declarable rows leaked into IVA observations"


def test_iva_observations_match_oracle_category_and_flow() -> None:
    """Every emitted observation matches the oracle's category and flow."""
    by_id = {tx.transaction_id: rule for tx, rule, _ in _BUILT}
    catalogue = _catalogue()
    seen = 0
    for period in _QUARTERLY_TEST_PERIODS:
        result = aggregate_iva_ledger_observations(
            catalogue,
            period=period,
            ledger_profile_id="corpus-test",
            investment_asset_register=BienesInversionIvaRegister(),
            investment_asset_profile_id="corpus-test",
        )
        # Issues are the pipeline's gating signal for transfers / personal /
        # no-IVA rows; they are expected for a mixed corpus, not an error.
        for obs in result.observations:
            rule = by_id[obs.ledger_id]
            assert obs.category is IvaCategory(rule["iva_category"]), (
                f"{rule['match']}: {obs.category} != {rule['iva_category']}"
            )
            expected_flow = (
                IvaFlowDirection.REPERCUTIDO if rule["direction"] == "INCOMING" else IvaFlowDirection.SOPORTADO
            )
            # Reverse-charge / intra-community acquisition / import self-assess
            # as inversion sujeto pasivo; allow either the directional flow or ISP.
            assert obs.flow_direction in {expected_flow, IvaFlowDirection.INVERSION_SUJETO_PASIVO}
            seen += 1
    assert seen > 0


def test_iva_pipeline_refuses_input_categories_without_authoritative_deduction_evidence() -> None:
    """Legacy corpus input categories remain blocked until their evidence oracle is extended."""
    catalogue = _catalogue()
    categories: set[IvaCategory] = set()
    refusal_count = 0
    for period in _QUARTERLY_TEST_PERIODS:
        result = aggregate_iva_ledger_observations(
            catalogue,
            period=period,
            ledger_profile_id="corpus-test",
            investment_asset_register=BienesInversionIvaRegister(),
            investment_asset_profile_id="corpus-test",
        )
        categories.update(o.category for o in result.observations)
        refusal_count += sum(
            issue.reason is IvaLedgerAggregationIssueReason.MISSING_DEDUCTION_CLASSIFICATION for issue in result.issues
        )
    for required in (
        IvaCategory.DOMESTIC_GENERAL,
        IvaCategory.INTRA_COMMUNITY_SUPPLY,
        IvaCategory.EXPORT_THIRD_COUNTRY_ZERO_RATED,
    ):
        assert required in categories, f"{required} never reached M303"
    assert IvaCategory.INTRA_COMMUNITY_ACQUISITION_REVERSE_CHARGE not in categories
    assert IvaCategory.IMPORT_THIRD_COUNTRY not in categories
    assert refusal_count > 0


def test_renta_income_excludes_salary_rent_and_interest_from_m130() -> None:
    """Trabajo / capital income must not feed M130 actividad income."""
    excluded_ids = {tx.transaction_id for tx, rule, _ in _BUILT if "excluded_m130" in rule.get("feeds", [])}
    assert excluded_ids, "corpus must contain salary/rent/interest income"
    catalogue = _catalogue()
    emitted: set[str] = set()
    for period in _QUARTERLY_TEST_PERIODS:
        result = aggregate_renta_income_ledger(catalogue, bucket_id="corpus", period=period)
        emitted.update(o.transaction_id for o in result.observations)
    leaked = emitted & excluded_ids
    assert not leaked, f"{len(leaked)} trabajo/capital rows leaked into M130 income"


def test_recargo_equivalencia_is_not_deductible_input_iva() -> None:
    """The RE anomaly row must never surface as deductible soportado IVA."""
    re_ids = {
        tx.transaction_id
        for tx, rule, _ in _BUILT
        if rule.get("iva_category") == IvaCategory.RECARGO_EQUIVALENCIA.value
    }
    assert re_ids, "corpus must contain the recargo-equivalencia anomaly row"
    catalogue = _catalogue()
    for period in _QUARTERLY_TEST_PERIODS:
        result = aggregate_iva_ledger_observations(
            catalogue,
            period=period,
            ledger_profile_id="corpus-test",
            investment_asset_register=BienesInversionIvaRegister(),
            investment_asset_profile_id="corpus-test",
        )
        soportado = {o.ledger_id for o in result.observations if o.flow_direction is IvaFlowDirection.SOPORTADO}
        assert not (soportado & re_ids), "RE row leaked into deductible soportado IVA"

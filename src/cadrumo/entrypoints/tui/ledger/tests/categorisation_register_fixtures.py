"""In-memory counterparty facts, usage ratios and classifier diagnostics for the categorisation tools.

Each handler answers with the operation's own public result model, so the
screens meet the same request validation and result invariants the registered
operations publish. Values are synthetic.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from hashlib import sha256

from .....application.ledger.counterparty_operation import (
    CounterpartyFactProjection,
    CounterpartyResolutionProjection,
    LedgerCounterpartyRequest,
    LedgerCounterpartyResult,
)
from .....application.ledger.llm_diagnostics_operation import (
    LedgerLlmConfidenceProviderSnapshot,
    LedgerLlmDiagnosticsProjection,
    LedgerLlmDiagnosticsReportSnapshot,
    LedgerLlmDiagnosticsRequest,
    LedgerLlmUsageCostProviderSnapshot,
)
from .....application.ledger.ratios_contracts import (
    LedgerRatiosEligibleProjection,
    LedgerRatiosEligibleRequest,
    LedgerRatiosEligibleRow,
    LedgerRatiosListProjection,
    LedgerRatiosListRequest,
    LedgerRatiosListRow,
    LedgerRatiosSetProjection,
    LedgerRatiosSetRequest,
    LedgerRatiosUnsetProjection,
    LedgerRatiosUnsetRequest,
    LedgerRatiosValidateProjection,
    LedgerRatiosValidateRequest,
    LedgerRatiosValidationFinding,
)
from .....application.operations.public_scalar import PublicDecimal
from .....core.operations import OperationEffect

_ASSERTED_AT = datetime(2026, 3, 1, tzinfo=UTC)
SYNTHETIC_TAX_ID = "B00000000"
SYNTHETIC_RATIO_CATEGORIES = ("suministros_vivienda", "vehiculo")


@dataclass
class MemoryCounterparties:
    """Confirmed establishment facts keyed by tax identifier."""

    facts: dict[str, CounterpartyFactProjection] = field(default_factory=dict)

    def act(self, request: LedgerCounterpartyRequest) -> LedgerCounterpartyResult:
        if request.action == "view":
            fact = self.facts.get(request.tax_identifier)
            return LedgerCounterpartyResult(
                profile_id=request.profile_id,
                action=request.action,
                tax_identifier=request.tax_identifier,
                country_code=request.country_code,
                evidenced_scope=request.evidenced_scope,
                resolution=CounterpartyResolutionProjection(
                    territorial_scope=None if fact is None else fact.territorial_scope,
                    territorial_source=None if fact is None else "operator_confirmed",
                    identification_state=None if fact is None else fact.identification_state,
                    identification_source=None if fact is None else "operator_confirmed",
                ),
            )
        if request.action == "withdraw":
            withdrawn = self.facts.pop(request.tax_identifier, None) is not None
            return LedgerCounterpartyResult(
                profile_id=request.profile_id,
                action=request.action,
                tax_identifier=request.tax_identifier,
                country_code=request.country_code,
                withdrawn=withdrawn,
                changed=withdrawn,
            )
        fact = CounterpartyFactProjection(
            counterparty_key=sha256(request.tax_identifier.encode()).hexdigest(),
            canonical_tax_identifier=request.tax_identifier,
            territorial_scope=request.territorial_scope,
            identification_state=request.identification_state,
            asserted_by=request.asserted_by or "operator",
            asserted_at=_ASSERTED_AT,
            note=request.note,
        )
        changed = self.facts.get(request.tax_identifier) != fact
        self.facts[request.tax_identifier] = fact
        return LedgerCounterpartyResult(
            profile_id=request.profile_id,
            action=request.action,
            tax_identifier=request.tax_identifier,
            country_code=request.country_code,
            facts=fact,
            recorded=True,
            changed=changed,
        )


@dataclass
class MemoryRatios:
    """Eligible ratio categories with their defaults and the profile's overrides."""

    overrides: dict[str, str] = field(default_factory=dict)
    censo_mismatch: bool = False

    def list_overrides(self, request: LedgerRatiosListRequest) -> LedgerRatiosListProjection:
        if self.censo_mismatch:
            return LedgerRatiosListProjection(
                profile_id=request.profile_id, year=request.year, outcome="censo_mismatch", count=0
            )
        rows = tuple(LedgerRatiosListRow(category=key, ratio=value) for key, value in sorted(self.overrides.items()))
        return LedgerRatiosListProjection(
            profile_id=request.profile_id, year=request.year, outcome="available", rows=rows, count=len(rows)
        )

    def eligible(self, request: LedgerRatiosEligibleRequest) -> LedgerRatiosEligibleProjection:
        rows = tuple(
            LedgerRatiosEligibleRow(
                category=category,
                proportionality_kind="surface_share" if index == 0 else "usage_share",
                default_ratio="0.3" if index == 0 else None,
                override_present=category in self.overrides,
            )
            for index, category in enumerate(SYNTHETIC_RATIO_CATEGORIES)
        )
        return LedgerRatiosEligibleProjection(
            profile_id=request.profile_id, year=request.year, rows=rows, count=len(rows)
        )

    def validate(self, request: LedgerRatiosValidateRequest) -> LedgerRatiosValidateProjection:
        missing = tuple(category for category in SYNTHETIC_RATIO_CATEGORIES if category not in self.overrides)
        findings = tuple(
            LedgerRatiosValidationFinding(category=category, kind="above_default", detail="share above 0.5")
            for category, ratio in sorted(self.overrides.items())
            if float(ratio) > 0.5
        )
        return LedgerRatiosValidateProjection(
            profile_id=request.profile_id,
            profile_present=True,
            eligible_count=len(SYNTHETIC_RATIO_CATEGORIES),
            overrides_count=len(self.overrides),
            missing_overrides=missing,
            findings=findings,
        )

    def set_ratio(self, request: LedgerRatiosSetRequest) -> LedgerRatiosSetProjection:
        prior = self.overrides.get(request.category)
        self.overrides[request.category] = request.ratio
        return LedgerRatiosSetProjection(
            profile_id=request.profile_id,
            requested_category=request.category,
            category=request.category,
            ratio=request.ratio,
            prior_ratio=prior,
        )

    def unset_ratio(self, request: LedgerRatiosUnsetRequest) -> LedgerRatiosUnsetProjection:
        prior = self.overrides.pop(request.category, None)
        return LedgerRatiosUnsetProjection(
            profile_id=request.profile_id,
            requested_category=request.category,
            category=request.category,
            outcome="cleared" if prior is not None else "no_override",
            prior_ratio=prior,
        )


def diagnostics_report(
    request: LedgerLlmDiagnosticsRequest, *, with_data: bool = True
) -> LedgerLlmDiagnosticsProjection:
    """A synthetic classifier report for exactly the requested coordinates."""
    usage = (
        (
            LedgerLlmUsageCostProviderSnapshot(
                provider="lector-local",
                calls=42,
                cache_hits=10,
                input_tokens=12000,
                output_tokens=3000,
                total_tokens=15000,
                cost_estimate_usd=None,
                unpriced_calls=42,
            ),
        )
        if with_data
        else ()
    )
    confidence = (
        (
            LedgerLlmConfidenceProviderSnapshot(
                provider="lector-local",
                classified_count=30,
                low_confidence_count=4,
                high_confidence_count=20,
                medium_confidence_count=6,
                min_confidence=PublicDecimal(decimal="0.31"),
                max_confidence=PublicDecimal(decimal="0.97"),
                mean_confidence=PublicDecimal(decimal="0.81"),
            ),
        )
        if with_data
        else ()
    )
    return LedgerLlmDiagnosticsProjection(
        profile_id=request.profile_id,
        operation_id="ledger.llm-diagnostics",
        outcome="completed",
        effect=OperationEffect.NONE,
        since=request.since,
        until=request.until,
        low_confidence_threshold=request.low_confidence_threshold,
        report=LedgerLlmDiagnosticsReportSnapshot(
            since=request.since,
            until=request.until,
            low_confidence_threshold=request.low_confidence_threshold,
            usage_providers=usage,
            total_calls=sum(row.calls for row in usage),
            total_cache_hits=sum(row.cache_hits for row in usage),
            total_input_tokens=sum(row.input_tokens for row in usage),
            total_output_tokens=sum(row.output_tokens for row in usage),
            total_cost_estimate_usd=None,
            total_unpriced_calls=sum(row.unpriced_calls for row in usage),
            confidence_providers=confidence,
            total_classified=sum(row.classified_count for row in confidence),
            total_low_confidence=sum(row.low_confidence_count for row in confidence),
        ),
    )


__all__ = [
    "SYNTHETIC_RATIO_CATEGORIES",
    "SYNTHETIC_TAX_ID",
    "MemoryCounterparties",
    "MemoryRatios",
    "diagnostics_report",
]

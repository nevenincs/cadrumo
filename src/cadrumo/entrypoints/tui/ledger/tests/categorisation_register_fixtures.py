"""In-memory counterparty facts, usage ratios and classifier diagnostics for the categorisation tools.

Each handler answers with the operation's own public result model, so the
screens meet the same request validation and result invariants the registered
operations publish. Values are synthetic.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from hashlib import sha256

from .....application.ledger.counterparty_establishment import declared_filing_name_from_parts
from .....application.ledger.counterparty_filing_name_slots import (
    CounterpartyFilingNamePartLimit,
    CounterpartyFilingNameSlot,
    FilingNameSlotRefusal,
)
from .....application.ledger.counterparty_operation import (
    CounterpartyFactProjection,
    CounterpartyFilingNameFinding,
    CounterpartyFilingNameProjection,
    CounterpartyFilingNameRendering,
    CounterpartyResolutionProjection,
    LedgerCounterpartyRequest,
    LedgerCounterpartyResult,
    served_kind_finding_words,
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
from .....core.external_constants import OutputLanguage
from .....core.operations import OperationEffect
from .....domain.calculations.registry.tests.authored_editions import filing_year_envelope

_YEAR = filing_year_envelope().horizon
_ASSERTED_AT = datetime(_YEAR, 3, 1, tzinfo=UTC)
SYNTHETIC_ASSERTED_ON = _ASSERTED_AT.date().isoformat()
SYNTHETIC_TAX_ID = "B00010082"
_NATURAL_PERSON_FIRST_CHARACTERS = "0123456789KLMXYZ"
SYNTHETIC_RATIO_CATEGORIES = ("suministros_vivienda", "vehiculo")
SYNTHETIC_EDITION_WORDS = ("Synthetic edition A", "Synthetic edition B")
"""The edition words the synthetic slots are served with."""
SYNTHETIC_SLOT_WIDTHS = (40, 20)
"""The widths of the synthetic party-name slots a view serves."""
SYNTHETIC_PART_LIMITS = (
    CounterpartyFilingNamePartLimit(part="primer_apellido", max_length=36),
    CounterpartyFilingNamePartLimit(part="razon_social", max_length=40),
)


def _synthetic_slots(name: CounterpartyFilingNameProjection | None) -> tuple[CounterpartyFilingNameSlot, ...]:
    """Synthetic slots in the served shape: unfilled with no name, else filled whole or by a stated rendering."""
    slots: list[CounterpartyFilingNameSlot] = []
    for index, (edition, width) in enumerate(
        ((SYNTHETIC_EDITION_WORDS[0], SYNTHETIC_SLOT_WIDTHS[0]), (SYNTHETIC_EDITION_WORDS[1], SYNTHETIC_SLOT_WIDTHS[1]))
    ):
        composed = (
            None
            if name is None
            else " ".join(
                part
                for part in (name.primer_apellido, name.segundo_apellido, name.nombre, name.razon_social)
                if part is not None
            )
        )
        rendered = name is not None and any(item.width == width for item in name.renderings)
        refusal: FilingNameSlotRefusal | None = (
            "missing" if composed is None else "too_wide" if len(composed) > width and not rendered else None
        )
        slots.append(
            CounterpartyFilingNameSlot(
                modelo="synthetic",
                revision_id=f"synthetic-{index}",
                edition_words=edition,
                edition_words_language=OutputLanguage.EN,
                layout_id="synthetic",
                export_record_id="synthetic",
                export_field_id=f"synthetic-{index}",
                width=width,
                fits=refusal is None,
                refusal=refusal,
                composed_length=None if composed is None else len(composed),
                uses_rendering=refusal is None and composed is not None and len(composed) > width,
            )
        )
    return tuple(slots)


def ratio_label(category: str, language: str) -> str:
    """Say a synthetic category's served label, naming the language the request asked for."""
    return f"{category} label ({language})"


def ratio_notes(category: str, language: str) -> str:
    """Say a synthetic category's served notes, naming the language the request asked for."""
    return f"{category} notes ({language})"


@dataclass
class MemoryCounterparties:
    """Confirmed establishment facts keyed by tax identifier."""

    facts: dict[str, CounterpartyFactProjection] = field(default_factory=dict)
    filing_names: dict[str, CounterpartyFilingNameProjection] = field(default_factory=dict)

    def _findings(
        self, request_identifier: str, name: CounterpartyFilingNameProjection | None
    ) -> tuple[CounterpartyFilingNameFinding, ...]:
        """Flag a stated kind that differs from the form the identifier's first character shows."""
        if name is None:
            return ()
        observed = "natural_person" if request_identifier[0] in _NATURAL_PERSON_FIRST_CHARACTERS else "entity"
        if name.party_kind == observed:
            return ()
        words, language = served_kind_finding_words(declared_kind=name.party_kind, observed_form=observed)
        return (
            CounterpartyFilingNameFinding(
                code="counterparty_filing_name_kind_contradicts_identifier_form",
                declared_kind="natural_person" if name.party_kind == "natural_person" else "entity",
                observed_form="natural_person" if observed == "natural_person" else "entity",
                words=words,
                words_language=language,
            ),
        )

    def _state_filing_name(self, request: LedgerCounterpartyRequest) -> LedgerCounterpartyResult:
        """Form the name with the operation's own parser, so a statement that forms none is refused as it is."""
        stated = declared_filing_name_from_parts(
            kind=request.party_kind or "",
            primer_apellido=request.primer_apellido,
            segundo_apellido=request.segundo_apellido,
            no_second_surname=request.no_second_surname,
            nombre=request.nombre,
            razon_social=request.razon_social,
            renderings=tuple((item.width, item.text) for item in request.renderings),
        )
        name = CounterpartyFilingNameProjection(
            party_kind=stated.kind.value,
            primer_apellido=stated.primer_apellido,
            segundo_apellido=stated.segundo_apellido,
            no_second_surname=stated.no_second_surname,
            nombre=stated.nombre,
            razon_social=stated.razon_social,
            renderings=tuple(
                CounterpartyFilingNameRendering(width=item.width, text=item.text) for item in stated.renderings
            ),
            asserted_by=request.asserted_by or "operator",
            asserted_at=_ASSERTED_AT,
        )
        changed = self.filing_names.get(request.tax_identifier) != name
        self.filing_names[request.tax_identifier] = name
        return LedgerCounterpartyResult(
            profile_id=request.profile_id,
            action=request.action,
            tax_identifier=request.tax_identifier,
            country_code=request.country_code,
            filing_name=name,
            findings=self._findings(request.tax_identifier, name),
            changed=changed,
        )

    def act(self, request: LedgerCounterpartyRequest) -> LedgerCounterpartyResult:
        if request.action == "filing_name":
            return self._state_filing_name(request)
        if request.action == "view":
            fact = self.facts.get(request.tax_identifier)
            name = self.filing_names.get(request.tax_identifier)
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
                filing_name=name,
                findings=self._findings(request.tax_identifier, name),
                filing_name_slots=_synthetic_slots(name),
                filing_name_part_limits=SYNTHETIC_PART_LIMITS,
            )
        if request.action == "withdraw":
            # The record is withdrawn whole: the confirmation and the filing name with it.
            had_fact = self.facts.pop(request.tax_identifier, None) is not None
            had_name = self.filing_names.pop(request.tax_identifier, None) is not None
            withdrawn = had_fact or had_name
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
    """Eligible ratio categories with their wording and the profile's overrides."""

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
                label=ratio_label(category, request.output_language.value),
                notes=ratio_notes(category, request.output_language.value),
                proportionality_kind="surface_share" if index == 0 else "usage_share",
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
    "SYNTHETIC_ASSERTED_ON",
    "SYNTHETIC_RATIO_CATEGORIES",
    "SYNTHETIC_TAX_ID",
    "MemoryCounterparties",
    "MemoryRatios",
    "diagnostics_report",
]

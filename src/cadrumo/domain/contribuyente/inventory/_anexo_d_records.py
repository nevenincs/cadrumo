"""Canonical Anexo D projection records for inventory ledgers.

The public projection model and closing resolver are loaded by the records
facade after the foundational ledger records exist. Their public module
identity remains the historical records module.
"""

from __future__ import annotations

from dataclasses import fields as dataclass_fields
from datetime import date
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

from ....core.decimal.constants import MONEY_ZERO
from ....core.filing_year import FilingYear
from ....core.hashing import content_hash_hex as _content_hash_hex
from ....core.identity.digest import ContentDigest
from ....core.models import STRICT_FROZEN_CONFIG as _STRICT_FROZEN_CONFIG
from ....core.money.rounding import round_to_cents as _quantize
from ...calculations.registry.authority import bundled_authority
from ...calculations.registry.queries import RegistryQueryService
from .closing_authority_records import (
    InventoryClosingAuthorityDecision,
    InventoryClosingConflictDiagnostic,
    InventoryClosingResolution,
    PriorAuthoritativeClosingLink,
)
from .records import (
    InventoryClosingAuthority,
    InventoryClosingValuationBasis,
    InventoryLedger,
    InventoryLedgerError,
    InventoryValidationError,
    PhysicalClosingObservation,
    ValuationMethod,
)


def _resolve_anexo_d_registry_declarations(*, filing_year: int) -> tuple[object, object]:
    """Resolve the selected M100 record and inventory-binding surfaces."""
    query_service = RegistryQueryService(bundled_authority())
    model_report = query_service.describe_modelo("100")
    bindings_report = query_service.bindings_for_year(
        "100",
        filing_year=filing_year,
        as_of=date(filing_year, 12, 31),
    )
    return model_report, bindings_report


def _validate_anexo_d_quantised_values(result: InventoryAnexoDResult) -> None:
    monetary_values = (
        result.opening_value,
        result.movement_derived_closing_value,
        result.authoritative_closing_value,
        *(value for value in (result.physical_observed_closing_value,) if value is not None),
        result.complete_acquisition_total,
        result.variation_increase_value,
        result.variation_decrease_value,
    )
    if any(value != _quantize(value) for value in monetary_values):
        raise InventoryValidationError("inventory projection values must be quantised to cents")


def _validate_anexo_d_variation_split(result: InventoryAnexoDResult) -> None:
    signed_variation = _quantize(result.authoritative_closing_value - result.opening_value)
    expected_increase = max(signed_variation, MONEY_ZERO)
    expected_decrease = max(-signed_variation, MONEY_ZERO)
    if result.variation_increase_value != expected_increase or result.variation_decrease_value != expected_decrease:
        raise InventoryValidationError(
            "inventory variation outputs must be the mutually exclusive split of closing minus opening",
        )


def _validate_anexo_d_acquisition_values(result: InventoryAnexoDResult) -> None:
    if result.complete_acquisition_total > MONEY_ZERO and not result.acquisition_fingerprints:
        raise InventoryValidationError("nonzero acquisition cost requires acquisition fingerprints")
    if len(set(result.acquisition_fingerprints)) != len(result.acquisition_fingerprints):
        raise InventoryValidationError("acquisition fingerprints must be unique")


def _validate_anexo_d_physical_state(result: InventoryAnexoDResult) -> bool:
    physical_state = (
        result.physical_observation_id,
        result.physical_observation_fingerprint,
        result.physical_observed_closing_value,
    )
    has_missing_value = any(value is None for value in physical_state)
    has_present_value = any(value is not None for value in physical_state)
    if has_missing_value and has_present_value:
        raise InventoryValidationError("physical observation identity, fingerprint, and value must travel together")
    has_physical = result.physical_observation_id is not None
    physical_differs = has_physical and result.physical_observed_closing_value != result.movement_derived_closing_value
    if physical_differs != (result.closing_conflict is not None):
        raise InventoryValidationError("divergent physical closing requires its retained conflict diagnostic")
    return has_physical


def _validate_anexo_d_authority_selection(result: InventoryAnexoDResult, has_physical: bool) -> None:
    if result.selected_authority is InventoryClosingAuthority.PHYSICAL_OBSERVATION:
        if not has_physical:
            raise InventoryValidationError("physical projection authority requires physical observation identity")
        if result.closing_conflict is None:
            if result.authoritative_closing_value != result.movement_derived_closing_value:
                raise InventoryValidationError("physical authority without conflict must equal movement closing")
        elif result.authoritative_closing_value != result.closing_conflict.physical_observed_value:
            raise InventoryValidationError("physical authoritative closing must match retained observation")
    elif result.authoritative_closing_value != result.movement_derived_closing_value:
        raise InventoryValidationError("movement-derived authority must select movement-derived closing")


def _validate_anexo_d_conflict(result: InventoryAnexoDResult, has_physical: bool) -> None:
    conflict = result.closing_conflict
    if conflict is None:
        return
    if not has_physical:
        raise InventoryValidationError("closing conflict requires physical observation identity")
    if (
        conflict.actividad_id != result.actividad_id
        or conflict.filing_year != result.filing_year
        or conflict.movement_derived_value != result.movement_derived_closing_value
        or conflict.physical_observed_value != result.physical_observed_closing_value
        or conflict.physical_observation_fingerprint != result.physical_observation_fingerprint
    ):
        raise InventoryValidationError("closing conflict must exactly match projection provenance")


def _validate_anexo_d_issues(result: InventoryAnexoDResult) -> None:
    expected_issues = ("physical_closing_conflict",) if result.closing_conflict is not None else ()
    if result.issues != expected_issues:
        raise InventoryValidationError("inventory projection issues must exactly reflect retained conflicts")


def _expected_anexo_d_source_values(result: InventoryAnexoDResult) -> Any:
    from .valuation import derive_inventory_anexo_d_values

    try:
        return derive_inventory_anexo_d_values(result.source_ledger)
    except InventoryLedgerError as exc:
        raise InventoryValidationError("inventory projection retained source is invalid") from exc


def _validate_anexo_d_source_values(result: InventoryAnexoDResult, expected_source_values: Any) -> None:
    for field in dataclass_fields(expected_source_values):
        field_name = field.name
        expected_value = getattr(expected_source_values, field_name)
        if getattr(result, field_name) != expected_value:
            raise InventoryValidationError(
                f"inventory projection field {field_name!r} does not match retained source authority",
            )


def _validate_anexo_d_projection_fingerprint(result: InventoryAnexoDResult) -> None:
    if result.projection_fingerprint != result.expected_projection_fingerprint:
        raise InventoryValidationError("inventory projection fingerprint does not match projection state")


class InventoryAnexoDResult(BaseModel):
    """Complete source-owned inventory projection for one activity."""

    model_config = _STRICT_FROZEN_CONFIG

    source_ledger: InventoryLedger = Field(exclude=True, repr=False)
    source_ledger_fingerprint: ContentDigest
    actividad_id: str = Field(min_length=1)
    filing_year: FilingYear
    opening_value: Decimal = Field(ge=MONEY_ZERO)
    movement_derived_closing_value: Decimal = Field(ge=MONEY_ZERO)
    authoritative_closing_value: Decimal = Field(ge=MONEY_ZERO)
    selected_authority: InventoryClosingAuthority
    authority_record_fingerprint: ContentDigest
    decision_id: str = Field(min_length=1, max_length=128)
    decision_fingerprint: ContentDigest
    physical_observation_id: str | None = Field(default=None, min_length=1, max_length=128)
    physical_observation_fingerprint: ContentDigest | None = None
    physical_observed_closing_value: Decimal | None = Field(default=None, ge=MONEY_ZERO)
    prior_closing_link_fingerprint: ContentDigest
    complete_acquisition_total: Decimal = Field(ge=MONEY_ZERO)
    acquisition_fingerprints: tuple[ContentDigest, ...]
    variation_increase_value: Decimal = Field(ge=MONEY_ZERO)
    variation_decrease_value: Decimal = Field(ge=MONEY_ZERO)
    closing_conflict: InventoryClosingConflictDiagnostic | None = None
    issues: tuple[Literal["physical_closing_conflict"], ...] = ()
    projection_fingerprint: ContentDigest

    @property
    def expected_projection_fingerprint(self) -> ContentDigest:
        """Derive the versioned identity of the complete projection envelope."""
        return _content_hash_hex(
            {
                "fingerprint_schema_version": "1",
                "projection": self.model_dump(mode="json", exclude={"projection_fingerprint"}),
            },
        )

    @model_validator(mode="after")
    def _variation_split_matches_audited_values(self) -> InventoryAnexoDResult:
        """Require an exact, mutually exclusive split of the audited basis."""
        _validate_anexo_d_quantised_values(self)
        _validate_anexo_d_variation_split(self)
        _validate_anexo_d_acquisition_values(self)
        has_physical = _validate_anexo_d_physical_state(self)
        _validate_anexo_d_authority_selection(self, has_physical)
        _validate_anexo_d_conflict(self, has_physical)
        _validate_anexo_d_issues(self)
        expected_source_values = _expected_anexo_d_source_values(self)
        _validate_anexo_d_source_values(self, expected_source_values)
        _validate_anexo_d_projection_fingerprint(self)
        return self


def resolve_inventory_authoritative_closing(
    ledger: InventoryLedger,
    *,
    decision: InventoryClosingAuthorityDecision,
    physical_observation: PhysicalClosingObservation | None,
    prior_closing_link: PriorAuthoritativeClosingLink | None,
) -> InventoryClosingResolution:
    """Resolve closing authority while retaining any physical/movement conflict."""
    _resolve_anexo_d_registry_declarations(filing_year=int(ledger.year))
    _validate_closing_decision_coordinate(ledger, decision)
    derived = _derive_inventory_closing_value(ledger)
    prior_closing_link = _require_prior_closing_continuity(ledger, prior_closing_link)
    _validate_decision_physical_presence(decision, physical_observation)
    if physical_observation is None:
        return _movement_closing_resolution(ledger, decision, derived, prior_closing_link)
    _validate_physical_closing_observation(ledger, decision, physical_observation)
    return _physical_closing_resolution(
        ledger,
        decision,
        physical_observation,
        prior_closing_link,
        derived,
    )


def _validate_closing_decision_coordinate(
    ledger: InventoryLedger,
    decision: InventoryClosingAuthorityDecision,
) -> None:
    if decision.actividad_id != ledger.actividad_id or decision.filing_year != ledger.year:
        raise InventoryValidationError("closing authority decision does not match the inventory ledger coordinate")


def _derive_inventory_closing_value(ledger: InventoryLedger) -> Decimal:
    from .valuation import compute_inventory_valuation

    return compute_inventory_valuation(ledger).closing_value


def _require_prior_closing_continuity(
    ledger: InventoryLedger,
    prior_closing_link: PriorAuthoritativeClosingLink | None,
) -> PriorAuthoritativeClosingLink:
    if prior_closing_link is None:
        raise InventoryValidationError("closing authority requires complete prior-closing continuity")
    if (
        prior_closing_link.actividad_id != ledger.actividad_id
        or prior_closing_link.current_filing_year != ledger.year
        or prior_closing_link.current_opening_value != _quantize(ledger.opening_stock)
    ):
        raise InventoryValidationError(
            "prior closing continuity does not match the inventory ledger coordinate and opening",
        )
    return prior_closing_link


def _validate_decision_physical_presence(
    decision: InventoryClosingAuthorityDecision,
    physical_observation: PhysicalClosingObservation | None,
) -> None:
    decision_names_physical = decision.physical_observation_id is not None
    if decision_names_physical != (physical_observation is not None):
        raise InventoryValidationError("closing decision and competing physical observation must travel together")


def _movement_closing_resolution(
    ledger: InventoryLedger,
    decision: InventoryClosingAuthorityDecision,
    derived: Decimal,
    prior_closing_link: PriorAuthoritativeClosingLink,
) -> InventoryClosingResolution:
    return InventoryClosingResolution(
        actividad_id=ledger.actividad_id,
        filing_year=ledger.year,
        authority=decision.authority,
        authoritative_value=derived,
        movement_derived_value=derived,
        decision_id=decision.decision_id,
        decision_fingerprint=decision.fingerprint,
        prior_closing_link_fingerprint=prior_closing_link.fingerprint,
    )


def _validate_physical_closing_observation(
    ledger: InventoryLedger,
    decision: InventoryClosingAuthorityDecision,
    physical_observation: PhysicalClosingObservation,
) -> None:
    if decision.physical_observation_id != physical_observation.observation_id:
        raise InventoryValidationError("closing authority decision names a different physical observation")
    if decision.physical_observation_fingerprint != physical_observation.fingerprint:
        raise InventoryValidationError("closing authority decision fingerprint does not match physical observation")
    if decision.decided_at.date() < physical_observation.observed_on:
        raise InventoryValidationError("closing authority decision cannot predate the physical observation")
    if physical_observation.actividad_id != ledger.actividad_id or physical_observation.filing_year != ledger.year:
        raise InventoryValidationError("physical closing observation does not match the inventory ledger coordinate")
    expected_basis = {
        ValuationMethod.FIFO: InventoryClosingValuationBasis.FIFO_ACQUISITION_PRICE,
        ValuationMethod.PMP: InventoryClosingValuationBasis.PMP_ACQUISITION_PRICE,
        ValuationMethod.COSTE_MEDIO: InventoryClosingValuationBasis.COSTE_MEDIO_ACQUISITION_PRICE,
    }[ledger.valuation_method]
    if physical_observation.valuation_basis is not expected_basis:
        raise InventoryValidationError("physical closing valuation basis does not match the ledger valuation method")


def _physical_closing_resolution(
    ledger: InventoryLedger,
    decision: InventoryClosingAuthorityDecision,
    physical_observation: PhysicalClosingObservation,
    prior_closing_link: PriorAuthoritativeClosingLink,
    derived: Decimal,
) -> InventoryClosingResolution:
    observed = physical_observation.closing_value
    conflict = _closing_conflict_diagnostic(ledger, physical_observation, derived)
    return InventoryClosingResolution(
        actividad_id=ledger.actividad_id,
        filing_year=ledger.year,
        authority=decision.authority,
        authoritative_value=(
            observed if decision.authority is InventoryClosingAuthority.PHYSICAL_OBSERVATION else derived
        ),
        movement_derived_value=derived,
        physical_observed_value=observed,
        physical_observation_fingerprint=physical_observation.fingerprint,
        decision_id=decision.decision_id,
        decision_fingerprint=decision.fingerprint,
        physical_observation_id=physical_observation.observation_id,
        prior_closing_link_fingerprint=prior_closing_link.fingerprint,
        conflict=conflict,
    )


def _closing_conflict_diagnostic(
    ledger: InventoryLedger,
    physical_observation: PhysicalClosingObservation,
    derived: Decimal,
) -> InventoryClosingConflictDiagnostic | None:
    observed = physical_observation.closing_value
    if observed == derived:
        return None
    return InventoryClosingConflictDiagnostic(
        actividad_id=ledger.actividad_id,
        filing_year=ledger.year,
        movement_derived_value=derived,
        physical_observed_value=observed,
        physical_observation_fingerprint=physical_observation.fingerprint,
    )

"""Read a destination rate change from the published fact, so tests follow the registry."""

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from itertools import pairwise

from ....core.period import Period
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.facts.payloads import MappingFactPayload
from ....domain.calculations.registry.facts.variants import GovernedFactVariant
from ....domain.iva.rates import IVA_RATE_FACT_ID


@dataclass(frozen=True)
class RateChange:
    member_state: str
    last_day_before: date
    first_day_after: date
    pct_before: Decimal
    pct_after: Decimal

    @property
    def period(self) -> Period:
        return exterior_period(self.first_day_after)


def exterior_period(on_date: date) -> Period:
    return Period.from_year_and_code(on_date.year, f"EXT-{(on_date.month - 1) // 3 + 1}T")


def ordinary_general_variants(operation: PinnedAuthorityOperation) -> dict[str, list[GovernedFactVariant]]:
    variants: dict[str, list[GovernedFactVariant]] = {}
    for variant in operation.governed_fact(IVA_RATE_FACT_ID).variants:
        selectors = {selector.name: selector.value for selector in variant.selectors}
        if selectors.get("kind") == "general" and selectors.get("rate_role") == "ordinary":
            variants.setdefault(str(selectors["member_state"]), []).append(variant)
    return variants


def variant_pct(variant: GovernedFactVariant) -> Decimal:
    assert isinstance(variant.payload, MappingFactPayload)
    return next(Decimal(str(entry.value)) for entry in variant.payload.entries if entry.key == "pct")


def rate_change_inside_a_quarter(operation: PinnedAuthorityOperation) -> RateChange:
    """Find a published change whose two boundary days fall in one exterior quarter."""
    for member_state, variants in sorted(ordinary_general_variants(operation).items()):
        by_start = sorted(variants, key=lambda item: item.valid_from or date.min)
        for before, after in pairwise(by_start):
            if before.valid_to is None or after.valid_from is None:
                continue
            if after.valid_from != before.valid_to + timedelta(days=1):
                continue
            if variant_pct(before) == variant_pct(after):
                continue
            if exterior_period(before.valid_to).registry_token == exterior_period(after.valid_from).registry_token:
                return RateChange(
                    member_state,
                    before.valid_to,
                    after.valid_from,
                    variant_pct(before),
                    variant_pct(after),
                )
    raise AssertionError("the published rate schedule declares no general-rate change inside a quarter")

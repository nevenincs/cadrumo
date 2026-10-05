"""Private parsers for the IVA component registry's shared vocabularies."""

from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import date
from typing import TYPE_CHECKING

from ...core.type_guards import is_str_keyed_dict
from ..calculations.registry.facts.resolution import MappingFactQuery, ResolvedMappingFact
from ..calculations.registry.schema_base import DateAxis
from ._fact_mapping_entries import mapping_entries
from .errors import IvaValidationError

if TYPE_CHECKING:
    from ..calculations.registry.governed_fact_scope import GovernedFactSource
    from .components import (
        IvaComponentVocabulary,
        IvaCuotaSettlement,
        IvaCuotaSettlementCatalogue,
        IvaCuotaSettlementDefinition,
    )

CATEGORY_PROJECTION_NAMES = frozenset(
    {
        "cuota_less_m303",
        "m303_base_out_of_scope",
        "evidence_exempt",
        "no_printed_tax",
        "cash_accounting_excluded",
    },
)

_CUOTA_SETTLEMENT_ORDER_KEY = "cuota_settlement.order"
_CUOTA_SETTLEMENT_NO_SETTLEMENT_KEY = "cuota_settlement.no_settlement"
_CUOTA_SETTLEMENT_PREFIX = "cuota_settlement."
_COMPONENT_PRESENCE_ORDER_KEY = "component_presence.order"
_RETENCION_EXPECTATION_ORDER_KEY = "retencion_expectation.order"
_RETENCION_ROLE_ORDER_KEY = "retencion_role.order"
_KIND_APPLICABILITY_ORDER_KEY = "kind_applicability.order"


def resolve_component_catalogue_entries(
    *,
    effective_date: date,
    authority: GovernedFactSource,
) -> dict[str, str]:
    """Resolve and type-check the raw 0084 mapping entries once."""
    resolved = authority.resolve_governed_fact(
        MappingFactQuery(
            fact_id="iva-category-component-catalogue",
            date_axis=DateAxis.FILING_PERIOD,
            effective_date=effective_date,
        ),
    )
    if not isinstance(resolved, ResolvedMappingFact):
        raise IvaValidationError("IVA component catalogue must resolve as a mapping fact")

    return dict(mapping_entries(resolved, subject="IVA component mapping"))


def cuota_settlement_catalogue_from_entries(
    entries: Mapping[str, str],
) -> IvaCuotaSettlementCatalogue:
    """Project the explicit cuota-settlement membership in fact 0084."""
    from .components import IvaCuotaSettlement, IvaCuotaSettlementCatalogue

    raw_tokens = _ordered_cuota_settlement_tokens(entries)
    no_settlement_token = _no_settlement_token(entries, IvaCuotaSettlement)
    definitions = tuple(_cuota_settlement_definition(entries, raw_token) for raw_token in raw_tokens)
    catalogue = IvaCuotaSettlementCatalogue(
        definitions=definitions,
        no_settlement_token=no_settlement_token,
    )
    _require_no_settlement_membership(no_settlement_token, catalogue)
    return catalogue


def _ordered_cuota_settlement_tokens(entries: Mapping[str, str]) -> tuple[str, ...]:
    order_text = entries.get(_CUOTA_SETTLEMENT_ORDER_KEY)
    if order_text is None or not order_text.strip():
        raise IvaValidationError(
            f"IVA component mapping is missing {_CUOTA_SETTLEMENT_ORDER_KEY!r}",
        )
    raw_tokens = tuple(token.strip() for token in order_text.split(",") if token.strip())
    if not raw_tokens or len(set(raw_tokens)) != len(raw_tokens):
        raise IvaValidationError("IVA cuota-settlement membership must contain unique non-empty tokens")
    return raw_tokens


def _no_settlement_token(
    entries: Mapping[str, str],
    token_type: type[IvaCuotaSettlement],
) -> IvaCuotaSettlement:
    no_settlement_value = entries.get(_CUOTA_SETTLEMENT_NO_SETTLEMENT_KEY)
    if no_settlement_value is None or not no_settlement_value.strip():
        raise IvaValidationError(
            f"IVA component mapping is missing {_CUOTA_SETTLEMENT_NO_SETTLEMENT_KEY!r}",
        )
    return token_type(no_settlement_value.strip())


def _cuota_settlement_definition(
    entries: Mapping[str, str],
    raw_token: str,
) -> IvaCuotaSettlementDefinition:
    from .components import IvaCuotaSettlement, IvaCuotaSettlementDefinition

    token = IvaCuotaSettlement(raw_token)
    prefix = f"{_CUOTA_SETTLEMENT_PREFIX}{raw_token}"
    declared_value = entries.get(f"{prefix}.value")
    if declared_value is None or not declared_value.strip():
        raise IvaValidationError(f"IVA component mapping is missing {prefix + '.value'!r}")
    if declared_value.strip() != raw_token:
        raise IvaValidationError(
            f"IVA cuota-settlement token {raw_token!r} declares mismatched value {declared_value!r}",
        )
    description = entries.get(f"{prefix}.description")
    legal_ref = entries.get(f"{prefix}.legal_ref")
    if description is None or not description.strip() or legal_ref is None or not legal_ref.strip():
        raise IvaValidationError(f"IVA component mapping is missing semantics for {raw_token!r}")
    return IvaCuotaSettlementDefinition(
        token=token,
        description=description.strip(),
        legal_ref=legal_ref.strip(),
    )


def _require_no_settlement_membership(
    no_settlement_token: IvaCuotaSettlement,
    catalogue: IvaCuotaSettlementCatalogue,
) -> None:
    if no_settlement_token not in catalogue.all_settlements:
        raise IvaValidationError(
            "IVA component mapping no-settlement token is not declared in cuota-settlement order",
        )


def ordered_component_rows(entries: Mapping[str, str]) -> tuple[str, ...]:
    """Return the validated row-key order declared by fact 0084."""
    order_text = entries.get("catalogue_order")
    if order_text is None or not order_text.strip():
        raise IvaValidationError("IVA component mapping is missing 'catalogue_order'")
    ordered_keys = tuple(token.strip() for token in order_text.split(",") if token.strip())
    if len(set(ordered_keys)) != len(ordered_keys):
        raise IvaValidationError("IVA component catalogue order contains duplicate rows")
    return ordered_keys


def component_vocabulary_from_entries(entries: Mapping[str, str]) -> IvaComponentVocabulary:
    """Project the four explicit component-axis memberships from fact 0084."""
    from .components import (
        IvaComponentPresence,
        IvaComponentVocabulary,
        IvaKindApplicability,
        IvaRetencionExpectation,
        IvaRetencionRole,
        component_axis_membership,
    )

    observed: dict[str, set[str]] = {
        "applicability": set(),
        "retencion_role": set(),
        "base": set(),
        "cuota": set(),
        "recargo": set(),
        "retencion": set(),
    }
    for row_key in ordered_component_rows(entries):
        raw_row = entries.get(f"row.{row_key}")
        if raw_row is None:
            raise IvaValidationError(f"IVA component mapping is missing row {row_key!r}")
        try:
            decoded: object = json.loads(raw_row)
        except json.JSONDecodeError as exc:
            raise IvaValidationError(f"IVA component row {row_key!r} is not valid JSON") from exc
        if not is_str_keyed_dict(decoded):
            raise IvaValidationError(f"IVA component row {row_key!r} must decode as an object")
        for field in observed:
            value = decoded.get(field)
            if not isinstance(value, str) or not value.strip():
                raise IvaValidationError(f"IVA component row {row_key!r} is missing {field!r}")
            observed[field].add(value.strip())
    return IvaComponentVocabulary(
        component_presence=frozenset(
            component_axis_membership(
                entries,
                key=_COMPONENT_PRESENCE_ORDER_KEY,
                token_type=IvaComponentPresence,
                observed=observed["base"] | observed["cuota"] | observed["recargo"],
                label="IVA component-presence",
            ),
        ),
        retencion_expectation=frozenset(
            component_axis_membership(
                entries,
                key=_RETENCION_EXPECTATION_ORDER_KEY,
                token_type=IvaRetencionExpectation,
                observed=observed["retencion"],
                label="IVA retención-expectation",
            ),
        ),
        retencion_role=frozenset(
            component_axis_membership(
                entries,
                key=_RETENCION_ROLE_ORDER_KEY,
                token_type=IvaRetencionRole,
                observed=observed["retencion_role"],
                label="IVA retención-role",
            ),
        ),
        kind_applicability=frozenset(
            component_axis_membership(
                entries,
                key=_KIND_APPLICABILITY_ORDER_KEY,
                token_type=IvaKindApplicability,
                observed=observed["applicability"],
                label="IVA kind-applicability",
            ),
        ),
    )

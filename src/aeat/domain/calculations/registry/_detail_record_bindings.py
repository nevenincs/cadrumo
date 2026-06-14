"""Detail-record row-set registry binding helpers."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from ....core import STRICT_FROZEN_CONFIG
from ....core.aggregation import RowSetGroupingKind
from ....core.external_constants import DEFAULT_CURRENCY
from ._binding_selector_utils import uppercase_alpha_code
from ._errors import RegistryValidationError
from ._schema import DataBindingDefinition, ModeloRevision

__all__ = [
    "AtributionMemberObservation",
    "Modelo720RowObservation",
    "RefundOperationObservation",
    "RelatedPartyOperationObservation",
    "resolve_atribucion_binding_row_values",
    "resolve_foreign_asset_binding_row_values",
    "resolve_refund_binding_row_values",
    "resolve_related_party_binding_row_values",
]

# Related-party operation source bindings (modelo 232).
#
# Legal authority: LIS art. 18 (operaciones vinculadas), RD 634/2015
# art. 13 (informe-país-por-país y declaración modelo 232), Orden
# HFP/816/2017 Anexo (diseno de registro modelo 232).
# ---------------------------------------------------------------------------


_RelatedPartyRowField = Literal[
    "counterparty_tax_id",
    "counterparty_legal_name",
    "country_code",
    "operation_kind_code",
    "transfer_pricing_method_code",
    "amount",
]


class RelatedPartyOperationObservation(BaseModel):
    """One related-party operation for modelo 232."""

    model_config = STRICT_FROZEN_CONFIG

    source_id: str = Field(min_length=1, max_length=128)
    counterparty_tax_id: str = Field(min_length=1, max_length=64)
    counterparty_legal_name: str = Field(default="", max_length=200)
    country_code: str = Field(default="ES", min_length=2, max_length=2)
    transaction_date: date
    operation_kind_code: str = Field(min_length=1, max_length=4)
    transfer_pricing_method_code: str = Field(default="", max_length=4)
    amount: Decimal

    _country_code_uppercase = field_validator("country_code")(uppercase_alpha_code("country_code"))

    @field_validator("amount")
    @classmethod
    def _decimal_amount(cls, value: Decimal) -> Decimal:
        if isinstance(value, bool) or not isinstance(value, Decimal):
            raise RegistryValidationError("related-party amount must be Decimal")
        return value


class _RelatedPartySelector(BaseModel):
    model_config = STRICT_FROZEN_CONFIG

    # Only ``row_field`` is a legal fact for related-party-operation
    # bindings; every handler raises on anything else. Promoting to a
    # Literal at the type level mirrors the runtime check at the
    # snapshot-build gate. Audit selector-drift F2.
    fact: Literal["row_field"]
    row_field: _RelatedPartyRowField | None = None
    grouping: str | None = Field(default=None, min_length=1, max_length=64)
    record: str | None = Field(default=None, min_length=1, max_length=64)


def _validated_related_party_selector(binding: DataBindingDefinition) -> _RelatedPartySelector:
    try:
        selector = _RelatedPartySelector.model_validate(binding.selector)
    except ValueError as exc:
        raise RegistryValidationError(f"binding {binding.id!r} has malformed related-party selector") from exc
    if selector.fact != "row_field":
        raise RegistryValidationError(
            f"binding {binding.id!r} declares unsupported related-party fact {selector.fact!r}",
        )
    op = str((binding.aggregation or {}).get("op", "rows"))
    if op != "rows":
        raise RegistryValidationError(f"binding {binding.id!r} fact 'row_field' requires aggregation op 'rows'")
    if selector.row_field is None:
        raise RegistryValidationError(f"binding {binding.id!r} fact 'row_field' requires a 'row_field' selector key")
    return selector


def resolve_related_party_binding_row_values(
    revision: ModeloRevision,
    observations: Iterable[RelatedPartyOperationObservation],
) -> dict[tuple[str, int], Decimal | str]:
    """Resolve row-producer related-party bindings into per-row indexed values.

    Args:
        revision: The :class:`ModeloRevision` whose related-party bindings to resolve.
        observations: Typed :class:`RelatedPartyOperationObservation` rows the
            row-producer bindings group into per-row indexed values.
    """
    available = tuple(observations)
    members: list[tuple[DataBindingDefinition, _RelatedPartySelector]] = []
    for binding in revision.bindings:
        if binding.source != "related_party_operation":
            continue
        selector = _validated_related_party_selector(binding)
        members.append((binding, selector))
    if not members:
        return {}
    rows = _build_related_party_rows(available)
    resolved: dict[tuple[str, int], Decimal | str] = {}
    for binding, selector in members:
        assert selector.row_field is not None
        for row_index, row in enumerate(rows, start=1):
            value = row.get(selector.row_field)
            if value is None:
                raise RegistryValidationError(
                    f"binding {binding.id!r} row_field {selector.row_field!r} not produced for related-party rows",
                )
            resolved[(binding.id, row_index)] = value
    return resolved


def _build_related_party_rows(
    observations: tuple[RelatedPartyOperationObservation, ...],
) -> tuple[Mapping[str, Decimal | str], ...]:
    """Group related-party observations by (party, country, kind, method) summing amounts."""
    accum: dict[tuple[str, str, str, str], dict[str, Decimal | str]] = {}
    for obs in observations:
        key = (obs.country_code, obs.counterparty_tax_id, obs.operation_kind_code, obs.transfer_pricing_method_code)
        bucket = accum.setdefault(
            key,
            {
                "country_code": obs.country_code,
                "counterparty_tax_id": obs.counterparty_tax_id,
                "counterparty_legal_name": obs.counterparty_legal_name,
                "operation_kind_code": obs.operation_kind_code,
                "transfer_pricing_method_code": obs.transfer_pricing_method_code,
                "amount": Decimal("0"),
            },
        )
        prev = bucket["amount"]
        assert isinstance(prev, Decimal)
        bucket["amount"] = prev + obs.amount
    return tuple(accum[key] for key in sorted(accum.keys()))


# ---------------------------------------------------------------------------
# Foreign asset source bindings (modelo 720).
#
# Legal authority: RD 1065/2007 arts. 42 bis / 42 ter, Orden HAP/72/2013
# Anexo (modelo 720 diseno de registro). Threshold: 50,000 EUR per asset
# class (already encoded as a parameter on modelo 720).
# ---------------------------------------------------------------------------


_ForeignAssetRowField = Literal[
    "asset_class_code",
    "country_code",
    "currency_code",
    "asset_identifier",
    "valuation_amount",
    "acquisition_date",
]


class Modelo720RowObservation(BaseModel):
    """One foreign asset for modelo 720."""

    model_config = STRICT_FROZEN_CONFIG

    source_id: str = Field(min_length=1, max_length=128)
    asset_class_code: str = Field(min_length=1, max_length=4)
    country_code: str = Field(min_length=2, max_length=2)
    currency_code: str = Field(default=DEFAULT_CURRENCY, min_length=3, max_length=3)
    asset_identifier: str = Field(default="", max_length=128)
    acquisition_date: date
    valuation_amount: Decimal

    _iso_code_uppercase = field_validator("country_code", "currency_code")(uppercase_alpha_code("ISO code"))

    @field_validator("valuation_amount")
    @classmethod
    def _decimal_amount(cls, value: Decimal) -> Decimal:
        if isinstance(value, bool) or not isinstance(value, Decimal):
            raise RegistryValidationError("foreign asset valuation must be Decimal")
        if value < Decimal("0"):
            raise RegistryValidationError("foreign asset valuation must be non-negative")
        return value


class _ForeignAssetSelector(BaseModel):
    model_config = STRICT_FROZEN_CONFIG

    fact: Literal["row_field"]
    row_field: _ForeignAssetRowField | None = None
    asset_classes: tuple[str, ...] = ()
    grouping: str | None = Field(default=None, min_length=1, max_length=64)
    record: str | None = Field(default=None, min_length=1, max_length=64)


def _validated_foreign_asset_selector(binding: DataBindingDefinition) -> _ForeignAssetSelector:
    try:
        selector = _ForeignAssetSelector.model_validate(binding.selector)
    except ValueError as exc:
        raise RegistryValidationError(f"binding {binding.id!r} has malformed foreign-asset selector") from exc
    if selector.fact != "row_field":
        raise RegistryValidationError(
            f"binding {binding.id!r} declares unsupported foreign-asset fact {selector.fact!r}",
        )
    op = str((binding.aggregation or {}).get("op", "rows"))
    if op != "rows":
        raise RegistryValidationError(f"binding {binding.id!r} fact 'row_field' requires aggregation op 'rows'")
    if selector.row_field is None:
        raise RegistryValidationError(f"binding {binding.id!r} fact 'row_field' requires a 'row_field' selector key")
    return selector


def resolve_foreign_asset_binding_row_values(
    revision: ModeloRevision,
    observations: Iterable[Modelo720RowObservation],
) -> dict[tuple[str, int], Decimal | str]:
    """Resolve row-producer foreign-asset bindings into per-row indexed values.

    Args:
        revision: The :class:`ModeloRevision` whose foreign-asset bindings are resolved.
        observations: Modelo 720 row observations to group into rows.
    """
    available = tuple(observations)
    members: list[tuple[DataBindingDefinition, _ForeignAssetSelector]] = []
    cohort_classes: set[tuple[str, ...]] = set()
    for binding in revision.bindings:
        if binding.source != RowSetGroupingKind.FOREIGN_ASSET:
            continue
        selector = _validated_foreign_asset_selector(binding)
        members.append((binding, selector))
        cohort_classes.add(tuple(sorted(selector.asset_classes)))
    if not members:
        return {}
    # All bindings in a cohort share the same asset_classes filter.
    sample_classes = next(iter(cohort_classes)) if cohort_classes else ()
    class_filter = set(sample_classes)
    filtered = tuple(obs for obs in available if not class_filter or obs.asset_class_code in class_filter)
    rows = _build_foreign_asset_rows(filtered)
    resolved: dict[tuple[str, int], Decimal | str] = {}
    for binding, selector in members:
        assert selector.row_field is not None
        for row_index, row in enumerate(rows, start=1):
            value = row.get(selector.row_field)
            if value is None:
                raise RegistryValidationError(
                    f"binding {binding.id!r} row_field {selector.row_field!r} not produced for foreign-asset rows",
                )
            resolved[(binding.id, row_index)] = value
    return resolved


def _build_foreign_asset_rows(
    observations: tuple[Modelo720RowObservation, ...],
) -> tuple[Mapping[str, Decimal | str], ...]:
    rows: list[Mapping[str, Decimal | str]] = []
    for obs in sorted(
        observations,
        key=lambda o: (o.country_code, o.asset_class_code, o.asset_identifier, o.acquisition_date.isoformat()),
    ):
        rows.append(
            {
                "asset_class_code": obs.asset_class_code,
                "country_code": obs.country_code,
                "currency_code": obs.currency_code,
                "asset_identifier": obs.asset_identifier,
                "valuation_amount": obs.valuation_amount,
                "acquisition_date": obs.acquisition_date.isoformat(),
            },
        )
    return tuple(rows)


# ---------------------------------------------------------------------------
# Atribución member source bindings (modelo 184).
#
# Legal authority: Ley 35/2006 LIRPF arts. 87-90 (régimen de atribución de
# rentas), Orden HFP/227/2017 Anexo (modelo 184 diseno de registro).
# ---------------------------------------------------------------------------


_AtributionRowField = Literal[
    "member_tax_id",
    "member_legal_name",
    "country_code",
    "share_percentage",
    "base_imponible_assigned",
]


class AtributionMemberObservation(BaseModel):
    """One atribución member for modelo 184."""

    model_config = STRICT_FROZEN_CONFIG

    source_id: str = Field(min_length=1, max_length=128)
    member_tax_id: str = Field(min_length=1, max_length=64)
    member_legal_name: str = Field(default="", max_length=200)
    country_code: str = Field(default="ES", min_length=2, max_length=2)
    transaction_date: date
    share_percentage: Decimal
    base_imponible_assigned: Decimal

    _country_code_uppercase = field_validator("country_code")(uppercase_alpha_code("country_code"))

    @field_validator("share_percentage")
    @classmethod
    def _share_within_bounds(cls, value: Decimal) -> Decimal:
        if isinstance(value, bool) or not isinstance(value, Decimal):
            raise RegistryValidationError("share_percentage must be Decimal")
        if value < Decimal("0") or value > Decimal("100"):
            raise RegistryValidationError("share_percentage must be within [0, 100]")
        return value

    @field_validator("base_imponible_assigned")
    @classmethod
    def _decimal_amount(cls, value: Decimal) -> Decimal:
        if isinstance(value, bool) or not isinstance(value, Decimal):
            raise RegistryValidationError("base_imponible_assigned must be Decimal")
        return value


class _AtributionSelector(BaseModel):
    model_config = STRICT_FROZEN_CONFIG

    fact: Literal["row_field"]
    row_field: _AtributionRowField | None = None
    grouping: str | None = Field(default=None, min_length=1, max_length=64)
    record: str | None = Field(default=None, min_length=1, max_length=64)


def _validated_atribucion_selector(binding: DataBindingDefinition) -> _AtributionSelector:
    try:
        selector = _AtributionSelector.model_validate(binding.selector)
    except ValueError as exc:
        raise RegistryValidationError(f"binding {binding.id!r} has malformed atribucion selector") from exc
    if selector.fact != "row_field":
        raise RegistryValidationError(f"binding {binding.id!r} declares unsupported atribucion fact {selector.fact!r}")
    op = str((binding.aggregation or {}).get("op", "rows"))
    if op != "rows":
        raise RegistryValidationError(f"binding {binding.id!r} fact 'row_field' requires aggregation op 'rows'")
    if selector.row_field is None:
        raise RegistryValidationError(f"binding {binding.id!r} fact 'row_field' requires a 'row_field' selector key")
    return selector


def resolve_atribucion_binding_row_values(
    revision: ModeloRevision,
    observations: Iterable[AtributionMemberObservation],
) -> dict[tuple[str, int], Decimal | str]:
    """Resolve row-producer atribucion bindings into per-row indexed values.

    Args:
        revision: The :class:`ModeloRevision` whose atribucion bindings are resolved.
        observations: Attribution member observations to group into rows.
    """
    available = tuple(observations)
    members: list[tuple[DataBindingDefinition, _AtributionSelector]] = []
    for binding in revision.bindings:
        if binding.source != "atribucion_member":
            continue
        selector = _validated_atribucion_selector(binding)
        members.append((binding, selector))
    if not members:
        return {}
    rows = tuple(
        {
            "member_tax_id": obs.member_tax_id,
            "member_legal_name": obs.member_legal_name,
            "country_code": obs.country_code,
            "share_percentage": obs.share_percentage,
            "base_imponible_assigned": obs.base_imponible_assigned,
        }
        for obs in sorted(available, key=lambda o: (o.country_code, o.member_tax_id))
    )
    resolved: dict[tuple[str, int], Decimal | str] = {}
    for binding, selector in members:
        assert selector.row_field is not None
        for row_index, row in enumerate(rows, start=1):
            value = row.get(selector.row_field)
            if value is None:
                raise RegistryValidationError(
                    f"binding {binding.id!r} row_field {selector.row_field!r} not produced for atribucion rows",
                )
            resolved[(binding.id, row_index)] = value
    return resolved


# ---------------------------------------------------------------------------
# Refund operation source bindings (modelo 360).
#
# Legal authority: Ley 37/1992 art. 117 bis (devolucion 8a Directiva),
# Orden EHA/789/2010 Anexo (modelo 360 diseno de registro).
# ---------------------------------------------------------------------------


_RefundRowField = Literal[
    "member_state_code",
    "operation_kind_code",
    "operation_date",
    "supplier_tax_id",
    "refund_amount",
]


class RefundOperationObservation(BaseModel):
    """One foreign-MS refund operation for modelo 360."""

    model_config = STRICT_FROZEN_CONFIG

    source_id: str = Field(min_length=1, max_length=128)
    member_state_code: str = Field(min_length=2, max_length=2)
    operation_kind_code: str = Field(min_length=1, max_length=4)
    operation_date: date
    supplier_tax_id: str = Field(min_length=1, max_length=64)
    refund_amount: Decimal

    _iso_code_uppercase = field_validator("member_state_code")(uppercase_alpha_code("member_state_code"))

    @field_validator("refund_amount")
    @classmethod
    def _decimal_amount(cls, value: Decimal) -> Decimal:
        if isinstance(value, bool) or not isinstance(value, Decimal):
            raise RegistryValidationError("refund_amount must be Decimal")
        if value < Decimal("0"):
            raise RegistryValidationError("refund_amount must be non-negative")
        return value


class _RefundSelector(BaseModel):
    model_config = STRICT_FROZEN_CONFIG

    fact: Literal["row_field"]
    row_field: _RefundRowField | None = None
    grouping: str | None = Field(default=None, min_length=1, max_length=64)
    record: str | None = Field(default=None, min_length=1, max_length=64)


def _validated_refund_selector(binding: DataBindingDefinition) -> _RefundSelector:
    try:
        selector = _RefundSelector.model_validate(binding.selector)
    except ValueError as exc:
        raise RegistryValidationError(f"binding {binding.id!r} has malformed refund selector") from exc
    if selector.fact != "row_field":
        raise RegistryValidationError(f"binding {binding.id!r} declares unsupported refund fact {selector.fact!r}")
    op = str((binding.aggregation or {}).get("op", "rows"))
    if op != "rows":
        raise RegistryValidationError(f"binding {binding.id!r} fact 'row_field' requires aggregation op 'rows'")
    if selector.row_field is None:
        raise RegistryValidationError(f"binding {binding.id!r} fact 'row_field' requires a 'row_field' selector key")
    return selector


def resolve_refund_binding_row_values(
    revision: ModeloRevision,
    observations: Iterable[RefundOperationObservation],
) -> dict[tuple[str, int], Decimal | str]:
    """Resolve row-producer refund-operation bindings into per-row indexed values.

    Args:
        revision: The :class:`ModeloRevision` whose refund bindings are resolved.
        observations: Refund operation observations to group into rows.
    """
    available = tuple(observations)
    members: list[tuple[DataBindingDefinition, _RefundSelector]] = []
    for binding in revision.bindings:
        if binding.source != "refund_operation":
            continue
        selector = _validated_refund_selector(binding)
        members.append((binding, selector))
    if not members:
        return {}
    rows = tuple(
        {
            "member_state_code": obs.member_state_code,
            "operation_kind_code": obs.operation_kind_code,
            "operation_date": obs.operation_date.isoformat(),
            "supplier_tax_id": obs.supplier_tax_id,
            "refund_amount": obs.refund_amount,
        }
        for obs in sorted(
            available,
            key=lambda o: (o.member_state_code, o.operation_date.isoformat(), o.supplier_tax_id),
        )
    )
    resolved: dict[tuple[str, int], Decimal | str] = {}
    for binding, selector in members:
        assert selector.row_field is not None
        for row_index, row in enumerate(rows, start=1):
            value = row.get(selector.row_field)
            if value is None:
                raise RegistryValidationError(
                    f"binding {binding.id!r} row_field {selector.row_field!r} not produced for refund rows",
                )
            resolved[(binding.id, row_index)] = value
    return resolved

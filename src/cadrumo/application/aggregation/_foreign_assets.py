"""Modelo 720 foreign-assets aggregation and source-mesh resolver.

Modelo 720 is an informativa declaration for assets and rights abroad. This
module groups per-asset observations by ``(source_kind, asset_class)`` and
returns :class:`ForeignAssetsAggregation` for
:mod:`application.aggregation._service`; the repository-free
:class:`ForeignAssetsAggregationSourceResolver` adapts the same observations to
the calculation source-mesh envelope when a caller supplies them.

Declarability is per regulatory obligation block. The aggregate keeps raw class
rollups, and :func:`declarable_asset_classes_720` applies each block's threshold
to the sum of every present class in that block. Observation construction accepts
only the four canonical source-kind values ``ledger_transaction``,
``purchase_invoice_evidence``, ``payable_invoice``, and
``collectible_invoice``; bare ``invoice`` is rejected.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from decimal import Decimal
from typing import ClassVar

from pydantic import (
    BaseModel,
    Field,
    InstanceOf,
    NonNegativeInt,
    TypeAdapter,
    ValidationError,
    field_validator,
    model_validator,
)

from ...core.aggregation import BindingSourceKind, ForeignAssetClass
from ...core.country_code import CountryCodeAlpha2
from ...core.foreign_asset_obligation import (
    MODELO_720_FOREIGN_ASSET_CLASS_CODES,
    ForeignAssetObligationGroup,
    M720AssetClassCode,
    foreign_asset_obligation_group,
)
from ...core.hashing import content_hash_hex
from ...core.identity import TransactionId
from ...core.modelo import Modelo
from ...core.models import STRICT_FROZEN_CONFIG
from ...core.parsing import IsoDateString, require_iso8601_date
from ...core.period import Period
from ...domain.calculations.registry.binding_selector_utils import binding_row_set_selector
from ...domain.calculations.registry.detail_record_bindings import (
    Modelo720RowObservation,
    resolve_foreign_asset_binding_row_values,
)
from ...domain.calculations.row_source_identity import RowSourceIdentity
from .._foreign_asset_thresholds import (
    ForeignAssetDeclarationThreshold,
    foreign_asset_declaration_thresholds,
    foreign_asset_declaration_thresholds_for_revision,
)
from ._grouping import assert_rollup_totals_match, group_observations
from ._source_mesh import (
    CalculationSourceContext,
    CalculationSourceLineageRole,
    CalculationSourceProvenance,
    CalculationSourceResolution,
)

_CANONICAL_SOURCE_KINDS: frozenset[BindingSourceKind] = frozenset(
    {
        BindingSourceKind.LEDGER_TRANSACTION,
        BindingSourceKind.PURCHASE_INVOICE_EVIDENCE,
        BindingSourceKind.PAYABLE_INVOICE,
        BindingSourceKind.COLLECTIBLE_INVOICE,
    },
)
_OWNED_SOURCES: tuple[BindingSourceKind, ...] = (BindingSourceKind.FOREIGN_ASSET,)

# One reusable validator for the canonical ledger-transaction identity shape.
_TRANSACTION_ID_ADAPTER: TypeAdapter[TransactionId] = TypeAdapter(TransactionId)


def _foreign_asset_source_kind(value: object) -> BindingSourceKind:
    if isinstance(value, BindingSourceKind):
        source_kind = value
    elif isinstance(value, str):
        try:
            source_kind = BindingSourceKind(value)
        except ValueError as exc:
            raise ValueError(f"foreign asset source_kind {value!r} is not a BindingSourceKind") from exc
    else:
        raise ValueError("foreign asset source_kind must be a BindingSourceKind or source-kind string")
    if source_kind not in _CANONICAL_SOURCE_KINDS:
        allowed = ", ".join(kind.value for kind in _CANONICAL_SOURCE_KINDS)
        raise ValueError(
            f"unsupported source_kind {source_kind.value!r}; use one of {allowed}",
        )
    return source_kind


def _validate_country(value: str) -> str:
    if len(value) != 2 or any(char < "A" or char > "Z" for char in value):
        raise ValueError(f"country must be uppercase ISO-3166 alpha-2, got {value!r}")
    return value


class ForeignAssetIngestObservation(BaseModel):
    """One asset observation for a Modelo 720 aggregator pass.

    ``acquisition_date`` is admitted by the canonical date authority at
    ingestion, before aggregation. Bounding its length alone let an impossible
    calendar date through -- ``2026-99-99`` and ``2026-02-30`` are both ten
    characters -- so the aggregate totals, the declarability decision, and the
    operator's rollups were all computed from a row no date authority had ever
    approved, and the refusal only surfaced later at the registry adapter that
    finally parses it.
    """

    model_config = STRICT_FROZEN_CONFIG

    source_kind: BindingSourceKind
    source_object_id: str = Field(min_length=1)
    asset_class: ForeignAssetClass
    asset_external_id: str = Field(min_length=1, max_length=128)
    country: CountryCodeAlpha2
    issuer_or_institution: str = Field(default="", max_length=200)
    valuation_eur: Decimal = Field(ge=Decimal("0"))
    acquisition_date: IsoDateString = Field(min_length=10, max_length=10)
    held_at_year_end: bool = True

    @field_validator("source_kind", mode="before")
    @classmethod
    def _source_kind_is_canonical(cls, value: object) -> BindingSourceKind:
        return _foreign_asset_source_kind(value)

    @field_validator("country")
    @classmethod
    def _country_is_uppercase(cls, value: str) -> str:
        return _validate_country(value)

    @model_validator(mode="after")
    def _ledger_source_is_a_transaction_identity(self) -> ForeignAssetIngestObservation:
        """Hold a ledger-sourced observation to the canonical transaction identity.

        The resolver copies ``source_object_id`` verbatim into
        :attr:`CalculationSourceResolution.source_transaction_ids`, which feeds
        the strict hex-64 transaction-identity field on
        :class:`CalculationRevision`. Accepting any non-empty string here let a
        validly-ingested ledger observation reach calculation persistence with
        an id the revision contract can never satisfy, so the refusal surfaced
        at the persistence boundary with no way back to the row that caused it.

        Only the ledger source kind is constrained: an invoice- or
        evidence-sourced observation legitimately carries an external
        identifier, and that value rides in typed provenance, never in the
        transaction-identity tuple.
        """
        if self.source_kind is BindingSourceKind.LEDGER_TRANSACTION:
            try:
                _TRANSACTION_ID_ADAPTER.validate_python(self.source_object_id)
            except ValidationError as exc:
                raise ValueError(
                    f"source_object_id {self.source_object_id!r} is not a ledger transaction identity "
                    f"(expected 64 lowercase hex characters); an external identifier belongs in provenance",
                ) from exc
        return self


class ForeignAssetClassRollup(BaseModel):
    """Per-source-kind and per-asset-class rollup row."""

    model_config = STRICT_FROZEN_CONFIG

    source_kind: BindingSourceKind
    asset_class: ForeignAssetClass
    assets_count: NonNegativeInt
    held_at_year_end_count: NonNegativeInt
    total_valuation_eur: Decimal = Field(ge=Decimal("0"))
    countries: tuple[str, ...] = Field(default_factory=tuple)

    @field_validator("countries")
    @classmethod
    def _countries_are_uppercase_ascii_alpha2(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        for country in value:
            _validate_country(country)
        return value

    @field_validator("source_kind", mode="before")
    @classmethod
    def _source_kind_is_canonical(cls, value: object) -> BindingSourceKind:
        return _foreign_asset_source_kind(value)

    @model_validator(mode="after")
    def _held_count_within_total(self) -> ForeignAssetClassRollup:
        if self.held_at_year_end_count > self.assets_count:
            raise ValueError(
                f"held_at_year_end_count {self.held_at_year_end_count} > assets_count {self.assets_count}",
            )
        return self


class ForeignAssetsAggregation(BaseModel):
    """720 aggregation output: per-class rollups + cross-class totals."""

    model_config = STRICT_FROZEN_CONFIG

    modelo: str = Field(min_length=1)
    period: InstanceOf[Period]
    rollups: tuple[ForeignAssetClassRollup, ...] = Field(default_factory=tuple)
    total_assets: NonNegativeInt
    total_valuation_eur: Decimal = Field(ge=Decimal("0"))

    @model_validator(mode="after")
    def _totals_match_rollups(self) -> ForeignAssetsAggregation:
        assert_rollup_totals_match(
            self.rollups,
            checks=(
                ("total_assets", self.total_assets, lambda row: row.assets_count),
                ("total_valuation_eur", self.total_valuation_eur, lambda row: row.total_valuation_eur),
            ),
        )
        cohorts = [(row.source_kind, row.asset_class) for row in self.rollups]
        if len(cohorts) != len(set(cohorts)):
            raise ValueError("each source_kind and ForeignAssetClass cohort may appear at most once in rollups")
        return self


def declarable_asset_classes_720(
    aggregation: ForeignAssetsAggregation,
    *,
    thresholds: Mapping[ForeignAssetObligationGroup, ForeignAssetDeclarationThreshold] | None = None,
) -> frozenset[ForeignAssetClass]:
    """Return present asset classes whose obligation block exceeds its 720 declaration floor.

    Returns a frozenset of :class:`ForeignAssetClass` members.
    """
    resolved_thresholds = thresholds or foreign_asset_declaration_thresholds(
        modelo=Modelo.M720.value,
        filing_year=aggregation.period.filing_year,
    )
    group_totals: dict[ForeignAssetObligationGroup, Decimal] = {}
    asset_classes_by_group: dict[ForeignAssetObligationGroup, set[ForeignAssetClass]] = {}
    for rollup in aggregation.rollups:
        group = foreign_asset_obligation_group(rollup.asset_class)
        group_totals[group] = group_totals.get(group, Decimal("0")) + rollup.total_valuation_eur
        asset_classes_by_group.setdefault(group, set()).add(rollup.asset_class)
    unsupported_groups = set(group_totals) - set(resolved_thresholds)
    if unsupported_groups:
        classes = sorted(
            asset_class.value for group in unsupported_groups for asset_class in asset_classes_by_group[group]
        )
        raise ValueError(f"asset classes {classes!r}: not a Modelo 720 foreign-asset class")
    return frozenset(
        asset_class
        for group, total in group_totals.items()
        if total > resolved_thresholds[group].initial_declaration_floor_eur
        for asset_class in asset_classes_by_group[group]
    )


def declarable_class(
    aggregation: ForeignAssetsAggregation,
    *,
    asset_class: ForeignAssetClass,
    thresholds: Mapping[ForeignAssetObligationGroup, ForeignAssetDeclarationThreshold] | None = None,
) -> bool:
    """Return True iff an asset class's obligation block crosses the 720 declaration floor."""
    return asset_class in declarable_asset_classes_720(aggregation, thresholds=thresholds)


def aggregate_foreign_assets_720(
    observations: tuple[ForeignAssetIngestObservation, ...],
    *,
    period: Period,
) -> ForeignAssetsAggregation:
    """Aggregate Modelo 720 observations into per-class rollups.

    Returns a :class:`ForeignAssetsAggregation` grouping observations
    by asset class. Pure function: identical observation input + period
    yields identical output. Rollups are sorted by asset_class.value so
    two equal aggregations serialise to identical bytes.

    No threshold gate is applied here; callers use
    :func:`declarable_class` to filter rollups by obligation block before binding to
    Modelo 720 casillas.
    """
    grouped = group_observations(observations, group_key_fn=lambda obs: (obs.source_kind, obs.asset_class))
    rollups: list[ForeignAssetClassRollup] = []
    for source_kind, asset_class in sorted(grouped, key=lambda c: (c[0], c[1].value)):
        group = grouped[(source_kind, asset_class)]
        countries = tuple(sorted({obs.country for obs in group}))
        rollups.append(
            ForeignAssetClassRollup(
                source_kind=source_kind,
                asset_class=asset_class,
                assets_count=len(group),
                held_at_year_end_count=sum(1 for o in group if o.held_at_year_end),
                total_valuation_eur=sum(
                    (obs.valuation_eur for obs in group),
                    Decimal("0"),
                ),
                countries=countries,
            ),
        )
    return ForeignAssetsAggregation(
        modelo=Modelo.M720.value,
        period=period,
        rollups=tuple(rollups),
        total_assets=sum(row.assets_count for row in rollups),
        total_valuation_eur=sum(
            (row.total_valuation_eur for row in rollups),
            Decimal("0"),
        ),
    )


class ForeignAssetsAggregationSourceResolver:
    """Resolve Modelo 720 foreign-asset rows from operator-supplied observations.

    The resolver is deliberately repository-free, mirroring the existing
    ``aggregate_foreign_assets_720`` shape-C surface: callers supply typed
    observations, the resolver delegates to the aggregate function for threshold
    semantics, then validates the declarable rows against the live M720 registry
    row-producer bindings.
    """

    resolver_id: ClassVar[str] = "foreign_assets_aggregation"
    owned_sources: ClassVar[tuple[BindingSourceKind, ...]] = _OWNED_SOURCES

    def __init__(
        self,
        *,
        observations: Iterable[ForeignAssetIngestObservation] = (),
        row_observations: Iterable[Modelo720RowObservation] = (),
    ) -> None:
        self._observations = tuple(observations)
        self._row_observations = tuple(row_observations)

    def resolve(self, context: CalculationSourceContext) -> CalculationSourceResolution:
        if not _foreign_asset_source_for_revision(context):
            return CalculationSourceResolution(resolver_id=self.resolver_id, owned_sources=self.owned_sources)

        if self._row_observations:
            return _worksheet_row_resolution(context, self._row_observations)

        aggregation = aggregate_foreign_assets_720(self._observations, period=context.period)
        thresholds = foreign_asset_declaration_thresholds_for_revision(
            modelo=context.modelo,
            revision=context.revision,
            filing_date=context.period.end_date,
        )
        selected_observations = _selected_foreign_asset_observations(
            aggregation,
            self._observations,
            thresholds=thresholds,
        )
        row_observations = _registry_observations_from_foreign_assets_aggregation(
            aggregation,
            selected_observations,
            thresholds=thresholds,
        )
        row_binding_values = resolve_foreign_asset_binding_row_values(context.revision, row_observations)
        return CalculationSourceResolution(
            resolver_id=self.resolver_id,
            owned_sources=self.owned_sources,
            row_binding_values=row_binding_values,
            source_transaction_ids=tuple(
                sorted(
                    observation.source_object_id
                    for observation in selected_observations
                    if observation.source_kind is BindingSourceKind.LEDGER_TRANSACTION
                ),
            ),
            # M720 has no authoritative persisted identity for the resolved asset.
            # Upstream carrier ids cannot truthfully stand in for a primary node,
            # so this resolver remains grounding-blocked and emits no provenance.
            provenance=(),
        )


def _foreign_asset_source_for_revision(context: CalculationSourceContext) -> bool:
    return any(binding.source == BindingSourceKind.FOREIGN_ASSET for binding in context.revision.bindings)


def _registry_observations_from_foreign_assets_aggregation(
    aggregation: ForeignAssetsAggregation,
    observations: Iterable[ForeignAssetIngestObservation],
    *,
    thresholds: Mapping[ForeignAssetObligationGroup, ForeignAssetDeclarationThreshold] | None = None,
) -> tuple[Modelo720RowObservation, ...]:
    declarable_classes = declarable_asset_classes_720(aggregation, thresholds=thresholds)
    return tuple(
        _registry_observation_from_foreign_asset(observation)
        for observation in observations
        if observation.asset_class in declarable_classes
    )


def _selected_foreign_asset_observations(
    aggregation: ForeignAssetsAggregation,
    observations: Iterable[ForeignAssetIngestObservation],
    *,
    thresholds: Mapping[ForeignAssetObligationGroup, ForeignAssetDeclarationThreshold] | None = None,
) -> tuple[ForeignAssetIngestObservation, ...]:
    declarable_classes = declarable_asset_classes_720(aggregation, thresholds=thresholds)
    return tuple(observation for observation in observations if observation.asset_class in declarable_classes)


def _registry_observation_from_foreign_asset(
    observation: ForeignAssetIngestObservation,
) -> Modelo720RowObservation:
    # Already admitted by the same authority at observation construction; this
    # is the string -> date lift the registry row shape needs, not a second gate.
    acquisition_date = require_iso8601_date(observation.acquisition_date)
    return Modelo720RowObservation(
        source_id=f"{observation.source_kind.value}:{observation.source_object_id}",
        asset_class_code=_asset_class_code(observation.asset_class),
        country_code=observation.country,
        asset_identifier=observation.asset_external_id,
        acquisition_date=acquisition_date,
        valuation_amount=observation.valuation_eur,
    )


def _asset_class_code(asset_class: ForeignAssetClass) -> M720AssetClassCode:
    try:
        return MODELO_720_FOREIGN_ASSET_CLASS_CODES[asset_class]
    except KeyError as exc:
        raise ValueError(f"{asset_class.value!r} is not a Modelo 720 foreign-asset class") from exc


def _worksheet_row_resolution(
    context: CalculationSourceContext,
    observations: tuple[Modelo720RowObservation, ...],
) -> CalculationSourceResolution:
    """Carry worksheet rows through M720's established resolver.

    The row-set assembler has already validated these observations against the
    selected snapshot.  This resolver remains the sole M720 source-mesh owner;
    it only retains the row coordinates and opaque source evidence that the
    former aggregate-only handoff could not truthfully reconstruct.
    """
    row_binding_values = resolve_foreign_asset_binding_row_values(context.revision, observations)
    row_bindings = tuple(
        binding for binding in context.revision.bindings if binding.source is BindingSourceKind.FOREIGN_ASSET
    )
    groupings = {
        selector.grouping for binding in row_bindings if (selector := binding_row_set_selector(binding)) is not None
    }
    if len(groupings) != 1:
        raise ValueError("Modelo 720 foreign-asset row bindings must declare one row-set grouping")
    grouping = next(iter(groupings))
    ordered = tuple(
        sorted(
            observations,
            key=lambda row: (
                row.country_code,
                row.asset_class_code,
                row.asset_identifier,
                row.acquisition_date.isoformat(),
            ),
        )
    )
    row_source_identities = {
        (binding.id, row_index): RowSourceIdentity(
            source_kind=BindingSourceKind.FOREIGN_ASSET,
            source_row_identity=row.source_id,
            fingerprint=content_hash_hex(row.model_dump(mode="json")),
            row_set_grouping=grouping,
        )
        for row_index, row in enumerate(ordered, start=1)
        for binding in row_bindings
    }
    provenance = tuple(
        CalculationSourceProvenance(
            resolver_id=ForeignAssetsAggregationSourceResolver.resolver_id,
            resolved_binding_source=BindingSourceKind.FOREIGN_ASSET,
            contributor_source_kind=BindingSourceKind.FOREIGN_ASSET.value,
            contributor_binding_source=BindingSourceKind.FOREIGN_ASSET,
            lineage_role=CalculationSourceLineageRole.PRIMARY,
            source_ref=f"worksheet:{row.source_id}",
            parent_source_ref=None,
            fingerprint=content_hash_hex(row.model_dump(mode="json")),
        )
        for row in ordered
    )
    return CalculationSourceResolution(
        resolver_id=ForeignAssetsAggregationSourceResolver.resolver_id,
        owned_sources=ForeignAssetsAggregationSourceResolver.owned_sources,
        row_binding_values=row_binding_values,
        row_source_identities=row_source_identities,
        provenance=provenance,
    )


__all__ = [
    "ForeignAssetClass",
    "ForeignAssetClassRollup",
    "ForeignAssetIngestObservation",
    "ForeignAssetsAggregation",
    "ForeignAssetsAggregationSourceResolver",
    "aggregate_foreign_assets_720",
    "declarable_asset_classes_720",
    "declarable_class",
]

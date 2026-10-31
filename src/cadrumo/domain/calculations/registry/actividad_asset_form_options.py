"""Form option records and official names for activity-asset table classes."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from ...renta.actividad_asset.election import AmortizationMethod, DirectEstimationRegime
from ...renta.actividad_asset.lifecycle import AssetKind
from .actividad_asset_parameters import (
    ACTIVITY_ASSET_COEFFICIENT_IDS,
    ACTIVITY_ASSET_INTANGIBLE_CLASS_ID,
    ACTIVITY_ASSET_MATERIAL_CLASS_ID,
    ACTIVITY_ASSET_METHOD_ADMISSION_IDS,
    ACTIVITY_ASSET_PERIOD_IDS,
    ACTIVITY_ASSET_REFUSED_METHOD_LOCALE_KEYS,
    ActivityAssetParameters,
)
from .errors import RegistryValidationError
from .facts.string_mapping import MappingValueWhitespace, StringMappingFact, StringMappingPolicy
from .governed_fact_scope import GovernedFactSource
from .schema import ModeloRevision
from .schema_base import DateAxis


@dataclass(frozen=True, slots=True)
class ActivityAssetTableGroup:
    """One amortization table class with the corridor RIS art. 4.1 draws from it."""

    class_key: str
    maximum_coefficient: Decimal
    minimum_coefficient: Decimal
    maximum_period_years: Decimal
    class_label: str
    requires_vehicle_declaration: bool
    """Whether an asset of this class is charged only on a vehicle affectation declaration."""
    can_hold_vehicle: bool
    """Whether the registry classes a material asset of this class as one that can be a restricted vehicle.

    Such an asset is charged only on a vehicle affectation declaration; an asset of another class is
    never asked for one, and a declaration given there is still held to the same test.
    """


@dataclass(frozen=True, slots=True)
class ActivityAssetFormOptions:
    """What one Modelo 100 edition admits for an asset kind, modality and tax year.

    ``class_labels`` names every table class of the modality, not only the
    classes this asset kind admits, because an election keeps its class under a
    method the table does not bound.
    """

    methods: tuple[AmortizationMethod, ...]
    table_groups: tuple[ActivityAssetTableGroup, ...]
    class_labels: Mapping[str, str]


_CLASS_LABELS_FACT = StringMappingFact(
    fact_id="renta-actividad-inmovilizado-amortizacion-clase-denominacion",
    date_axis=DateAxis.FILING_PERIOD,
    policy=StringMappingPolicy(
        subject="activity-asset table class names", value_whitespace=MappingValueWhitespace.STRIP
    ),
)
_CLASS_LABEL_PREFIXES: dict[DirectEstimationRegime, str] = {
    DirectEstimationRegime.NORMAL: "normal.",
    DirectEstimationRegime.SIMPLIFIED: "simplificada.",
}


def resolve_activity_asset_class_labels(
    authority: GovernedFactSource,
    *,
    regime: DirectEstimationRegime,
    tax_year: int,
) -> Mapping[str, str]:
    """Read the official names of a modality's table classes for the end of a tax year.

    Returns:
        Each class key mapped to the name its legal table gives it.
    """
    prefix = _CLASS_LABEL_PREFIXES[regime]
    entries = _CLASS_LABELS_FACT.resolve_entries(authority, effective_date=date(tax_year, 12, 31))
    return {key.removeprefix(prefix): name for key, name in entries.items() if key.startswith(prefix)}


def activity_asset_form_options(
    modelo_revision: ModeloRevision,
    *,
    tax_year: int,
    asset_kind: AssetKind,
    regime: DirectEstimationRegime,
    class_labels: Mapping[str, str],
) -> ActivityAssetFormOptions:
    """Read a :class:`ModeloRevision`'s admitted methods and table groups from resolver parameters.

    Raises:
        RegistryValidationError: When an offered table class has no official name.
    """
    parameters = ActivityAssetParameters(
        by_id={parameter.id: parameter for parameter in modelo_revision.parameters},
        revision_id=modelo_revision.id,
        tax_year=tax_year,
    )
    # Inside the resolver a missing row is a refusal; for a form it only means "not offered".
    methods = tuple(
        method
        for method in AmortizationMethod
        if method not in ACTIVITY_ASSET_REFUSED_METHOD_LOCALE_KEYS
        and parameters.keyed(ACTIVITY_ASSET_METHOD_ADMISSION_IDS[regime], f"{asset_kind.value}:{method.value}")
        == Decimal("1")
    )
    groups = _form_table_groups(parameters, regime=regime, asset_kind=asset_kind, class_labels=class_labels)
    return ActivityAssetFormOptions(methods=methods, table_groups=groups, class_labels=class_labels)


def _form_table_groups(
    parameters: ActivityAssetParameters,
    *,
    regime: DirectEstimationRegime,
    asset_kind: AssetKind,
    class_labels: Mapping[str, str],
) -> tuple[ActivityAssetTableGroup, ...]:
    kind_parameter = (
        ACTIVITY_ASSET_INTANGIBLE_CLASS_ID if asset_kind is AssetKind.INTANGIBLE else ACTIVITY_ASSET_MATERIAL_CLASS_ID
    )
    groups: list[ActivityAssetTableGroup] = []
    class_keys = {entry.key for entry in parameters.require(ACTIVITY_ASSET_COEFFICIENT_IDS[regime]).keyed_brackets}
    for class_key in sorted(class_keys):
        maximum_percent = parameters.keyed(ACTIVITY_ASSET_COEFFICIENT_IDS[regime], class_key)
        period_years = parameters.keyed(ACTIVITY_ASSET_PERIOD_IDS[regime], class_key)
        if (
            maximum_percent is None
            or period_years is None
            or parameters.keyed(kind_parameter, class_key) != Decimal("1")
        ):
            continue
        requires_vehicle_declaration = parameters.requires_vehicle_declaration(asset_kind, class_key)
        class_label = class_labels.get(class_key)
        if class_label is None:
            raise RegistryValidationError(
                f"table class {class_key!r} has no official name for modality {regime.value!r}"
            )
        groups.append(
            ActivityAssetTableGroup(
                class_key=class_key,
                maximum_coefficient=maximum_percent / Decimal("100"),
                minimum_coefficient=Decimal("1") / period_years,
                maximum_period_years=period_years,
                class_label=class_label,
                can_hold_vehicle=requires_vehicle_declaration,
                requires_vehicle_declaration=requires_vehicle_declaration,
            ),
        )
    return tuple(groups)


__all__ = [
    "ActivityAssetFormOptions",
    "ActivityAssetTableGroup",
    "activity_asset_form_options",
    "resolve_activity_asset_class_labels",
]

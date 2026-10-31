"""Backend vocabulary the desktop Assets tab words, derived from the backend itself.

The tab draws tokens and catalogue keys that the activity-asset operations serve:
the members of the operations' closed enums, and the refusal and absence reasons
they state as ``ledger.actividad_asset.errors.*`` keys with the facts to fill
in. The words live once, in the canonical catalogues, under
``ledger.actividad_asset.<family>.<token>``. Nothing here holds a word or a
hand-kept member list: each family reads its members from the enum the
operations serve, and the reason family reads them from the catalogue the
backend renders them from. A member the backend adds is declared with it, and
generation then refuses until its word is authored in every locale.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from enum import Enum
from types import MappingProxyType
from typing import Final

from ._paths import LOCALES_DIR, SRC_DIR
from .locale_tree import _flatten_raw_locale_leaves
from .locale_yaml import locale_catalogue_source
from .manager import LocaleManager

#: The namespace of every key the Assets tab shares with the backend.
ASSET_NAMESPACE: Final[str] = "ledger.actividad_asset."

#: The family whose members the backend serves as ``reason_key`` values.
ASSET_REASON_FAMILY: Final[str] = f"{ASSET_NAMESPACE}errors."

#: The family whose members word the facts the timeline shows a change of; the backend serves the
#: key of each change as ``field_key``.
ASSET_FIELD_FAMILY: Final[str] = f"{ASSET_NAMESPACE}field."


def _enum_families() -> dict[str, type[Enum]]:
    """Return each token family with the enum the operations serve it from."""
    from cadrumo.application.actividad_asset.activity_asset_read_models import (
        DISPOSAL_FINDING_FAMILY,
        NON_DEDUCTIBLE_IVA_STATE_FAMILY,
        PLAN_ADVISORY_FAMILY,
        TIMELINE_TOKEN_FAMILIES,
        ActivityAssetClaimStaleReason,
        ActivityAssetClaimState,
        ActivityAssetNonDeductibleIvaState,
        ActivityAssetNotTableBoundReason,
        ActivityAssetPlanAdvisoryKind,
        ActivityAssetRegisterState,
        ActivityAssetTimelineEventKind,
    )
    from cadrumo.application.actividad_asset.schedule_walk import PlanFigureAbsence
    from cadrumo.domain.renta.actividad_asset.disposal import (
        ActivityAssetDisposalFindingKind,
        ActivityAssetDisposalReason,
        PriorFreeDepreciationRegime,
    )
    from cadrumo.domain.renta.actividad_asset.election import (
        AmortizationMethod,
        DigitOrder,
        DirectEstimationRegime,
        OriginalPriceDetermination,
    )
    from cadrumo.domain.renta.actividad_asset.lifecycle import AssetKind
    from cadrumo.domain.renta.actividad_asset.register_records import AcquisitionDocumentKind

    return {
        f"{ASSET_NAMESPACE}asset_kind.": AssetKind,
        f"{ASSET_NAMESPACE}claim_state.": ActivityAssetClaimState,
        f"{ASSET_NAMESPACE}{DISPOSAL_FINDING_FAMILY}.": ActivityAssetDisposalFindingKind,
        f"{ASSET_NAMESPACE}{PLAN_ADVISORY_FAMILY}.": ActivityAssetPlanAdvisoryKind,
        f"{ASSET_NAMESPACE}digit_order.": DigitOrder,
        f"{ASSET_NAMESPACE}disposal_reason.": ActivityAssetDisposalReason,
        f"{ASSET_NAMESPACE}document_kind.": AcquisitionDocumentKind,
        f"{ASSET_NAMESPACE}event_kind.": ActivityAssetTimelineEventKind,
        f"{ASSET_NAMESPACE}method.": AmortizationMethod,
        f"{ASSET_NAMESPACE}{NON_DEDUCTIBLE_IVA_STATE_FAMILY}.": ActivityAssetNonDeductibleIvaState,
        f"{ASSET_NAMESPACE}not_table_bound.": ActivityAssetNotTableBoundReason,
        f"{ASSET_NAMESPACE}original_price_determination.": OriginalPriceDetermination,
        f"{ASSET_NAMESPACE}plan_absence.": PlanFigureAbsence,
        f"{ASSET_NAMESPACE}prior_free_depreciation_regime.": PriorFreeDepreciationRegime,
        f"{ASSET_NAMESPACE}regime.": DirectEstimationRegime,
        f"{ASSET_NAMESPACE}register_state.": ActivityAssetRegisterState,
        f"{ASSET_NAMESPACE}stale_reason.": ActivityAssetClaimStaleReason,
        **{f"{ASSET_NAMESPACE}{family}.": enum for family, enum in TIMELINE_TOKEN_FAMILIES.values()},
    }


def _values(members: Iterable[Enum]) -> tuple[str, ...]:
    return tuple(sorted(str(member.value) for member in members))


def _reason_members() -> tuple[str, ...]:
    """Return the reason keys the catalogue renders for the backend, as members of the reason family."""
    source = locale_catalogue_source(LOCALES_DIR, "en")
    if source is None:
        raise ValueError(f"No source catalogue under {LOCALES_DIR}, so no backend reason could be listed")
    leaves = _flatten_raw_locale_leaves(LocaleManager(SRC_DIR, LOCALES_DIR).load_locale(source))
    return tuple(sorted(key.removeprefix(ASSET_REASON_FAMILY) for key in leaves if key.startswith(ASSET_REASON_FAMILY)))


def _field_members() -> tuple[str, ...]:
    """Return the facts the timeline words, as members of the field family."""
    from cadrumo.application.actividad_asset.activity_asset_read_models import (
        TIMELINE_FIELD_PATHS,
        timeline_field_word_key,
    )

    return tuple(
        sorted(timeline_field_word_key(path).removeprefix(ASSET_FIELD_FAMILY) for path in TIMELINE_FIELD_PATHS)
    )


def _asset_families() -> Mapping[str, tuple[str, ...]]:
    families = {prefix: _values(enum) for prefix, enum in _enum_families().items()}
    families[ASSET_REASON_FAMILY] = _reason_members()
    families[ASSET_FIELD_FAMILY] = _field_members()
    return MappingProxyType(families)


#: Every family the tab words by its token, as ``prefix -> members``.
ASSET_FAMILIES: Final[Mapping[str, tuple[str, ...]]] = _asset_families()

#: The family whose members are the sentences the backend serves as advisories about a book, with the
#: facts that fill each in.
INVENTORY_ADVISORY_FAMILY: Final[str] = "application.inventory.advisories."

#: The families whose catalogue text the backend renders with ``%{name}``
#: placeholders. The shell substitutes ``{name}``, so generation writes the
#: same placeholder in that form; the wording is otherwise projected as authored.
ASSET_PERCENT_PLACEHOLDER_PREFIXES: Final[tuple[str, ...]] = (ASSET_REASON_FAMILY,)

#: The enum behind each token family, for the test that compares them.
ASSET_ENUM_FAMILIES: Final[Mapping[str, type[Enum]]] = MappingProxyType(_enum_families())

def _backend_reason_keys() -> frozenset[str]:
    """Return the reason keys the plan serves outside the reason family, which the tab words as they stand."""
    from cadrumo.application.actividad_asset.activity_asset_read_models import NO_TABLE_MINIMUM_REASON_KEY

    return frozenset({NO_TABLE_MINIMUM_REASON_KEY})


#: Words the command line and the terminal workbench already state for the same
#: figure, which the tab reads rather than words again, and the reason keys the
#: plan serves that belong to no enum or reason family.
ASSET_SHARED_KEYS: Final[frozenset[str]] = (
    frozenset(
        {
            "tui.ledger.activity_asset.plan_minimum",
        }
    )
    | _backend_reason_keys()
)

#: Every key the tab words, each family member spelled out.
ASSET_KEYS: Final[frozenset[str]] = (
    frozenset(f"{prefix}{member}" for prefix, members in ASSET_FAMILIES.items() for member in members)
    | ASSET_SHARED_KEYS
)


#: The namespace the backend words the inventory enums under, which the Stock
#: panel reads rather than words again.
INVENTORY_LABEL_NAMESPACE: Final[str] = "application.inventory.labels."

#: The family whose members the backend serves as ``reason_key`` values when
#: it refuses an inventory change: one sentence for each reason, with the facts
#: that fill it in.
INVENTORY_REASON_FAMILY: Final[str] = "application.inventory.service.errors."

#: The families whose catalogue text the backend renders with ``%{name}``
#: placeholders, which the shell substitutes as ``{name}``.
INVENTORY_PERCENT_PLACEHOLDER_PREFIXES: Final[tuple[str, ...]] = (INVENTORY_REASON_FAMILY, INVENTORY_ADVISORY_FAMILY)


def _inventory_enum_families() -> dict[str, type[Enum]]:
    """Return each inventory token family with the enum the options operation serves it from."""
    from cadrumo.application.inventory.registered_options_operation import INVENTORY_OPTION_FAMILIES

    return {f"{INVENTORY_LABEL_NAMESPACE}{family}.": enum for family, enum in INVENTORY_OPTION_FAMILIES}


def _inventory_reason_members() -> tuple[str, ...]:
    """Return the reason keys the catalogue renders for the inventory operations, as members of the reason family."""
    source = locale_catalogue_source(LOCALES_DIR, "en")
    if source is None:
        raise ValueError(f"No source catalogue under {LOCALES_DIR}, so no backend reason could be listed")
    leaves = _flatten_raw_locale_leaves(LocaleManager(SRC_DIR, LOCALES_DIR).load_locale(source))
    return tuple(
        sorted(key.removeprefix(INVENTORY_REASON_FAMILY) for key in leaves if key.startswith(INVENTORY_REASON_FAMILY))
    )


def _inventory_advisory_members() -> tuple[str, ...]:
    """Return the advisory sentences the catalogue has for a book, as members of the advisory family."""
    source = locale_catalogue_source(LOCALES_DIR, "en")
    if source is None:
        raise ValueError(f"No source catalogue under {LOCALES_DIR}, so no backend advisory could be listed")
    leaves = _flatten_raw_locale_leaves(LocaleManager(SRC_DIR, LOCALES_DIR).load_locale(source))
    return tuple(
        sorted(
            key.removeprefix(INVENTORY_ADVISORY_FAMILY) for key in leaves if key.startswith(INVENTORY_ADVISORY_FAMILY)
        )
    )


def _inventory_families() -> Mapping[str, tuple[str, ...]]:
    families = {prefix: _values(enum) for prefix, enum in _inventory_enum_families().items()}
    families[INVENTORY_REASON_FAMILY] = _inventory_reason_members()
    families[INVENTORY_ADVISORY_FAMILY] = _inventory_advisory_members()
    return MappingProxyType(families)


#: Every inventory family the panel words by its token, as ``prefix -> members``.
INVENTORY_FAMILIES: Final[Mapping[str, tuple[str, ...]]] = _inventory_families()

#: The enum behind each inventory token family, for the test that compares them.
INVENTORY_ENUM_FAMILIES: Final[Mapping[str, type[Enum]]] = MappingProxyType(_inventory_enum_families())

#: Every inventory key the panel words, each family member spelled out.
INVENTORY_KEYS: Final[frozenset[str]] = frozenset(
    f"{prefix}{member}" for prefix, members in INVENTORY_FAMILIES.items() for member in members
)

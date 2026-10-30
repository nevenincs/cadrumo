"""The desktop Assets tab words every token the activity-asset operations serve.

The operations serve closed enums and ``ledger.actividad_asset.errors.*`` reason
keys. The canonical catalogues hold one word for each, and the desktop reads
them through its generated strings. Each test below fails when a backend token
has no word in a locale, when a word outlives its token, or when a reason the
backend names would reach the shell without a word.
"""

from __future__ import annotations

import re

import pytest

from cadrumo.application.actividad_asset.activity_asset_read_models import (
    TIMELINE_FIELD_PATHS,
    ActivityAssetClaimStaleReason,
    ActivityAssetClaimState,
    ActivityAssetNonDeductibleIvaState,
    ActivityAssetNotTableBoundReason,
    ActivityAssetPlanAdvisoryKind,
    ActivityAssetRegisterState,
    timeline_field_word_key,
)
from cadrumo.application.actividad_asset.fact_wording import ActivityAssetFlag
from cadrumo.application.actividad_asset.schedule_walk import PlanFigureAbsence
from cadrumo.core.tipos_actividad import TipoActividad
from cadrumo.domain.renta.actividad_asset.disposal import (
    ActivityAssetDisposalFindingKind,
    ActivityAssetDisposalReason,
    PriorFreeDepreciationRegime,
)
from cadrumo.domain.renta.actividad_asset.election import (
    AcquiredCondition,
    AmortizationMethod,
    DigitOrder,
    DirectEstimationRegime,
    OriginalPriceDetermination,
    PlanApprovalKind,
    RenewableDocumentationKind,
    RenewableInstallationPurpose,
)
from cadrumo.domain.renta.actividad_asset.lifecycle import (
    AcquisitionShape,
    AssetBasisStage,
    AssetKind,
    OpeningHistoryStatus,
    OwnershipMode,
)
from cadrumo.domain.renta.actividad_asset.register_records import AcquisitionDocumentKind, ActivityAssetEventKind
from cadrumo.domain.renta.actividad_asset.vehicle_affectation import (
    ElectricPropulsion,
    VehicleCategory,
    VehicleListedUse,
    VehiclePrivateUse,
)
from dev._paths import REPO_ROOT

from .._ast_scanner import scan_source_text
from .._paths import LOCALES_DIR, SRC_DIR
from ..desktop_assets_keys import (
    ASSET_ENUM_FAMILIES,
    ASSET_FAMILIES,
    ASSET_FIELD_FAMILY,
    ASSET_KEYS,
    ASSET_REASON_FAMILY,
    ASSET_SHARED_KEYS,
)
from ..desktop_chrome import (
    DESKTOP_CHROME_FAMILIES,
    DESKTOP_CHROME_KEYS,
    DESKTOP_LOCALES,
    desktop_chrome_strings,
    shell_key_references,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

#: Each family and the enum the operations serve its tokens from, written out
#: here so the declaration cannot agree with itself while drifting from the
#: backend.
_SERVED = {
    "acquired_condition": AcquiredCondition,
    "acquisition_shape": AcquisitionShape,
    "asset_kind": AssetKind,
    "basis_stage": AssetBasisStage,
    "claim_state": ActivityAssetClaimState,
    "declared_activity": TipoActividad,
    "digit_order": DigitOrder,
    "disposal_finding": ActivityAssetDisposalFindingKind,
    "disposal_reason": ActivityAssetDisposalReason,
    "document_kind": AcquisitionDocumentKind,
    "electric_propulsion": ElectricPropulsion,
    "event_kind": ActivityAssetEventKind,
    "flag": ActivityAssetFlag,
    "method": AmortizationMethod,
    "non_deductible_iva_state": ActivityAssetNonDeductibleIvaState,
    "not_table_bound": ActivityAssetNotTableBoundReason,
    "plan_advisory": ActivityAssetPlanAdvisoryKind,
    "opening_history_status": OpeningHistoryStatus,
    "original_price_determination": OriginalPriceDetermination,
    "ownership_mode": OwnershipMode,
    "plan_approval_kind": PlanApprovalKind,
    "plan_absence": PlanFigureAbsence,
    "prior_free_depreciation_regime": PriorFreeDepreciationRegime,
    "regime": DirectEstimationRegime,
    "register_state": ActivityAssetRegisterState,
    "renewable_documentation_kind": RenewableDocumentationKind,
    "renewable_installation_purpose": RenewableInstallationPurpose,
    "stale_reason": ActivityAssetClaimStaleReason,
    "vehicle_category": VehicleCategory,
    "vehicle_listed_use": VehicleListedUse,
    "vehicle_private_use": VehiclePrivateUse,
}
_FRONTEND_SOURCE = REPO_ROOT / "native" / "desktop" / "frontend" / "src"
_BACKEND_SOURCES = (
    SRC_DIR / "application" / "actividad_asset",
    SRC_DIR / "domain" / "renta" / "actividad_asset",
    SRC_DIR / "domain" / "calculations" / "registry" / "actividad_asset_bindings.py",
)


def test_the_declared_families_are_exactly_the_enums_the_backend_serves() -> None:
    declared = {
        prefix.removeprefix("ledger.actividad_asset.").rstrip("."): members
        for prefix, members in ASSET_FAMILIES.items()
        if prefix not in {ASSET_REASON_FAMILY, ASSET_FIELD_FAMILY}
    }

    assert declared == {family: tuple(sorted(member.value for member in enum)) for family, enum in _SERVED.items()}
    assert set(ASSET_ENUM_FAMILIES.values()) == set(_SERVED.values())


@pytest.mark.parametrize("locale", DESKTOP_LOCALES)
def test_every_token_the_backend_serves_has_a_word_in_every_locale(locale: str) -> None:
    words = desktop_chrome_strings(LOCALES_DIR, keys=ASSET_KEYS, locales=(locale,))[locale]

    missing = sorted(
        f"ledger.actividad_asset.{family}.{member.value}"
        for family, enum in _SERVED.items()
        for member in enum
        if not words.get(f"ledger.actividad_asset.{family}.{member.value}", "").strip()
    )

    assert missing == []


@pytest.mark.parametrize("locale", DESKTOP_LOCALES)
def test_no_word_outlives_the_token_it_words(locale: str) -> None:
    words = desktop_chrome_strings(LOCALES_DIR, keys=ASSET_KEYS, locales=(locale,))[locale]
    served = {f"ledger.actividad_asset.{family}.{member.value}" for family, enum in _SERVED.items() for member in enum}

    stale = sorted(
        key
        for key in words
        if not key.startswith((ASSET_REASON_FAMILY, ASSET_FIELD_FAMILY))
        and key not in served
        and key not in ASSET_SHARED_KEYS
    )

    assert stale == []


@pytest.mark.parametrize("locale", DESKTOP_LOCALES)
def test_every_fact_the_timeline_shows_has_a_word_in_every_locale_and_no_other_word_is_carried(locale: str) -> None:
    words = desktop_chrome_strings(LOCALES_DIR, keys=ASSET_KEYS, locales=(locale,))[locale]
    facts = {timeline_field_word_key(path) for path in TIMELINE_FIELD_PATHS}

    carried = {key for key in words if key.startswith(ASSET_FIELD_FAMILY)}

    assert facts, "the backend names no fact the timeline shows, so nothing was compared"
    assert carried == facts
    assert [key for key in sorted(facts) if not words[key].strip()] == []


def test_the_reference_of_a_purchase_outside_the_ledger_is_worded_plainly() -> None:
    key = timeline_field_word_key("acquisition.invoice_evidence_id")
    words = desktop_chrome_strings(LOCALES_DIR, keys=frozenset({key}), locales=DESKTOP_LOCALES)

    assert words["en"][key] == "Invoice or document reference"
    assert all(words[locale][key].strip() for locale in DESKTOP_LOCALES)


def test_every_reason_the_backend_names_is_carried_to_the_shell() -> None:
    named: set[str] = set()
    for root in _BACKEND_SOURCES:
        paths = (
            [root] if root.is_file() else [p for p in root.rglob("*.py") if "tests" not in p.relative_to(root).parts]
        )
        for path in paths:
            named |= {
                key
                for key in scan_source_text(path.read_text(encoding="utf-8"), filename=str(path))
                if key.startswith(ASSET_REASON_FAMILY)
            }

    carried = {f"{ASSET_REASON_FAMILY}{member}" for member in ASSET_FAMILIES[ASSET_REASON_FAMILY]}

    assert named, "the scan found no backend reason, so it checked nothing"
    assert named <= carried, sorted(named - carried)


@pytest.mark.parametrize("locale", DESKTOP_LOCALES)
def test_a_backend_reason_reaches_the_shell_with_the_placeholders_it_substitutes(locale: str) -> None:
    words = desktop_chrome_strings(LOCALES_DIR, keys=ASSET_KEYS, locales=(locale,))[locale]
    reasons = {key: text for key, text in words.items() if key.startswith(ASSET_REASON_FAMILY)}

    assert reasons
    assert [key for key, text in reasons.items() if "%{" in text] == []
    # A reason the backend renders with facts keeps those placeholders in the shell's form.
    assert re.search(r"\{[a-z_]+\}", reasons[f"{ASSET_REASON_FAMILY}elected_coefficient_out_of_range"])


def test_the_shell_names_the_families_and_every_member_is_declared() -> None:
    _, templates = shell_key_references(_FRONTEND_SOURCE)

    assert set(ASSET_FAMILIES) <= templates
    assert set(ASSET_FAMILIES) <= DESKTOP_CHROME_FAMILIES.keys()
    assert ASSET_KEYS <= DESKTOP_CHROME_KEYS

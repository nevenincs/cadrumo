"""Shared fixtures for verification substance tests."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from ....domain.buckets import BucketEventHistoryRepository
from ....domain.calculations.registry import CasillaId, validated_casilla_id
from ....domain.deadlines import IVARegime, TaxpayerProfile
from ....domain.modelos._calculation_repository import CalculationRevisionCatalogueRepository
from ....domain.modelos._repository import WorkUnitCatalogueRepository
from ....domain.modelos._verification_repository import VerificationReportCatalogueRepository
from ....domain.user_profile import UserProfileFact, UserProfileRecord
from ...user_profile import UserProfileLifecycleRepository

_Repos = tuple[
    WorkUnitCatalogueRepository,
    CalculationRevisionCatalogueRepository,
    VerificationReportCatalogueRepository,
    BucketEventHistoryRepository,
]

_T0 = datetime(2026, 1, 15, 12, 0, 0, tzinfo=UTC)
_T1 = datetime(2026, 1, 15, 13, 0, 0, tzinfo=UTC)
_T2 = datetime(2026, 4, 14, 14, 0, 0, tzinfo=UTC)


def _casilla_id(value: object) -> CasillaId:
    try:
        return validated_casilla_id(value, surface="test casilla id")
    except ValueError as exc:
        raise AssertionError(f"verification substance fixture casilla key {value!r} is not a CasillaId") from exc


_CASILLA_01: CasillaId = _casilla_id("01")
_CASILLA_02: CasillaId = _casilla_id("02")
_CASILLA_03: CasillaId = _casilla_id("03")
_CASILLA_05: CasillaId = _casilla_id("05")
_CASILLA_06: CasillaId = _casilla_id("06")
_CASILLA_07: CasillaId = _casilla_id("07")
_CASILLA_08: CasillaId = _casilla_id("08")
_CASILLA_09: CasillaId = _casilla_id("09")
_CASILLA_10: CasillaId = _casilla_id("10")
_CASILLA_11: CasillaId = _casilla_id("11")
_CASILLA_12: CasillaId = _casilla_id("12")
_CASILLA_14: CasillaId = _casilla_id("14")
_CASILLA_15: CasillaId = _casilla_id("15")
_CASILLA_16: CasillaId = _casilla_id("16")
_CASILLA_18: CasillaId = _casilla_id("18")
_CASILLA_00501: CasillaId = _casilla_id("00501")
_ABSENT_REGISTRY_CASILLA: CasillaId = _casilla_id("99")
_M200_BIN_OPEN_CASILLA: CasillaId = _casilla_id("00670")
_M200_BIN_CLOSING_CASILLA: CasillaId = _casilla_id("00671")
_M200_BIN_APPLIED_CASILLA: CasillaId = _casilla_id("DP200014:00547")
_M200_BIN_GENERATED_CASILLA: CasillaId = _casilla_id("DP200014:00552")

_READY_PROFILE_FACTS: tuple[UserProfileFact, ...] = (
    UserProfileFact(path="identity.tax_id", value="00000000T"),
    UserProfileFact(path="identity.name", value="Test"),
    UserProfileFact(path="identity.surnames", value="Operator"),
    UserProfileFact(path="tax_residence.ccaa", value="madrid"),
    UserProfileFact(path="tax_residence.jurisdiction_scope", value="common_regime"),
    UserProfileFact(path="activities.description", value="economic activity"),
    UserProfileFact(path="iva.regime", value="GENERAL"),
    UserProfileFact(path="taxpayer_type.entity_type", value="natural_person"),
    UserProfileFact(path="taxpayer_type.irpf_income_categories", value="actividad_economica"),
    UserProfileFact(path="irpf.estimation_regime", value="directa_normal"),
)


def _casilla_values(*entries: tuple[CasillaId, str]) -> dict[CasillaId, Decimal]:
    return {casilla_id: Decimal(value) for casilla_id, value in entries}


def _seed_ready_profile(repository: UserProfileLifecycleRepository, *, bucket_id: str) -> None:
    repository.save(
        UserProfileRecord(
            profile_id=bucket_id,
            display_name="Test Operator",
            facts=_READY_PROFILE_FACTS,
            created_at=_T0,
            updated_at=_T0,
        ),
    )


def _workflow_profile() -> TaxpayerProfile:
    return TaxpayerProfile(
        tax_id="X1234567L",
        iva_regime=IVARegime.GENERAL,
        has_employees=False,
        pays_rent_with_retencion=False,
        does_intracomunitario=False,
        bienes_extranjero_above_threshold=False,
    )

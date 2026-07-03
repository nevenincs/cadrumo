from __future__ import annotations

from datetime import UTC, date, datetime

from ....adapters.persistence.storage.sql import SecureObjectRepository
from ....core.resources import resources
from ....domain.calculations.registry import CasillaId, ModeloRevision, validated_casilla_id
from ....domain.user_profile import UserProfileFact, UserProfileRecord
from ...user_profile import UserProfileLifecycleRepository

_T0 = datetime(2026, 1, 10, 10, 0, tzinfo=UTC)
_T1 = datetime(2026, 1, 10, 11, 0, tzinfo=UTC)

_READY_PROFILE_FACTS: tuple[UserProfileFact, ...] = (
    UserProfileFact(path="identity.tax_id", value="12345678Z"),
    UserProfileFact(path="identity.name", value="Ready"),
    UserProfileFact(path="identity.surnames", value="Operator"),
    UserProfileFact(path="activities.description", value="design services"),
    UserProfileFact(path="tax_residence.ccaa", value="madrid"),
    UserProfileFact(path="tax_residence.jurisdiction_scope", value="common_regime"),
    UserProfileFact(path="iva.regime", value="GENERAL"),
    UserProfileFact(path="taxpayer_type.entity_type", value="natural_person"),
    UserProfileFact(path="taxpayer_type.irpf_income_categories", value="actividad_economica"),
    UserProfileFact(path="irpf.estimation_regime", value="directa_normal"),
    UserProfileFact(path="censo.activity_start_date", value=date(2000, 1, 1)),
)


def _seed_ready_profile(objects: SecureObjectRepository, *, bucket_id: str) -> None:
    UserProfileLifecycleRepository(bucket_id=bucket_id, objects=objects).save(
        UserProfileRecord(
            profile_id=bucket_id,
            display_name="Ready operator",
            facts=_READY_PROFILE_FACTS,
            created_at=_T0,
            updated_at=_T0,
        ),
    )


def _casilla_id(value: object) -> CasillaId:
    try:
        return validated_casilla_id(value, surface="test casilla id")
    except ValueError as exc:
        raise AssertionError(f"dormant resolver fixture casilla key {value!r} is not a CasillaId") from exc


def _revision(modelo: str, revision_id: str) -> ModeloRevision:
    modelo_def = next(item for item in resources().modelos.all() if item.id == modelo)
    return modelo_def.revisions[revision_id]

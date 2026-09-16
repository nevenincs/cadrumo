"""Profile-binding calculations over the encrypted Modelo persistence boundary.

The profile resolver's channel and type behavior is covered by the inward
application tests.  These cases additionally compose the real encrypted
profile, work-unit, revision, and bucket-event repositories so the calculation
entrypoint is proven against its persistence boundary here.
"""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from dev.registry.tests.profile_schema_support import (
    profile_creation_context_for_test as _profile_creation_context_for_test,
)

from cadrumo.adapters.persistence.profile.buckets import BucketEventHistoryRepository
from cadrumo.adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from cadrumo.adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from cadrumo.adapters.persistence.profile.tests.file_flow_test_support import calculation_ports_for_test
from cadrumo.adapters.persistence.profile.tests.published_authority_support import published_authority_operation
from cadrumo.adapters.persistence.storage.tests.profile_capsule_runtime import seed_test_profile_record
from cadrumo.adapters.persistence.storage.tests.secure_sql import isolated_runtime_profile
from cadrumo.application.modelo.calculation_actions import calculate_modelo_revision
from cadrumo.application.modelo.work_lifecycle import create_work_unit
from cadrumo.application.modelo.work_lifecycle_ports import WorkLifecyclePorts
from cadrumo.core.period import Period
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation
from cadrumo.domain.calculations.registry.ids import BindingId, RelationId
from cadrumo.domain.calculations.registry.relations import relation_prefill_bindings_for_period
from cadrumo.domain.calculations.registry.schema import RegistrySnapshot
from cadrumo.domain.modelos.errors import ModeloError
from cadrumo.domain.user_profile.values import ProfileSetupState, UserProfileFact, UserProfileRecord
from cadrumo.domain.user_profile.values import create_user_profile_record as _create_profile_record_for_test

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PROFILE_ID = "10000000-0000-4000-8000-000000000476"
_BUCKET_ID = _PROFILE_ID
_YEAR = 2025
_PERIOD = "0A"
_TYPED_PERIOD = Period.from_year_and_code(_YEAR, _PERIOD)
_CCAA_BINDING: BindingId = "renta-profile-tax-residence-ccaa"
_ESTIMACION_BINDING: BindingId = "renta-modelo-100-estimacion-directa-es-normal"
_SYNTHETIC_DECIMAL_PROFILE_BINDING: BindingId = "test-profile-business-ratio-decimal-binding"
_CLOCK = datetime(2026, 5, 21, 10, 0, 0, tzinfo=UTC)


@contextmanager
def _secure_backend(tmp_path: Path) -> Generator[None]:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        yield


def _calculation_repositories() -> tuple[
    WorkUnitCatalogueRepository,
    CalculationRevisionCatalogueRepository,
    BucketEventHistoryRepository,
]:
    return (
        WorkUnitCatalogueRepository(),
        CalculationRevisionCatalogueRepository(),
        BucketEventHistoryRepository(),
    )


def _store_profile(record: UserProfileRecord) -> None:
    seed_test_profile_record(record)


def _modelo_100_snapshot() -> RegistrySnapshot:
    return published_authority_operation().snapshot("100", filing_year=_YEAR, period=_PERIOD)


def _profile_with_ccaa(ccaa: str) -> UserProfileRecord:
    return _create_profile_record_for_test(
        setup_state=ProfileSetupState.COMPLETE,
        profile_id=_PROFILE_ID,
        facts=(
            UserProfileFact(path="identity.tax_id", value="12345678Z"),
            UserProfileFact(path="activities.description", value="economic activity"),
            UserProfileFact(path="iva.regime", value="GENERAL"),
            UserProfileFact(path="tax_residence.jurisdiction_scope", value="common_regime"),
            UserProfileFact(path="iva.m303_regime_composition", value="general"),
            UserProfileFact(path="iva.redeme_enrolled", value=False),
            UserProfileFact(path="iva.cash_accounting_regime_enrolled", value=False),
            UserProfileFact(path="iva.voluntary_sii_enrolled", value=False),
            UserProfileFact(path="iva.hydrocarbon_deposit_advance_payment_deduction_entitled", value=False),
            UserProfileFact(path="tax_residence.ccaa", value=ccaa),
            UserProfileFact(path="renta_taxpayer.birth_date", value=date(1980, 3, 15)),
            UserProfileFact(path="renta_taxpayer.marital_status", value="1"),
            UserProfileFact(path="renta_taxpayer.marriage_full_year", value=Decimal("0")),
            UserProfileFact(path="renta_taxpayer.marriage_month_start", value=Decimal("0")),
            UserProfileFact(path="renta_taxpayer.marriage_month_end", value=Decimal("0")),
            UserProfileFact(path="renta_filing.declaration_type", value="1"),
            UserProfileFact(path="renta_family.minor_children_in_unit", value=False),
        ),
        created_at=_CLOCK,
        updated_at=_CLOCK,
        context=_profile_creation_context_for_test(),
    )


def _non_ccaa_decimal_binding_values(snapshot: RegistrySnapshot) -> dict[BindingId, Decimal]:
    """Supply non-CCAA, non-profile bindings through the Decimal channel."""
    return {
        binding.id: Decimal("0")
        for binding in snapshot.revision.bindings
        if binding.id != _CCAA_BINDING and binding.source != "profile"
    }


def _zero_relation_values(snapshot: RegistrySnapshot) -> dict[RelationId, Decimal]:
    return {binding.id: Decimal("0") for binding, _ in relation_prefill_bindings_for_period(snapshot.revision)}


def test_calculate_modelo_revision_resolves_ccaa_from_profile_without_caller_input(
    tmp_path: Path, *, operation: PinnedAuthorityOperation
) -> None:
    """A Modelo 100 calculation resolves CCAA from the persisted profile."""
    with _secure_backend(tmp_path):
        _store_profile(_profile_with_ccaa("madrid"))
        snapshot = _modelo_100_snapshot()
        work_repo, calc_repo, event_repo = _calculation_repositories()
        work_unit = create_work_unit(
            bucket_id=_BUCKET_ID,
            modelo="100",
            filing_year=_YEAR,
            period=_TYPED_PERIOD,
            revision_id="2025",
            ports=WorkLifecyclePorts(work_unit_repository=work_repo, bucket_event_repository=event_repo),
            clock=_CLOCK,
            operation=operation,
        )
        with calculation_ports_for_test(
            bucket_id=_BUCKET_ID,
            work_unit_repository=work_repo,
            calculation_repository=calc_repo,
            bucket_event_repository=event_repo,
        ) as _calculation_ports_144:
            revision = calculate_modelo_revision(
                work_unit.work_unit_id,
                actor="operator",
                casilla_inputs={},
                binding_values=_non_ccaa_decimal_binding_values(snapshot),
                relation_values=_zero_relation_values(snapshot),
                ports=_calculation_ports_144,
                clock=_CLOCK,
            )
        assert "0512" in revision.casilla_values
        assert revision.binding_overrides[_CCAA_BINDING] == "madrid"


def test_calculate_modelo_revision_rejects_ccaa_supplied_through_decimal_channel(
    tmp_path: Path, *, operation: PinnedAuthorityOperation
) -> None:
    """Supplying the enum-consumed CCAA binding as Decimal is refused."""
    with _secure_backend(tmp_path):
        _store_profile(_profile_with_ccaa("madrid"))
        snapshot = _modelo_100_snapshot()
        work_repo, calc_repo, event_repo = _calculation_repositories()
        work_unit = create_work_unit(
            bucket_id=_BUCKET_ID,
            modelo="100",
            filing_year=_YEAR,
            period=_TYPED_PERIOD,
            revision_id="2025",
            ports=WorkLifecyclePorts(work_unit_repository=work_repo, bucket_event_repository=event_repo),
            clock=_CLOCK,
            operation=operation,
        )
        decimal_bindings = {binding.id: Decimal("0") for binding in snapshot.revision.bindings}
        with (
            pytest.raises(ModeloError),
            calculation_ports_for_test(
                bucket_id=_BUCKET_ID,
                work_unit_repository=work_repo,
                calculation_repository=calc_repo,
                bucket_event_repository=event_repo,
            ) as _calculation_ports_181,
        ):
            calculate_modelo_revision(
                work_unit.work_unit_id,
                actor="operator",
                casilla_inputs={},
                binding_values=decimal_bindings,
                relation_values=_zero_relation_values(snapshot),
                ports=_calculation_ports_181,
                clock=_CLOCK,
            )
        assert calc_repo.load().revisions == {}


def test_estimacion_directa_binding_stays_in_the_decimal_channel(
    tmp_path: Path, *, operation: PinnedAuthorityOperation
) -> None:
    """The estimacion-directa binding remains on the Decimal channel."""
    with _secure_backend(tmp_path):
        _store_profile(_profile_with_ccaa("madrid"))
        snapshot = _modelo_100_snapshot()
        work_repo, calc_repo, event_repo = _calculation_repositories()
        work_unit = create_work_unit(
            bucket_id=_BUCKET_ID,
            modelo="100",
            filing_year=_YEAR,
            period=_TYPED_PERIOD,
            revision_id="2025",
            ports=WorkLifecyclePorts(work_unit_repository=work_repo, bucket_event_repository=event_repo),
            clock=_CLOCK,
            operation=operation,
        )
        with calculation_ports_for_test(
            bucket_id=_BUCKET_ID,
            work_unit_repository=work_repo,
            calculation_repository=calc_repo,
            bucket_event_repository=event_repo,
        ) as _calculation_ports_215:
            revision = calculate_modelo_revision(
                work_unit.work_unit_id,
                actor="operator",
                casilla_inputs={},
                binding_values=_non_ccaa_decimal_binding_values(snapshot),
                relation_values=_zero_relation_values(snapshot),
                ports=_calculation_ports_215,
                clock=_CLOCK,
            )
        assert Decimal(revision.binding_overrides[_ESTIMACION_BINDING]) == Decimal("0")


def test_estimacion_directa_binding_rejected_through_enum_channel(
    tmp_path: Path, *, operation: PinnedAuthorityOperation
) -> None:
    """Routing the Decimal-consumed binding through enum is refused."""
    with _secure_backend(tmp_path):
        _store_profile(_profile_with_ccaa("madrid"))
        snapshot = _modelo_100_snapshot()
        work_repo, calc_repo, event_repo = _calculation_repositories()
        work_unit = create_work_unit(
            bucket_id=_BUCKET_ID,
            modelo="100",
            filing_year=_YEAR,
            period=_TYPED_PERIOD,
            revision_id="2025",
            ports=WorkLifecyclePorts(work_unit_repository=work_repo, bucket_event_repository=event_repo),
            clock=_CLOCK,
            operation=operation,
        )
        with (
            pytest.raises(ModeloError),
            calculation_ports_for_test(
                bucket_id=_BUCKET_ID,
                work_unit_repository=work_repo,
                calculation_repository=calc_repo,
                bucket_event_repository=event_repo,
            ) as _calculation_ports_251,
        ):
            calculate_modelo_revision(
                work_unit.work_unit_id,
                actor="operator",
                casilla_inputs={},
                binding_values=_non_ccaa_decimal_binding_values(snapshot),
                enum_binding_values={_ESTIMACION_BINDING: "normal"},
                relation_values=_zero_relation_values(snapshot),
                ports=_calculation_ports_251,
                clock=_CLOCK,
            )
        assert calc_repo.load().revisions == {}

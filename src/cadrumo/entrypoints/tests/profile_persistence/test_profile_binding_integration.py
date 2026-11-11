"""Profile-binding calculations over the encrypted Modelo persistence boundary.

The profile resolver's channel and type behavior is covered by the inward
application tests.  These cases additionally compose the real encrypted
profile, work-unit, revision, and bucket-event repositories so the calculation
entrypoint is proven against its persistence boundary here.
"""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from cadrumo.application.modelo.calculation_source_policy import BUCKET_AGGREGATION_LOCK_SOURCES
from cadrumo.application.user_profile.tests.persona_profile_facts import persona_facts_beneath
from cadrumo.domain.user_profile.tests.profile_creation_authority import (
    profile_creation_context_for_test,
)

from ....adapters.persistence.profile.buckets import BucketEventHistoryRepository
from ....adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from ....adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from ....adapters.persistence.profile.tests.published_authority_support import published_authority_operation
from ....adapters.persistence.storage.tests.profile_capsule_runtime import seed_test_profile_record
from ....adapters.persistence.storage.tests.secure_sql import isolated_runtime_profile
from ....application.modelo.calculation_bucket_actions import (
    calculate_modelo_revision_from_bucket_aggregation_with_diagnostics,
)
from ....application.modelo.work_lifecycle import create_work_unit
from ....application.modelo.work_lifecycle_ports import WorkLifecyclePorts
from ....core.period import Period
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.ids import BindingId, RelationId
from ....domain.calculations.registry.relations import relation_prefill_bindings_for_period
from ....domain.calculations.registry.schema import RegistrySnapshot
from ....domain.calculations.registry.tests.authored_editions import (
    filing_year_envelope,
    newest_authored_edition,
    revision_covering,
)
from ....domain.modelos.errors import ModeloError
from ....domain.user_profile.tests.general_regime_facts import RENTA_UNMARRIED_TAXPAYER_FACTS
from ....domain.user_profile.values import (
    ProfileSetupState,
    UserProfileFact,
    UserProfileRecord,
    create_user_profile_record,
)
from .file_flow_test_support import calculation_ports_for_test

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_PROFILE_ID = "10000000-0000-4000-8000-000000000476"
_BUCKET_ID = _PROFILE_ID
_YEAR = newest_authored_edition("100")
_PERIOD = "0A"
_TYPED_PERIOD = Period.from_year_and_code(_YEAR, _PERIOD)
_CCAA_BINDING: BindingId = "renta-profile-tax-residence-ccaa"
_ESTIMACION_BINDING: BindingId = "renta-modelo-100-estimacion-directa-es-normal"
_SYNTHETIC_DECIMAL_PROFILE_BINDING: BindingId = "test-profile-business-ratio-decimal-binding"
_CLOCK = datetime(filing_year_envelope().horizon, 5, 21, 10, 0, 0, tzinfo=UTC)


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
    return create_user_profile_record(
        setup_state=ProfileSetupState.COMPLETE,
        profile_id=_PROFILE_ID,
        facts=persona_facts_beneath(
            (
                UserProfileFact(path="identity.tax_id", value="12345678Z"),
                UserProfileFact(path="activities.description", value="economic activity"),
                UserProfileFact(path="tax_residence.ccaa", value=ccaa),
                *RENTA_UNMARRIED_TAXPAYER_FACTS,
            )
        ),
        created_at=_CLOCK,
        updated_at=_CLOCK,
        context=profile_creation_context_for_test(),
    )


def _non_ccaa_decimal_binding_values(snapshot: RegistrySnapshot) -> dict[BindingId, Decimal]:
    """Supply the operator-entered bindings other than CCAA through the Decimal channel.

    Profile- and bucket-sourced bindings are resolved by the calculation itself.
    """
    return {
        binding.id: Decimal("0")
        for binding in snapshot.revision.bindings
        if binding.id != _CCAA_BINDING
        and binding.source != "profile"
        and binding.source not in BUCKET_AGGREGATION_LOCK_SOURCES
        and binding.provider.kind != "retencion_soportada"
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
            revision_id=str(revision_covering("100", _YEAR).id),
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
            revision = calculate_modelo_revision_from_bucket_aggregation_with_diagnostics(
                work_unit.work_unit_id,
                actor="operator",
                casilla_inputs={},
                binding_values=_non_ccaa_decimal_binding_values(snapshot),
                relation_values=_zero_relation_values(snapshot),
                ports=_calculation_ports_144,
                clock=_CLOCK,
            ).revision
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
            revision_id=str(revision_covering("100", _YEAR).id),
            ports=WorkLifecyclePorts(work_unit_repository=work_repo, bucket_event_repository=event_repo),
            clock=_CLOCK,
            operation=operation,
        )
        decimal_bindings = {**_non_ccaa_decimal_binding_values(snapshot), _CCAA_BINDING: Decimal("0")}
        with (
            pytest.raises(ModeloError),
            calculation_ports_for_test(
                bucket_id=_BUCKET_ID,
                work_unit_repository=work_repo,
                calculation_repository=calc_repo,
                bucket_event_repository=event_repo,
            ) as _calculation_ports_181,
        ):
            calculate_modelo_revision_from_bucket_aggregation_with_diagnostics(
                work_unit.work_unit_id,
                actor="operator",
                casilla_inputs={},
                binding_values=decimal_bindings,
                relation_values=_zero_relation_values(snapshot),
                ports=_calculation_ports_181,
                clock=_CLOCK,
            )
        assert calc_repo.load().revisions == {}


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
            revision_id=str(revision_covering("100", _YEAR).id),
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
            calculate_modelo_revision_from_bucket_aggregation_with_diagnostics(
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

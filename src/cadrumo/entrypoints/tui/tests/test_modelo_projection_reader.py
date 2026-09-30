"""Real proof for the launcher's shared Modelo projection reader.

``_modelo_projection_reader`` is the one seam that tries GRADED_SNAPSHOT and
falls back to STATIC_INSPECTION on a taxpayer-facing refusal. These tests
exercise it against a real bucket, a real registry authority and a real
work unit -- never a mocked resolver -- so the fallback and the carried
refusal are proven against the actual admission functions, not a stand-in
that would agree with itself.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, date, datetime
from pathlib import Path
from typing import cast

import pytest

from ....adapters.persistence.profile.buckets import BucketEventHistoryRepository
from ....adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from ....adapters.persistence.storage.tests.profile_capsule_runtime import seed_test_profile_record
from ....adapters.persistence.storage.tests.secure_sql import isolated_runtime_profile
from ....application.modelo.work_addressing import law_selected_revision_for_work_target
from ....application.modelo.work_lifecycle import create_work_unit
from ....application.modelo.work_lifecycle_ports import WorkLifecyclePorts
from ....application.modelo.workspace_models import ModeloWorkspaceAdmissionKind
from ....application.producer_capture import ProducerCaptureError
from ....core.authority_grade import RegistryAuthorityGrade
from ....core.period import Period
from ....domain.calculations.registry.authority import (
    PinnedAuthorityOperation,
    RegistryAuthorityCapture,
    RegistryAuthorityCurrentCoordinate,
    bundled_indexed_authority,
)
from ....domain.user_profile.values import ProfileSetupState, UserProfileFact, create_user_profile_record
from ..launcher import MODELO_WORKSPACE_READ_ATTEMPTS, _modelo_projection_reader

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_PROFILE_ID = "13000000-0000-4000-8000-000000000231"
_T0 = datetime(2026, 6, 5, 9, 0, 0, tzinfo=UTC)
_READY_PROFILE_FACTS: tuple[UserProfileFact, ...] = (
    UserProfileFact(path="identity.tax_id", value="00000000T"),
    UserProfileFact(path="identity.name", value="Test Operator"),
    UserProfileFact(path="identity.surnames", value="Workspace"),
    UserProfileFact(path="tax_residence.ccaa", value="madrid"),
    UserProfileFact(path="tax_residence.jurisdiction_scope", value="common_regime"),
    UserProfileFact(path="activities.description", value="economic activity"),
    UserProfileFact(path="iva.regime", value="GENERAL"),
    UserProfileFact(path="iva.m303_regime_composition", value="general"),
    UserProfileFact(path="iva.redeme_enrolled", value=False),
    UserProfileFact(path="iva.cash_accounting_regime_enrolled", value=False),
    UserProfileFact(path="iva.voluntary_sii_enrolled", value=False),
    UserProfileFact(path="iva.hydrocarbon_deposit_advance_payment_deduction_entitled", value=False),
    UserProfileFact(path="provenance.source", value="manual_cli"),
    UserProfileFact(path="taxpayer_type.entity_type", value="natural_person"),
    UserProfileFact(path="taxpayer_type.irpf_income_categories", value="actividad_economica"),
    UserProfileFact(path="irpf.estimation_regime", value="directa_normal"),
)


@pytest.fixture
def bucket_and_repository(tmp_path: Path) -> Iterator[tuple[str, WorkUnitCatalogueRepository]]:
    """Yield one real bucket-scoped work-unit repository holding one uncalculated Modelo 130 unit."""
    with (
        isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_PROFILE_ID) as profile,
        bundled_indexed_authority().operation() as operation,
    ):
        seed_test_profile_record(
            create_user_profile_record(
                setup_state=ProfileSetupState.COMPLETE,
                profile_id=profile.bucket_id,
                facts=_READY_PROFILE_FACTS,
                created_at=_T0,
                updated_at=_T0,
                context=operation.profile_create_context(),
            ),
        )
        repository = WorkUnitCatalogueRepository(objects=profile.repository)
        period = Period.from_year_and_code(2026, "1T")
        create_work_unit(
            bucket_id=profile.bucket_id,
            modelo="130",
            filing_year=2026,
            period=period,
            revision_id=law_selected_revision_for_work_target(
                modelo="130", filing_year=2026, period=period, operation=operation
            ),
            ports=WorkLifecyclePorts(
                work_unit_repository=repository,
                bucket_event_repository=BucketEventHistoryRepository(),
            ),
            clock=_T0,
            operation=operation,
        )
        yield profile.bucket_id, repository


def test_the_reader_falls_back_to_the_static_inspection_of_an_uncalculated_unit(
    bucket_and_repository: tuple[str, WorkUnitCatalogueRepository],
) -> None:
    """A freshly created work unit has no calculation, so the graded read refuses and the static one answers.

    The seeded work unit exists but was never calculated, so a graded snapshot
    is refused; STATIC_INSPECTION remains valid for that refusal, and the
    reader returns it for the same work unit rather than failing the source.
    """
    bucket_id, repository = bucket_and_repository
    catalogue, _ = repository.load_revisioned()
    (unit,) = catalogue.work_units.values()

    with bundled_indexed_authority().operation() as operation:
        read = _modelo_projection_reader(operation)(unit)

    assert read.admission.kind is ModeloWorkspaceAdmissionKind.STATIC_INSPECTION
    assert read.target.work_unit_id == unit.work_unit_id
    assert read.target.bucket_id == bucket_id


class _RepublishedAfterEveryCapture:
    """The real pinned operation, republished after every registry capture taken from it.

    Every admission therefore finds the registry moved at its currentness
    pass. Only the coordinate read is altered; every other call, the captures
    included, is the real operation's.
    """

    def __init__(self, operation: PinnedAuthorityOperation) -> None:
        self._operation = operation
        self._republications = 0

    def capture_law_selected_projection(
        self,
        modelo_id: str,
        *,
        filing_year: int,
        period: str,
        on: date | None = None,
        grade: RegistryAuthorityGrade | None = None,
    ) -> RegistryAuthorityCapture:
        capture = self._operation.capture_law_selected_projection(
            modelo_id, filing_year=filing_year, period=period, on=on, grade=grade
        )
        self._republications += 1
        return capture

    def read_current_coordinate(self) -> RegistryAuthorityCurrentCoordinate:
        current = self._operation.read_current_coordinate()
        return RegistryAuthorityCurrentCoordinate(
            comparison_domain=current.comparison_domain,
            generation=current.generation + self._republications,
        )

    def __getattr__(self, name: str) -> object:
        return getattr(self._operation, name)


def test_the_reader_gives_up_on_a_unit_that_changes_on_every_read(
    bucket_and_repository: tuple[str, WorkUnitCatalogueRepository],
) -> None:
    """A bounded number of re-reads, then the contended refusal; never an endless loop."""
    _bucket_id, repository = bucket_and_repository
    catalogue, _ = repository.load_revisioned()
    (unit,) = catalogue.work_units.values()

    with bundled_indexed_authority().operation() as operation:
        republishing = cast("PinnedAuthorityOperation", _RepublishedAfterEveryCapture(operation))
        with pytest.raises(ProducerCaptureError) as refusal:
            _modelo_projection_reader(republishing)(unit)

    assert refusal.value.context == {"reason": "contended", "attempts": MODELO_WORKSPACE_READ_ATTEMPTS}

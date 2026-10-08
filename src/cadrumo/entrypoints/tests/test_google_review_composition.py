"""Production review loading binds saved coordinates and full authority digests."""

from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import UUID

import pytest

from ...application.export.review_snapshot import CalculationReviewSelection
from ...application.user_profile.access_errors import ProfileAccessRefusedError
from ...core.hashing import content_hash_hex
from ...core.period import Period
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.calculations.registry.schema_references import RegistrySnapshotRef
from ...domain.modelos.calculation_revision import (
    CalculationRevision,
    CalculationRevisionCatalogue,
    CalculationRevisionState,
    derive_calculation_revision_id,
)
from ...domain.modelos.calculation_revision_rendering import CalculationRenderingSnapshot
from ...domain.modelos.filing_record import ModeloRecordCatalogue
from ...domain.modelos.work_unit import WorkUnit, WorkUnitCatalogue, derive_work_unit_id
from .. import calculation_review_snapshot_composition as snapshot_composition
from .. import google_review_operation_composition as composition

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]
_PROFILE = UUID("5aa00000-0000-4000-8000-0000000000aa")


def _saved(operation: PinnedAuthorityOperation) -> tuple[CalculationRevision, WorkUnit]:
    registry = operation.snapshot("130", filing_year=2026, period="1T")
    rendering = CalculationRenderingSnapshot.capture(
        registry, authority_generation=operation.generation.logical_generation
    )
    period = Period.from_year_and_code(2026, "1T")
    instant = datetime(2026, 3, 10, 12, tzinfo=UTC)
    unit = WorkUnit(
        work_unit_id=derive_work_unit_id(
            bucket_id=str(_PROFILE), modelo="130", filing_year=2026, period=period, revision_id=registry.revision.id
        ),
        bucket_id=str(_PROFILE),
        modelo="130",
        filing_year=2026,
        period=period,
        revision_id=registry.revision.id,
        name="Saved synthetic calculation",
        created_at=instant,
        updated_at=instant,
        current_calculation_revision_id="f" * 64,
    )
    revision = CalculationRevision(
        calculation_revision_id=derive_calculation_revision_id(
            work_unit_id=unit.work_unit_id,
            input_values_by_casilla_id={},
            binding_overrides={},
            casilla_values={},
            filing_instance_evidence=None,
            source_provenance=(),
            rendering_snapshot=rendering,
        ),
        work_unit_id=unit.work_unit_id,
        registry_snapshot_ref=RegistrySnapshotRef(
            modelo="130", revision_id=registry.revision.id, modelo_year=2026, period="1T"
        ),
        state=CalculationRevisionState.BORRADOR,
        source_provenance=(),
        filing_instance_evidence=None,
        rendering_snapshot=rendering,
        created_at=instant,
        updated_at=instant,
    )
    return revision, unit


def _repositories(
    monkeypatch: pytest.MonkeyPatch,
    operation: PinnedAuthorityOperation,
    *,
    foreign_bucket: bool = False,
) -> tuple[CalculationRevision, WorkUnit]:
    revision, unit = _saved(operation)

    class Calculations:
        bucket_id = "other-profile" if foreign_bucket else str(_PROFILE)

        def load(self, *, operation: PinnedAuthorityOperation) -> CalculationRevisionCatalogue:
            assert operation is pinned
            return CalculationRevisionCatalogue(revisions={revision.calculation_revision_id: revision})

    class WorkUnits:
        bucket_id = str(_PROFILE)

        def load(self) -> WorkUnitCatalogue:
            return WorkUnitCatalogue(work_units={unit.work_unit_id: unit})

    class Filings:
        bucket_id = str(_PROFILE)

        def load(self) -> ModeloRecordCatalogue:
            return ModeloRecordCatalogue()

    pinned = operation

    def factory(profile: str, *, operation: PinnedAuthorityOperation) -> SimpleNamespace:
        assert profile == str(_PROFILE)
        assert operation is pinned
        return SimpleNamespace(calculation=Calculations(), work_unit=WorkUnits(), filing=Filings())

    monkeypatch.setattr(snapshot_composition, "build_verification_repository_bundle", factory)
    return revision, unit


def test_composed_loader_uses_exact_saved_revision_and_full_digest(
    authority_operation: PinnedAuthorityOperation, monkeypatch: pytest.MonkeyPatch
) -> None:
    revision, unit = _repositories(monkeypatch, authority_operation)
    ports = composition.build_google_review_ports(profile_id=_PROFILE, operation=authority_operation)
    snapshot = ports.load_snapshot(revision.calculation_revision_id)
    selection = snapshot.selection
    assert isinstance(selection, CalculationReviewSelection)
    assert selection.profile_id == _PROFILE
    assert selection.work_unit_id == unit.work_unit_id
    assert selection.calculation_revision_id == revision.calculation_revision_id
    assert selection.calculation_revision_id != unit.current_calculation_revision_id
    assert selection.registry_snapshot_ref == revision.registry_snapshot_ref
    assert selection.authority_generation == authority_operation.generation.logical_generation
    registry = authority_operation.snapshot(
        "130", filing_year=2026, period="1T", revision_id=revision.registry_snapshot_ref.revision_id
    )
    assert selection.registry_digest == content_hash_hex(registry.model_dump(mode="json"))
    assert len(selection.registry_digest) == 64


def test_composed_loader_refuses_unknown_saved_revision(
    authority_operation: PinnedAuthorityOperation, monkeypatch: pytest.MonkeyPatch
) -> None:
    _repositories(monkeypatch, authority_operation)
    ports = composition.build_google_review_ports(profile_id=_PROFILE, operation=authority_operation)
    with pytest.raises(ProfileAccessRefusedError):
        ports.load_snapshot("e" * 64)


def test_composed_loader_refuses_foreign_profile_repository(
    authority_operation: PinnedAuthorityOperation, monkeypatch: pytest.MonkeyPatch
) -> None:
    revision, _unit = _repositories(monkeypatch, authority_operation, foreign_bucket=True)
    ports = composition.build_google_review_ports(profile_id=_PROFILE, operation=authority_operation)
    with pytest.raises(ProfileAccessRefusedError):
        ports.load_snapshot(revision.calculation_revision_id)

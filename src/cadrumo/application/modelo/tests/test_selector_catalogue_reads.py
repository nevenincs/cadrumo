"""Selectors derive one result from one fresh catalogue without retaining it."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import override

import pytest

from ....core.period import Period
from ....core.secure_object_write import SecureObjectWrite
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.schema_references import RegistrySnapshotRef
from ....domain.modelos.calculation_revision import (
    CalculationRevision,
    CalculationRevisionCatalogue,
    CalculationRevisionState,
    derive_calculation_revision_id,
)
from ....domain.modelos.protocols import CalculationRevisionCatalogueRepositoryProtocol
from ....domain.modelos.work_unit import WorkUnit, derive_work_unit_id
from ..action_errors import WorkUnitRevisionDivergenceError
from ..selectors import (
    ModeloCalculationRevisionSelector,
    ModeloCalculationRevisionSelectorNotFoundError,
    ModeloCalculationRevisionSelectorStateError,
    resolve_modelo_calculation_revision_pick,
    select_exportable_revision,
    select_modelo_calculation_revision,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PROFILE = "5aa00000-0000-4000-8000-0000000000aa"
_INSTANT = datetime(2026, 3, 10, 12, tzinfo=UTC)


class _ReadRepository(CalculationRevisionCatalogueRepositoryProtocol):
    def __init__(self, catalogue: CalculationRevisionCatalogue) -> None:
        self.catalogue = catalogue
        self.operations: list[PinnedAuthorityOperation | None] = []

    @property
    @override
    def bucket_id(self) -> str:
        return _PROFILE

    @override
    def load(self, *, operation: PinnedAuthorityOperation | None = None) -> CalculationRevisionCatalogue:
        self.operations.append(operation)
        return self.catalogue

    @override
    def exists(self) -> bool:
        pytest.fail("Selector must read the catalogue directly")

    @override
    def load_revisioned(
        self, *, operation: PinnedAuthorityOperation | None = None
    ) -> tuple[CalculationRevisionCatalogue, str]:
        pytest.fail("Selector must not perform a write-boundary read")

    @override
    def save(self, catalogue: CalculationRevisionCatalogue) -> None:
        pytest.fail("Selector must not persist a catalogue")

    @override
    def to_secure_object_write(
        self, catalogue: CalculationRevisionCatalogue, *, expected_revision_id: str | None = None
    ) -> SecureObjectWrite:
        pytest.fail("Selector must not prepare a write")

    @override
    def save_with_secure_object_writes(
        self,
        catalogue: CalculationRevisionCatalogue,
        extra_writes: tuple[SecureObjectWrite, ...],
        *,
        expected_revision_id: str | None = None,
    ) -> None:
        pytest.fail("Selector must not persist co-emitted writes")


def _facts(
    *, state: CalculationRevisionState = CalculationRevisionState.BORRADOR, profile: str = _PROFILE
) -> tuple[WorkUnit, CalculationRevision, CalculationRevisionCatalogue]:
    period = Period.from_year_and_code(2026, "2T")
    work_id = derive_work_unit_id(
        bucket_id=profile, modelo="303", filing_year=2026, period=period, revision_id="2026-y-siguientes"
    )
    revision_id = derive_calculation_revision_id(
        work_unit_id=work_id,
        input_values_by_casilla_id={},
        binding_overrides={},
        casilla_values={},
        filing_instance_evidence=None,
        source_provenance=(),
    )
    unit = WorkUnit(
        work_unit_id=work_id,
        bucket_id=profile,
        modelo="303",
        filing_year=2026,
        period=period,
        revision_id="2026-y-siguientes",
        name="Quarterly return",
        created_at=_INSTANT,
        updated_at=_INSTANT,
        current_calculation_revision_id=revision_id,
        filed_calculation_revision_id=revision_id if state is CalculationRevisionState.PRESENTADO else None,
    )
    revision = CalculationRevision(
        calculation_revision_id=revision_id,
        work_unit_id=work_id,
        registry_snapshot_ref=RegistrySnapshotRef(
            modelo="303", revision_id=unit.revision_id, modelo_year=2026, period="2T"
        ),
        state=state,
        created_at=_INSTANT,
        updated_at=_INSTANT,
        verified_at=None if state is CalculationRevisionState.BORRADOR else _INSTANT,
        verified_by=None if state is CalculationRevisionState.BORRADOR else "operator",
        filed_at=_INSTANT if state is CalculationRevisionState.PRESENTADO else None,
        filed_by="operator" if state is CalculationRevisionState.PRESENTADO else None,
        filing_instance_evidence=None,
        source_provenance=(),
    )
    return unit, revision, CalculationRevisionCatalogue(revisions={revision_id: revision})


@pytest.mark.parametrize(
    "selector",
    [
        ModeloCalculationRevisionSelector.CURRENT,
        ModeloCalculationRevisionSelector.EXPLICIT,
        ModeloCalculationRevisionSelector.FILED,
    ],
)
def test_pointer_and_explicit_picks_read_once_then_freshly_on_next_call(
    selector: ModeloCalculationRevisionSelector, *, authority_operation: PinnedAuthorityOperation
) -> None:
    unit, revision, catalogue = _facts(
        state=CalculationRevisionState.PRESENTADO
        if selector is ModeloCalculationRevisionSelector.FILED
        else CalculationRevisionState.BORRADOR
    )
    repository = _ReadRepository(catalogue)
    selection = select_modelo_calculation_revision(
        unit,
        selector=selector,
        calculation_revision_id=revision.calculation_revision_id
        if selector is ModeloCalculationRevisionSelector.EXPLICIT
        else None,
        calculation_repository=repository,
        operation=authority_operation,
    )
    assert selection.revision is revision
    assert selection.selector is selector
    assert selection.candidates[0].calculation_revision_id == revision.calculation_revision_id
    assert repository.operations == [authority_operation]
    repository.catalogue = CalculationRevisionCatalogue()
    with pytest.raises(ModeloCalculationRevisionSelectorNotFoundError):
        select_modelo_calculation_revision(
            unit,
            selector=selector,
            calculation_revision_id=revision.calculation_revision_id
            if selector is ModeloCalculationRevisionSelector.EXPLICIT
            else None,
            calculation_repository=repository,
            operation=authority_operation,
        )
    assert repository.operations == [authority_operation, authority_operation]


@pytest.mark.parametrize("filed", [False, True])
def test_export_policy_read_preserves_current_and_filed_preference(
    filed: bool, *, authority_operation: PinnedAuthorityOperation
) -> None:
    unit, revision, catalogue = _facts(
        state=CalculationRevisionState.PRESENTADO if filed else CalculationRevisionState.VERIFICADO_COMPLETO
    )
    repository = _ReadRepository(catalogue)
    selection = select_exportable_revision(unit, calculation_repository=repository, operation=authority_operation)
    assert selection.revision is revision
    assert selection.selector is (
        ModeloCalculationRevisionSelector.FILED if filed else ModeloCalculationRevisionSelector.CURRENT
    )
    assert repository.operations == [authority_operation]


def test_missing_foreign_parent_is_still_refused_after_one_read(
    *, authority_operation: PinnedAuthorityOperation
) -> None:
    unit, _revision, _catalogue = _facts()
    _other_unit, other_revision, foreign_catalogue = _facts(profile="6bb00000-0000-4000-8000-0000000000bb")
    repository = _ReadRepository(foreign_catalogue)
    with pytest.raises(ModeloCalculationRevisionSelectorStateError):
        select_modelo_calculation_revision(
            unit,
            selector=ModeloCalculationRevisionSelector.EXPLICIT,
            calculation_revision_id=other_revision.calculation_revision_id,
            calculation_repository=repository,
            operation=authority_operation,
        )
    assert repository.operations == [authority_operation]


def test_export_still_refuses_current_draft_after_one_read(*, authority_operation: PinnedAuthorityOperation) -> None:
    unit, _revision, catalogue = _facts()
    repository = _ReadRepository(catalogue)
    with pytest.raises(ModeloCalculationRevisionSelectorStateError):
        select_exportable_revision(unit, calculation_repository=repository, operation=authority_operation)
    assert repository.operations == [authority_operation]


def test_reused_capture_catalogue_still_checks_revision_coordinates(
    *, authority_operation: PinnedAuthorityOperation
) -> None:
    unit, revision, catalogue = _facts()
    repository = _ReadRepository(catalogue)
    stale = revision.model_copy(
        update={
            "registry_snapshot_ref": RegistrySnapshotRef(
                modelo="303", revision_id="2022", modelo_year=2026, period="1T"
            )
        }
    )
    loaded = CalculationRevisionCatalogue(revisions={stale.calculation_revision_id: stale})
    with pytest.raises(WorkUnitRevisionDivergenceError):
        resolve_modelo_calculation_revision_pick(
            unit, calculation_repository=repository, calculation_catalogue=loaded, operation=authority_operation
        )
    assert not repository.operations

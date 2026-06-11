"""Real-behavior tests for modelo work-unit application selectors."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import cast

import pytest

from ....core import Period
from ....domain.modelos._calculation_repository import (
    CalculationRevisionCatalogueRepository,
    upsert_calculation_revision,
)
from ....domain.modelos._calculation_revision import (
    CalculationRevision,
    CalculationRevisionState,
    derive_calculation_revision_id,
)
from ....domain.modelos._codes import ModeloCode
from ....domain.modelos._repository import WorkUnitCatalogueRepository, upsert_work_unit
from ....domain.modelos._work_unit import WorkUnit, WorkUnitState, derive_work_unit_id
from ....tests.secure_sql import isolated_runtime_profile
from .. import create_work_unit
from .._selectors import (
    ModeloCalculationRevisionSelector,
    ModeloCalculationRevisionSelectorAmbiguousError,
    ModeloCalculationRevisionSelectorStateError,
    ModeloWorkRevisionConflictError,
    ModeloWorkSelectorContradictionError,
    ModeloWorkSelectorRequest,
    ModeloWorkSelectorState,
    ModeloWorkVisibleTargetAmbiguousError,
    resolve_modelo_work_bucket,
    resolve_modelo_work_unit,
    select_current_draft_revision,
    select_current_verified_revision,
    select_exportable_revision,
    select_modelo_calculation_revision,
    visible_target_work_units,
)
from .._work_addressing import (
    ModeloWorkAddress,
    resolve_exportable_modelo_calculation_revision_address,
    resolve_fileable_modelo_calculation_revision_address,
    resolve_verifiable_modelo_calculation_revision_address,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


_T0 = datetime(2026, 6, 4, 9, 0, 0, tzinfo=UTC)
_P_2026_1T = Period.from_year_and_code(2026, "1T")


@pytest.fixture
def work_repo(tmp_path: Path) -> Iterator[WorkUnitCatalogueRepository]:
    """Yield the real work-unit repository through isolated profile storage."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="modelo-selector-test") as profile:
        yield WorkUnitCatalogueRepository(bucket_id=profile.bucket_id)


@pytest.fixture
def selector_repos(
    tmp_path: Path,
) -> Iterator[tuple[WorkUnitCatalogueRepository, CalculationRevisionCatalogueRepository]]:
    """Yield real work-unit and calculation-revision repositories."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="modelo-revision-selector-test") as profile:
        objects = profile.repository
        yield WorkUnitCatalogueRepository(objects=objects), CalculationRevisionCatalogueRepository(objects=objects)


def _request(**overrides: object) -> ModeloWorkSelectorRequest:
    data: dict[str, object] = {
        "modelo": "130",
        "filing_year": 2026,
        "period": _P_2026_1T,
    }
    data.update(overrides)
    return ModeloWorkSelectorRequest.model_validate(data)


def _seed_work_unit(wu_repo: WorkUnitCatalogueRepository) -> WorkUnit:
    return create_work_unit(
        bucket_id=wu_repo.bucket_id or "modelo-revision-selector-test",
        modelo="130",
        filing_year=2026,
        period=_P_2026_1T,
        revision_id="2019-y-siguientes",
        repository=wu_repo,
        clock=_T0,
    )


def _seed_revision(
    cr_repo: CalculationRevisionCatalogueRepository,
    *,
    work_unit_id: str,
    state: CalculationRevisionState,
    created_at: datetime,
    output: Decimal,
) -> CalculationRevision:
    calculation_revision_id = derive_calculation_revision_id(
        work_unit_id=work_unit_id,
        inputs_snapshot={"01": str(output)},
        binding_overrides={},
        casilla_values={"01": output},
    )
    revision = CalculationRevision(
        calculation_revision_id=calculation_revision_id,
        work_unit_id=work_unit_id,
        state=state,
        inputs_snapshot={"01": str(output)},
        casilla_values={"01": output},
        created_at=created_at,
        updated_at=created_at,
        verified_at=created_at if state is not CalculationRevisionState.BORRADOR else None,
        verified_by="operator" if state is not CalculationRevisionState.BORRADOR else None,
        filed_at=created_at if state is CalculationRevisionState.PRESENTADO else None,
        filed_by="operator" if state is CalculationRevisionState.PRESENTADO else None,
    )
    cr_repo.save(upsert_calculation_revision(cr_repo.load(), revision))
    return revision


def test_selector_resolves_active_bucket_when_no_explicit_bucket(work_repo: WorkUnitCatalogueRepository) -> None:
    request = _request()
    assert resolve_modelo_work_bucket(request) == work_repo.bucket_id


def test_selector_honours_explicit_bucket_over_active_bucket(work_repo: WorkUnitCatalogueRepository) -> None:
    request = _request(bucket_id="explicit-bucket")
    assert resolve_modelo_work_bucket(request) == "explicit-bucket"


def test_visible_target_resolution_reports_absent_before_exact_creation(work_repo: WorkUnitCatalogueRepository) -> None:
    resolution = resolve_modelo_work_unit(_request(), repository=work_repo)

    assert resolution.state is ModeloWorkSelectorState.ABSENT
    assert resolution.work_unit is None
    assert resolution.bucket_id == work_repo.bucket_id
    assert resolution.modelo == "130"
    assert resolution.filing_year == 2026
    assert resolution.period == _P_2026_1T


def test_visible_target_resolution_ignores_discarded_work_units(work_repo: WorkUnitCatalogueRepository) -> None:
    unit = create_work_unit(
        bucket_id=work_repo.bucket_id or "modelo-selector-test",
        modelo="130",
        filing_year=2026,
        period=_P_2026_1T,
        revision_id="2019-y-siguientes",
        repository=work_repo,
        clock=_T0,
    )
    discarded = unit.model_copy(
        update={
            "state": WorkUnitState.DESCARTADO,
            "discarded_at": _T0 + timedelta(minutes=1),
            "discarded_by": "operator",
            "discard_reason": "abandoned draft",
            "updated_at": _T0 + timedelta(minutes=1),
        },
    )
    work_repo.save(upsert_work_unit(work_repo.load(), discarded))

    resolution = resolve_modelo_work_unit(_request(), repository=work_repo)
    assert resolution.state is ModeloWorkSelectorState.ABSENT
    assert visible_target_work_units(_request(), repository=work_repo) == ()


def test_visible_target_resolution_returns_single_active_work_unit(work_repo: WorkUnitCatalogueRepository) -> None:
    unit = create_work_unit(
        bucket_id=work_repo.bucket_id or "modelo-selector-test",
        modelo="130",
        filing_year=2026,
        period=_P_2026_1T,
        revision_id="2019-y-siguientes",
        repository=work_repo,
        clock=_T0,
    )

    resolution = resolve_modelo_work_unit(_request(), repository=work_repo)

    assert resolution.state is ModeloWorkSelectorState.RESOLVED
    assert resolution.work_unit == unit
    assert resolution.candidates[0].work_unit_id == unit.work_unit_id
    assert resolution.candidates[0].short_work_unit_id == unit.work_unit_id[-12:]


def test_explicit_work_unit_id_validates_supplied_natural_key_flags(work_repo: WorkUnitCatalogueRepository) -> None:
    unit = create_work_unit(
        bucket_id=work_repo.bucket_id or "modelo-selector-test",
        modelo="130",
        filing_year=2026,
        period=_P_2026_1T,
        revision_id="2019-y-siguientes",
        repository=work_repo,
        clock=_T0,
    )

    with pytest.raises(ModeloWorkSelectorContradictionError, match="filing_year=2025"):
        resolve_modelo_work_unit(
            _request(work_unit_id=unit.work_unit_id, filing_year=2025),
            repository=work_repo,
        )


def test_revision_conflict_refuses_before_exact_target_creation(work_repo: WorkUnitCatalogueRepository) -> None:
    unit = create_work_unit(
        bucket_id=work_repo.bucket_id or "modelo-selector-test",
        modelo="130",
        filing_year=2026,
        period=_P_2026_1T,
        revision_id="2019-y-siguientes",
        repository=work_repo,
        clock=_T0,
    )

    with pytest.raises(ModeloWorkRevisionConflictError) as raised:
        resolve_modelo_work_unit(
            _request(revision_id="future-revision"),
            repository=work_repo,
        )

    assert raised.value.requested_revision_id == "future-revision"
    assert raised.value.existing.work_unit_id == unit.work_unit_id
    assert raised.value.existing.revision_id == "2019-y-siguientes"


def test_visible_target_ambiguity_refuses_with_candidate_guidance(work_repo: WorkUnitCatalogueRepository) -> None:
    bucket_id = work_repo.bucket_id or "modelo-selector-test"
    first = create_work_unit(
        bucket_id=bucket_id,
        modelo="130",
        filing_year=2026,
        period=_P_2026_1T,
        revision_id="2019-y-siguientes",
        repository=work_repo,
        clock=_T0,
    )
    second_id = derive_work_unit_id(
        bucket_id=bucket_id,
        modelo="130",
        filing_year=2026,
        period=_P_2026_1T,
        revision_id="legacy-manual-revision",
    )
    second = WorkUnit(
        work_unit_id=second_id,
        bucket_id=bucket_id,
        modelo=cast(ModeloCode, "130"),
        filing_year=2026,
        period=_P_2026_1T,
        revision_id="legacy-manual-revision",
        name="legacy ambiguous unit",
        created_at=_T0 + timedelta(minutes=1),
        updated_at=_T0 + timedelta(minutes=1),
    )
    work_repo.save(upsert_work_unit(work_repo.load(), second))

    with pytest.raises(ModeloWorkVisibleTargetAmbiguousError) as raised:
        resolve_modelo_work_unit(_request(), repository=work_repo)

    candidate_ids = {candidate.work_unit_id for candidate in raised.value.candidates}
    assert candidate_ids == {first.work_unit_id, second.work_unit_id}
    assert {candidate.revision_id for candidate in raised.value.candidates} == {
        "2019-y-siguientes",
        "legacy-manual-revision",
    }
    assert all(candidate.short_work_unit_id == candidate.work_unit_id[-12:] for candidate in raised.value.candidates)


def test_revision_selectors_cover_current_latest_filed_and_explicit(
    selector_repos: tuple[WorkUnitCatalogueRepository, CalculationRevisionCatalogueRepository],
) -> None:
    wu_repo, cr_repo = selector_repos
    work_unit = _seed_work_unit(wu_repo)
    first_draft = _seed_revision(
        cr_repo,
        work_unit_id=work_unit.work_unit_id,
        state=CalculationRevisionState.BORRADOR,
        created_at=_T0 + timedelta(minutes=1),
        output=Decimal("10"),
    )
    latest_draft = _seed_revision(
        cr_repo,
        work_unit_id=work_unit.work_unit_id,
        state=CalculationRevisionState.BORRADOR,
        created_at=_T0 + timedelta(minutes=2),
        output=Decimal("20"),
    )
    verified = _seed_revision(
        cr_repo,
        work_unit_id=work_unit.work_unit_id,
        state=CalculationRevisionState.VERIFICADO_COMPLETO,
        created_at=_T0 + timedelta(minutes=3),
        output=Decimal("30"),
    )
    filed = _seed_revision(
        cr_repo,
        work_unit_id=work_unit.work_unit_id,
        state=CalculationRevisionState.PRESENTADO,
        created_at=_T0 + timedelta(minutes=4),
        output=Decimal("40"),
    )
    work_unit = work_unit.model_copy(
        update={
            "current_calculation_revision_id": latest_draft.calculation_revision_id,
            "filed_calculation_revision_id": filed.calculation_revision_id,
            "updated_at": _T0 + timedelta(minutes=5),
        },
    )
    wu_repo.save(upsert_work_unit(wu_repo.load(), work_unit))

    assert (
        select_modelo_calculation_revision(
            work_unit,
            selector=ModeloCalculationRevisionSelector.CURRENT,
            calculation_repository=cr_repo,
        ).revision
        == latest_draft
    )
    assert (
        select_modelo_calculation_revision(
            work_unit,
            selector=ModeloCalculationRevisionSelector.LATEST_DRAFT,
            calculation_repository=cr_repo,
        ).revision
        == latest_draft
    )
    assert (
        select_modelo_calculation_revision(
            work_unit,
            selector=ModeloCalculationRevisionSelector.LATEST_VERIFIED,
            calculation_repository=cr_repo,
        ).revision
        == verified
    )
    assert (
        select_modelo_calculation_revision(
            work_unit,
            selector=ModeloCalculationRevisionSelector.FILED,
            calculation_repository=cr_repo,
        ).revision
        == filed
    )
    assert (
        select_modelo_calculation_revision(
            work_unit,
            selector=ModeloCalculationRevisionSelector.EXPLICIT,
            calculation_revision_id=first_draft.calculation_revision_id,
            calculation_repository=cr_repo,
        ).revision
        == first_draft
    )


def test_current_command_specific_revision_selectors_enforce_state(
    selector_repos: tuple[WorkUnitCatalogueRepository, CalculationRevisionCatalogueRepository],
) -> None:
    wu_repo, cr_repo = selector_repos
    work_unit = _seed_work_unit(wu_repo)
    draft = _seed_revision(
        cr_repo,
        work_unit_id=work_unit.work_unit_id,
        state=CalculationRevisionState.BORRADOR,
        created_at=_T0 + timedelta(minutes=1),
        output=Decimal("10"),
    )
    verified = _seed_revision(
        cr_repo,
        work_unit_id=work_unit.work_unit_id,
        state=CalculationRevisionState.VERIFICADO_COMPLETO,
        created_at=_T0 + timedelta(minutes=2),
        output=Decimal("20"),
    )
    draft_current = work_unit.model_copy(update={"current_calculation_revision_id": draft.calculation_revision_id})
    verified_current = work_unit.model_copy(
        update={"current_calculation_revision_id": verified.calculation_revision_id},
    )

    assert select_current_draft_revision(draft_current, calculation_repository=cr_repo).revision == draft
    with pytest.raises(ModeloCalculationRevisionSelectorStateError, match="verification requires a draft"):
        select_current_draft_revision(verified_current, calculation_repository=cr_repo)

    assert select_current_verified_revision(verified_current, calculation_repository=cr_repo).revision == verified
    with pytest.raises(ModeloCalculationRevisionSelectorStateError, match="filing requires a verified"):
        select_current_verified_revision(draft_current, calculation_repository=cr_repo)


def test_exportable_revision_prefers_filed_then_current_verified(
    selector_repos: tuple[WorkUnitCatalogueRepository, CalculationRevisionCatalogueRepository],
) -> None:
    wu_repo, cr_repo = selector_repos
    work_unit = _seed_work_unit(wu_repo)
    verified = _seed_revision(
        cr_repo,
        work_unit_id=work_unit.work_unit_id,
        state=CalculationRevisionState.VERIFICADO_COMPLETO,
        created_at=_T0 + timedelta(minutes=1),
        output=Decimal("20"),
    )
    filed = _seed_revision(
        cr_repo,
        work_unit_id=work_unit.work_unit_id,
        state=CalculationRevisionState.PRESENTADO,
        created_at=_T0 + timedelta(minutes=2),
        output=Decimal("30"),
    )
    current_verified = work_unit.model_copy(
        update={"current_calculation_revision_id": verified.calculation_revision_id},
    )
    current_and_filed = current_verified.model_copy(
        update={"filed_calculation_revision_id": filed.calculation_revision_id},
    )

    assert select_exportable_revision(current_verified, calculation_repository=cr_repo).revision == verified
    assert select_exportable_revision(current_and_filed, calculation_repository=cr_repo).revision == filed


def test_exportable_revision_refuses_draft_current_and_ambiguous_verified(
    selector_repos: tuple[WorkUnitCatalogueRepository, CalculationRevisionCatalogueRepository],
) -> None:
    wu_repo, cr_repo = selector_repos
    work_unit = _seed_work_unit(wu_repo)
    draft = _seed_revision(
        cr_repo,
        work_unit_id=work_unit.work_unit_id,
        state=CalculationRevisionState.BORRADOR,
        created_at=_T0 + timedelta(minutes=1),
        output=Decimal("10"),
    )
    verified_a = _seed_revision(
        cr_repo,
        work_unit_id=work_unit.work_unit_id,
        state=CalculationRevisionState.VERIFICADO_COMPLETO,
        created_at=_T0 + timedelta(minutes=2),
        output=Decimal("20"),
    )
    verified_b = _seed_revision(
        cr_repo,
        work_unit_id=work_unit.work_unit_id,
        state=CalculationRevisionState.VERIFICADO_COMPLETO,
        created_at=_T0 + timedelta(minutes=3),
        output=Decimal("30"),
    )
    draft_current = work_unit.model_copy(update={"current_calculation_revision_id": draft.calculation_revision_id})

    with pytest.raises(ModeloCalculationRevisionSelectorStateError, match="still draft"):
        select_exportable_revision(draft_current, calculation_repository=cr_repo)

    with pytest.raises(ModeloCalculationRevisionSelectorAmbiguousError) as raised:
        select_exportable_revision(work_unit, calculation_repository=cr_repo)
    assert {candidate.calculation_revision_id for candidate in raised.value.candidates} == {
        verified_a.calculation_revision_id,
        verified_b.calculation_revision_id,
    }


def test_addressed_revision_policy_resolvers_enforce_command_specific_state(
    selector_repos: tuple[WorkUnitCatalogueRepository, CalculationRevisionCatalogueRepository],
) -> None:
    wu_repo, cr_repo = selector_repos
    work_unit = _seed_work_unit(wu_repo)
    draft = _seed_revision(
        cr_repo,
        work_unit_id=work_unit.work_unit_id,
        state=CalculationRevisionState.BORRADOR,
        created_at=_T0 + timedelta(minutes=1),
        output=Decimal("10"),
    )
    verified = _seed_revision(
        cr_repo,
        work_unit_id=work_unit.work_unit_id,
        state=CalculationRevisionState.VERIFICADO_COMPLETO,
        created_at=_T0 + timedelta(minutes=2),
        output=Decimal("20"),
    )
    filed = _seed_revision(
        cr_repo,
        work_unit_id=work_unit.work_unit_id,
        state=CalculationRevisionState.PRESENTADO,
        created_at=_T0 + timedelta(minutes=3),
        output=Decimal("30"),
    )
    current_draft = work_unit.model_copy(
        update={
            "current_calculation_revision_id": draft.calculation_revision_id,
            "filed_calculation_revision_id": filed.calculation_revision_id,
        },
    )
    wu_repo.save(upsert_work_unit(wu_repo.load(), current_draft))
    address = ModeloWorkAddress(modelo="130", filing_year=2026, period=_P_2026_1T)

    assert resolve_verifiable_modelo_calculation_revision_address(address=address) == draft
    assert (
        resolve_fileable_modelo_calculation_revision_address(
            address=address,
            selector=ModeloCalculationRevisionSelector.LATEST_VERIFIED,
        )
        == verified
    )
    assert resolve_exportable_modelo_calculation_revision_address(address=address) == filed

    with pytest.raises(ModeloCalculationRevisionSelectorStateError, match="verification requires borrador"):
        resolve_verifiable_modelo_calculation_revision_address(
            address=ModeloWorkAddress(),
            calculation_revision_id=verified.calculation_revision_id,
        )
    with pytest.raises(ModeloCalculationRevisionSelectorStateError, match="filing requires verificado_completo"):
        resolve_fileable_modelo_calculation_revision_address(
            address=address,
            selector=ModeloCalculationRevisionSelector.LATEST_DRAFT,
        )

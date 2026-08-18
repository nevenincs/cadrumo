"""Real-behavior tests for modelo work-unit application selectors."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import cast

import pytest
from pydantic import ValidationError

from ....adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from ....adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from ....adapters.persistence.storage.sql import SecureObjectRepository
from ....core import CasillaId, Period, validated_casilla_id
from ....domain.modelos import (
    CalculationRevision,
    CalculationRevisionState,
    ModeloCode,
    WorkUnit,
    WorkUnitState,
    derive_calculation_revision_id,
    derive_work_unit_id,
    upsert_calculation_revision,
    upsert_work_unit,
)
from ....domain.user_profile import ProfileSetupState, UserProfileFact, UserProfileRecord
from ....tests.profile_capsule import seed_test_profile_record
from ....tests.registry_observations import registry_grounded_observations
from ....tests.secure_sql import isolated_runtime_profile
from .. import create_work_unit
from .._action_errors import CalculationRevisionStateError
from .._selectors import (
    ModeloCalculationRevisionSelector,
    ModeloCalculationRevisionSelectorAmbiguousError,
    ModeloCalculationRevisionSelectorStateError,
    ModeloWorkRevisionConflictError,
    ModeloWorkSelectorContradictionError,
    ModeloWorkSelectorRequest,
    ModeloWorkSelectorState,
    ModeloWorkVisibleTargetAmbiguousError,
    active_natural_target_work_units,
    natural_target_work_units,
    resolve_modelo_calculation_revision_pick,
    resolve_modelo_work_bucket,
    resolve_modelo_work_unit,
    select_current_verified_revision,
    select_exportable_revision,
    select_modelo_calculation_revision,
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
_SELECTOR_PROFILE_ID = "13000000-0000-4000-8000-000000000130"
_REVISION_SELECTOR_PROFILE_ID = "13000000-0000-4000-8000-000000000131"
_EXPLICIT_PROFILE_ID = "13000000-0000-4000-8000-000000000132"
_READY_PROFILE_FACTS: tuple[UserProfileFact, ...] = (
    UserProfileFact(path="identity.tax_id", value="00000000T"),
    UserProfileFact(path="identity.name", value="Test Operator"),
    UserProfileFact(path="identity.surnames", value="Modelo Selector"),
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


def _seed_ready_profile(objects: SecureObjectRepository, *, bucket_id: str) -> None:
    seed_test_profile_record(
        UserProfileRecord(setup_state=ProfileSetupState.COMPLETE,
            profile_id=bucket_id,
            facts=_READY_PROFILE_FACTS,
            created_at=_T0,
            updated_at=_T0,
        ),
    )


_OUTPUT_CASILLA: CasillaId = validated_casilla_id("01")


@pytest.fixture
def work_repo(tmp_path: Path) -> Iterator[WorkUnitCatalogueRepository]:
    """Yield the real work-unit repository through isolated profile storage."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_SELECTOR_PROFILE_ID) as profile:
        _seed_ready_profile(profile.repository, bucket_id=profile.bucket_id)
        yield WorkUnitCatalogueRepository(bucket_id=profile.bucket_id)


@pytest.fixture
def selector_repos(
    tmp_path: Path,
) -> Iterator[tuple[WorkUnitCatalogueRepository, CalculationRevisionCatalogueRepository]]:
    """Yield real work-unit and calculation-revision repositories."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_REVISION_SELECTOR_PROFILE_ID) as profile:
        objects = profile.repository
        _seed_ready_profile(objects, bucket_id=profile.bucket_id)
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
        bucket_id=wu_repo.bucket_id or _REVISION_SELECTOR_PROFILE_ID,
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
        input_values_by_casilla_id={_OUTPUT_CASILLA: str(output)},
        binding_overrides={},
        casilla_values={_OUTPUT_CASILLA: output},
        filing_instance_evidence=None,
    )
    revision = CalculationRevision(
        calculation_revision_id=calculation_revision_id,
        work_unit_id=work_unit_id,
        state=state,
        input_values_by_casilla_id={_OUTPUT_CASILLA: str(output)},
        casilla_values={_OUTPUT_CASILLA: output},
        observations=registry_grounded_observations(
            modelo="130",
            filing_year=2026,
            period=_P_2026_1T.registry_token,
            casilla_values={_OUTPUT_CASILLA: output},
        ),
        created_at=created_at,
        updated_at=created_at,
        verified_at=created_at if state is not CalculationRevisionState.BORRADOR else None,
        verified_by="operator" if state is not CalculationRevisionState.BORRADOR else None,
        filed_at=created_at if state is CalculationRevisionState.PRESENTADO else None,
        filed_by="operator" if state is CalculationRevisionState.PRESENTADO else None,
        filing_instance_evidence=None,
    )
    cr_repo.save(upsert_calculation_revision(cr_repo.load(), revision))
    return revision


def test_selector_resolves_active_bucket_when_no_explicit_bucket(work_repo: WorkUnitCatalogueRepository) -> None:
    request = _request()
    assert resolve_modelo_work_bucket(request) == work_repo.bucket_id


def test_selector_honours_explicit_bucket_over_active_bucket(work_repo: WorkUnitCatalogueRepository) -> None:
    request = _request(bucket_id=_EXPLICIT_PROFILE_ID)
    assert resolve_modelo_work_bucket(request) == _EXPLICIT_PROFILE_ID


def test_visible_target_resolution_reports_absent_before_exact_creation(work_repo: WorkUnitCatalogueRepository) -> None:
    resolution = resolve_modelo_work_unit(_request(), repository=work_repo)

    assert resolution.state is ModeloWorkSelectorState.ABSENT
    assert resolution.work_unit is None
    assert resolution.bucket_id == work_repo.bucket_id
    assert resolution.modelo == "130"
    assert resolution.filing_year == 2026
    assert resolution.period == _P_2026_1T


def test_natural_target_resolution_retains_discarded_work_units_for_terminal_state_handling(
    work_repo: WorkUnitCatalogueRepository,
) -> None:
    unit = create_work_unit(
        bucket_id=work_repo.bucket_id or _SELECTOR_PROFILE_ID,
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
    assert resolution.state is ModeloWorkSelectorState.RESOLVED
    assert resolution.work_unit == discarded
    assert natural_target_work_units(_request(), repository=work_repo) == (discarded,)
    assert active_natural_target_work_units(_request(), repository=work_repo) == ()


def test_visible_target_resolution_returns_single_active_work_unit(work_repo: WorkUnitCatalogueRepository) -> None:
    unit = create_work_unit(
        bucket_id=work_repo.bucket_id or _SELECTOR_PROFILE_ID,
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


def test_explicit_work_unit_id_accepts_displayed_short_id(work_repo: WorkUnitCatalogueRepository) -> None:
    unit = _seed_work_unit(work_repo)

    resolution = resolve_modelo_work_unit(
        ModeloWorkSelectorRequest(work_unit_id=unit.work_unit_id[-12:]),
        repository=work_repo,
    )

    assert resolution.state is ModeloWorkSelectorState.RESOLVED
    assert resolution.work_unit == unit


def test_work_unit_id_selector_refuses_abbreviations_shorter_than_the_displayed_id() -> None:
    """Mutable work may be addressed only by the published 12-char handle or full id."""
    with pytest.raises(ValidationError, match="work_unit_id"):
        ModeloWorkSelectorRequest(work_unit_id="a")


def test_explicit_work_unit_id_validates_supplied_natural_key_flags(work_repo: WorkUnitCatalogueRepository) -> None:
    unit = create_work_unit(
        bucket_id=work_repo.bucket_id or _SELECTOR_PROFILE_ID,
        modelo="130",
        filing_year=2026,
        period=_P_2026_1T,
        revision_id="2019-y-siguientes",
        repository=work_repo,
        clock=_T0,
    )

    with pytest.raises(ModeloWorkSelectorContradictionError):
        resolve_modelo_work_unit(
            _request(work_unit_id=unit.work_unit_id, filing_year=2025),
            repository=work_repo,
        )


def test_revision_conflict_refuses_before_exact_target_creation(work_repo: WorkUnitCatalogueRepository) -> None:
    unit = create_work_unit(
        bucket_id=work_repo.bucket_id or _SELECTOR_PROFILE_ID,
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
    bucket_id = work_repo.bucket_id or _SELECTOR_PROFILE_ID
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
        revision_id="manual-revision",
    )
    second = WorkUnit(
        work_unit_id=second_id,
        bucket_id=bucket_id,
        modelo=cast(ModeloCode, "130"),
        filing_year=2026,
        period=_P_2026_1T,
        revision_id="manual-revision",
        name="manual ambiguous unit",
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
        "manual-revision",
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

    # The verify pick no longer gates draft at the selector layer: it returns the
    # current revision in ANY state so an already-verified revision reaches
    # verify_modelo_revision's idempotent collapse
    # (aeat-cli-contract) instead of being refused
    # upstream. State policy for verify lives in the application action.
    assert (
        resolve_modelo_calculation_revision_pick(
            draft_current,
            default_for="verify",
            calculation_repository=cr_repo,
        ).revision
        == draft
    )
    assert (
        resolve_modelo_calculation_revision_pick(
            verified_current,
            default_for="verify",
            calculation_repository=cr_repo,
        ).revision
        == verified
    )

    assert select_current_verified_revision(verified_current, calculation_repository=cr_repo).revision == verified
    with pytest.raises(ModeloCalculationRevisionSelectorStateError):
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

    with pytest.raises(ModeloCalculationRevisionSelectorStateError):
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

    # The verify resolver no longer gates state: an explicitly-addressed verified
    # revision is returned (not refused) so verify_modelo_revision can collapse it
    # to its existing granting report (aeat-cli-contract).
    assert (
        resolve_verifiable_modelo_calculation_revision_address(
            address=ModeloWorkAddress(),
            calculation_revision_id=verified.calculation_revision_id,
        )
        == verified
    )
    with pytest.raises(CalculationRevisionStateError) as raised:
        resolve_fileable_modelo_calculation_revision_address(
            address=address,
            selector=ModeloCalculationRevisionSelector.LATEST_DRAFT,
        )
    failure = raised.value.precondition_failure
    assert failure is not None
    assert failure.scenario_id == "modelo.work.file.calculation_revision.unverified"
    assert raised.value.terminal_precondition_verdict is failure.verdict
    assert failure.verdict.action is not None
    assert failure.verdict.action.action_id == "operator.modelo.work.verify"
    assert failure.verdict.argument_bindings[0].value == work_unit.work_unit_id

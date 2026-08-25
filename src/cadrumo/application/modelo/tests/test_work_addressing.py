"""Real-behavior tests for centralized modelo work addressing facades."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Literal

import pytest

from ....adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from ....adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from ....adapters.persistence.storage.sql import SecureObjectRepository
from ....core import (
    ActionArgumentSource,
    ActionConditionality,
    CasillaId,
    NoRecoveryOutcome,
    Period,
    validated_casilla_id,
)
from ....domain.modelos import (
    CalculationRevision,
    CalculationRevisionState,
    WorkUnit,
    derive_calculation_revision_id,
    upsert_calculation_revision,
    upsert_work_unit,
)
from ....domain.user_profile.values import ProfileSetupState, UserProfileFact, UserProfileRecord
from ....tests.profile_capsule import seed_test_profile_record
from ....tests.registry_observations import registry_grounded_observations
from ....tests.secure_sql import isolated_runtime_profile
from .. import (
    CalculationRevisionNotFoundError,
    ModeloCalculationRevisionSelector,
    ModeloExactWorkUnitTarget,
    ModeloRevisionPick,
    ModeloVisibleFilingTarget,
    create_work_unit,
    discard_work_unit,
    project_modelo_work_target,
    resolve_modelo_revision_for_operator_target,
    resolve_modelo_revision_pick,
    resolve_modelo_work_unit_id,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_T0 = datetime(2026, 6, 5, 9, 0, 0, tzinfo=UTC)
_ADDRESSING_PROFILE_ID = "13000000-0000-4000-8000-000000000230"
_READY_PROFILE_FACTS: tuple[UserProfileFact, ...] = (
    UserProfileFact(path="identity.tax_id", value="00000000T"),
    UserProfileFact(path="identity.name", value="Test Operator"),
    UserProfileFact(path="identity.surnames", value="Modelo Work"),
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
        UserProfileRecord(
            setup_state=ProfileSetupState.COMPLETE,
            profile_id=bucket_id,
            facts=_READY_PROFILE_FACTS,
            created_at=_T0,
            updated_at=_T0,
        ),
    )


_OUTPUT_CASILLA: CasillaId = validated_casilla_id("01")


@pytest.fixture
def addressing_repos(
    tmp_path: Path,
) -> Iterator[tuple[str, WorkUnitCatalogueRepository, CalculationRevisionCatalogueRepository]]:
    """Yield real repositories over one isolated runtime profile."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_ADDRESSING_PROFILE_ID) as profile:
        objects = profile.repository
        _seed_ready_profile(objects, bucket_id=profile.bucket_id)
        yield (
            profile.bucket_id,
            WorkUnitCatalogueRepository(objects=objects),
            CalculationRevisionCatalogueRepository(objects=objects),
        )


def _seed_work_unit(
    repository: WorkUnitCatalogueRepository,
    *,
    bucket_id: str,
    clock: datetime = _T0,
) -> WorkUnit:
    return create_work_unit(
        bucket_id=bucket_id,
        modelo="130",
        filing_year=2026,
        period=Period.from_year_and_code(2026, "1T"),
        revision_id="2019-y-siguientes",
        repository=repository,
        clock=clock,
    )


def _seed_revision(
    repository: CalculationRevisionCatalogueRepository,
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
        source_provenance=(),
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
            period="1T",
            casilla_values={_OUTPUT_CASILLA: output},
        ),
        created_at=created_at,
        updated_at=created_at,
        verified_at=created_at if state is not CalculationRevisionState.BORRADOR else None,
        verified_by="operator" if state is not CalculationRevisionState.BORRADOR else None,
        filed_at=created_at if state is CalculationRevisionState.PRESENTADO else None,
        filed_by="operator" if state is CalculationRevisionState.PRESENTADO else None,
        filing_instance_evidence=None,
        source_provenance=(),
    )
    repository.save(upsert_calculation_revision(repository.load(), revision))
    return revision


def test_visible_and_exact_work_targets_round_trip_to_same_work_unit(
    addressing_repos: tuple[str, WorkUnitCatalogueRepository, CalculationRevisionCatalogueRepository],
) -> None:
    bucket_id, work_repository, calculation_repository = addressing_repos
    work_unit = _seed_work_unit(work_repository, bucket_id=bucket_id)
    draft = _seed_revision(
        calculation_repository,
        work_unit_id=work_unit.work_unit_id,
        state=CalculationRevisionState.BORRADOR,
        created_at=_T0 + timedelta(minutes=1),
        output=Decimal("10"),
    )
    work_repository.save(
        upsert_work_unit(
            work_repository.load(),
            work_unit.model_copy(update={"current_calculation_revision_id": draft.calculation_revision_id}),
        ),
    )

    visible = ModeloVisibleFilingTarget(
        modelo="130",
        filing_year=2026,
        period=Period.from_year_and_code(2026, "1T"),
        bucket_id=bucket_id,
    )
    exact = ModeloExactWorkUnitTarget(work_unit_id=work_unit.work_unit_id, bucket_id=bucket_id)

    assert resolve_modelo_work_unit_id(visible) == work_unit.work_unit_id
    assert resolve_modelo_work_unit_id(exact) == work_unit.work_unit_id

    projected = project_modelo_work_target(visible)
    assert projected.work_unit_id == work_unit.work_unit_id
    assert projected.short_work_unit_id == work_unit.work_unit_id[-12:]
    assert projected.modelo == "130"
    assert projected.filing_year == 2026
    assert projected.period == Period.from_year_and_code(2026, "1T")

    current_pick = resolve_modelo_revision_pick(target=visible, pick=ModeloRevisionPick(default_for="verify"))
    assert current_pick.calculation_revision_id == draft.calculation_revision_id
    assert current_pick.work_unit_id == work_unit.work_unit_id
    assert current_pick.short_calculation_revision_id == draft.calculation_revision_id[-12:]

    explicit_pick = resolve_modelo_revision_pick(
        target=exact,
        pick=ModeloRevisionPick.explicit(draft.calculation_revision_id),
    )
    assert explicit_pick.calculation_revision_id == draft.calculation_revision_id
    assert explicit_pick.work_unit_id == work_unit.work_unit_id
    assert explicit_pick.selector is ModeloCalculationRevisionSelector.EXPLICIT


def test_revision_pick_defaults_are_command_specific_under_one_work_unit(
    addressing_repos: tuple[str, WorkUnitCatalogueRepository, CalculationRevisionCatalogueRepository],
) -> None:
    bucket_id, work_repository, calculation_repository = addressing_repos
    work_unit = _seed_work_unit(work_repository, bucket_id=bucket_id)
    draft = _seed_revision(
        calculation_repository,
        work_unit_id=work_unit.work_unit_id,
        state=CalculationRevisionState.BORRADOR,
        created_at=_T0 + timedelta(minutes=1),
        output=Decimal("10"),
    )
    verified = _seed_revision(
        calculation_repository,
        work_unit_id=work_unit.work_unit_id,
        state=CalculationRevisionState.VERIFICADO_COMPLETO,
        created_at=_T0 + timedelta(minutes=2),
        output=Decimal("20"),
    )
    filed = _seed_revision(
        calculation_repository,
        work_unit_id=work_unit.work_unit_id,
        state=CalculationRevisionState.PRESENTADO,
        created_at=_T0 + timedelta(minutes=3),
        output=Decimal("30"),
    )
    visible = ModeloVisibleFilingTarget(
        modelo="130",
        filing_year=2026,
        period=Period.from_year_and_code(2026, "1T"),
        bucket_id=bucket_id,
    )
    work_repository.save(
        upsert_work_unit(
            work_repository.load(),
            work_unit.model_copy(
                update={
                    "current_calculation_revision_id": draft.calculation_revision_id,
                    "filed_calculation_revision_id": filed.calculation_revision_id,
                },
            ),
        ),
    )

    verify_pick = resolve_modelo_revision_pick(target=visible, pick=ModeloRevisionPick(default_for="verify"))
    export_pick = resolve_modelo_revision_pick(target=visible, pick=ModeloRevisionPick(default_for="export"))

    assert verify_pick.calculation_revision_id == draft.calculation_revision_id
    assert export_pick.calculation_revision_id == filed.calculation_revision_id

    work_repository.save(
        upsert_work_unit(
            work_repository.load(),
            work_unit.model_copy(
                update={
                    "current_calculation_revision_id": verified.calculation_revision_id,
                    "filed_calculation_revision_id": None,
                },
            ),
        ),
    )

    file_pick = resolve_modelo_revision_pick(target=visible, pick=ModeloRevisionPick(default_for="file"))
    assert file_pick.calculation_revision_id == verified.calculation_revision_id
    assert file_pick.work_unit_id == work_unit.work_unit_id


@pytest.mark.parametrize(
    ("default_for", "subject_leaf_key"),
    (("verify", "modelo.work.verify"), ("file", "modelo.work.file")),
)
def test_exact_work_unit_id_in_calculation_revision_slot_has_only_the_canonical_calculate_action(
    addressing_repos: tuple[str, WorkUnitCatalogueRepository, CalculationRevisionCatalogueRepository],
    default_for: Literal["verify", "file"],
    subject_leaf_key: str,
) -> None:
    """The application, rather than the CLI, recognizes the exact persisted work-unit identity."""
    bucket_id, work_repository, _calculation_repository = addressing_repos
    work_unit = _seed_work_unit(work_repository, bucket_id=bucket_id)

    with pytest.raises(CalculationRevisionNotFoundError) as raised:
        resolve_modelo_revision_for_operator_target(
            calculation_revision_id=work_unit.work_unit_id,
            work_unit_id=None,
            modelo=None,
            year=None,
            period=None,
            registry_revision_id=None,
            selector=ModeloCalculationRevisionSelector.CURRENT,
            default_for=default_for,
        )

    failure = raised.value.precondition_failure
    assert failure is not None
    assert failure.subject_leaf_key == subject_leaf_key
    assert failure.scenario_id == f"{subject_leaf_key}.calculation_revision.work_unit_target"
    verdict = failure.verdict
    assert verdict.failed_condition_id == f"{subject_leaf_key}.calculation_revision.addresses_calculation"
    assert verdict.conditionality is ActionConditionality.IMMEDIATE
    assert verdict.no_recovery_outcome is None
    assert verdict.action is not None
    assert verdict.action.action_id == "operator.modelo.work.calculate"
    assert len(verdict.argument_bindings) == 1
    binding = verdict.argument_bindings[0]
    assert binding.argument_name == "work_unit_id"
    assert binding.value == work_unit.work_unit_id
    assert binding.source is ActionArgumentSource.VERDICT_CONTEXT
    assert binding.source_key == "work_unit_id"


@pytest.mark.parametrize(
    ("default_for", "revision_state"),
    (
        ("verify", CalculationRevisionState.BORRADOR),
        ("file", CalculationRevisionState.VERIFICADO_COMPLETO),
    ),
)
def test_positional_work_unit_id_resolves_its_current_revision_after_calculation(
    addressing_repos: tuple[str, WorkUnitCatalogueRepository, CalculationRevisionCatalogueRepository],
    default_for: Literal["verify", "file"],
    revision_state: CalculationRevisionState,
) -> None:
    """The declared calculate recovery makes the unchanged verify/file selector executable."""
    bucket_id, work_repository, calculation_repository = addressing_repos
    work_unit = _seed_work_unit(work_repository, bucket_id=bucket_id)
    revision = _seed_revision(
        calculation_repository,
        work_unit_id=work_unit.work_unit_id,
        state=revision_state,
        created_at=_T0 + timedelta(minutes=1),
        output=Decimal("10"),
    )
    work_repository.save(
        upsert_work_unit(
            work_repository.load(),
            work_unit.model_copy(update={"current_calculation_revision_id": revision.calculation_revision_id}),
        ),
    )

    resolved = resolve_modelo_revision_for_operator_target(
        calculation_revision_id=work_unit.work_unit_id,
        work_unit_id=None,
        modelo=None,
        year=None,
        period=None,
        registry_revision_id=None,
        selector=ModeloCalculationRevisionSelector.CURRENT,
        default_for=default_for,
    )

    assert resolved == revision
    assert resolved.work_unit_id == work_unit.work_unit_id


@pytest.mark.parametrize(
    ("default_for", "subject_leaf_key"),
    (("verify", "modelo.work.verify"), ("file", "modelo.work.file")),
)
def test_discarded_work_unit_id_in_calculation_revision_slot_is_a_terminal_application_verdict(
    addressing_repos: tuple[str, WorkUnitCatalogueRepository, CalculationRevisionCatalogueRepository],
    default_for: Literal["verify", "file"],
    subject_leaf_key: str,
) -> None:
    """A discarded work unit cannot be advertised as a calculable recovery target."""
    bucket_id, work_repository, _calculation_repository = addressing_repos
    work_unit = _seed_work_unit(work_repository, bucket_id=bucket_id)
    discard_work_unit(
        work_unit.work_unit_id,
        actor="operator",
        reason="test terminal selector state",
        repository=work_repository,
        clock=_T0 + timedelta(minutes=1),
    )

    with pytest.raises(CalculationRevisionNotFoundError) as raised:
        resolve_modelo_revision_for_operator_target(
            calculation_revision_id=work_unit.work_unit_id,
            work_unit_id=None,
            modelo=None,
            year=None,
            period=None,
            registry_revision_id=None,
            selector=ModeloCalculationRevisionSelector.CURRENT,
            default_for=default_for,
        )

    failure = raised.value.precondition_failure
    assert failure is not None
    assert failure.subject_leaf_key == subject_leaf_key
    assert failure.scenario_id == f"{subject_leaf_key}.calculation_revision.work_unit_target_discarded"
    verdict = failure.verdict
    assert verdict.failed_condition_id == f"{subject_leaf_key}.calculation_revision.addresses_calculation"
    assert verdict.conditionality is ActionConditionality.NOT_APPLICABLE
    assert verdict.action is None
    assert verdict.argument_bindings == ()
    assert verdict.missing_argument_names == ()
    assert verdict.no_recovery_outcome is NoRecoveryOutcome.TERMINAL

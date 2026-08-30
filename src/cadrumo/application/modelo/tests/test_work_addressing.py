"""Real-behavior tests for centralized modelo work addressing facades."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Literal

import pytest
from sqlalchemy import event

from ....adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from ....adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from ....adapters.persistence.storage.sql import SecureObjectRepository
from ....core.operator_action_enums import ActionArgumentSource, ActionConditionality, NoRecoveryOutcome
from ....core.period import Period
from ....core.casilla_id import CasillaId, validated_casilla_id
from ....domain.modelos.calculation_repository import upsert_calculation_revision
from ....domain.modelos.repository import upsert_work_unit
from ....domain.modelos.work_unit import WorkUnit, WorkUnitCatalogue, derive_work_unit_id
from ....domain.modelos.calculation_revision import (
    CalculationRevision,
    CalculationRevisionState,
    derive_calculation_revision_id,
)
from ....domain.user_profile.values import ProfileSetupState, UserProfileFact, UserProfileRecord
from ....tests.profile_capsule import seed_test_profile_record
from ....tests.registry_observations import registry_grounded_observations
from ....tests.secure_sql import isolated_runtime_profile
from .._action_errors import CalculationRevisionNotFoundError
from .._selectors import ModeloCalculationRevisionSelector
from ..work_lifecycle import (
    create_work_unit,
    discard_work_unit,
)
from ..work_addressing import (
    ModeloExactWorkUnitTarget,
    ModeloRevisionPick,
    ModeloVisibleFilingTarget,
    ModeloWorkCapture,
    ModeloWorkCaptureError,
    ModeloWorkCurrentCoordinate,
    ModeloWorkSelectorRequest,
    ModeloWorkSelectorState,
    capture_modelo_work_resolution,
    project_modelo_work_target,
    read_modelo_work_current_coordinate,
    resolve_modelo_revision_for_operator_target,
    resolve_modelo_revision_pick,
    resolve_modelo_work_unit_id,
    select_modelo_work_resolution,
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


def test_captured_catalogue_selector_uses_no_second_encrypted_sql_read_after_mutation(tmp_path: Path) -> None:
    """Selection stays on one encrypted-SQL capture after the persisted singleton changes."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_ADDRESSING_PROFILE_ID) as profile:
        _seed_ready_profile(profile.repository, bucket_id=profile.bucket_id)
        repository = WorkUnitCatalogueRepository(objects=profile.repository)
        first = _seed_work_unit(repository, bucket_id=profile.bucket_id)
        captured, _revision_id = repository.load_revisioned()
        second_revision_id = "2019-y-siguientes-post-capture"
        second_payload = first.model_dump()
        second_payload.update(
            work_unit_id=derive_work_unit_id(
                bucket_id=first.bucket_id,
                modelo=first.modelo,
                filing_year=first.filing_year,
                period=first.period,
                revision_id=second_revision_id,
            ),
            revision_id=second_revision_id,
            name="130-2026-1T-post-capture",
            created_at=_T0 + timedelta(seconds=1),
            updated_at=_T0 + timedelta(seconds=1),
        )
        second = WorkUnit(**second_payload)
        repository.save(WorkUnitCatalogue.from_work_units((first, second)))

        selects: list[str] = []

        def _record_secure_object_select(
            _connection: object,
            _cursor: object,
            statement: str,
            _parameters: object,
            _context: object,
            _executemany: bool,
        ) -> None:
            normalized = " ".join(statement.split()).upper()
            if normalized.startswith("SELECT") and " FROM SECURE_OBJECTS " in f" {normalized} ":
                selects.append(statement)

        event.listen(profile.repository.engine, "after_cursor_execute", _record_secure_object_select)
        try:
            resolution = select_modelo_work_resolution(
                ModeloWorkSelectorRequest(
                    bucket_id=profile.bucket_id,
                    modelo="130",
                    filing_year=2026,
                    period=Period.from_year_and_code(2026, "1T"),
                ),
                catalogue=captured,
                bucket_id=profile.bucket_id,
            )
        finally:
            event.remove(profile.repository.engine, "after_cursor_execute", _record_secure_object_select)

    assert selects == []
    assert resolution.state is ModeloWorkSelectorState.RESOLVED
    assert resolution.work_unit == first


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

    catalogue = work_repository.load()
    assert resolve_modelo_work_unit_id(visible, catalogue=catalogue, bucket_id=bucket_id) == work_unit.work_unit_id
    assert resolve_modelo_work_unit_id(exact, catalogue=catalogue, bucket_id=bucket_id) == work_unit.work_unit_id

    projected = project_modelo_work_target(visible, catalogue=catalogue, bucket_id=bucket_id)
    assert projected.work_unit_id == work_unit.work_unit_id
    assert projected.short_work_unit_id == work_unit.work_unit_id[-12:]
    assert projected.modelo == "130"
    assert projected.filing_year == 2026
    assert projected.period == Period.from_year_and_code(2026, "1T")

    current_pick = resolve_modelo_revision_pick(
        target=visible,
        pick=ModeloRevisionPick(default_for="verify"),
        catalogue=catalogue,
        resolved_bucket_id=bucket_id,
    )
    assert current_pick.calculation_revision_id == draft.calculation_revision_id
    assert current_pick.work_unit_id == work_unit.work_unit_id
    assert current_pick.short_calculation_revision_id == draft.calculation_revision_id[-12:]

    explicit_pick = resolve_modelo_revision_pick(
        target=exact,
        pick=ModeloRevisionPick.explicit(draft.calculation_revision_id),
        catalogue=catalogue,
        resolved_bucket_id=bucket_id,
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

    catalogue = work_repository.load()
    verify_pick = resolve_modelo_revision_pick(
        target=visible,
        pick=ModeloRevisionPick(default_for="verify"),
        catalogue=catalogue,
        resolved_bucket_id=bucket_id,
    )
    export_pick = resolve_modelo_revision_pick(
        target=visible,
        pick=ModeloRevisionPick(default_for="export"),
        catalogue=catalogue,
        resolved_bucket_id=bucket_id,
    )

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

    file_pick = resolve_modelo_revision_pick(
        target=visible,
        pick=ModeloRevisionPick(default_for="file"),
        catalogue=work_repository.load(),
        resolved_bucket_id=bucket_id,
    )
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
            catalogue=work_repository.load(),
            resolved_bucket_id=bucket_id,
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
        catalogue=work_repository.load(),
        resolved_bucket_id=bucket_id,
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
            catalogue=work_repository.load(),
            resolved_bucket_id=bucket_id,
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


def _capture_period() -> Period:
    return Period.from_year_and_code(2026, "1T")


def _capture_request(bucket_id: str | None) -> ModeloWorkSelectorRequest:
    return ModeloWorkSelectorRequest(bucket_id=bucket_id, modelo="130", filing_year=2026, period=_capture_period())


def _capture_source_imports() -> str:
    """Return the capture region source so a registry reach would be visible."""
    import inspect

    from .. import work_addressing

    return "".join(
        inspect.getsource(member)
        for member in (
            work_addressing.capture_modelo_work_resolution,
            work_addressing.read_modelo_work_current_coordinate,
            work_addressing._work_capture_observation,
        )
    )


def test_work_capture_is_singleflight_for_one_unchanged_observation(tmp_path: Path) -> None:
    """Two captures over one unchanged catalogue share their generation."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_ADDRESSING_PROFILE_ID) as profile:
        _seed_ready_profile(profile.repository, bucket_id=profile.bucket_id)
        repository = WorkUnitCatalogueRepository(objects=profile.repository)
        _seed_work_unit(repository, bucket_id=profile.bucket_id)
        request = _capture_request(profile.bucket_id)

        first = capture_modelo_work_resolution(request, catalogue_repository=repository)
        second = capture_modelo_work_resolution(request, catalogue_repository=repository)

        assert first.generation == second.generation
        assert first.comparison_domain == second.comparison_domain
        coordinate = read_modelo_work_current_coordinate(request, catalogue_repository=repository)
        assert first.require_current(coordinate) is first


def test_work_capture_generation_advances_and_refuses_a_superseded_capture(tmp_path: Path) -> None:
    """A catalogue write supersedes an earlier capture through its coordinate."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_ADDRESSING_PROFILE_ID) as profile:
        _seed_ready_profile(profile.repository, bucket_id=profile.bucket_id)
        repository = WorkUnitCatalogueRepository(objects=profile.repository)
        first_unit = _seed_work_unit(repository, bucket_id=profile.bucket_id)
        request = _capture_request(profile.bucket_id)
        stale = capture_modelo_work_resolution(request, catalogue_repository=repository)

        successor_revision_id = "2019-y-siguientes-successor"
        payload = first_unit.model_dump()
        payload.update(
            work_unit_id=derive_work_unit_id(
                bucket_id=first_unit.bucket_id,
                modelo=first_unit.modelo,
                filing_year=first_unit.filing_year,
                period=first_unit.period,
                revision_id=successor_revision_id,
            ),
            revision_id=successor_revision_id,
            name="130-2026-1T-successor",
            created_at=_T0 + timedelta(seconds=1),
            updated_at=_T0 + timedelta(seconds=1),
        )
        repository.save(WorkUnitCatalogue.from_work_units((first_unit, WorkUnit(**payload))))

        current = read_modelo_work_current_coordinate(request, catalogue_repository=repository)

        assert current.generation > stale.generation
        with pytest.raises(ModeloWorkCaptureError):
            stale.require_current(current)


def test_work_capture_pointer_limb_defeats_an_aba_return_to_the_same_bucket(tmp_path: Path) -> None:
    """A pointer rewritten away and back is not mistaken for an unchanged limb."""
    from ....core.bucket_pointer import read_pointer, write_pointer
    from ....core.config import load_settings

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_ADDRESSING_PROFILE_ID) as profile:
        _seed_ready_profile(profile.repository, bucket_id=profile.bucket_id)
        repository = WorkUnitCatalogueRepository(objects=profile.repository)
        _seed_work_unit(repository, bucket_id=profile.bucket_id)
        implicit_request = _capture_request(None)
        root = load_settings().cadrumo_local_storage_root
        original = read_pointer(root)
        before = capture_modelo_work_resolution(implicit_request, catalogue_repository=repository)

        write_pointer(root, original.model_copy(update={"bucket_id": "99999999-0000-4000-8000-000000000999"}))
        write_pointer(root, original)

        after = capture_modelo_work_resolution(implicit_request, catalogue_repository=repository)

        assert after.resolution.bucket_id == before.resolution.bucket_id
        assert after.generation > before.generation


def test_explicit_bucket_capture_excludes_the_pointer_limb(tmp_path: Path) -> None:
    """An explicit operand keeps its catalogue generation across pointer churn."""
    from ....core.bucket_pointer import read_pointer, write_pointer
    from ....core.config import load_settings

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_ADDRESSING_PROFILE_ID) as profile:
        _seed_ready_profile(profile.repository, bucket_id=profile.bucket_id)
        repository = WorkUnitCatalogueRepository(objects=profile.repository)
        _seed_work_unit(repository, bucket_id=profile.bucket_id)
        explicit_request = _capture_request(profile.bucket_id)
        root = load_settings().cadrumo_local_storage_root
        original = read_pointer(root)
        before = capture_modelo_work_resolution(explicit_request, catalogue_repository=repository)

        write_pointer(root, original.model_copy(update={"bucket_id": "99999999-0000-4000-8000-000000000999"}))
        write_pointer(root, original)

        after = capture_modelo_work_resolution(explicit_request, catalogue_repository=repository)

        assert after.generation == before.generation


def test_work_capture_reads_the_catalogue_exactly_once_and_touches_no_registry(tmp_path: Path) -> None:
    """One capture is one encrypted-SQL catalogue read and no registry access."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_ADDRESSING_PROFILE_ID) as profile:
        _seed_ready_profile(profile.repository, bucket_id=profile.bucket_id)
        repository = WorkUnitCatalogueRepository(objects=profile.repository)
        _seed_work_unit(repository, bucket_id=profile.bucket_id)
        request = _capture_request(profile.bucket_id)
        selects: list[str] = []

        def _record_secure_object_select(
            _connection: object,
            _cursor: object,
            statement: str,
            _parameters: object,
            _context: object,
            _executemany: bool,
        ) -> None:
            normalized = " ".join(statement.split()).upper()
            if normalized.startswith("SELECT") and " FROM SECURE_OBJECTS " in f" {normalized} ":
                selects.append(statement)

        event.listen(profile.repository.engine, "after_cursor_execute", _record_secure_object_select)
        try:
            capture = capture_modelo_work_resolution(request, catalogue_repository=repository)
        finally:
            event.remove(profile.repository.engine, "after_cursor_execute", _record_secure_object_select)

        assert capture.resolution.bucket_id == profile.bucket_id
        assert len(selects) == 1
        assert "cadrumo.domain.calculations.registry" not in _capture_source_imports()


def test_distinct_storage_roots_cannot_compare_their_coordinates(tmp_path: Path) -> None:
    """Coordinates from two physical roots are refused, not silently equal."""
    with isolated_runtime_profile(tmp_path=tmp_path / "one", bucket_id=_ADDRESSING_PROFILE_ID) as first_profile:
        _seed_ready_profile(first_profile.repository, bucket_id=first_profile.bucket_id)
        first_repository = WorkUnitCatalogueRepository(objects=first_profile.repository)
        _seed_work_unit(first_repository, bucket_id=first_profile.bucket_id)
        first_capture = capture_modelo_work_resolution(
            _capture_request(first_profile.bucket_id),
            catalogue_repository=first_repository,
        )

    with isolated_runtime_profile(tmp_path=tmp_path / "two", bucket_id=_ADDRESSING_PROFILE_ID) as second_profile:
        _seed_ready_profile(second_profile.repository, bucket_id=second_profile.bucket_id)
        second_repository = WorkUnitCatalogueRepository(objects=second_profile.repository)
        _seed_work_unit(second_repository, bucket_id=second_profile.bucket_id)
        second_coordinate = read_modelo_work_current_coordinate(
            _capture_request(second_profile.bucket_id),
            catalogue_repository=second_repository,
        )

    assert first_capture.comparison_domain != second_coordinate.comparison_domain
    with pytest.raises(ModeloWorkCaptureError):
        first_capture.require_current(second_coordinate)


def test_work_capture_contract_is_owned_by_its_defining_module() -> None:
    """Every capture symbol is defined here and bound nowhere in the package namespace."""
    from .. import __init__ as modelo_namespace

    for owned in (
        ModeloWorkCapture,
        ModeloWorkCurrentCoordinate,
        ModeloWorkCaptureError,
        capture_modelo_work_resolution,
        read_modelo_work_current_coordinate,
    ):
        assert owned.__module__ == "cadrumo.application.modelo.work_addressing"
        assert not hasattr(modelo_namespace, owned.__name__)

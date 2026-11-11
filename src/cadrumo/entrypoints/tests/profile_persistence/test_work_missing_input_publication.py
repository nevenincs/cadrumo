"""Missing binding classification is confined to the pre-publication engine call."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from cadrumo.application.modelo.calculation_source_policy import BUCKET_AGGREGATION_LOCK_SOURCES
from cadrumo.application.user_profile.tests.persona_profile_facts import persona_facts_beneath
from cadrumo.domain.user_profile.tests.general_regime_facts import (
    RENTA_UNMARRIED_TAXPAYER_FACTS,
)

from ....adapters.persistence.profile.buckets import BucketEventHistoryRepository
from ....adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from ....adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from ....adapters.persistence.storage.tests.profile_capsule_runtime import seed_test_profile_record
from ....adapters.persistence.storage.tests.secure_sql import isolated_runtime_profile
from ....application.modelo import calculate_input
from ....application.modelo.calculate_input import WorkCalculateInputBundle, calculate_modelo_work_revision
from ....application.modelo.calculation_bucket_actions import (
    calculate_modelo_revision_from_bucket_aggregation_with_diagnostics,
)
from ....application.modelo.work_lifecycle import create_work_unit
from ....application.modelo.work_lifecycle_ports import WorkLifecyclePorts
from ....application.modelo.work_missing_input import ModeloPriorCarryAbsenceUnstatedError, ModeloWorkMissingInputError
from ....core.period import Period
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.errors import RegistryValidationError
from ....domain.calculations.registry.relations import relation_prefill_bindings_for_period
from ....domain.calculations.registry.schema import RegistrySnapshot
from ....domain.calculations.registry.tests.authored_editions import newest_authored_edition, revision_covering
from ....domain.user_profile.tests.profile_creation_authority import profile_creation_context_for_test
from ....domain.user_profile.values import ProfileSetupState, UserProfileFact, create_user_profile_record
from .file_flow_test_support import calculation_ports_for_test

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

PROFILE_ID = "10000000-0000-4000-8000-000000000476"
YEAR = newest_authored_edition("100")
_PERIOD = Period.from_year_and_code(YEAR, "0A")
_CLOCK = datetime(YEAR + 1, 5, 21, 10, tzinfo=UTC)
REQUIRED_BINDING = "renta-base-liquidable-negativa-general-anterior"


def work_missing_input_publication_profile() -> None:
    record = create_user_profile_record(
        setup_state=ProfileSetupState.COMPLETE,
        profile_id=PROFILE_ID,
        facts=persona_facts_beneath(
            (
                UserProfileFact(path="identity.tax_id", value="12345678Z"),
                UserProfileFact(path="identity.name", value="Test"),
                UserProfileFact(path="identity.surnames", value="Operator"),
                UserProfileFact(path="activities.description", value="economic activity"),
                *RENTA_UNMARRIED_TAXPAYER_FACTS,
                UserProfileFact(path="censo.activity_start_date", value=date(YEAR - 5, 1, 1)),
                UserProfileFact(path="withholding.colegio_concertado", value=False),
                # Modelo 123 is filed by whoever pays capital income subject to retención (RIRPF art. 108.1).
                UserProfileFact(path="withholding.pays_capital_income_with_retencion", value=True),
            )
        ),
        created_at=_CLOCK,
        updated_at=_CLOCK,
        context=profile_creation_context_for_test(),
    )
    seed_test_profile_record(record)


def _inputs(snapshot: RegistrySnapshot, *, omit_required: bool) -> WorkCalculateInputBundle:
    binding_values = {
        binding.id: Decimal("0")
        for binding in snapshot.revision.bindings
        if binding.id != "renta-profile-tax-residence-ccaa"
        and (not omit_required or binding.id != REQUIRED_BINDING)
        and binding.source != "profile"
        and binding.source not in BUCKET_AGGREGATION_LOCK_SOURCES
        and binding.provider.kind != "retencion_soportada"
    }
    return WorkCalculateInputBundle.build(
        casilla_inputs={},
        binding_values=binding_values,
        enum_binding_values={},
        relation_values={
            binding.id: Decimal("0") for binding, _ in relation_prefill_bindings_for_period(snapshot.revision)
        },
        detail_rows=(),
        borrador_snapshot_id=None,
    )


def work_and_repositories(
    operation: PinnedAuthorityOperation,
    *,
    modelo: str = "100",
    period: Period = _PERIOD,
    revision_id: str = str(revision_covering("100", YEAR).id),
):
    work_repo = WorkUnitCatalogueRepository()
    revision_repo = CalculationRevisionCatalogueRepository()
    event_repo = BucketEventHistoryRepository()
    unit = create_work_unit(
        bucket_id=PROFILE_ID,
        modelo=modelo,
        filing_year=period.filing_year,
        period=period,
        revision_id=revision_id,
        ports=WorkLifecyclePorts(work_unit_repository=work_repo, bucket_event_repository=event_repo),
        clock=_CLOCK,
        operation=operation,
    )
    return unit, work_repo, revision_repo, event_repo


def test_real_missing_required_binding_stops_before_revision_publication(
    tmp_path: Path, *, operation: PinnedAuthorityOperation
) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=PROFILE_ID):
        work_missing_input_publication_profile()
        snapshot = operation.snapshot("100", filing_year=YEAR, period="0A")
        required = next(binding for binding in snapshot.revision.bindings if binding.id == REQUIRED_BINDING)
        assert required.provider.kind == "previous_filing"
        unit, work_repo, revision_repo, event_repo = work_and_repositories(operation)
        inputs = _inputs(snapshot, omit_required=True)
        with (
            calculation_ports_for_test(
                bucket_id=PROFILE_ID,
                work_unit_repository=work_repo,
                calculation_repository=revision_repo,
                bucket_event_repository=event_repo,
            ) as ports,
            pytest.raises(ModeloWorkMissingInputError) as refused,
        ):
            calculate_modelo_revision_from_bucket_aggregation_with_diagnostics(
                unit.work_unit_id,
                actor="operator",
                casilla_inputs=inputs.casilla_inputs,
                binding_values=inputs.binding_values,
                relation_values=inputs.relation_values,
                ports=ports,
                clock=_CLOCK,
            )
        assert refused.value.binding_id == REQUIRED_BINDING
        # The binding is a carry the filer can state holds nothing, so the
        # refusal is worded as that open statement; the engine's stays its cause.
        assert isinstance(refused.value, ModeloPriorCarryAbsenceUnstatedError)
        assert refused.value.open_carry_ids == (REQUIRED_BINDING,)
        cause = refused.value.__cause__
        assert isinstance(cause, RegistryValidationError)
        assert cause.translated_message in {
            "errors.calc.binding_value_missing",
            "errors.calc.bound_casilla_binding_value_missing",
        }
        assert revision_repo.load().revisions == {}
        stored_unit = work_repo.load().get(unit.work_unit_id)
        assert stored_unit is not None
        assert stored_unit.current_calculation_revision_id is None


def test_same_tag_after_publication_remains_generic_and_published(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *, operation: PinnedAuthorityOperation
) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=PROFILE_ID):
        work_missing_input_publication_profile()
        m123_period = Period.from_year_and_code(YEAR, "2T")
        m123_snapshot = operation.snapshot("123", filing_year=YEAR, period="2T")
        unit, work_repo, revision_repo, event_repo = work_and_repositories(
            operation, modelo="123", period=m123_period, revision_id=m123_snapshot.revision.id
        )
        inputs = WorkCalculateInputBundle.build(
            casilla_inputs={},
            binding_values={},
            enum_binding_values={},
            relation_values={},
            detail_rows=(),
            borrador_snapshot_id=None,
        )

        def fail_modality(*_args: object, **_kwargs: object) -> None:
            raise RegistryValidationError(
                "injected post-publication diagnostic failure",
                translated_message="errors.calc.binding_value_missing",
                context={"binding_id": REQUIRED_BINDING},
            )

        monkeypatch.setattr(calculate_input, "modelo_202_modality_for_record", fail_modality)
        with (
            calculation_ports_for_test(
                bucket_id=PROFILE_ID,
                work_unit_repository=work_repo,
                calculation_repository=revision_repo,
                bucket_event_repository=event_repo,
            ) as ports,
            pytest.raises(RegistryValidationError) as refused,
        ):
            calculate_modelo_work_revision(
                work_unit_id=unit.work_unit_id,
                actor="operator",
                inputs=inputs,
                ports=ports,
            )
        assert type(refused.value) is RegistryValidationError
        assert refused.value.translated_message == "errors.calc.binding_value_missing"
        revisions = revision_repo.load().revisions
        assert len(revisions) == 1
        published = next(iter(revisions.values()))
        stored_unit = work_repo.load().get(unit.work_unit_id)
        assert stored_unit is not None
        assert stored_unit.current_calculation_revision_id == published.calculation_revision_id

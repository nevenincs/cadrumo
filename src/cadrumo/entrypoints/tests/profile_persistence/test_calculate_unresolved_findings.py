"""``modelo work calculate`` names what it left without a value, as ``modelo project`` does.

The calculation runs over real encrypted stores, the real source mesh and the real engine; the unresolved
rows are the ones the Modelo 100 projection produces, carried onto the public wire shape. All identifiers
and amounts are synthetic.
"""

from __future__ import annotations

from collections.abc import Generator
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import select

from cadrumo.application.user_profile.tests.persona_profile_facts import persona_facts_beneath

from ....adapters.persistence.profile.buckets import BucketEventHistoryRepository
from ....adapters.persistence.profile.calculation_observations import CalculationObservationRepository
from ....adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from ....adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from ....adapters.persistence.profile.tests.retencion_soportada_seed import seed_payer_certificate
from ....adapters.persistence.storage.sql.secure_objects import SecureObjectRepository
from ....adapters.persistence.storage.sql.tables import secure_objects_table
from ....adapters.persistence.storage.tests.profile_capsule_runtime import seed_test_profile_record
from ....adapters.persistence.storage.tests.secure_sql import (
    isolated_runtime_profile,
    mutate_encrypted_secure_object_json,
)
from ....application.calculations.observations_repository import observation_key
from ....application.modelo.calculation_bucket_actions import (
    BucketAggregationCalculationResult,
    calculate_modelo_revision_from_bucket_aggregation_with_diagnostics,
)
from ....application.modelo.projection_operation import (
    ProjectUnresolvedBindingProjection,
    ProjectUnresolvedCasillaProjection,
    require_unresolved_boxes_carry_no_value,
)
from ....application.modelo.reconciliation_sources import ReconciliationSourceNeed, ReconciliationSourceStanding
from ....application.modelo.work_lifecycle import create_work_unit
from ....application.modelo.work_lifecycle_ports import WorkLifecyclePorts
from ....application.modelo.work_missing_input import (
    ModeloPriorPeriodUnfiledError,
    ModeloWorkMissingInputError,
    prior_period_unfiled,
)
from ....application.operator_actions.models import PreconditionVerdict
from ....core.aggregation import BindingSourceKind
from ....core.casilla_id import validated_casilla_id
from ....core.external_constants import OutputLanguage
from ....core.period import Period
from ....core.retencion_soportada import RetencionSoportadaClase
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.relations import relation_prefill_bindings_for_period
from ....domain.calculations.registry.tests.authored_editions import (
    newest_authored_edition,
)
from ....domain.calculations.registry.tests.published_authority import published_snapshot
from ....domain.calculations.registry.tests.registry_observations import (
    registry_grounded_modelo_observation,
    revision_id_for_observation,
)
from ....domain.modelos.work_unit import WorkUnit
from ....domain.user_profile.tests.profile_creation_authority import profile_creation_context_for_test
from ....domain.user_profile.values import ProfileSetupState, UserProfileFact, create_user_profile_record
from .file_flow_test_support import calculation_ports_for_test

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_BUCKET_ID = "22222222-2222-4222-8222-222222222222"
_TAXPAYER = "12345678Z"
_CATEGORIES = "taxpayer_type.irpf_income_categories"
_M100_YEAR = newest_authored_edition("100")
_CAPITAL_CREDIT_BINDING = "renta-retencion-soportada-capital-mobiliario"
_CAPITAL_CREDIT_CASILLA = "0597"
_WORDS = OutputLanguage.ES


@pytest.fixture
def objects(tmp_path: Path) -> Generator[SecureObjectRepository]:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        yield profile.repository


def _seed_profile(year: int, categories: str, *, activity_start: date | None = None) -> None:
    seed_test_profile_record(
        create_user_profile_record(
            setup_state=ProfileSetupState.COMPLETE,
            profile_id=_BUCKET_ID,
            facts=persona_facts_beneath(
                (
                    UserProfileFact(path="identity.tax_id", value=_TAXPAYER),
                    UserProfileFact(path="identity.name", value="Test"),
                    UserProfileFact(path="identity.surnames", value="Operator"),
                    UserProfileFact(path="activities.description", value="economic activity"),
                    # A consulting activity, so no urban rental is carried on as an activity.
                    UserProfileFact(path="activities.iae_epigraph", value="844"),
                    UserProfileFact(path=_CATEGORIES, value=categories),
                    UserProfileFact(
                        path="censo.activity_start_date",
                        value=activity_start if activity_start is not None else date(year - 5, 1, 1),
                    ),
                    UserProfileFact(path="renta_taxpayer.birth_date", value=date(year - 45, 3, 15)),
                    UserProfileFact(path="renta_taxpayer.marital_status", value="1"),
                    UserProfileFact(path="renta_taxpayer.marriage_full_year", value=False),
                    UserProfileFact(path="renta_taxpayer.marriage_month_start", value=Decimal("0")),
                    UserProfileFact(path="renta_taxpayer.marriage_month_end", value=Decimal("0")),
                    UserProfileFact(path="renta_filing.declaration_type", value="1"),
                    UserProfileFact(path="renta_family.minor_children_in_unit", value=False),
                )
            ),
            created_at=datetime(year + 1, 4, 1, tzinfo=UTC),
            updated_at=datetime(year + 1, 4, 1, tzinfo=UTC),
            context=profile_creation_context_for_test(),
        ),
    )


def _calculate(
    objects: SecureObjectRepository,
    operation: PinnedAuthorityOperation,
    *,
    modelo: str,
    year: int,
    period_code: str,
    revision_id: str,
    binding_values: dict[str, Decimal] | None = None,
    relation_values: dict[str, Decimal] | None = None,
) -> BucketAggregationCalculationResult:
    work_unit_repository = WorkUnitCatalogueRepository(objects=objects)
    calculation_repository = CalculationRevisionCatalogueRepository(objects=objects)
    bucket_event_repository = BucketEventHistoryRepository(objects=objects)
    work_unit = create_work_unit(
        bucket_id=_BUCKET_ID,
        modelo=modelo,
        filing_year=year,
        period=Period.from_year_and_code(year, period_code),
        revision_id=revision_id,
        ports=WorkLifecyclePorts(
            work_unit_repository=work_unit_repository, bucket_event_repository=bucket_event_repository
        ),
        operation=operation,
    )
    with calculation_ports_for_test(
        bucket_id=_BUCKET_ID,
        work_unit_repository=work_unit_repository,
        calculation_repository=calculation_repository,
        bucket_event_repository=bucket_event_repository,
    ) as ports:
        return calculate_modelo_revision_from_bucket_aggregation_with_diagnostics(
            work_unit.work_unit_id,
            actor="operator-A",
            binding_values=binding_values,
            relation_values=relation_values,
            ports=ports,
        )


def _seed_work_certificate(operation: PinnedAuthorityOperation) -> None:
    seed_payer_certificate(
        operation=operation,
        taxpayer_tax_id=_TAXPAYER,
        ejercicio=_M100_YEAR,
        payer_tax_id="B00000001",
        income_class=RetencionSoportadaClase.TRABAJO,
        retencion=Decimal("1200.00"),
        ingreso_a_cuenta=Decimal("300.00"),
    )


def _m100_binding_values() -> dict[str, Decimal]:
    """State zero for every carry a prior filing would supply, which this profile has none of."""
    revision = published_snapshot("100", filing_year=_M100_YEAR, period="0A").revision
    carried = {
        binding.id: Decimal("0") for binding in revision.bindings if binding.source is BindingSourceKind.PREVIOUS_FILING
    }
    return carried


def _zero_relation_values() -> dict[str, Decimal]:
    """State zero for the quarterly payments the annual return folds in, which this profile made none of."""
    revision = published_snapshot("100", filing_year=_M100_YEAR, period="0A").revision
    return {binding.id: Decimal("0") for binding, _ in relation_prefill_bindings_for_period(revision)}


def _calculate_m100(
    objects: SecureObjectRepository, operation: PinnedAuthorityOperation
) -> BucketAggregationCalculationResult:
    return _calculate(
        objects,
        operation,
        modelo="100",
        year=_M100_YEAR,
        period_code="0A",
        revision_id=str(_M100_YEAR),
        binding_values=_m100_binding_values(),
        relation_values=_zero_relation_values(),
    )


def test_a_declared_income_class_with_no_payer_is_named_with_its_box_and_the_box_has_no_value(
    objects: SecureObjectRepository, operation: PinnedAuthorityOperation
) -> None:
    _seed_profile(_M100_YEAR, "trabajo,actividad_economica,capital_mobiliario")
    _seed_work_certificate(operation)
    result = _calculate_m100(objects, operation)

    rows = {row.binding_id: row for row in result.unresolved_bindings}
    assert _CAPITAL_CREDIT_BINDING in rows
    credit = rows[_CAPITAL_CREDIT_BINDING]
    assert credit.casilla_id == _CAPITAL_CREDIT_CASILLA
    assert credit.reason == "unresolved_binding"
    assert credit.note is not None
    assert _CAPITAL_CREDIT_CASILLA not in result.revision.casilla_values
    assert result.revision.casilla_values["0596"] == Decimal("1500.00")
    # The box that adds the unresolved credit has no value either, and is named.
    unresolved_boxes = {row.casilla_id for row in result.unresolved_casillas}
    assert unresolved_boxes
    assert not unresolved_boxes.intersection(result.revision.casilla_values)

    public_bindings = tuple(
        ProjectUnresolvedBindingProjection.from_service(row, language=_WORDS) for row in result.unresolved_bindings
    )
    public_casillas = tuple(
        ProjectUnresolvedCasillaProjection.from_service(row, language=_WORDS) for row in result.unresolved_casillas
    )
    assert all(row.words for row in public_bindings)
    assert all(row.reason_words for row in public_casillas)
    require_unresolved_boxes_carry_no_value(set(result.revision.casilla_values), public_bindings, public_casillas)


def test_a_credit_the_payer_certificate_resolves_is_not_named(
    objects: SecureObjectRepository, operation: PinnedAuthorityOperation
) -> None:
    _seed_profile(_M100_YEAR, "trabajo,actividad_economica")
    _seed_work_certificate(operation)
    result = _calculate_m100(objects, operation)

    assert result.revision.casilla_values["0596"] == Decimal("1500.00")
    assert "renta-retencion-soportada-trabajo" not in {row.binding_id for row in result.unresolved_bindings}
    assert "0596" not in {row.casilla_id for row in result.unresolved_casillas}
    assert "0596" not in {row.casilla_id for row in result.unresolved_bindings}


def test_a_modelo_130_whose_operands_are_all_resolved_names_nothing(
    objects: SecureObjectRepository, operation: PinnedAuthorityOperation
) -> None:
    year = operation.supported_filing_years().floor
    _seed_profile(year, "actividad_economica")
    revision_id = published_snapshot("130", filing_year=year, period="1T").revision.id
    result = _calculate(
        objects,
        operation,
        modelo="130",
        year=year,
        period_code="1T",
        revision_id=str(revision_id),
        # The prior year's net income, which the profile's earlier return would have recorded.
        binding_values={"irpf.previous_year_economic_activity_net_income": Decimal("0")},
    )

    assert result.unresolved_bindings == (), result.unresolved_bindings
    assert result.unresolved_casillas == (), result.unresolved_casillas


def test_a_box_that_is_both_valued_and_unresolved_is_refused() -> None:
    row = ProjectUnresolvedCasillaProjection(
        casilla_id="0180",
        reason="unresolved_operand",
        reason_words="words",
        formula_id="a-formula",
        legal_refs=("a-law",),
        source_refs=("a-source",),
    )
    with pytest.raises(ValueError, match="also carries a value"):
        require_unresolved_boxes_carry_no_value({"0180"}, (), (row,))
    require_unresolved_boxes_carry_no_value({"0181"}, (), (row,))


_M130_PRIOR_NET_INCOME = {"irpf.previous_year_economic_activity_net_income": Decimal("0")}


def _create_m130_quarter(
    objects: SecureObjectRepository, operation: PinnedAuthorityOperation, *, year: int, period_code: str
) -> WorkUnit:
    revision_id = published_snapshot("130", filing_year=year, period=period_code).revision.id
    return create_work_unit(
        bucket_id=_BUCKET_ID,
        modelo="130",
        filing_year=year,
        period=Period.from_year_and_code(year, period_code),
        revision_id=str(revision_id),
        ports=WorkLifecyclePorts(
            work_unit_repository=WorkUnitCatalogueRepository(objects=objects),
            bucket_event_repository=BucketEventHistoryRepository(objects=objects),
        ),
        operation=operation,
    )


def _calculate_m130_quarter(
    objects: SecureObjectRepository, operation: PinnedAuthorityOperation, *, year: int, period_code: str = "2T"
) -> BucketAggregationCalculationResult:
    revision_id = published_snapshot("130", filing_year=year, period=period_code).revision.id
    return _calculate(
        objects,
        operation,
        modelo="130",
        year=year,
        period_code=period_code,
        revision_id=str(revision_id),
        binding_values=_M130_PRIOR_NET_INCOME,
    )


def _refused_quarter(
    objects: SecureObjectRepository, operation: PinnedAuthorityOperation, *, year: int, period_code: str = "2T"
) -> ModeloPriorPeriodUnfiledError:
    revisions_before = dict(CalculationRevisionCatalogueRepository(objects=objects).load().revisions)
    with pytest.raises(ModeloPriorPeriodUnfiledError) as refused:
        _calculate_m130_quarter(objects, operation, year=year, period_code=period_code)
    assert CalculationRevisionCatalogueRepository(objects=objects).load().revisions == revisions_before
    return refused.value


def _door(refused: ModeloPriorPeriodUnfiledError) -> tuple[str, dict[str, object]]:
    verdict = refused.terminal_precondition_verdict
    assert isinstance(verdict, PreconditionVerdict)
    assert verdict.action is not None
    return verdict.action.action_id, {item.argument_name: item.value for item in verdict.argument_bindings}


def _save_first_quarter(objects: SecureObjectRepository, *, year: int, payment: Decimal) -> None:
    filed_first_quarter = registry_grounded_modelo_observation(
        modelo="130",
        filing_year=year,
        period="1T",
        casilla_values={
            validated_casilla_id("07"): payment,
            validated_casilla_id("16"): Decimal("0"),
            validated_casilla_id("19"): payment,
        },
    )
    observations = CalculationObservationRepository(objects=objects)
    observations.save(
        observations.prepare_observation_envelope(
            filed_first_quarter,
            source_kind="app_filing",
            stamped_revision_id=revision_id_for_observation(filed_first_quarter),
        )
    )


def _restamp_first_quarter(objects: SecureObjectRepository, *, year: int, stamp: str) -> None:
    """Rewrite the stored 1T stamp in place, as a row saved under another registry revision reads back."""

    def restamp(envelope: dict[str, Any]) -> None:
        layers = envelope["payload"]
        (layers["pending_local"] or layers["official"])["stamped_revision_id"] = stamp

    mutate_encrypted_secure_object_json(
        objects.engine,
        row_statement=select(secure_objects_table).where(
            secure_objects_table.c.namespace == CalculationObservationRepository.namespace,
            secure_objects_table.c.object_key == observation_key("130", Period.from_year_and_code(year, "1T")),
        ),
        mutate=restamp,
    )


def test_a_second_quarter_with_no_first_quarter_offers_to_create_it(
    objects: SecureObjectRepository, operation: PinnedAuthorityOperation
) -> None:
    """The pagos anteriores of 2T are read from the filed 1T, so a missing 1T is the way on, not a bare box."""
    year = operation.supported_filing_years().floor
    _seed_profile(year, "actividad_economica")

    refused = _refused_quarter(objects, operation, year=year)

    assert refused.unfiled_period == Period.from_year_and_code(year, "1T")
    assert [(need.period.registry_token, need.unit) for need in refused.source_needs] == [("1T", None)]
    assert refused.translated_message == "application.modelo.errors.prior_period_unfiled"
    assert dict(refused.context or {}) == {"modelo": "130", "filing_year": year, "period": "2T", "unfiled_period": "1T"}
    assert _door(refused) == ("operator.modelo.work.create", {"modelo": "130", "period": "1T", "year": year})
    step = refused.operation_next_step(_WORDS)
    assert step is not None
    assert step.model_dump()["period_code"] == "1T"


def test_a_first_quarter_with_no_calculation_is_the_one_to_calculate(
    objects: SecureObjectRepository, operation: PinnedAuthorityOperation
) -> None:
    year = operation.supported_filing_years().floor
    _seed_profile(year, "actividad_economica")
    first_quarter = _create_m130_quarter(objects, operation, year=year, period_code="1T")

    refused = _refused_quarter(objects, operation, year=year)

    assert refused.source_needs[0].standing is ReconciliationSourceStanding.MISSING
    assert _door(refused) == ("operator.modelo.work.calculate", {"work_unit_id": first_quarter.work_unit_id})
    step = refused.operation_next_step(_WORDS)
    assert step is not None
    assert step.model_dump()["work_unit_id"] == first_quarter.work_unit_id


def test_a_calculated_first_quarter_is_the_one_to_verify(
    objects: SecureObjectRepository, operation: PinnedAuthorityOperation
) -> None:
    year = operation.supported_filing_years().floor
    _seed_profile(year, "actividad_economica")
    first_quarter = _calculate_m130_quarter(objects, operation, year=year, period_code="1T")

    refused = _refused_quarter(objects, operation, year=year)

    assert refused.source_needs[0].standing is ReconciliationSourceStanding.UNVERIFIED
    assert _door(refused) == ("operator.modelo.work.verify", {"work_unit_id": first_quarter.revision.work_unit_id})


def test_a_stored_first_quarter_the_fold_drops_as_stale_is_not_filed(
    objects: SecureObjectRepository, operation: PinnedAuthorityOperation
) -> None:
    """An observation stamped with a revision the law does not select is one the fold refuses, so 1T is still owed."""
    year = operation.supported_filing_years().floor
    _seed_profile(year, "actividad_economica")
    _save_first_quarter(objects, year=year, payment=Decimal("412.35"))
    _restamp_first_quarter(objects, year=year, stamp="not-the-law-selected-revision")

    refused = _refused_quarter(objects, operation, year=year)

    assert refused.unfiled_period == Period.from_year_and_code(year, "1T")
    assert _door(refused)[0] == "operator.modelo.work.create"


def test_a_mid_year_alta_never_names_a_quarter_before_the_activity_started(
    objects: SecureObjectRepository, operation: PinnedAuthorityOperation
) -> None:
    """Activity began in 2T, so a 3T calculation waits on 2T alone: 1T owed no return."""
    year = operation.supported_filing_years().floor
    _seed_profile(year, "actividad_economica", activity_start=date(year, 5, 1))

    refused = _refused_quarter(objects, operation, year=year, period_code="3T")

    assert [need.period.registry_token for need in refused.source_needs] == ["2T"]
    assert _door(refused) == ("operator.modelo.work.create", {"modelo": "130", "period": "2T", "year": year})


@pytest.mark.parametrize(
    ("standing", "action_id"),
    [
        (ReconciliationSourceStanding.MISSING, "operator.modelo.work.calculate"),
        (ReconciliationSourceStanding.UNVERIFIED, "operator.modelo.work.verify"),
        (ReconciliationSourceStanding.UNFILED, "operator.modelo.work.file"),
    ],
)
def test_an_existing_earlier_declaration_is_moved_on_by_the_work_its_standing_calls_for(
    objects: SecureObjectRepository,
    operation: PinnedAuthorityOperation,
    standing: ReconciliationSourceStanding,
    action_id: str,
) -> None:
    year = operation.supported_filing_years().floor
    _seed_profile(year, "actividad_economica")
    first_quarter = _create_m130_quarter(objects, operation, year=year, period_code="1T")
    engine_refusal = _refused_quarter(objects, operation, year=year)
    missing = ModeloWorkMissingInputError(engine_refusal, binding_id=engine_refusal.binding_id)
    second_quarter = _create_m130_quarter(objects, operation, year=year, period_code="2T")
    snapshot = published_snapshot("130", filing_year=year, period="2T")
    asked: list[tuple[tuple[str, Period], ...]] = []

    def standing_of(periods: tuple[tuple[str, Period], ...]) -> tuple[ReconciliationSourceNeed, ...]:
        asked.append(periods)
        return (
            ReconciliationSourceNeed(modelo="130", period=first_quarter.period, standing=standing, unit=first_quarter),
        )

    refused = prior_period_unfiled(missing, work_unit=second_quarter, snapshot=snapshot, source_needs=standing_of)

    assert asked == [(("130", first_quarter.period),)]
    assert refused is not None
    assert _door(refused) == (action_id, {"work_unit_id": first_quarter.work_unit_id})


def test_a_second_quarter_carries_the_filed_first_quarter_payment_into_box_05(
    objects: SecureObjectRepository, operation: PinnedAuthorityOperation
) -> None:
    """Box 05 of 2T holds the positive box 07 the filed 1T return shows, with no value typed by the filer."""
    year = operation.supported_filing_years().floor
    _seed_profile(year, "actividad_economica")
    first_quarter_payment = Decimal("412.35")
    _save_first_quarter(objects, year=year, payment=first_quarter_payment)

    result = _calculate_m130_quarter(objects, operation, year=year)

    assert result.revision.casilla_values["05"] == first_quarter_payment

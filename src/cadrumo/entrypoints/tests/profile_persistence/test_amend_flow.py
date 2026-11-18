"""End-to-end tests for the modelo external-filing amend path.

Every test wires the full set of catalogue repositories over a
fresh encrypted SQLite database and seeds a baseline filing record
that carries ``external_evidence`` — the gate the amend path
demands. The new revision lands as a complementaria amendment that
supersedes the baseline filing and emits a ``modelo.amended``
bucket event.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal

import pytest
from pydantic import SecretStr

from cadrumo.core.operator_action_enums import ActionArgumentStatus
from cadrumo.entrypoints.tests.profile_persistence.verification_repository_support import (
    build_test_certificate_secret_backend_factory,
    build_test_verification_repository_bundle,
)

from ....adapters.persistence.profile.tests.cross_period_seeding import seed_clean_cross_period_sources
from ....adapters.persistence.storage.operator_scope import build_operator_scope_ports
from ....application.modelo.action_errors import (
    AmendmentComplementariaLiabilityDecreaseError,
    AmendmentEvidenceMissingError,
    AmendmentTargetStateError,
)
from ....application.modelo.amendment_actions import amend_modelo_revision
from ....application.modelo.calculation_bucket_actions import (
    calculate_modelo_revision_from_bucket_aggregation_with_diagnostics,
)
from ....application.modelo.calculation_revision_queries import get_calculation_revision
from ....application.modelo.verification_actions import verify_modelo_revision_with_preconditions
from ....application.modelo.work_lifecycle import (
    get_work_unit,
)
from ....core.auth_provider import AuthProviderKind
from ....core.casilla_id import validated_casilla_id
from ....core.config import Settings
from ....core.errors.error_codes import ErrorCategory, get_registered_error_code
from ....core.filing_timeliness import FilingTimeliness
from ....core.time.clock import MADRID_TZ
from ....domain.buckets.event import BucketEventType
from ....domain.calculations.registry.authority import PinnedAuthorityOperation, bundled_indexed_authority
from ....domain.calculations.registry.formula_runtime import calculate_registry_snapshot
from ....domain.calculations.registry.schema import RegistrySnapshot
from ....domain.calculations.registry.schema_references import date_within_validity_window
from ....domain.deadlines.effective_close import resolve_effective_filing_deadline
from ....domain.modelos.calculation_revision import (
    CalculationRevision,
    CalculationRevisionState,
)
from ....domain.modelos.calculation_revision_operator_layer import CalculationOperatorLayer
from ....domain.modelos.filing_record import (
    AeatConfirmationState,
    FilingDeclarationKind,
    FilingOrigin,
    ModeloRecord,
    ModeloRecordStatus,
    derive_filing_record_id,
)
from ....domain.modelos.filing_repository import upsert_filing_record
from ...adapter_composition_work_ports import (
    build_amendment_action_ports,
    build_calculation_action_ports,
    build_filing_action_ports,
    build_work_lifecycle_ports,
)
from ..filing_record_read_support import persisted_filing_record
from .amend_flow_support import (
    AMEND_EXPENSE_CASILLA,
    AMEND_HOME_DEDUCTION_CASILLA,
    AMEND_INCOME_CASILLA,
    AMEND_PREVIOUS_PAYMENT_CASILLA,
    AMEND_PRIOR_RETURN_RESULT_CASILLA,
    AMEND_WITHHELD_CASILLA,
    M303_RESULT_CASILLA,
    PRIOR_YEAR,
    PROFILE_ID,
    T1,
    T2,
    T3,
    T4,
    YEAR,
    Repos,
    drive_amend_creates_complementaria,
    repos,
    seed_engine_computed_baseline,
    seed_external_baseline,
    seed_local_filing_record,
    seed_work_unit,
)
from .file_flow_test_support import (
    workflow_profile,
)
from .import_flow_support import TAX_ID, import_external_filing, persist_matching_justificante

__all__ = ["repos"]

_OPERATOR_SCOPE_PORTS = build_operator_scope_ports()

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_DEFAULT_130_BINDING_VALUES = {
    "irpf.previous_year_economic_activity_net_income": Decimal("0"),
}


def test_amend_refuses_evidence_less_m303_external_baseline(
    repos: Repos, *, operation: PinnedAuthorityOperation
) -> None:
    m303_year = YEAR
    snapshot = operation.snapshot("303", filing_year=m303_year, period="1T")
    _, _, baseline = seed_external_baseline(
        repos,
        modelo="303",
        filing_year=m303_year,
        period_code="1T",
        revision_id_value=snapshot.revision.id,
        casilla_values={M303_RESULT_CASILLA: Decimal("0")},
        filing_instance_evidence=None,
        operation=operation,
    )

    with pytest.raises(AmendmentEvidenceMissingError), bundled_indexed_authority().operation() as operation:
        amend_modelo_revision(
            ports=build_amendment_action_ports(bucket_id=PROFILE_ID, operation=operation),
            from_filing_record_id=baseline.filing_record_id,
            overrides={M303_RESULT_CASILLA: Decimal("1")},
            amendment_kind=FilingDeclarationKind.RECTIFICATIVA,
            reason="correction requires immutable filing evidence",
            actor="operator-A",
            clock=T4,
        )


def test_amend_refuses_without_external_evidence(repos: Repos, *, operation: PinnedAuthorityOperation) -> None:
    """A locally-filed return (no ``external_evidence``) cannot be amended."""

    wu_repo, cr_repo, fr_repo, _vr_repo, bv_repo = repos
    work_unit = seed_work_unit(wu_repo, operation=operation)
    with bundled_indexed_authority().operation() as operation:
        revision = calculate_modelo_revision_from_bucket_aggregation_with_diagnostics(
            work_unit.work_unit_id,
            ports=build_calculation_action_ports(bucket_id=work_unit.bucket_id, operation=operation),
            actor="operator-A",
            casilla_inputs={
                AMEND_WITHHELD_CASILLA: Decimal("0"),
                AMEND_PREVIOUS_PAYMENT_CASILLA: Decimal("0"),
                AMEND_HOME_DEDUCTION_CASILLA: Decimal("0"),
                AMEND_PRIOR_RETURN_RESULT_CASILLA: Decimal("0"),
            },
            binding_values=_DEFAULT_130_BINDING_VALUES,
            clock=T1,
        ).revision
    seed_clean_cross_period_sources(
        work_unit,
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        filing_repository=fr_repo,
        bucket_event_repository=bv_repo,
        operation=operation,
    )
    with bundled_indexed_authority().operation() as operation:
        report = verify_modelo_revision_with_preconditions(
            revision.calculation_revision_id,
            certificate_secret_backend_factory=build_test_certificate_secret_backend_factory(),
            verification_repositories=build_test_verification_repository_bundle(),
            actor="operator-A",
            workflow_profile=workflow_profile(),
            settings=Settings(
                cadrumo_auth_provider=AuthProviderKind.CLAVE_MOVIL,
                cadrumo_clave_movil_dni_nie=SecretStr("X0001500M"),
            ),
            clock=T2,
            operator_scope_ports=_OPERATOR_SCOPE_PORTS,
            operation=operation,
        ).report
    assert report.granted_verificado_completo is True
    with bundled_indexed_authority().operation() as operation:
        verified_revision = get_calculation_revision(
            revision.calculation_revision_id,
            ports=build_calculation_action_ports(bucket_id=PROFILE_ID, operation=operation),
        )
    locally_filed = seed_local_filing_record(
        work_unit=work_unit,
        revision=verified_revision,
        calculation_repository=cr_repo,
        filing_repository=fr_repo,
        filed_at=T3,
        filed_by="operator-A",
    )
    assert locally_filed.external_evidence is None

    with pytest.raises(AmendmentEvidenceMissingError) as refused, bundled_indexed_authority().operation() as operation:
        amend_modelo_revision(
            ports=build_amendment_action_ports(bucket_id=PROFILE_ID, operation=operation),
            from_filing_record_id=locally_filed.filing_record_id,
            overrides={AMEND_INCOME_CASILLA: Decimal("1100")},
            amendment_kind=FilingDeclarationKind.COMPLEMENTARIA,
            reason="under-reported turnover",
            actor="operator-A",
            clock=T4,
        )

    # A refusal with a door, not a fault: importing the AEAT justificante for
    # this work unit is what makes the filing amendable. The work unit is known;
    # the evidence kind and its reference are on the operator's justificante,
    # so the door asks for them rather than being served unable to run.
    assert get_registered_error_code(refused.value).category is ErrorCategory.REFUSED
    verdict = refused.value.terminal_precondition_verdict
    assert verdict is not None
    assert verdict.failed_condition_id == "modelo.work.amend.external_evidence.present"
    assert verdict.action is not None
    assert verdict.action.action_id == "operator.modelo.filing_record.import"
    bound = {binding.argument_name: (binding.status, binding.value) for binding in verdict.argument_bindings}
    assert bound == {
        "evidence_kind": (ActionArgumentStatus.MISSING, None),
        "evidence_reference_id": (ActionArgumentStatus.MISSING, None),
        "work_unit_id": (ActionArgumentStatus.RESOLVED, work_unit.work_unit_id),
    }


def test_amend_refuses_when_baseline_already_superseded(repos: Repos, *, operation: PinnedAuthorityOperation) -> None:
    """A SUPERSEDED filing record cannot be amended."""

    _wu_repo, _cr_repo, fr_repo, _, _bv_repo = repos
    _, _, baseline = seed_external_baseline(
        repos, casilla_values={AMEND_INCOME_CASILLA: Decimal("1000")}, operation=operation
    )
    successor_record_id = "f" * 64
    fr_repo.save(
        upsert_filing_record(
            fr_repo.load(),
            baseline.model_copy(
                update={
                    "status": ModeloRecordStatus.SUPERSEDIDO,
                    "superseded_at": T3,
                    "superseded_by_filing_record_id": successor_record_id,
                },
            ),
        ),
    )

    with pytest.raises(AmendmentTargetStateError), bundled_indexed_authority().operation() as operation:
        amend_modelo_revision(
            ports=build_amendment_action_ports(bucket_id=PROFILE_ID, operation=operation),
            from_filing_record_id=baseline.filing_record_id,
            overrides={AMEND_INCOME_CASILLA: Decimal("1100")},
            amendment_kind=FilingDeclarationKind.COMPLEMENTARIA,
            reason="late evidence",
            actor="operator-A",
            clock=T4,
        )


#: Casilla 13 for a prior-year net income of at most 9.000 EUR, which the test's binding of zero selects.
_MINORACION_PRIOR_INCOME_AT_MOST_9000 = Decimal("100")
_CENT = Decimal("0.01")


def _served_percent(snapshot: RegistrySnapshot, parameter_id: str) -> Decimal:
    """Return the percentage the registry serves for the snapshot's first-quarter close."""
    quarter_close = date(snapshot.filing_year, 3, 31)
    parameter = next(item for item in snapshot.revision.parameters if item.id == parameter_id)
    (served,) = (
        value
        for value in parameter.values
        if date_within_validity_window(quarter_close, valid_from=value.valid_from, valid_to=value.valid_to)
    )
    return Decimal(served.value)


def _expected_pago_fraccionado(snapshot: RegistrySnapshot, *, income: Decimal, expenses: Decimal) -> Decimal:
    """Casilla 04 of a simplified-modality 1T return, from the instructions' own arithmetic.

    The provisiones y gastos de difícil justificación are the served percentage of
    income less the other expenses (RIRPF art. 30.2.a, 7 per cent only for 2023); the
    rendimiento neto is income less expenses and that provision; the payment is the
    served percentage of it.
    """
    provision = ((income - expenses) * _served_percent(snapshot, "irpf.art-30-2-provision-rate") / 100).quantize(
        _CENT, ROUND_HALF_UP
    )
    net = (income - expenses - provision).quantize(_CENT, ROUND_HALF_UP)
    rate = _served_percent(snapshot, "irpf.direct_estimation_fractional_payment_rate")
    return (net * rate / 100).quantize(_CENT, ROUND_HALF_UP)


def _assert_saved_content_kept(revision: CalculationRevision, saved: dict[str, object]) -> None:
    """A correction leaves the corrected calculation's content alone; only its lifecycle moves to superseded."""
    lifecycle = {"state", "superseded_at", "updated_at"}
    assert revision.state is CalculationRevisionState.PRESENTADO_SUPERSEDIDO
    kept = {key: value for key, value in revision.model_dump(mode="json").items() if key not in lifecycle}
    assert kept == {key: value for key, value in saved.items() if key not in lifecycle}


def test_operation_backed_130_successive_confirmed_corrections_recompute_and_guard_decreases(
    repos: Repos, *, operation: PinnedAuthorityOperation
) -> None:
    """A confirmed correction becomes the paid-period seed for the next correction."""
    wu_repo, cr_repo, fr_repo, _, _ = repos
    work_unit = seed_work_unit(
        wu_repo,
        filing_year=PRIOR_YEAR,
        period_code="1T",
        operation=operation,
    )
    snapshot = operation.snapshot("130", filing_year=PRIOR_YEAR, period="1T")
    engine_inputs = {
        AMEND_INCOME_CASILLA: Decimal("8840"),
        validated_casilla_id("gastos-deducibles-previos"): Decimal("4982"),
        AMEND_WITHHELD_CASILLA: Decimal("0"),
        AMEND_PREVIOUS_PAYMENT_CASILLA: Decimal("0"),
        AMEND_HOME_DEDUCTION_CASILLA: Decimal("0"),
        AMEND_PRIOR_RETURN_RESULT_CASILLA: Decimal("0"),
        validated_casilla_id("rendimiento-neto-reducible-art-32-1"): Decimal("0"),
    }
    engine_bindings = {
        "modelo-130-actividad-economica-ingresos-cumulative": Decimal("8840"),
        "modelo-130-actividad-economica-gastos-cumulative": Decimal("4982"),
        "modelo-130-volumen-ingresos-agrario": Decimal("0"),
        "modelo-130-retenciones-agrarias": Decimal("0"),
        "modelo-130-pagos-fraccionados-anteriores": Decimal("0"),
        "modelo-130-resultados-negativos-anteriores": Decimal("0"),
        "irpf.previous_year_economic_activity_net_income": Decimal("0"),
    }
    engine_enum_bindings = {"modelo-130-estimacion-directa-modalidad": "directa_simplificada"}
    original_result = calculate_registry_snapshot(
        snapshot,
        inputs=engine_inputs,
        binding_values=engine_bindings,
        enum_binding_values=engine_enum_bindings,
        date_context={},
    )
    serialized_inputs = {key: str(value) for key, value in engine_inputs.items()}
    serialized_bindings = {key: str(value) for key, value in engine_bindings.items()} | engine_enum_bindings
    original_layer = CalculationOperatorLayer(
        decimal_casilla_inputs=serialized_inputs,
        binding_overrides=serialized_bindings,
    )
    _, original_revision, original = seed_external_baseline(
        repos,
        casilla_values=original_result.values,
        filing_year=PRIOR_YEAR,
        input_values_by_casilla_id=serialized_inputs,
        binding_overrides=serialized_bindings,
        observations=original_result.observations,
        operator_layer=original_layer,
        operation=operation,
    )
    original_saved = original_revision.model_dump(mode="json")

    first = amend_modelo_revision(
        ports=build_amendment_action_ports(bucket_id=PROFILE_ID, operation=operation),
        from_filing_record_id=original.filing_record_id,
        overrides={AMEND_INCOME_CASILLA: Decimal("10000")},
        amendment_kind=FilingDeclarationKind.COMPLEMENTARIA,
        reason="corrected turnover",
        actor="operator-A",
        clock=T4,
        operation=operation,
    )
    first_revision = cr_repo.load().revisions[first.calculation_revision_id]
    expected_original_04 = _expected_pago_fraccionado(snapshot, income=Decimal("8840"), expenses=Decimal("4982"))
    expected_first_04 = _expected_pago_fraccionado(snapshot, income=Decimal("10000"), expenses=Decimal("4982"))
    expected_first_17 = expected_first_04 - _MINORACION_PRIOR_INCOME_AT_MOST_9000
    expected_first_18 = expected_original_04 - _MINORACION_PRIOR_INCOME_AT_MOST_9000
    assert first_revision.casilla_values[validated_casilla_id("04")] == expected_first_04
    assert first_revision.casilla_values[validated_casilla_id("17")] == expected_first_17
    assert first_revision.casilla_values[validated_casilla_id("18")] == expected_first_18
    assert first_revision.casilla_values[validated_casilla_id("19")] == expected_first_17 - expected_first_18

    from datetime import timedelta

    receipt_time = T4 + timedelta(minutes=30)
    persist_matching_justificante("JUST130CORRECT1", work_unit, captured_at=receipt_time)
    confirmed_first = import_external_filing(
        repos,
        work_unit,
        casilla_values=first_revision.casilla_values,
        evidence_reference_id="JUST130CORRECT1",
        expected_tax_id=TAX_ID,
        clock=receipt_time,
        declared_kind=FilingDeclarationKind.COMPLEMENTARIA,
    )
    second = amend_modelo_revision(
        ports=build_amendment_action_ports(bucket_id=PROFILE_ID, operation=operation),
        from_filing_record_id=confirmed_first.filing_record_id,
        overrides={AMEND_INCOME_CASILLA: Decimal("11000")},
        amendment_kind=FilingDeclarationKind.COMPLEMENTARIA,
        reason="further corrected turnover",
        actor="operator-A",
        clock=receipt_time + timedelta(minutes=30),
        operation=operation,
    )
    second_revision = cr_repo.load().revisions[second.calculation_revision_id]
    expected_second_04 = _expected_pago_fraccionado(snapshot, income=Decimal("11000"), expenses=Decimal("4982"))
    expected_second_17 = expected_second_04 - _MINORACION_PRIOR_INCOME_AT_MOST_9000
    assert second_revision.casilla_values[validated_casilla_id("04")] == expected_second_04
    assert second_revision.casilla_values[validated_casilla_id("18")] == expected_first_17
    assert second_revision.casilla_values[validated_casilla_id("19")] == expected_second_17 - expected_first_17
    _assert_saved_content_kept(cr_repo.load().revisions[original_revision.calculation_revision_id], original_saved)

    records_before_decrease = fr_repo.load().model_dump(mode="json")
    revisions_before_decrease = cr_repo.load().model_dump(mode="json")
    with pytest.raises(AmendmentComplementariaLiabilityDecreaseError):
        amend_modelo_revision(
            ports=build_amendment_action_ports(bucket_id=PROFILE_ID, operation=operation),
            from_filing_record_id=second.filing_record_id,
            overrides={AMEND_WITHHELD_CASILLA: Decimal("400")},
            amendment_kind=FilingDeclarationKind.COMPLEMENTARIA,
            reason="decrease attempt",
            actor="operator-A",
            clock=receipt_time + timedelta(hours=1),
            operation=operation,
        )
    assert fr_repo.load().model_dump(mode="json") == records_before_decrease
    assert cr_repo.load().model_dump(mode="json") == revisions_before_decrease


def test_amend_new_filing_is_current_complementaria_record(
    repos: Repos, *, operation: PinnedAuthorityOperation
) -> None:
    outcome = drive_amend_creates_complementaria(repos, operation=operation)
    assert outcome.new_filing.status is ModeloRecordStatus.VIGENTE
    assert outcome.new_filing.amends_filing_record_id == outcome.baseline.filing_record_id
    assert outcome.new_filing.external_evidence is None


def test_amend_new_filing_records_filing_metadata(repos: Repos, *, operation: PinnedAuthorityOperation) -> None:
    outcome = drive_amend_creates_complementaria(repos, operation=operation)
    assert outcome.new_filing.filed_at == T4
    assert outcome.new_filing.filed_by == "operator-A"


def test_amend_inside_the_window_records_a_timely_complementaria(
    repos: Repos, *, operation: PinnedAuthorityOperation
) -> None:
    """A complementaria decides its own posture at its own presentation date.

    Ley 58/2003 art. 122.1 lets a complementaria be presented inside the plazo
    or after it; only in the second case is it extemporánea. The amend clock of
    this module's fixture falls inside the window its own work unit addresses,
    which the deadline resolved from that work unit confirms.
    """
    outcome = drive_amend_creates_complementaria(repos, operation=operation)
    deadline = resolve_effective_filing_deadline(
        str(outcome.work_unit.modelo),
        outcome.work_unit.filing_year,
        outcome.work_unit.period,
        operation=operation,
    )

    assert deadline is not None
    assert T4.astimezone(MADRID_TZ).date() <= deadline.closes_on
    assert outcome.new_filing.declaration_kind is FilingDeclarationKind.COMPLEMENTARIA
    assert outcome.new_filing.filing_timeliness is FilingTimeliness.EN_PLAZO


def test_amend_after_the_window_records_an_extemporanea_complementaria(
    repos: Repos, *, operation: PinnedAuthorityOperation
) -> None:
    """Past the window the complementaria is extemporánea (art. 122.1 in fine).

    It does not inherit the baseline's posture: the amendment is its own
    presentation, on its own date.
    """
    work_unit, _baseline_revision, baseline = seed_engine_computed_baseline(repos, operation=operation)
    deadline = resolve_effective_filing_deadline(
        str(work_unit.modelo),
        work_unit.filing_year,
        work_unit.period,
        operation=operation,
    )
    assert deadline is not None
    filed_late = datetime(
        deadline.closes_on.year, deadline.closes_on.month, deadline.closes_on.day, 12, 0, 0, tzinfo=UTC
    ) + timedelta(days=1)

    with bundled_indexed_authority().operation() as amend_operation:
        new_filing = amend_modelo_revision(
            ports=build_amendment_action_ports(bucket_id=PROFILE_ID, operation=amend_operation),
            from_filing_record_id=baseline.filing_record_id,
            overrides={AMEND_INCOME_CASILLA: Decimal("1100")},
            amendment_kind=FilingDeclarationKind.COMPLEMENTARIA,
            reason="under-reported turnover discovered after the window closed",
            actor="operator-A",
            clock=filed_late,
        )

    assert baseline.filing_timeliness is None, "the seeded external baseline decided no posture of its own"
    assert new_filing.filing_timeliness is FilingTimeliness.EXTEMPORANEA


def test_amend_baseline_is_superseded_by_new_filing(repos: Repos, *, operation: PinnedAuthorityOperation) -> None:
    outcome = drive_amend_creates_complementaria(repos, operation=operation)
    _, _, _fr_repo, _, _ = repos
    refreshed_baseline = persisted_filing_record(
        outcome.baseline.filing_record_id,
        ports=build_filing_action_ports(bucket_id=PROFILE_ID, operation=operation),
    )
    assert refreshed_baseline.status is ModeloRecordStatus.SUPERSEDIDO
    assert refreshed_baseline.superseded_by_filing_record_id == outcome.new_filing.filing_record_id


def test_amend_new_revision_is_filed_complementaria(repos: Repos, *, operation: PinnedAuthorityOperation) -> None:
    outcome = drive_amend_creates_complementaria(repos, operation=operation)
    _, _cr_repo, _, _, _ = repos
    with bundled_indexed_authority().operation() as operation:
        new_revision = get_calculation_revision(
            outcome.new_filing.calculation_revision_id,
            ports=build_calculation_action_ports(bucket_id=PROFILE_ID, operation=operation),
        )
        assert new_revision.state is CalculationRevisionState.PRESENTADO
    assert new_revision.amendment_identity is not None
    assert new_revision.amendment_identity.kind is FilingDeclarationKind.COMPLEMENTARIA
    assert new_revision.amendment_identity.amends_filing_record_id == outcome.baseline.filing_record_id
    assert new_revision.amendment_reason == "under-reported turnover discovered in audit"


def test_amend_member_scoped_filing_id_carries_member_nif(repos: Repos, *, operation: PinnedAuthorityOperation) -> None:
    """A member-scoped amendment's new filing record carries the baseline's
    ``member_nif`` -- both on the persisted record and in its derived id --
    rather than silently defaulting to the single-filer ``None`` slot."""

    _wu_repo, _cr_repo, _fr_repo, _, _bv_repo = repos
    _, _, baseline = seed_external_baseline(
        repos,
        casilla_values={AMEND_INCOME_CASILLA: Decimal("1000")},
        member_nif="A00010009",
        operation=operation,
    )
    assert baseline.member_nif == "A00010009"

    with bundled_indexed_authority().operation() as operation:
        new_filing = amend_modelo_revision(
            ports=build_amendment_action_ports(bucket_id=PROFILE_ID, operation=operation),
            from_filing_record_id=baseline.filing_record_id,
            overrides={AMEND_INCOME_CASILLA: Decimal("1100")},
            amendment_kind=FilingDeclarationKind.COMPLEMENTARIA,
            reason="member A turnover correction",
            actor="operator-A",
            clock=T4,
        )

    assert new_filing.member_nif == "A00010009"
    assert new_filing.filing_record_id == derive_filing_record_id(
        work_unit_id=new_filing.work_unit_id,
        calculation_revision_id=new_filing.calculation_revision_id,
        filed_by="operator-A",
        member_nif="A00010009",
    )


def test_amend_member_scoped_filing_does_not_collide_with_single_filer_record(
    repos: Repos, *, operation: PinnedAuthorityOperation
) -> None:
    """Amending a member-scoped baseline must not collide with an unrelated
    single-filer VIGENTE record sharing the same (modelo, year, period).

    Reproduces the second-order ``ModeloRecordCatalogue`` hazard the
    ``member_nif`` drop caused: without it, the amendment's new filing record
    would land on the single-filer ``None`` coordinate and collide with a
    genuine single-filer current record for the same (bucket, modelo,
    filing_year, period) -- surfacing as a confusing "more than one current
    filing record" catalogue error with no path back to the missing-member
    cause."""

    _wu_repo, _cr_repo, fr_repo, _, _bv_repo = repos
    work_unit, _, baseline_a = seed_external_baseline(
        repos,
        casilla_values={AMEND_INCOME_CASILLA: Decimal("1000")},
        member_nif="A00010009",
        operation=operation,
    )

    single_filer_revision_id = "b" * 64
    single_filer_filing_id = derive_filing_record_id(
        work_unit_id=work_unit.work_unit_id,
        calculation_revision_id=single_filer_revision_id,
        filed_by="aeat-import",
    )
    single_filer_filing = ModeloRecord(
        filing_record_id=single_filer_filing_id,
        work_unit_id=work_unit.work_unit_id,
        calculation_revision_id=single_filer_revision_id,
        bucket_id=work_unit.bucket_id,
        modelo=work_unit.modelo,
        filing_year=work_unit.filing_year,
        period=work_unit.period,
        filed_at=T1,
        filed_by="aeat-import",
        status=ModeloRecordStatus.VIGENTE,
        origin=FilingOrigin.LOCAL,
        confirmation=AeatConfirmationState.PENDIENTE,
        declaration_kind=FilingDeclarationKind.ORIGINAL,
    )
    fr_repo.save(upsert_filing_record(fr_repo.load(), single_filer_filing))

    with bundled_indexed_authority().operation() as operation:
        new_filing = amend_modelo_revision(
            ports=build_amendment_action_ports(bucket_id=PROFILE_ID, operation=operation),
            from_filing_record_id=baseline_a.filing_record_id,
            overrides={AMEND_INCOME_CASILLA: Decimal("1100")},
            amendment_kind=FilingDeclarationKind.COMPLEMENTARIA,
            reason="member A turnover correction",
            actor="operator-A",
            clock=T4,
        )

    assert new_filing.member_nif == "A00010009"
    refreshed_single_filer = persisted_filing_record(
        single_filer_filing_id,
        ports=build_filing_action_ports(bucket_id=PROFILE_ID, operation=operation),
    )
    assert refreshed_single_filer.status is ModeloRecordStatus.VIGENTE


def test_amend_overridden_casilla_takes_new_value(repos: Repos, *, operation: PinnedAuthorityOperation) -> None:
    outcome = drive_amend_creates_complementaria(repos, operation=operation)
    _, _cr_repo, _, _, _ = repos
    with bundled_indexed_authority().operation() as operation:
        new_revision = get_calculation_revision(
            outcome.new_filing.calculation_revision_id,
            ports=build_calculation_action_ports(bucket_id=PROFILE_ID, operation=operation),
        )
        assert new_revision.casilla_values[AMEND_INCOME_CASILLA] == Decimal("1100")


def test_amend_unoverridden_casilla_inherits_baseline_value(
    repos: Repos, *, operation: PinnedAuthorityOperation
) -> None:
    outcome = drive_amend_creates_complementaria(repos, operation=operation)
    _, _cr_repo, _, _, _ = repos
    with bundled_indexed_authority().operation() as operation:
        new_revision = get_calculation_revision(
            outcome.new_filing.calculation_revision_id,
            ports=build_calculation_action_ports(bucket_id=PROFILE_ID, operation=operation),
        )
        assert new_revision.casilla_values[AMEND_EXPENSE_CASILLA] == Decimal("55.00")


def test_amend_work_unit_pointers_advance_to_new_filing(repos: Repos, *, operation: PinnedAuthorityOperation) -> None:
    outcome = drive_amend_creates_complementaria(repos, operation=operation)
    _wu_repo, _, _, _, _ = repos
    refreshed_wu = get_work_unit(
        outcome.work_unit.work_unit_id,
        ports=build_work_lifecycle_ports(bucket_id=PROFILE_ID),
    )
    assert refreshed_wu.filed_calculation_revision_id == outcome.new_filing.calculation_revision_id
    assert refreshed_wu.current_filing_record_id == outcome.new_filing.filing_record_id


def test_amend_emits_single_modelo_amended_event(repos: Repos, *, operation: PinnedAuthorityOperation) -> None:
    outcome = drive_amend_creates_complementaria(repos, operation=operation)
    _, _, _, _, bv_repo = repos
    amended_events = bv_repo.load().for_bucket(
        outcome.work_unit.bucket_id,
        event_types=(BucketEventType.MODELO_AMENDED,),
    )
    assert len(amended_events) == 1


_AMENDED_EVENT_PAYLOAD_EXPECTATIONS = (
    ("amendment_kind", "complementaria"),
    ("override_count", "1"),
)


@pytest.mark.parametrize(("payload_key", "expected"), _AMENDED_EVENT_PAYLOAD_EXPECTATIONS)
def test_amend_amended_event_payload_records_metadata(
    repos: Repos, payload_key: str, expected: str, *, operation: PinnedAuthorityOperation
) -> None:
    outcome = drive_amend_creates_complementaria(repos, operation=operation)
    _, _, _, _, bv_repo = repos
    amended_events = bv_repo.load().for_bucket(
        outcome.work_unit.bucket_id,
        event_types=(BucketEventType.MODELO_AMENDED,),
    )
    assert amended_events[0].payload[payload_key] == expected


def test_amend_amended_event_targets_new_filing_record(repos: Repos, *, operation: PinnedAuthorityOperation) -> None:
    outcome = drive_amend_creates_complementaria(repos, operation=operation)
    _, _, _, _, bv_repo = repos
    amended_events = bv_repo.load().for_bucket(
        outcome.work_unit.bucket_id,
        event_types=(BucketEventType.MODELO_AMENDED,),
    )
    event = amended_events[0]
    assert event.object_id == outcome.new_filing.filing_record_id
    assert event.payload["amends_filing_record_id"] == outcome.baseline.filing_record_id

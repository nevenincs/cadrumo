"""Real persistence and registry coverage for the modelo work review projection."""

from __future__ import annotations

import importlib
from decimal import Decimal
from typing import TypedDict

import pytest
from pydantic import ValidationError

from ....core.modelo_work_progress_state import ModeloWorkProgressState
from ....core.period import Period
from ....core.aggregation import BindingSourceKind
from ....domain.calculations import RowSourceIdentity
from ....domain.calculations.registry.authority import bundled_authority
from ....domain.calculations.registry.bindings import CasillaObservation
from ....domain.calculations.registry.runtime_graph import revision_date_binding_ids
from ....domain.calculations.registry.schema_input_kind import InputKind
from ....domain.calculations.registry.temporal import select_revision
from ....domain.filing.schema import ModeloValueKind
from ....domain.modelos.calculation_repository import upsert_calculation_revision
from ....domain.modelos.codes import ModeloCode
from ....domain.modelos.protocols import CalculationRevisionCatalogueRepositoryProtocol, VerificationReportCatalogueRepositoryProtocol
from ....domain.modelos.repository import upsert_work_unit
from ....domain.modelos.verification_report import ModeloVerificationFinding, ModeloVerificationFindingKind, ModeloVerificationFindingSeverity, VerificationCompletenessStatus, VerificationReport, derive_verification_report_id
from ....domain.modelos.verification_repository import upsert_verification_report
from ....domain.modelos.work_unit import WorkUnit, derive_work_unit_id
from ....domain.modelos.calculation_revision import (
    CalculationRevision,
    CalculationRevisionState,
    derive_calculation_revision_id,
    derive_calculation_revision_id_from_revision,
)
from ....domain.modelos.work_unit_repository import WorkUnitCatalogueRepositoryProtocol
from ....domain.user_profile.values import UserProfileFact
from ....tests.profile_capsule import load_test_profile_record, replace_test_profile_record
from .._calculation_actions import calculate_modelo_revision
from ..work_review import (
    ModeloWorkOriginAnomaly,
    ModeloWorkProgress,
    ModeloWorkProgressDenominator,
    ModeloWorkReview,
    ModeloWorkReviewCapture,
    ModeloWorkReviewCaptureError,
    ModeloWorkReviewCurrentCoordinate,
    build_modelo_work_review,
    capture_modelo_work_review,
    read_modelo_work_review_current_coordinate,
)
from ._file_flow_support import (
    DEFAULT_130_BASELINE_INPUTS,
    DEFAULT_130_BINDING_VALUES,
    M130_CARRY_FORWARD_CASILLA,
    M130_INCOME_CASILLA,
    M130_NET_RESULT_CASILLA,
    T0,
    Repos,
    verify_revision,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]
_BUCKET_ID = "11111111-1111-4111-8111-111111111111"
_M130 = ModeloCode("130")
_M130_INCOME_BINDING = "modelo-130-actividad-economica-ingresos-cumulative"


def test_review_projection_has_one_public_defining_module_and_no_package_facade() -> None:
    """The application package cannot become a second home for review symbols."""
    namespace = importlib.import_module("cadrumo.application.modelo")
    review_symbols = (
        "BlockerRef",
        "ModeloWorkBindingOrigin",
        "ModeloWorkFormulaOrigin",
        "ModeloWorkOriginAnomaly",
        "ModeloWorkProgress",
        "ModeloWorkProgressDenominator",
        "ModeloWorkRelationConsumption",
        "ModeloWorkReview",
        "ModeloWorkReviewCasilla",
        "build_modelo_work_review",
    )

    assert set(review_symbols).isdisjoint(vars(namespace))
    assert ModeloWorkReview.__module__ == "cadrumo.application.modelo.work_review"
    assert build_modelo_work_review.__module__ == "cadrumo.application.modelo.work_review"


def _persist_work_unit(
    repos: Repos,
    *,
    modelo: ModeloCode = _M130,
    filing_year: int = 2026,
    period_code: str = "1T",
) -> WorkUnit:
    work_repo, _, _, _, _ = repos
    period = Period.from_year_and_code(filing_year, period_code)
    authority = bundled_authority()
    selected_revision = select_revision(
        authority.validate_modelo(modelo),
        filing_year=filing_year,
        period=period.registry_token,
    )
    revision_id = authority.snapshot(
        modelo,
        filing_year=filing_year,
        period=period.registry_token,
        revision_id=selected_revision.id,
        grade=selected_revision.effective_authority_grade,
    ).revision.id
    unit = WorkUnit(
        work_unit_id=derive_work_unit_id(
            bucket_id=_BUCKET_ID,
            modelo=modelo,
            filing_year=filing_year,
            period=period,
            revision_id=revision_id,
        ),
        bucket_id=_BUCKET_ID,
        modelo=modelo,
        filing_year=filing_year,
        period=period,
        revision_id=revision_id,
        name="130-2026-1T",
        created_at=T0,
        updated_at=T0,
    )
    work_repo.save(upsert_work_unit(work_repo.load(), unit))
    return unit


def test_review_projects_resolvable_work_without_a_calculation_from_real_storage(repos: Repos) -> None:
    work_repo, calculation_repo, _, verification_repo, _ = repos
    work_unit = _persist_work_unit(repos)
    authority = bundled_authority()

    review = build_modelo_work_review(
        work_unit.bucket_id,
        work_unit.modelo,
        work_unit.filing_year,
        work_unit.period,
        authority=authority,
        work_unit_repository=work_repo,
        calculation_repository=calculation_repo,
        verification_repository=verification_repo,
    )

    assert isinstance(review, ModeloWorkReview)
    assert (
        review.registry_revision_id
        == authority.snapshot(
            str(work_unit.modelo),
            filing_year=work_unit.filing_year,
            period=work_unit.period.registry_token,
        ).revision.id
    )
    assert review.registry_revision_id == work_unit.revision_id
    assert review.calculation_revision_id is None
    assert review.lifecycle_state is None
    assert review.verification_outcome is None
    assert review.progress.state is ModeloWorkProgressState.IN_PROGRESS
    assert review.progress.materialised_count == 0
    manifest = authority.snapshot(
        str(work_unit.modelo),
        filing_year=work_unit.filing_year,
        period=work_unit.period.registry_token,
    ).revision.completeness_manifest
    assert manifest is not None
    assert review.progress.target_count == len(manifest.casillas)
    assert review.progress.denominator is not None
    assert review.progress.denominator.registry_revision_id == review.registry_revision_id
    assert review.progress.denominator.source_ref == "aeat-dr-130-2019-v12"
    assert review.findings == ()
    assert review.blockers == ()
    assert review.casillas
    assert all(row.realised_kind is ModeloValueKind.EMPTY and row.value is None for row in review.casillas)
    computed = next(row for row in review.casillas if row.casilla_id == M130_NET_RESULT_CASILLA)
    assert computed.declared_input_kind is InputKind.COMPUTED
    assert computed.origin_anomaly is ModeloWorkOriginAnomaly.BROKEN_CALCULATION_CHAIN


def test_review_progress_is_undefined_without_a_revision_manifest(repos: Repos) -> None:
    work_repo, calculation_repo, _, verification_repo, _ = repos
    work_unit = _persist_work_unit(
        repos,
        modelo=ModeloCode("189"),
        filing_year=2025,
        period_code="0A",
    )

    review = build_modelo_work_review(
        work_unit.bucket_id,
        work_unit.modelo,
        work_unit.filing_year,
        work_unit.period,
        authority=bundled_authority(),
        work_unit_repository=work_repo,
        calculation_repository=calculation_repo,
        verification_repository=verification_repo,
    )

    assert review.progress.state is ModeloWorkProgressState.UNDEFINED
    assert review.progress.materialised_count is None
    assert review.progress.target_count is None
    assert review.progress.denominator is None


def test_review_progress_reads_a_persisted_blocking_verdict(repos: Repos) -> None:
    work_repo, calculation_repo, _, verification_repo, _ = repos
    work_unit = _persist_work_unit(repos)
    snapshot = bundled_authority().snapshot(
        str(work_unit.modelo),
        filing_year=work_unit.filing_year,
        period=work_unit.period.registry_token,
    )
    manifest = snapshot.revision.completeness_manifest
    assert manifest is not None
    target = manifest.casillas[0]
    target_definition = next(casilla for casilla in snapshot.revision.casillas if casilla.id == target.casilla_id)
    target_value = Decimal("1")
    casilla_values = {target.casilla_id: target_value}
    revision_id = derive_calculation_revision_id(
        work_unit_id=work_unit.work_unit_id,
        input_values_by_casilla_id={},
        binding_overrides={},
        casilla_values=casilla_values,
        filing_instance_evidence=None,
        source_provenance=(),
    )
    revision = CalculationRevision(
        calculation_revision_id=revision_id,
        work_unit_id=work_unit.work_unit_id,
        state=CalculationRevisionState.BORRADOR,
        casilla_values=casilla_values,
        observations=(
            CasillaObservation(
                casilla_id=target.casilla_id,
                value=target_value,
                legal_refs=tuple(target_definition.legal_refs),
                source_refs=tuple(target_definition.source_refs),
            ),
        ),
        created_at=T0,
        updated_at=T0,
        filing_instance_evidence=None,
        source_provenance=(),
    )
    calculation_repo.save(upsert_calculation_revision(calculation_repo.load(), revision))
    work_repo.save(
        upsert_work_unit(
            work_repo.load(),
            work_unit.model_copy(update={"current_calculation_revision_id": revision_id}),
        ),
    )
    finding = ModeloVerificationFinding(
        kind=ModeloVerificationFindingKind.BLOCKING_RULE,
        severity=ModeloVerificationFindingSeverity.BLOCKING,
        casilla_id=target.casilla_id,
        message_locale_key="application.modelo.findings.blocking_rule",
        message_facts={"casilla_id": str(target.casilla_id)},
        legal_refs=tuple(manifest.legal_refs),
        source_refs=tuple(manifest.source_refs),
    )
    report_id = derive_verification_report_id(
        calculation_revision_id=revision_id,
        completeness_status=VerificationCompletenessStatus.BLOCKED,
        findings=(finding,),
        verified_by="operator-A",
    )
    report = VerificationReport(
        verification_report_id=report_id,
        calculation_revision_id=revision_id,
        completeness_status=VerificationCompletenessStatus.BLOCKED,
        findings=(finding,),
        run_at=T0,
        verified_by="operator-A",
        granted_verificado_completo=False,
    )
    verification_repo.save(upsert_verification_report(verification_repo.load(), report))

    review = build_modelo_work_review(
        work_unit.bucket_id,
        work_unit.modelo,
        work_unit.filing_year,
        work_unit.period,
        authority=bundled_authority(),
        work_unit_repository=work_repo,
        calculation_repository=calculation_repo,
        verification_repository=verification_repo,
    )

    assert review.progress.state is ModeloWorkProgressState.BLOCKED
    assert review.progress.materialised_count == 1
    assert review.progress.target_count == len(manifest.casillas)


def test_review_progress_schema_refuses_unnamed_or_impossible_counts() -> None:
    denominator = ModeloWorkProgressDenominator(
        registry_revision_id="2019-y-siguientes",
        source_ref="aeat-dr-130-2019-v12",
    )
    with pytest.raises(ValidationError, match="undefined modelo work progress"):
        ModeloWorkProgress(
            state=ModeloWorkProgressState.UNDEFINED,
            materialised_count=0,
            target_count=1,
            denominator=denominator,
        )
    with pytest.raises(ValidationError, match="cannot exceed"):
        ModeloWorkProgress(
            state=ModeloWorkProgressState.IN_PROGRESS,
            materialised_count=2,
            target_count=1,
            denominator=denominator,
        )


def test_review_progress_fields_do_not_express_a_ratio() -> None:
    forbidden = ("percent", "percentage", "fraction", "ratio", "pct", "coverage_rate", "completeness")
    schema = ModeloWorkReview.model_json_schema()
    pending: list[object] = [schema]
    names: list[str] = []
    while pending:
        node = pending.pop()
        if isinstance(node, dict):
            properties = node.get("properties")
            if isinstance(properties, dict):
                names.extend(str(name) for name in properties)
            pending.extend(node.values())
        elif isinstance(node, list):
            pending.extend(node)
    joined_names = " ".join(names).casefold()
    assert all(token not in joined_names for token in forbidden)
    assert all(field.annotation is not float for field in ModeloWorkProgress.model_fields.values())


def test_review_joins_real_persisted_calculation_into_origin_layers(repos: Repos) -> None:
    work_repo, calculation_repo, filing_repo, verification_repo, bucket_event_repo = repos
    work_unit = _persist_work_unit(repos)
    profile = load_test_profile_record(_BUCKET_ID)
    replace_test_profile_record(
        profile.model_copy(
            update={
                "facts": (
                    *profile.facts,
                    UserProfileFact(path="iva.m303_regime_composition", value="general"),
                    UserProfileFact(path="iva.redeme_enrolled", value=False),
                    UserProfileFact(path="iva.cash_accounting_regime_enrolled", value=False),
                    UserProfileFact(path="iva.voluntary_sii_enrolled", value=False),
                    UserProfileFact(
                        path="iva.hydrocarbon_deposit_advance_payment_deduction_entitled",
                        value=False,
                    ),
                ),
            },
        ),
    )
    revision = calculate_modelo_revision(
        work_unit.work_unit_id,
        casilla_inputs=DEFAULT_130_BASELINE_INPUTS,
        binding_values={**DEFAULT_130_BINDING_VALUES, _M130_INCOME_BINDING: Decimal("9000")},
        work_unit_repository=work_repo,
        calculation_repository=calculation_repo,
        bucket_event_repository=bucket_event_repo,
    )

    review = build_modelo_work_review(
        work_unit.bucket_id,
        work_unit.modelo,
        work_unit.filing_year,
        work_unit.period,
        authority=bundled_authority(),
        work_unit_repository=work_repo,
        calculation_repository=calculation_repo,
        verification_repository=verification_repo,
    )
    rows = {row.casilla_id: row for row in review.casillas}

    assert review.calculation_revision_id == revision.calculation_revision_id
    assert review.lifecycle_state is revision.state
    assert rows[M130_INCOME_CASILLA].realised_kind is ModeloValueKind.LITERAL
    assert rows[M130_INCOME_CASILLA].value == Decimal("10000")
    assert rows[M130_INCOME_CASILLA].origin_anomaly is ModeloWorkOriginAnomaly.OPERATOR_OVERRIDE
    assert rows[M130_INCOME_CASILLA].concrete_bindings
    assert rows[M130_INCOME_CASILLA].concrete_bindings[0].resolved is True
    assert rows[M130_NET_RESULT_CASILLA].realised_kind is ModeloValueKind.COMPUTED
    assert rows[M130_NET_RESULT_CASILLA].value == Decimal("7000")
    assert rows[M130_NET_RESULT_CASILLA].origin_anomaly is None
    assert rows[M130_CARRY_FORWARD_CASILLA].realised_kind is ModeloValueKind.COMPUTED
    carry_forward_formula = rows[M130_CARRY_FORWARD_CASILLA].concrete_formula
    assert carry_forward_formula is not None
    assert "modelo-130-resultados-negativos-anteriores" in carry_forward_formula.operand_refs

    equal_value_revision = calculate_modelo_revision(
        work_unit.work_unit_id,
        casilla_inputs=DEFAULT_130_BASELINE_INPUTS,
        binding_values={**DEFAULT_130_BINDING_VALUES, _M130_INCOME_BINDING: Decimal("10000")},
        work_unit_repository=work_repo,
        calculation_repository=calculation_repo,
        bucket_event_repository=bucket_event_repo,
    )
    equal_value_review = build_modelo_work_review(
        work_unit.bucket_id,
        work_unit.modelo,
        work_unit.filing_year,
        work_unit.period,
        authority=bundled_authority(),
        work_unit_repository=work_repo,
        calculation_repository=calculation_repo,
        verification_repository=verification_repo,
    )
    equal_value_income = next(row for row in equal_value_review.casillas if row.casilla_id == M130_INCOME_CASILLA)
    assert equal_value_review.calculation_revision_id == equal_value_revision.calculation_revision_id
    assert equal_value_income.realised_kind is ModeloValueKind.INHERITED
    assert equal_value_income.origin_anomaly is None
    assert equal_value_income.concrete_bindings[0].resolved is True

    verification = verify_revision(
        equal_value_revision.calculation_revision_id,
        revision=equal_value_revision,
        work_unit=work_unit,
        work_unit_repository=work_repo,
        calculation_repository=calculation_repo,
        verification_repository=verification_repo,
        filing_repository=filing_repo,
        bucket_event_repository=bucket_event_repo,
        clock=equal_value_revision.updated_at,
    )
    verified_review = build_modelo_work_review(
        work_unit.bucket_id,
        work_unit.modelo,
        work_unit.filing_year,
        work_unit.period,
        authority=bundled_authority(),
        work_unit_repository=work_repo,
        calculation_repository=calculation_repo,
        verification_repository=verification_repo,
    )
    assert verification.completeness_status is VerificationCompletenessStatus.COMPLETE
    assert verified_review.progress.state is ModeloWorkProgressState.COMPLETE
    assert verified_review.progress.materialised_count == verified_review.progress.target_count


def test_real_review_projects_only_fingerprint_for_persisted_row_identity(repos: Repos) -> None:
    work_repo, calculation_repo, _, verification_repo, bucket_event_repo = repos
    work_unit = _persist_work_unit(repos)
    revision = calculate_modelo_revision(
        work_unit.work_unit_id,
        casilla_inputs=DEFAULT_130_BASELINE_INPUTS,
        binding_values=DEFAULT_130_BINDING_VALUES,
        work_unit_repository=work_repo,
        calculation_repository=calculation_repo,
        bucket_event_repository=bucket_event_repo,
    )
    raw_identity = "opaque-review-row-canary"
    fingerprint = "d" * 64
    amended = revision.model_copy(
        update={
            "row_binding_values": {"review-row-binding": {"1": "100"}},
            "row_source_identities": {
                ("review-row-binding", 1): RowSourceIdentity(
                    source_kind=BindingSourceKind.INVENTORY,
                    source_row_identity=raw_identity,
                    fingerprint=fingerprint,
                ),
            },
        },
    )
    amended = amended.model_copy(
        update={"calculation_revision_id": derive_calculation_revision_id_from_revision(amended)},
    )
    calculation_repo.save(upsert_calculation_revision(calculation_repo.load(), amended))
    stored_work = work_repo.load().get(work_unit.work_unit_id)
    assert stored_work is not None
    work_repo.save(
        upsert_work_unit(
            work_repo.load(),
            stored_work.model_copy(update={"current_calculation_revision_id": amended.calculation_revision_id}),
        ),
    )

    review = build_modelo_work_review(
        work_unit.bucket_id,
        work_unit.modelo,
        work_unit.filing_year,
        work_unit.period,
        authority=bundled_authority(),
        work_unit_repository=work_repo,
        calculation_repository=calculation_repo,
        verification_repository=verification_repo,
    )

    assert [item.model_dump(mode="json") for item in review.row_source_fingerprints] == [
        {
            "binding_id": "review-row-binding",
            "row_index": 1,
            "source_kind": "inventory",
            "fingerprint": fingerprint,
        },
    ]
    rendered = f"{review!r} {review.model_dump()!r} {review.model_dump_json()}"
    assert raw_identity not in rendered


def test_review_reads_persisted_date_bindings_without_decimal_reinterpretation(repos: Repos) -> None:
    work_repo, calculation_repo, _, verification_repo, _ = repos
    work_unit = _persist_work_unit(
        repos,
        modelo=ModeloCode("100"),
        filing_year=2025,
        period_code="0A",
    )
    snapshot = bundled_authority().snapshot(
        str(work_unit.modelo),
        filing_year=work_unit.filing_year,
        period=work_unit.period.registry_token,
    )
    date_binding_id = next(iter(sorted(revision_date_binding_ids(snapshot.revision))))
    binding_overrides = {date_binding_id: "1980-01-01"}
    revision_id = derive_calculation_revision_id(
        work_unit_id=work_unit.work_unit_id,
        input_values_by_casilla_id={},
        binding_overrides=binding_overrides,
        casilla_values={},
        filing_instance_evidence=None,
        source_provenance=(),
    )
    revision = CalculationRevision(
        calculation_revision_id=revision_id,
        work_unit_id=work_unit.work_unit_id,
        state=CalculationRevisionState.BORRADOR,
        binding_overrides=binding_overrides,
        created_at=T0,
        updated_at=T0,
        filing_instance_evidence=None,
        source_provenance=(),
    )
    calculation_repo.save(upsert_calculation_revision(calculation_repo.load(), revision))
    work_repo.save(
        upsert_work_unit(
            work_repo.load(),
            work_unit.model_copy(update={"current_calculation_revision_id": revision_id}),
        ),
    )

    review = build_modelo_work_review(
        work_unit.bucket_id,
        work_unit.modelo,
        work_unit.filing_year,
        work_unit.period,
        authority=bundled_authority(),
        work_unit_repository=work_repo,
        calculation_repository=calculation_repo,
        verification_repository=verification_repo,
    )

    assert review.calculation_revision_id == revision_id


class _ReviewArguments(TypedDict):
    work_unit_repository: WorkUnitCatalogueRepositoryProtocol
    calculation_repository: CalculationRevisionCatalogueRepositoryProtocol
    verification_repository: VerificationReportCatalogueRepositoryProtocol


def _review_arguments(repos: Repos) -> _ReviewArguments:
    work_repo, calculation_repo, _filing_repo, verification_repo, _events = repos
    return {
        "work_unit_repository": work_repo,
        "calculation_repository": calculation_repo,
        "verification_repository": verification_repo,
    }


def test_captured_review_is_the_exact_assembler_record_field_for_field(repos: Repos) -> None:
    """The capture republishes the sole assembler output without reconstruction."""
    _persist_work_unit(repos)
    arguments = _review_arguments(repos)
    period = Period.from_year_and_code(2026, "1T")

    assembled = build_modelo_work_review(_BUCKET_ID, _M130, 2026, period, **arguments)
    captured = capture_modelo_work_review(_BUCKET_ID, _M130, 2026, period, **arguments)

    assert captured.review == assembled
    assert captured.review.model_fields_set == assembled.model_fields_set


def test_review_capture_is_singleflight_and_refuses_a_superseded_coordinate(repos: Repos) -> None:
    """An unchanged join shares a generation; a catalogue write supersedes it."""
    unit = _persist_work_unit(repos)
    work_repo, _calculation_repo, _filing_repo, _verification_repo, _events = repos
    arguments = _review_arguments(repos)
    period = Period.from_year_and_code(2026, "1T")

    first = capture_modelo_work_review(_BUCKET_ID, _M130, 2026, period, **arguments)
    second = capture_modelo_work_review(_BUCKET_ID, _M130, 2026, period, **arguments)

    assert first.generation == second.generation
    assert first.comparison_domain == second.comparison_domain

    current = read_modelo_work_review_current_coordinate(_BUCKET_ID, _M130, 2026, period, **arguments)
    assert first.require_current(current) is first

    work_repo.save(upsert_work_unit(work_repo.load(), unit.model_copy(update={"name": "130-2026-1T-renamed"})))

    advanced = read_modelo_work_review_current_coordinate(_BUCKET_ID, _M130, 2026, period, **arguments)

    assert advanced.generation > first.generation
    with pytest.raises(ModeloWorkReviewCaptureError):
        first.require_current(advanced)


def test_review_capture_contract_is_owned_by_its_defining_module() -> None:
    """Every review symbol is defined here and bound nowhere in the package namespace."""
    from ....application import modelo as modelo_namespace

    for owned in (
        ModeloWorkReviewCapture,
        ModeloWorkReviewCurrentCoordinate,
        ModeloWorkReviewCaptureError,
        capture_modelo_work_review,
        read_modelo_work_review_current_coordinate,
        build_modelo_work_review,
    ):
        assert owned.__module__ == "cadrumo.application.modelo.work_review"
        assert not hasattr(modelo_namespace, owned.__name__)


def test_the_retired_projection_module_is_gone_with_no_bridge() -> None:
    """The hard move leaves no module, shim, alias, or re-export behind."""
    from pathlib import Path as _Path

    from .. import work_review as owning_module

    retired = _Path(owning_module.__file__).with_name("work_review_projection.py")

    assert not retired.exists()
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("cadrumo.application.modelo.work_review_projection")

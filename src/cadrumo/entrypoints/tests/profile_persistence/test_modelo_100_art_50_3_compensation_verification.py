"""Verify the Modelo 100 compensation of pending negative general bases against LIRPF art. 50.3.

Art. 50.3 lets a negative base liquidable general be compensated only against
the positive base liquidable general of the four following years, and "La
compensación deberá efectuarse en la cuantía máxima que permita cada uno de los
ejercicios siguientes". The amount applied this year (casilla 1389) is therefore
fixed: the smaller of the pending stock (1388) and the positive base liquidable
general before the compensation. Applying less, applying more, applying any
amount with no stock behind it, and an amount that cannot yet be worked out all
refuse verification.

Each case runs the real calculation and the real verification over encrypted
profile storage, and reads only the findings of the two Art. 50.3 gates. The
expected maximum is derived here from the statutory rule and the calculated
base, not read back from the registry formula. An unknown stock already stops
the calculation, so no revision with an unresolved maximum reaches the gates.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from uuid import UUID

import pytest

from cadrumo.application.modelo.calculation_source_policy import BUCKET_AGGREGATION_LOCK_SOURCES
from cadrumo.domain.user_profile.tests.general_regime_facts import GENERAL_REGIME_NATURAL_PERSON_FACTS
from cadrumo.domain.user_profile.tests.profile_creation_authority import (
    profile_creation_context_for_test as _profile_creation_context_for_test,
)
from cadrumo.entrypoints.tests.profile_persistence.verification_repository_support import (
    build_test_certificate_secret_backend_factory,
    build_test_verification_repository_bundle,
)

from ....adapters.persistence.profile.buckets import BucketEventHistoryRepository
from ....adapters.persistence.profile.calculation_observations import CalculationObservationRepository
from ....adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from ....adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from ....adapters.persistence.profile.tests.published_authority_support import published_authority_operation
from ....adapters.persistence.storage.operator_scope import build_operator_scope_ports
from ....adapters.persistence.storage.tests.profile_capsule_runtime import seed_test_profile_record
from ....adapters.persistence.storage.tests.secure_sql import isolated_runtime_profile
from ....application.aggregation.retencion_soportada_absence_repository import attest_retencion_soportada_absence
from ....application.modelo.calculation_bucket_actions import (
    calculate_modelo_revision_from_bucket_aggregation_with_diagnostics,
)
from ....application.modelo.operation_shared import resolve_active_workflow_profile
from ....application.modelo.verification_actions import verify_modelo_revision_with_preconditions
from ....application.modelo.work_lifecycle import create_work_unit
from ....application.modelo.work_missing_input import ModeloWorkMissingInputError
from ....core.casilla_id import CasillaId, validated_casilla_id
from ....core.period import Period
from ....core.retencion_soportada import RetencionSoportadaClase
from ....core.secure_object_write import ABSENT_SECURE_OBJECT_REVISION_ID
from ....domain.calculations.registry.authority import bundled_indexed_authority
from ....domain.calculations.registry.ids import BindingId, RelationId
from ....domain.calculations.registry.relations import relation_prefill_bindings_for_period
from ....domain.calculations.registry.tests.registry_observations import registry_grounded_modelo_observation
from ....domain.modelos.calculation_revision import CalculationRevision
from ....domain.modelos.verification_report import (
    ModeloVerificationFinding,
    ModeloVerificationFindingKind,
    ModeloVerificationFindingSeverity,
)
from ....domain.renta.retencion_soportada_absence import RetencionSoportadaAbsence
from ....domain.user_profile.values import ProfileSetupState, UserProfileFact
from ....domain.user_profile.values import create_user_profile_record as _create_profile_record_for_test
from ...adapter_composition_work_ports import build_work_lifecycle_ports
from ...retencion_soportada_absence_composition import build_retencion_soportada_absence_ports
from .file_flow_test_support import calculation_ports_for_test
from .general_iva_profile_facts_support import renta_single_taxpayer_facts
from .observation_seeding_support import save_stamped_observation

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_MODELO = "100"
_PERIOD = "0A"
_FILING_YEAR = 2025
_PROFILE_ID = "10010000-0000-4100-8100-000000000503"
_CLOCK = datetime(2026, 6, 30, 9, 0, 0, tzinfo=UTC)

_STOCK_PREDICATE_ID = "modelo-100-2025-compensacion-base-neg-general-no-excede-stock"
_MAXIMUM_PREDICATE_ID = "modelo-100-2025-compensacion-base-neg-general-cuantia-maxima"
_NOT_AT_MAXIMUM_KEY = "application.modelo.findings.application_not_required_maximum"
_MAXIMUM_UNRESOLVED_KEY = "application.modelo.findings.required_maximum_unresolved"

#: Pending at the start of the year, carried from the prior return's 1391.
_PENDING_STOCK: CasillaId = validated_casilla_id("1388")
#: Applied this year; the Form 100 compensation line 0501 is its total.
_APPLIED: CasillaId = validated_casilla_id("1389")
_COMPENSATION: CasillaId = validated_casilla_id("0501")
_PRIOR_GENERATED: CasillaId = validated_casilla_id("1391")
_BASE_IMPONIBLE_GENERAL: CasillaId = validated_casilla_id("0435")
_BASE_LIQUIDABLE_GENERAL: CasillaId = validated_casilla_id("0500")
#: Retribuciones dinerarias, importe íntegro: this unit's only income.
_WORK_INCOME: CasillaId = validated_casilla_id("0003")
_PRIOR_NEGATIVE_BASE_BINDING: BindingId = "renta-base-liquidable-negativa-general-anterior"


def _seed_profile() -> None:
    record = _create_profile_record_for_test(
        setup_state=ProfileSetupState.COMPLETE,
        profile_id=_PROFILE_ID,
        facts=(
            UserProfileFact(path="identity.tax_id", value="12345678Z"),
            UserProfileFact(path="identity.name", value="Test"),
            UserProfileFact(path="identity.surnames", value="Operator"),
            *(
                fact
                for fact in GENERAL_REGIME_NATURAL_PERSON_FACTS
                if fact.path not in {"taxpayer_type.irpf_income_categories", "irpf.estimation_regime"}
            ),
            UserProfileFact(path="taxpayer_type.irpf_income_categories", value="trabajo"),
            *renta_single_taxpayer_facts(birth_date=date(1980, 3, 15)),
        ),
        created_at=_CLOCK,
        updated_at=_CLOCK,
        context=_profile_creation_context_for_test(),
    )
    seed_test_profile_record(record)
    # The 0596 withholding comes only from the register; here it records that no payer withheld.
    with bundled_indexed_authority().operation() as operation:
        attest_retencion_soportada_absence(
            RetencionSoportadaAbsence(
                ejercicio=_FILING_YEAR,
                income_class=RetencionSoportadaClase.TRABAJO,
                note="No payer withheld on this income in the ejercicio.",
                attested_at=_CLOCK,
            ),
            ports=build_retencion_soportada_absence_ports(profile_id=UUID(_PROFILE_ID), operation=operation),
            expected_revision_id=ABSENT_SECURE_OBJECT_REVISION_ID,
        )


def _seed_prior_negative_base(saldo: Decimal) -> None:
    """Record the prior return's generated negative general base, which 1388 carries."""
    save_stamped_observation(
        CalculationObservationRepository(),
        registry_grounded_modelo_observation(
            modelo=_MODELO,
            filing_year=_FILING_YEAR - 1,
            period=_PERIOD,
            casilla_values={_PRIOR_GENERATED: saldo},
        ),
        source_kind="app_filing",
        captured_at=_CLOCK,
    )


def _operator_zeros() -> tuple[dict[BindingId, Decimal], dict[RelationId, Decimal]]:
    """Zero every operator-owned channel except the withholding register and the prior-year carry."""
    snapshot = published_authority_operation().snapshot(_MODELO, filing_year=_FILING_YEAR, period=_PERIOD)
    binding_values = {
        binding.id: Decimal("0")
        for binding in snapshot.revision.bindings
        if binding.source != "profile"
        and binding.source not in BUCKET_AGGREGATION_LOCK_SOURCES
        and binding.provider.kind not in {"retencion_soportada", "previous_filing"}
    }
    relation_values = {
        binding.id: Decimal("0")
        for binding, _provider in relation_prefill_bindings_for_period(snapshot.revision, period=snapshot.period)
    }
    return binding_values, relation_values


def _calculate(
    *,
    work_income: Decimal,
    applied: Decimal,
    binding_overrides: Mapping[BindingId, Decimal],
) -> CalculationRevision:
    binding_values, relation_values = _operator_zeros()
    binding_values.update(binding_overrides)
    with bundled_indexed_authority().operation() as operation:
        work_unit = create_work_unit(
            bucket_id=_PROFILE_ID,
            modelo=_MODELO,
            filing_year=_FILING_YEAR,
            period=Period.from_year_and_code(_FILING_YEAR, _PERIOD),
            revision_id=str(_FILING_YEAR),
            ports=build_work_lifecycle_ports(bucket_id=_PROFILE_ID),
            operation=operation,
            clock=_CLOCK,
        )
        with calculation_ports_for_test(
            bucket_id=_PROFILE_ID,
            work_unit_repository=WorkUnitCatalogueRepository(),
            calculation_repository=CalculationRevisionCatalogueRepository(),
            bucket_event_repository=BucketEventHistoryRepository(),
        ) as ports:
            return calculate_modelo_revision_from_bucket_aggregation_with_diagnostics(
                work_unit.work_unit_id,
                actor=_PROFILE_ID,
                casilla_inputs={_WORK_INCOME: work_income, _APPLIED: applied},
                binding_values=binding_values,
                relation_values=relation_values,
                ports=ports,
                clock=_CLOCK,
            ).revision


def _art_50_3_findings(revision: CalculationRevision) -> dict[str, ModeloVerificationFinding]:
    """Verify the revision and return the two Art. 50.3 gates' findings by predicate id."""
    with bundled_indexed_authority().operation() as operation:
        report = verify_modelo_revision_with_preconditions(
            str(revision.calculation_revision_id),
            certificate_secret_backend_factory=build_test_certificate_secret_backend_factory(),
            operator_scope_ports=build_operator_scope_ports(),
            actor="art-50-3-verification",
            workflow_profile=resolve_active_workflow_profile(operation),
            verification_repositories=build_test_verification_repository_bundle(),
            clock=_CLOCK,
            operation=operation,
        ).report
    findings: dict[str, ModeloVerificationFinding] = {}
    for finding in report.findings:
        predicate_id = finding.message_facts.get("predicate_id")
        if predicate_id in {_STOCK_PREDICATE_ID, _MAXIMUM_PREDICATE_ID}:
            assert finding.kind is ModeloVerificationFindingKind.BLOCKING_RULE
            assert finding.severity is ModeloVerificationFindingSeverity.BLOCKING
            assert "ley-35-2006:art-50" in finding.legal_refs
            findings[str(predicate_id)] = finding
    if findings:
        assert report.granted_verificado_completo is False
    return findings


def _statutory_maximum(revision: CalculationRevision, stock: Decimal) -> Decimal:
    """The art. 50.3 maximum: the smaller of the stock and the positive base before compensation."""
    values = revision.casilla_values
    base_before_compensation = values[_BASE_LIQUIDABLE_GENERAL] + values[_COMPENSATION]
    return min(stock, max(Decimal("0"), base_before_compensation))


def _assert_not_at_maximum(finding: ModeloVerificationFinding, *, applied: Decimal, maximum: Decimal) -> None:
    assert finding.casilla_id == _APPLIED
    assert finding.message_locale_key == _NOT_AT_MAXIMUM_KEY
    assert dict(finding.message_facts) == {
        "predicate_id": _MAXIMUM_PREDICATE_ID,
        "box": _APPLIED,
        "casilla_value": applied,
        "computed_value": maximum,
    }


@pytest.mark.parametrize(
    ("applied", "stock_refused"),
    (
        pytest.param(Decimal("2000.00"), False, id="under-application"),
        pytest.param(Decimal("3500.00"), True, id="over-application"),
    ),
)
def test_an_application_other_than_the_maximum_is_refused(
    tmp_path: Path,
    applied: Decimal,
    stock_refused: bool,
) -> None:
    """With 3,000 pending and a larger positive base, art. 50.3 requires exactly 3,000."""
    stock = Decimal("3000.00")
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_PROFILE_ID):
        _seed_profile()
        _seed_prior_negative_base(stock)
        revision = _calculate(work_income=Decimal("40000.00"), applied=applied, binding_overrides={})
        findings = _art_50_3_findings(revision)

    assert revision.casilla_values[_PENDING_STOCK] == stock
    maximum = _statutory_maximum(revision, stock)
    assert maximum == stock
    assert (_STOCK_PREDICATE_ID in findings) is stock_refused
    _assert_not_at_maximum(findings[_MAXIMUM_PREDICATE_ID], applied=applied, maximum=maximum)


def test_the_exact_maximum_passes_both_gates(tmp_path: Path) -> None:
    """Applying the whole stock, which the positive base can absorb, raises no Art. 50.3 finding."""
    stock = Decimal("3000.00")
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_PROFILE_ID):
        _seed_profile()
        _seed_prior_negative_base(stock)
        revision = _calculate(work_income=Decimal("40000.00"), applied=stock, binding_overrides={})
        findings = _art_50_3_findings(revision)

    assert _statutory_maximum(revision, stock) == stock
    assert revision.casilla_values[_COMPENSATION] == stock
    assert findings == {}


def test_a_positive_application_against_a_proven_zero_stock_is_refused(tmp_path: Path) -> None:
    """A stated zero stock leaves nothing to compensate, so 5,000 applied fails both gates."""
    applied = Decimal("5000.00")
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_PROFILE_ID):
        _seed_profile()
        revision = _calculate(
            work_income=Decimal("40000.00"),
            applied=applied,
            binding_overrides={_PRIOR_NEGATIVE_BASE_BINDING: Decimal("0")},
        )
        findings = _art_50_3_findings(revision)

    assert revision.casilla_values[_PENDING_STOCK] == Decimal("0")
    assert revision.casilla_values[_COMPENSATION] == applied
    assert set(findings) == {_STOCK_PREDICATE_ID, _MAXIMUM_PREDICATE_ID}
    _assert_not_at_maximum(findings[_MAXIMUM_PREDICATE_ID], applied=applied, maximum=Decimal("0"))


def test_a_proven_zero_stock_with_nothing_applied_passes(tmp_path: Path) -> None:
    """With no pending negative base and nothing applied, the maximum is zero and is met."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_PROFILE_ID):
        _seed_profile()
        revision = _calculate(
            work_income=Decimal("40000.00"),
            applied=Decimal("0"),
            binding_overrides={_PRIOR_NEGATIVE_BASE_BINDING: Decimal("0")},
        )
        findings = _art_50_3_findings(revision)

    assert findings == {}


def test_a_positive_application_with_no_positive_base_is_refused(tmp_path: Path) -> None:
    """Art. 50.3 compensates only against a positive base, so a zero base admits nothing."""
    stock = Decimal("3000.00")
    applied = Decimal("2000.00")
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_PROFILE_ID):
        _seed_profile()
        _seed_prior_negative_base(stock)
        revision = _calculate(work_income=Decimal("0"), applied=applied, binding_overrides={})
        findings = _art_50_3_findings(revision)

    assert revision.casilla_values[_BASE_IMPONIBLE_GENERAL] <= Decimal("0")
    assert _statutory_maximum(revision, stock) == Decimal("0")
    assert set(findings) == {_MAXIMUM_PREDICATE_ID}
    _assert_not_at_maximum(findings[_MAXIMUM_PREDICATE_ID], applied=applied, maximum=Decimal("0"))


@pytest.mark.parametrize("applied", (Decimal("0"), Decimal("5000.00")), ids=("nothing-applied", "positive-applied"))
def test_an_unknown_stock_stops_the_calculation_before_any_gate(tmp_path: Path, applied: Decimal) -> None:
    """With no prior return and no stated stock, 1388 is unknown and is never read as zero."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_PROFILE_ID):
        _seed_profile()
        with pytest.raises(ModeloWorkMissingInputError) as refused:
            _calculate(work_income=Decimal("40000.00"), applied=applied, binding_overrides={})

    assert refused.value.binding_id == _PRIOR_NEGATIVE_BASE_BINDING

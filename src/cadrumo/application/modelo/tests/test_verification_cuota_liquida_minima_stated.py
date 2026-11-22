"""A Modelo 200 under the tributacion minima is blocked until it states [00619], in every supported year.

LIS art. 30 bis.1 applies the cuota liquida minima to a contribuyente whose net
turnover of the twelve months before the period is at least 20 millones de
euros, and to one taxed under the consolidacion fiscal regime. The minimum is
the filer's to work out and may be zero, so verification blocks on the edition's
[00619] with the door that states it; a typed 0 is a statement, a missing box is
not. A contribuyente below the threshold outside a group, or excluded as a Ley
49/2002 entity, is asked nothing. An undeclared turnover cannot decide the rule,
so verification asks for the profile fact instead.
"""

from __future__ import annotations

import json
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from ....core.authority_grade import RegistryAuthorityGrade
from ....core.casilla_id import CasillaId, validated_casilla_id
from ....core.period import Period
from ....domain.calculations.registry.formula_runtime import RegistryCalculationResult, calculate_registry_snapshot
from ....domain.calculations.registry.formula_runtime_ops import RegistryUnresolvedOutcomeReason
from ....domain.calculations.registry.schema import RegistrySnapshot
from ....domain.calculations.registry.schema_references import RegistrySnapshotRef
from ....domain.calculations.registry.tests.authored_editions import filing_year_envelope
from ....domain.calculations.registry.tests.modelo_200_turnover import (
    PRIOR_TWELVE_MONTHS_TURNOVER,
    turnover_binding_values,
)
from ....domain.calculations.registry.tests.published_authority import published_snapshot
from ....domain.contribuyente.entity_type import EntityType, LegalEntityForm
from ....domain.deadlines.models import IVARegime, TaxpayerProfile
from ....domain.modelos.calculation_revision import (
    CalculationRevision,
    CalculationRevisionState,
    derive_calculation_revision_id,
)
from ....domain.modelos.codes import ModeloCode
from ....domain.modelos.verification_report import ModeloVerificationFinding, ModeloVerificationFindingSeverity
from ....domain.modelos.work_unit import WorkUnit, derive_work_unit_id
from ..preconditions import ModeloPreconditionFailure
from ..projection_words import casilla_reason_locale_key
from ..verification_operator_stated_outcomes import STATED_BOX_ACTION_ID
from ..verification_revision_findings import append_registry_predicate_findings, append_unresolved_outcome_findings

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("authority_operation")]

_BUCKET_ID = "61961961-9619-4619-8619-619619619619"
_EXERCISES = tuple(filing_year_envelope().years)
_MINIMUM_CHAIN = "is-liquidacion-iv-cuota-liquida-minima"
_REASON = RegistryUnresolvedOutcomeReason.M200_CUOTA_LIQUIDA_MINIMA_UNSTATED
_TURNOVER_PREDICATE = "modelo-200-incn-doce-meses-anteriores-declarado"
_BASE_CASILLA = validated_casilla_id("DP200012:00501", surface="test resultado")
_DOMINANTE = validated_casilla_id("DP200001:00009", surface="test entidad dominante")
#: "al menos de 20 millones de euros" (Manual practico de Sociedades, "Cuota liquida minima").
_AT_THRESHOLD = Decimal("20000000")
_BELOW_THRESHOLD = Decimal("19999999.99")


def _snapshot(exercise: int) -> RegistrySnapshot:
    return published_snapshot("200", filing_year=exercise, period="0A", grade=RegistryAuthorityGrade.CALCULATION)


def _in_edition(snapshot: RegistrySnapshot, raw: str) -> CasillaId:
    number = raw.rsplit(":", 1)[-1]
    matches = [c.id for c in snapshot.revision.casillas if c.number == number and c.id.rsplit(":", 1)[-1] == number]
    return matches[0] if len(matches) == 1 else validated_casilla_id(raw, surface="test casilla")


def _minimum_box(snapshot: RegistrySnapshot) -> CasillaId:
    (box,) = (c.id for c in snapshot.revision.casillas if c.continuidad_id == _MINIMUM_CHAIN)
    return box


def _sociedad(*, turnover: Decimal | None, legal_form: str = "sl") -> TaxpayerProfile:
    return TaxpayerProfile(
        tax_id="B00015016",
        entity_type=EntityType.from_registry("legal_entity"),
        legal_entity_form=LegalEntityForm.from_registry(legal_form),
        iva_regime=IVARegime("GENERAL"),
        has_employees=False,
        pays_rent_with_retencion=False,
        does_intracomunitario=False,
        bienes_extranjero_above_threshold=False,
        incn_prior_12_months=turnover,
    )


def _calculate(
    exercise: int,
    snapshot: RegistrySnapshot,
    profile: TaxpayerProfile,
    inputs: dict[CasillaId, Decimal],
) -> RegistryCalculationResult:
    base_inputs = {
        _in_edition(snapshot, raw): Decimal("0")
        for raw in (
            "DP200013:00417",
            "DP200013:00418",
            "01032",
            "DP200014:01033",
            "DP200014:01034",
            "DP200014B:01766",
            "DP200014B:01784",
        )
    }
    turnover = profile.incn_prior_12_months
    turnover_values = turnover_binding_values(snapshot, Decimal("0") if turnover is None else turnover)
    unresolved: tuple[str, ...] = ()
    if turnover is None:
        turnover_values.pop(PRIOR_TWELVE_MONTHS_TURNOVER)
        unresolved = (PRIOR_TWELVE_MONTHS_TURNOVER,)
    assert profile.legal_entity_form is not None
    return calculate_registry_snapshot(
        snapshot,
        inputs={_BASE_CASILLA: Decimal("2000000"), **base_inputs, **inputs},
        enum_binding_values={"modelo-200-profile-legal-entity-form": str(profile.legal_entity_form)},
        binding_values={
            "modelo-200-profile-new-entity-flag": Decimal("0"),
            **turnover_values,
            "modelo-200-profile-tributacion-estado-porcentaje": Decimal("100"),
            "modelo-200-bin-pendiente-ejercicios-anteriores": Decimal("0"),
            "modelo-200-dotaciones-deterioro-creditos-saldo-no-cumplido-anteriores": Decimal("0"),
            "modelo-200-dotaciones-deterioro-creditos-saldo-cumplido-anteriores": Decimal("0"),
        },
        unresolved_binding_ids=unresolved,
        relation_values={
            f"modelo-200-pago-fraccionado-{ordinal}-{modalidad}": Decimal("0")
            for ordinal in ("primero", "segundo", "tercero")
            for modalidad in ("40-2", "40-3")
        },
        date_context={"filing_period": date(exercise, 12, 31)},
    )


def _work_unit(exercise: int) -> WorkUnit:
    period = Period.from_year_and_code(exercise, "0A")
    created_at = datetime(exercise + 1, 7, 2, tzinfo=UTC)
    return WorkUnit(
        work_unit_id=derive_work_unit_id(
            bucket_id=_BUCKET_ID, modelo=ModeloCode("200"), filing_year=exercise, period=period, revision_id="minimum"
        ),
        bucket_id=_BUCKET_ID,
        modelo=ModeloCode("200"),
        filing_year=exercise,
        period=period,
        revision_id="minimum",
        name="minimum-200",
        created_at=created_at,
        updated_at=created_at,
    )


def _revision(
    exercise: int, work_unit: WorkUnit, result: RegistryCalculationResult, typed: dict[CasillaId, str]
) -> CalculationRevision:
    created_at = datetime(exercise + 1, 7, 3, tzinfo=UTC)
    return CalculationRevision(
        calculation_revision_id=derive_calculation_revision_id(
            work_unit_id=work_unit.work_unit_id,
            input_values_by_casilla_id=typed,
            binding_overrides={},
            casilla_values=dict(result.values),
            filing_instance_evidence=None,
            source_provenance=(),
        ),
        work_unit_id=work_unit.work_unit_id,
        registry_snapshot_ref=RegistrySnapshotRef(
            modelo=work_unit.modelo,
            revision_id=work_unit.revision_id,
            modelo_year=exercise,
            period=work_unit.period.registry_token,
        ),
        state=CalculationRevisionState.BORRADOR,
        input_values_by_casilla_id=typed,
        casilla_values=dict(result.values),
        observations=tuple(result.observations),
        unresolved_outcomes=result.unresolved_outcomes,
        created_at=created_at,
        updated_at=created_at,
        filing_instance_evidence=None,
        source_provenance=(),
    )


def _verify(
    exercise: int,
    profile: TaxpayerProfile,
    *,
    marked: tuple[str, ...] = (),
    stated_minimum: str | None = None,
) -> tuple[list[ModeloVerificationFinding], dict[int, ModeloPreconditionFailure]]:
    """Calculate and verify one declaration; ``stated_minimum`` is the raw text typed into [00619]."""
    snapshot = _snapshot(exercise)
    work_unit = _work_unit(exercise)
    inputs = {_in_edition(snapshot, raw): Decimal("1") for raw in marked}
    typed = {casilla_id: str(value) for casilla_id, value in inputs.items()}
    if stated_minimum is not None:
        inputs[_minimum_box(snapshot)] = Decimal(stated_minimum)
        typed[_minimum_box(snapshot)] = stated_minimum
    result = _calculate(exercise, snapshot, profile, inputs)
    revision = _revision(exercise, work_unit, result, typed)
    findings: list[ModeloVerificationFinding] = []
    failures: dict[int, ModeloPreconditionFailure] = {}
    for append in (append_registry_predicate_findings, append_unresolved_outcome_findings):
        append(
            work_unit=work_unit,
            target=revision,
            snapshot=snapshot,
            predicate_profile=profile,
            findings=findings,
            failures_by_finding_id=failures,
        )
    return findings, failures


def _minimum_findings(findings: list[ModeloVerificationFinding]) -> list[ModeloVerificationFinding]:
    key = casilla_reason_locale_key(_REASON.value)
    return [f for f in findings if f.message_locale_key == key]


def _turnover_findings(findings: list[ModeloVerificationFinding]) -> list[ModeloVerificationFinding]:
    return [f for f in findings if f.message_facts.get("predicate_id") == _TURNOVER_PREDICATE]


def _blocking(findings: list[ModeloVerificationFinding]) -> list[ModeloVerificationFinding]:
    return [f for f in findings if f.severity is ModeloVerificationFindingSeverity.BLOCKING]


@pytest.mark.parametrize("exercise", _EXERCISES)
def test_an_unstated_minimum_at_the_threshold_blocks_with_the_door_that_states_it(exercise: int) -> None:
    box = _minimum_box(_snapshot(exercise))

    findings, failures = _verify(exercise, _sociedad(turnover=_AT_THRESHOLD))

    blocking = _blocking(findings)
    assert [f.casilla_id for f in blocking] == [box]
    (finding,) = _minimum_findings(blocking)
    assert finding.message_facts["reason"] == _REASON.value
    verdict = json.loads(failures[id(finding)].verdict.model_dump_json())
    assert verdict["action"]["action_id"] == STATED_BOX_ACTION_ID
    bound = {item["argument_name"]: item for item in verdict["argument_bindings"]}
    assert bound["casilla_id"]["value"] == box
    assert bound["value"]["status"] == "missing"


@pytest.mark.parametrize("stated", ["0", "300000"], ids=["stated-zero", "stated-amount"])
@pytest.mark.parametrize("exercise", _EXERCISES)
def test_stating_the_minimum_admits_the_declaration_even_as_zero(exercise: int, stated: str) -> None:
    findings, _failures = _verify(exercise, _sociedad(turnover=_AT_THRESHOLD), stated_minimum=stated)

    assert _blocking(findings) == []


@pytest.mark.parametrize("exercise", _EXERCISES)
def test_below_the_threshold_outside_a_group_nothing_is_asked(exercise: int) -> None:
    findings, _failures = _verify(exercise, _sociedad(turnover=_BELOW_THRESHOLD))

    assert _blocking(findings) == []


@pytest.mark.parametrize("exercise", _EXERCISES)
def test_a_group_entity_below_the_threshold_is_asked(exercise: int) -> None:
    findings, _failures = _verify(exercise, _sociedad(turnover=_BELOW_THRESHOLD), marked=(str(_DOMINANTE),))

    assert [f.casilla_id for f in _minimum_findings(_blocking(findings))] == [_minimum_box(_snapshot(exercise))]


@pytest.mark.parametrize("exercise", _EXERCISES)
def test_a_ley_49_2002_entity_at_the_threshold_is_not_asked(exercise: int) -> None:
    findings, _failures = _verify(exercise, _sociedad(turnover=_AT_THRESHOLD, legal_form="sin_fines_lucrativos"))

    assert _minimum_findings(findings) == []


@pytest.mark.parametrize("exercise", _EXERCISES)
def test_an_undeclared_turnover_blocks_until_the_profile_states_it(exercise: int) -> None:
    findings, _failures = _verify(exercise, _sociedad(turnover=None))

    (finding,) = _turnover_findings(_blocking(findings))
    assert _minimum_findings(findings) == []
    assert "ley-27-2014:art-30-bis" in finding.legal_refs


@pytest.mark.parametrize("exercise", _EXERCISES)
def test_a_declared_turnover_satisfies_the_turnover_gate(exercise: int) -> None:
    findings, _failures = _verify(exercise, _sociedad(turnover=_BELOW_THRESHOLD))

    assert _turnover_findings(findings) == []

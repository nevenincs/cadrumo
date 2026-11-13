"""A Modelo 200 entity that marks its extinción is blocked until it states the compensation, in every supported year.

The BIN compensation ceiling of such an entity has no value, because the
registry does not tell an extinción from a restructuring. Verification blocks
with the door that states casilla 00547; stating it admits the declaration, and
an entity that does not mark the extinción is checked as before.
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
from ....domain.calculations.registry.tests.modelo_200_turnover import turnover_binding_values
from ....domain.calculations.registry.tests.published_authority import published_snapshot
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
from .verification_substance_fixtures import workflow_profile

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("authority_operation")]

_BUCKET_ID = "36363636-3636-4636-8636-363636363636"
_EXERCISES = tuple(filing_year_envelope().years)
_EXTINCION = validated_casilla_id("00072", surface="test extinción")
_BASE_CASILLA = validated_casilla_id("DP200012:00501", surface="test resultado")
_STOCK_BINDING = "modelo-200-bin-pendiente-ejercicios-anteriores"
_STATED = Decimal("4000000")  # above the 70 per cent limit, which an extinction does not apply


def _snapshot(exercise: int) -> RegistrySnapshot:
    return published_snapshot("200", filing_year=exercise, period="0A", grade=RegistryAuthorityGrade.CALCULATION)


def _in_edition(snapshot: RegistrySnapshot, raw: str) -> CasillaId:
    number = raw.rsplit(":", 1)[-1]
    matches = [c.id for c in snapshot.revision.casillas if c.number == number and c.id.rsplit(":", 1)[-1] == number]
    return matches[0] if len(matches) == 1 else validated_casilla_id(raw, surface="test casilla")


def _compensation_box(snapshot: RegistrySnapshot) -> CasillaId:
    """The box the ceiling formula names for the operator to state, read from the registry itself."""
    formula = next(f for f in snapshot.revision.formulas if f.id == "modelo-200-bin-aplicada-maxima")
    stack = [formula.expression]
    while stack:
        node = stack.pop()
        if node.op == "unresolved_outcome" and len(node.args) == 2:
            assert node.args[1].casilla_id is not None
            return node.args[1].casilla_id
        stack.extend(node.args)
    raise AssertionError("the ceiling formula names no box for the operator to state")


def _calculate(
    exercise: int, snapshot: RegistrySnapshot, inputs: dict[CasillaId, Decimal]
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
    return calculate_registry_snapshot(
        snapshot,
        inputs={_BASE_CASILLA: Decimal("5000000"), **base_inputs, **inputs},
        enum_binding_values={"modelo-200-profile-legal-entity-form": "sl"},
        binding_values={
            "modelo-200-profile-new-entity-flag": Decimal("0"),
            **turnover_binding_values(snapshot, Decimal("10000000")),
            "modelo-200-profile-tributacion-estado-porcentaje": Decimal("100"),
            _STOCK_BINDING: Decimal("10000000"),
            "modelo-200-dotaciones-deterioro-creditos-saldo-no-cumplido-anteriores": Decimal("0"),
            "modelo-200-dotaciones-deterioro-creditos-saldo-cumplido-anteriores": Decimal("0"),
        },
        relation_values={
            f"modelo-200-pago-fraccionado-{ordinal}-{modalidad}": Decimal("0")
            for ordinal in ("primero", "segundo", "tercero")
            for modalidad in ("40-2", "40-3")
        },
        date_context={"filing_period": date(exercise, 12, 31)},
    )


def _work_unit(exercise: int) -> WorkUnit:
    period = Period.from_year_and_code(exercise, "0A")
    created_at = datetime(exercise, 7, 2, tzinfo=UTC)
    return WorkUnit(
        work_unit_id=derive_work_unit_id(
            bucket_id=_BUCKET_ID, modelo=ModeloCode("200"), filing_year=exercise, period=period, revision_id="stated"
        ),
        bucket_id=_BUCKET_ID,
        modelo=ModeloCode("200"),
        filing_year=exercise,
        period=period,
        revision_id="stated",
        name="stated-200",
        created_at=created_at,
        updated_at=created_at,
    )


def _revision(
    exercise: int, work_unit: WorkUnit, result: RegistryCalculationResult, inputs: dict[CasillaId, Decimal]
) -> CalculationRevision:
    typed = {casilla_id: str(value) for casilla_id, value in inputs.items()}
    created_at = datetime(exercise, 7, 3, tzinfo=UTC)
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
    exercise: int, inputs: dict[CasillaId, Decimal]
) -> tuple[list[ModeloVerificationFinding], dict[int, ModeloPreconditionFailure]]:
    snapshot = _snapshot(exercise)
    work_unit = _work_unit(exercise)
    result = _calculate(exercise, snapshot, inputs)
    revision = _revision(exercise, work_unit, result, inputs)
    findings: list[ModeloVerificationFinding] = []
    failures: dict[int, ModeloPreconditionFailure] = {}
    for append in (append_registry_predicate_findings, append_unresolved_outcome_findings):
        append(
            work_unit=work_unit,
            target=revision,
            snapshot=snapshot,
            predicate_profile=workflow_profile(),
            findings=findings,
            failures_by_finding_id=failures,
        )
    return findings, failures


def _blocking(findings: list[ModeloVerificationFinding]) -> list[ModeloVerificationFinding]:
    return [f for f in findings if f.severity is ModeloVerificationFindingSeverity.BLOCKING]


@pytest.mark.parametrize("exercise", _EXERCISES)
def test_an_extinction_without_the_compensation_stated_is_blocked_with_the_door_that_states_it(exercise: int) -> None:
    snapshot = _snapshot(exercise)
    box = _compensation_box(snapshot)

    findings, failures = _verify(exercise, {_in_edition(snapshot, "00072"): Decimal("1")})

    blocking = _blocking(findings)
    assert [f.casilla_id for f in blocking] == [box]
    assert blocking[0].message_locale_key == casilla_reason_locale_key(
        RegistryUnresolvedOutcomeReason.M200_EXTINCION_ENTIDAD_UNSUPPORTED.value
    )
    verdict = json.loads(failures[id(blocking[0])].verdict.model_dump_json())
    assert verdict["action"]["action_id"] == STATED_BOX_ACTION_ID
    bound = {item["argument_name"]: item for item in verdict["argument_bindings"]}
    assert bound["casilla_id"]["value"] == box
    assert bound["value"]["status"] == "missing"


@pytest.mark.parametrize("exercise", _EXERCISES)
def test_stating_the_compensation_admits_the_extinction(exercise: int) -> None:
    snapshot = _snapshot(exercise)

    findings, _failures = _verify(
        exercise, {_in_edition(snapshot, "00072"): Decimal("1"), _compensation_box(snapshot): _STATED}
    )

    assert _blocking(findings) == []


@pytest.mark.parametrize("exercise", _EXERCISES)
def test_an_entity_that_does_not_mark_the_extinction_is_checked_as_before(exercise: int) -> None:
    snapshot = _snapshot(exercise)
    box = _compensation_box(snapshot)

    within, _ = _verify(exercise, {box: Decimal("3000000")})
    beyond, _ = _verify(exercise, {box: Decimal("4000000")})

    assert _blocking(within) == []
    over_the_ceiling = _blocking(beyond)
    assert over_the_ceiling
    stated_key = casilla_reason_locale_key(RegistryUnresolvedOutcomeReason.M200_EXTINCION_ENTIDAD_UNSUPPORTED.value)
    assert all(f.message_locale_key != stated_key for f in over_the_ceiling)

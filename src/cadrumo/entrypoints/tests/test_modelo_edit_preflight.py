"""Edit preflight names the address of every finding before anything is submitted.

Driven over real encrypted storage against a real admitted baseline and
calculation head, so each finding is judged against what the executor will
see. All values are synthetic.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ...application.modelo.calculation_actions import (
    calculate_modelo_revision_from_bucket_aggregation_with_diagnostics,
)
from ...application.modelo.edit_contract import ModeloEditMutationFamily
from ...application.modelo.edit_models import (
    ModeloEditBaselineV1,
    ModeloEditFindingSeverity,
    ModeloEditFindingV1,
    ModeloEditPreflightEvaluatedV1,
    ModeloEditPreflightResultV1,
    ModeloEditRefusedV1,
    ModeloEditScalarAddressV1,
    ModeloEditScalarIntentKind,
    ModeloEditStaleBaselineRefusalV1,
    ModeloEditSubmissionV1,
    ModeloEditWritableScalarSurfaceEntryV1,
    ModeloScalarEditIntentV1,
)
from ...application.modelo.edit_preflight import (
    CLEAR_OF_SOURCE_FED_CASILLA,
    NOTHING_TO_RESTORE,
    OPERATOR_LAYER_UNKNOWN,
    OVERRIDES_SOURCE_VALUE,
    REQUIRED_EMPTY,
    preflight_modelo_edit,
)
from ...core.casilla_id import CasillaId, validated_casilla_id
from ...domain.calculations.registry.tax_id_format import runtime_tax_id_format
from ...domain.filing.schema import ModeloScalar
from .modelo_operator_work_storage import SEEDED_AT, SeededOperatorWork, seeded_operator_work

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_C06 = validated_casilla_id("06")
_C08 = validated_casilla_id("08")


def _intent(
    casilla_id: CasillaId, kind: ModeloEditScalarIntentKind, value: ModeloScalar = None
) -> ModeloScalarEditIntentV1:
    return ModeloScalarEditIntentV1(address=ModeloEditScalarAddressV1(casilla_id=casilla_id), kind=kind, value=value)


def _preflight(
    work: SeededOperatorWork,
    *intents: ModeloScalarEditIntentV1,
    baseline: ModeloEditBaselineV1 | None = None,
) -> ModeloEditPreflightResultV1:
    return preflight_modelo_edit(
        ModeloEditSubmissionV1(
            baseline=baseline if baseline is not None else work.baseline(),
            mutation_family=ModeloEditMutationFamily.CALCULATE,
            scalar_intents=intents,
        ),
        work_catalogue=work.ports.work_unit_repository.load(),
        calculation_catalogue=work.ports.calculation_repository.load(),
        tax_id_format=runtime_tax_id_format(authority=work.operation),
    )


def _findings(result: ModeloEditPreflightResultV1) -> dict[tuple[str, str | None], ModeloEditFindingV1]:
    assert isinstance(result, ModeloEditPreflightEvaluatedV1), result
    return {
        (
            finding.code,
            finding.address.casilla_id if isinstance(finding.address, ModeloEditScalarAddressV1) else None,
        ): finding
        for finding in result.findings
    }


def test_each_finding_names_its_address_and_severity(tmp_path: Path) -> None:
    with seeded_operator_work(tmp_path) as work:
        head = calculate_modelo_revision_from_bucket_aggregation_with_diagnostics(
            work.work_unit_id, ports=work.ports, record_operator_layer=True, clock=SEEDED_AT
        ).revision
        assert _C06 in head.input_values_by_casilla_id, "casilla 06 of Modelo 130 is fed by a source"
        findings = _findings(
            _preflight(
                work,
                _intent(_C06, ModeloEditScalarIntentKind.SET_TYPED_VALUE, "100"),
                _intent(_C08, ModeloEditScalarIntentKind.SET_TYPED_VALUE, "12.345"),
            )
        )
        clear = _findings(_preflight(work, _intent(_C06, ModeloEditScalarIntentKind.CLEAR_DECLARED_VALUE)))
        restore = _findings(_preflight(work, _intent(_C08, ModeloEditScalarIntentKind.RESTORE_SOURCE_VALUE)))

    assert findings[OVERRIDES_SOURCE_VALUE, _C06].severity is ModeloEditFindingSeverity.WARNING
    refused = findings["value.too_many_decimals", _C08]
    assert refused.severity is ModeloEditFindingSeverity.ERROR
    assert refused.message_arguments == ("2",)
    assert clear[CLEAR_OF_SOURCE_FED_CASILLA, _C06].severity is ModeloEditFindingSeverity.ERROR
    assert restore[NOTHING_TO_RESTORE, _C08].severity is ModeloEditFindingSeverity.INFO
    assert all("12.345" not in str(finding.message_arguments) for finding in findings.values())


def test_a_head_stored_before_operator_layers_is_flagged_once(tmp_path: Path) -> None:
    with seeded_operator_work(tmp_path) as work:
        calculate_modelo_revision_from_bucket_aggregation_with_diagnostics(
            work.work_unit_id, ports=work.ports, clock=SEEDED_AT
        )
        findings = _findings(_preflight(work, _intent(_C08, ModeloEditScalarIntentKind.SET_TYPED_VALUE, "5")))

    assert findings[OPERATOR_LAYER_UNKNOWN, None].severity is ModeloEditFindingSeverity.WARNING


def test_a_required_casilla_left_empty_is_named(tmp_path: Path) -> None:
    """Marks one writable casilla required in an isolated copy of a real baseline, then clears it."""
    with seeded_operator_work(tmp_path) as work:
        baseline = work.baseline()
        required = baseline.model_copy(
            update={
                "permitted_surface": tuple(
                    entry.model_copy(update={"grammar": entry.grammar.model_copy(update={"required": True})})
                    if isinstance(entry, ModeloEditWritableScalarSurfaceEntryV1) and entry.casilla_id == _C08
                    else entry
                    for entry in baseline.permitted_surface
                )
            }
        )
        cleared = _findings(
            _preflight(work, _intent(_C08, ModeloEditScalarIntentKind.CLEAR_DECLARED_VALUE), baseline=required)
        )
        set_value = _findings(
            _preflight(work, _intent(_C08, ModeloEditScalarIntentKind.SET_TYPED_VALUE, "1"), baseline=required)
        )

    assert cleared[REQUIRED_EMPTY, _C08].severity is ModeloEditFindingSeverity.WARNING
    assert (REQUIRED_EMPTY, _C08) not in set_value


def test_a_stale_baseline_is_refused_instead_of_evaluated(tmp_path: Path) -> None:
    with seeded_operator_work(tmp_path) as work:
        baseline = work.baseline()
        calculate_modelo_revision_from_bucket_aggregation_with_diagnostics(
            work.work_unit_id, ports=work.ports, record_operator_layer=True, clock=SEEDED_AT
        )
        result = _preflight(work, _intent(_C08, ModeloEditScalarIntentKind.SET_TYPED_VALUE, "5"), baseline=baseline)

    assert isinstance(result, ModeloEditRefusedV1)
    assert isinstance(result.refusal, ModeloEditStaleBaselineRefusalV1)

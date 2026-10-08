"""An edit baseline is scoped to its own declaration and renews silently while nothing changed.

Driven over real encrypted storage. The baseline's concurrency coordinates are
the edited work unit's record and its calculation head, so a recalculation of
another declaration in the same profile cannot stale it, while a change to the
edited declaration always does. An expired baseline renews without the
operator noticing when only its lifetime moved.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from ...application.calculations.tests.filing_evidence import general_m303_filing_evidence
from ...application.modelo.action_errors import ModeloEditBaselineStaleError
from ...application.modelo.calculation_actions import (
    calculate_modelo_revision_from_bucket_aggregation_with_diagnostics,
)
from ...application.modelo.calculation_source_policy import (
    BUCKET_AGGREGATION_LOCK_SOURCES,
    CALLER_OVERRIDABLE_CARRY_SOURCES,
)
from ...application.modelo.edit_admission import ModeloEditRenewedV1
from ...application.modelo.edit_models import (
    ModeloEditAdmittedV1,
    ModeloEditNonWritableBindingOverrideSurfaceEntryV1,
    ModeloEditNonWritableReason,
    ModeloEditNonWritableScalarSurfaceEntryV1,
    ModeloEditRefusedV1,
    ModeloEditScalarAddressV1,
    ModeloEditScalarIntentKind,
    ModeloEditStaleBaselineRefusalV1,
    ModeloEditWritableBindingOverrideSurfaceEntryV1,
    ModeloEditWritableScalarSurfaceEntryV1,
    ModeloScalarEditIntentV1,
)
from ...core.aggregation import BindingSourceKind
from ...core.casilla_id import validated_casilla_id
from ...domain.calculations.registry.casilla_membership import row_field_template_records_by_casilla
from ...domain.calculations.registry.schema_base import CasillaDataType
from ...domain.calculations.registry.schema_input_kind import InputKind
from .modelo_operator_work_storage import SEEDED_AT, seeded_operator_work

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_SET_06 = ModeloScalarEditIntentV1(
    address=ModeloEditScalarAddressV1(casilla_id=validated_casilla_id("06")),
    kind=ModeloEditScalarIntentKind.SET_TYPED_VALUE,
    value="100",
)


def test_an_apply_after_the_lifetime_succeeds_once_renewed_when_nothing_changed(tmp_path: Path) -> None:
    with seeded_operator_work(tmp_path) as work:
        admission = work.admit(issued_at=datetime.now(UTC) - timedelta(minutes=10))
        assert isinstance(admission, ModeloEditAdmittedV1)
        expired = admission.baseline

        refused = work.apply(scalar=(_SET_06,), baseline=expired)
        renewal = work.renew(expired)
        assert isinstance(renewal, ModeloEditRenewedV1)
        applied = work.apply(scalar=(_SET_06,), baseline=renewal.baseline)

    assert isinstance(refused.refusal, ModeloEditBaselineStaleError)
    assert renewal.baseline.permitted_surface_digest == expired.permitted_surface_digest
    assert renewal.baseline.expires_at > datetime.now(UTC)
    assert applied.refusal is None


def test_recalculating_another_declaration_does_not_stale_this_baseline(tmp_path: Path) -> None:
    with seeded_operator_work(tmp_path) as work:
        other = work.sibling("2T")
        baseline = work.baseline()
        calculate_modelo_revision_from_bucket_aggregation_with_diagnostics(
            other.work_unit_id,
            ports=other.ports,
            # The second quarter's carries, answered as the operator would with
            # no first-quarter payment on file in this fresh synthetic profile.
            binding_values={
                "modelo-130-pagos-fraccionados-anteriores": Decimal("0"),
                "modelo-130-resultados-negativos-anteriores": Decimal("0"),
            },
            record_operator_layer=True,
            clock=SEEDED_AT,
        )

        renewal = work.renew(baseline)
        applied = work.apply(scalar=(_SET_06,), baseline=baseline)

    assert isinstance(renewal, ModeloEditRenewedV1)
    assert applied.refusal is None


def test_a_change_to_the_edited_declaration_stales_the_baseline_and_is_not_renewed(tmp_path: Path) -> None:
    with seeded_operator_work(tmp_path) as work:
        baseline = work.baseline()
        calculate_modelo_revision_from_bucket_aggregation_with_diagnostics(
            work.work_unit_id, ports=work.ports, record_operator_layer=True, clock=SEEDED_AT
        )

        renewal = work.renew(baseline)
        applied = work.apply(scalar=(_SET_06,), baseline=baseline)

    assert isinstance(renewal, ModeloEditRefusedV1)
    assert isinstance(renewal.refusal, ModeloEditStaleBaselineRefusalV1)
    assert "calculation_head_digest" in renewal.refusal.mismatching_coordinates
    assert isinstance(applied.refusal, ModeloEditBaselineStaleError)


@pytest.mark.parametrize(("modelo", "year", "period"), [("130", 2026, "1T"), ("303", 2026, "1T")])
def test_the_surface_classifies_every_address_by_what_can_reach_the_engine(
    tmp_path: Path, modelo: str, year: int, period: str
) -> None:
    with seeded_operator_work(tmp_path, modelo=modelo, filing_year=year, period_code=period) as work:
        if modelo == "303":
            calculate_modelo_revision_from_bucket_aggregation_with_diagnostics(
                work.work_unit_id,
                ports=work.ports,
                filing_instance_evidence=general_m303_filing_evidence(
                    work.work_unit.period, reference="test:admission-scope", operation=work.operation
                ),
                record_operator_layer=True,
                clock=SEEDED_AT,
            )
        baseline = work.baseline()
        revision = work.operation.revision_for_context(
            modelo, filing_year=year, period=work.work_unit.period.registry_token
        )

    row_fields = frozenset(row_field_template_records_by_casilla(revision))
    casillas = {casilla.id: casilla for casilla in revision.casillas}
    bindings = {binding.id: binding for binding in revision.bindings}
    for entry in baseline.permitted_surface:
        if isinstance(entry, ModeloEditWritableScalarSurfaceEntryV1):
            casilla = casillas[entry.casilla_id]
            assert casilla.input_kind is InputKind.MANUAL
            assert entry.casilla_id not in row_fields
            assert casilla.data_type not in {CasillaDataType.DATE, CasillaDataType.YEAR}
        elif isinstance(entry, ModeloEditNonWritableScalarSurfaceEntryV1):
            casilla = casillas[entry.casilla_id]
            if casilla.input_kind is InputKind.MANUAL:
                assert entry.reason in {
                    ModeloEditNonWritableReason.ROW_FIELD_TEMPLATE,
                    ModeloEditNonWritableReason.VALUE_CHANNEL_UNAVAILABLE,
                }
        elif isinstance(entry, ModeloEditWritableBindingOverrideSurfaceEntryV1):
            source = bindings[entry.binding_id].source
            assert source is BindingSourceKind.MANUAL_INPUT or source in CALLER_OVERRIDABLE_CARRY_SOURCES
        elif isinstance(entry, ModeloEditNonWritableBindingOverrideSurfaceEntryV1):
            source = bindings[entry.binding_id].source
            if source in BUCKET_AGGREGATION_LOCK_SOURCES:
                assert entry.reason is ModeloEditNonWritableReason.SOURCE_LOCKED
            elif source is not BindingSourceKind.MANUAL_INPUT and source not in CALLER_OVERRIDABLE_CARRY_SOURCES:
                assert entry.reason is ModeloEditNonWritableReason.OVERRIDE_POLICY_UNDECIDED
            else:
                assert entry.reason is ModeloEditNonWritableReason.VALUE_CHANNEL_UNAVAILABLE


def test_a_carry_binding_override_is_admitted_set_and_removed(tmp_path: Path) -> None:
    """Modelo 130's prior-payments carry takes an operator override the editor can later withdraw."""
    from ...application.modelo.edit_models import (
        ModeloBindingEditIntentV1,
        ModeloEditBindingAddressV1,
        ModeloEditBindingIntentKind,
    )
    from ...domain.modelos.calculation_revision_operator_layer import CalculationOperatorLayer

    with seeded_operator_work(tmp_path) as work:
        carry = next(
            entry.binding_id
            for entry in work.baseline().permitted_surface
            if isinstance(entry, ModeloEditWritableBindingOverrideSurfaceEntryV1) and entry.grammar.money_operand_bound
        )
        address = ModeloEditBindingAddressV1(binding_id=carry)
        set_applied = work.apply(
            binding=(
                ModeloBindingEditIntentV1(
                    address=address, kind=ModeloEditBindingIntentKind.SET_OVERRIDE_VALUE, value="12.50"
                ),
            )
        )
        overridden = work.require_head()
        removed = work.apply(
            binding=(ModeloBindingEditIntentV1(address=address, kind=ModeloEditBindingIntentKind.REMOVE_OVERRIDE),)
        )
        restored = work.require_head()

    assert set_applied.refusal is None
    assert overridden.operator_layer == CalculationOperatorLayer(binding_overrides={carry: "12.5"})
    assert removed.refusal is None
    assert restored.operator_layer == CalculationOperatorLayer()

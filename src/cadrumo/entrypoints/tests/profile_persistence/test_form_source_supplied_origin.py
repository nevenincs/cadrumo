"""A box the ledger resolver filled is imported, not assumed: the form reads the revision's own source trace.

Modelo 130 box 06 declares no input kind, so it is a box the filer may type, yet the
ledger renta resolver hands it the retención stated on the issued invoices
(RIRPF art. 110.3.a), and the calculation records that resolver as its source. The
form therefore shows the figure as imported from the filer's records and the
assumed-value gate does not hold the declaration back on it. A figure the filer typed
keeps the filer's origin, and a held figure no resolver supplied stays assumed. Real
encrypted store, bucket-aggregation calculation and work-form service over the
published authority; the invoice arithmetic is the one the sibling ledger scenario
works out by hand.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from cadrumo.adapters.persistence.storage.sql.secure_objects import SecureObjectRepository
from cadrumo.application.modelo.calculation_bucket_actions import (
    calculate_modelo_revision_from_bucket_aggregation_with_diagnostics,
)
from cadrumo.application.modelo.source_policy import SourceFamily
from cadrumo.application.modelo.tests.work_form_fixture import built_form
from cadrumo.application.modelo.work_form_assumed import assumed_fields
from cadrumo.application.modelo.work_form_field_vocabulary import ModeloFormCasillaAddressV1, ModeloFormOrigin
from cadrumo.application.modelo.work_form_models import ModeloFormField, ModeloWorkForm
from cadrumo.application.modelo.work_form_next_step import applicable_fields
from cadrumo.core.aggregation import BindingSourceKind
from cadrumo.core.casilla_id import CasillaId
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation, bundled_indexed_authority
from cadrumo.domain.modelos.calculation_revision import CalculationRevision
from cadrumo.domain.modelos.calculation_revision_sources import bound_input_source_refs
from cadrumo.domain.modelos.work_unit import WorkUnit
from cadrumo.entrypoints.adapter_composition_work_ports import build_calculation_action_ports

from .test_e2e_ledger_m130_retenciones import (
    _BUCKET_ID,
    _PRIOR_BINDINGS,
    _QUARTER,
    _RETENCIONES_BOX,
    _STATED_RETENCION,
    _T0,
    _WITHHELD_YEAR,
    _ZERO_MANUAL_INPUTS,
    _form,
    _persist_ledger,
    _seed_taxpayer_profile,
    _work_unit,
    secure_objects,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

__all__ = ["secure_objects"]

_TYPED = Decimal("500.00")


@pytest.fixture
def bucket_id() -> str:
    return _BUCKET_ID


def _calculate(
    work_unit: WorkUnit, operation: PinnedAuthorityOperation, *, typed: dict[CasillaId, Decimal] | None = None
) -> CalculationRevision:
    """Calculate as the operator's executor does: the caller's own entries are recorded, here the two zero boxes."""
    return calculate_modelo_revision_from_bucket_aggregation_with_diagnostics(
        work_unit.work_unit_id,
        ports=build_calculation_action_ports(bucket_id=_BUCKET_ID, operation=operation),
        casilla_inputs={**_ZERO_MANUAL_INPUTS, **(typed or {})},
        binding_values=_PRIOR_BINDINGS,
        record_operator_layer=True,
        clock=_T0,
    ).revision


def _box(form: ModeloWorkForm) -> ModeloFormField:
    (field,) = (
        item
        for item in applicable_fields(form)
        if isinstance(item.address, ModeloFormCasillaAddressV1) and item.address.casilla_id == _RETENCIONES_BOX
    )
    return field


def test_the_retencion_the_ledger_supplied_is_imported_and_not_assumed(secure_objects: SecureObjectRepository) -> None:
    _seed_taxpayer_profile()
    _persist_ledger(secure_objects)

    with bundled_indexed_authority().operation() as operation:
        work_unit = _work_unit(secure_objects, _WITHHELD_YEAR, operation)
        revision = _calculate(work_unit, operation)

        # The revision names the resolver and its source kind, and records no figure beside them.
        supplied = bound_input_source_refs(revision.source_provenance)[_RETENCIONES_BOX]
        assert supplied.resolver_id == "ledger_renta_income_aggregation"
        assert supplied.resolved_binding_source is BindingSourceKind.LEDGER_RENTA_INCOME_AGGREGATION
        assert Decimal(revision.casilla_values[_RETENCIONES_BOX]) == _STATED_RETENCION

        form = _form(secure_objects, _WITHHELD_YEAR, operation).form
        field = _box(form)
        assert field.origin is ModeloFormOrigin.IMPORTED
        assert field.source is not None
        assert field.source.source_kind is BindingSourceKind.LEDGER_RENTA_INCOME_AGGREGATION
        assert field.source.family is SourceFamily.RECORDS
        assert field.unattributed is False
        assert _RETENCIONES_BOX not in {
            item.address.casilla_id
            for item in assumed_fields(form)
            if isinstance(item.address, ModeloFormCasillaAddressV1)
        }


def test_a_figure_the_filer_typed_over_the_ledgers_overrides_the_source(secure_objects: SecureObjectRepository) -> None:
    _seed_taxpayer_profile()
    _persist_ledger(secure_objects)

    with bundled_indexed_authority().operation() as operation:
        work_unit = _work_unit(secure_objects, _WITHHELD_YEAR, operation)
        _calculate(work_unit, operation, typed={_RETENCIONES_BOX: _TYPED})

        field = _box(_form(secure_objects, _WITHHELD_YEAR, operation).form)

    assert field.origin is ModeloFormOrigin.OVERRIDES_SOURCE
    assert field.value == _TYPED


def test_a_held_figure_no_resolver_supplied_stays_assumed_until_confirmed() -> None:
    with bundled_indexed_authority().operation() as operation:
        form = built_form(
            operation, "130", _WITHHELD_YEAR, _QUARTER, held={_RETENCIONES_BOX: _TYPED}, entered=frozenset()
        )

    assert _box(form).origin is ModeloFormOrigin.DEFAULT_TO_CONFIRM
    assert _RETENCIONES_BOX in {
        item.address.casilla_id for item in assumed_fields(form) if isinstance(item.address, ModeloFormCasillaAddressV1)
    }

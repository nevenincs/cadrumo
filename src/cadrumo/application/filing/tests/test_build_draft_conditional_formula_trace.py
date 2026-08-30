"""Regression: a conditional computed casilla's trace is its declared inputs.

A computed casilla driven by an ``if_then_else`` formula short-circuits at
evaluation time — only the predicate plus the branch actually taken are
evaluated, so the runtime ``operand_refs`` are a *subset* of the casilla's
statically declared ``formula_input_casilla_ids``. The draft validator
(``_validate_formula_traces``) checks the persisted ``formula_trace_casilla_ids`` against the
declared ``formula_input_casilla_ids`` for set-equality, so a trace built from the runtime
operand set raised a spurious ``formula-divergence`` ERROR and pinned the draft
in ``BORRADOR``.

The worked surface is Modelo 303 ``iva.prorrata-porcentaje``:
``if_then_else(volumen_total > 0, (volumen_con_derecho * 100) / volumen_total,
0)``. When the prorrata volumes are absent (the common general-régimen case),
``volumen_total > 0`` is false, the then-branch is never evaluated, and
``iva.prorrata-volumen-con-derecho`` drops out of the runtime operand set.

These tests prove a complete first-period (1T) Modelo 303 draft built from the
inputs the calculate path persists now reaches
:attr:`ModeloDraftStatus.LISTO_PARA_PRESENTAR`, which is the precondition the
verify workflow gate requires before it can approve and the export can run.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from pydantic import TypeAdapter, ValidationError

from ....core import CasillaId, Period, validated_casilla_id
from ....domain.calculations.registry.ids import BindingId
from ....domain.filing.protocols import ModeloInputs
from ....domain.iva.regimen_simplificado_rows import M303RegimenSimplificadoScope, M303RegimenSimplificadoScopeDecision
from ....domain.submission import ModeloDraftStatus
from .. import build_draft, build_runtime_schema_provider
from ..runtime import ModeloOperatorProfile

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]
_BINDING_ID_ADAPTER: TypeAdapter[BindingId] = TypeAdapter(BindingId)


def _general_m303_scope() -> M303RegimenSimplificadoScopeDecision:
    return M303RegimenSimplificadoScopeDecision(
        scope=M303RegimenSimplificadoScope.REGIMEN_SIMPLIFICADO_NOT_CLAIMED,
    )


def _binding_id(value: object) -> BindingId:
    try:
        return _BINDING_ID_ADAPTER.validate_python(value)
    except ValidationError as exc:
        raise AssertionError(f"test fixture binding key {value!r} is not a canonical binding.id") from exc


_PERIOD = Period.from_year_and_code(2026, "1T")
_TAX_ID = "12345678Z"
_M303_REPERCUTIDO_GENERAL_CUOTA_BINDING: BindingId = _binding_id("modelo-303-iva-repercutido-general-cuota")
_M303_REPERCUTIDO_REDUCIDO_CUOTA_BINDING: BindingId = _binding_id("modelo-303-iva-repercutido-reducido-cuota")
_M303_REPERCUTIDO_SUPER_REDUCIDO_CUOTA_BINDING: BindingId = _binding_id(
    "modelo-303-iva-repercutido-super-reducido-cuota",
)
_M303_SOPORTADO_INTERIORES_CUOTA_BINDING: BindingId = _binding_id("modelo-303-iva-soportado-interiores-cuota")
_M303_AUTOREPERCUTIDO_INTRACOMUNITARIA_CUOTA_BINDING: BindingId = _binding_id(
    "modelo-303-iva-autorepercutido-intracomunitaria-cuota",
)
_M303_COMPENSACION_PENDIENTE_ANTERIORES_BINDING: BindingId = _binding_id(
    "modelo-303-compensacion-pendiente-anteriores",
)
_M303_AUTOCONSUMO_PROMOTOR_BASE_BINDING: BindingId = _binding_id("modelo-303-autoconsumo-promotor-base")
_M303_STATE_ATTRIBUTION_RATIO_BINDING: BindingId = _binding_id("modelo-303-profile-state-attribution-ratio")
_DECL_EJERCICIO_CASILLA: CasillaId = validated_casilla_id("decl.ejercicio")
_DECL_PERIODO_CASILLA: CasillaId = validated_casilla_id("decl.periodo")
_M303_PRORRATA_PORCENTAJE_CASILLA: CasillaId = validated_casilla_id("iva.prorrata-porcentaje")
_M303_PRORRATA_VOLUMEN_CON_DERECHO_CASILLA: CasillaId = validated_casilla_id("iva.prorrata-volumen-con-derecho")


def _modelo_303_1t_inputs() -> ModeloInputs:
    """Inputs a from-nothing Modelo 303 1T calculate persists for the draft.

    A sale of base 1000 / IVA 210 and a purchase of base 500 / IVA 105 reduce to
    the engine cuota bindings below. ``decl.ejercicio`` / ``decl.periodo`` are
    the informational casillas the calculate path projects from the work unit's
    ``(filing_year, period)`` axes; they ride into the draft via the persisted
    ``input_values_by_casilla_id``. ``decl.periodo`` is declared
    ``data_type = "period_code"``, so it carries the AEAT token ``"1T"`` on the
    typed text-scalar channel, not a quarter ordinal on the Decimal channel.
    """
    return {
        _M303_REPERCUTIDO_GENERAL_CUOTA_BINDING: Decimal("210.00"),
        _M303_REPERCUTIDO_REDUCIDO_CUOTA_BINDING: Decimal("0.00"),
        _M303_REPERCUTIDO_SUPER_REDUCIDO_CUOTA_BINDING: Decimal("0.00"),
        _M303_SOPORTADO_INTERIORES_CUOTA_BINDING: Decimal("105.00"),
        _M303_AUTOREPERCUTIDO_INTRACOMUNITARIA_CUOTA_BINDING: Decimal("0.00"),
        _M303_COMPENSACION_PENDIENTE_ANTERIORES_BINDING: Decimal("0.00"),
        _M303_AUTOCONSUMO_PROMOTOR_BASE_BINDING: Decimal("0.00"),
        _M303_STATE_ATTRIBUTION_RATIO_BINDING: Decimal("100"),
        _DECL_EJERCICIO_CASILLA: Decimal("2026"),
        _DECL_PERIODO_CASILLA: "1T",
    }


def _build_modelo_303_1t_draft():
    schema_provider = build_runtime_schema_provider(
        filing_year=2026,
        period=_PERIOD,
        modelos=("303",),
    )
    return build_draft(
        modelo="303",
        period=_PERIOD,
        profile=ModeloOperatorProfile(tax_id=_TAX_ID, display_name="Conditional-trace regression"),
        inputs=_modelo_303_1t_inputs(),
        schema_provider=schema_provider,
    ), schema_provider


def test_conditional_computed_casilla_trace_equals_declared_formula_inputs() -> None:
    """The prorrata trace carries every declared input, not just the branch taken.

    Structural assertion (not a numeric oracle): the persisted ``formula_trace_casilla_ids``
    of the conditional computed casilla equals the schema's declared
    ``formula_input_casilla_ids``, which the validator's divergence rule checks. Before the
    fix the trace was the short-circuit runtime operand set
    (``iva.prorrata-volumen-total`` only), so this assertion failed.
    """
    draft, schema_provider = _build_modelo_303_1t_draft()
    collection = schema_provider.get_collection("303")
    schema = collection.get(_M303_PRORRATA_PORCENTAJE_CASILLA)
    assert schema is not None
    declared_inputs = schema.formula_input_casilla_ids

    # The casilla genuinely has more than one declared input (both branches of
    # the conditional reference distinct casillas); otherwise the short-circuit
    # subset would coincide with the full set and the regression could not occur.
    assert len(declared_inputs) >= 2
    assert _M303_PRORRATA_VOLUMEN_CON_DERECHO_CASILLA in declared_inputs

    value = next(v for v in draft.values if v.casilla_id == _M303_PRORRATA_PORCENTAJE_CASILLA)
    assert value.formula_trace_casilla_ids is not None
    assert set(value.formula_trace_casilla_ids) == set(declared_inputs)


def test_modelo_303_first_period_draft_reaches_listo_para_presentar() -> None:
    """A complete first-period 303 draft is filing-ready, with zero ERROR findings.

    This is the end-to-end precondition the verify workflow gate enforces: a
    draft still in ``BORRADOR`` aborts the gate with ``DRAFT_HAS_ERRORS``. Before
    the fix the spurious prorrata divergence kept the draft in ``BORRADOR``.
    """
    draft, _ = _build_modelo_303_1t_draft()

    blocking = [finding for finding in draft.findings if finding.code == "formula-divergence"]
    assert blocking == []
    assert draft.status is ModeloDraftStatus.LISTO_PARA_PRESENTAR

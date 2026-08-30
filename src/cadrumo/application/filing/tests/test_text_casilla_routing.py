"""Regression tests for text-casilla routing in filing draft construction."""

from __future__ import annotations

from decimal import Decimal

import pytest

from ....core import (
    CasillaId,
    Period,
    validated_casilla_id,
)
from ....domain.filing.errors import ModeloBuilderError
from ....domain.filing.schema import ModeloValueKind
from ....domain.iva.regimen_simplificado_rows import M303RegimenSimplificadoScope, M303RegimenSimplificadoScopeDecision
from .. import build_draft
from ..runtime import ModeloOperatorProfile, build_runtime_schema_provider

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_TIPO_RENTA_CASILLA: CasillaId = validated_casilla_id("tipo_renta", surface="_TIPO_RENTA_CASILLA")
_RENDIMIENTOS_INTEGROS_CASILLA: CasillaId = validated_casilla_id(
    "rendimientos_integros",
    surface="_RENDIMIENTOS_INTEGROS_CASILLA",
)
_VALOR_CATASTRAL_CASILLA: CasillaId = validated_casilla_id("valor_catastral", surface="_VALOR_CATASTRAL_CASILLA")
_COEFICIENTE_IMPUTACION_CASILLA: CasillaId = validated_casilla_id(
    "coeficiente_imputacion_inmobiliaria",
    surface="_COEFICIENTE_IMPUTACION_CASILLA",
)
_DIAS_IMPUTACION_CASILLA: CasillaId = validated_casilla_id("dias_imputacion", surface="_DIAS_IMPUTACION_CASILLA")
_GASTOS_DEDUCIBLES_CASILLA: CasillaId = validated_casilla_id(
    "gastos_deducibles",
    surface="_GASTOS_DEDUCIBLES_CASILLA",
)
_RETENCION_PRACTICADA_CASILLA: CasillaId = validated_casilla_id(
    "retencion_practicada",
    surface="_RETENCION_PRACTICADA_CASILLA",
)
_BASE_IMPONIBLE_CASILLA: CasillaId = validated_casilla_id("base_imponible", surface="_BASE_IMPONIBLE_CASILLA")
# `tipo2.miembro-nif` is gone, and its removal is recorded in the registry
# itself: no field exists at those positions in either bundled design epoch, and
# the casilla named for the member was reading the DECLARANTE's NIF bytes. The
# member's own NIF is `tipo3.miembro-nif`, but that one is declared `text`
# rather than `nif` -- members may be non-resident and carry a foreign
# identifier, which Spanish NIF validation would wrongly refuse. So the routing
# property this case exists for is exercised on the casilla the registry DOES
# declare as `nif`.
_M184_NIF_TYPED_CASILLA: CasillaId = validated_casilla_id(
    "decl.representante-nif",
    surface="_M184_NIF_TYPED_CASILLA",
)
# Modelo 303 and Modelo 369 declare the same informational period casilla id.
_DECL_PERIODO_CASILLA: CasillaId = validated_casilla_id("decl.periodo", surface="_DECL_PERIODO_CASILLA")


def _general_m303_scope() -> M303RegimenSimplificadoScopeDecision:
    return M303RegimenSimplificadoScopeDecision(
        scope=M303RegimenSimplificadoScope.REGIMEN_SIMPLIFICADO_NOT_CLAIMED,
    )


def test_build_draft_routes_m210_tipo_renta_as_text_input() -> None:
    """M210 ``tipo_renta`` must not enter the Decimal casilla-input channel."""
    period = Period.from_year_and_code(2025, "EVENT-1")

    draft = build_draft(
        modelo="210",
        period=period,
        profile=ModeloOperatorProfile(tax_id="12345678Z", display_name="M210 text casilla routing"),
        inputs={
            _TIPO_RENTA_CASILLA: "inmobiliaria",
            _RENDIMIENTOS_INTEGROS_CASILLA: Decimal("0"),
            _VALOR_CATASTRAL_CASILLA: Decimal("100000.00"),
            _COEFICIENTE_IMPUTACION_CASILLA: Decimal("0.011"),
            _DIAS_IMPUTACION_CASILLA: Decimal("365"),
            _GASTOS_DEDUCIBLES_CASILLA: Decimal("0"),
            _RETENCION_PRACTICADA_CASILLA: Decimal("0"),
        },
        schema_provider=build_runtime_schema_provider(modelos=("210",), filing_year=2025, period=period),
    )

    values = {value.casilla_id: value for value in draft.values}
    tipo_renta = values[_TIPO_RENTA_CASILLA]

    assert tipo_renta.kind is ModeloValueKind.LITERAL
    assert tipo_renta.value == "inmobiliaria"
    assert values[_BASE_IMPONIBLE_CASILLA].value == Decimal("1100.00")


def test_build_draft_routes_and_validates_a_nif_typed_m184_casilla() -> None:
    """A registry-declared NIF reaches its scalar validator, not Decimal parsing."""
    period = Period.from_year_and_code(2026, "0A")

    draft = build_draft(
        modelo="184",
        period=period,
        profile=ModeloOperatorProfile(tax_id="12345678Z", display_name="M184 NIF routing"),
        inputs={_M184_NIF_TYPED_CASILLA: "12345678Z"},
        schema_provider=build_runtime_schema_provider(modelos=("184",), filing_year=2026, period=period),
    )

    values = {value.casilla_id: value for value in draft.values}
    assert values[_M184_NIF_TYPED_CASILLA].value == "12345678Z"

    with pytest.raises(ModeloBuilderError) as refusal:
        build_draft(
            modelo="184",
            period=period,
            profile=ModeloOperatorProfile(tax_id="12345678Z", display_name="M184 NIF routing"),
            inputs={_M184_NIF_TYPED_CASILLA: "12345678A"},
            schema_provider=build_runtime_schema_provider(modelos=("184",), filing_year=2026, period=period),
        )

    # The wrapper is localized; the wrapped registry error still names the defect.
    assert refusal.value.translated_message == "application.filing.build_draft.errors.text_casilla_invalid"
    assert "invalid NIF / NIE / CIF identifier" in str(refusal.value.__cause__)


def test_build_draft_routes_and_validates_modelo_369_period_code() -> None:
    """A registry period-code casilla uses the same typed-string channel as NIF."""
    period = Period.from_year_and_code(2025, "EXT-1T")
    provider = build_runtime_schema_provider(modelos=("369",), filing_year=2025, period=period)
    profile = ModeloOperatorProfile(tax_id="12345678Z", display_name="M369 period routing")

    draft = build_draft(
        modelo="369",
        period=period,
        profile=profile,
        inputs={_DECL_PERIODO_CASILLA: "EXT-1T"},
        schema_provider=provider,
    )

    values = {value.casilla_id: value for value in draft.values}
    assert values[_DECL_PERIODO_CASILLA].value == "EXT-1T"

    with pytest.raises(ModeloBuilderError) as refusal:
        build_draft(
            modelo="369",
            period=period,
            profile=profile,
            inputs={_DECL_PERIODO_CASILLA: "T1"},
            schema_provider=provider,
        )

    # The refusal is localized, so its rendered text no longer spells the
    # offending value. One key serves every text-casilla rejection, so the key
    # alone would not tell an invalid period token from any other bad scalar:
    # the context names the casilla and its declared data_type, and the CAUSE
    # -- the registry validation error this wraps -- still carries the value.
    assert refusal.value.translated_message == "application.filing.build_draft.errors.text_casilla_invalid"
    context = refusal.value.context or {}
    assert context.get("casilla_id") == _DECL_PERIODO_CASILLA
    assert context.get("data_type") == "period_code"
    assert "period_code value 'T1' does not match" in str(refusal.value.__cause__)


def test_build_draft_refuses_ordinal_shaped_modelo_303_period_value() -> None:
    """A stale ordinal-shaped ``decl.periodo`` is refused loudly at draft build.

    Modelo 303's ``decl.periodo`` was previously filled with the bare quarter
    ordinal, so a revision persisted before the token fix carries
    ``Decimal("1")`` in ``casilla_values``; the filing replay stringifies that
    to ``"1"`` and feeds it back as a draft input. ``"1"`` is not a supported
    filing-period form (``"01"`` is monthly January, ``"1T"`` is the first
    quarter), so the typed text-scalar channel must refuse it rather than
    render a value AEAT does not accept.

    This targets the BUILD GATE, which is where the refusal genuinely lives: a
    strict pydantic load of the persisted revision cannot reject ``"1"``,
    because ``input_values_by_casilla_id`` is a ``Mapping[CasillaId, str]`` and
    ``"1"`` is a perfectly well-formed string — it is merely the wrong one. The
    remedy for such a revision is recalculation, never coercion.

    Mutation check: routing ``decl.periodo`` back to the Decimal channel (the
    retired ``data_type == "text"`` literal membership filter)
    makes ``"1"`` parse as a Decimal and the build succeed, flipping this
    assertion from pass to fail.
    """
    period = Period.from_year_and_code(2026, "1T")
    provider = build_runtime_schema_provider(modelos=("303",), filing_year=2026, period=period)
    profile = ModeloOperatorProfile(tax_id="12345678Z", display_name="M303 stale period value")

    with pytest.raises(ModeloBuilderError) as refusal:
        build_draft(
            modelo="303",
            period=period,
            profile=profile,
            inputs={_DECL_PERIODO_CASILLA: "1"},
            schema_provider=provider,
        )

    # The refusal is localized, so its rendered text no longer spells the
    # offending value. One key serves every text-casilla rejection, so the key
    # alone would not tell an invalid period token from any other bad scalar:
    # the context names the casilla and its declared data_type, and the CAUSE
    # -- the registry validation error this wraps -- still carries the value.
    assert refusal.value.translated_message == "application.filing.build_draft.errors.text_casilla_invalid"
    context = refusal.value.context or {}
    assert context.get("casilla_id") == _DECL_PERIODO_CASILLA
    assert context.get("data_type") == "period_code"
    assert "period_code value '1' does not match" in str(refusal.value.__cause__)

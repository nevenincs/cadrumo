"""Contract tests for identity fields populated by the production build_draft path.

:class:`ModeloDraft.subject_tax_id` and :class:`ModeloDraft.snapshot_ref`
both default to ``None`` on the model so already-persisted drafts remain
loadable. The production ``build_draft`` entry point is the only path
that constructs a *new* draft, and it must populate both fields:
``subject_tax_id`` from the validated profile substrate and
``snapshot_ref`` from the resolved registry snapshot. Without a contract
test exercising the real ``build_draft``, a regression that stopped
wiring either field would leave new drafts silently identity-less and
the encrypted-persistence roundtrip suite would not catch it (the
roundtrip fixtures build drafts directly, not via ``build_draft``).
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import cast

import pytest

from ....core import Period
from ....core.resources import resources
from ....domain.calculations.registry import CasillaId, validated_casilla_id
from ....domain.filing import ModeloBuilderError
from .. import _filing_period_date, build_draft, build_runtime_schema_provider
from ..testing import ModeloTestProfile

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_M130_INGRESOS_CASILLA: CasillaId = validated_casilla_id("01", surface="_M130_INGRESOS_CASILLA")
_M130_GASTOS_CASILLA: CasillaId = validated_casilla_id("02", surface="_M130_GASTOS_CASILLA")
_M130_PAGOS_PREVIOS_CASILLA: CasillaId = validated_casilla_id("05", surface="_M130_PAGOS_PREVIOS_CASILLA")
_M130_RETENCIONES_CASILLA: CasillaId = validated_casilla_id("06", surface="_M130_RETENCIONES_CASILLA")
_M130_AGRARIAN_VOLUME_CASILLA: CasillaId = validated_casilla_id("08", surface="_M130_AGRARIAN_VOLUME_CASILLA")
_M130_AGRARIAN_WITHHELD_CASILLA: CasillaId = validated_casilla_id("10", surface="_M130_AGRARIAN_WITHHELD_CASILLA")
_M130_HOME_DEDUCTION_CASILLA: CasillaId = validated_casilla_id("16", surface="_M130_HOME_DEDUCTION_CASILLA")
_M130_PRIOR_RETURN_CASILLA: CasillaId = validated_casilla_id("18", surface="_M130_PRIOR_RETURN_CASILLA")
_M303_PREVIOUS_COMPENSATION_CASILLA: CasillaId = validated_casilla_id(
    "iva.compensacion-pendiente-periodos-anteriores",
    surface="_M303_PREVIOUS_COMPENSATION_CASILLA",
)
_M303_REGIMEN_GENERAL_RESULT_CASILLA: CasillaId = validated_casilla_id(
    "iva.resultado-regimen-general",
    surface="_M303_REGIMEN_GENERAL_RESULT_CASILLA",
)
_M200_AMBIGUOUS_PRINTED_NUMBER: CasillaId = validated_casilla_id(
    "00562",
    surface="_M200_AMBIGUOUS_PRINTED_NUMBER",
)
_M200_ECPN_REUSED_PRINTED_NUMBER_CASILLA: CasillaId = validated_casilla_id(
    "DP200010:00562",
    surface="_M200_ECPN_REUSED_PRINTED_NUMBER_CASILLA",
)
_M200_LIQUIDACION_REUSED_PRINTED_NUMBER_CASILLA: CasillaId = validated_casilla_id(
    "DP200014:00562",
    surface="_M200_LIQUIDACION_REUSED_PRINTED_NUMBER_CASILLA",
)


def _profile() -> ModeloTestProfile:
    return ModeloTestProfile(
        tax_id="12345678Z",
        display_name="build_draft identity contract",
    )


def test_build_draft_populates_subject_tax_id_and_snapshot_ref() -> None:
    """The production build_draft path populates both identity fields.

    Both ``subject_tax_id`` and ``snapshot_ref`` default to ``None`` on
    :class:`ModeloDraft`; this contract test pins that a freshly built
    draft carries the validated taxpayer identity and the registry
    snapshot reference resolved during the build.
    """

    draft = build_draft(
        modelo="130",
        period=Period.from_year_and_code(2026, "1T"),
        profile=_profile(),
        inputs={
            _M130_INGRESOS_CASILLA: Decimal("10000"),
            _M130_GASTOS_CASILLA: Decimal("4000"),
            _M130_PAGOS_PREVIOS_CASILLA: Decimal("250"),
            _M130_RETENCIONES_CASILLA: Decimal("100"),
            _M130_AGRARIAN_VOLUME_CASILLA: Decimal("2000"),
            _M130_AGRARIAN_WITHHELD_CASILLA: Decimal("10"),
            # Binding IDs are extracted from the flat inputs dict via
            # _decimal_inputs_for_ids(inputs, decimal_binding_ids).
            "irpf.previous_year_economic_activity_net_income": Decimal("13000"),
            "modelo-130-pagos-fraccionados-anteriores": Decimal("250"),
            # Casilla 15 is previous_filing-bound (modelo-130-resultados-
            # negativos-anteriores). For Q1 the prior-quarter anchor is
            # absent by design (max_year_delta=0, no prior trimestre in
            # the same ejercicio). Supplying it as a casilla input would
            # violate the smuggled-binding guard; the formula
            # engine materialises it as Decimal("0") via the absent-by-
            # design path with provenance marker on the CasillaObservation.
            _M130_HOME_DEDUCTION_CASILLA: Decimal("0"),
            _M130_PRIOR_RETURN_CASILLA: Decimal("0"),
        },
        schema_provider=build_runtime_schema_provider(),
    )

    assert draft.subject_tax_id is not None
    assert draft.subject_tax_id == "12345678Z"
    assert draft.subject_tax_id == draft.profile_tax_id

    snapshot = resources().modelos.authority.snapshot("130", filing_year=2026, period="1T", on=date(2026, 4, 1))

    assert draft.snapshot_ref is not None
    assert draft.snapshot_ref.modelo == "130"
    assert draft.snapshot_ref.revision_id == snapshot.revision.id
    assert draft.snapshot_ref.modelo_year == 2026
    assert draft.snapshot_ref.period == "1T"


def test_build_draft_rejects_whitespace_padded_casilla_input_key() -> None:
    """The filing builder must not silently ignore an inexact casilla key."""
    period = Period.from_year_and_code(2026, "1T")

    with pytest.raises(ModeloBuilderError, match="without leading or trailing whitespace"):
        build_draft(
            modelo="130",
            period=period,
            profile=_profile(),
            inputs={
                cast(CasillaId, " 01"): Decimal("10000"),
            },
            schema_provider=build_runtime_schema_provider(modelos=("130",), filing_year=2026, period=period),
        )


def test_build_draft_rejects_printed_number_for_semantic_casilla_id() -> None:
    """A printed number must not be accepted as a filing input casilla reference."""
    period = Period.from_year_and_code(2026, "1T")
    snapshot = resources().modelos.authority.snapshot("303", filing_year=2026, period=period.code, on=date(2026, 4, 1))
    casilla = next(c for c in snapshot.revision.casillas if c.id == _M303_PREVIOUS_COMPENSATION_CASILLA)
    assert casilla.number != casilla.id

    with pytest.raises(ModeloBuilderError, match="non-canonical casilla reference tokens are not accepted") as exc_info:
        build_draft(
            modelo="303",
            period=period,
            profile=_profile(),
            inputs={
                casilla.number: Decimal("100.00"),
            },
            schema_provider=build_runtime_schema_provider(modelos=("303",), filing_year=2026, period=period),
        )

    assert "iva.compensacion-pendiente-periodos-anteriores" in str(exc_info.value)


def test_build_draft_rejects_ambiguous_reused_printed_number() -> None:
    """A reused printed number must fail before any filing calculation can run."""
    period = Period.from_year_and_code(2024, "0A")

    with pytest.raises(ModeloBuilderError, match="is ambiguous") as exc_info:
        build_draft(
            modelo="200",
            period=period,
            profile=_profile(),
            inputs={
                _M200_AMBIGUOUS_PRINTED_NUMBER: Decimal("100.00"),
            },
            schema_provider=build_runtime_schema_provider(modelos=("200",), filing_year=2024, period=period),
        )

    assert _M200_ECPN_REUSED_PRINTED_NUMBER_CASILLA in str(exc_info.value)
    assert _M200_LIQUIDACION_REUSED_PRINTED_NUMBER_CASILLA in str(exc_info.value)


def test_build_draft_rejects_export_ref_for_semantic_casilla_id() -> None:
    """An export field reference must not be accepted as a filing input casilla reference."""
    period = Period.from_year_and_code(2026, "1T")
    snapshot = resources().modelos.authority.snapshot("303", filing_year=2026, period=period.code, on=date(2026, 4, 1))
    casilla = next(c for c in snapshot.revision.casillas if c.id == _M303_REGIMEN_GENERAL_RESULT_CASILLA)
    export_ref = next(ref for ref in casilla.export_refs if ref != casilla.id)

    with pytest.raises(ModeloBuilderError, match="non-canonical casilla reference tokens are not accepted") as exc_info:
        build_draft(
            modelo="303",
            period=period,
            profile=_profile(),
            inputs={
                export_ref: Decimal("100.00"),
            },
            schema_provider=build_runtime_schema_provider(modelos=("303",), filing_year=2026, period=period),
        )

    assert _M303_REGIMEN_GENERAL_RESULT_CASILLA in str(exc_info.value)


def test_typed_extended_and_event_periods_resolve_filing_date_context() -> None:
    """Typed non-standard registry periods still supply the calculation date axis."""

    assert _filing_period_date(Period.from_year_and_code(2025, "EXT-1T")) == date(2025, 3, 31)
    assert _filing_period_date(Period.from_year_and_code(2025, "EXT-4T")) == date(2025, 12, 31)
    assert _filing_period_date(Period.from_year_and_code(2025, "AD-HOC")) == date(2025, 12, 31)

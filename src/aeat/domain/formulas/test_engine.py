"""End-to-end tests for :class:`Engine` against the Modelo 130 rulesets.

Exercises :class:`aeat.domain.formulas._engine.Engine` ``derive`` and
``audit_against`` paths plus :func:`compute_casilla_13_minoracion`
edge-case behaviour against the
:data:`aeat.domain.formulas._rulesets.modelo_130_2024.RULESET`.
"""

from __future__ import annotations

from decimal import Decimal
from typing import cast

import pytest

from ...core.errors import (
    AuditDiscrepancyError,
    CasillaNotDefinedError,
    EvaluationError,
)
from ..modelos import ModeloCode
from ._codes import Quarter
from ._engine import Engine
from ._period import FiscalPeriod
from ._registry import get_registry
from ._rulesets.modelo_130_2024 import (
    RULESET as MODELO_130_2024,
)
from ._rulesets.modelo_130_2024 import (
    compute_casilla_13_minoracion,
)

pytestmark = [pytest.mark.unit, pytest.mark.domain_model]


def _resolve_2024_q2():
    return get_registry().resolve(
        modelo=ModeloCode.MODELO_130,
        period=FiscalPeriod(year=2024, quarter=Quarter.Q2),
    )


@pytest.mark.unit
def test_derive_q1_ordinary_apartado_i_positive() -> None:
    """Happy-path Apartado I derivation matches hand-computed values."""
    engine = Engine()
    ledger = engine.derive(
        ruleset=_resolve_2024_q2(),
        inputs={
            "01": Decimal("12000"),
            "02": Decimal("3500"),
            "06": Decimal("500"),
        },
    )
    values = {entry.casilla_id: entry.value for entry in ledger.entries}
    assert values["03"] == Decimal("8500.00")
    assert values["04"] == Decimal("1700.00")
    assert values["07"] == Decimal("1200.00")
    assert values["09"] == Decimal("0.00")
    assert values["11"] == Decimal("0.00")
    assert values["12"] == Decimal("1200.00")
    assert values["14"] == Decimal("1200.00")
    assert values["17"] == Decimal("1200.00")
    assert values["19"] == Decimal("1200.00")


@pytest.mark.unit
def test_derive_q1_loss_floors_pago_fraccionado_and_total() -> None:
    """Negative rendimiento neto floors casilla 04 at 0 and casilla 12 at 0."""
    engine = Engine()
    ledger = engine.derive(
        ruleset=_resolve_2024_q2(),
        inputs={"01": Decimal("1000"), "02": Decimal("3000"), "06": Decimal("500")},
    )
    values = {entry.casilla_id: entry.value for entry in ledger.entries}
    assert values["03"] == Decimal("-2000.00")
    assert values["04"] == Decimal("0.00")
    assert values["07"] == Decimal("-500.00")
    assert values["12"] == Decimal("0.00")
    assert values["14"] == Decimal("0.00")
    assert values["17"] == Decimal("0.00")
    assert values["19"] == Decimal("0.00")


@pytest.mark.unit
def test_derive_caller_maintained_arrastre() -> None:
    """Prior-quarter 19 carry (casilla 15) flows through casilla 17 as a user-input."""
    engine = Engine()
    ledger = engine.derive(
        ruleset=_resolve_2024_q2(),
        inputs={
            "01": Decimal("12000"),
            "02": Decimal("3500"),
            "06": Decimal("500"),
            "15": Decimal("500"),
        },
    )
    values = {entry.casilla_id: entry.value for entry in ledger.entries}
    assert values["14"] == Decimal("1200.00")
    assert values["17"] == Decimal("700.00")
    assert values["19"] == Decimal("700.00")


@pytest.mark.unit
def test_derive_pago_fraccionado_anterior_flows_through_casilla_07() -> None:
    """Caller-maintained casilla 05 reduces casilla 07 by its amount."""
    engine = Engine()
    ledger = engine.derive(
        ruleset=_resolve_2024_q2(),
        inputs={
            "01": Decimal("20000"),
            "02": Decimal("5000"),
            "05": Decimal("800"),
            "06": Decimal("400"),
        },
    )
    values = {entry.casilla_id: entry.value for entry in ledger.entries}
    # 03 = 15000, 04 = 3000, 07 = 3000 - 800 - 400 = 1800.
    assert values["03"] == Decimal("15000.00")
    assert values["04"] == Decimal("3000.00")
    assert values["07"] == Decimal("1800.00")


@pytest.mark.unit
def test_derive_apartados_cross_offset() -> None:
    """A positive Apartado I offsets a negative Apartado II in casilla 12."""
    engine = Engine()
    ledger = engine.derive(
        ruleset=_resolve_2024_q2(),
        inputs={
            "01": Decimal("10000"),
            "02": Decimal("5000"),
            "06": Decimal("100"),
            "08": Decimal("1000"),
            "10": Decimal("50"),
        },
    )
    values = {entry.casilla_id: entry.value for entry in ledger.entries}
    # 03 = 5000; 04 = 1000; 07 = 1000 - 0 - 100 = 900.
    # 09 = 20; 11 = 20 - 50 = -30.
    # 12 = max(0, 900 + (-30)) = 870.
    assert values["07"] == Decimal("900.00")
    assert values["11"] == Decimal("-30.00")
    assert values["12"] == Decimal("870.00")


@pytest.mark.unit
def test_derive_casilla_14_signed_negative_per_aeat_literal() -> None:
    """Casilla 14 preserves algebraic negative per AEAT Instrucciones."""
    engine = Engine()
    ledger = engine.derive(
        ruleset=_resolve_2024_q2(),
        inputs={
            "01": Decimal("500"),
            "02": Decimal("500"),
            "13": Decimal("100"),
        },
    )
    values = {entry.casilla_id: entry.value for entry in ledger.entries}
    assert values["12"] == Decimal("0.00")
    assert values["14"] == Decimal("-100.00")


@pytest.mark.unit
def test_audit_detects_discrepancy() -> None:
    """audit_against flags a user-supplied derived value that disagrees."""
    engine = Engine()
    report = engine.audit_against(
        ruleset=_resolve_2024_q2(),
        provided={
            "01": Decimal("12000"),
            "02": Decimal("3500"),
            "03": Decimal("8499"),
            "06": Decimal("500"),
        },
    )
    assert len(report.discrepancies) == 1
    discrepancy = report.discrepancies[0]
    assert discrepancy.casilla_id == "03"
    assert discrepancy.computed_value == Decimal("8500.00")
    assert discrepancy.user_value == Decimal("8499")


@pytest.mark.unit
def test_audit_clean_when_derived_matches() -> None:
    """audit_against returns an empty discrepancy tuple when math agrees."""
    engine = Engine()
    report = engine.audit_against(
        ruleset=_resolve_2024_q2(),
        provided={
            "01": Decimal("12000"),
            "02": Decimal("3500"),
            "03": Decimal("8500.00"),
            "06": Decimal("500"),
        },
    )
    assert report.is_clean()
    report.assert_clean()  # does not raise


@pytest.mark.unit
def test_audit_report_assert_clean_raises() -> None:
    """AuditReport.assert_clean raises AuditDiscrepancyError."""
    engine = Engine()
    report = engine.audit_against(
        ruleset=_resolve_2024_q2(),
        provided={
            "01": Decimal("12000"),
            "02": Decimal("3500"),
            "03": Decimal("1"),
        },
    )
    with pytest.raises(AuditDiscrepancyError):
        report.assert_clean()


@pytest.mark.unit
@pytest.mark.parametrize(
    ("rendimiento_neto", "expected"),
    [
        (Decimal("0"), Decimal("100")),
        (Decimal("8500"), Decimal("100")),
        (Decimal("9000"), Decimal("100")),
        (Decimal("9000.01"), Decimal("75")),
        (Decimal("10000"), Decimal("75")),
        (Decimal("10000.01"), Decimal("50")),
        (Decimal("11000"), Decimal("50")),
        (Decimal("11000.01"), Decimal("25")),
        (Decimal("12000"), Decimal("25")),
        (Decimal("12000.01"), Decimal("0")),
        (Decimal("50000"), Decimal("0")),
    ],
)
def test_compute_casilla_13_sliding_scale(
    rendimiento_neto: Decimal,
    expected: Decimal,
) -> None:
    """The art 110.3.c step function lands on the right tier at every boundary."""
    assert compute_casilla_13_minoracion(rendimiento_neto) == expected


@pytest.mark.unit
def test_compute_casilla_13_rejects_non_decimal() -> None:
    """The helper only accepts Decimal inputs."""
    sentinel: Decimal = cast(Decimal, 1000)
    with pytest.raises(TypeError):
        compute_casilla_13_minoracion(sentinel)


@pytest.mark.unit
def test_derive_deterministic_ledger_order() -> None:
    """Two runs yield byte-identical ledgers."""
    engine = Engine()
    inputs = {
        "01": Decimal("12000"),
        "02": Decimal("3500"),
        "06": Decimal("500"),
    }
    first = engine.derive(ruleset=_resolve_2024_q2(), inputs=inputs)
    second = engine.derive(ruleset=_resolve_2024_q2(), inputs=inputs)
    assert first.model_dump_json() == second.model_dump_json()


@pytest.mark.unit
def test_derive_rejects_float_inputs() -> None:
    """Floating-point monetary inputs are refused at the engine boundary."""
    engine = Engine()
    tainted: dict[str, Decimal] = {
        "01": cast(Decimal, 12000.0),
        "02": Decimal("3500"),
    }
    with pytest.raises(ValueError):
        engine.derive(ruleset=_resolve_2024_q2(), inputs=tainted)


@pytest.mark.unit
def test_derive_rejects_unknown_casilla() -> None:
    """Inputs keyed to casillas not declared by the ruleset are rejected."""
    engine = Engine()
    with pytest.raises(CasillaNotDefinedError):
        engine.derive(
            ruleset=_resolve_2024_q2(),
            inputs={"99": Decimal("1")},
        )


@pytest.mark.unit
def test_derive_defaults_missing_user_inputs_to_zero() -> None:
    """Missing user-input casillas default to zero per the AEAT blank-field contract."""
    engine = Engine()
    ledger = engine.derive(
        ruleset=_resolve_2024_q2(),
        inputs={"01": Decimal("5000"), "02": Decimal("2000")},
    )
    values = {entry.casilla_id: entry.value for entry in ledger.entries}
    # 03 = 3000, 04 = 600, 07 = 600 - 0 - 0 = 600.
    assert values["07"] == Decimal("600.00")


@pytest.mark.unit
def test_ledger_entry_records_operand_metadata() -> None:
    """Each ledger entry traces its formula id and contributing casillas."""
    engine = Engine()
    ledger = engine.derive(
        ruleset=_resolve_2024_q2(),
        inputs={"01": Decimal("100"), "02": Decimal("40")},
    )
    casilla_03 = next(e for e in ledger.entries if e.casilla_id == "03")
    assert casilla_03.formula_id == "modelo_130.2024.rendimiento_neto"
    assert casilla_03.operand_refs == ("01", "02")
    assert casilla_03.operand_values == (Decimal("100"), Decimal("40"))
    assert casilla_03.ruleset_id == "modelo_130.2024"


@pytest.mark.unit
def test_two_rulesets_derive_identical_results_for_same_inputs() -> None:
    """2024 and 2025 rulesets compute the same values because rules are unchanged."""
    engine = Engine()
    inputs = {
        "01": Decimal("10000"),
        "02": Decimal("4000"),
        "06": Decimal("250"),
    }
    registry = get_registry()
    rs_2024 = registry.resolve(
        modelo=ModeloCode.MODELO_130,
        period=FiscalPeriod(year=2024, quarter=Quarter.Q2),
    )
    rs_2025 = registry.resolve(
        modelo=ModeloCode.MODELO_130,
        period=FiscalPeriod(year=2025, quarter=Quarter.Q2),
    )
    ledger_2024 = engine.derive(ruleset=rs_2024, inputs=inputs)
    ledger_2025 = engine.derive(ruleset=rs_2025, inputs=inputs)
    vals_2024 = {e.casilla_id: e.value for e in ledger_2024.entries}
    vals_2025 = {e.casilla_id: e.value for e in ledger_2025.entries}
    assert vals_2024 == vals_2025


@pytest.mark.unit
def test_engine_logs_evaluation_info(caplog: pytest.LogCaptureFixture) -> None:
    """The engine emits a single INFO log line per derivation."""
    caplog.set_level("INFO", logger="aeat.domain.formulas._engine")
    engine = Engine()
    engine.derive(
        ruleset=_resolve_2024_q2(),
        inputs={"01": Decimal("100"), "02": Decimal("40")},
    )
    info_lines = [r for r in caplog.records if r.levelname == "INFO"]
    assert any("derived ruleset=modelo_130.2024" in r.getMessage() for r in info_lines)


@pytest.mark.unit
def test_derive_division_by_zero_raises_evaluation_error() -> None:
    """Domain-level arithmetic faults surface as EvaluationError."""
    # Constructs a synthetic ruleset with div-by-zero to exercise the dispatcher.
    from datetime import date

    from ..casillas import CasillaDataType
    from ..modelos import LegalCitation, LegalCitationSource
    from ._casilla import CasillaDefinition
    from ._formula import (
        DivFormula,
        FormulaCasillaRef,
        FormulaDefinition,
        Literal,
        RoundFormula,
    )
    from ._ruleset import Ruleset

    body = DivFormula(
        operands=(  # type: ignore[arg-type]
            FormulaCasillaRef(casilla_id="01"),
            Literal(value=Decimal("0")),
        )
    )
    fixture_citation = LegalCitation(
        source=LegalCitationSource.REAL_DECRETO,
        article="110",
        url=None,
        quoted_text_es=(
            "Fixture-only citation for the engine division-by-zero test; not authored as a binding ruleset reference."
        ),
        retrieval_date=date(2026, 4, 25),
        is_curated_summary=True,
    )
    ruleset = Ruleset(
        ruleset_id="test.divzero",
        modelo=ModeloCode.MODELO_130,
        effective_from=date(2100, 1, 1),
        effective_to=date(2100, 12, 31),
        casillas=(
            CasillaDefinition(
                casilla_id="01",
                label={"es": "A", "en": "A", "hu": "A"},
                computed=False,
                data_type=CasillaDataType.CURRENCY_EUR,
            ),
            CasillaDefinition(
                casilla_id="02",
                label={"es": "B", "en": "B", "hu": "B"},
                computed=True,
                data_type=CasillaDataType.CURRENCY_EUR,
                legal_basis=(fixture_citation,),
            ),
        ),
        formulas=(
            FormulaDefinition(
                casilla_id="02",
                formula_id="test.divzero.02",
                formula=RoundFormula(operands=(body,)),  # type: ignore[arg-type]
            ),
        ),
    )
    engine = Engine()
    with pytest.raises(EvaluationError):
        engine.derive(ruleset=ruleset, inputs={"01": Decimal("1")})


@pytest.mark.unit
def test_vivienda_habitual_cap_clamp_via_min_op() -> None:
    """The caller applies the 660.14 € cap via min(2%xbase, 660.14, max(0, 14-15))."""
    # Rather than baking the cap into the ruleset (which would require
    # cross-casilla gating the engine does not enforce), we verify that
    # Apartado I base 50000 x 2% = 1000 > 660.14, so the caller-side
    # ``min(..., 660.14)`` would produce 660.14. This test documents the
    # expected integration behaviour.
    base = Decimal("50000")
    rate = Decimal("0.02")
    hard_cap = Decimal("660.14")
    headroom = Decimal("500.00")  # max(0, 14 - 15) for the example
    proposed = base * rate
    clamped = min(proposed, hard_cap, headroom)
    assert clamped == Decimal("500.00")
    # Without any headroom constraint the hard cap wins.
    clamped_cap_only = min(proposed, hard_cap)
    assert clamped_cap_only == Decimal("660.14")


@pytest.mark.unit
def test_modelo_130_2024_modelo_binds_to_authoritative_enum() -> None:
    """The shipped ruleset uses aeat.domain.modelos.ModeloCode."""
    assert MODELO_130_2024.modelo is ModeloCode.MODELO_130

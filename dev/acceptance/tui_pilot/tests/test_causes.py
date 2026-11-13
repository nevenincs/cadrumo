"""A TUI row matches the persona table's row only on its stages and figures, and a differing row names one cause."""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest

from ...persona_table.frontend import DIFFERS, MATCHED
from ...persona_table.rows import Stage, TableRow
from ..causes import outcome, row_cause, unreported_cause
from ..intake import OUT_ENV, TREE_ENV, IntakeConfigurationError, PilotRow, write_rows

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_PERSONA = "synthetic-autonomo"
_YEAR = 7
"""A synthetic year: these rows meet no registry."""


def _table(period: str, *, verify: Stage = Stage.PASSED, export: Stage = Stage.PASSED) -> TableRow:
    return TableRow(
        persona=_PERSONA,
        modelo="130",
        year=_YEAR,
        period=period,
        horizon=_YEAR,
        grounding="verified",
        sources=("rd-439-2007:art-110",),
        has_values=True,
        calculate=Stage.PASSED,
        verify=verify,
        export=export,
        figures=(("01", "1000"), ("03", "475")),
    )


def _row(**data: object) -> PilotRow:
    held = PilotRow(
        persona=_PERSONA,
        modelo="130",
        year=_YEAR,
        period="1T",
        calculate="pass",
        verify="pass",
        export="pass",
        figures={"01": "1000.00", "03": "475.00", "decl.periodo": "1T"},
    )
    return replace(held, **data)


def test_a_row_with_the_tables_stages_and_figures_matches_and_names_no_cause() -> None:
    row = _row()

    assert outcome(row, _table("1T")) == MATCHED
    assert row_cause(row, _table("1T"), []) == (None, "")


def test_a_figure_shown_otherwise_is_the_figures_cause() -> None:
    row = _row(figures={"01": "1000.00", "03": "474.00"})

    cause, words = row_cause(row, _table("1T"), [])

    assert outcome(row, _table("1T")) == DIFFERS
    assert cause == "other:figures_differ"
    assert "casilla 03" in words


def test_a_served_confirmation_before_the_check_is_an_unconfirmed_assumed_value() -> None:
    row = _row(verify="not-reached", export="not-reached", stopped_at="confirm")

    assert row_cause(row, _table("1T"), [])[0] == "assumed_value_unconfirmed"


def test_a_chain_refusal_names_the_earlier_unfiled_returns_own_cause_upstream() -> None:
    first = _row(verify="not-reached", export="not-reached", stopped_at="fill")
    first.cause, first.cause_words = row_cause(first, _table("1T"), [])
    second = _row(
        period="2T",
        calculate="refused",
        verify="not-reached",
        export="not-reached",
        refusal_code="REFUSED_MODELO_PRIOR_PERIOD_UNFILED",
        figures={},
    )
    second.cause, second.cause_words = row_cause(second, _table("2T"), [first])
    third = _row(period="3T", calculate="refused", refusal_code="REFUSED_MODELO_PRIOR_PERIOD_UNFILED", figures={})

    assert first.cause == "next_step_fill_before_verify"
    assert second.cause == "upstream:next_step_fill_before_verify"
    assert row_cause(third, _table("3T"), [first, second])[0] == "upstream:next_step_fill_before_verify"


def test_a_filed_earlier_return_is_never_named_upstream() -> None:
    first = _row(filed=True)
    second = _row(period="2T", calculate="refused", refusal_code="REFUSED_MODELO_PRIOR_PERIOD_UNFILED", figures={})

    assert unreported_cause(first, []) == (None, "")
    assert row_cause(second, _table("2T"), [first])[0] == "other:calculate_refused_modelo_prior_period_unfiled"


def test_a_return_the_table_holds_not_owed_differs_by_the_missing_calendar_verdict() -> None:
    table = _table("1T", verify=Stage.NOT_OWED, export=Stage.NOT_REACHED)

    assert row_cause(_row(), table, [])[0] == "tui_calendar_omits_not_applicable_verdict"


def test_the_intake_line_is_the_persona_tables_schema_and_needs_the_tree(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    out = tmp_path / "tui.jsonl"
    monkeypatch.setenv(OUT_ENV, str(out))
    monkeypatch.delenv(TREE_ENV, raising=False)

    with pytest.raises(IntakeConfigurationError):
        write_rows([PilotRow(persona=_PERSONA)])
    monkeypatch.setenv(TREE_ENV, "synthetic-tree")
    write_rows([PilotRow(persona=_PERSONA), _row(cause="other:figures_differ")])

    lines = [json.loads(line) for line in out.read_text(encoding="utf-8").splitlines()]
    assert [line["modelo"] for line in lines] == [None, "130"]
    assert lines[1]["reason"].startswith("cause=other:figures_differ")
    assert set(lines[1]) == {
        "surface",
        "tree",
        "persona",
        "modelo",
        "year",
        "period",
        "loads",
        "calculate",
        "verify",
        "export",
        "refusal_code",
        "figures",
        "reason",
        "log",
    }

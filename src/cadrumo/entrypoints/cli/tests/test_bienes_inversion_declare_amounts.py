"""A bien de inversion's cuota and prorrata on the command line are read with the canonical decimal grammar.

``1.000`` is how Spanish writes one thousand; read as raw text it would state a
cuota of one euro, so the declaration refuses it, and scientific, comma and
negative forms, before it asks which profile it is for.
"""

from __future__ import annotations

import pytest
import typer
import typer.main

from ....core.time.clock import today_madrid
from ..operation_ledger_bienes_inversion import declare_bien_inversion

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def _context() -> typer.Context:
    app = typer.Typer()

    @app.command()
    def declare() -> None:
        """Stand in for the declare command whose context the boundary receives."""

    return typer.Context(typer.main.get_command(app))


def _declare(*, cuota: str = "210.00", prorrata: str = "100") -> None:
    declare_bien_inversion(
        _context(),
        identifier="bien-1",
        description="maquinaria",
        acquisition_year=today_madrid().year,
        acquisition_ledger_id="entry-1",
        cuota_soportada=cuota,
        prorrata_inicial_pct=prorrata,
        kind="general",
    )


@pytest.mark.parametrize("written", ["1.000", "1e3", "1.234,50", "1,5", "-10", "NaN"])
@pytest.mark.parametrize(("field", "label"), [("cuota", "--cuota-soportada"), ("prorrata", "--prorrata-inicial")])
def test_a_non_canonical_value_is_refused_naming_its_option(field: str, label: str, written: str) -> None:
    with pytest.raises(typer.BadParameter) as refused:
        _declare(**{field: written})

    assert label in str(refused.value)
    assert written in str(refused.value)

"""Hand-curated static casilla schema for Modelo 390 (v1).

Modelo 390 is the annual IVA ``declaración-resumen`` filed once
a year by Spanish autónomos and businesses whose IVA obligations
are settled via the quarterly Modelo 303. The v1 casilla coverage
committed in the ADR ``2026-04-12-modelo-303-390-adr`` is the
arithmetic backbone that reconciles the annual IVA general
regime totals against the four quarterly Modelo 303 drafts; the
full form carries hundreds of additional casillas which are out
of scope for v1 and will ship via follow-up issues.

Quarterly-sum casillas (100, 101, 104, 105, 108, 109, 190, 191,
192, 193) declare EMPTY ``formula_inputs`` at the schema level
because they are not summed from the 390's own casillas but from
*four different drafts*. Their provenance is carried on the
:class:`FilingValue` as a synthetic trace so that the existing
``_validate_formula_traces`` rule does not flag them. The
intra-390 aggregates (84, 85, 86, 95) use real
``formula_inputs`` that refer to the preceding 390 casillas.
"""

from __future__ import annotations

from decimal import Decimal

from .._schema import SCHEMA_VERSION_DEFAULT
from ._modelo_130_schema import StaticCasillaCollection, StaticCasillaSchema


def _quarterly_sum(id_: str, description: str) -> StaticCasillaSchema:
    """Return a schema record for a 390 casilla summed from quarterly drafts.

    These casillas are populated by :class:`Modelo390Builder` via
    a synthetic ``formula_trace`` referring to 303 quarterly
    drafts. They keep ``formula_inputs`` empty because the
    validator's formula-trace rule compares to *in-draft*
    casilla IDs only.
    """
    return StaticCasillaSchema(
        id=id_,
        value_type="decimal",
        required=False,
        default=Decimal("0"),
        description=description,
    )


def _formula(id_: str, inputs: tuple[str, ...], description: str) -> StaticCasillaSchema:
    """Return a computed casilla declaring its in-draft formula inputs."""
    return StaticCasillaSchema(
        id=id_,
        value_type="decimal",
        required=False,
        formula_inputs=inputs,
        description=description,
    )


MODELO_390_SCHEMA = StaticCasillaCollection(
    schema_version=SCHEMA_VERSION_DEFAULT,
    casillas=(
        StaticCasillaSchema(
            id="01",
            value_type="int",
            required=True,
            min_value=2000,
            max_value=2100,
            description="Ejercicio (4-digit year)",
        ),
        # ── IVA devengado anual — régimen general ──
        _quarterly_sum("100", "Base imponible anual al 4%"),
        _quarterly_sum("101", "Cuota anual al 4%"),
        _quarterly_sum("104", "Base imponible anual al 10%"),
        _quarterly_sum("105", "Cuota anual al 10%"),
        _quarterly_sum("108", "Base imponible anual al 21%"),
        _quarterly_sum("109", "Cuota anual al 21%"),
        # ── IVA deducible anual — operaciones interiores ──
        _quarterly_sum("190", "Base imponible anual operaciones interiores corrientes"),
        _quarterly_sum("191", "Cuota deducible anual operaciones interiores corrientes"),
        _quarterly_sum("192", "Base imponible anual operaciones interiores bienes de inversión"),
        _quarterly_sum("193", "Cuota deducible anual bienes de inversión"),
        # ── Resultado anual (in-draft formulas) ──
        _formula("84", ("101", "105", "109"), "Total cuotas devengadas anuales = 101 + 105 + 109"),
        _formula("85", ("191", "193"), "Total a deducir anual = 191 + 193"),
        _formula("86", ("84", "85"), "Resultado régimen general anual = 84 - 85"),
        _formula("95", ("86",), "Resultado liquidación anual = 86"),
    ),
)

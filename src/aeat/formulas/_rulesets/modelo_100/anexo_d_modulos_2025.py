"""Modelo 100 Anexo D — estimación objetiva / módulos (ejercicio 2025).

Estimación objetiva (módulos) is a per-actividad lookup-table régimen
governed by an annual Orden HAC. For ejercicio 2025 the relevant
Orden is HAC/277/2026 (BOE-A-2026-7041); for ejercicio 2026 it is
Orden HAC/1425/2025 (BOE-A-2025-25272 — published 11/12/2025 covering
módulos 2026).

The per-actividad módulo computation (number of employed persons,
floor area, kw of installed power, etc.) is not encoded here — it
lives in the caller's domain because it depends on the actividad code
and the Orden HAC table for the given año. Anexo D módulos verifies
the aggregate chain after the caller has computed the per-módulo
rendimiento neto previo:

- ``0250`` (rendimiento neto previo módulos, input — caller-computed
  from the Orden HAC tabla per actividad)
- ``0255`` — reducción del 5 % por incentivos al empleo / inversión
  (input — caller-computed per the Orden HAC reductions)
- ``0260`` (rendimiento neto reducido módulos, computed) =
  ``clamp_pos(0250 - 0255)``

Stable structurally across 2024 / 2025 / 2026 — only the underlying
Orden HAC tabla values change yearly; that variation is encapsulated
in the caller-supplied 0250 input.
"""

from __future__ import annotations

from datetime import date

from ....i18n import Translatable
from ..._ruleset import ParameterTable
from .._common import (
    casilla,
    clamp_pos,
    formula,
    ref,
    sub_op,
)
from ._common import cite_lirpf, cite_rirpf

EFFECTIVE_FROM = date(2025, 1, 1)
EFFECTIVE_TO = date(2025, 12, 31)


def _label(es: str, en: str, hu: str) -> Translatable:
    return {"es": es, "en": en, "hu": hu}


CITATIONS = (
    cite_lirpf(
        "31",
        "Artículo 31 Ley 35/2006 (IRPF) — método de estimación "
        "objetiva: el rendimiento neto se determinará por aplicación "
        "de los signos, índices y módulos generales y particulares "
        "fijados anualmente por Orden Ministerial (Orden HAC vigente "
        "para el ejercicio).",
    ),
    cite_rirpf(
        "32",
        "Artículo 32 RD 439/2007 (Reglamento del IRPF) — ámbito de "
        "aplicación de la estimación objetiva: actividades incluidas "
        "en la Orden ministerial vigente y que no superen los umbrales "
        "de exclusión (volumen de rendimientos íntegros, volumen de "
        "compras, número de personas empleadas).",
    ),
)


CASILLAS = (
    casilla(
        casilla_id="0250",
        label=_label(
            "Rendimiento neto previo módulos",
            "Net business income before reduction (módulos)",
            "Bruttó vállalkozási jövedelem csökkentés előtt (módulos)",
        ),
        computed=False,
        legal_basis=(CITATIONS[0],),
        notes_es=(
            "Caller-computed from the Orden HAC tabla anual: signos, "
            "índices y módulos por actividad. Para 2025 la Orden "
            "rectora es HAC/277/2026 (BOE-A-2026-7041); para 2026 es "
            "Orden HAC/1425/2025 (BOE-A-2025-25272)."
        ),
    ),
    casilla(
        casilla_id="0255",
        label=_label(
            "Reducción rendimiento neto módulos",
            "Modulus regime reduction",
            "Modulus rendszer csökkentés",
        ),
        computed=False,
        legal_basis=(CITATIONS[0],),
        notes_es=(
            "Reducción del 5 % o porcentaje específico vigente per "
            "Orden HAC del ejercicio (DA primera Orden HAC, en "
            "ocasiones reducciones extraordinarias por DANA, "
            "incendios, etc.)."
        ),
    ),
    casilla(
        casilla_id="0260",
        label=_label(
            "Rendimiento neto reducido módulos",
            "Net business income (reduced, módulos)",
            "Nettó vállalkozási jövedelem (csökkentett, módulos)",
        ),
        computed=True,
        legal_basis=(CITATIONS[0],),
    ),
)


FORMULAS = (
    formula(
        casilla_id="0260",
        formula_id="modelo_100.2025.d_modulos.rendimiento_neto_reducido",
        body=clamp_pos(sub_op(ref("0250"), ref("0255"))),
    ),
)


PARAMETERS = ParameterTable(entries={})


__all__ = [
    "CASILLAS",
    "CITATIONS",
    "EFFECTIVE_FROM",
    "EFFECTIVE_TO",
    "FORMULAS",
    "PARAMETERS",
]

"""Modelo 100 Anexo B2 — rendimientos del capital mobiliario (ejercicio 2025).

Anexo B2 covers dividendos, intereses, and other rendimientos del
capital mobiliario per LIRPF arts. 25-26. Retenciones aplicables al
19% per LIRPF art. 101.4 + RIRPF art. 90 (the rate applied via
Modelo 123 declarations). The aggregation chain on M100:

- ``0048`` (rendimiento neto previo capital mobiliario) =
  ``0028 + 0029 + 0030 + 0031 - 0035`` clamped >= 0
- ``0049`` (rendimiento neto reducido capital mobiliario) =
  ``clamp_pos(0048 - 0032)`` where ``0032`` is the LIRPF art. 26.2
  30% reducción over rendimientos irregulares (caller-supplied since
  it depends on which sub-rendimientos qualify).

Stable across 2024 / 2025 / 2026 (LIRPF arts. 25-26 unchanged at BOE
consolidated text consult 2026-02-28).
"""

from __future__ import annotations

from datetime import date

from ....i18n import Translatable
from ..._ruleset import ParameterTable
from .._common import (
    add_op,
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
        "25",
        "Artículo 25 Ley 35/2006 (IRPF) — define los rendimientos "
        "íntegros del capital mobiliario: dividendos, intereses de "
        "cuentas y de títulos públicos / privados, otras "
        "contraprestaciones derivadas de la cesión a terceros de "
        "capitales propios, rendimientos de operaciones de "
        "capitalización, rendimientos derivados de la propiedad "
        "intelectual cuando el contribuyente no sea el autor.",
    ),
    cite_lirpf(
        "26",
        "Artículo 26 Ley 35/2006 (IRPF) — gastos deducibles del capital "
        "mobiliario (administración, custodia y similares) y reducción "
        "del 30 % sobre rendimientos íntegros con período de generación "
        "superior a dos años o calificados como notoriamente "
        "irregulares, con cap cuantitativo de 300.000 €.",
    ),
    cite_lirpf(
        "101.4",
        "Artículo 101.4 Ley 35/2006 (IRPF) — fija al 19 % la "
        "retención e ingreso a cuenta sobre rendimientos del capital "
        "mobiliario, con las excepciones legales aplicables.",
    ),
    cite_rirpf(
        "90",
        "Artículo 90 RD 439/2007 (Reglamento del IRPF) — aplica el "
        "19 % a la base de retención del capital mobiliario; soporta "
        "el flujo Modelo 123 → Anexo B2 del Modelo 100.",
    ),
)


CASILLAS = (
    casilla(
        casilla_id="0028",
        label=_label(
            "Dividendos íntegros",
            "Gross dividend income",
            "Bruttó osztalékjövedelem",
        ),
        computed=False,
        legal_basis=(CITATIONS[0],),
    ),
    casilla(
        casilla_id="0029",
        label=_label(
            "Intereses de cuentas y depósitos",
            "Bank deposit interest income",
            "Banki betét kamatjövedelem",
        ),
        computed=False,
        legal_basis=(CITATIONS[0],),
    ),
    casilla(
        casilla_id="0030",
        label=_label(
            "Intereses de títulos (públicos / privados)",
            "Securities interest income (public/private)",
            "Értékpapír kamatjövedelem",
        ),
        computed=False,
        legal_basis=(CITATIONS[0],),
    ),
    casilla(
        casilla_id="0031",
        label=_label(
            "Otros rendimientos del capital mobiliario",
            "Other capital-income types",
            "Egyéb tőkejövedelem",
        ),
        computed=False,
        legal_basis=(CITATIONS[0],),
    ),
    casilla(
        casilla_id="0032",
        label=_label(
            "Reducción art. 26.2 — irregularidad capital mobiliario",
            "Art. 26.2 reduction (irregular capital income)",
            "26.2 cikk csökkentés (rendszertelen tőkejövedelem)",
        ),
        computed=False,
        legal_basis=(CITATIONS[1],),
        notes_es=("Importe ya minorado por el 30 % del art. 26.2 sobre la base irregular, con cap de 300.000 €."),
    ),
    casilla(
        casilla_id="0035",
        label=_label(
            "Gastos de administración y custodia",
            "Administration and custody expenses",
            "Adminisztrációs és letétkezelési költségek",
        ),
        computed=False,
        legal_basis=(CITATIONS[1],),
    ),
    casilla(
        casilla_id="0048",
        label=_label(
            "Rendimiento neto previo capital mobiliario",
            "Net capital-income before art. 26.2 reduction",
            "Bruttó tőkejövedelem 26.2 csökkentés előtt",
        ),
        computed=True,
        legal_basis=(CITATIONS[0], CITATIONS[1]),
    ),
    casilla(
        casilla_id="0049",
        label=_label(
            "Rendimiento neto reducido capital mobiliario",
            "Net capital-income (reduced)",
            "Nettó tőkejövedelem (csökkentett)",
        ),
        computed=True,
        legal_basis=(CITATIONS[0], CITATIONS[1]),
    ),
)


FORMULAS = (
    formula(
        casilla_id="0048",
        formula_id="modelo_100.2025.b2.rendimiento_neto_previo",
        body=clamp_pos(
            sub_op(
                add_op(
                    add_op(ref("0028"), ref("0029")),
                    add_op(ref("0030"), ref("0031")),
                ),
                ref("0035"),
            ),
        ),
    ),
    formula(
        casilla_id="0049",
        formula_id="modelo_100.2025.b2.rendimiento_neto_reducido",
        body=clamp_pos(sub_op(ref("0048"), ref("0032"))),
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

"""Synthetic delta-edition fixtures: one modelo id, its references and the casilla and formula TOML fragments."""

from __future__ import annotations

from typing import Final

MODELO_ID: Final = "999"
LEGAL_REF: Final = "ley-58-2003:art-29"
SOURCE_REF: Final = "aeat-manual"
PREDECESSOR_EDITION: Final = "2024"
SUCCESSOR_EDITION: Final = "2025"


def delta_casilla(revision_id: str, casilla_id: str, *, number: str, lineage: str) -> str:
    return (
        f'[[revisions."{revision_id}".casillas]]\n'
        f'id = "{casilla_id}"\n'
        f'number = "{number}"\n'
        'section = ["liquidacion"]\n'
        'data_type = "money"\n'
        f'continuidad_id = "{lineage}"\n'
        f'legal_refs = ["{LEGAL_REF}"]\n'
        f'source_refs = ["{SOURCE_REF}"]\n\n'
    )


def delta_formula(revision_id: str, formula_id: str, *, target: str) -> str:
    return (
        f'[[revisions."{revision_id}".formulas]]\n'
        f'id = "{formula_id}"\n'
        f'target_casilla_id = "{target}"\n'
        'expression = { literal = "0" }\n'
        f'legal_refs = ["{LEGAL_REF}"]\n'
        f'source_refs = ["{SOURCE_REF}"]\n\n'
    )

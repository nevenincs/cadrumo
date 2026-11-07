"""Synthetic delta-edition fixtures: one modelo id, its references and the casilla and formula TOML fragments."""

from __future__ import annotations

from pathlib import Path
from typing import Final

from cadrumo.domain.calculations.registry.tests.authored_editions import filing_year_envelope

MODELO_ID: Final = "999"
LEGAL_REF: Final = "ley-58-2003:art-29"
SOURCE_REF: Final = "aeat-manual"
SUCCESSOR_EDITION_YEAR: Final = filing_year_envelope().horizon - 1
"""The exercise of the successor edition: below the horizon, so it is no open edge of the envelope."""
PREDECESSOR_EDITION_YEAR: Final = SUCCESSOR_EDITION_YEAR - 1
PREDECESSOR_EDITION: Final = str(PREDECESSOR_EDITION_YEAR)
SUCCESSOR_EDITION: Final = str(SUCCESSOR_EDITION_YEAR)


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


def _write_manifest(revision_dir: Path, revision_id: str, *, year: int, extra: str) -> None:
    (revision_dir / "revision.toml").write_text(
        f'[revisions."{revision_id}"]\n'
        f"valid_from = {year}-01-01\n"
        f"valid_to = {year}-12-31\n"
        f'period_selector = {{ years = [{year}], periods = ["0A"] }}\n'
        f'legal_refs = ["{LEGAL_REF}"]\n'
        f'source_refs = ["{SOURCE_REF}"]\n'
        f"{extra}",
        encoding="utf-8",
        newline="\n",
    )


def write_sectioned_edition(
    modelo_dir: Path,
    revision_id: str,
    *,
    manifest_extra: str = "",
    sections: dict[str, str],
) -> Path:
    """Write a one-year edition whose sections each hold one ``0001-declarations.toml``."""
    revision_dir = modelo_dir / "revisions" / revision_id
    revision_dir.mkdir(parents=True)
    _write_manifest(revision_dir, revision_id, year=int(revision_id), extra=manifest_extra)
    for section, text in sections.items():
        (revision_dir / section).mkdir()
        (revision_dir / section / "0001-declarations.toml").write_text(text, encoding="utf-8", newline="\n")
    return revision_dir


def write_revision(
    modelo_dir: Path,
    revision_id: str,
    *,
    year: int,
    casillas: str,
    formulas: str,
    constructs: str = "",
    predecessor: str | None = None,
    extra_manifest: str = "",
) -> None:
    """Write an edition with casillas and formulas, and constructs when given, naming its predecessor."""
    revision_dir = modelo_dir / "revisions" / revision_id
    revision_dir.mkdir(parents=True)
    predecessor_line = f'predecessor = "{predecessor}"\n' if predecessor is not None else ""
    _write_manifest(revision_dir, revision_id, year=year, extra=f"{predecessor_line}{extra_manifest}")
    (revision_dir / "casillas").mkdir()
    (revision_dir / "casillas" / "0001-casillas.toml").write_text(casillas, encoding="utf-8", newline="\n")
    (revision_dir / "formulas").mkdir()
    (revision_dir / "formulas" / "0001-formulas.toml").write_text(formulas, encoding="utf-8", newline="\n")
    if constructs:
        (revision_dir / "constructs").mkdir()
        (revision_dir / "constructs" / "0001-constructs.toml").write_text(constructs, encoding="utf-8", newline="\n")

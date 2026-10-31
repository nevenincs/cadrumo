"""On-disk modelo trees for the edition staging tests: a full first edition and delta editions after it."""

from __future__ import annotations

from pathlib import Path

LEGAL_REF = "ley-58-2003:art-29"


MANIFEST = (
    "[modelo]\n"
    'id = "999"\n'
    'tax_domain = "iva"\n'
    'cadence = "annual"\n'
    'jurisdiction = "ES-AEAT"\n'
    f'legal_refs = ["{LEGAL_REF}"]\n'
    'source_refs = ["aeat-manual"]\n'
)


def edition_casilla(revision_id: str, casilla_id: str, *, number: str, lineage: str) -> str:
    return (
        f'[[revisions."{revision_id}".casillas]]\n'
        f'id = "{casilla_id}"\n'
        f'number = "{number}"\n'
        'section = ["liquidacion"]\n'
        f'continuidad_id = "{lineage}"\n'
        f'legal_refs = ["{LEGAL_REF}"]\n'
        'source_refs = ["aeat-manual"]\n\n'
    )


def write_edition(
    modelo_dir: Path,
    revision_id: str,
    *,
    year: int,
    casillas: str,
    predecessor: str | None = None,
    retire: tuple[str, str] | None = None,
) -> None:
    revision_dir = modelo_dir / "revisions" / revision_id
    (revision_dir / "casillas").mkdir(parents=True)
    predecessor_line = f'predecessor = "{predecessor}"\n' if predecessor is not None else ""
    (revision_dir / "revision.toml").write_text(
        f'[revisions."{revision_id}"]\n'
        f"valid_from = {year}-01-01\n"
        f"valid_to = {year}-12-31\n"
        f'period_selector = {{ years = [{year}], periods = ["0A"] }}\n'
        f'legal_refs = ["{LEGAL_REF}"]\n'
        'source_refs = ["aeat-manual"]\n'
        f"{predecessor_line}",
        encoding="utf-8",
        newline="\n",
    )
    (revision_dir / "casillas" / "0001-casillas.toml").write_text(casillas, encoding="utf-8", newline="\n")
    if retire is not None:
        lineage, from_revision = retire
        (revision_dir / "casilla_continuidad_evolutions").mkdir()
        (revision_dir / "casilla_continuidad_evolutions" / "0001-evolutions.toml").write_text(
            f'[[revisions."{revision_id}".casilla_continuidad_evolutions]]\n'
            f'id = "retire-{lineage}"\n'
            f'continuidad_id = "{lineage}"\n'
            f'from_revision = "{from_revision}"\n'
            f'to_revision = "{revision_id}"\n'
            'evolution_kind = "retired"\n'
            f'legal_refs = ["{LEGAL_REF}"]\n'
            'source_refs = ["aeat-manual"]\n',
            encoding="utf-8",
            newline="\n",
        )


def staged_modelo(root: Path) -> Path:
    modelo_dir = root / "source" / "999"
    modelo_dir.mkdir(parents=True)
    (modelo_dir / "manifest.toml").write_text(MANIFEST, encoding="utf-8", newline="\n")
    return modelo_dir


def migrated_chain(root: Path, *, retire_from: str = "2024") -> Path:
    """2023 states everything; 2024 names 2023, and 2025 names 2024, each stating only what changed.

    ``retire_from`` is the ``from_revision`` of 2025's one retirement record,
    which is the only link the continuity evolution chain offers out of 2025.
    """
    modelo_dir = staged_modelo(root)
    write_edition(
        modelo_dir,
        "2023",
        year=2023,
        casillas=(
            edition_casilla("2023", "0001", number="1", lineage="base-imponible")
            + edition_casilla("2023", "0002", number="2", lineage="cuota-integra")
            + edition_casilla("2023", "0003", number="3", lineage="deduccion-retirada")
        ),
    )
    write_edition(
        modelo_dir,
        "2024",
        year=2024,
        predecessor="2023",
        casillas=edition_casilla("2024", "0002", number="22", lineage="cuota-integra"),
    )
    write_edition(
        modelo_dir,
        "2025",
        year=2025,
        predecessor="2024",
        casillas=edition_casilla("2025", "0004", number="4", lineage="recargo-nuevo"),
        retire=("deduccion-retirada", retire_from),
    )
    return modelo_dir

"""On-disk modelo trees for the edition staging tests: a full first edition and delta editions after it."""

from __future__ import annotations

from pathlib import Path

from cadrumo.domain.calculations.registry.tests.authored_editions import filing_year_envelope

LEGAL_REF = "ley-58-2003:art-29"


THIRD_EDITION_YEAR = filing_year_envelope().horizon
"""The exercise of the newest of the three editions the migrated chain declares: the support horizon."""

SECOND_EDITION_YEAR = THIRD_EDITION_YEAR - 1
FIRST_EDITION_YEAR = THIRD_EDITION_YEAR - 2

FIRST_EDITION = str(FIRST_EDITION_YEAR)
SECOND_EDITION = str(SECOND_EDITION_YEAR)
THIRD_EDITION = str(THIRD_EDITION_YEAR)

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


def migrated_chain(root: Path, *, retire_from: str = SECOND_EDITION) -> Path:
    """The first edition states everything; each later one names its predecessor and states only what changed.

    ``retire_from`` is the ``from_revision`` of the third edition's one retirement record,
    which is the only link the continuity evolution chain offers out of the third edition.
    """
    modelo_dir = staged_modelo(root)
    write_edition(
        modelo_dir,
        FIRST_EDITION,
        year=FIRST_EDITION_YEAR,
        casillas=(
            edition_casilla(FIRST_EDITION, "0001", number="1", lineage="base-imponible")
            + edition_casilla(FIRST_EDITION, "0002", number="2", lineage="cuota-integra")
            + edition_casilla(FIRST_EDITION, "0003", number="3", lineage="deduccion-retirada")
        ),
    )
    write_edition(
        modelo_dir,
        SECOND_EDITION,
        year=SECOND_EDITION_YEAR,
        predecessor=FIRST_EDITION,
        casillas=edition_casilla(SECOND_EDITION, "0002", number="22", lineage="cuota-integra"),
    )
    write_edition(
        modelo_dir,
        THIRD_EDITION,
        year=THIRD_EDITION_YEAR,
        predecessor=SECOND_EDITION,
        casillas=edition_casilla(THIRD_EDITION, "0004", number="4", lineage="recargo-nuevo"),
        retire=("deduccion-retirada", retire_from),
    )
    return modelo_dir

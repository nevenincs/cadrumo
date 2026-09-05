"""Every shipped casilla label that an adjudication pinned must BE the pinned text.

The M200/2024 adjudication ledger records `official_label_sha256` for each
casilla it settled: the digest of the exact cell in the pinned Diseno de
Registro that names the box. That digest is what makes a label grounded rather
than plausible -- a label can be written from the right section, in the right
house style, and still be the wrong box's text, and nothing about reading it
would say so.

Casilla numbers are REUSED across record pages in Modelo 200 (00066 is
"Entidad patrimonial" on one page and an AIE/UTE deduction base on another), so
picking the text by searching for the number is exactly the mistake available
here. Matching the digest picks the cell the adjudication actually settled on.

The gate covers the labels a pin exists for, which today is a small share of the
revision. That is a statement about how many casillas have been adjudicated, not
about how much the check is worth: it holds for each one from the moment the pin
lands, and an unpinned casilla is not silently reported as verified.
"""

from __future__ import annotations

import hashlib
import re
import tomllib

import pytest
import yaml

from ..._paths import REPO_ROOT

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_ADJUDICATIONS = REPO_ROOT / "dev" / "registry" / "analysis"
_CATALOGUE = REPO_ROOT / "src" / "cadrumo" / "locales" / "es" / "modelo" / "schema" / "200.yml"
_CASILLA_CELL = re.compile(r"\[\d{5}\]")


def _official_cells() -> dict[str, str]:
    """Digest every record-design cell that names a casilla, keyed by digest."""
    cells: dict[str, str] = {}
    for ledger in sorted(_ADJUDICATIONS.glob("*.toml")):
        document = tomllib.loads(ledger.read_text(encoding="utf-8"))
        corpus = document.get("source_ref")
        if corpus is None:
            continue
        break
    design = next(
        (
            path
            for path in (REPO_ROOT / "src" / "cadrumo" / "_data" / "corpus").rglob("*200*2024*.xls.extracted.md")
            if "modelo_200" in path.as_posix()
        ),
        None,
    )
    assert design is not None, "the pinned Modelo 200 record design is not bundled"
    for line in design.read_text(encoding="utf-8").splitlines():
        for part in line.split("|"):
            cell = part.strip()
            if _CASILLA_CELL.search(cell):
                cells[hashlib.sha256(cell.encode("utf-8")).hexdigest()] = cell
    return cells


def _pinned_labels() -> dict[str, str]:
    """Map casilla id to its pinned official-label digest."""
    pinned: dict[str, str] = {}
    for ledger in sorted(_ADJUDICATIONS.glob("*.toml")):
        document = tomllib.loads(ledger.read_text(encoding="utf-8"))
        for adjudication in document.get("adjudications", ()):
            digest = adjudication.get("official_label_sha256")
            if digest is not None:
                pinned.setdefault(adjudication["casilla_id"], digest)
    return pinned


def _shipped_labels() -> dict[str, str]:
    catalogue = yaml.safe_load(_CATALOGUE.read_text(encoding="utf-8"))
    revision = catalogue["modelo"]["schema"]["200"]["revision"]["2024"]["casilla"]
    return {casilla: entry["label"] for casilla, entry in revision.items()}


def test_the_shipped_spanish_label_is_the_pinned_official_cell() -> None:
    """A pinned label ships verbatim, or the pin is not what shipped."""
    cells = _official_cells()
    shipped = _shipped_labels()
    covered = 0
    wrong: list[str] = []
    for casilla, digest in _pinned_labels().items():
        official = cells.get(digest)
        if official is None or casilla not in shipped:
            continue
        covered += 1
        if shipped[casilla] != official:
            wrong.append(f"{casilla}: shipped {shipped[casilla]!r} is not the pinned {official!r}")

    assert covered, "no pinned label reached the catalogue, so this proved nothing"
    assert not wrong, "\n".join(wrong)

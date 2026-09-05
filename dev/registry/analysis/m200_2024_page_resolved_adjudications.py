"""Compile the M200/2024 cohort resolved by the page its own identifier names.

A record-qualified casilla carries its page in its identifier: ``DP200013:00417``
IS casilla 00417 on page DP200013. The bundled Diseno de Registro is segmented
by page headers, so that number resolves to exactly one cell and no adjudication
is needed to choose among its occurrences -- which is the job the other cohorts'
pins were doing.

What a pin also does, less obviously, is corroborate. Casilla 00067 carried a
declaration naming a part of the form its own cited design does not put that
number in, and only the digest exposed it. So this compiler refuses a member
whose declared ``section`` does not appear in the resolved cell's own path: a
label written against a contradicted section is the wrong-box error the pins
exist to prevent.

The TOML beside this module is a RECEIPT, not the authority. Every digest is
re-derived from the bundled design at compile time and compared against the
recorded one, so a hand-edited value fails rather than being believed.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path

import rtoml

from cadrumo.core.hashing import sha256_hex
from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.errors import RegistryValidationError

ADJUDICATION_PATH = Path(__file__).with_suffix(".toml")
TARGET_SOURCE_REF = "aeat-dr-200-2024"
TARGET_SOURCE_SHA256 = "ed4df89a451abc2184bc60a1d13ff53a3d38e9a6201698fb635cf0b8ee455218"
_DESIGN_RELATIVE = (
    "corpus/aeat_official/disenos_registro/modelo_200/files/"
    "16-200-ejercicio-2024-actualizado-13-10-2025-10-7-mb-xls.xls.extracted.md"
)
_PAGE_HEADER = re.compile(r"^#\s+(DP\w+)\s*$")
_TRAILING_CASILLA = re.compile(r"\[(\d{5})\]$")
_SEGMENT = re.compile(r" - |: ")


@dataclass(frozen=True, slots=True)
class Adjudication:
    """One page-resolved declaration receipt row."""

    casilla_id: str
    official_label: str
    official_label_sha256: str


@dataclass(frozen=True, slots=True)
class CompiledM200PageResolvedAuthority:
    """The immutable receipt for the page-resolved cohort."""

    reviewed_by: str
    reviewed_at: str
    adjudications: tuple[Adjudication, ...]


def _slug(text: str) -> str:
    folded = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-zA-Z0-9]+", "_", folded).strip("_").lower()[:49]


def _design_cells() -> dict[tuple[str, str], set[str]]:
    """Map (page, casilla number) to the labelled cells on that page."""
    design = bundled_path(_DESIGN_RELATIVE)
    cells: dict[tuple[str, str], set[str]] = {}
    page: str | None = None
    for line in design.read_text(encoding="utf-8").splitlines():
        header = _PAGE_HEADER.match(line.strip())
        if header is not None:
            page = header.group(1).upper()
            continue
        if page is None:
            continue
        for part in line.split("|"):
            cell = part.strip()
            match = _TRAILING_CASILLA.search(cell)
            if match is not None:
                cells.setdefault((page, match.group(1)), set()).add(re.sub(r"\s+", " ", cell).strip())
    return cells


def _declared_sections() -> dict[str, tuple[str, ...]]:
    sections: dict[str, tuple[str, ...]] = {}
    root = bundled_path("registry", "aeat", "modelos", "200", "revisions", "2024", "casillas")
    for path in sorted(root.glob("*.toml")):
        document = rtoml.loads(path.read_text(encoding="utf-8"))
        for casilla in document.get("revisions", {}).get("2024", {}).get("casillas", ()):
            sections[str(casilla["id"])] = tuple(str(part) for part in casilla.get("section", ()))
    return sections


def _resolve(casilla_id: str, cells: dict[tuple[str, str], set[str]]) -> str:
    if ":" not in casilla_id:
        raise RegistryValidationError(f"M200/2024 page-resolved {casilla_id!r} carries no record page")
    page, number = casilla_id.split(":", 1)
    candidates = cells.get((page.upper(), number), set())
    if len(candidates) != 1:
        raise RegistryValidationError(
            f"M200/2024 page-resolved {casilla_id!r} does not name exactly one cell on its own page"
        )
    return next(iter(candidates))


def _require_section_corroboration(casilla_id: str, label: str, declared: tuple[str, ...]) -> None:
    if not declared:
        raise RegistryValidationError(f"M200/2024 page-resolved {casilla_id!r} declares no section to corroborate")
    path = [_slug(part) for part in _SEGMENT.split(label.split("[")[0].strip()) if part.strip()]
    for part in (segment.lower() for segment in declared):
        if not any(step.startswith(part[:24]) or part.startswith(step[:24]) for step in path):
            raise RegistryValidationError(
                f"M200/2024 page-resolved {casilla_id!r} declares a section its own design cell contradicts"
            )


def compile_m200_2024_page_resolved_authority(
    path: Path = ADJUDICATION_PATH,
) -> CompiledM200PageResolvedAuthority:
    """Compile the page-resolved cohort, re-deriving every digest from the design."""
    raw = rtoml.loads(path.read_text(encoding="utf-8"))
    if (
        str(raw.get("modelo")) != "200"
        or str(raw.get("revision")) != "2024"
        or str(raw.get("source_ref")) != TARGET_SOURCE_REF
        or str(raw.get("source_sha256")) != TARGET_SOURCE_SHA256
    ):
        raise RegistryValidationError("M200/2024 page-resolved adjudication header is not target-authoritative")

    cells = _design_cells()
    sections = _declared_sections()
    rows: list[Adjudication] = []
    seen: set[str] = set()
    for entry in raw.get("adjudications", ()):
        if not isinstance(entry, dict):
            raise RegistryValidationError("M200/2024 page-resolved adjudication entry is malformed")
        casilla_id = str(entry["casilla_id"])
        if casilla_id in seen:
            raise RegistryValidationError(f"M200/2024 page-resolved {casilla_id!r} is adjudicated twice")
        seen.add(casilla_id)
        if casilla_id not in sections:
            raise RegistryValidationError(f"M200/2024 page-resolved {casilla_id!r} declares no casilla")
        label = _resolve(casilla_id, cells)
        _require_section_corroboration(casilla_id, label, sections[casilla_id])
        digest = sha256_hex(label.encode("utf-8"))
        if digest != str(entry["official_label_sha256"]):
            raise RegistryValidationError(f"M200/2024 page-resolved {casilla_id!r} official label drifted")
        rows.append(Adjudication(casilla_id, label, digest))

    if not rows:
        raise RegistryValidationError("M200/2024 page-resolved cohort is empty")
    return CompiledM200PageResolvedAuthority(
        str(raw["reviewed_by"]),
        str(raw["reviewed_at"]),
        tuple(sorted(rows, key=lambda row: row.casilla_id)),
    )


__all__ = [
    "ADJUDICATION_PATH",
    "Adjudication",
    "CompiledM200PageResolvedAuthority",
    "compile_m200_2024_page_resolved_authority",
]

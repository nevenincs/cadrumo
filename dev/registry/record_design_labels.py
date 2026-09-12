"""Read an AEAT record design's own field labels out of its extracted sidecar.

A fixed-width binding names a slot. Where the ingested corpus recorded no name
for a slot and fell back to its byte offset -- modelo 714's asset blocks spell
``...inst-invers-290`` for the field at offset 290 -- the name is not missing
from the world, only from the corpus: the official diseno de registro states it
in the ``Descripcion`` column of the row at that position, together with the
repetition ordinal that tells one member of a repeated block from another
(``... - No Valores 3``).

This module reads that column. It is deliberately a READER and not an importer:
it returns what the design states at a ``(record, offset)`` address, and the
caller decides whether the design proves the row it is about to rename. The
proof is the caller's, not this module's, because a label alone is not identity
-- a design row whose declared length disagrees with the binding's provider is
a different field at the same address and must not lend it a name.

Provenance. The sidecar consulted for an edition is the one the registry itself
cites: the edition's ``source_refs`` name a ``record_design`` source, that
source declares a ``corpus_path`` and a ``sha256``, and the binary is hashed
before its sidecar is read. A sidecar beside a binary whose content has moved
is refused rather than trusted, so a label can never outlive the design that
stated it.
"""

from __future__ import annotations

import hashlib
import re
import tomllib
import unicodedata
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_ROOT = REPO_ROOT / "src" / "cadrumo" / "_data"
LEGAL_ROOT = DATA_ROOT / "registry" / "aeat" / "legal"
MODELOS_ROOT = DATA_ROOT / "registry" / "aeat" / "modelos"

#: The sidecars are written in Latin-1. This is not a guess to be widened to a
#: tolerant decode: a mis-decoded ``Descripcion`` yields a WRONG slot name that
#: still looks plausible, so the encoding is stated once and a file that does
#: not decode under it is an error the caller sees.
_SIDECAR_ENCODING = "latin-1"

_RECORD_HEADING = re.compile(r"^# (?P<record>\S+)")

#: The design source families whose sidecars carry a positional field table.
_RECORD_DESIGN_KIND = "record_design"


class RecordDesignUnavailableError(Exception):
    """The design an edition cites cannot be read, so no row may borrow a name from it."""


@dataclass(frozen=True)
class RecordDesignRow:
    """One row of an official record design: an address, a width, and the field's own label."""

    record: str
    offset: int
    length: int | None
    label: str


def read_record_design(sidecar: Path) -> dict[tuple[str, int], RecordDesignRow]:
    """Return one extracted sidecar's rows, keyed by ``(record, offset)``.

    The sidecar renders each record as a ``#`` heading followed by a pipe table
    whose header names its own columns. The column POSITIONS are read from that
    header rather than assumed, because the corpus is not uniform: modelo 714's
    ``714-00`` table has no ``Comp`` column while ``714-05`` does, and a fixed
    index would silently read the width column as the label in one of them.

    The first row at an address wins. A design that restates an address is
    stating the same field twice in a rendered table, not declaring two fields,
    and taking the later row would let a footnote overwrite a declaration.
    """
    rows: dict[tuple[str, int], RecordDesignRow] = {}
    record: str | None = None
    columns: dict[str, int] | None = None
    for line in sidecar.read_text(encoding=_SIDECAR_ENCODING).splitlines():
        heading = _RECORD_HEADING.match(line)
        if heading is not None:
            record, columns = heading.group("record"), None
            continue
        if record is None:
            continue
        cells = [cell.strip() for cell in line.split("|")]
        if len(cells) < 4:
            continue
        normalised = [cell.lower().rstrip(".") for cell in cells]
        if normalised[1].startswith("posic"):
            columns = {name: index for index, name in enumerate(normalised)}
            continue
        if columns is None:
            continue
        offset = _cell_int(cells, columns.get("posic"))
        label_index = next((index for name, index in columns.items() if name.startswith("descripci")), None)
        if offset is None or label_index is None or label_index >= len(cells):
            continue
        length_index = next((index for name, index in columns.items() if name.startswith("lon")), None)
        rows.setdefault(
            (record, offset),
            RecordDesignRow(
                record=record,
                offset=offset,
                length=_cell_int(cells, length_index),
                label=cells[label_index],
            ),
        )
    return rows


def _cell_int(cells: list[str], index: int | None) -> int | None:
    """Return one cell parsed as an integer, or ``None`` when it is absent or not a number."""
    if index is None or index >= len(cells):
        return None
    try:
        return int(cells[index])
    except ValueError:
        return None


def design_slot_name(label: str) -> str:
    """Return the identifier slot a design label states.

    The label is the field's own name in the official design, so the transform
    is a spelling change and nothing more: the leading rendered marker
    (``(1) ``) is dropped, ``No``/``a`` ordinal marks and ``%`` are written out
    rather than deleted -- ``% Titularidad 7`` must not become ``titularidad-7``
    beside a ``Titularidad 7`` that means something else -- accents are folded,
    and every remaining run of non-alphanumerics becomes one separator. The
    trailing ordinal the design writes for a repeated block survives, because it
    is what distinguishes the third holding from the fourth.
    """
    text = re.sub(r"^\(\d+\)\s*", "", label)
    text = text.replace("º", "o").replace("ª", "a").replace("%", " porcentaje ")
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^A-Za-z0-9]+", "-", text).strip("-").lower()
    return re.sub(r"-+", "-", text)


def _legal_sources() -> dict[str, dict[str, object]]:
    """Return every declared source across the legal-domain tables, keyed by source id."""
    sources: dict[str, dict[str, object]] = {}
    for path in sorted(LEGAL_ROOT.glob("*.toml")):
        with path.open("rb") as handle:
            declared = tomllib.load(handle).get("sources")
        if isinstance(declared, dict):
            for source_id, table in declared.items():
                if isinstance(table, dict):
                    sources.setdefault(str(source_id), table)
    return sources


def _sidecar_for(source_id: str, source: Mapping[str, object]) -> Path:
    """Return the extracted sidecar beside a design source, after hashing the binary it describes.

    The hash is the point. The sidecar is derived text sitting beside a binary,
    and nothing else ties the two together; checking the binary against the
    ``sha256`` the registry declares is what makes a label read from the sidecar
    a statement about the design the edition actually cites.
    """
    corpus_path = source.get("corpus_path")
    declared_hash = source.get("sha256")
    if not isinstance(corpus_path, str) or not isinstance(declared_hash, str):
        raise RecordDesignUnavailableError(f"source {source_id!r} declares no corpus_path and sha256 pair")
    binary = DATA_ROOT / corpus_path
    if not binary.is_file():
        raise RecordDesignUnavailableError(f"source {source_id!r}: {corpus_path} is not present in this repository")
    actual = hashlib.sha256(binary.read_bytes()).hexdigest()
    if actual != declared_hash:
        raise RecordDesignUnavailableError(
            f"source {source_id!r}: {corpus_path} hashes {actual}, but the registry declares {declared_hash}; "
            "the sidecar beside it describes a different file and its labels are not this design's"
        )
    sidecar = binary.with_name(binary.name + ".extracted.md")
    if not sidecar.is_file():
        raise RecordDesignUnavailableError(f"source {source_id!r}: {corpus_path} has no .extracted.md sidecar")
    return sidecar


def edition_record_designs(
    modelo: str,
    modelos_root: Path = MODELOS_ROOT,
) -> dict[str, dict[tuple[str, int], RecordDesignRow]]:
    """Return each edition's record-design rows, resolved through the registry's own citations.

    The chain is the registry's, not this module's: an edition's
    ``revision.toml`` names its ``source_refs``, a legal table declares which of
    those is a ``record_design`` and where its file sits, and the file is hashed
    before its sidecar is read. An edition citing no readable design is simply
    absent from the result, and the caller treats its rows as needing design
    evidence rather than naming them from somewhere else.
    """
    sources = _legal_sources()
    designs: dict[str, dict[tuple[str, int], RecordDesignRow]] = {}
    revisions_dir = modelos_root / modelo / "revisions"
    if not revisions_dir.is_dir():
        return designs
    for revision_dir in sorted(path for path in revisions_dir.iterdir() if path.is_dir()):
        manifest = revision_dir / "revision.toml"
        if not manifest.is_file():
            continue
        with manifest.open("rb") as handle:
            table = tomllib.load(handle).get("revisions", {}).get(revision_dir.name, {})
        refs = table.get("source_refs") if isinstance(table, dict) else None
        for ref in refs if isinstance(refs, list) else ():
            source = sources.get(str(ref))
            if not isinstance(source, dict) or source.get("kind") != _RECORD_DESIGN_KIND:
                continue
            designs[revision_dir.name] = read_record_design(_sidecar_for(str(ref), source))
            break
    return designs

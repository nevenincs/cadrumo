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

import re
import unicodedata
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from cadrumo.core.hashing import sha256_file
from cadrumo.core.toml import load_toml
from cadrumo.domain.calculations.registry.schema_references import SourceReference

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_ROOT = REPO_ROOT / "src" / "cadrumo" / "_data"
LEGAL_ROOT = DATA_ROOT / "registry" / "aeat" / "legal"
MODELOS_ROOT = DATA_ROOT / "registry" / "aeat" / "modelos"

#: The sidecars are written in UTF-8, and the decode is deliberately strict.
#: A tolerant decode does not fail on a mis-read sidecar, it yields a WRONG slot
#: name that still looks plausible -- reading these files as Latin-1 turns
#: ``Nº Valores 3`` into ``nao-valores-3`` without raising anything. So the
#: encoding is stated once, errors are not suppressed, and a file that does not
#: decode under it is an error the caller sees.
_SIDECAR_ENCODING = "utf-8"

#: A record heading names the whole record: ``# DP30301`` and ``# Pág. 2 bis``
#: alike. Reading only the first word would fold every ``Pág. N`` record of a
#: design into one key ``Pág.``, so later pages would borrow the first page's
#: labels at the same offset.
_RECORD_HEADING = re.compile(r"^# (?P<record>\S.*?)\s*$")

#: The design source families whose sidecars carry a positional field table.
_RECORD_DESIGN_KIND = "record_design"


class RecordDesignUnavailableError(Exception):
    """The design an edition cites cannot be read, so no row may borrow a name from it."""


@dataclass(frozen=True)
class RecordDesignRow:
    """One row of an official record design: its ordinal, address, width, and the field's own label."""

    record: str
    offset: int
    length: int | None
    label: str
    #: The design's own row number, from the leading column of that record's
    #: field table. It is the design's second way of identifying a row, used
    #: where the label does not single one out, and it is a statement the design
    #: makes rather than a property of the wire format.
    ordinal: int | None = None


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
        record, columns, cells = _record_design_table_cells(line, record, columns)
        if cells is None or record is None or columns is None:
            continue
        row = _record_design_row(record, columns, cells)
        if row is None:
            continue
        rows.setdefault((row.record, row.offset), row)
    return rows


def _record_design_table_cells(
    line: str,
    record: str | None,
    columns: dict[str, int] | None,
) -> tuple[str | None, dict[str, int] | None, list[str] | None]:
    heading = _RECORD_HEADING.match(line)
    if heading is not None:
        return str(heading.group("record")), None, None
    if record is None:
        return record, columns, None
    cells = [cell.strip() for cell in line.split("|")]
    if len(cells) < 4:
        return record, columns, None
    normalised = [cell.lower().rstrip(".") for cell in cells]
    if normalised[1].startswith("posic"):
        return record, {name: index for index, name in enumerate(normalised)}, None
    if columns is None:
        return record, columns, None
    return record, columns, cells


def _record_design_row(
    record: str,
    columns: Mapping[str, int],
    cells: list[str],
) -> RecordDesignRow | None:
    offset = _cell_int(cells, columns.get("posic"))
    label_index = next((index for name, index in columns.items() if name.startswith("descripci")), None)
    if offset is None or label_index is None or label_index >= len(cells):
        return None
    length_index = next((index for name, index in columns.items() if name.startswith("lon")), None)
    return RecordDesignRow(
        record=record,
        offset=offset,
        length=_cell_int(cells, length_index),
        label=cells[label_index],
        ordinal=_cell_int(cells, 0),
    )


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


def design_field_component(label: str) -> str:
    """Return the slot name for the LAST component of a design label.

    An AEAT label states a path: the apartado, the block, the block's full
    description, and finally the field itself with its repetition ordinal --
    ``... - Acciones y particip. Inst. Invers. Colectiva negociadas - No Valores 3``.
    Everything before the final component is the BLOCK, which the corpus id
    already carries in its own (abbreviated) spelling; repeating it in full
    pushes the identifier past the schema's length limit without adding a
    distinction. So only the final component is taken, and it is the part that
    actually separates one slot of a block from another.

    The separator is a dash surrounded by whitespace on at least the right,
    because the corpus contains ``negociadas- Valor 3`` as well as
    ``negociadas - Valor 3``, while a dash inside a word (``NIF/NIE``) or a
    hyphenated term must not split the component.
    """
    parts = re.split(r"\s-\s+|\s-(?=\S)|(?<=\S)-\s+", label)
    return design_slot_name(parts[-1] if parts else label)


def design_field_text(label: str) -> str:
    """Return the design's OWN words for the final component of a label.

    :func:`design_field_component` slugifies the same span for use in an
    identifier. This returns it unchanged -- accents, ordinal marks and the
    per-cent sign intact -- for prose a human reads, where the design's exact
    wording is the evidence and a slug is a paraphrase of it.
    """
    parts = re.split(r"\s-\s+|\s-(?=\S)|(?<=\S)-\s+", label)
    return str(parts[-1] if parts else label).strip()


def _legal_sources() -> dict[str, dict[str, object]]:
    """Return every declared source across the legal-domain tables, keyed by source id."""
    sources: dict[str, dict[str, object]] = {}
    for path in sorted(LEGAL_ROOT.glob("*.toml")):
        with path.open("rb") as handle:
            declared = load_toml(handle).get("sources")
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
    actual = sha256_file(binary)
    if actual != declared_hash:
        raise RecordDesignUnavailableError(
            f"source {source_id!r}: {corpus_path} hashes {actual}, but the registry declares {declared_hash}; "
            "the sidecar beside it describes a different file and its labels are not this design's"
        )
    sidecar = binary.with_name(binary.name + ".extracted.md")
    if not sidecar.is_file():
        raise RecordDesignUnavailableError(f"source {source_id!r}: {corpus_path} has no .extracted.md sidecar")
    return sidecar


def record_design_sidecars(
    source_refs: Sequence[str],
    sources: Mapping[str, SourceReference],
) -> tuple[tuple[str, Path], ...]:
    """Return the extracted sidecar of every ``record_design`` source among ``source_refs``, in citation order.

    ``sources`` is the compiled source catalogue, so a caller already holding an
    edition's typed citations reads the same provenance chain as
    :func:`edition_record_designs` without re-reading raw manifests. Each binary
    is hashed against its declared ``sha256`` before its sidecar is returned.

    Raises:
        RecordDesignUnavailableError: When a cited design cannot be read or does
            not hash to the declared value.
    """
    sidecars: list[tuple[str, Path]] = []
    for ref in source_refs:
        source = sources.get(str(ref))
        if source is None or str(source.kind) != _RECORD_DESIGN_KIND:
            continue
        sidecars.append(
            (str(ref), _sidecar_for(str(ref), {"corpus_path": source.corpus_path, "sha256": source.sha256}))
        )
    return tuple(sidecars)


def record_design_source_ref(
    modelo: str,
    edition: str,
    modelos_root: Path = MODELOS_ROOT,
) -> str:
    """Return the ``record_design`` source id one edition cites, read from the registry.

    Provenance is READ, never spelled. The corpus does not name design sources
    to one pattern -- ``aeat-dr-714-2021`` sits beside ``aeat-dr-111-2019-v18``
    -- so constructing the id from the modelo and the year produces a citation
    that happens to be right for some modelos and silently wrong for others. The
    edition already states which source it means; this returns that.

    Raises:
        RecordDesignUnavailableError: When the edition cites no readable
            ``record_design`` source. A statement that cites nothing is not a
            statement, so the caller refuses rather than inventing one.
    """
    sources = _legal_sources()
    manifest = modelos_root / modelo / "revisions" / edition / "revision.toml"
    if manifest.is_file():
        with manifest.open("rb") as handle:
            table = load_toml(handle).get("revisions", {}).get(edition, {})
        refs = table.get("source_refs") if isinstance(table, dict) else None
        for ref in refs if isinstance(refs, list) else ():
            source = sources.get(str(ref))
            if isinstance(source, dict) and source.get("kind") == _RECORD_DESIGN_KIND:
                return str(ref)
    raise RecordDesignUnavailableError(
        f"modelo {modelo} {edition} cites no record_design source, so a statement about its record "
        "design has nothing to cite; refusing to name one from a pattern"
    )


def edition_record_designs(
    modelo: str,
    modelos_root: Path = MODELOS_ROOT,
    editions: Sequence[str] | None = None,
) -> dict[str, dict[tuple[str, int], RecordDesignRow]]:
    """Return each edition's record-design rows, resolved through the registry's own citations.

    The chain is the registry's, not this module's: an edition's
    ``revision.toml`` names its ``source_refs``, a legal table declares which of
    those is a ``record_design`` and where its file sits, and the file is hashed
    before its sidecar is read. An edition citing no ``record_design`` source at
    all is simply absent from the result.

    An edition citing one that cannot be TRUSTED is different, and fails closed:
    a missing file, a missing sidecar, or a binary whose hash no longer matches
    the registry's declaration raises rather than returning a partial map. A
    silently absent edition there would read as "this edition has no design",
    which is the one thing the caller must not conclude from a broken link.

    Raises:
        RecordDesignUnavailableError: When a cited design cannot be read or does
            not hash to the declared value.
    """
    sources = _legal_sources()
    designs: dict[str, dict[tuple[str, int], RecordDesignRow]] = {}
    revisions_dir = modelos_root / modelo / "revisions"
    for revision_dir in _selected_revision_directories(revisions_dir, editions):
        design = _record_design_for_revision(revision_dir, sources)
        if design is not None:
            designs[revision_dir.name] = design
    return designs


def _selected_revision_directories(revisions_dir: Path, editions: Sequence[str] | None) -> tuple[Path, ...]:
    if not revisions_dir.is_dir():
        return ()
    return tuple(
        sorted(
            path for path in revisions_dir.iterdir() if path.is_dir() and (editions is None or path.name in editions)
        )
    )


def _record_design_for_revision(
    revision_dir: Path,
    sources: Mapping[str, dict[str, object]],
) -> dict[tuple[str, int], RecordDesignRow] | None:
    manifest = revision_dir / "revision.toml"
    if not manifest.is_file():
        return None
    refs = _revision_source_references(manifest, revision_dir.name)
    for ref in refs:
        source = sources.get(str(ref))
        if not isinstance(source, dict) or source.get("kind") != _RECORD_DESIGN_KIND:
            continue
        return read_record_design(_sidecar_for(str(ref), source))
    return None


def _revision_source_references(manifest: Path, revision: str) -> Sequence[object]:
    with manifest.open("rb") as handle:
        table = load_toml(handle).get("revisions", {}).get(revision, {})
    refs = table.get("source_refs") if isinstance(table, dict) else None
    return refs if isinstance(refs, list) else ()

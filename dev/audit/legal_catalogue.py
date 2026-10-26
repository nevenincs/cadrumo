"""Read the legal catalogue's authoring tree, once, for the screens that audit it.

Both legal screens in this package need the same thing: every catalogue entry
id mapped to its authored body. Each had grown its own copy of the walk -- the
same directory constant, the same byte-identical refusal, the same
glob-to-``rtoml``-to-``legal`` traversal -- and the copies had already
diverged in what they returned, one projecting ``required_text`` and one
carrying the whole body. The wider read is the one that generalises, so it is
the one that lives here and the narrower consumer projects what it needs.

READ RAW, deliberately, rather than through the registry authority. These are
screens OVER the authoring tree, and the shipped loader is a validating
compiler: it is entitled to refuse an entry, and a reader that refuses the data
under audit reports nothing about it. The authority remains the only production
path to catalogue data; this is an audit instrument's view of the same files.

The refusal on a missing directory is not defensive noise. An empty read would
let every screen in this package print a clean worklist, and a silent all-clear
is the one output an audit instrument must never emit.
"""

from __future__ import annotations

from pathlib import Path
from typing import Final

from pydantic import ValidationError

from cadrumo.core.directory_scan import scan_directory
from cadrumo.core.toml import freeze_toml, parse_toml
from cadrumo.domain.calculations.registry.schema import RegistryCatalogues
from cadrumo.domain.calculations.registry.schema_references import SourceReference
from dev._paths import UTF_8
from dev.registry.compiler.loader_materialisation import validate_catalogue_section
from dev.registry.compiler.runtime_catalogues import published_recargo_bands

#: Sourced from ``dev._paths`` so the dev harness has one owner for it. The
#: directory walk is imported from its canonical defining module above.
_UTF_8: Final[str] = UTF_8

#: The catalogue's authoring tree, relative to the repository root.
LEGAL_DIR: Final = Path("src/cadrumo/_data/registry/aeat/legal")


def load_legal_entries(root: Path) -> dict[str, dict[str, object]]:
    """Return every legal catalogue entry id mapped to its authored TOML body.

    Args:
        root: The repository root the catalogue is read beneath.

    Returns:
        Entry id mapped to its authored table, accumulated in filename order so
        duplicate entry ids refuse instead of silently replacing evidence.

    Raises:
        SystemExit: The catalogue directory is absent.
    """
    legal_dir = root / LEGAL_DIR
    if not legal_dir.is_dir():
        raise SystemExit(f"legal catalogue is missing, so the result would be meaningless: {legal_dir}")
    entries: dict[str, dict[str, object]] = {}
    for path in scan_directory(legal_dir, pattern="*.toml"):
        data = parse_toml(path.read_text(encoding=_UTF_8))
        unknown = set(data) - RegistryCatalogues.model_fields.keys() - {"band"}
        if unknown or not data:
            raise SystemExit(f"{path}: unrecognized or empty catalogue declarations: {sorted(unknown)}")
        if "band" in data:
            published_recargo_bands(data)
        metadata = {key: value for key, value in data.items() if key not in {"legal", "band"}}
        if "sources" in metadata:
            raw_sources = metadata["sources"]
            if not isinstance(raw_sources, dict) or not raw_sources:
                raise SystemExit(f"{path}: source declarations must be a non-empty table")
            metadata["sources"] = validate_catalogue_section(
                path,
                raw=freeze_toml(raw_sources),
                kind="source reference",
                model=SourceReference,
            )
        try:
            RegistryCatalogues.model_validate(freeze_toml({"sources": {}, **metadata, "legal": {}}))
        except ValidationError as exc:
            raise SystemExit(f"{path}: invalid non-legal catalogue declarations: {exc}") from exc
        if "legal" not in data:
            continue
        legal = data["legal"]
        if not isinstance(legal, dict) or not legal:
            raise SystemExit(f"{path}: legal declarations must be a non-empty table")
        for entry_id, body in legal.items():
            if not isinstance(body, dict) or not body:
                raise SystemExit(f"{path}: legal entry {entry_id!r} must be a non-empty table")
            if entry_id in entries:
                raise SystemExit(f"{path}: duplicate legal entry {entry_id!r}")
            entries[entry_id] = body
    if not entries:
        raise SystemExit(f"legal catalogue contains no legal entries: {legal_dir}")
    return entries


def required_text_by_entry(entries: dict[str, dict[str, object]]) -> dict[str, tuple[str, ...]]:
    """Return each entry's declared ``required_text`` phrases, in file order.

    The projection a presence-gate screen needs, taken off the full body rather
    than read by a second walk of the same directory.

    Args:
        entries: Catalogue bodies as :func:`load_legal_entries` returns them.

    Returns:
        Entry id mapped to its phrases; an empty tuple where none are declared
        or the declaration is not a list, which is a catalogue defect the
        registry's own validation owns rather than a screen's.
    """
    projected: dict[str, tuple[str, ...]] = {}
    for entry_id, body in entries.items():
        declared = body.get("required_text")
        projected[entry_id] = tuple(str(phrase) for phrase in declared) if isinstance(declared, list) else ()
    return projected

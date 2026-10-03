"""Read the authored legal catalogue with deterministic ordering and duplicate refusal."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Final, cast

from cadrumo.core.directory_scan import scan_directory
from cadrumo.core.toml import TomlDecodeError, parse_toml
from dev._paths import UTF_8

from .legal_catalogue_fields import _record_from_table, _validate_authored_text
from .legal_reference_models import LegalProvisionRecord, LegalReferenceError

#: The legal catalogue tree, relative to the repository root.  The leading
#: segment is the CADRUMO package root; the trailing ``aeat`` is the authority
#: taxonomy directory (aeat-naming).  This surface owns the constant because
#: the legal catalogue is its source; the glossary reads it for grounding.
LEGAL_CATALOGUE_RELPATH: Final[Path] = Path("src") / "cadrumo" / "_data" / "registry" / "aeat" / "legal"


@lru_cache(maxsize=4)
def load_legal_provisions(repo_root: Path) -> tuple[LegalProvisionRecord, ...]:
    """Load every provision from the legal catalogue, ordered deterministically.

    Only ``[legal."<id>"]`` tables are read.  Other tables in the same TOML
    files, such as ``[sources]``, are intentionally ignored.

    The catalogue is read-only authored data and the records are frozen, so the
    parse is memoised per source root for the process: the glossary, the casilla
    reference, the legal reference and the legal search projection all ground on
    the same rows, and each was re-parsing the whole catalogue for itself. A
    caller reading a DIFFERENT root (a temporary catalogue) keys its own entry.
    """
    catalogue = repo_root / LEGAL_CATALOGUE_RELPATH
    if not catalogue.is_dir():
        raise LegalReferenceError(f"legal catalogue directory does not exist: {catalogue}")

    records: list[LegalProvisionRecord] = []
    seen_ids: dict[str, Path] = {}
    for fragment in scan_directory(catalogue, pattern="*.toml"):
        _read_legal_fragment(fragment, records, seen_ids)

    return tuple(
        sorted(
            records,
            key=lambda record: (
                record.document_id,
                record.article or "",
                record.section or "",
                record.legal_id,
            ),
        ),
    )


def _read_legal_fragment(fragment: Path, records: list[LegalProvisionRecord], seen_ids: dict[str, Path]) -> None:
    try:
        data = cast(dict[str, object], parse_toml(fragment.read_text(encoding=UTF_8)))
    except (OSError, TomlDecodeError) as exc:
        raise LegalReferenceError(f"cannot read legal catalogue fragment {fragment}: {exc}") from exc
    legal = data.get("legal")
    if legal is None:
        return
    if not isinstance(legal, dict):
        raise LegalReferenceError(f"{fragment}: 'legal' must contain provision tables")
    legal_tables = cast(dict[object, object], legal)
    for raw_id, body in legal_tables.items():
        if not isinstance(raw_id, str) or not raw_id.strip():
            raise LegalReferenceError(f"{fragment}: legal provision id must be a non-empty string")
        legal_id = raw_id
        _validate_authored_text(legal_id, path=fragment, legal_id=legal_id, field="legal id")
        previous = seen_ids.get(legal_id)
        if previous is not None:
            raise LegalReferenceError(
                f"duplicate legal provision id {legal_id!r} in {fragment} and {previous}; refusing to merge authority",
            )
        seen_ids[legal_id] = fragment
        records.append(_record_from_table(fragment, legal_id, body))

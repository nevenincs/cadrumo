"""BOE/AEAT corpus-catalogue integrity helpers.

Verifies each :class:`SourceReference` in a registry source catalogue against
the bundled corpus filesystem: that the cited corpus file exists, stays within
the repository root, and matches the recorded byte count and SHA-256. The
``source`` here is a corpus file (a BOE/AEAT consolidated text or AEAT manual),
not a binding ``BindingSourceKind``; this module is the corpus-catalogue
verifier, not a registry binding family.

Large corpus binaries live in the two mandatory ``cadrumo-data-*`` runtime
dependencies and resolve through the shared ``cadrumo_data`` namespace. A
missing binary therefore means the installed product cohort is incomplete or
corrupt and fails the same byte-integrity gate as any other missing source.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from ....core.hashing import hash_file
from ....core.resources import resolve_companion_binary
from ._errors import RegistryValidationError
from ._schema import SourceReference


def verify_source_file(root: Path, source: SourceReference) -> None:
    """Verify one source reference against the local repository filesystem.

    A source may resolve from the command-bearing package tree or either
    mandatory data-companion namespace portion. Missing, mismatched, or
    escaping paths raise :class:`RegistryValidationError`; there is no
    partially installed degradation mode.
    """
    repo_root = root.resolve()
    path = _resolve_corpus_path(repo_root, source)
    if repo_root not in path.parents and path != repo_root:
        raise RegistryValidationError(f"source {source.id!r} escapes repository root")

    if path.is_file():
        present_path = path
        _verify_manual_structure(repo_root, source)
    else:
        companion_path = resolve_companion_binary(*source.corpus_path.split("/"))
        if companion_path is None:
            raise RegistryValidationError(f"source {source.id!r} missing corpus file {source.corpus_path!r}")
        present_path = companion_path

    actual_sha256, length = hash_file(present_path)
    if length != source.bytes:
        raise RegistryValidationError(f"source {source.id!r} byte count mismatch")
    if actual_sha256 != source.sha256:
        raise RegistryValidationError(f"source {source.id!r} sha256 mismatch")


def _verify_manual_structure(repo_root: Path, source: SourceReference) -> None:
    """Run the manual-part structure check for a present ``manual_pdf`` source.

    Only meaningful when the manual PDF is present under the source tree (the
    full-checkout / dev path); a companion-resolved manual is proven by its
    byte-exact hash instead.
    """
    if not (source.kind == "manual_pdf" and "corpus/manuals" in source.corpus_path):
        return
    parts = source.corpus_path.split("/")
    try:
        idx = parts.index("manuals")
        if idx >= 0 and idx + 3 < len(parts):
            manual_id_str = parts[idx + 1]
            year_str = parts[idx + 2]
            part_str = parts[idx + 3]

            from ....core.config import Settings
            from ...manuals import ManualId, ManualPart, load_manual

            manual_id = ManualId(manual_id_str)
            year = int(year_str)
            part = ManualPart.SINGLE if part_str == "source.pdf" else ManualPart(part_str)

            manuals_dir = repo_root / "corpus" / "manuals"
            if not manuals_dir.is_dir():
                manuals_dir = repo_root / "src" / "cadrumo" / "_data" / "corpus" / "manuals"

            settings = Settings(aeat_manuals_root=manuals_dir)
            load_manual(manual_id=manual_id, year=year, part=part, settings=settings)
    except Exception as exc:
        raise RegistryValidationError(
            f"source {source.id!r} manual structure check failed for path {source.corpus_path!r}: {exc}",
        ) from exc


def _resolve_corpus_path(root: Path, source: SourceReference) -> Path:
    direct = (root / source.corpus_path).resolve()
    if direct.is_file():
        return direct
    packaged = (root / "src" / "cadrumo" / "_data" / source.corpus_path).resolve()
    if packaged.is_file():
        return packaged
    return direct


def verify_source_catalogue(root: Path, sources: Mapping[str, SourceReference]) -> None:
    """Verify every source reference in a source catalogue mapping.

    Every source is byte-exact hash-enforced. Missing mandatory-companion data
    is an installation-integrity failure, not an advisory path.
    """
    verified: set[tuple[Path, int, str]] = set()
    for source in sources.values():
        key = ((root / source.corpus_path).resolve(), source.bytes, source.sha256)
        if key in verified:
            continue
        verify_source_file(root, source)
        verified.add(key)

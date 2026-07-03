"""BOE/AEAT corpus-catalogue integrity helpers.

Verifies each :class:`SourceReference` in a registry source catalogue against
the bundled corpus filesystem: that the cited corpus file exists, stays within
the repository root, and matches the recorded byte count and SHA-256. The
``source`` here is a corpus file (a BOE/AEAT consolidated text or AEAT manual),
not a binding ``BindingSourceKind``; this module is the corpus-catalogue
verifier, not a registry binding family.

The corpus SOURCE BINARIES (``.pdf`` / ``.xls`` / ``.xlsx`` under ``corpus/``)
are excluded from the slim ``aeat`` runtime wheel and shipped in an optional
``aeat_data`` companion distribution. The gate is companion-aware: a binary that
is PRESENT (in the runtime tree or the companion) stays byte-exact hash-enforced
exactly as before; a companion binary that is ABSENT from both roots yields an
accumulable, loud advisory naming the missing set and the ``aeat-cli[corpus-sources]``
install hint rather than hard-failing — the split-install degradation is loud,
never silent. Every non-binary corpus file (extracted text, normative HTML, XSD)
stays in the runtime wheel, so its absence remains a hard failure as before.
"""

from __future__ import annotations

import warnings
from collections.abc import Mapping
from functools import lru_cache
from pathlib import Path

from ....core.hashing import hash_file
from ....core.resources import resolve_companion_binary
from ._errors import RegistryValidationError
from ._schema import SourceReference

CORPUS_SOURCES_INSTALL_HINT = "pip install 'aeat-cli[corpus-sources]'"
"""Operator install command that adds the optional ``aeat_data`` companion.

Named in every companion-absent advisory so an operator whose split install
lacks the corpus source binaries learns exactly how to restore full
byte-integrity verification and the ``aeat app registry`` verification verbs.
"""

# The slim ``aeat`` wheel excludes ``_data/corpus/**/*.{pdf,xls,xlsx}``; the
# ``aeat_data`` companion carries exactly those binaries. A companion binary is
# therefore classified from catalogue DATA — a corpus-tree file with one of the
# excluded binary extensions — never a hand-maintained per-source list. Every
# other corpus surface (extracted ``.txt``, normative ``.html``, ``.xsd``) stays
# in the runtime wheel.
_COMPANION_CORPUS_PREFIX = "corpus/"
_COMPANION_BINARY_SUFFIXES = (".pdf", ".xls", ".xlsx")


class CorpusCompanionAdvisory(UserWarning):
    """Loud, non-fatal advisory that the ``aeat_data`` companion binaries are absent."""


def is_companion_corpus_binary(source: SourceReference) -> bool:
    """Return whether a source is a corpus binary shipped by the ``aeat_data`` companion.

    Derived from the catalogue entry alone: a ``corpus/...`` file whose
    extension is one the slim ``aeat`` wheel excludes (``.pdf`` / ``.xls`` /
    ``.xlsx``). Extracted-text, normative HTML, and XSD sources stay in the
    runtime wheel and are NOT companion binaries, so their absence stays a hard
    failure.
    """
    path = source.corpus_path
    if not path.startswith(_COMPANION_CORPUS_PREFIX):
        return False
    return path.lower().endswith(_COMPANION_BINARY_SUFFIXES)


def _companion_absent_advisory(source: SourceReference) -> str:
    return (
        f"source {source.id!r} corpus binary {source.corpus_path!r} is absent from the runtime tree "
        f"and the aeat_data companion; install the companion to restore verification: "
        f"{CORPUS_SOURCES_INSTALL_HINT}"
    )


def verify_source_file(root: Path, source: SourceReference) -> str | None:
    """Verify one source reference against the local repository filesystem.

    Returns ``None`` when the cited file is PRESENT (in the source tree or the
    ``aeat_data`` companion) and its byte count and SHA-256 match — the
    byte-exact contract, unchanged. When the file is a companion corpus binary
    (``.pdf`` / ``.xls`` / ``.xlsx`` under ``corpus/``) that is ABSENT from both
    roots, returns an accumulable advisory string instead of raising, so the
    split-install degradation is loud but non-fatal. A mismatched present file,
    a path that escapes the repository root, or an absent NON-companion file
    (extracted text, HTML, XSD) still raises :class:`RegistryValidationError`
    exactly as before.
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
            if is_companion_corpus_binary(source):
                return _companion_absent_advisory(source)
            raise RegistryValidationError(f"source {source.id!r} missing corpus file {source.corpus_path!r}")
        present_path = companion_path

    stat = present_path.stat()
    length, actual_sha256 = _source_file_fingerprint(str(present_path), stat.st_size, stat.st_mtime_ns)
    if length != source.bytes:
        raise RegistryValidationError(f"source {source.id!r} byte count mismatch")
    if actual_sha256 != source.sha256:
        raise RegistryValidationError(f"source {source.id!r} sha256 mismatch")
    return None


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
                manuals_dir = repo_root / "src" / "aeat" / "_data" / "corpus" / "manuals"

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
    packaged = (root / "src" / "aeat" / "_data" / source.corpus_path).resolve()
    if packaged.is_file():
        return packaged
    return direct


@lru_cache(maxsize=2048)
def _source_file_fingerprint(path: str, byte_count: int, modified_ns: int) -> tuple[int, str]:
    del byte_count, modified_ns
    hex_digest, length = hash_file(Path(path))
    return length, hex_digest


def _corpus_companion_advisory(missing_corpus_paths: list[str]) -> str:
    """Build the single loud advisory naming the absent companion set and install hint."""
    unique = sorted(set(missing_corpus_paths))
    missing = ", ".join(unique)
    return (
        f"{len(unique)} corpus source binary file(s) declared by the registry are absent from both "
        f"the runtime tree and the optional aeat_data companion distribution; corpus byte-integrity "
        f"verification and the aeat app registry verification verbs are degraded until it is "
        f"installed. Missing: {missing}. Install the companion to restore full verification: "
        f"{CORPUS_SOURCES_INSTALL_HINT}"
    )


def verify_source_catalogue(root: Path, sources: Mapping[str, SourceReference]) -> tuple[str, ...]:
    """Verify every source reference in a source catalogue mapping.

    Present binaries stay byte-exact hash-enforced (a mismatch or an absent
    non-companion file raises :class:`RegistryValidationError`). Absent companion
    binaries are accumulated into ONE loud advisory naming the missing set and
    the ``aeat-cli[corpus-sources]`` install hint: the advisory is both emitted
    through :class:`CorpusCompanionAdvisory` (so a split-install run surfaces it
    loudly at first registry load) and returned to the caller, so the
    degradation is never silenced. When every declared binary is present the
    return is empty and no advisory is emitted.
    """
    verified: set[tuple[Path, int, str]] = set()
    missing_companion: list[str] = []
    for source in sources.values():
        key = ((root / source.corpus_path).resolve(), source.bytes, source.sha256)
        if key in verified:
            continue
        advisory = verify_source_file(root, source)
        if advisory is not None:
            missing_companion.append(source.corpus_path)
            continue
        verified.add(key)
    if not missing_companion:
        return ()
    message = _corpus_companion_advisory(missing_companion)
    warnings.warn(message, CorpusCompanionAdvisory, stacklevel=2)
    return (message,)

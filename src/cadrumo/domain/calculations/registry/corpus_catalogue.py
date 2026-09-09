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
from typing import Final

from ....core.hashing import hash_file
from ....core.resources.bundled_data import resolve_companion_binary
from .errors import RegistryValidationError
from .legal import _PROVISION_SUFFIXED_FILENAME
from .schema_base import RegistrySourceKind
from .schema_references import SourceReference
from .static_inspection import GeneratedArtifactSource

#: The one corpus tree carrying the excerpt/full-text duality
#: ``SourceReference.corpus_tier`` describes -- the same BOE/AEAT norm-text
#: tree ``LegalReference.corpus_ref`` resolves into. A ``form_spec`` or
#: ``instructions`` source pointing here can legitimately cite the exact file
#: a ``LegalReference`` entry also cites. A design workbook, manual PDF, XSD
#: or data dictionary under ``corpus/aeat_official/`` has no such duality.
_NORMATIVES_TREE_PREFIX: Final = "corpus/normatives/"

#: Calibrated against THIS model's own observed population (measured
#: 2026-08-15, not reused from ``_legal.py``'s ``_FULL_CONSOLIDATED_SIZE_FLOOR``):
#: every non-provision-suffixed ``SourceReference`` under ``corpus/normatives/``
#: is either a landing-page/annex stub topping out at 2308 bytes, or a genuine
#: full consolidated orden/ley/RD text starting at 32119 bytes -- a clean,
#: order-of-magnitude gap with nothing observed in between. 10000 sits in that
#: gap: comfortably above every observed stub, comfortably below every
#: observed full text.
_SOURCE_FULL_CONSOLIDATED_SIZE_FLOOR: Final = 10000


def verify_source_file(root: Path, source: GeneratedArtifactSource) -> Path:
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
    _validate_source_corpus_tier_declaration(source, present_path)
    return present_path


def _validate_source_corpus_tier_declaration(source: GeneratedArtifactSource, path: Path) -> None:
    """Verify a DECLARED ``corpus_tier`` against the bundled file, when present.

    Purely additive: nothing in the committed catalogue declares
    ``corpus_tier`` on a :class:`SourceReference` today, so this can never
    fire against the existing tree. It exists so a FUTURE declaration is
    checked rather than trusted -- verified against the file, never merely
    typed. Mirrors ``_legal.py``'s ``_validate_corpus_tier_declaration`` in
    shape; the size floor and the corpus-tree gate are this model's own,
    per the field's docstring in ``_schema_references.py``.
    """
    if source.corpus_tier is None:
        return
    if not source.corpus_path.startswith(_NORMATIVES_TREE_PREFIX):
        raise RegistryValidationError(
            f"source {source.id!r} declares corpus_tier={source.corpus_tier!r} but corpus_path "
            f"{source.corpus_path!r} is not under {_NORMATIVES_TREE_PREFIX!r} -- the "
            "full_consolidated/provision_excerpt duality only applies to the BOE/AEAT norm-text "
            "tree; a design workbook, manual PDF, XSD or data dictionary has no such duality, so "
            "declaring a tier for one is a claim this check cannot verify and must not accept",
        )
    filename = path.name
    size = path.stat().st_size
    is_provision_suffixed = bool(_PROVISION_SUFFIXED_FILENAME.search(filename))

    if source.corpus_tier == "full_consolidated":
        if is_provision_suffixed or size < _SOURCE_FULL_CONSOLIDATED_SIZE_FLOOR:
            raise RegistryValidationError(
                f"source {source.id!r} declares corpus_tier='full_consolidated' but {filename!r} "
                f"({size} bytes) does not match the observed full-text shape (a bare, "
                f"non-provision-suffixed filename of at least {_SOURCE_FULL_CONSOLIDATED_SIZE_FLOOR} "
                "bytes) -- reclassify as 'provision_excerpt', or confirm this really is the full "
                "consolidated instrument and not a thin stub",
            )
    elif source.corpus_tier == "provision_excerpt":
        if is_provision_suffixed:
            return
        raise RegistryValidationError(
            f"source {source.id!r} declares corpus_tier='provision_excerpt' but {filename!r} carries "
            "no provision-suffixed filename of the corpus's own excerpt convention (-art/-apartado/"
            "-anexo/-da/-dt/-df/-se/-pr/-ar/-redacciones) -- this model has no anchored dispositive-"
            "content reader ('SourceReference.corpus_path' carries no '#anchor'), so filename "
            "convention is the only signal it can verify; rename to the convention or remove the claim",
        )


def _verify_manual_structure(repo_root: Path, source: GeneratedArtifactSource) -> None:
    """Run the manual-part structure check for a present ``manual_pdf`` source.

    Only meaningful when the manual PDF is present under the source tree (the
    full-checkout / dev path); a companion-resolved manual is proven by its
    byte-exact hash instead.

    ``corpus/manuals/<manual_id>/<year>[/<part>]/source.pdf`` is the ONE home for
    practical manuals consumed by the structured manual loader. Other ``manual_pdf``
    sources are evidence PDFs in a different corpus family (for example, EU IVA
    rate studies or AEAT instruction artefacts) and do not carry the practical-
    manual structure contract. The Sociedades practical manuals were moved into
    the canonical tree so they now receive the same check as their IVA and Renta
    peers.
    """
    if source.kind is not RegistrySourceKind.MANUAL_PDF or not source.corpus_path.startswith("corpus/manuals/"):
        return
    parts = source.corpus_path.split("/")
    try:
        if parts[:2] != ["corpus", "manuals"] or len(parts) < 5:
            raise ValueError(
                "a manual_pdf source must live at 'corpus/manuals/<manual_id>/<year>[/<part>]/source.pdf'",
            )
        manual_id_str, year_str, part_str = parts[2], parts[3], parts[4]

        from ....core.config import Settings
        from ...manuals.loader import load_manual
        from ...manuals.schema import ManualId, ManualPart

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


def _resolve_corpus_path(root: Path, source: GeneratedArtifactSource) -> Path:
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

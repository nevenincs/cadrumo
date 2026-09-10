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

import json
from collections.abc import Mapping
from pathlib import Path, PurePosixPath
from typing import Final

from ....core.hashing import hash_file
from ....core.resources.bundled_data import resolve_companion_binary
from .artifact_catalogue import (
    ArtifactCatalogue,
    ArtifactIdentity,
    ArtifactRole,
    compile_artifact_catalogue,
    record_design_manifest_identities,
    registry_source_identity,
)
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
        # The prefix is already proven above; only the coordinate depth is open.
        # A short path used to fall through this check silently, which is how a
        # misfiled manual could claim to be verified without ever being loaded.
        if len(parts) < 5:
            raise ValueError(
                "a practical-manual source must live at 'corpus/manuals/<manual_id>/<year>[/<part>]/source.pdf'",
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


def verify_catalogue_identity_bindings(
    catalogue: ArtifactCatalogue,
    sources: Mapping[str, SourceReference],
) -> None:
    """Require each registry source to exactly join an official catalog identity.

    The artifact catalog is deliberately a read-only identity projection, not
    registry authority.  This join therefore checks only the shared immutable
    acquisition fields.  It neither interprets source kind, evidence tier, or
    applicability nor publishes an authority snapshot; those registry
    semantics remain the responsibility of the established validator.

    Callers may pass a catalogue covering a wider corpus than ``sources``.  A
    source without an exact catalog payload identity, including one with the
    same path but a divergent URL, digest, or size, fails closed and names the
    registry source whose binding needs correction.  Publisher and retrieval
    date deliberately remain source-specific acquisition claims: a manifest's
    corpus-wide retrieval timestamp and its human publisher label are not the
    registry's typed authority/review semantics, so treating either as a
    binding mismatch would manufacture a false gap for an otherwise identical
    official payload.
    """
    failures: list[str] = []
    failures.extend(
        f"artifact catalog diagnostic {diagnostic.kind.value} for {diagnostic.path!s}: {diagnostic.message}"
        for diagnostic in catalogue.diagnostics
    )
    for source in sources.values():
        registry_identity = registry_source_identity(source)
        catalog_identity = catalogue.identities.get(registry_identity.path)
        catalog_role = catalogue.roles.get(registry_identity.path)
        if (
            catalog_identity is None
            or catalog_role is not ArtifactRole.OFFICIAL_ARTIFACT
            or not _same_payload_identity(catalog_identity, registry_identity)
        ):
            failures.append(
                f"source {source.id!r} does not exactly bind an official artifact catalog identity "
                f"for {source.corpus_path!r}"
            )
    if failures:
        raise RegistryValidationError("; ".join(sorted(failures)))


def compile_record_design_manifest_catalogue(
    root: Path,
    sources: Mapping[str, SourceReference],
) -> tuple[ArtifactCatalogue, Mapping[str, SourceReference]] | None:
    """Compile independent record-design manifest identities for registry joins.

    Per-model manifests are acquisition declarations made outside the registry.
    They are therefore the only inputs to this compilation; registry records
    are supplied separately as binding projections.  The bounded path set is
    exactly the record-design payloads named by the registry, so unrelated
    manifest rows remain the acquisition consumer's responsibility.

    ``None`` is meaningful: a registry with no record-design sources has no
    such acquisition projection to join, rather than a fabricated catalog made
    from its own source records.
    """
    record_design_sources = {
        source_id: source
        for source_id, source in sources.items()
        if _record_design_manifest_path(source.corpus_path) is not None
    }
    if not record_design_sources:
        return None

    bundle_root = _bundle_root(root)
    manifest_paths = {
        manifest_path
        for source in record_design_sources.values()
        if (manifest_path := _record_design_manifest_path(source.corpus_path)) is not None
    }
    identities: list[ArtifactIdentity] = []
    for manifest_path in sorted(manifest_paths):
        path = bundle_root.joinpath(*manifest_path.parts)
        try:
            raw_manifest = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise RegistryValidationError(
                f"record-design manifest {manifest_path.as_posix()!r} is unavailable: {error}"
            ) from error
        if not isinstance(raw_manifest, Mapping):
            raise RegistryValidationError(
                f"record-design manifest {manifest_path.as_posix()!r} must be a JSON object",
            )
        try:
            identities.extend(record_design_manifest_identities(raw_manifest, manifest_path=manifest_path.as_posix()))
        except (TypeError, ValueError) as error:
            raise RegistryValidationError(
                f"record-design manifest {manifest_path.as_posix()!r} has invalid acquisition identity: {error}",
            ) from error

    registry_identities = tuple(registry_source_identity(source) for source in record_design_sources.values())
    known_paths = tuple(identity.path for identity in registry_identities)
    known_set = set(known_paths)
    catalogue = compile_artifact_catalogue(
        known_paths=known_paths,
        official_identities=tuple(identity for identity in identities if identity.path in known_set),
    )
    return catalogue, record_design_sources


def _bundle_root(root: Path) -> Path:
    """Resolve the installed bundled-data root without probing arbitrary trees."""
    direct = root / "corpus"
    if direct.is_dir():
        return root
    packaged = root / "src" / "cadrumo" / "_data"
    if (packaged / "corpus").is_dir():
        return packaged
    return root


def _record_design_manifest_path(corpus_path: str) -> PurePosixPath | None:
    """Return the exact per-model manifest for a record-design corpus path."""
    parts = Path(corpus_path).parts
    prefix = ("corpus", "aeat_official", "disenos_registro")
    if len(parts) < len(prefix) + 2 or parts[: len(prefix)] != prefix:
        return None
    modelo_dir = parts[len(prefix)]
    if not modelo_dir.startswith("modelo_"):
        return None
    return PurePosixPath(*prefix, modelo_dir, "manifest.json")


def _same_payload_identity(catalog_identity: ArtifactIdentity, registry_identity: ArtifactIdentity) -> bool:
    """Return whether two typed identities name the same immutable payload.

    Kept private to this verifier because it defines a registry-to-catalogue
    join, not universal ``ArtifactIdentity`` equality.  Full identity records
    retain acquisition context for their own adapters; the registry controls
    its source authority, review, and retrieval context separately.
    """
    return (
        catalog_identity.path == registry_identity.path
        and catalog_identity.sha256 == registry_identity.sha256
        and catalog_identity.bytes == registry_identity.bytes
        and catalog_identity.source_url == registry_identity.source_url
    )


def verify_source_catalogue(
    root: Path,
    sources: Mapping[str, SourceReference],
) -> None:
    """Verify every source reference in a source catalogue mapping.

    Every source is byte-exact hash-enforced. Missing mandatory-companion data
    is an installation-integrity failure, not an advisory path.  Artifact
    identity joins are intentionally a separate operation: their independent
    manifest input must not be mistaken for the filesystem verifier's source
    authority.
    """
    verified: set[tuple[Path, int, str]] = set()
    for source in sources.values():
        key = ((root / source.corpus_path).resolve(), source.bytes, source.sha256)
        if key in verified:
            continue
        verify_source_file(root, source)
        verified.add(key)

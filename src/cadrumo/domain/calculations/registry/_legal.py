"""Legal catalogue helpers."""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from pathlib import Path

from ....core import CorpusAnchorResolutionError, normalise_corpus_text, resolve_anchored_extracted_unit
from ._citation_blocklist import CitationSource, find_known_bad
from ._errors import RegistryValidationError
from ._schema import LegalReference

_SOURCE_BY_KIND: dict[str, CitationSource] = {
    "ley": "ley",
    "real_decreto": "reglamento",
    "real_decreto_legislativo": "real_decreto_legislativo",
    "real_decreto_ley": "reglamento",
    "orden": "orden",
    "reglamento": "reglamento",
    "manual": "manual",
    "instruction": "instruction",
}


def verify_legal_reference(
    reference: LegalReference,
    *,
    source_root: Path | None = None,
) -> None:
    """Verify one already parsed legal reference is filing-grade.

    Type-system invariants enforced by the Pydantic schema (and thus
    NOT re-checked here):

      - ``review_status`` is ``Literal["reviewed"]`` — the type makes
        any other value unrepresentable, so a prior runtime check
        ``if reference.review_status != "reviewed"`` was structurally
        unreachable dead code.
      - ``evidence_tier`` on ``LegalReference`` is
        ``Literal["legal_authority"]`` — same dead-branch reasoning.
      - ``corpus_ref`` matches the ``path#anchor`` shape — the
        ``LegalReference`` model validator rejects malformed refs at
        parse time, so the defensive ``corpus_ref.split("#", 1)[0]``
        in :func:`_legal_corpus_text` will always find a non-empty path.

    This function therefore only checks runtime invariants that the
    type system cannot express: known-bad citation patterns and
    required-text presence against the local corpus.
    """
    if reference.kind == "manual":
        path_text = reference.corpus_ref.split("#", 1)[0]
        if source_root is not None:
            path = (source_root / path_text).resolve()
            if path.is_file():
                try:
                    from ...manuals import Section

                    Section.model_validate_json(path.read_text(encoding="utf-8"))
                except Exception as exc:
                    raise RegistryValidationError(
                        f"legal reference {reference.id!r} manual section JSON validation failed: {exc}",
                    ) from exc

    if reference.required_text and source_root is not None:
        corpus_text = _legal_corpus_text(source_root, reference)
        for required in reference.required_text:
            if normalise_corpus_text(required) not in corpus_text:
                raise RegistryValidationError(
                    f"legal reference {reference.id!r} corpus text missing required text {required!r}",
                )
    if reference.article is None:
        return
    source = _SOURCE_BY_KIND.get(reference.kind)
    if source is None:
        return
    role_text = " ".join(part for part in (reference.section, reference.notes) if part)
    if role_text and (known_bad := find_known_bad(source, reference.article, role_text)):
        raise RegistryValidationError(
            f"legal reference {reference.id!r} matches known-bad citation: {known_bad.reason}",
        )


def verify_legal_catalogue(
    legal: Mapping[str, LegalReference],
    *,
    source_root: Path | None = None,
) -> None:
    """Verify every legal reference in a shared legal catalogue."""
    failures: list[str] = []
    for ref_id, reference in legal.items():
        if ref_id != reference.id:
            failures.append(f"legal catalogue key {ref_id!r} does not match reference id {reference.id!r}")
        try:
            verify_legal_reference(reference, source_root=source_root)
        except RegistryValidationError as exc:
            failures.append(str(exc))
    if failures:
        raise RegistryValidationError("legal catalogue validation failed:\n" + "\n".join(f" - {f}" for f in failures))


_LEGAL_CORPUS_CACHE: dict[tuple[str, int, int, str, str, tuple[str, ...]], str] = {}


def _sidecar_content_digest(sidecar: Path, reference: LegalReference) -> str:
    """Return the trusted content discriminator for an extracted corpus sidecar.

    Args:
        sidecar: Path to the ``.extracted.json`` artefact backing the reference.
        reference: The legal reference being verified, named in the failure.

    Returns:
        The hex blake2b digest of the sidecar's bytes.

    Raises:
        RegistryValidationError: If the sidecar cannot be read.
    """
    try:
        data = sidecar.read_bytes()
    except OSError as exc:
        raise RegistryValidationError(
            f"legal reference {reference.id!r} extracted corpus sidecar could not be fingerprinted: {exc}",
        ) from exc
    return hashlib.blake2b(data, digest_size=16).hexdigest()


def _legal_corpus_text(source_root: Path, reference: LegalReference) -> str:
    path_text, _, anchor = reference.corpus_ref.partition("#")
    path = (source_root / path_text).resolve()
    repo_root = source_root.resolve()
    if repo_root not in path.parents and path != repo_root:
        raise RegistryValidationError(f"legal reference {reference.id!r} escapes repository root")
    sidecar = path.with_name(path.name + ".extracted.json")
    if not sidecar.is_file():
        raise RegistryValidationError(
            f"legal reference {reference.id!r} missing extracted corpus sidecar {path_text!r}",
        )
    stat = sidecar.stat()
    # A sidecar holds many extracted units.  The selected unit is therefore
    # part of the cache identity; caching only by sidecar would let the first
    # legal reference read from a document satisfy later sibling anchors.
    #
    # The content digest is load-bearing, not belt-and-braces: size and mtime
    # are forgeable together, so a same-length replacement whose mtime is
    # restored is invisible to a metadata-only key and the cache would keep
    # serving the superseded text as the legal evidence behind a filing.  The
    # stat fields stay as the cheap first-order discriminator, mirroring the
    # registry loader's TOML fingerprint.
    cache_key = (
        str(sidecar),
        stat.st_size,
        stat.st_mtime_ns,
        _sidecar_content_digest(sidecar, reference),
        anchor,
        reference.required_text,
    )
    if cache_key in _LEGAL_CORPUS_CACHE:
        return _LEGAL_CORPUS_CACHE[cache_key]

    try:
        text = normalise_corpus_text(
            resolve_anchored_extracted_unit(
                sidecar,
                anchor=anchor,
                required_text=reference.required_text,
                include_title=True,
            ),
        )
    except CorpusAnchorResolutionError as exc:
        raise RegistryValidationError(
            f"legal reference {reference.id!r} cannot resolve one corpus unit for anchor {anchor!r}",
        ) from exc
    _LEGAL_CORPUS_CACHE[cache_key] = text
    return text

"""Legal catalogue helpers."""

from __future__ import annotations

import hashlib
from collections.abc import Iterable, Mapping
from pathlib import Path

from ....core import (
    CorpusAnchorResolutionError,
    LegalReviewStatus,
    corpus_redaction_marks,
    extracted_unit_count,
    normalise_corpus_text,
    resolve_anchored_extracted_unit,
)
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


def _validate_manual_legal_reference(reference: LegalReference, source_root: Path) -> None:
    path_text = reference.corpus_ref.split("#", 1)[0]
    path = (source_root / path_text).resolve()
    if not path.is_file():
        return
    try:
        from ...manuals import Section

        Section.model_validate_json(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise RegistryValidationError(
            f"legal reference {reference.id!r} manual section JSON validation failed: {exc}",
        ) from exc


def _validate_legal_corpus_clauses(reference: LegalReference, source_root: Path) -> None:
    corpus_text = _legal_corpus_text(source_root, reference)
    for required in reference.required_text:
        if normalise_corpus_text(required) not in corpus_text:
            raise RegistryValidationError(
                f"legal reference {reference.id!r} corpus text missing required text {required!r}",
            )
    for forbidden in reference.forbidden_text:
        if normalise_corpus_text(forbidden) in corpus_text:
            raise RegistryValidationError(
                f"legal reference {reference.id!r} corpus text contains forbidden text {forbidden!r}",
            )


def _validate_known_bad_citation(reference: LegalReference) -> None:
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


def verify_legal_reference(
    reference: LegalReference,
    *,
    source_root: Path | None = None,
) -> None:
    """Verify one already parsed legal reference is filing-grade.

    Type-system invariants enforced by the Pydantic schema (and thus
    NOT re-checked here):

      - ``review_status`` is a closed provenance vocabulary whose companion
        reviewer fields are kept coherent by the model.
      - ``evidence_tier`` on ``LegalReference`` is
        ``Literal["legal_authority"]`` — same dead-branch reasoning.
      - ``corpus_ref`` matches the ``path#anchor`` shape — the
        ``LegalReference`` model validator rejects malformed refs at
        parse time, so the defensive ``corpus_ref.split("#", 1)[0]``
        in :func:`_legal_corpus_text` will always find a non-empty path.

    This function therefore only checks runtime invariants that the
    type system cannot express: known-bad citation patterns, required-text
    presence and forbidden-text absence against the local corpus. The two
    text clauses diagnose opposite defects — a missing required phrase and a
    present forbidden phrase — so their failures are raised with distinct
    messages naming which clause fired.
    """
    if reference.review_status is not LegalReviewStatus.OPERATOR_REVIEWED:
        raise RegistryValidationError(
            f"legal reference {reference.id!r} is {reference.review_status.value!r}; "
            "filing-grade authority requires operator_reviewed",
        )
    verify_legal_reference_grounding(reference, source_root=source_root)


def verify_legal_reference_grounding(
    reference: LegalReference,
    *,
    source_root: Path | None = None,
) -> None:
    """Verify legal content independently of its production review eligibility.

    Corpus audits need to inspect every authored reference, including references
    that are honestly marked as awaiting operator review. Production consumers
    call :func:`verify_legal_reference`, which applies the stricter review-status
    gate before delegating here.
    """
    if reference.kind == "manual" and source_root is not None:
        _validate_manual_legal_reference(reference, source_root)
    if source_root is not None and (reference.required_text or reference.forbidden_text):
        _validate_legal_corpus_clauses(reference, source_root)
    _validate_known_bad_citation(reference)


def legal_reference_quotes_corpus(
    reference: LegalReference,
    quotation: str,
    *,
    source_root: Path,
) -> bool:
    """Report whether ``quotation`` occurs in ``reference``'s bundled corpus text.

    This is the ``required_text`` presence check above, exposed for a caller
    that holds a quotation of its own rather than one declared on the reference.
    The corpus text itself stays private: a caller that could read it could
    also mint a quotation from it, which would make the check circular.

    Args:
        reference: The legal reference whose corpus text is authoritative.
        quotation: Candidate verbatim text.
        source_root: Repository root the corpus reference resolves against.

    Returns:
        ``True`` when the normalised quotation is present in the normalised
        corpus text. An empty quotation is never present.

    Raises:
        RegistryValidationError: If the corpus evidence cannot be read.
    """
    if not quotation.strip():
        return False
    return normalise_corpus_text(quotation) in _legal_corpus_text(source_root, reference)


def assert_legal_ref_ids_resolve(
    ref_ids: Iterable[str],
    *,
    legal: Mapping[str, LegalReference],
    subject: str,
) -> None:
    """Refuse any of ``ref_ids`` that is absent from the legal catalogue.

    A caller outside the registry tree -- a calculation advisory declaring a
    provision it asserts about itself, rather than one read off a casilla or
    binding already grounded by the registry -- has no structural guarantee
    its declared ids are real. This is the check a prose-only message could
    never carry: every id is resolved against the same ``legal`` mapping
    registry build already validates, so a renumbered or retired provision
    reds here instead of surviving silently in a string.

    ``subject`` names what declared ``ref_ids``, folded into the failure
    message so a refusal names its origin without the caller re-deriving it
    from a stack trace.

    Args:
        ref_ids: The declared legal-catalogue ids to resolve. Order and
            duplicates are irrelevant to the check.
        legal: The legal catalogue to resolve against, keyed by id -- the same
            mapping :func:`verify_legal_catalogue` validates.
        subject: A short description of what declared ``ref_ids`` (e.g. an
            advisory's ``reason`` or module name), named in the failure.

    Raises:
        RegistryValidationError: If any id in ``ref_ids`` is absent from
            ``legal``.
    """
    missing = sorted({ref_id for ref_id in ref_ids if ref_id not in legal})
    if missing:
        raise RegistryValidationError(
            f"{subject} declares legal ref id(s) absent from the legal catalogue: {missing!r}",
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


def verify_legal_catalogue_grounding(
    legal: Mapping[str, LegalReference],
    *,
    source_root: Path | None = None,
) -> None:
    """Audit every catalogue entry's identity and corpus grounding.

    Review eligibility is deliberately excluded: it is applied to the exact
    legal slice selected for a production snapshot, so unfinished references
    cannot disable unrelated registry consumers before a filing context exists.
    """
    failures: list[str] = []
    for ref_id, reference in legal.items():
        if ref_id != reference.id:
            failures.append(f"legal catalogue key {ref_id!r} does not match reference id {reference.id!r}")
        try:
            verify_legal_reference_grounding(reference, source_root=source_root)
        except RegistryValidationError as exc:
            failures.append(str(exc))
    if failures:
        raise RegistryValidationError(
            "legal catalogue grounding validation failed:\n" + "\n".join(f" - {failure}" for failure in failures),
        )


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


def _assert_redactions_are_not_fused(
    document: Path,
    sidecar: Path,
    reference: LegalReference,
    *,
    path_text: str,
) -> None:
    """Refuse a citation whose evidence fuses repealed law with the law in force.

    BOE's open-data article endpoint concatenates EVERY historical redaction of
    an article into one response, correctly and by design -- that history is why
    the endpoint is worth reading. The bundled extractor then folds the whole
    response into a single undelimited unit carrying no ``fecha_vigencia``
    attribution, so the text a ``required_text`` clause is checked against is
    ten successive statements of the same provision run together. A phrase that
    exists ONLY in a redaction repealed decades ago is then *present*, the
    presence check passes, and the entry reads as grounded in current law while
    its evidence is a pile. That is the failure a presence-only gate cannot
    see from the inside, so it is refused from the outside instead.

    Detection is STRUCTURAL rather than by filename. The redaction-history
    captures happen to share a ``-redacciones`` stem, but that is an authoring
    convention a later acquisition can sidestep without meaning to -- and the
    live catalogue already proved it, citing a two-redaction article capture
    under an ordinary ``-art-N`` name. The durable signal is the shape: the
    cited document itself declares more than one dated redaction. A document
    declaring none or one -- a consolidated page, an as-published view, a
    hand-sliced article, an article never amended -- is untouched.

    The refusal is on the redaction count alone rather than on a unit-count
    comparison, and that is fail-closed on purpose. "Fewer units than
    redactions" proves fusion by pigeonhole, but its converse proves nothing: a
    sidecar can carry more units than the document has redactions and still run
    two of them together, because the extractor splits on article headings and
    knows nothing about redaction boundaries. Nothing in the sidecar schema says
    which redaction a unit holds, so no sidecar shape available today can
    establish separation, and a check that accepted one would be granting on a
    signal it does not have. The unit count is measured and reported because it
    quantifies the collapse for whoever reads the failure; it does not decide
    it.

    CONSIDERED AND DEFERRED: splitting the article-endpoint extraction into one
    unit per ``<version>``, each carrying its own ``fecha_vigencia``, so the
    committed data stops being a pile rather than merely being unusable as
    evidence. It is the larger and better remedy and it is deferred rather than
    rejected: it reshapes shared production extraction output that several
    concurrent efforts consume, and choosing the per-redaction unit identity,
    anchor grammar and attribution field is architecturally significant enough
    to warrant its own decision record. This refusal does not preclude it. When
    that attribution exists, this check gains an acceptance clause reading it;
    until then no such clause is written, because a branch no committed sidecar
    can reach is a branch no test can honestly exercise.

    A sidecar with no source document beside it is out of scope rather than
    fail-closed, and the distinction is deliberate. The sidecar is what the app
    reads as evidence and its presence is already required above; the source
    document is not, and making it required here would smuggle a separate
    integrity rule in under this one. A sidecar standing alone carries no
    redaction markup to read, so there is nothing for this check to decide.
    Every document the committed catalogue cites does exist, and the gate
    asserts that over the whole population, so the skip swallows nothing real.
    A document that is PRESENT but unreadable is a different matter and
    refuses: then the markup exists and could not be examined.

    Args:
        document: The corpus document the reference cites.
        sidecar: Its resolved ``.extracted.json`` artefact.
        reference: The legal reference being verified, named in the failure.
        path_text: The reference's own corpus path, quoted back to the author.

    Raises:
        RegistryValidationError: If the document is present but cannot be read,
            or if it declares more than one dated redaction of the provision.
    """
    if not document.is_file():
        return
    try:
        payload = document.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        raise RegistryValidationError(
            f"legal reference {reference.id!r} corpus document {path_text!r} could not be read, so it "
            f"cannot be shown to carry a single redaction of the provision: {exc}",
        ) from exc
    marks = corpus_redaction_marks(payload)
    if len(marks) < 2:
        return
    try:
        units = extracted_unit_count(sidecar)
    except CorpusAnchorResolutionError as exc:
        raise RegistryValidationError(
            f"legal reference {reference.id!r} extracted corpus sidecar could not be counted: {exc}",
        ) from exc
    vigencias = ", ".join(mark.vigencia for mark in marks)
    raise RegistryValidationError(
        f"legal reference {reference.id!r} cites {path_text!r}, which declares {len(marks)} dated "
        f"redactions of the provision ({vigencias}) collapsed into {units} extracted unit(s), so the "
        f"text this entry is checked against fuses repealed law with the law in force. A required-text "
        f"presence check against fused evidence passes on REPEALED text, which is exactly what the "
        f"clause exists to prevent. Cite a consolidated current-text document for this provision "
        f"instead, or reduce the capture to the redaction in force -- the maximum fecha_vigencia, "
        f"refusing a tie -- through the corpus acquirer's own redaction-in-force rule before citing it.",
    )


def _legal_corpus_text(source_root: Path, reference: LegalReference) -> str:
    path_text, _, anchor = reference.corpus_ref.partition("#")
    path = (source_root / path_text).resolve()
    repo_root = source_root.resolve()
    if repo_root not in path.parents and path != repo_root:
        raise RegistryValidationError(f"legal reference {reference.id!r} escapes repository root")
    sidecar = path.with_name(path.name + ".extracted.json")
    try:
        resolved_sidecar = sidecar.resolve()
    except OSError as exc:
        raise RegistryValidationError(
            f"legal reference {reference.id!r} extracted corpus sidecar could not be resolved: {exc}",
        ) from exc
    if repo_root not in resolved_sidecar.parents and resolved_sidecar != repo_root:
        raise RegistryValidationError(
            f"legal reference {reference.id!r} extracted corpus sidecar escapes repository root"
        )
    if not resolved_sidecar.is_file():
        raise RegistryValidationError(
            f"legal reference {reference.id!r} missing extracted corpus sidecar {path_text!r}",
        )
    _assert_redactions_are_not_fused(path, resolved_sidecar, reference, path_text=path_text)
    stat = resolved_sidecar.stat()
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
        str(resolved_sidecar),
        stat.st_size,
        stat.st_mtime_ns,
        _sidecar_content_digest(resolved_sidecar, reference),
        anchor,
        reference.required_text,
    )
    if cache_key in _LEGAL_CORPUS_CACHE:
        return _LEGAL_CORPUS_CACHE[cache_key]

    try:
        text = normalise_corpus_text(
            resolve_anchored_extracted_unit(
                resolved_sidecar,
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

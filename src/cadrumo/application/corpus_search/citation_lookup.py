"""Structured exact-citation lookup over the registry legal catalogue.

Exact citations ("art. 27.2 LGT", ``ley-58-2003:art-27.2``) do not go
through the FTS index: the wheel already ships typed citation data (the
registry ``legal_refs`` with their ``corpus_ref`` and BOE permalinks),
so this is a direct structured key lookup, not a parallel citation
parser. The registry legal catalogue is the single citation authority;
this module reuses it and adds
the one thing the product lacked at runtime: resolving a citation id to
the verbatim authoritative text its ``corpus_ref`` points at.

The verbatim text is read from the bundled ``*.extracted.json`` sidecar
(the clean, structured extraction the corpus ships) rather than the raw
HTML, and sliced to the unit the citation's anchor names when the source
file carries multiple units.

See Also:
    :class:`~application.corpus_search.CitationResolution`
        Typed result carrying catalogue metadata and verbatim text.
    :func:`~application.corpus_search.search_corpus`
        Exact citation ids short-circuit through this lookup before ranking.

Notes:
    External adapters may resolve citation ids and retrieval ``corpus_ref``
    values through this product-owned service.
"""

from __future__ import annotations

from ...domain.calculations.registry.authority import ValidatedRegistryAuthority, bundled_authority
from ...domain.calculations.registry.authority_artifact import AuthorityArtifactError
from ...domain.calculations.registry.schema_references import LegalReference
from .errors import CorpusSearchInputError
from .models import CitationResolution


class CitationLookup:
    """Resolve a registry citation id to metadata plus verbatim text.

    The lookup is built over a published authority. Its text projection is
    signed with the authority, so resolving a citation never opens a bundled
    corpus file or source root.
    """

    def __init__(self, authority: ValidatedRegistryAuthority) -> None:
        """Initialize the lookup with one signed runtime authority."""
        self._authority = authority
        self._legal = dict(authority.catalogues.legal)

    @property
    def citation_ids(self) -> tuple[str, ...]:
        """Return every resolvable citation id, sorted."""
        return tuple(sorted(self._legal))

    def resolve(self, citation_id: str) -> CitationResolution:
        """Resolve ``citation_id`` to a :class:`CitationResolution`.

        Args:
            citation_id: A registry ``legal_refs`` id, e.g.
                ``ley-58-2003:art-27.2``.

        Returns:
            The citation's catalogue metadata plus the verbatim
            authoritative text its ``corpus_ref`` points at.

        Raises:
            CorpusSearchInputError: If the id is unknown to the catalogue
                or its backing corpus text cannot be read.
        """
        key = citation_id.strip()
        reference = self._legal.get(key)
        if reference is None:
            raise CorpusSearchInputError(
                reason="citation_id_unknown",
                context={"citation_id": citation_id},
            )
        _path_part, _, anchor_part = reference.corpus_ref.partition("#")
        anchor = anchor_part or None
        verbatim = self._verbatim_text(reference)
        return CitationResolution(
            citation_id=reference.id,
            document_id=reference.document_id,
            kind=reference.kind,
            corpus_ref=reference.corpus_ref,
            permalink=reference.permalink,
            article=reference.article,
            section=reference.section,
            anchor=anchor,
            verbatim_text=verbatim,
        )

    def resolve_corpus_text(self, ref: str) -> str:
        """Resolve a citation id OR a corpus_ref (``path#anchor``) to verbatim text.

        The ``cadrumo://corpus/{ref}`` resource accepts either form: a retrieval
        hit's ``corpus_ref`` or a bare citation id. A known citation id routes
        through :meth:`resolve`; otherwise ``ref`` is read as a corpus path and
        anchor.

        Raises:
            CorpusSearchInputError: If ``ref`` resolves to no readable text or
                escapes the corpus root.
        """
        key = ref.strip()
        if key in self._legal:
            return self.resolve(key).verbatim_text
        references = tuple(reference for reference in self._legal.values() if reference.corpus_ref == key)
        if len(references) != 1:
            raise CorpusSearchInputError(reason="corpus_text_unreadable", context={"ref": ref})
        return self._verbatim_text(references[0])

    def _verbatim_text(self, reference: LegalReference) -> str:
        try:
            return self._authority.legal_evidence_text(reference.id)
        except AuthorityArtifactError as exc:
            raise CorpusSearchInputError(
                reason="citation_extracted_text_absent",
                context={"citation_id": reference.id, "corpus_ref": reference.corpus_ref},
            ) from exc


def bundled_citation_lookup() -> CitationLookup:
    """Return a :class:`CitationLookup` over the bundled registry catalogue."""
    authority = bundled_authority()
    return CitationLookup(authority)


__all__ = ["CitationLookup", "bundled_citation_lookup"]

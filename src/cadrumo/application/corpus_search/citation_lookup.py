"""Structured exact-citation lookup over the registry legal catalogue.

Exact citations ("art. 27.2 LGT", ``ley-58-2003:art-27.2``) do not go
through the FTS index: the wheel already ships typed citation data (the
registry ``legal_refs`` with their ``corpus_ref`` and BOE permalinks),
so this is a direct structured key lookup, not a parallel citation
parser. The registry legal catalogue is the single citation authority;
this module reuses it and adds
the one thing the product lacked at runtime: resolving a citation id to
the verbatim authoritative text its ``corpus_ref`` points at.

The verbatim text is read from the published authority artifact's signed
evidence projection rather than the raw HTML, and sliced to the unit the
citation's anchor names when the source file carries multiple units.

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

from abc import ABC, abstractmethod
from collections.abc import Collection, Mapping
from typing import TYPE_CHECKING

from ...domain.calculations.registry.authority_artifact import (
    AuthorityComponentCodecError,
    AuthorityComponentKind,
    AuthorityGenerationPin,
    EvidenceComponentQuery,
    PublishedLegalEvidence,
)
from ...domain.calculations.registry.schema_references import LegalReference
from .errors import CorpusSearchInputError
from .models import CitationResolution

if TYPE_CHECKING:
    from ...domain.calculations.registry.authority import PinnedAuthorityOperation
    from ...domain.calculations.registry.authority_artifact import AuthorityComponentReader


class CitationLookup(ABC):
    """Resolve a registry citation id to metadata plus verbatim text.

    The lookup is built over one caller-selected component operation. Its text
    projection is signed with the authority, so resolving a citation never
    opens a bundled corpus file or source root.
    """

    _legal: dict[str, LegalReference]

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

    @abstractmethod
    def _verbatim_text(self, reference: LegalReference) -> str:
        """Return pinned verbatim evidence for one selected legal declaration."""

    @classmethod
    def from_component_reader(
        cls,
        legal: Mapping[str, LegalReference],
        *,
        reader: AuthorityComponentReader,
        pin: AuthorityGenerationPin,
    ) -> CitationLookup:
        """Build a citation lookup over one pinned component reader.

        ``legal`` is the metadata projection selected by the caller. Evidence
        remains point-addressed: resolving one citation asks the reader for
        only that citation's legal evidence component and never opens a corpus
        path or hydrates sibling evidence.
        """
        return _ComponentCitationLookup(legal, reader=reader, pin=pin)

    @classmethod
    def from_operation(
        cls,
        reference_ids: Collection[str],
        *,
        operation: PinnedAuthorityOperation,
    ) -> CitationLookup:
        """Build an evidence lookup from exact ids under one pinned operation.

        Legal declarations and their evidence are both addressed pointwise.
        The caller supplies the ids it has selected; this constructor does not
        hydrate a legal catalogue or accept a parallel metadata projection.
        """
        legal = {reference_id: operation.legal_reference(reference_id) for reference_id in reference_ids}
        return cls.from_component_reader(legal, reader=operation, pin=operation.pin())


class _ComponentCitationLookup(CitationLookup):
    """Citation lookup whose evidence comes from one generation-pinned reader."""

    def __init__(
        self,
        legal: Mapping[str, LegalReference],
        *,
        reader: AuthorityComponentReader,
        pin: AuthorityGenerationPin,
    ) -> None:
        self._legal = dict(legal)
        self._reader = reader
        self._pin = pin

    def _verbatim_text(self, reference: LegalReference) -> str:
        try:
            evidence = self._reader.load(
                EvidenceComponentQuery(
                    reference_id=str(reference.id),
                    kind=AuthorityComponentKind.LEGAL_EVIDENCE,
                ),
                pin=self._pin,
            )
        except (AuthorityComponentCodecError, LookupError) as exc:
            raise CorpusSearchInputError(
                reason="citation_extracted_text_absent",
                context={"citation_id": reference.id, "corpus_ref": reference.corpus_ref},
            ) from exc
        if not isinstance(evidence, PublishedLegalEvidence) or evidence.legal_reference_id != str(reference.id):
            raise CorpusSearchInputError(
                reason="citation_extracted_text_absent",
                context={"citation_id": reference.id, "corpus_ref": reference.corpus_ref},
            )
        return evidence.anchored_text


def bundled_citation_lookup(
    reference_ids: Collection[str],
    *,
    operation: PinnedAuthorityOperation,
) -> CitationLookup:
    """Build the bundled lookup from caller-selected ids and one live operation.

    The indexed authority does not expose a global legal catalogue projection
    here.  Its composition root must select the ids and keep ``operation``
    leased for every lookup call.
    """
    return CitationLookup.from_operation(reference_ids, operation=operation)


__all__ = ["CitationLookup", "bundled_citation_lookup"]

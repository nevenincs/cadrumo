"""Structured exact-citation lookup over the registry legal catalogue.

Exact citations ("art. 27.2 LGT", ``ley-58-2003:art-27.2``) do not go
through the FTS index: the wheel already ships typed citation data (the
registry ``legal_refs`` with their ``corpus_ref`` and BOE permalinks),
so this is a direct structured key lookup, not a parallel citation
parser. The registry legal catalogue is the single citation authority
(:data:`aeat-registry-authority-flow`); this module reuses it and adds
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

from collections.abc import Mapping
from pathlib import Path

from ...core.corpus_text import CorpusAnchorResolutionError, resolve_anchored_extracted_unit
from ...domain.calculations.registry.authority import bundled_authority
from ...domain.calculations.registry.schema_references import LegalReference
from .errors import CorpusSearchInputError
from .models import CitationResolution


class CitationLookup:
    """Resolve a registry citation id to metadata plus verbatim text.

    The lookup is built over the reviewed legal catalogue and the corpus
    source root (the bundled ``_data`` tree the catalogue's ``corpus_ref``
    values are relative to).
    """

    def __init__(self, legal: Mapping[str, LegalReference], *, source_root: Path) -> None:
        """Initialize the lookup with the legal catalogue and the corpus source root."""
        self._legal = dict(legal)
        self._source_root = source_root.resolve()

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
        path_part, _, anchor_part = reference.corpus_ref.partition("#")
        anchor = anchor_part or None
        verbatim = self._verbatim_text(reference, path_part=path_part, anchor=anchor)
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
        path_part, _, anchor_part = key.partition("#")
        text = self._read_corpus_text(path_part, anchor=anchor_part or None)
        if text is None:
            raise CorpusSearchInputError(reason="corpus_text_unreadable", context={"ref": ref})
        return text

    def _verbatim_text(self, reference: LegalReference, *, path_part: str, anchor: str | None) -> str:
        text = self._read_corpus_text(path_part, anchor=anchor, required_text=reference.required_text)
        if text is None:
            raise CorpusSearchInputError(
                reason="citation_extracted_text_absent",
                context={"citation_id": reference.id, "corpus_ref": reference.corpus_ref},
            )
        return text

    def _read_corpus_text(
        self,
        path_part: str,
        *,
        anchor: str | None,
        required_text: tuple[str, ...] = (),
    ) -> str | None:
        source_path = (self._source_root / path_part).resolve()
        if self._source_root not in source_path.parents:
            raise CorpusSearchInputError(
                reason="corpus_ref_escapes_root",
                context={"path": path_part},
            )
        extracted_json = source_path.with_name(source_path.name + ".extracted.json")
        if not extracted_json.is_file():
            return None
        try:
            return resolve_anchored_extracted_unit(
                extracted_json,
                anchor=anchor or "",
                required_text=required_text,
            )
        except CorpusAnchorResolutionError as exc:
            raise CorpusSearchInputError(
                reason="corpus_ref_not_one_unit",
                context={"path": path_part, "anchor": anchor or ""},
            ) from exc


def bundled_citation_lookup() -> CitationLookup:
    """Return a :class:`CitationLookup` over the bundled registry catalogue."""
    authority = bundled_authority()
    return CitationLookup(authority.catalogues.legal, source_root=authority.source_root)


__all__ = ["CitationLookup", "bundled_citation_lookup"]

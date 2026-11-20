"""One public reference question answered from the bundled corpus and terminology handbook.

The corpus search, an exact citation's verbatim evidence and the approved
terminology concepts all come from sources that ship with the product and hold
no profile data. Every frontend asks the question through this one composition,
under the publication pin its caller already holds, so no surface joins the
retrieval and the terminology a second way.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel

from ...core.models import STRICT_FROZEN_CONFIG
from .models import RetrievalResponse
from .runtime import search_corpus
from .terminology import TerminologyHit, search_terminology

if TYPE_CHECKING:
    from ...core.external_constants import OutputLanguage
    from ...domain.calculations.registry.authority import PinnedAuthorityOperation


class ReferenceCorpusSearch(BaseModel):
    """The ranked retrieval or exact citation for one query, with its terminology concepts."""

    model_config = STRICT_FROZEN_CONFIG

    retrieval: RetrievalResponse
    terminology: tuple[TerminologyHit, ...]


def search_reference_corpus(
    query: str,
    *,
    limit: int,
    operation: PinnedAuthorityOperation,
    language: OutputLanguage | None = None,
) -> ReferenceCorpusSearch:
    """Ground ``query`` in the bundled corpus and the approved terminology.

    An exact citation resolves its verbatim evidence under ``operation``'s pin.
    Terminology concepts are worded in ``language``, or in the handbook's
    fallback language when none is named.
    """
    retrieval = search_corpus(query, operation=operation, limit=limit)
    terminology = (
        search_terminology(query, limit=limit)
        if language is None
        else search_terminology(query, locale=language.value, limit=limit)
    )
    return ReferenceCorpusSearch(retrieval=retrieval, terminology=terminology)


__all__ = ["ReferenceCorpusSearch", "search_reference_corpus"]

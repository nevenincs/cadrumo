"""Period correctness: a casilla cites the legal rows that govern its own edition.

The legal catalogue records one dated row per redaction of an article: a row's
governed span is its in-force window, or its declared retroactive reach (see
:func:`~.schema_references.governed_period_span`). A casilla's ``legal_refs``
are a grounding claim for the edition that carries the casilla, so every row it
cites must govern that edition.

A cited row COVERS an edition exactly when the snapshot's revision-scoped
legal-window predicate accepts the pair, so a casilla citation and a revision
citation are judged by one definition:

- a substantive-law row (ley, real decreto, real decreto legislativo, real
  decreto-ley, reglamento, directiva, acuerdo internacional) must govern the
  edition's devengo: its governed span contains the edition's ``valid_to``.
  For an open-ended edition it must not have ceased before the edition's
  ``valid_from``;
- a procedural row (orden, manual, instruction) must overlap the edition's
  presentation-aware window, which runs from ``valid_from`` to the latest of
  ``valid_to`` and every declared deadline close, and is open for an open-ended
  edition.

A citation whose row does not cover its edition is REFUSED, and so is one whose
id resolves to no row. The snapshot check exempts a revision's modelo-level
references as the modelo's cross-year corpus; that exemption does not reach a
casilla, whose citation is specific to its edition whatever else also cites the
same row.

Each refusal also names the ALTERNATIVES: the other rows of the same article
(same ``document_id``, ``article`` and ``section``) that do cover the edition.
An empty tuple means the catalogue carries no row of that article governing the
edition.

Completeness is judged against an explicit exception set keyed per citation. A
refused citation no exception names is UNCOVERED. An exception naming a
citation that is not refused in the corpus given is STALE. Pass the whole
corpus, or every exception outside it reads as stale.

Where this rule stops:

- only casilla ``legal_refs`` are judged. Revision, modelo, alias, constraint,
  parameter and every other record's citations belong to the snapshot check;
- the devengo anchor is the edition's closing date. An edition spanning several
  devengos, whose law changed partway through, is not required to cite a row
  for each period inside it;
- whether the cited article is the right one for the casilla is a content
  question this rule cannot see. A citation set that churns between editions
  while every row still covers both is period-correct;
- a missing citation is not detected: a casilla citing nothing passes;
- a row's dates and retroactive reach are taken as the catalogue declares
  them. Whether they match the norm is the catalogue's own verification;
- exceptions are matched by key alone. Their classification and reason belong
  to whoever keeps the exception set, and are not read here.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Collection, Iterable, Mapping
from dataclasses import dataclass
from datetime import date

from ._snapshot_internals import _legal_window_covers_devengo
from .schema import ModeloDefinition, ModeloRevision
from .schema_references import LegalReference, governed_period_span

__all__ = (
    "CasillaCitationKey",
    "CitationPeriodRefusal",
    "CitationPeriodReport",
    "casilla_citation_period_refusals",
    "citation_period_correctness",
)


@dataclass(frozen=True, slots=True, order=True)
class CasillaCitationKey:
    """One legal reference cited by one casilla row of one edition of one modelo."""

    modelo: str
    revision: str
    casilla: str
    reference: str


@dataclass(frozen=True, slots=True)
class CitationPeriodRefusal:
    """A casilla citation whose row does not govern the citing edition."""

    key: CasillaCitationKey
    edition_from: date
    edition_to: date | None
    governs_from: date | None
    """Start of the cited row's governed span; ``None`` when the id resolves to no row."""
    governs_to: date | None
    alternatives: tuple[str, ...]
    """Other rows of the cited article that do cover the edition, in id order."""

    def describe(self) -> str:
        """Render the refusal naming the modelo, edition, casilla, reference and window."""
        edition = f"[{self.edition_from.isoformat()}..{_bound(self.edition_to)}]"
        head = (
            f"modelo {self.key.modelo} edition {self.key.revision} {edition} "
            f"casilla {self.key.casilla} cites {self.key.reference!r}"
        )
        if self.governs_from is None:
            return f"{head}, which resolves to no legal catalogue row"
        governed = f"[{self.governs_from.isoformat()}..{_bound(self.governs_to)}]"
        tail = f"; rows of the same article that do: {', '.join(self.alternatives)}" if self.alternatives else ""
        return f"{head}, whose governed span {governed} does not cover the edition{tail}"


@dataclass(frozen=True, slots=True)
class CitationPeriodReport:
    """Refused citations no exception covers, and exceptions no citation needs."""

    uncovered: tuple[CitationPeriodRefusal, ...]
    stale: tuple[CasillaCitationKey, ...]

    @property
    def is_correct(self) -> bool:
        """Whether every refused citation is covered and no exception is stale."""
        return not self.uncovered and not self.stale


def casilla_citation_period_refusals(
    modelo: ModeloDefinition,
    legal_catalogue: Mapping[str, LegalReference],
) -> tuple[CitationPeriodRefusal, ...]:
    """Return every casilla citation of ``modelo`` whose row does not govern its edition."""
    articles = _article_rows(legal_catalogue)
    refusals: list[CitationPeriodRefusal] = []
    for revision in modelo.revisions.values():
        for casilla in revision.casillas:
            for reference_id in casilla.legal_refs:
                key = CasillaCitationKey(
                    modelo=modelo.id,
                    revision=str(revision.id),
                    casilla=str(casilla.id),
                    reference=reference_id,
                )
                refusal = _refusal(key, revision, legal_catalogue.get(reference_id), articles)
                if refusal is not None:
                    refusals.append(refusal)
    return tuple(sorted(refusals, key=lambda refusal: refusal.key))


def citation_period_correctness(
    modelos: Iterable[ModeloDefinition],
    legal_catalogue: Mapping[str, LegalReference],
    exceptions: Collection[CasillaCitationKey],
) -> CitationPeriodReport:
    """Judge ``modelos`` for citation period correctness against a per-citation exception set."""
    refused = {
        refusal.key: refusal
        for modelo in modelos
        for refusal in casilla_citation_period_refusals(modelo, legal_catalogue)
    }
    excepted = frozenset(exceptions)
    return CitationPeriodReport(
        uncovered=tuple(refused[key] for key in sorted(refused.keys() - excepted)),
        stale=tuple(sorted(excepted - refused.keys())),
    )


type _ArticleKey = tuple[str, str | None, str | None]


def _article_key(reference: LegalReference) -> _ArticleKey:
    return (reference.document_id, reference.article, reference.section)


def _article_rows(legal_catalogue: Mapping[str, LegalReference]) -> Mapping[_ArticleKey, tuple[LegalReference, ...]]:
    rows: defaultdict[_ArticleKey, list[LegalReference]] = defaultdict(list)
    for reference in legal_catalogue.values():
        rows[_article_key(reference)].append(reference)
    return {key: tuple(sorted(members, key=lambda member: member.id)) for key, members in rows.items()}


def _refusal(
    key: CasillaCitationKey,
    revision: ModeloRevision,
    reference: LegalReference | None,
    articles: Mapping[_ArticleKey, tuple[LegalReference, ...]],
) -> CitationPeriodRefusal | None:
    if reference is None:
        return CitationPeriodRefusal(
            key=key,
            edition_from=revision.valid_from,
            edition_to=revision.valid_to,
            governs_from=None,
            governs_to=None,
            alternatives=(),
        )
    if _legal_window_covers_devengo(revision, reference):
        return None
    governs_from, governs_to = governed_period_span(reference)
    return CitationPeriodRefusal(
        key=key,
        edition_from=revision.valid_from,
        edition_to=revision.valid_to,
        governs_from=governs_from,
        governs_to=governs_to,
        alternatives=tuple(
            sibling.id
            for sibling in articles[_article_key(reference)]
            if sibling.id != reference.id and _legal_window_covers_devengo(revision, sibling)
        ),
    )


def _bound(value: date | None) -> str:
    return "open" if value is None else value.isoformat()

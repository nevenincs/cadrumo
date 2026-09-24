"""An article citation is verified against that article's text, never the document's.

``required_text`` proves a citation only when it is checked against the unit
the anchor names. A sidecar that holds a multi-article excerpt as one
anonymous unit made every article anchor resolve to the whole document, so a
phrase quoted from article 6 verified a citation of article 1. These gates
drive both halves of the repair through the production extractor, resolver and
legal-grounding validator: the refusal on a small fixture corpus, and the
corpus-wide property that every article anchor lands on its own article.
"""

from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path
from typing import Final

import pytest

from cadrumo.core.corpus_text import resolve_anchored_extracted_unit
from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.schema_base import EvidenceTier
from cadrumo.domain.calculations.registry.schema_references import LegalReference
from dev.docs.preprocess.normatives_html import extract_html

from ..compiler.legal_grounding import verify_legal_reference_grounding
from .catalogue_verification_support import authored_catalogues

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_PROBE_RELATIVE: Final = "corpus/normatives/html/orden-hac-999-2099.html"

#: A two-article excerpt in the plain-heading shape several bundled excerpts
#: use. The BOE document id makes it BOE-attested evidence for the validator.
_PROBE_EXCERPT: Final = (
    '<!DOCTYPE html>\n<html lang="es">\n<head><meta charset="utf-8">'
    "<title>Orden HAC/999/2099 (BOE-A-2099-99999) - Modelo 999</title></head>\n<body>\n"
    "<p>Orden HAC/999/2099, por la que se aprueba el modelo 999.</p>\n"
    '<div id="a1">\n<h2>Articulo 1. Aprobacion del modelo 999.</h2>\n'
    "<p>Se aprueba el modelo 999 «Declaración informativa de prueba».</p>\n</div>\n"
    '<div id="a6">\n<h2>Articulo 6. Plazo de presentacion.</h2>\n'
    "<p>La presentación se realizará en el mes de enero de cada año.</p>\n</div>\n"
    "</body>\n</html>\n"
)

_ARTICLE_ONE_PHRASE: Final = "Se aprueba el modelo 999"
_ARTICLE_SIX_PHRASE: Final = "se realizará en el mes de enero de cada año"


def _probe_corpus(tmp_path: Path) -> Path:
    """Write the excerpt and its sidecar through the production extractor."""
    source = tmp_path / _PROBE_RELATIVE
    source.parent.mkdir(parents=True)
    source.write_text(_PROBE_EXCERPT, encoding="utf-8", newline="\n")
    extract_html(source, repo_root=tmp_path)
    return source


def _reference(anchor: str, *, required_text: tuple[str, ...]) -> LegalReference:
    return LegalReference(
        id="orden-hac-999-2099:probe",
        evidence_tier=EvidenceTier.LEGAL_AUTHORITY,
        authority="boe",
        kind="orden",
        corpus_ref=f"{_PROBE_RELATIVE}#{anchor}",
        document_id="BOE-A-2099-99999",
        permalink="https://www.boe.es/buscar/act.php?id=BOE-A-2099-99999",
        published_at=date(2099, 1, 2),
        effective_from=date(2099, 1, 3),
        review_status="operator_reviewed",
        reviewed_at=date(2026, 9, 24),
        reviewed_by="operator",
        notes="Probe reference driving article-anchor grounding.",
        required_text=required_text,
    )


def test_a_phrase_quoted_from_another_article_is_refused(tmp_path: Path) -> None:
    """Article 6's wording cannot ground a citation of article 1 of the same orden."""
    _probe_corpus(tmp_path)

    with pytest.raises(RegistryValidationError, match="missing required text"):
        verify_legal_reference_grounding(_reference("a1", required_text=(_ARTICLE_SIX_PHRASE,)), source_root=tmp_path)
    with pytest.raises(RegistryValidationError, match="missing required text"):
        verify_legal_reference_grounding(_reference("a6", required_text=(_ARTICLE_ONE_PHRASE,)), source_root=tmp_path)


def test_each_article_heading_grounds_its_own_body(tmp_path: Path) -> None:
    """The positive half: heading N's unit carries article N's body and verifies it."""
    _probe_corpus(tmp_path)

    verify_legal_reference_grounding(_reference("a1", required_text=(_ARTICLE_ONE_PHRASE,)), source_root=tmp_path)
    verify_legal_reference_grounding(_reference("a6", required_text=(_ARTICLE_SIX_PHRASE,)), source_root=tmp_path)


def test_an_unsplit_excerpt_refuses_an_article_citation(tmp_path: Path) -> None:
    """A sidecar still holding the whole excerpt as one unit refuses instead of widening."""
    source = _probe_corpus(tmp_path)
    sidecar = source.with_name(source.name + ".extracted.json")
    payload = json.loads(sidecar.read_text(encoding="utf-8"))
    payload["units"] = [
        {
            "anchor": None,
            "section": None,
            "title": None,
            "text": "\n".join(f"{unit['title']}\n{unit['text']}" for unit in payload["units"]),
        },
    ]
    sidecar.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    with pytest.raises(RegistryValidationError, match="cannot resolve one corpus unit"):
        verify_legal_reference_grounding(_reference("a1", required_text=(_ARTICLE_SIX_PHRASE,)), source_root=tmp_path)


# --- Corpus-wide: every article anchor lands on its own article ---------------------------

_ORDINALS: Final[dict[str, str]] = {
    "primero": "1",
    "segundo": "2",
    "tercero": "3",
    "cuarto": "4",
    "quinto": "5",
    "sexto": "6",
    "septimo": "7",
    "séptimo": "7",
    "octavo": "8",
    "noveno": "9",
    "decimo": "10",
    "décimo": "10",
}
_QUALIFIER: Final = r"bis|ter|quater|quinquies|sexies|septies|octies|nonies|decies|[a-z]+ies"
#: An anchor spelled as an article fragment: ``a13``, ``art-19``, ``a1-2`` (BOE's
#: own fragment for article 10), ``articulo-primero``. It only decides that the
#: entry cites an article; WHICH article is read from the entry's ``article``.
_ARTICLE_ANCHOR: Final = re.compile(rf"^(?:articulo|art|a)[-_.]?(?:\d|{'|'.join(_ORDINALS)})")
#: The article an entry declares: ``10``, ``13.1.h``, ``163-duovicies``, ``81 bis``.
_DECLARED_ARTICLE: Final = re.compile(
    rf"^(?P<number>\d+|{'|'.join(_ORDINALS)})(?:[\s-]*(?P<qualifier>{_QUALIFIER}))?(?=$|[\s.,-])",
)
_ARTICLE_HEADING_LINE: Final = re.compile(
    rf"^\s*Art[ií]culo\s+(?P<number>\d+|{'|'.join(_ORDINALS)})(?:\s+(?P<qualifier>{_QUALIFIER}))?\s*[.:](?:\s|$)",
    re.IGNORECASE,
)

#: Anti-vacuity floor. 609 article-anchored citations were checked on
#: 2026-09-24; a probe reaching far fewer has stopped reading the catalogue.
_MINIMUM_ARTICLE_CITATIONS: Final = 550


def _article_key(number: str, qualifier: str | None) -> str:
    folded = number.casefold()
    return _ORDINALS.get(folded, folded) + (f" {qualifier.casefold()}" if qualifier else "")


def _requested_article(anchor: str, declared_article: str | None) -> str | None:
    """Return the article an article-anchored entry cites, or ``None`` for any other entry."""
    if declared_article is None or _ARTICLE_ANCHOR.match(anchor.lstrip("#").casefold()) is None:
        return None
    match = _DECLARED_ARTICLE.match(declared_article.strip().casefold())
    return _article_key(match.group("number"), match.group("qualifier")) if match else None


def _heading_articles(text: str) -> list[str]:
    """Every article heading opening a line of ``text``, in order."""
    return [
        _article_key(match.group("number"), match.group("qualifier"))
        for match in map(_ARTICLE_HEADING_LINE.match, text.splitlines())
        if match is not None
    ]


def _lands_on_its_article(sidecar: Path, anchor: str, article: str) -> bool:
    """Whether ``anchor`` resolves to article ``article``'s own unit.

    A titled unit's first line is its heading. A sidecar whose sole unit is
    untitled may be a one-article excerpt, and is accepted only when every
    article heading it carries is the cited one.
    """
    headings = _heading_articles(resolve_anchored_extracted_unit(sidecar, anchor=anchor, include_title=True))
    units = json.loads(sidecar.read_text(encoding="utf-8"))["units"]
    if len(units) == 1 and not units[0].get("title"):
        return headings == [article]
    return bool(headings) and headings[0] == article


def _article_citations() -> list[tuple[str, Path, str, str]]:
    source_root = bundled_path()
    citations: list[tuple[str, Path, str, str]] = []
    for ref_id, reference in sorted(authored_catalogues().legal.items()):
        path_text, _, anchor = reference.corpus_ref.partition("#")
        sidecar = source_root / (path_text + ".extracted.json")
        article = _requested_article(anchor, reference.article)
        if (
            article is None
            or not sidecar.is_file()
            or sidecar.with_name(Path(path_text).name + ".annotation.json").is_file()
        ):
            continue
        citations.append((ref_id, sidecar, anchor, article))
    return citations


def test_every_article_anchor_resolves_to_that_articles_unit() -> None:
    """No legal entry citing an article by anchor is grounded on another article's text."""
    citations = _article_citations()
    assert len(citations) >= _MINIMUM_ARTICLE_CITATIONS, (
        f"only {len(citations)} article citations reached; the probe is not reading the catalogue"
    )

    misplaced = [
        f"{ref_id} -> {sidecar.name}#{anchor} (article {article})"
        for ref_id, sidecar, anchor, article in citations
        if not _lands_on_its_article(sidecar, anchor, article)
    ]

    assert not misplaced, f"{len(misplaced)} article citations do not land on their article: {misplaced[:10]}"


def test_the_article_oracle_rejects_a_neighbouring_article(tmp_path: Path) -> None:
    """Anti-tautology: the corpus-wide oracle must fail a unit holding another article."""
    sidecar = _probe_corpus(tmp_path).with_name(Path(_PROBE_RELATIVE).name + ".extracted.json")

    assert _lands_on_its_article(sidecar, "a1", "1")
    assert not _lands_on_its_article(sidecar, "a6", "1")
    assert _heading_articles("Artículo 113. Ámbito.\nartículo 25.1.f) del texto refundido") == ["113"]

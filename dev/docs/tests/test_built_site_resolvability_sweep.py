"""Kind-agnostic built-site target-resolvability sweep.

This is the coarse cross-kind backstop the ratified
search-record contract mandates: the single gate whose absence let the
pre-LEGAL custom record producers ship dead or self-referential deep links
with no test noticing. Where the existing per-kind parity gates
(``test_glossary_anchor_parity``, ``test_casilla_anchor_parity``,
``test_cli_anchor_parity``) validate each producer against its OWN generator's
RST/render-level anchor inventory -- fast, no full build -- this sweep validates
every injected record against the ACTUALLY BUILT site. It therefore catches what
a per-kind RST-level view structurally cannot:

- a record KIND that grows no per-kind gate (nothing else would notice);
- a destination page dropped from a toctree or that fails to render (the page
  simply is not in the built tree);
- Sphinx slug drift between the RST label and the real rendered HTML ``id``;
- a query-string hand-off masquerading as a destination (D1 bans ``?`` in a
  record target -- the casilla ``search.html?q=`` punt no per-kind gate covers).

Both layers are wanted; this is layer (ii), the ``-n -W`` analogue for
the injection seam. It walks the ONE unified projection funnel the Pagefind
injection consumes (:func:`~dev.docs.pagefind_inject._materialise_records`) --
never a hand re-enumeration of kinds, which would rebuild the exact hardcoding
that caused the CLI break -- and asserts every record's ``target`` resolves
against a real built page and (where a fragment is present) a real element id.

Scope boundary: resolvability ONLY. Destination-grounding coverage (D6 -- does
the page render the record's ``legal_refs``?) is a per-kind assertion living in
the casilla/concept gates and is deliberately NOT duplicated here. This gate
proves the link is not dead; the per-kind gates prove the destination is rich.

The built tree is the run's one user-scope compile
(:func:`~dev.docs.tests.built_site.built_documentation_site`): its English root
is a real ``-b html`` Sphinx build under ``CADRUMO_DOCS_SCOPE=user``, the same
site every other reader of rendered pages shares, so this gate builds nothing of
its own. The user scope excludes the ``api/``/``_modules/`` autodoc tree -- by
far the most expensive part of the build -- which is a PRINCIPLED narrowing, not
a shortcut: no injected record target points under ``api/`` (the CONCEPT,
CASILLA, LEGAL and CLI destinations are the generated glossary, per-modelo
casilla pages, generated legal-reference pages (the LEGAL targets use these
site-relative pages, not authored BOE URLs), and the CLI reference, all outside
``api/``; full-text PAGE hits, which do live under ``api/``, are Pagefind's own
records and are not part of this projection), so excluding it loses no sweep
coverage while it renders the casilla, glossary and generated legal-reference
pages, and CLI destinations in full. That compile is strict, so a nitpick warning
reds the compile gate (``test_docs_build_localized_compile``) and this sweep
reports the same failed build rather than reading a partial tree.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from bs4 import BeautifulSoup

from cadrumo.core.external_constants import OutputLanguage

from ..pagefind_inject import _materialise_records
from .built_site import built_documentation_site

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_core,
    pytest.mark.docs,
]


def _element_ids(page: Path, cache: dict[Path, set[str]]) -> set[str]:
    """Return (memoised) the set of every element ``id`` rendered on a built page."""
    ids = cache.get(page)
    if ids is None:
        soup = BeautifulSoup(page.read_text(encoding="utf-8"), "html.parser")
        ids = {str(element["id"]) for element in soup.find_all(id=True)}
        cache[page] = ids
    return ids


def test_every_injected_record_target_resolves_in_built_site() -> None:
    """Every injected search-record target resolves to a real built page + anchor.

    Walks the unified projection (concept + casilla + legal + CLI records -- the same set
    the Pagefind injection ships) and, against a real user-scope HTML build,
    asserts for every record's ``target`` that: it is not a query-string form
    (D1); the ``<page>.html`` exists under the built tree; and where the target
    carries a ``#fragment``, an element with that id is rendered on that page. A
    failure names the offending record's kind + id + target + which check failed,
    so 274-dead-link-class breaks come back triage-ready, not as a bare count.
    """
    materialised = _materialise_records()
    assert materialised.cli_skipped_reason is None, (
        "CLI projection was skipped -- the sweep would silently drop a whole record kind. "
        f"Reason: {materialised.cli_skipped_reason}"
    )
    records = materialised.records
    assert records, "the unified projection produced no records"

    html_root = built_documentation_site().language_root(OutputLanguage.EN.value)
    id_cache: dict[Path, set[str]] = {}
    failures: list[str] = []
    for record in records:
        target = record.target
        page_part, _, fragment = target.partition("#")
        prefix = f"[{record.kind.value}] {record.id} -> {target!r}: "
        if "?" in target:
            # D1: a query-string hand-off is a search-for-itself, not a
            # destination; it is forbidden as a record target. This is the check
            # that catches the casilla ``search.html?q=`` punt directly.
            failures.append(prefix + "query-string target forbidden (D1: not a destination)")
            continue
        page_file = html_root / page_part.lstrip("/")
        if not page_file.is_file():
            failures.append(prefix + f"page {page_part!r} absent from the built site")
            continue
        if fragment and fragment not in _element_ids(page_file, id_cache):
            failures.append(prefix + f"anchor #{fragment} not rendered on {page_part!r}")

    assert not failures, "injected search records with unresolvable targets in the built site:\n  " + "\n  ".join(
        failures[:60]
    )

    # Guard against a silent empty pass: the projection ships the full concept +
    # casilla + legal + CLI surface (thousands of records), so a near-zero count means the
    # projection collapsed rather than everything genuinely resolving.
    assert len(records) > 200, f"expected the full injected surface (200+ records); walked only {len(records)}"

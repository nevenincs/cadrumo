"""Durable palette-ladder gate: the SHIPPED Ctrl-K palette, in a browser.

The prorrata smoke gate proves the index + injection + ``pf.search`` surface a
concept card; this gate proves the palette's COMPOSE LADDER on top of it -- the
exact behaviour an operator sees when they press Ctrl-K and type. It drives the
real shipped ``docs/_static/cadrumo-docs.js`` (not a re-implementation): opens the
palette, types a query, and reads the rendered ``.cadrumo-palette-item`` rows.

It locks in two invariants found and fixed during the corpus-quality drive
(audit ``2026-06-15-docs-terminology-search``):

* PERF-003 ranking -- every injected concept card carries the flat tier-one
  weight, so a pure weight sort ties them and the exact-term match can sink
  below incidental matches (``iva`` once surfaced VIES first). The palette now
  breaks within-tier ties by relevance, so the exact-term concept leads its
  tier. Asserted: ``iva`` -> the IVA concept is the FIRST palette result and
  ranks ahead of VIES.
* PERF-001 draft-free -- the injected concept set carries only approved
  concepts (drafts 404 against the approved-only glossary), asserted on the
  materialised records the palette renders.

Scope/cost: builds the generated-glossary subset (for the ``#term`` anchors) and
a single trigger page, injects the approved concept cards (no casilla/CLI walk),
and drives one browser -- seconds, ``integration`` marked.
"""

from __future__ import annotations

import io
from pathlib import Path

import pytest

from cadrumo.core.external_constants import OutputLanguage

from ..._paths import REPO_ROOT
from ..glossary_reference import generate_glossary_reference
from ..pagefind_index import build_search_index
from ..pagefind_inject import _inject_records, _Materialised
from ..terminology._concept_cards import project_concept_cards
from ..terminology._search_record import ResultDisplayClass, SearchRecordKind
from ..terminology._unified_record import (
    RankingTier,
    SearchRecord,
    SearchRecordMetadata,
    normalise_display_class_weight,
    to_search_record,
)
from ._http_serve_support import serve_directory

pytestmark = [pytest.mark.integration, pytest.mark.hex_core]

_REPO_ROOT = REPO_ROOT
_DOCS = _REPO_ROOT / "docs"

# A page carrying the palette trigger + the real palette JS, dropped at the
# build root so the palette resolves /pagefind/ against the document base.
_TRIGGER_PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>palette</title></head>
<body>
<button data-cadrumo-search data-cadrumo-search-url="search.html">Search</button>
<script src="_static/cadrumo-docs.js"></script>
</body></html>
"""


# A made-up token present ONLY in these two records' descriptions, absent from
# every concept card, glossary page, and nav title -- so a search for it returns
# exactly the casilla and CLI cards and the D8 ordering (casilla above cli) is
# read cleanly, with the title-match tie-break neutral (neither title carries it).
_MIXED_QUERY_TERM = "zzqcasclitest"


def _casilla_and_cli_records() -> _Materialised:
    """A casilla card + a CLI card sharing one query token (D8 ordering fixture).

    Built directly as unified records with the same display-class base weights
    the injection seam ships (casilla 0.8 > cli 0.7), so the palette must render
    the casilla row ABOVE the cli row -- the D8 amendment that casilla now
    outranks cli. The casilla carries `modelo`/`number`/`segmento` meta so the
    crumb + per-class icon (D6/D7) render on a real casilla shape.
    """
    casilla = SearchRecord(
        id="casilla-record:mixedladdertest",
        kind=SearchRecordKind.CASILLA,
        tier=RankingTier.NAVIGATION,
        title="Modelo 200 · casilla 00562",
        descriptions={
            OutputLanguage.ES: f"{_MIXED_QUERY_TERM} base imponible del ejercicio",
            OutputLanguage.EN: f"{_MIXED_QUERY_TERM} taxable base for the period",
        },
        target="_generated/casillas/200.html#casilla-00562",
        ranking_weight=normalise_display_class_weight(ResultDisplayClass.CASILLA),
        metadata=SearchRecordMetadata(modelo="200", number="00562", segmento="DP200014"),
    )
    cli = SearchRecord(
        id="cli:mixedladdertest",
        kind=SearchRecordKind.CLI,
        tier=RankingTier.NAVIGATION,
        title="aeat app modelo calculate",
        descriptions={
            OutputLanguage.ES: f"{_MIXED_QUERY_TERM} calcula el modelo",
            OutputLanguage.EN: f"{_MIXED_QUERY_TERM} calculate the modelo",
        },
        target="cli/app/modelo.html#aeat-app-modelo-calculate",
        ranking_weight=normalise_display_class_weight(ResultDisplayClass.CLI),
        metadata=SearchRecordMetadata(command_path="aeat app modelo calculate"),
    )
    return _Materialised(records=[casilla, cli], casillas=1, cli_commands=1)


def _approved_concept_records() -> _Materialised:
    """The approved concept cards the production injector ships (no drafts)."""
    from cadrumo.core import ConceptLifecycle

    cards, _ = project_concept_cards()
    approved = [c for c in cards if c.lifecycle is ConceptLifecycle.APPROVED]
    # The invariant the palette renders: nothing draft reaches a card.
    assert approved and all(c.lifecycle is ConceptLifecycle.APPROVED for c in approved)
    records = [to_search_record(c) for c in approved]
    return _Materialised(records=records, concepts=len(records))


def _build_glossary_site(out: Path) -> Path:
    """Build the generated-glossary subset and return the built-HTML root."""
    src = out / "src"
    build = out / "html"
    src.mkdir(parents=True)
    generate_glossary_reference(src)
    (src / "conf.py").write_text(
        'project = "cadrumo-palette"\nextensions = []\nhtml_theme = "basic"\n',
        encoding="utf-8",
    )
    (src / "index.rst").write_text(
        "Palette\n=======\n\n.. toctree::\n\n   _generated/glossary\n",
        encoding="utf-8",
    )
    from sphinx.application import Sphinx

    app = Sphinx(
        str(src),
        str(src),
        str(build),
        str(out / "doctree"),
        "html",
        status=io.StringIO(),
        warning=io.StringIO(),
        freshenv=True,
    )
    app.build()
    return build


def test_palette_ranks_exact_term_concept_first(tmp_path: Path) -> None:
    """Ctrl-K + "iva" -> the IVA concept is the first row, ahead of VIES."""
    out = tmp_path / "site"
    out.mkdir()
    build = _build_glossary_site(out)

    static = build / "_static"
    static.mkdir(parents=True, exist_ok=True)
    for name in ("cadrumo-docs.js", "cadrumo-docs.css"):
        (static / name).write_bytes((_DOCS / "_static" / name).read_bytes())
    (build / "pagefind.yml").write_bytes((_DOCS / "pagefind.yml").read_bytes())
    (build / "palette.html").write_text(_TRIGGER_PAGE, encoding="utf-8")

    materialised = _approved_concept_records()

    async def inject(index: object) -> None:
        await _inject_records(index, materialised, {})  # type: ignore[arg-type]  # ty: ignore[invalid-argument-type]  # reason: pagefind index is dynamically typed

    build_search_index(build, inject=inject)

    with serve_directory(build) as (_httpd, port):
        base = f"http://127.0.0.1:{port}"
        from playwright.sync_api import sync_playwright

        with sync_playwright() as pw:
            browser = pw.chromium.launch()
            page = browser.new_page()
            page.goto(f"{base}/palette.html", wait_until="networkidle")
            # Open the palette and type the query through the real shipped JS.
            page.keyboard.press("Control+k")
            page.locator(".cadrumo-palette-input").fill("iva")
            # Wait until the async Pagefind cards have painted concept rows.
            page.wait_for_function(
                "document.querySelectorAll('.cadrumo-palette-item--concept .cadrumo-palette-item-title').length > 0",
                timeout=15000,
            )
            titles = page.eval_on_selector_all(
                ".cadrumo-palette-item--concept .cadrumo-palette-item-title",
                "els => els.map(e => e.textContent.trim())",
            )
            # Also read the very first rendered row (any kind) to prove the
            # concept leads the whole ladder, not just its own tier.
            first_row = page.eval_on_selector_all(
                ".cadrumo-palette-item .cadrumo-palette-item-title",
                "els => els.length ? els[0].textContent.trim() : ''",
            )
            browser.close()

    assert titles, "no concept rows rendered for 'iva'"
    # The exact-term concept leads its tier (regression: VIES once led).
    assert titles[0] == "IVA", f"expected IVA first, got {titles}"
    if "VIES" in titles:
        assert titles.index("IVA") < titles.index("VIES"), titles
    # And a concept leads the entire palette ladder (cards above nav/full-text).
    assert first_row == "IVA", f"expected IVA as first palette row, got {first_row!r}"


def test_palette_casilla_outranks_cli_and_renders_class_icon(tmp_path: Path) -> None:
    """D8: a casilla card ranks ABOVE a cli card; D7: each renders its class icon.

    Drives the real shipped palette JS over an index carrying exactly one casilla
    and one cli card sharing a query token. The D8 amendment (casilla 0.8 > cli
    0.7, previously cli-above-casilla) is read as the rendered row order, and the
    per-class D7 icon (`display_class` consumed verbatim) is asserted on both
    rows plus the segmento crumb (D6 meta) on the casilla.
    """
    out = tmp_path / "site"
    out.mkdir()
    build = _build_glossary_site(out)

    static = build / "_static"
    static.mkdir(parents=True, exist_ok=True)
    for name in ("cadrumo-docs.js", "cadrumo-docs.css"):
        (static / name).write_bytes((_DOCS / "_static" / name).read_bytes())
    (build / "pagefind.yml").write_bytes((_DOCS / "pagefind.yml").read_bytes())
    (build / "palette.html").write_text(_TRIGGER_PAGE, encoding="utf-8")

    materialised = _casilla_and_cli_records()

    async def inject(index: object) -> None:
        await _inject_records(index, materialised, {})  # type: ignore[arg-type]  # ty: ignore[invalid-argument-type]  # reason: pagefind index is dynamically typed

    build_search_index(build, inject=inject)

    with serve_directory(build) as (_httpd, port):
        base = f"http://127.0.0.1:{port}"
        from playwright.sync_api import sync_playwright

        with sync_playwright() as pw:
            browser = pw.chromium.launch()
            page = browser.new_page()
            page.goto(f"{base}/palette.html", wait_until="networkidle")
            page.keyboard.press("Control+k")
            page.locator(".cadrumo-palette-input").fill(_MIXED_QUERY_TERM)
            # Wait until both injected cards have painted.
            page.wait_for_function(
                "document.querySelectorAll('.cadrumo-palette-item--casilla').length > 0"
                " && document.querySelectorAll('.cadrumo-palette-item--cli').length > 0",
                timeout=15000,
            )
            # The rendered row order (kind modifier per row) decides the ladder.
            row_kinds = page.eval_on_selector_all(
                ".cadrumo-palette-item",
                "els => els.map(e => e.className)",
            )
            # Icons: the shipped display_class drives one class-scoped SVG per row.
            casilla_icon_svgs = page.eval_on_selector_all(
                ".cadrumo-palette-item--casilla .cadrumo-palette-item-icon--casilla svg",
                "els => els.length",
            )
            cli_icon_svgs = page.eval_on_selector_all(
                ".cadrumo-palette-item--cli .cadrumo-palette-item-icon--cli svg",
                "els => els.length",
            )
            casilla_crumb = page.eval_on_selector_all(
                ".cadrumo-palette-item--casilla .cadrumo-palette-item-crumb",
                "els => els.length ? els[0].textContent.trim() : ''",
            )
            browser.close()

    casilla_index = next(
        (i for i, cls in enumerate(row_kinds) if "cadrumo-palette-item--casilla" in cls),
        None,
    )
    cli_index = next(
        (i for i, cls in enumerate(row_kinds) if "cadrumo-palette-item--cli" in cls),
        None,
    )
    assert casilla_index is not None, f"no casilla row rendered: {row_kinds}"
    assert cli_index is not None, f"no cli row rendered: {row_kinds}"
    # D8: casilla (weight 0.8) ranks strictly above cli (weight 0.7).
    assert casilla_index < cli_index, f"casilla did not outrank cli: {row_kinds}"
    # D7: each row rendered its own class icon from the shipped display_class.
    assert casilla_icon_svgs == 1, f"casilla class icon missing: {casilla_icon_svgs}"
    assert cli_icon_svgs == 1, f"cli class icon missing: {cli_icon_svgs}"
    # D6: the segmento the injection seam ships reaches the casilla crumb.
    assert "DP200014" in casilla_crumb, f"segmento not in casilla crumb: {casilla_crumb!r}"

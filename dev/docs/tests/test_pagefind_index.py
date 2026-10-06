"""Real-behaviour tests for the post-build Pagefind index pass.

Exercises the vendored Pagefind binary over a self-contained HTML fixture
(no mocks): the directory pass indexes pages, the whole corpus lands in ONE
index split, the extended binary carries every published language's stemmer,
and the custom-record injection seam works.

Every test here runs the bundled binary over real HTML, so the module is
``integration`` throughout. The config and template assertions that used to
share this file are pure-file checks and now live in ``test_pagefind_config``,
one execution lane per module. None mock Pagefind - the whole point is to prove
the vendored binary runs offline.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from cadrumo.core.directory_scan import DirectoryEntryKind, scan_directory
from cadrumo.core.external_constants import OutputLanguage
from dev._paths import REPO_ROOT

from ..pagefind_index import (
    SHARED_INDEX_LANGUAGE,
    SearchIndexResult,
    await_complete_pagefind_entry,
    build_search_index,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_core]

# dev/docs/tests/test_pagefind_index.py -> parents[3] is the repo root.
_REPO_ROOT = REPO_ROOT
_DOCS = _REPO_ROOT / "docs"

_FIXTURE_PAGE = """<!DOCTYPE html>
<html lang="en">
<head><meta charset="utf-8"><title>{title}</title></head>
<body>
  <nav class="sidebar-tree"><a href="/x">nav noise</a></nav>
  <article role="main" id="furo-main-content">
    <h1>{title}</h1>
    <p>{body}</p>
  </article>
</body>
</html>
"""


def _write_fixture_site(root: Path) -> None:
    """Materialise a tiny built-HTML site."""
    (root / "index.html").write_text(
        _FIXTURE_PAGE.format(
            title="Prorrata",
            body="La prorrata determina el porcentaje de IVA deducible.",
        ),
        encoding="utf-8",
    )
    (root / "casilla.html").write_text(
        _FIXTURE_PAGE.format(
            title="Casilla",
            body="Posicion longitud tipo descripcion del campo del registro.",
        ),
        encoding="utf-8",
    )


def test_index_pass_indexes_built_html(tmp_path: Path) -> None:
    """The post-build pass indexes the fixture pages and writes the index.

    Proves the vendored binary runs offline and emits the chunked index plus
    the Pagefind UI bundle the search page loads.
    """
    _write_fixture_site(tmp_path)

    result = build_search_index(tmp_path)

    assert isinstance(result, SearchIndexResult)
    assert result.page_count == 2
    pf = tmp_path / "pagefind"
    assert pf.is_dir()
    files = {p.name for p in scan_directory(pf, recursive=True, select=DirectoryEntryKind.FILES)}
    # The UI bundle the search.html template references must be emitted.
    assert "pagefind-ui.js" in files
    assert "pagefind-ui.css" in files
    assert "pagefind.js" in files


def test_custom_record_injection_seam_writes_one_index_split(tmp_path: Path) -> None:
    """The injection seam runs and the pass writes ONE index split, not one per language.

    Confirms two contract points at once: the custom-record injection seam is
    callable (records injected via the ``inject`` callback), and the whole
    corpus lands in a single split. The split is the load-bearing half: a
    reader's bundle loads one split, so a record shared by every language is
    reachable from all of them only because there is one -- which is what lets
    the site index each shared record once instead of once per language.
    """
    _write_fixture_site(tmp_path)

    async def inject(index: object) -> None:
        # The custom-record step plugs in here, under the index's own language.
        await index.add_custom_record(  # type: ignore[attr-defined]  # ty: ignore[unresolved-attribute]  # reason: pagefind index is dynamically typed
            url="_generated/glossary.html#term-prorrata",
            content="La prorrata es la regla del porcentaje de IVA deducible.",
            language=SHARED_INDEX_LANGUAGE,
            meta={"title": "prorrata", "kind": "concept"},
            filters={"kind": ["concept"], "language": ["en", "es", "ca", "hu"]},
        )

    result = build_search_index(tmp_path, inject=inject)
    assert result.page_count == 2

    pf = tmp_path / "pagefind"
    languages = {p.name.split("_")[0] for p in scan_directory(pf, pattern="*.pf_index", recursive=True)}
    assert languages == {SHARED_INDEX_LANGUAGE}, languages


@pytest.mark.parametrize("language", sorted(member.value for member in OutputLanguage))
def test_the_vendored_binary_carries_every_published_language_stemmer(tmp_path: Path, language: str) -> None:
    """Each published language's stemmer is in the vendored binary.

    The site's one index is built under a single language, so nothing in the
    production path would notice the Catalan or Hungarian stemmer going missing
    -- and the vendoring of the EXTENDED wheel, rather than the standard one, is
    the reason those stemmers are available at all. Forcing the index to each
    published language in turn and reading back the emitted WASM is what keeps
    that vendoring proven, and it keeps the choice of the shared index language
    a reversible one rather than the only language that still works.
    """
    site = tmp_path / language
    site.mkdir()
    _write_fixture_site(site)

    asyncio.run(_index_forced_to(site, language))

    emitted = {p.name for p in scan_directory(site / "pagefind", recursive=True)}
    assert f"wasm.{language}.pagefind" in emitted, sorted(emitted)


async def _index_forced_to(site: Path, language: str) -> None:
    """Index ``site`` with the language forced, through the real vendored binary."""
    from ..pagefind_service import ResponsivePagefindService

    output = site / "pagefind"
    async with ResponsivePagefindService() as service:
        index = await service.create_index({"output_path": str(output), "force_language": language})
        await index.add_directory(str(site))
        await index.write_files(output_path=str(output))
        await await_complete_pagefind_entry(output / "pagefind-entry.json")

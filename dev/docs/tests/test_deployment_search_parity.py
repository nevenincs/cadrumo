"""Deployment-parity gate: the published site carries the decided search contract.

The defect this gate exists to catch shipped for weeks in plain sight. The
deploy environment set ``CADRUMO_DOCS_PAGEFIND_MODE=pages``, the build read that
and skipped the record-injection seam entirely, and the published index carried
75 rendered pages and not one concept, casilla, or CLI record — while every
search test in the tree stayed green, because they all built in ``full`` mode.
The build was correct, the deployment was not, and nothing compared the two.

So this gate observes the SHIPPED ARTEFACT, never the build configuration. It
resolves the injector from the real deploy environment through the production
resolver, writes a real Pagefind index over real built HTML, and then reads the
record kinds back out of that index through ``pagefind.js`` — the same API the
reader's palette calls. A gate that asserted an environment value instead would
have passed on every day this defect was live.

Cost note: the full corpus is 7,890 records and takes about fifteen minutes to
write, which is long enough that the gate would be deselected in practice and
deselection is its own false green. The injection is therefore bounded to a few
real records per kind. The projections, the injector object, the Pagefind write,
and the artefact read are all the production ones; only the row count is
bounded, and the row count is not the property under test.
"""

from __future__ import annotations

import gzip
import http.server
import json
import shutil
import socketserver
import threading
from functools import partial
from pathlib import Path

import pytest

from dev.deploy.docs_static_site import (
    CANONICAL_DOCS_BASE_URL,
    DeploymentTarget,
    _language_build_environment,
    _localized_languages,
    _public_delivery_checks,
    _site_build_environment,
)
from dev.docs.build import resolve_record_injector
from dev.docs.pagefind_index import build_search_index
from dev.docs.pagefind_inject import InjectionStats

pytestmark = [pytest.mark.integration, pytest.mark.hex_core, pytest.mark.docs]

# dev/docs/tests -> parents[3] is the repo root.
_REPO_ROOT = Path(__file__).resolve().parents[3]
_BUILT_HTML = _REPO_ROOT / "docs" / "_build" / "html"
_PAGEFIND_YML = _REPO_ROOT / "docs" / "pagefind.yml"

#: Record kinds the ADR decides the shipped index carries. A kind absent from
#: the built index means a reader cannot reach that surface at all.
#:
#: This set is the deployment contract's inventory, so it must grow with the
#: contract: the ADR's Update 1 rules a fifth LEGAL kind that no injector emits
#: yet, and the step that builds it must add it here. A gate whose inventory
#: silently lags the contract stops covering the newest surface while still
#: reporting green — the same shape as the defect this module exists to catch.
_DECIDED_RECORD_KINDS = frozenset({"concept", "casilla", "cli"})

#: Real records per kind for the bounded injection (see the module docstring).
_SAMPLE_PER_KIND = 4


def _fixture_site(tmp_path: Path, *, pages: int = 3) -> Path:
    """Copy a small real built-HTML subset plus the real pagefind.yml into tmp."""
    if not _BUILT_HTML.is_dir():
        pytest.fail(
            f"no built documentation HTML at {_BUILT_HTML}; this gate reads the shipped "
            "artefact, so it needs a real build to read. Run the docs build first.",
        )
    site = tmp_path / "site"
    site.mkdir()
    html = sorted(_BUILT_HTML.rglob("*.html"))[:pages]
    if not html:
        pytest.fail(f"built documentation HTML at {_BUILT_HTML} contains no pages.")
    for source in html:
        dest = site / source.relative_to(_BUILT_HTML)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(source, dest)
    shutil.copy(_PAGEFIND_YML, site / "pagefind.yml")
    return site


def _kinds_in_built_index(site: Path) -> dict[str, int]:
    """Return the ``kind`` filter counts read out of the built index by Pagefind.

    Reads through ``pagefind.js`` in a real browser against a real HTTP server:
    the record kinds a reader's palette can actually narrow by, taken from the
    written artefact rather than from the injection's own report.
    """
    handler = partial(http.server.SimpleHTTPRequestHandler, directory=str(site))
    httpd = socketserver.TCPServer(("127.0.0.1", 0), handler)
    port = httpd.server_address[1]
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    try:
        from playwright.sync_api import sync_playwright

        page_name = sorted(p.name for p in site.glob("*.html"))[0]
        with sync_playwright() as pw:
            browser = pw.chromium.launch()
            page = browser.new_page()
            page.goto(f"http://127.0.0.1:{port}/{page_name}", wait_until="networkidle")
            filters = page.evaluate(
                """async () => {
                  const pf = await import('/pagefind/pagefind.js');
                  await pf.options({});
                  await pf.init();
                  return await pf.filters();
                }"""
            )
            browser.close()
    finally:
        httpd.shutdown()
    return dict(filters.get("kind") or {})


def _build_deployed_index(site: Path) -> InjectionStats | None:
    """Build the index the way the DEPLOYMENT would, and return the injection stats.

    The injector comes from the production resolver applied to the real deploy
    build environment, so the mode-to-injector decision under test is the
    deployment's own. ``None`` means the deploy environment injected nothing.
    """
    captured: list[InjectionStats] = []
    injector = resolve_record_injector(
        _REPO_ROOT,
        _site_build_environment(base_environment={}),
        on_complete=captured.append,
        sample_per_kind=_SAMPLE_PER_KIND,
    )
    build_search_index(site, inject=injector)
    return captured[0] if captured else None


def test_deploy_environment_resolves_the_record_injector() -> None:
    """The deploy environment must select record injection, not the pages-only contract.

    The narrow half of the gate: the decision itself, read through the
    production resolver rather than a re-derived copy of its mapping. Necessary
    but not sufficient, which is why the artefact test below is the real gate.
    """
    assert resolve_record_injector(_REPO_ROOT, _site_build_environment(base_environment={})) is not None
    for language in _localized_languages():
        assert resolve_record_injector(_REPO_ROOT, _language_build_environment(language)) is not None, (
            f"localized root {language!r} would deploy without injected search records"
        )


def test_deployed_index_carries_every_decided_record_kind(tmp_path: Path) -> None:
    """Every decided record kind is present in the index the deploy environment builds.

    Read back through Pagefind's own API over the written artefact: this is what
    a reader's palette can find. Under the pages-only contract this list is
    empty, which is exactly the live defect.
    """
    site = _fixture_site(tmp_path)
    stats = _build_deployed_index(site)

    assert stats is not None, "the deploy environment injected no records at all"
    kinds = _kinds_in_built_index(site)

    missing = sorted(_DECIDED_RECORD_KINDS - set(kinds))
    assert not missing, f"the deployed index carries no records of kind(s) {missing}; found {sorted(kinds)}"
    assert all(kinds[kind] > 0 for kind in _DECIDED_RECORD_KINDS)


def test_deployed_pagefind_entry_counts_the_injected_records(tmp_path: Path) -> None:
    """The shipped ``pagefind-entry.json`` reflects pages PLUS injected records.

    The entry file is the one artefact a live check can read over HTTP without a
    browser, so it is worth pinning what it proves: its ``page_count`` counts
    every indexed record, so a full-mode index always exceeds its page count. A
    deployed entry whose count equals the page count is a pages-only index —
    the live site read 75 pages and 75 records' worth of nothing.
    """
    site = _fixture_site(tmp_path, pages=3)
    stats = _build_deployed_index(site)
    assert stats is not None

    entry = json.loads((site / "pagefind" / "pagefind-entry.json").read_bytes().decode("utf-8"))
    languages = entry["languages"]
    assert "en" in languages, f"the built index carries no English split: {sorted(languages)}"

    indexed = languages["en"]["page_count"]
    assert indexed == 3 + stats.custom_records_written, (
        f"entry page_count {indexed} does not equal 3 pages + {stats.custom_records_written} injected records"
    )
    assert indexed > 3, "the entry count shows pages only; no records reached the shipped index"


def test_every_language_root_is_built_and_verified_after_publish() -> None:
    """Each localized root is published under the same contract and checked live.

    The second half of the deployment contract: the record kinds must reach
    every root, not only the English one. The publisher builds each localized
    root, and its post-publish endpoint checks must require each one to answer
    200 — the roots were built but unreachable live for two weeks, so an
    unverified root is the failure mode this pins.
    """
    checks = dict(_public_delivery_checks(DeploymentTarget(bucket="cadrumo-docs-000000000000", distribution_id="E1")))

    assert checks.get(f"{CANONICAL_DOCS_BASE_URL}/") == 200
    for language in _localized_languages():
        url = f"{CANONICAL_DOCS_BASE_URL}/{language}/"
        assert checks.get(url) == 200, f"publish does not verify the {language!r} root is reachable ({url})"


def test_the_gate_reads_the_artefact_not_the_configuration(tmp_path: Path) -> None:
    """The artefact read is grounded in the written index, not the injection report.

    Guards the gate against becoming a tautology of its own build call: the
    fragments written to disk must carry the kinds, so the assertions above
    cannot pass on a report while the artefact is empty.
    """
    site = _fixture_site(tmp_path)
    _build_deployed_index(site)

    fragments = sorted((site / "pagefind" / "fragment").rglob("*.pf_fragment"))
    assert fragments, "the built index wrote no fragments"

    on_disk: set[str] = set()
    for fragment in fragments:
        payload = gzip.decompress(fragment.read_bytes())
        for kind in _DECIDED_RECORD_KINDS:
            if f'"kind":"{kind}"'.encode() in payload or f'"kind": "{kind}"'.encode() in payload:
                on_disk.add(kind)
    assert on_disk >= _DECIDED_RECORD_KINDS, (
        f"kinds {sorted(_DECIDED_RECORD_KINDS - on_disk)} are absent from the written fragments"
    )

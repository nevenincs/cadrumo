"""Publish preflight: a pages-only search index must not reach S3.

The defect this pins shipped for weeks and was caught by reading, not by any
gate. The deploy environment selected the pages-only contract, the published
index carried rendered pages and not one concept, casilla, or CLI record, and
the publish preflight waved it through -- because the preflight asserted that
``.pf_index`` chunks were NON-EMPTY, and a pages-only index is full of
non-empty chunks. Non-emptiness cannot distinguish "indexed nothing" from
"indexed pages and dropped every record", and only the first was being checked.

The build-time parity gate now covers the property in CI. This module covers
the OTHER instrument on the OTHER path: the preflight that runs at publish, the
last check before bytes leave the machine.

Every index here is written by REAL Pagefind over REAL built pages. The
pages-only case is not simulated -- it is a genuine no-injection build, exactly
what the misconfigured deploy produced. Hand-writing fragment bytes would have
repeated a sibling defect from the same day, where a gate that claimed to read
a real artefact built a fixture instead and never touched the surface the
defect lived on.
"""

from __future__ import annotations

import contextlib
import shutil
from pathlib import Path

import pytest
from dev.deploy.docs_static_site import _localized_languages, _require_search_index, _validate_language_roots
from dev.docs.pagefind_index import (
    DECIDED_INJECTED_RECORD_KINDS,
    build_search_index,
    injected_record_kinds_in_index,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_core, pytest.mark.docs]

# dev/deploy/tests -> parents[3] is the repo root.
_REPO_ROOT = Path(__file__).resolve().parents[3]
_BUILT_HTML = _REPO_ROOT / "docs" / "_build" / "html"
_PAGEFIND_YML = _REPO_ROOT / "docs" / "pagefind.yml"

_PAGES = 3


def _page_corpus(tmp_path: Path, name: str) -> Path:
    """Copy a few real built pages plus the real ``pagefind.yml`` into ``name``."""
    if not _BUILT_HTML.is_dir():
        pytest.fail(
            f"no built documentation HTML at {_BUILT_HTML}; this preflight reads a real "
            "artefact, so it needs a real build to read. Run the docs build first.",
        )
    pages = sorted(_BUILT_HTML.glob("*.html"))[:_PAGES]
    if len(pages) < _PAGES:
        pytest.fail(f"need {_PAGES} built pages under {_BUILT_HTML} to assemble a site corpus.")
    site = tmp_path / name
    site.mkdir(parents=True)
    for source in pages:
        (site / source.name).write_bytes(source.read_bytes())
    shutil.copy(_PAGEFIND_YML, site / "pagefind.yml")
    return site


async def _inject_one_record_per_kind(index: object) -> None:
    """Add one real custom record per decided kind through Pagefind's own API.

    The same ``add_custom_record`` seam the production injector writes through.
    The record SHAPE is production's too: ``dev/docs/pagefind_inject`` stamps the
    kind into BOTH ``meta`` and ``filters``, so both are set here. An earlier
    draft set only ``filters`` and passed a reader that happened to look there --
    a record shape production never emits proves nothing about production.

    The row COUNT is not the property under test, so one per kind is enough.
    """
    for kind in sorted(DECIDED_INJECTED_RECORD_KINDS):
        await index.add_custom_record(  # type: ignore[attr-defined]
            url=f"/records/{kind}.html",
            content=f"a real injected {kind} record for the publish preflight proof",
            language="en",
            meta={"kind": kind, "title": f"{kind} record"},
            filters={"kind": [kind]},
        )


def _build_in_place(site: Path, inject: object) -> None:
    """Build ``site``'s index with the CWD held inside the scratch tree.

    The chdir is a containment measure, not decoration.
    :func:`build_search_index` opens ``async with PagefindIndex()``, and the
    context manager's exit performs a SECOND, unpathed ``write_files()`` that
    lands in the process CWD -- so a build run from the repo root deposits a
    ~10,000-file ``pagefind/`` tree there (gitignored, but real). Holding the
    CWD inside the scratch tree keeps this suite from doing that. The
    double-write itself is a pre-existing defect in the build path, reported
    separately; it is not this module's to fix.
    """
    with contextlib.chdir(site.parent):
        build_search_index(site, inject=inject)  # type: ignore[arg-type]


@pytest.fixture(scope="module")
def pages_only_site(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """A REAL Pagefind index built with no injection: pages, zero records."""
    site = _page_corpus(tmp_path_factory.mktemp("pages-only"), "site")
    _build_in_place(site, None)
    return site


@pytest.fixture(scope="module")
def record_bearing_site(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """A REAL Pagefind index carrying one injected record of every decided kind."""
    site = _page_corpus(tmp_path_factory.mktemp("with-records"), "site")
    _build_in_place(site, _inject_one_record_per_kind)
    return site


def test_the_pages_only_index_is_the_shape_the_old_check_waved_through(pages_only_site: Path) -> None:
    """Ground the mutation: this artefact is non-empty AND record-free.

    Without this, a refusal below could be passing for the wrong reason -- an
    index that failed to build at all would also refuse, and would prove
    nothing about the defect. The old check's exact predicate is re-run here to
    show it is still satisfied by the artefact the new check rejects.
    """
    chunks = [c for c in (pages_only_site / "pagefind" / "index").rglob("*.pf_index") if c.stat().st_size > 0]
    assert chunks, "the pages-only build wrote no index chunks; it is broken, not merely record-free"
    assert injected_record_kinds_in_index(pages_only_site) == frozenset()


def test_publish_refuses_a_pages_only_index(pages_only_site: Path) -> None:
    """The preflight REFUSES the real pages-only artefact, naming every missing kind."""
    with pytest.raises(SystemExit) as excinfo:
        _require_search_index(pages_only_site, root_label="Docs build")

    message = str(excinfo.value)
    for kind in sorted(DECIDED_INJECTED_RECORD_KINDS):
        assert kind in message, f"the refusal does not name the missing kind {kind!r}: {message}"
    assert "Docs build" in message


def test_publish_accepts_a_record_bearing_index(record_bearing_site: Path) -> None:
    """The other half of the mutation: a correct artefact passes, unchanged."""
    assert injected_record_kinds_in_index(record_bearing_site) == DECIDED_INJECTED_RECORD_KINDS

    _require_search_index(record_bearing_site, root_label="Docs build")


def test_an_empty_index_is_still_refused(tmp_path: Path) -> None:
    """The pre-existing non-emptiness check is supplemented, never weakened.

    An index that built nothing and an index that dropped every record are
    different failures, and both must refuse.
    """
    site = tmp_path / "empty"
    (site / "pagefind" / "index").mkdir(parents=True)

    with pytest.raises(SystemExit) as excinfo:
        _require_search_index(site, root_label="Docs build")

    assert "no substantive generated index data" in str(excinfo.value)


def test_a_localized_root_is_refused_and_named(tmp_path: Path, pages_only_site: Path) -> None:
    """The localized call site refuses too, and says WHICH root.

    Exercises ``_validate_language_roots`` itself rather than asserting that it
    routes to the shared check -- routing is a decision, and a decision is not
    the surface a reader's search runs against.
    """
    languages = _localized_languages()
    assert languages, "no localized roots configured; this test would prove nothing"

    html_root = tmp_path / "html"
    for language in languages:
        root = html_root / language
        shutil.copytree(pages_only_site, root)
        (root / "index.html").write_text("<html lang='x'><body>root</body></html>", encoding="utf-8")

    with pytest.raises(SystemExit) as excinfo:
        _validate_language_roots(html_root)

    message = str(excinfo.value)
    assert any(f"{language!r}" in message for language in languages), message
    assert "concept" in message


def test_decided_kinds_match_the_canonical_enum() -> None:
    """Hold the literal kind set to the enum it stands for.

    ``DECIDED_INJECTED_RECORD_KINDS`` is spelled as literals because its module
    imports the terminology package lazily. This is what keeps that spelling
    honest: rename or remove a member and this fails.
    """
    from dev.docs.terminology import SearchRecordKind

    assert {kind.value for kind in SearchRecordKind} >= DECIDED_INJECTED_RECORD_KINDS
    assert SearchRecordKind.PAGE.value not in DECIDED_INJECTED_RECORD_KINDS, (
        "PAGE is produced by the directory pass, so requiring it would be satisfied "
        "by exactly the pages-only index this set exists to reject"
    )

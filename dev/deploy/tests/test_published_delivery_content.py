"""Post-publish verification reads what landed, not just that something answered.

The publisher verified delivery with HTTP status codes alone. A status cannot
distinguish a working root from a broken one: a docs root serving a record-free
search index answers 200 on every checked URL. This is the layer that is
supposed to confirm the thing that actually LANDED is correct, and it could only
confirm that something replied.

The artefacts here are real: two genuine Pagefind indexes are built — one with
injected records, one without — and each is served as the published entry. The
network read is injected rather than faked at the socket, so the HTTPS guard on
the production fetch stays intact and the comparison is still exercised end to
end.

"""

from __future__ import annotations

import contextlib
import json
import shutil
from pathlib import Path

import pytest

from cadrumo.core.directory_scan import scan_directory

from ..._paths import REPO_ROOT
from ...docs.pagefind_index import build_search_index
from ..docs_static_site import (
    _assert_served_index_matches_build,
    _localized_languages,
    _verify_published_search_index,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_core, pytest.mark.docs]

# dev/deploy/tests -> parents[3] is the repo root.
_REPO_ROOT = REPO_ROOT
_BUILT_HTML = _REPO_ROOT / "docs" / "_build" / "html"
_PAGEFIND_YML = _REPO_ROOT / "docs" / "pagefind.yml"
_PAGES = 2


def _built_root(tmp_path: Path, name: str, *, with_records: bool) -> Path:
    """Build a real Pagefind index, with or without injected records."""
    pages = list(scan_directory(_BUILT_HTML, pattern="*.html")[:_PAGES]) if _BUILT_HTML.is_dir() else []
    if len(pages) < _PAGES:
        pytest.fail(
            f"need {_PAGES} built pages under {_BUILT_HTML}; this gate compares real indexes, "
            "so it needs a real build to read.",
        )
    site = tmp_path / name
    site.mkdir(parents=True)
    for source in pages:
        (site / source.name).write_bytes(source.read_bytes())
    shutil.copy(_PAGEFIND_YML, site / "pagefind.yml")

    async def _inject(index: object) -> None:
        for kind in ("concept", "casilla", "cli"):
            await index.add_custom_record(  # type: ignore[attr-defined]
                url=f"/records/{kind}.html",
                content=f"a real injected {kind} record",
                language="en",
                meta={"kind": kind},
                filters={"kind": [kind]},
            )

    with contextlib.chdir(site.parent):
        build_search_index(site, inject=(_inject if with_records else None))
    return site


def _entry_bytes(site: Path) -> bytes:
    return (site / "pagefind" / "pagefind-entry.json").read_bytes()


def test_a_record_free_published_index_is_refused(tmp_path: Path) -> None:
    """The mutation: the build carried records, the published root does not.

    Both artefacts are real Pagefind output over the same pages, so the ONLY
    difference is the injected records — which is exactly the defect that
    shipped, and exactly what a status check cannot see.
    """
    built = _built_root(tmp_path, "built", with_records=True)
    published = _built_root(tmp_path, "published", with_records=False)

    with pytest.raises(SystemExit) as excinfo:
        _assert_served_index_matches_build(
            built=built / "pagefind" / "pagefind-entry.json",
            served=_entry_bytes(published),
            label="docs root",
        )

    message = str(excinfo.value)
    assert "does not match the build that was validated" in message
    assert "docs root" in message


def test_the_matching_published_index_passes(tmp_path: Path) -> None:
    """The other half: the index that was built and validated is accepted."""
    built = _built_root(tmp_path, "built", with_records=True)

    _assert_served_index_matches_build(
        built=built / "pagefind" / "pagefind-entry.json",
        served=_entry_bytes(built),
        label="docs root",
    )


def test_the_two_real_indexes_actually_differ(tmp_path: Path) -> None:
    """Ground the mutation: a record-free build really does report a lower count.

    Without this, the refusal above could be passing because the fixtures differ
    for some incidental reason. Comparing the counts directly shows the
    difference is the records.
    """
    with_records = json.loads(_entry_bytes(_built_root(tmp_path, "a", with_records=True)))
    without = json.loads(_entry_bytes(_built_root(tmp_path, "b", with_records=False)))

    total_with = sum(int(split["page_count"]) for split in with_records["languages"].values())
    total_without = sum(int(split["page_count"]) for split in without["languages"].values())
    assert total_with == total_without + 3, f"expected exactly the 3 injected records: {total_with} vs {total_without}"


def test_every_published_root_is_checked_not_only_the_default(tmp_path: Path) -> None:
    """The per-root sweep fetches each localized root's own entry, not just ``/``.

    A localized root serving a record-free index was the second defect in this
    family, so a check that only read the default root would repeat it.
    """
    built = _built_root(tmp_path, "root", with_records=True)
    html_root = tmp_path / "html"
    html_root.mkdir()
    shutil.copytree(built, html_root / "site")
    for language in _localized_languages():
        shutil.copytree(built, html_root / language)
    shutil.copytree(built / "pagefind", html_root / "pagefind")

    requested: list[str] = []

    def _fetch(url: str) -> bytes:
        requested.append(url)
        return _entry_bytes(built)

    _verify_published_search_index(html_root, base_url="https://example.invalid/docs", fetch=_fetch)

    for language in _localized_languages():
        assert any(f"/{language}/pagefind/pagefind-entry.json" in url for url in requested), (
            f"the {language!r} root's own published index was never read: {requested}"
        )

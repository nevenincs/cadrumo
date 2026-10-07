"""The comparison counts what a composed site still differs from its own build in.

Two small sites are written by hand -- one standing for a language's own build,
one for the site composed from the one compile -- with a difference in each kind
of markup a page offers, plus a file only the built site has. The counts and the
contexts they are filed under are stated here.
"""

from __future__ import annotations

import zlib
from pathlib import Path

import pytest

from ..compile_once import IntendedDifference, _per_language_inventory, compare
from ..compile_slots import Rendering, activate, deactivate
from ..message_marks import FRAGMENT_PREFIX

pytestmark = [pytest.mark.unit, pytest.mark.hex_core, pytest.mark.docs]

_BUILT = {
    "index.html": (
        "<head><title>Calendario fiscal</title></head>"
        '<body><h1 id="calendario-fiscal">Calendario fiscal</h1>'
        '<a title="Actividad">Novedades</a>'
        '<script src="_static/chrome.js?v=aaaaaaaa"></script></body>'
    ),
    "notice.html": "<body><p>Ley 37/1992</p></body>",
    "_static/translations.js": "es();",
}
_COMPOSED = {
    "index.html": (
        "<head><title>Calendario fiscal</title></head>"
        '<body><h1 id="filing-calendar">Calendario fiscal</h1>'
        '<a title="Activity">Novedades</a>'
        '<script src="_static/chrome.js?v=bbbbbbbb"></script></body>'
    ),
    "notice.html": "<body><p>Ley 37/1992</p></body>",
}


def _site(root: Path, files: dict[str, str]) -> Path:
    for path, content in files.items():
        target = root.joinpath(*path.split("/"))
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8", newline="")
    return root


def _inventory(entries: list[str]) -> bytes:
    """Return an inventory as Sphinx writes one: a header, then its entries compressed.

    One entry at a time, which is how ``InventoryFile.dump`` feeds its
    compressor, because the deflate stream depends on that.
    """
    compressor = zlib.compressobj(9)
    body = b"".join(compressor.compress(f"{entry}\n".encode()) for entry in entries)
    return (
        b"# Sphinx inventory version 2\n# Project: Cadrumo\n# Version: 0.5.1\n"
        + b"# The remainder of this file is compressed using zlib.\n"
        + body
        + compressor.flush()
    )


def test_each_language_gets_its_own_object_inventory(tmp_path: Path) -> None:
    """The inventory names each page by its title, and a title is a mark.

    The entries are compressed, so nothing in the file looks language
    dependent: stored by the ordinary rule, every language would be given the
    compile's own marks. The expected bytes are the ones a build of each
    language writes, which is what the hand-written inventory states.
    """
    slots = activate(("en", "es"))
    try:
        title = slots.reserve(Rendering.MESSAGE)
        slots.supply(title, ["Filing calendar", "Calendario fiscal"], ["Filing calendar", "Calendario fiscal"])
        compiled = tmp_path / "compiled"
        compiled.mkdir()
        (compiled / "objects.inv").write_bytes(
            _inventory(
                [
                    f"index std:doc -1 index.html {title}",
                    # A fragment document is build scaffolding: its written page
                    # is deleted once the translations on it have been read, and
                    # no language's own build has such a page to name.
                    f"{FRAGMENT_PREFIX}index std:doc -1 {FRAGMENT_PREFIX}index.html <no title>",
                    f"a-label std:label -1 how-to/{FRAGMENT_PREFIX}guide.html#a-label A label",
                ]
            )
        )
        files = {"objects.inv": compiled / "objects.inv"}
        written = _per_language_inventory(files, slots, compiled / "staging")
        assert files == {}, "the compiled inventory is not a fifth inventory the site holds"
        assert written["en"]["objects.inv"].read_bytes() == _inventory(["index std:doc -1 index.html Filing calendar"])
        assert written["es"]["objects.inv"].read_bytes() == _inventory(
            ["index std:doc -1 index.html Calendario fiscal"]
        )
    finally:
        deactivate()


def test_an_inventory_without_the_compressed_entry_header_is_refused(tmp_path: Path) -> None:
    """Nothing can read the titles out of a file whose entries are not where they are."""
    slots = activate(("en", "es"))
    try:
        (tmp_path / "objects.inv").write_bytes(b"# Sphinx inventory version 1\nindex index.html\n")
        with pytest.raises(SystemExit, match="does not carry the compressed-entry header"):
            _per_language_inventory({"objects.inv": tmp_path / "objects.inv"}, slots, tmp_path / "staging")
    finally:
        deactivate()


def test_each_remaining_difference_is_counted_under_the_markup_it_sits_in(tmp_path: Path) -> None:
    """The counts are the remaining work, filed where the work is."""
    found = compare(
        _site(tmp_path / "composed", _COMPOSED),
        _site(tmp_path / "built", _BUILT),
        "es",
    )
    assert (found.pages, found.equal) == (2, 1)
    assert found.missing == ["_static/translations.js"]
    assert found.extra == []
    assert dict(found.by_context) == {"attr:h1.id": 1, "attr:a.title": 1, "attr:script.src": 1}
    assert found.differences == 3
    assert found.intended == {}


def test_a_file_that_is_not_a_page_is_compared_whole(tmp_path: Path) -> None:
    """The search index, the inventory and the sitemap are each a language's own.

    A proof that read only the pages would call a site equal while every
    language was served the compile's own inventory, so what is not a page is
    counted too -- whole, because it holds no markup for a difference to sit in.
    """
    found = compare(
        _site(tmp_path / "composed", {"notice.html": "<p>a</p>", "objects.inv": "composed inventory"}),
        _site(tmp_path / "built", {"notice.html": "<p>a</p>", "objects.inv": "built inventory"}),
        "es",
    )
    assert (found.pages, found.equal) == (1, 1)
    assert dict(found.by_context) == {"file": 1}
    assert found.samples["file"] == [("objects.inv", "15 byte(s)", "18 byte(s)")]


def test_an_equal_site_reports_nothing(tmp_path: Path) -> None:
    """The gate is silent exactly when every page of the language already matches."""
    found = compare(
        _site(tmp_path / "composed", {"notice.html": "<body><p>Ley 37/1992</p></body>"}),
        _site(tmp_path / "built", {"notice.html": "<body><p>Ley 37/1992</p></body>"}),
        "es",
    )
    assert (found.pages, found.equal, found.differences) == (1, 1, 0)
    assert found.report().startswith("es: 1 of 1 page(s) already equal, 0 differing stretch(es)")


def test_a_declared_intended_difference_is_reported_apart_with_its_reason(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A difference kept on purpose must never be folded into the count it would hide in."""
    monkeypatch.setattr(
        "dev.docs.compile_once.INTENDED_DIFFERENCES",
        (
            IntendedDifference(
                context="attr:h1.id",
                page="index.html",
                built="calendario-fiscal",
                reason="the anchor no longer depends on the language",
            ),
        ),
    )
    found = compare(
        _site(tmp_path / "composed", _COMPOSED),
        _site(tmp_path / "built", _BUILT),
        "es",
    )
    assert dict(found.intended) == {"index.html attr:h1.id": 1}
    assert "attr:h1.id" not in found.by_context
    assert found.differences == 2
    assert "intended: the anchor no longer depends on the language" in found.report()


def test_a_declared_difference_covers_the_page_and_the_bytes_it_names_and_no_others(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A markup context covers a whole site, so a declaration must not excuse one.

    The same context on another page, and the same page's own other bytes in
    that context, stay in the count: a declaration excusing them would be a
    standing permission for every later difference of that kind.
    """
    monkeypatch.setattr(
        "dev.docs.compile_once.INTENDED_DIFFERENCES",
        (
            IntendedDifference(
                context="attr:a.title",
                page="other.html",
                built="Actividad",
                reason="another page's",
            ),
            IntendedDifference(
                context="attr:h1.id",
                page="index.html",
                built="something-else",
                reason="the same page's other bytes",
            ),
        ),
    )
    found = compare(
        _site(tmp_path / "composed", _COMPOSED),
        _site(tmp_path / "built", _BUILT),
        "es",
    )
    assert found.intended == {}
    assert found.differences == 3

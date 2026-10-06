"""The comparison counts what a composed site still differs from its own build in.

Two small sites are written by hand -- one standing for a language's own build,
one for the site composed from the one compile -- with a difference in each kind
of markup a page offers, plus a file only the built site has. The counts and the
contexts they are filed under are stated here.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ..compile_once import IntendedDifference, compare

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

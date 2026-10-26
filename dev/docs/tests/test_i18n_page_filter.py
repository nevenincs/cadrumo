"""Scoping contract for the ``--page`` catalogue re-sync filter.

A whole-surface re-sync rewrites catalogue state for every localized page, which
is not usable when one contributor edited two pages and another is mid-edit on a
third. The filter narrows which catalogues a pass may write. These tests pin the
two properties that make it safe: it refuses a page outside the localized
surface rather than silently matching nothing, and it stages exactly the
selected templates for the update.

The second is not a formality. ``sphinx-intl update`` syncs whatever templates
it is pointed at and demotes every message absent from them to obsolete, so a
template tree holding one extra page is a template tree that rewrites that
page's catalogue. The staging step is the whole enforcement.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from dev._paths import REPO_ROOT

from ..i18n import _stage_selected_templates, user_scope_source_pages, validated_pages

pytestmark = [pytest.mark.unit, pytest.mark.hex_core, pytest.mark.docs]


def _authored_page() -> str:
    """Return one page the localized surface really carries."""
    pages = user_scope_source_pages(REPO_ROOT / "docs")
    assert pages, "the localized surface must not be empty"
    return pages[0]


def test_an_authored_page_is_accepted_and_returned_as_a_docpath() -> None:
    page = _authored_page()
    assert validated_pages(REPO_ROOT / "docs", [page]) == (page,)


def test_a_windows_spelling_of_an_authored_page_is_accepted() -> None:
    page = _authored_page()
    assert validated_pages(REPO_ROOT / "docs", [page.replace("/", "\\")]) == (page,)


def test_a_page_outside_the_localized_surface_is_refused() -> None:
    with pytest.raises(SystemExit) as refusal:
        validated_pages(REPO_ROOT / "docs", ["how-to/not-a-real-page.md"])
    assert "how-to/not-a-real-page.md" in str(refusal.value)


def test_a_generated_page_is_refused_like_any_other_unauthored_one() -> None:
    # The API tree is excluded from the localized surface, so naming a page
    # inside it is the same mistake as naming one that does not exist.
    with pytest.raises(SystemExit):
        validated_pages(REPO_ROOT / "docs", ["api/cadrumo.md"])


def test_an_empty_selection_is_refused_rather_than_silently_meaning_everything() -> None:
    with pytest.raises(SystemExit) as refusal:
        validated_pages(REPO_ROOT / "docs", [])
    assert "no pages selected" in str(refusal.value)


def test_staging_copies_only_the_selected_templates(tmp_path: Path) -> None:
    templates = tmp_path / "pot"
    (templates / "how-to").mkdir(parents=True)
    (templates / "how-to" / "wanted.pot").write_text("wanted", encoding="utf-8")
    (templates / "how-to" / "other.pot").write_text("other", encoding="utf-8")
    (templates / "index.pot").write_text("index", encoding="utf-8")
    destination = tmp_path / "staged"
    destination.mkdir()

    _stage_selected_templates(templates, ["how-to/wanted.md"], destination, tmp_path)

    staged = sorted(path.relative_to(destination).as_posix() for path in destination.rglob("*.pot"))
    assert staged == ["how-to/wanted.pot"]


def test_staging_refuses_a_page_with_no_extracted_template(tmp_path: Path) -> None:
    templates = tmp_path / "pot"
    templates.mkdir()
    destination = tmp_path / "staged"
    destination.mkdir()

    with pytest.raises(SystemExit) as refusal:
        _stage_selected_templates(templates, ["how-to/wanted.md"], destination, tmp_path)
    assert "how-to/wanted.md" in str(refusal.value)
    assert not list(destination.rglob("*.pot"))

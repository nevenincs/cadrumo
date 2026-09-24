"""Unit tests for documentation gettext catalogue ownership."""

from __future__ import annotations

import os
from pathlib import Path, PurePosixPath, PureWindowsPath

import pytest
from babel.messages.catalog import Catalog
from babel.messages.pofile import read_po, write_po

from dev._paths import REPO_ROOT

from ..i18n import _EXCLUDED_FILES, prune_orphan_catalogues, relocate_template_locations, sync_catalogue_locations

pytestmark = [pytest.mark.unit, pytest.mark.hex_core, pytest.mark.docs]


def _source(repo_root: Path, page: str, content: str = "# Page\n") -> Path:
    """Create one authored documentation source page."""
    source = repo_root / "docs" / page
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text(content, encoding="utf-8")
    return source


def _catalogue(repo_root: Path, language: str, page: str, content: str) -> Path:
    """Create one language catalogue corresponding to a documentation page."""
    catalogue = repo_root / "docs" / "locales" / language / "LC_MESSAGES" / Path(page).with_suffix(".po")
    catalogue.parent.mkdir(parents=True, exist_ok=True)
    catalogue.write_text(content, encoding="utf-8")
    return catalogue


def test_prune_orphan_catalogues_removes_excluded_and_deleted_pages_without_touching_live_translations(
    tmp_path: Path,
) -> None:
    """Only catalogues with no authored user-scope source page are removed."""
    _source(tmp_path, "index.md")
    _source(tmp_path, "how-to/live.rst")
    _source(tmp_path, "reference/generated.md", "<!-- GENERATED FILE -->\n# Generated\n")
    live_index = _catalogue(tmp_path, "es", "index.md", "live index translation\n")
    live_nested = _catalogue(tmp_path, "es", "how-to/live.rst", "live nested translation\n")
    generated = _catalogue(tmp_path, "es", "reference/generated.md", "generated translation\n")
    deleted = _catalogue(tmp_path, "es", "reference/deleted.md", "deleted translation\n")
    unrelated = tmp_path / "docs" / "locales" / "es" / "LC_MESSAGES" / "notes.txt"
    unrelated.write_text("not a catalogue\n", encoding="utf-8")

    removed = prune_orphan_catalogues(tmp_path, ("es",))

    assert set(removed) == {generated, deleted}
    assert live_index.read_text(encoding="utf-8") == "live index translation\n"
    assert live_nested.read_text(encoding="utf-8") == "live nested translation\n"
    assert unrelated.read_text(encoding="utf-8") == "not a catalogue\n"
    assert not generated.exists()
    assert not deleted.exists()


def test_prune_orphan_catalogues_is_idempotent(tmp_path: Path) -> None:
    """A second cleanup has no files left to remove."""
    _source(tmp_path, "index.md")
    orphan = _catalogue(tmp_path, "es", "removed.md", "orphan translation\n")

    assert prune_orphan_catalogues(tmp_path, ("es",)) == (orphan,)
    assert prune_orphan_catalogues(tmp_path, ("es",)) == ()


@pytest.mark.parametrize(
    "language",
    (
        PurePosixPath("..", "outside").as_posix(),
        str(PureWindowsPath("..", "outside")),
        ".",
        "..",
        str(PureWindowsPath("C:")),
        str(PureWindowsPath(r"C:\outside")),
        PurePosixPath("/outside").as_posix(),
        str(PureWindowsPath(r"\outside")),
    ),
)
def test_prune_orphan_catalogues_rejects_language_path_traversal(tmp_path: Path, language: str) -> None:
    """A language argument cannot redirect cleanup outside its locale tree."""
    outside_catalogue = tmp_path / "docs" / "outside" / "LC_MESSAGES" / "orphan.po"
    outside_catalogue.parent.mkdir(parents=True)
    outside_catalogue.write_text("must remain\n", encoding="utf-8")

    with pytest.raises(ValueError, match="BCP-47 directory token"):
        prune_orphan_catalogues(tmp_path, (language,))

    assert outside_catalogue.read_text(encoding="utf-8") == "must remain\n"


def test_every_declared_file_exclusion_names_a_page_that_exists() -> None:
    """A suppression that suppresses nothing still reads as a reviewed decision.

    The one entry this set used to hold named a docs-root process brief that was
    retired in commit 06e03da6a4. The file went; the exemption stayed, excluding
    nothing. That is precisely the "second registry to fall out of step" the
    generated-marker rule in the same module is written to avoid, so the entries
    are checked against the tree rather than trusted.

    Vacuously true while the set is empty, which is the current and correct
    state; it bites the moment someone adds a name.
    """
    docs_root = REPO_ROOT / "docs"
    assert docs_root.is_dir(), f"no docs tree at {docs_root}; this gate would prove nothing"

    missing = sorted(name for name in _EXCLUDED_FILES if not any(docs_root.rglob(name)))

    assert not missing, (
        "these files are excluded from the localized surface but no longer exist, so the "
        f"exemption is inert and unreviewable: {missing}"
    )


def _write_template(path: Path, locations: list[tuple[str, int]]) -> None:
    """Write one POT template whose single message carries *locations*."""
    catalogue = Catalog()
    catalogue.add("Listed as the `renta-ledger-*` rows.", locations=locations)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as handle:
        write_po(handle, catalogue)


def test_scoped_template_locations_match_the_committed_tree_extraction(tmp_path: Path) -> None:
    """A template extracted anywhere stages with ``../../<docpath>`` locations.

    Sphinx writes a location relative to the directory it extracted into and
    falls back to an absolute path across drives, so a scoped pass extracting
    into a temporary directory leaked machine paths into committed catalogues.
    Both spellings must stage as the committed-tree extraction writes them.
    """
    docs_root = tmp_path / "repo" / "docs"
    source = _source(tmp_path / "repo", "explanation/assembled.md")
    extracted_root = tmp_path / "elsewhere" / "scoped-pot"
    template = extracted_root / "explanation" / "assembled.pot"
    relative_spelling = os.path.relpath(source, extracted_root)
    _write_template(template, [(source.as_posix(), 34), (relative_spelling, 37)])
    staged = tmp_path / "staged" / "explanation" / "assembled.pot"
    staged.parent.mkdir(parents=True)

    relocate_template_locations(template, staged, extracted_root=extracted_root, docs_root=docs_root)

    with staged.open("rb") as handle:
        messages = [message for message in read_po(handle) if message.id]
    assert [message.id for message in messages] == ["Listed as the `renta-ledger-*` rows."]
    assert messages[0].locations == [("../../explanation/assembled.md", 34), ("../../explanation/assembled.md", 37)]
    raw = staged.read_text(encoding="utf-8")
    assert source.as_posix() not in raw
    assert str(tmp_path.as_posix()) not in raw


def test_catalogue_takes_the_template_locations_when_no_msgid_changed(tmp_path: Path) -> None:
    """A leaked location in a committed catalogue is repaired, its translation kept.

    ``sphinx-intl update`` writes a catalogue only when its msgid set changes,
    so a location from another checkout survived every later update.
    """
    docs_root = tmp_path / "docs"
    msgid = "Listed as the `renta-ledger-*` rows."
    templates = tmp_path / "staged"
    _write_template(templates / "explanation" / "assembled.pot", [("../../explanation/assembled.md", 37)])
    leaked = Catalog(locale="es")
    leaked.add(
        msgid, "Las filas `renta-ledger-*`.", locations=[("Y:/code/other-checkout/docs/explanation/assembled.md", 37)]
    )
    catalogue = docs_root / "locales" / "es" / "LC_MESSAGES" / "explanation" / "assembled.po"
    catalogue.parent.mkdir(parents=True)
    with catalogue.open("wb") as handle:
        write_po(handle, leaked)

    assert sync_catalogue_locations(docs_root, templates, ("es",)) == (catalogue,)

    with catalogue.open("rb") as handle:
        repaired = read_po(handle)
    message = repaired.get(msgid)
    assert message is not None
    assert message.locations == [("../../explanation/assembled.md", 37)]
    assert message.string == "Las filas `renta-ledger-*`."
    assert "other-checkout" not in catalogue.read_text(encoding="utf-8")
    assert sync_catalogue_locations(docs_root, templates, ("es",)) == ()

    _write_template(templates / "explanation" / "assembled.pot", [("../../explanation/assembled.md", 40)])
    assert sync_catalogue_locations(docs_root, templates, ("es",)) == (), "a moved line alone rewrote a catalogue"

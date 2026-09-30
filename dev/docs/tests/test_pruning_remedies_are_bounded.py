"""A remedy that deletes the population its gate measures must be bounded.

:mod:`dev.docs.tests.test_docs_catalogue_drift` compares a live population
against a committed artefact and prescribes a remedy that DELETES the artefact
rather than repairing the cause: the documented fix, ``python -m dev.docs.i18n``,
ends in :func:`dev.docs.i18n.prune_orphan_catalogues`, which unlinks catalogues.

The population is derived from an eligibility filter, and a defect that narrows
the filter turns published pages into orphans. The gate then fires exactly
ONCE: the remedy removes the pages, and every later run is green over a smaller
world with no record that the pages existed. That is a ratchet running
backwards — not debt that may only shrink, but evidence that may only shrink.
``docs/locales/*/LC_MESSAGES/*.po`` is unambiguously evidence: the msgstr values
are hand-written translations, and no regeneration restores them.

By contrast two prunes act on genuinely derived trees and are correctly
unbounded, so they are not gated here: :func:`dev.docs.build.remove_orphan_pages`
prunes the BUILT HTML tree, and :meth:`dev.docs.apidocs.manager.ApiStubManager.scaffold`
prunes the ``docs/api/*.rst`` stubs a full build regenerates from the module
tree. The stubs are not committed, so no stub tree records coverage; the
module population a narrowed filter would drop is re-derived independently in
:mod:`dev.docs.tests.test_api_stubs` instead.

Run via::

    uv run --no-sync pytest dev/docs/tests/test_pruning_remedies_are_bounded.py -q
"""

from __future__ import annotations

from pathlib import Path

import pytest

from dev._paths import REPO_ROOT

from ..i18n import (
    MAX_CATALOGUE_REMOVALS_PER_RUN,
    TARGET_LANGUAGES,
    CatalogueRemovalRefusedError,
    prune_orphan_catalogues,
    user_scope_source_pages,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core, pytest.mark.docs]

_DOCS = REPO_ROOT / "docs"


# ── The translation catalogues ───────────────────────────────────────────────


def _catalogue_tree(root: Path, pages: list[str], languages: tuple[str, ...]) -> Path:
    """Materialise a ``docs/`` tree with one source page and catalogue per entry."""
    docs_root = root / "docs"
    for page in pages:
        source = docs_root / page
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_text(f"# {page}\n", encoding="utf-8", newline="\n")
    for language in languages:
        for page in pages:
            catalogue = docs_root / "locales" / language / "LC_MESSAGES" / Path(page).with_suffix(".po")
            catalogue.parent.mkdir(parents=True, exist_ok=True)
            catalogue.write_text(f'msgid "{page}"\nmsgstr "translated"\n', encoding="utf-8", newline="\n")
    return docs_root


def test_a_collapsed_page_authority_is_refused_and_deletes_no_catalogue(tmp_path: Path) -> None:
    """Hand-written translations survive a page authority that stops finding pages.

    The collapse is produced the way it would really occur — the authored source
    pages stop being discoverable while the catalogues remain — and the prune is
    then asked to reconcile the two. Unbounded it empties every language.
    """
    pages = [f"guide/page-{index:02d}.md" for index in range(MAX_CATALOGUE_REMOVALS_PER_RUN + 3)]
    docs_root = _catalogue_tree(tmp_path, pages, TARGET_LANGUAGES)
    catalogues_before = sorted(path.relative_to(docs_root).as_posix() for path in docs_root.rglob("*.po"))
    assert len(catalogues_before) > MAX_CATALOGUE_REMOVALS_PER_RUN

    for page in pages:
        (docs_root / page).unlink()
    assert user_scope_source_pages(docs_root) == [], "the fixture failed to collapse the page authority"

    with pytest.raises(CatalogueRemovalRefusedError) as raised:
        prune_orphan_catalogues(tmp_path)

    assert str(len(catalogues_before)) in str(raised.value)
    assert sorted(path.relative_to(docs_root).as_posix() for path in docs_root.rglob("*.po")) == catalogues_before, (
        "the refused prune still deleted catalogues; a refusal must be atomic across every language"
    )


def test_an_ordinary_page_retirement_still_prunes_its_catalogues(tmp_path: Path) -> None:
    """Retiring one page removes exactly its catalogues, one per target language."""
    pages = ["guide/kept.md", "guide/retired.md"]
    docs_root = _catalogue_tree(tmp_path, pages, TARGET_LANGUAGES)
    (docs_root / "guide" / "retired.md").unlink()

    removed = prune_orphan_catalogues(tmp_path)

    assert len(removed) == len(TARGET_LANGUAGES), f"expected one catalogue per language, removed {len(removed)}"
    assert all(path.name == "retired.po" for path in removed), [path.name for path in removed]
    assert sorted(path.name for path in docs_root.rglob("*.po")) == ["kept.po"] * len(TARGET_LANGUAGES)


def test_the_catalogue_bound_sits_below_the_committed_corpus() -> None:
    """A bound at or above the committed catalogue count would permit total erasure."""
    committed = sorted(path for path in (_DOCS / "locales").rglob("*.po") if "pot" not in path.parts)
    assert committed, f"no committed catalogues found under {_DOCS / 'locales'}; this gate measured nothing"
    assert len(committed) > MAX_CATALOGUE_REMOVALS_PER_RUN, (
        f"the declared bound {MAX_CATALOGUE_REMOVALS_PER_RUN} permits deleting all {len(committed)} "
        "committed catalogues in one pass, which is the failure it exists to refuse"
    )

"""A remedy that deletes the population its gate measures must be bounded.

Two gates under ``dev/docs/`` compare a live population against a committed
artefact and prescribe a remedy that DELETES the artefact rather than repairing
the cause:

- :func:`dev.docs.apidocs.manager.ApiStubManager.check` reports orphan stubs;
  the documented fix, ``python -m dev.docs.apidocs scaffold``, unlinks them.
- :mod:`dev.docs.tests.test_docs_catalogue_drift` reports catalogue drift; the
  documented fix, ``python -m dev.docs.i18n``, ends in
  :func:`dev.docs.i18n.prune_orphan_catalogues`, which unlinks catalogues.

In both, the population is derived from an eligibility filter, and a defect
that narrows the filter turns published pages into orphans. The gate then fires
exactly ONCE: the remedy removes the pages, and every later run is green over a
smaller world with no record that the pages existed. That is a ratchet running
backwards — not debt that may only shrink, but evidence that may only shrink.

The artefacts are not equivalent, and the adjudication matters:

- ``docs/api/*.rst`` LOOKS derived (a generator writes every byte) and ACTS as
  evidence: the committed tree is the only statement of which modules the
  published API reference covers, and a narrowed filter regenerates a smaller
  tree that is internally consistent and silently missing pages.
- ``docs/locales/*/LC_MESSAGES/*.po`` is unambiguously evidence: the msgstr
  values are hand-written translations, and no regeneration restores them.

By contrast :func:`dev.docs.build.remove_orphan_pages` prunes the BUILT HTML
tree, which is genuinely derived — ``docs/`` is the authority and a rebuild
restores it — so it is correctly unbounded and is not gated here.

Run via::

    uv run --no-sync pytest dev/docs/tests/test_pruning_remedies_are_bounded.py -q
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ..._paths import REPO_ROOT
from ..apidocs.manager import (
    MAX_STUB_REMOVALS_PER_RUN,
    ApiStubManager,
    StubRemovalRefusedError,
)
from ..i18n import (
    MAX_CATALOGUE_REMOVALS_PER_RUN,
    TARGET_LANGUAGES,
    CatalogueRemovalRefusedError,
    prune_orphan_catalogues,
    user_scope_source_pages,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core, pytest.mark.docs]

_SRC_CADRUMO = REPO_ROOT / "src" / "cadrumo"
_DOCS = REPO_ROOT / "docs"


class _NarrowedManager(ApiStubManager):
    """A manager whose eligibility rule excludes one extra top-level segment.

    This is how the defect actually arrives: a segment is added to the exclusion
    set and every module beneath it stops being admitted. Subclassing the real
    generator exercises the real discovery, expansion, and scaffold path; no
    production module is patched, and the narrowing lives on the instance.
    """

    def __init__(self, src_cadrumo: Path, docs_api: Path, excluded_segment: str) -> None:
        super().__init__(src_cadrumo=src_cadrumo, docs_api=docs_api)
        self._excluded_segment = excluded_segment

    def excludes_source(self, path: Path) -> bool:
        if self._excluded_segment in path.relative_to(self.src_cadrumo).parts:
            return True
        return super().excludes_source(path)


def _build_source_tree(root: Path, package_sizes: dict[str, int]) -> Path:
    """Materialise a ``src/cadrumo``-shaped tree with the given per-package sizes."""
    src_cadrumo = root / "src" / "cadrumo"
    src_cadrumo.mkdir(parents=True)
    (src_cadrumo / "__init__.py").write_text('"""Root."""\n', encoding="utf-8", newline="\n")
    for package, size in package_sizes.items():
        package_dir = src_cadrumo / package
        package_dir.mkdir()
        (package_dir / "__init__.py").write_text(f'"""{package}."""\n', encoding="utf-8", newline="\n")
        for index in range(size):
            (package_dir / f"module_{index:03d}.py").write_text(
                f'"""{package} module {index}."""\n', encoding="utf-8", newline="\n"
            )
    return src_cadrumo


# ── The stub tree ────────────────────────────────────────────────────────────


def test_a_narrowed_eligibility_rule_is_refused_and_deletes_nothing(tmp_path: Path) -> None:
    """The self-erasing path is refused, and the refusal is atomic.

    Without the bound this run is the whole failure mode in one call: the tree
    is scaffolded clean, the filter narrows, and the very next scaffold reports
    success while deleting every page for the excluded subtree — after which the
    drift gate is permanently green and nothing records the loss.
    """
    src_cadrumo = _build_source_tree(tmp_path, {"kept": 4, "widened": MAX_STUB_REMOVALS_PER_RUN + 5})
    docs_api = tmp_path / "docs" / "api"

    ApiStubManager(src_cadrumo=src_cadrumo, docs_api=docs_api).scaffold()
    before = sorted(path.name for path in docs_api.glob("*.rst"))
    assert len(before) > MAX_STUB_REMOVALS_PER_RUN, (
        f"the fixture scaffolded only {len(before)} stubs, so the refusal below could not be reached"
    )

    narrowed = _NarrowedManager(src_cadrumo, docs_api, excluded_segment="widened")
    doomed = narrowed.check().orphan_stubs
    assert len(doomed) > MAX_STUB_REMOVALS_PER_RUN, (
        f"the narrowing orphaned only {len(doomed)} stub(s); it must exceed the bound to prove the refusal"
    )

    with pytest.raises(StubRemovalRefusedError) as raised:
        narrowed.scaffold()

    assert str(len(doomed)) in str(raised.value), "the refusal must name how many pages it declined to delete"
    assert sorted(path.name for path in docs_api.glob("*.rst")) == before, (
        "the refused run still mutated the stub tree; a refusal must leave it byte-for-byte as it was"
    )


def test_an_ordinary_module_retirement_still_prunes(tmp_path: Path) -> None:
    """The bound must not block real churn, or it will be raised until it does not bind."""
    src_cadrumo = _build_source_tree(tmp_path, {"kept": 6})
    docs_api = tmp_path / "docs" / "api"
    manager = ApiStubManager(src_cadrumo=src_cadrumo, docs_api=docs_api)
    manager.scaffold()

    retired = src_cadrumo / "kept" / "module_000.py"
    assert retired.is_file()
    retired.unlink()

    result = manager.scaffold()

    assert result.removed == 1, f"a single retired module must prune its single stub, got {result.removed}"
    assert result.removed_names == ["cadrumo.kept.module_000.rst"]
    assert not (docs_api / "cadrumo.kept.module_000.rst").exists()


def test_an_explicit_allowance_authorises_a_bulk_retirement(tmp_path: Path) -> None:
    """A deliberate bulk removal is possible, but only as a stated number."""
    src_cadrumo = _build_source_tree(tmp_path, {"kept": 2, "widened": MAX_STUB_REMOVALS_PER_RUN + 5})
    docs_api = tmp_path / "docs" / "api"
    ApiStubManager(src_cadrumo=src_cadrumo, docs_api=docs_api).scaffold()

    narrowed = _NarrowedManager(src_cadrumo, docs_api, excluded_segment="widened")
    doomed = len(narrowed.check().orphan_stubs)

    result = narrowed.scaffold(removal_allowance=doomed)

    assert result.removed == doomed, f"the authorised run removed {result.removed}, not the {doomed} it declared"
    assert narrowed.check().is_conformant


def test_the_declared_bound_separates_churn_from_every_measured_collapse() -> None:
    """The bound is re-derived against the live tree, so the number cannot rot.

    ``MAX_STUB_REMOVALS_PER_RUN`` is only meaningful if it sits below the
    smallest collapse a single narrowing can cause. That figure is a property of
    the current source layout, so it is measured here rather than restated: if a
    future refactor produces a top-level package small enough that excluding it
    falls under the bound, this fails and the bound must come down with it.
    """
    docs_api = REPO_ROOT / "docs" / "api"
    committed = list(docs_api.glob("*.rst"))
    assert len(committed) > 1000, f"only {len(committed)} committed stubs found; this gate measured nothing"

    segments = sorted(
        entry.name
        for entry in _SRC_CADRUMO.iterdir()
        if entry.is_dir() and (entry / "__init__.py").is_file() and not entry.name.startswith("_")
    )
    baseline = len(ApiStubManager(src_cadrumo=_SRC_CADRUMO, docs_api=docs_api).check().orphan_stubs)

    collapses: dict[str, int] = {}
    for segment in segments:
        narrowed = _NarrowedManager(_SRC_CADRUMO, docs_api, excluded_segment=segment)
        collapses[segment] = len(narrowed.check().orphan_stubs) - baseline
    documented = {segment: size for segment, size in collapses.items() if size > 0}
    assert documented, f"excluding any of {segments} orphaned nothing; the widening no longer bites"

    smallest = min(documented.values())
    assert smallest > MAX_STUB_REMOVALS_PER_RUN, (
        f"the declared bound {MAX_STUB_REMOVALS_PER_RUN} no longer sits below the smallest single-segment "
        f"collapse ({smallest}, from excluding {min(documented, key=lambda key: documented[key])!r}). "
        f"Per-segment collapse sizes today: {dict(sorted(documented.items(), key=lambda item: item[1]))}"
    )


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

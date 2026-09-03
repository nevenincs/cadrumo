"""Year-resolved IVA catalogue registry tests."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from shutil import copy2, copytree

import pytest

from ....core.resources.bundled_data import bundled_path
from .._grounding import registry_catalogues
from ..catalogue import bundled_iva_catalogue, iva_catalogue_years, load_iva_catalogue, resolve_catalogue
from ..errors import IvaCatalogueError

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_the_grounded_years_are_derived_from_the_citation_windows() -> None:
    """Coverage comes from the evidence, not from a filename.

    Property, not tally: the assertion is that every grounded year resolves and
    that the set is non-empty, so adding a year's citations widens it without
    editing this test.
    """
    grounded = iva_catalogue_years()

    assert grounded, "the catalogue grounds no year at all; every assertion below would be vacuous"
    for year in sorted(grounded):
        assert resolve_catalogue(on=date(year, 6, 15)) is not None


def test_a_resolved_catalogue_carries_only_citations_asserted_over_that_year() -> None:
    """Projection is the point: a year gets the evidence that speaks to it."""
    year = min(iva_catalogue_years())

    catalogue = resolve_catalogue(on=date(year, 6, 15))

    citations = [citation for regulation in catalogue for citation in regulation.citations]
    assert citations, "the resolved catalogue carries no citations; the projection dropped everything"
    assert all(citation.window.covers_year(year) for citation in citations)


def test_resolving_the_same_year_twice_returns_the_same_projection() -> None:
    assert resolve_catalogue(on=date(2025, 6, 15)) is resolve_catalogue(on=date(2025, 1, 1))


def test_the_undated_corpus_carries_every_citation_regardless_of_span() -> None:
    """The loaded corpus is the whole record; only resolution narrows it."""
    whole = sum(len(regulation.citations) for regulation in bundled_iva_catalogue())
    resolved = sum(
        len(regulation.citations) for regulation in resolve_catalogue(on=date(max(iva_catalogue_years()), 1, 1))
    )

    assert whole >= resolved > 0


def test_resolve_catalogue_requires_a_grounded_year() -> None:
    # The witness year is deliberately OUTSIDE the registry's supported filing
    # window. A supported year used here would assert that a year the product
    # claims to file is permanently ungrounded, pinning today's coverage gap as
    # the contract and reddening the moment that year is correctly added.
    with pytest.raises(IvaCatalogueError, match="year=1990"):
        resolve_catalogue(on=date(1990, 6, 15))


def test_load_iva_catalogue_wraps_missing_path_as_domain_error(tmp_path: Path) -> None:
    missing = tmp_path / "missing-iva-catalogue.toml"

    with pytest.raises(IvaCatalogueError, match=r"cannot stat IVA catalogue"):
        load_iva_catalogue(missing)


def _mutated_catalogue(tmp_path: Path, *, old: str, new: str) -> Path:
    """Copy the committed catalogue and replace one evidence claim."""
    source = bundled_path("registry", "aeat", "iva", "catalogues.toml")
    payload = source.read_text(encoding="utf-8")
    assert old in payload, f"mutation anchor {old!r} disappeared from the bundled catalogue"
    target = tmp_path / "catalogues.toml"
    target.write_text(payload.replace(old, new, 1), encoding="utf-8")
    return target


def test_loader_refuses_an_unknown_legal_reference(tmp_path: Path) -> None:
    target = _mutated_catalogue(
        tmp_path,
        old='legal_reference = "ley-37-1992:art-90"',
        new='legal_reference = "ley-37-1992:art-invented"',
    )

    with pytest.raises(IvaCatalogueError, match="unknown_legal_reference"):
        load_iva_catalogue(target)


def test_loader_refuses_an_unquoted_verified_citation(tmp_path: Path) -> None:
    target = _mutated_catalogue(
        tmp_path,
        old='quoted_text = "Artículo 90. Tipo impositivo general. Uno. El Impuesto se exigirá al tipo del 21 por ciento, salvo lo dispuesto en el artículo siguiente. Dos. El tipo impositivo aplicable a cada operación será el vigente en el momento del devengo. Tres."',
        new='quoted_text = ""',
    )

    with pytest.raises(IvaCatalogueError, match="must carry its verbatim quotation"):
        load_iva_catalogue(target)


def test_loader_refuses_a_verified_quotation_absent_from_its_corpus(tmp_path: Path) -> None:
    target = _mutated_catalogue(
        tmp_path,
        old="El Impuesto se exigirá al tipo del 21 por ciento",
        new="El Impuesto se exigirá al tipo del 25 por ciento",
    )

    with pytest.raises(IvaCatalogueError, match="quotation_absent_from_corpus"):
        load_iva_catalogue(target)


def test_loader_cache_invalidates_after_cited_corpus_evidence_changes(tmp_path: Path) -> None:
    """A green cache entry cannot outlive the corpus bytes it certified."""
    source_root = tmp_path / "source"
    registry_root = source_root / "registry" / "aeat"
    copytree(bundled_path("registry", "aeat", "legal"), registry_root / "legal")
    target = tmp_path / "catalogues.toml"
    copy2(bundled_path("registry", "aeat", "iva", "catalogues.toml"), target)
    legal, _sources, _loaded_root = registry_catalogues(registry_root=registry_root, source_root=source_root)
    for reference_id in {
        citation.legal_reference for regulation in bundled_iva_catalogue() for citation in regulation.citations
    }:
        reference = legal[reference_id]
        corpus_path = bundled_path(*reference.corpus_ref.partition("#")[0].split("/"))
        target_corpus = source_root / reference.corpus_ref.partition("#")[0]
        target_corpus.parent.mkdir(parents=True, exist_ok=True)
        copy2(corpus_path, target_corpus)
        copy2(
            corpus_path.with_name(corpus_path.name + ".extracted.json"),
            target_corpus.with_name(target_corpus.name + ".extracted.json"),
        )

    reference = legal["ley-37-1992:art-90"]
    target_corpus = source_root / reference.corpus_ref.partition("#")[0]
    target_sidecar = target_corpus.with_name(target_corpus.name + ".extracted.json")

    assert load_iva_catalogue(target, registry_root=registry_root, source_root=source_root)

    target_sidecar.write_text(
        target_sidecar.read_text(encoding="utf-8").replace("21 por ciento", "25 por ciento", 1),
        encoding="utf-8",
    )

    with pytest.raises(IvaCatalogueError, match="legal_reference_unverified"):
        load_iva_catalogue(target, registry_root=registry_root, source_root=source_root)

"""Real-behaviour conformance for the chunk-to-target resolution map (ADR D6).

The resolution map wrangles raw RAG sweep hits (path + line range + score) into
typed, linkable targets across the five grounding surfaces -- modelo casillas,
the CLI surface, BOE legal grounding, the codebase API reference, and built
docs pages -- and DROPS+REPORTS any hit it cannot resolve (never shipped
half-mapped). These gates drive real ``src/aeat/_data`` paths and the real
registry/legal authority through the resolver, so each rule is exercised
against the actual on-disk surfaces, not mocks.

No dependency on the live CLI tree walk (transiently peer-broken): the CLI
grounding surface is reached via the generated ``docs/cli/*.rst`` reference
page, and the casilla namespace via the (fast, ~1s) registry projection.
"""

from __future__ import annotations

import pytest

from aeat.domain.calculations.registry import bundled_authority

pytestmark = [pytest.mark.unit, pytest.mark.hex_core, pytest.mark.docs]


@pytest.fixture(scope="module")
def resolver() -> object:
    """Build the resolver once (projects casilla records + legal index)."""
    from dev.docs.terminology._resolution import TargetResolver

    return TargetResolver()


def _hit(path: str, *, score: float = 0.7) -> object:
    from dev.docs.terminology._resolution import ChunkHit

    return ChunkHit(path=path, line_start=1, line_end=20, score=score)


# ---------------------------------------------------------------------------
# Each grounding surface resolves correctly
# ---------------------------------------------------------------------------


def test_casilla_toml_resolves_to_the_casilla_surface(resolver: object) -> None:
    """A real casilla TOML fragment resolves to its modelo's casilla target."""
    from dev.docs.terminology._resolution import GroundingSurface, ResolvedTarget

    path = "src/aeat/_data/registry/aeat/modelos/303/revisions/2009-y-siguientes/casillas/0001-casillas.part-001.toml"
    out = resolver.resolve(_hit(path))  # type: ignore[attr-defined]
    assert isinstance(out, ResolvedTarget)
    assert out.surface is GroundingSurface.CASILLA
    assert out.record.metadata.modelo == "303"
    assert "303" in out.record.target


def test_diseno_sidecar_resolves_to_the_casilla_surface(resolver: object) -> None:
    """A Diseno de Registro sidecar resolves to its modelo's casilla target."""
    from dev.docs.terminology._resolution import GroundingSurface, ResolvedTarget

    path = (
        "src/aeat/_data/corpus/aeat_official/disenos_registro/modelo_036/files/"
        "01-036-diseno-de-registro-del-modelo-m036-03-02-2025-y-siguientes-124-kb-xlsx.xlsx.extracted.md"
    )
    out = resolver.resolve(_hit(path))  # type: ignore[attr-defined]
    assert isinstance(out, ResolvedTarget)
    assert out.surface is GroundingSurface.CASILLA
    assert out.record.metadata.modelo == "036"


def test_normatives_sidecar_resolves_to_the_boe_article_anchor(resolver: object) -> None:
    """A normatives sidecar resolves to the BOE permalink via the legal corpus_ref.

    The legal catalogue's ``corpus_ref`` points at the normatives html path;
    stripping the ``.extracted.md`` suffix recovers that path, and the reverse
    index resolves it to the legal id carrying the BOE permalink + ``#aN``
    article anchor.
    """
    from dev.docs.terminology._resolution import GroundingSurface, ResolvedTarget

    # ley-37-1992:art-104 has corpus_ref corpus/normatives/html/ley-37-1992-art-104.html#a104
    path = "src/aeat/_data/corpus/normatives/html/ley-37-1992-art-104.html.extracted.md"
    out = resolver.resolve(_hit(path))  # type: ignore[attr-defined]
    assert isinstance(out, ResolvedTarget)
    assert out.surface is GroundingSurface.LEGAL
    assert out.record.target.startswith("https://www.boe.es/")
    assert "#a104" in out.record.target
    assert out.record.metadata.legal_refs == ("ley-37-1992:art-104",)


def test_normatives_target_matches_the_catalogue_permalink(resolver: object) -> None:
    """The resolved BOE link equals the legal catalogue's permalink (real authority)."""
    from dev.docs.terminology._resolution import ResolvedTarget

    catalogue = bundled_authority().catalogues.legal
    entry = catalogue["ley-37-1992:art-104"]
    path = "src/aeat/_data/corpus/normatives/html/ley-37-1992-art-104.html.extracted.md"
    out = resolver.resolve(_hit(path))  # type: ignore[attr-defined]
    assert isinstance(out, ResolvedTarget)
    assert out.record.target == entry.permalink


def test_legal_toml_resolves_to_a_legal_target(resolver: object) -> None:
    """A legal catalogue TOML resolves to a legal-grounding target.

    The file declares many provisions under ``[legal."<id>"]`` headers; the
    resolver discovers the catalogue-known ids it declares and resolves to the
    first as the representative legal-grounding link.
    """
    from dev.docs.terminology._resolution import GroundingSurface, ResolvedTarget

    out = resolver.resolve(_hit("src/aeat/_data/registry/aeat/legal/iva.toml"))  # type: ignore[attr-defined]
    assert isinstance(out, ResolvedTarget)
    assert out.surface is GroundingSurface.LEGAL
    assert out.record.target.startswith("https://www.boe.es/")
    assert out.record.metadata.legal_refs  # at least one legal ref carried


def test_code_module_resolves_to_its_api_stub(resolver: object) -> None:
    """A real src/aeat module resolves to its generated API-stub page.

    The codebase grounding surface: ``src/aeat/foo/bar.py`` ->
    ``api/aeat.foo.bar.html`` (the apidocs stub-naming convention).
    """
    from dev.docs.terminology._resolution import GroundingSurface, ResolvedTarget

    out = resolver.resolve(_hit("src/aeat/domain/calculations/registry/_temporal.py"))  # type: ignore[attr-defined]
    assert isinstance(out, ResolvedTarget)
    assert out.surface is GroundingSurface.CODEBASE
    assert out.record.target == "api/aeat.domain.calculations.registry._temporal.html"


def test_package_init_resolves_to_the_package_stub(resolver: object) -> None:
    """A package ``__init__.py`` resolves to the package's dotted stub page."""
    from dev.docs.terminology._resolution import ResolvedTarget

    out = resolver.resolve(_hit("src/aeat/domain/calculations/registry/__init__.py"))  # type: ignore[attr-defined]
    assert isinstance(out, ResolvedTarget)
    assert out.record.target == "api/aeat.domain.calculations.registry.html"


def test_cli_reference_page_resolves_to_the_cli_surface(resolver: object) -> None:
    """A generated CLI-reference page resolves to the CLI grounding surface.

    Reaches the CLI surface WITHOUT the live CLI tree walk: the reference page
    ``docs/cli/app.rst`` links to the built ``cli/app.html`` family page.
    """
    from dev.docs.terminology._resolution import GroundingSurface, ResolvedTarget

    out = resolver.resolve(_hit("docs/cli/app.rst"))  # type: ignore[attr-defined]
    assert isinstance(out, ResolvedTarget)
    assert out.surface is GroundingSurface.CLI
    assert out.record.target == "cli/app.html"


def test_docs_page_resolves_to_its_built_page(resolver: object) -> None:
    """A docs source page resolves to its built HTML page anchor."""
    from dev.docs.terminology._resolution import GroundingSurface, ResolvedTarget

    out = resolver.resolve(_hit("docs/how-to/profile-setup.md"))  # type: ignore[attr-defined]
    assert isinstance(out, ResolvedTarget)
    assert out.surface is GroundingSurface.DOCS
    assert out.record.target == "how-to/profile-setup.html"


# ---------------------------------------------------------------------------
# Dropped + reported — never shipped half-mapped (anti-tautology)
# ---------------------------------------------------------------------------


def test_unknown_path_is_dropped_and_reported(resolver: object) -> None:
    """A junk path matches no rule: it is dropped and reported, not mapped.

    Anti-tautology: a path the map cannot resolve MUST surface in the dropped
    report with a reason, never be silently turned into a target.
    """
    from dev.docs.terminology._resolution import DroppedHit, DropReason

    out = resolver.resolve(_hit("some/random/unmapped/file.xyz"))  # type: ignore[attr-defined]
    assert isinstance(out, DroppedHit)
    assert out.reason is DropReason.UNKNOWN_PATH
    assert "some/random/unmapped/file.xyz" in out.detail


def test_test_surface_is_dropped_as_excluded(resolver: object) -> None:
    """A test/fixture path is dropped as an excluded surface (never indexed)."""
    from dev.docs.terminology._resolution import DroppedHit, DropReason

    out = resolver.resolve(_hit("src/aeat/domain/calculations/registry/tests/test_temporal.py"))  # type: ignore[attr-defined]
    assert isinstance(out, DroppedHit)
    assert out.reason is DropReason.EXCLUDED_SURFACE


def test_casilla_for_unknown_modelo_is_dropped(resolver: object) -> None:
    """A casilla path for a modelo with no projected records is dropped+reported.

    Defence: the path matches the casilla rule but the entity is absent, so it
    is dropped as NO_TARGET_ENTITY rather than half-mapped to nothing.
    """
    from dev.docs.terminology._resolution import DroppedHit, DropReason

    path = "src/aeat/_data/registry/aeat/modelos/999/revisions/2099/casillas/0001-casillas.toml"
    out = resolver.resolve(_hit(path))  # type: ignore[attr-defined]
    assert isinstance(out, DroppedHit)
    assert out.reason is DropReason.NO_TARGET_ENTITY


# ---------------------------------------------------------------------------
# Batch resolution partitions resolved from dropped
# ---------------------------------------------------------------------------


def test_batch_resolution_partitions_resolved_and_dropped() -> None:
    """``resolve_chunk_hits`` partitions resolvable hits from dropped ones."""
    from dev.docs.terminology._resolution import resolve_chunk_hits

    hits = (
        _hit("src/aeat/domain/calculations/registry/_temporal.py"),
        _hit("docs/how-to/profile-setup.md"),
        _hit("totally/unmapped/path.bin"),
    )
    result = resolve_chunk_hits(tuple(hits))  # type: ignore[arg-type]
    assert result.resolved_count == 2
    assert result.dropped_count == 1
    # Every resolved record is a unified SearchRecord with a non-empty target.
    for resolved in result.resolved:
        assert resolved.record.target.strip()
        assert resolved.record.ranking_weight >= 0.0


def test_resolver_reuse_avoids_reprojection() -> None:
    """A pre-built resolver can resolve multiple batches without re-projecting."""
    from dev.docs.terminology._resolution import TargetResolver, resolve_chunk_hits

    shared = TargetResolver()
    first = resolve_chunk_hits((_hit("docs/index.md"),), resolver=shared)  # type: ignore[arg-type]
    second = resolve_chunk_hits((_hit("docs/tutorials/index.md"),), resolver=shared)  # type: ignore[arg-type]
    assert first.resolved_count == 1
    assert second.resolved_count == 1


def test_chunk_hit_and_resolved_target_are_frozen() -> None:
    """The strict-frozen contract on the typed inputs/outputs."""
    from pydantic import ValidationError

    from dev.docs.terminology._resolution import ChunkHit

    hit = ChunkHit(path="docs/index.md", line_start=1, line_end=2, score=0.5)
    with pytest.raises(ValidationError):
        hit.score = 0.9  # type: ignore[misc]

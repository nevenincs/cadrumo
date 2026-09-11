"""Real-behaviour conformance for the chunk-to-target resolution map.

The resolution map wrangles raw RAG sweep hits (path + line range + score) into
typed, linkable targets across the five grounding surfaces -- modelo casillas,
the CLI surface, generated legal-reference pages, the codebase API reference,
and built docs pages -- and DROPS+REPORTS any hit it cannot resolve (never
shipped half-mapped). These gates drive real ``src/cadrumo/_data`` paths, the
Pagefind record projection, and the real registry/legal authority through the
resolver, so each rule is exercised against the actual on-disk surfaces, not
mocks.

The CLI grounding surface is reached via the generated ``docs/cli/*.rst``
reference page and the exact Pagefind projection; the casilla namespace is
reached via the (fast, ~1s) registry projection.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from dev._paths import REPO_ROOT
from dev.registry.compiler.authority import compiled_bundled_authority

from .._resolution import ChunkHit, TargetResolver

pytestmark = [pytest.mark.unit, pytest.mark.hex_core, pytest.mark.docs]


@pytest.fixture(scope="module")
def resolver() -> TargetResolver:
    """Build the resolver once (projects casilla records + legal index)."""
    from .._resolution import TargetResolver

    return TargetResolver()


def _hit(
    path: str,
    *,
    score: float = 0.7,
    line_start: int = 1,
    line_end: int = 20,
) -> ChunkHit:
    return ChunkHit(path=path, line_start=line_start, line_end=line_end, score=score)


# ---------------------------------------------------------------------------
# Each grounding surface resolves correctly
# ---------------------------------------------------------------------------


def test_casilla_toml_resolves_to_the_casilla_surface(resolver: TargetResolver) -> None:
    """A real casilla TOML fragment resolves to its modelo's casilla target."""
    from .._resolution import GroundingSurface, ResolvedTarget

    path = "src/cadrumo/_data/registry/aeat/modelos/303/revisions/2022/casillas/civa.repercutido.general__c22.toml"
    # The first declaration occupies lines 1–13; stopping before the next
    # header keeps the source evidence unambiguous for this individual casilla.
    out = resolver.resolve(_hit(path, line_end=13))
    assert isinstance(out, ResolvedTarget)
    assert out.surface is GroundingSurface.CASILLA
    assert out.record.metadata.modelo == "303"
    assert out.record.metadata.casilla_id == "iva.repercutido.general"
    assert out.record.target == "_generated/casillas/303.html#casilla-iva-repercutido-general"


def test_model_only_diseno_source_is_dropped_without_casilla_locator(
    resolver: TargetResolver,
) -> None:
    """A model-only Diseño workbook hit fails closed without a casilla locator."""
    from .._resolution import DroppedHit, DropReason

    path = (
        "src/cadrumo/_data/corpus/aeat_official/disenos_registro/modelo_036/files/"
        "01-036-diseno-de-registro-del-modelo-m036-03-02-2025-y-siguientes-124-kb-xlsx.xlsx"
    )
    out = resolver.resolve(_hit(path))
    assert isinstance(out, DroppedHit)
    assert out.reason is DropReason.NO_TARGET_ENTITY


def test_normatives_source_resolves_to_the_generated_legal_anchor(resolver: TargetResolver) -> None:
    """A normatives source page resolves to the generated legal-reference target.

    The legal catalogue's ``corpus_ref`` points at the normatives html path;
    the hook-indexed hit path IS that source path, and the reverse index
    resolves it to the legal id carrying the generated page/anchor target and
    BOE permalink provenance.
    """
    from ...legal_reference import legal_reference_target
    from .._resolution import GroundingSurface, ResolvedTarget
    from ..search_record import SearchRecordKind

    # ley-37-1992:art-104 has corpus_ref corpus/normatives/html/ley-37-1992-art-104.html#a104
    catalogue = compiled_bundled_authority().catalogues.legal
    legal_id = "ley-37-1992:art-104"
    entry = catalogue[legal_id]
    path = "src/cadrumo/_data/corpus/normatives/html/ley-37-1992-art-104.html"
    out = resolver.resolve(_hit(path))
    assert isinstance(out, ResolvedTarget)
    assert out.surface is GroundingSurface.LEGAL
    assert out.record.kind is SearchRecordKind.LEGAL
    assert out.record.target == legal_reference_target(
        entry.document_id,
        legal_id,
        article=entry.article,
        section=entry.section,
        corpus_ref=entry.corpus_ref,
        permalink=str(entry.permalink),
    )
    assert out.record.metadata.legal_permalink.startswith("https://www.boe.es/")
    assert out.record.metadata.legal_refs == ("ley-37-1992:art-104",)


def test_normatives_target_uses_generated_legal_reference_and_preserves_permalink(
    resolver: TargetResolver,
) -> None:
    """The target follows the renderer while the catalogue permalink stays provenance."""
    from ...legal_reference import legal_reference_target
    from .._resolution import ResolvedTarget

    catalogue = compiled_bundled_authority().catalogues.legal
    legal_id = "ley-37-1992:art-104"
    entry = catalogue[legal_id]
    path = "src/cadrumo/_data/corpus/normatives/html/ley-37-1992-art-104.html"
    out = resolver.resolve(_hit(path))
    assert isinstance(out, ResolvedTarget)
    assert out.record.target == legal_reference_target(
        entry.document_id,
        legal_id,
        article=entry.article,
        section=entry.section,
        corpus_ref=entry.corpus_ref,
        permalink=str(entry.permalink),
    )
    assert out.record.metadata.legal_permalink == str(entry.permalink)


def test_legal_toml_resolves_to_a_legal_target(resolver: TargetResolver) -> None:
    """An unambiguous legal-table range resolves to a legal-grounding target.

    The source range identifies the first ``[legal."<id>"]`` table in this
    catalogue file. The resolver uses that source evidence to select the
    provision; it never chooses a representative when a range is absent,
    invalid, or overlaps multiple tables.
    """
    from .._resolution import GroundingSurface, ResolvedTarget

    out = resolver.resolve(
        _hit(
            "src/cadrumo/_data/registry/aeat/legal/iva.toml",
            line_start=1,
            line_end=20,
        ),
    )
    assert isinstance(out, ResolvedTarget)
    assert out.surface is GroundingSurface.LEGAL
    assert out.record.kind.value == "legal"
    assert out.record.metadata.legal_id == "orden-eha-789-2010:art-1"
    assert out.record.target.startswith("_generated/legal/")
    assert ".html" in out.record.target
    assert out.record.metadata.legal_permalink
    assert out.record.metadata.legal_refs  # at least one legal ref carried


def test_precise_legal_toml_range_resolves_named_provision_and_preserves_boe_provenance(
    resolver: TargetResolver,
) -> None:
    """A precise legal-table range resolves its generated provision target."""
    from ...legal_reference import legal_reference_target
    from .._resolution import GroundingSurface, ResolvedTarget
    from ..search_record import SearchRecordKind

    path = "src/cadrumo/_data/registry/aeat/legal/atribucion-rentas.toml"
    legal_id = "orden-hap-2250-2015:art-1"
    entry = compiled_bundled_authority().catalogues.legal[legal_id]
    out = resolver.resolve(_hit(path, line_start=2, line_end=19))

    assert isinstance(out, ResolvedTarget)
    assert out.surface is GroundingSurface.LEGAL
    assert out.record.kind is SearchRecordKind.LEGAL
    assert out.record.metadata.legal_id == legal_id
    assert out.record.target == legal_reference_target(
        entry.document_id,
        legal_id,
        article=entry.article,
        section=entry.section,
        corpus_ref=entry.corpus_ref,
        permalink=str(entry.permalink),
    )
    assert out.record.metadata.legal_permalink == str(entry.permalink)
    assert out.record.metadata.legal_refs == (legal_id,)


def test_legal_toml_range_spanning_two_legal_tables_is_dropped(
    resolver: TargetResolver,
) -> None:
    """A range overlapping two legal tables cannot identify one provision."""
    from .._resolution import DroppedHit, DropReason

    path = "src/cadrumo/_data/registry/aeat/legal/atribucion-rentas.toml"
    out = resolver.resolve(_hit(path, line_start=19, line_end=22))

    assert isinstance(out, DroppedHit)
    assert out.reason is DropReason.NO_TARGET_ENTITY


def test_legal_toml_range_in_sources_table_is_dropped(resolver: TargetResolver) -> None:
    """A source-evidence table is not a legal provision target."""
    from .._resolution import DroppedHit, DropReason

    path = "src/cadrumo/_data/registry/aeat/legal/atribucion-rentas.toml"
    out = resolver.resolve(_hit(path, line_start=101, line_end=112))

    assert isinstance(out, DroppedHit)
    assert out.reason is DropReason.NO_TARGET_ENTITY


def test_invalid_legal_toml_source_range_is_dropped(resolver: TargetResolver) -> None:
    """An invalid source line range is never mapped to a legal provision."""
    from .._resolution import DroppedHit, DropReason

    path = "src/cadrumo/_data/registry/aeat/legal/atribucion-rentas.toml"
    out = resolver.resolve(_hit(path, line_start=20, line_end=19))

    assert isinstance(out, DroppedHit)
    assert out.reason is DropReason.NO_TARGET_ENTITY


def test_code_module_resolves_to_its_api_stub(resolver: TargetResolver) -> None:
    """A real src/cadrumo module resolves to its generated API-stub page.

    The codebase grounding surface: ``src/cadrumo/foo/bar.py`` ->
    ``api/cadrumo.foo.bar.html`` (the apidocs stub-naming convention).
    """
    from .._resolution import GroundingSurface, ResolvedTarget

    out = resolver.resolve(_hit("src/cadrumo/domain/calculations/registry/temporal.py"))
    assert isinstance(out, ResolvedTarget)
    assert out.surface is GroundingSurface.CODEBASE
    assert out.record.target == "api/cadrumo.domain.calculations.registry.temporal.html"


def test_package_init_resolves_to_the_package_stub(resolver: TargetResolver) -> None:
    """A package ``__init__.py`` resolves to the package's dotted stub page."""
    from .._resolution import ResolvedTarget

    out = resolver.resolve(_hit("src/cadrumo/domain/calculations/registry/__init__.py"))
    assert isinstance(out, ResolvedTarget)
    assert out.record.target == "api/cadrumo.domain.calculations.registry.html"


def _cli_reference_source(relpath: str) -> Path:
    """Return one generated CLI-reference page, refusing by name when it is unbuilt.

    ``docs/cli`` is a gitignored build product. Read directly, an unbuilt tree
    surfaces as a bare ``FileNotFoundError`` from ``pathlib``, which blames the
    reader rather than naming the tree that was never generated or how to
    generate it. This refuses once, at the read, with both.
    """
    from .._resolution import _require_built_cli_reference

    _require_built_cli_reference(REPO_ROOT)
    path = Path(relpath)
    if not path.is_file():
        pytest.fail(
            f"the generated CLI reference tree is built but does not hold {relpath!r}; "
            "rebuild it with `just docs-build` if the command tree changed",
        )
    return path


def test_cli_navigation_page_is_dropped_without_an_emitted_record(
    resolver: TargetResolver,
) -> None:
    """A navigation-only span of a CLI family page is dropped without a record.

    ``docs/cli/app.rst`` opens with pure navigation prose (an intro paragraph
    and a "Direct commands" heading) before its first individual command
    section -- the family page also renders any command mounted directly on
    the family root, so it is not purely navigation end to end. A hit confined
    to the navigation span above the first command heading is still not a
    Pagefind CLI record target, so the resolver fails closed instead of
    fabricating ``cli/app.html``; valid CLI grounding comes only from emitted
    command/option records with exact page-and-anchor targets.
    """
    from .._resolution import DroppedHit, DropReason

    source_path = _cli_reference_source("docs/cli/app.rst")
    source_lines = source_path.read_text(encoding="utf-8").splitlines()
    first_command_line = next(
        (
            line_number
            for line_number, line in enumerate(source_lines, start=1)
            if line.startswith("aeat ")
            and line_number < len(source_lines)
            and source_lines[line_number] == "-" * len(line)
        ),
        len(source_lines) + 1,
    )
    assert first_command_line > 1, "expected the family page to open with navigation prose before any command"

    out = resolver.resolve(_hit("docs/cli/app.rst", line_end=first_command_line - 1))
    assert isinstance(out, DroppedHit)
    assert out.reason is DropReason.NO_TARGET_ENTITY
    assert "no authoritative CLI search record was emitted" in out.detail
    assert "'cli/app.html'" in out.detail


def test_emitted_cli_option_resolves_to_its_exact_page_anchor(
    resolver: TargetResolver,
) -> None:
    """A real emitted CLI option record resolves through its source page.

    The Pagefind projection is the authoritative CLI record set. Select an
    actual option record from that projection, derive its generated source
    page through the CLI reference router, and feed that on-disk page to the
    resolver as a real ``ChunkHit``. The resolver must preserve the emitted
    record's exact page-and-anchor target and classify it as CLI; it must not
    widen the hit to a family landing page or invent a record.
    """
    from ...cli_reference import cli_reference_page_for_command
    from ...pagefind_inject import materialise_search_records
    from .._resolution import GroundingSurface, ResolvedTarget
    from ..search_record import SearchRecordKind

    projection = materialise_search_records()
    assert projection.cli_skipped_reason is None
    emitted = next(
        (
            record
            for record in projection.records
            if record.kind is SearchRecordKind.CLI
            and record.metadata.command_path
            and record.metadata.option_names
            and "#" in record.target
        ),
        None,
    )
    assert emitted is not None, "the live CLI projection must emit an option with a page anchor"

    command_path = tuple(emitted.metadata.command_path.split(" "))
    page_stem = cli_reference_page_for_command(command_path)
    source_path = _cli_reference_source(f"docs/{page_stem}.rst")

    source_lines = source_path.read_text(encoding="utf-8").splitlines()
    command_locator_line = next(
        line_number
        for line_number, line in enumerate(source_lines, start=1)
        if line == emitted.metadata.command_path
        and line_number < len(source_lines)
        and source_lines[line_number] == "-" * len(line)
    )
    next_command_locator_line = next(
        (
            line_number
            for line_number, line in enumerate(source_lines, start=1)
            if line_number > command_locator_line
            and line.startswith("aeat ")
            and line_number < len(source_lines)
            and source_lines[line_number] == "-" * len(line)
        ),
        len(source_lines) + 1,
    )
    option_line = next(
        line_number
        for line_number, line in enumerate(source_lines, start=1)
        if command_locator_line < line_number < next_command_locator_line
        and line == " / ".join(emitted.metadata.option_names)
    )
    out = resolver.resolve(
        _hit(source_path.as_posix(), line_start=option_line, line_end=option_line + 1),
    )
    assert isinstance(out, ResolvedTarget)
    assert out.surface is GroundingSurface.CLI
    assert out.record.kind is SearchRecordKind.CLI
    assert out.record.target == emitted.target
    assert out.record.metadata.command_path == emitted.metadata.command_path
    assert out.record.metadata.option_names == emitted.metadata.option_names


def test_emitted_nested_cli_command_resolves_to_its_exact_page_anchor(
    resolver: TargetResolver,
) -> None:
    """A real emitted nested command record resolves from its command locator."""
    from ...cli_reference import cli_reference_page_for_command
    from ...pagefind_inject import materialise_search_records
    from .._resolution import GroundingSurface, ResolvedTarget
    from ..search_record import SearchRecordKind

    projection = materialise_search_records()
    assert projection.cli_skipped_reason is None
    emitted = next(
        (
            record
            for record in projection.records
            if record.kind is SearchRecordKind.CLI
            and record.metadata.command_path
            and len(record.metadata.command_path.split()) >= 4
            and not record.metadata.option_names
            and "#" in record.target
        ),
        None,
    )
    assert emitted is not None, "the live CLI projection must emit an anchored nested command"

    command_path = tuple(emitted.metadata.command_path.split())
    page_stem = cli_reference_page_for_command(command_path)
    source_path = _cli_reference_source(f"docs/{page_stem}.rst")
    source_lines = source_path.read_text(encoding="utf-8").splitlines()
    command_locator_line = next(
        line_number
        for line_number, line in enumerate(source_lines, start=1)
        if line == emitted.metadata.command_path
        and line_number < len(source_lines)
        and source_lines[line_number] == "-" * len(line)
    )

    out = resolver.resolve(
        _hit(source_path.as_posix(), line_start=command_locator_line, line_end=command_locator_line),
    )
    assert isinstance(out, ResolvedTarget)
    assert out.surface is GroundingSurface.CLI
    assert out.record.kind is SearchRecordKind.CLI
    assert out.record.target == emitted.target
    assert out.record.metadata.command_path == emitted.metadata.command_path
    assert out.record.metadata.option_names == emitted.metadata.option_names


def test_cli_output_schema_prose_is_dropped_without_a_parameter_locator(
    resolver: TargetResolver,
) -> None:
    """A command's help prose is not a command or parameter source locator.

    Per-command output-schema prose was retired from the generated reference
    (the schema registry now lives only on the standalone ``schemas.rst``
    page); the surviving prose between a command's heading and its
    ``Parameters`` block is the command's own help text. It is real content on
    the page but carries no exact command-or-option locator of its own, so a
    hit confined to it must still drop.
    """
    from .._resolution import DroppedHit, DropReason

    source_path = _cli_reference_source("docs/cli/app/diagnostics.rst")
    source_lines = source_path.read_text(encoding="utf-8").splitlines()
    command_locator_line = next(
        line_number
        for line_number, line in enumerate(source_lines, start=1)
        if line == "aeat app diagnostics errors"
        and line_number < len(source_lines)
        and source_lines[line_number] == "-" * len(line)
    )
    help_prose_line = next(
        line_number
        for line_number, line in enumerate(source_lines, start=1)
        if line_number > command_locator_line + 1 and line.strip() and line != "Parameters"
    )

    out = resolver.resolve(
        _hit(
            source_path.as_posix(),
            line_start=help_prose_line,
            line_end=help_prose_line,
        ),
    )
    assert isinstance(out, DroppedHit)
    assert out.reason is DropReason.NO_TARGET_ENTITY
    assert "identify no CLI command or option locator" in out.detail


def test_cli_source_range_past_file_end_is_dropped(resolver: TargetResolver) -> None:
    """A CLI locator range beyond the real source file cannot resolve.

    The reference is split per family/verb-group, so no single page is a
    fixed size; the longest generated page is derived from the live tree
    (rather than a hardcoded page name) so this probe survives a future
    re-split.
    """
    from .._resolution import DroppedHit, DropReason, _require_built_cli_reference

    _require_built_cli_reference(REPO_ROOT)
    pages = tuple((REPO_ROOT / "docs" / "cli").rglob("*.rst"))
    assert pages, "the generated CLI reference tree must hold at least one page"
    longest_page = max(pages, key=lambda page: len(page.read_text(encoding="utf-8").splitlines()))
    source_line_count = len(longest_page.read_text(encoding="utf-8").splitlines())
    assert source_line_count >= 500, (
        f"expected the longest generated CLI page to carry substantial real content; "
        f"{longest_page.relative_to(REPO_ROOT).as_posix()!r} is only {source_line_count} lines"
    )

    source_relpath = longest_page.relative_to(REPO_ROOT).as_posix()
    out = resolver.resolve(
        _hit(source_relpath, line_start=source_line_count, line_end=9999),
    )
    assert isinstance(out, DroppedHit)
    assert out.reason is DropReason.NO_TARGET_ENTITY
    assert f"source length of {source_line_count} lines" in out.detail


def test_ambiguous_cli_source_range_is_dropped(resolver: TargetResolver) -> None:
    """A range spanning two generated parameters cannot pick one CLI record."""
    from .._resolution import DroppedHit, DropReason

    source_path = _cli_reference_source("docs/cli/app/diagnostics.rst")
    source_lines = source_path.read_text(encoding="utf-8").splitlines()
    command_locator_line = next(
        line_number
        for line_number, line in enumerate(source_lines, start=1)
        if line == "aeat app diagnostics errors"
        and line_number < len(source_lines)
        and source_lines[line_number] == "-" * len(line)
    )
    next_command_locator_line = next(
        (
            line_number
            for line_number, line in enumerate(source_lines, start=1)
            if line_number > command_locator_line
            and line.startswith("aeat ")
            and line_number < len(source_lines)
            and source_lines[line_number] == "-" * len(line)
        ),
        len(source_lines) + 1,
    )
    # A declaration line is unindented and its second following line is one of
    # the generator's four fixed classification strings -- the generator
    # always renders a parameter as declaration / description / classification.
    classifications = {"Argument, required.", "Argument, optional.", "Option, required.", "Option, optional."}
    parameter_lines = [
        line_number
        for line_number, line in enumerate(source_lines, start=1)
        if command_locator_line < line_number < next_command_locator_line
        and line
        and not line.startswith(" ")
        and line_number + 1 < len(source_lines)
        and source_lines[line_number + 1].strip() in classifications
    ]
    assert len(parameter_lines) >= 2

    out = resolver.resolve(
        _hit(
            source_path.as_posix(),
            line_start=parameter_lines[0],
            line_end=parameter_lines[1],
        ),
    )
    assert isinstance(out, DroppedHit)
    assert out.reason is DropReason.NO_TARGET_ENTITY
    assert "multiple CLI source locators" in out.detail


def test_docs_page_resolves_to_its_built_page(resolver: TargetResolver) -> None:
    """A docs source page resolves to its built HTML page anchor."""
    from .._resolution import GroundingSurface, ResolvedTarget

    out = resolver.resolve(_hit("docs/how-to/profile-setup.md"))
    assert isinstance(out, ResolvedTarget)
    assert out.surface is GroundingSurface.DOCS
    assert out.record.target == "how-to/profile-setup.html"


# ---------------------------------------------------------------------------
# Dropped + reported — never shipped half-mapped (anti-tautology)
# ---------------------------------------------------------------------------


def test_unknown_path_is_dropped_and_reported(resolver: TargetResolver) -> None:
    """A junk path matches no rule: it is dropped and reported, not mapped.

    Anti-tautology: a path the map cannot resolve MUST surface in the dropped
    report with a reason, never be silently turned into a target.
    """
    from .._resolution import DroppedHit, DropReason

    out = resolver.resolve(_hit("some/random/unmapped/file.xyz"))
    assert isinstance(out, DroppedHit)
    assert out.reason is DropReason.UNKNOWN_PATH
    assert "some/random/unmapped/file.xyz" in out.detail


def test_test_surface_is_dropped_as_excluded(resolver: TargetResolver) -> None:
    """A test/fixture path is dropped as an excluded surface (never indexed)."""
    from .._resolution import DroppedHit, DropReason

    out = resolver.resolve(_hit("src/cadrumo/domain/calculations/registry/tests/test_temporal.py"))
    assert isinstance(out, DroppedHit)
    assert out.reason is DropReason.EXCLUDED_SURFACE


def test_casilla_for_unknown_modelo_is_dropped(resolver: TargetResolver) -> None:
    """A casilla path for a modelo with no projected records is dropped+reported.

    Defence: the path matches the casilla rule but the entity is absent, so it
    is dropped as NO_TARGET_ENTITY rather than half-mapped to nothing.
    """
    from .._resolution import DroppedHit, DropReason

    path = "src/cadrumo/_data/registry/aeat/modelos/999/revisions/2099/casillas/0001-casillas.toml"
    out = resolver.resolve(_hit(path))
    assert isinstance(out, DroppedHit)
    assert out.reason is DropReason.NO_TARGET_ENTITY


# ---------------------------------------------------------------------------
# Batch resolution partitions resolved from dropped
# ---------------------------------------------------------------------------


def test_batch_resolution_partitions_resolved_and_dropped() -> None:
    """``resolve_chunk_hits`` partitions resolvable hits from dropped ones."""
    from .._resolution import resolve_chunk_hits

    hits = (
        _hit("src/cadrumo/domain/calculations/registry/temporal.py"),
        _hit("docs/how-to/profile-setup.md"),
        _hit("totally/unmapped/path.bin"),
    )
    result = resolve_chunk_hits(tuple(hits))
    assert result.resolved_count == 2
    assert result.dropped_count == 1
    # Every resolved record is a unified SearchRecord with a non-empty target.
    for resolved in result.resolved:
        assert resolved.record.target.strip()
        assert resolved.record.ranking_weight >= 0.0


def test_resolver_reuse_avoids_reprojection() -> None:
    """A pre-built resolver can resolve multiple batches without re-projecting."""
    from .._resolution import TargetResolver, resolve_chunk_hits

    shared = TargetResolver()
    first = resolve_chunk_hits((_hit("docs/index.md"),), resolver=shared)
    second = resolve_chunk_hits((_hit("docs/how-to/quickstart.md"),), resolver=shared)
    assert first.resolved_count == 1
    assert second.resolved_count == 1


def _write_cli_pages(root: Path, count: int) -> None:
    """Write ``count`` generator-shaped pages into a checkout root's docs/cli tree."""
    tree = root / "docs" / "cli"
    tree.mkdir(parents=True, exist_ok=True)
    for index in range(count):
        (tree / f"page{index}.rst").write_text(
            f"page{index}\n=======\n\n**Command path:** ``aeat app page{index}``\n",
            encoding="utf-8",
        )


def test_absent_generated_cli_reference_tree_is_refused_not_dropped(tmp_path: Path) -> None:
    """An unbuilt docs/cli tree refuses by name; it does not become a per-hit drop.

    docs/cli is a gitignored build product, so a clean checkout does not have
    it. Without this refusal every CLI hit read through it fails alike and is
    reported as an ordinary unresolvable hit -- an absent input laundered into
    a corpus finding, which is the failure this gate exists to make impossible.
    """
    from .._resolution import UnbuiltGeneratedInputError, _require_built_cli_reference

    with pytest.raises(UnbuiltGeneratedInputError) as refusal:
        _require_built_cli_reference(tmp_path)
    message = str(refusal.value)
    assert "docs/cli" in message, "the refusal must name the root that is missing"
    assert "just docs-build" in message, "the refusal must name the remedy that writes it"


def test_short_generated_cli_reference_tree_is_refused_like_an_absent_one(tmp_path: Path) -> None:
    """A one-page docs/cli tree is a partial artefact and is refused too.

    An interrupted or partial generator run leaves a tree that exists and reads
    cleanly, so an existence check alone passes over it while every hit outside
    the single emitted page still drops. Short and absent fail the same way and
    are refused the same way.
    """
    from .._resolution import UnbuiltGeneratedInputError, _require_built_cli_reference

    _write_cli_pages(tmp_path, 1)
    with pytest.raises(UnbuiltGeneratedInputError) as refusal:
        _require_built_cli_reference(tmp_path)
    assert "1 page(s)" in str(refusal.value)


def test_a_complete_generated_cli_reference_tree_is_accepted(tmp_path: Path) -> None:
    """The refusal has to let a real generator run through, or it proves nothing."""
    from .._resolution import _MIN_CLI_REFERENCE_PAGES, _require_built_cli_reference

    _write_cli_pages(tmp_path, _MIN_CLI_REFERENCE_PAGES)
    _require_built_cli_reference(tmp_path)


def test_chunk_hit_and_resolved_target_are_frozen() -> None:
    """The strict-frozen contract on the typed inputs/outputs."""
    from pydantic import ValidationError

    from .._resolution import ChunkHit

    hit = ChunkHit(path="docs/index.md", line_start=1, line_end=2, score=0.5)
    with pytest.raises(ValidationError):
        hit.score = 0.9  # type: ignore[misc]

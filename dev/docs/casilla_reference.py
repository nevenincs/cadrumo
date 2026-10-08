"""Render and publish per-modelo casilla-reference pages from the typed registry."""

from __future__ import annotations

from collections import OrderedDict
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING

from cadrumo.core.directory_scan import scan_directory
from dev._paths import REPO_ROOT, UTF_8
from dev.registry.compiler.authority import compiled_bundled_authority
from dev.registry.compiler.authority_state import compiler_generation

from .casilla_display import _display_language
from .casilla_legal_grounding import _legal_links
from .casilla_page_rendering import _render_index, _render_modelo_page
from .casilla_reference_models import CasillaPage, CasillaReferenceError, CasillaReferenceResult, CompiledSchema
from .casilla_schema_compilation import compile_schema
from .terminology.casilla_anchor import CASILLA_REFERENCE_DIR
from .terminology.casilla_projection import project_casilla_search_records
from .terminology.search_record import CasillaSearchRecord

if TYPE_CHECKING:
    from cadrumo.core.external_constants import OutputLanguage


def _repo_root() -> Path:
    """The repository checkout this dev-side module lives in."""
    return REPO_ROOT


def render_casilla_reference(
    repo_root: Path,
    records: tuple[CasillaSearchRecord, ...] | None = None,
    *,
    language: OutputLanguage | None = None,
    schema: CompiledSchema | None = None,
) -> CasillaReferenceResult:
    """Render every modelo's casilla reference page and the index.

    Args:
        repo_root: Repository root (for the legal-catalogue read).
        records: Optional pre-projected casilla records; defaults to the full
            registry projection. Injectable so the parity gate and a narrowed
            test can drive the same renderer deterministically.
        language: The one language the pages render in; defaults to the build
            language signal so a localized build is single-language end to end.
        schema: Optional pre-compiled schema facts; defaults to compiling them
            from the bundled authority. Pass :data:`EMPTY_SCHEMA` to render from
            the records alone with no registry read.

    Returns:
        A :class:`CasillaReferenceResult` with one :class:`CasillaPage` per
        modelo, the index page path, and the render counts.
    """
    resolved_language = language if language is not None else _display_language()
    links = _legal_links(repo_root.resolve(), resolved_language)
    resolved = records if records is not None else project_casilla_search_records()[0]
    resolved_schema = schema if schema is not None else compile_schema(resolved, resolved_language)

    by_modelo: OrderedDict[str, list[CasillaSearchRecord]] = OrderedDict()
    for record in resolved:
        by_modelo.setdefault(record.modelo.value, []).append(record)

    pages: list[CasillaPage] = []
    legal_links = 0
    casilla_count = 0
    for modelo in sorted(by_modelo):
        page, page_legal_links = _render_modelo_page(
            modelo,
            tuple(by_modelo[modelo]),
            links,
            resolved_language,
            resolved_schema,
        )
        pages.append(page)
        legal_links += page_legal_links
        casilla_count += len(page.anchors)

    index_relpath = f"{CASILLA_REFERENCE_DIR}/index.rst"
    return CasillaReferenceResult(
        pages=tuple(pages),
        index_relpath=index_relpath,
        modelo_count=len(pages),
        casilla_count=casilla_count,
        legal_links=legal_links,
    )


def generate_casilla_reference(docs_root: Path, *, repo_root: Path | None = None) -> CasillaReferenceResult:
    """Materialise the generated casilla reference pages under ``docs_root/_generated/``.

    Mirrors :func:`~dev.docs.glossary_reference.generate_glossary_reference`: it
    renders every modelo page plus the toctree index and writes them to the
    generated (gitignored, uncommitted) location, returning a summary. Wired at
    the ``builder-inited`` seam so the pages exist before Sphinx reads the tree.

    ``docs_root`` may be an isolated copy used by a sandboxed build, so the
    source repository (needed for the legal-catalogue read) must be
    independently selectable, mirroring
    :func:`~dev.docs.legal_reference.generate_legal_reference`.

    Args:
        docs_root: The documentation root (the directory holding ``index.md``).
        repo_root: Repository root for the legal-catalogue read. Defaults to
            this dev-side module's own checkout.

    Returns:
        A :class:`CasillaReferenceResult` summarising the render.
    """
    repo_root = (repo_root if repo_root is not None else _repo_root()).resolve()
    language = _display_language()
    # Compile first, then read the generation: compiling is what advances it, so
    # reading it first would file this render under the previous generation.
    compiled_bundled_authority()
    result, index_rst = _bundled_reference(repo_root, language, compiler_generation())
    out_dir = docs_root / CASILLA_REFERENCE_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    index_path = out_dir / "index.rst"
    _write_if_changed(index_path, index_rst)
    for page in result.pages:
        _write_if_changed(docs_root / page.output_relpath, page.rst)
    _remove_generated_rst(
        out_dir,
        keep=frozenset({index_path, *(docs_root / page.output_relpath for page in result.pages)}),
    )
    return result


@lru_cache(maxsize=4)
def _bundled_reference(
    repo_root: Path,
    language: OutputLanguage,
    registry_generation: int,
) -> tuple[CasillaReferenceResult, str]:
    """Render the whole bundled reference once per (root, language, registry).

    The render is a pure function of the bundled registry, the legal catalogue
    under ``repo_root`` and the build language, and every page it returns is
    frozen, so the rendered bytes are memoised and only the write and prune below
    repeat. That is what the pruning contract is about -- which files a render
    owns, and which residue it removes -- and those still run on every call; what
    no longer repeats is recompiling fifty-nine pages to produce identical bytes.

    Args:
        repo_root: Repository root for the legal-catalogue read.
        language: The one language the pages render in.
        registry_generation: :func:`~dev.registry.compiler.authority_state.compiler_generation`
            observed after the bundled authority was compiled, so an edit to any
            registry source, or a compiler reset, rerenders.

    Returns:
        The render result and the rendered toctree index page.
    """
    records = project_casilla_search_records()[0]
    schema = compile_schema(records, language)
    result = render_casilla_reference(repo_root, records=records, language=language, schema=schema)
    return result, _render_index(result.pages, schema, language)


def _remove_generated_rst(out_dir: Path, keep: frozenset[Path]) -> None:
    """Remove direct generated RST files this render no longer produces.

    The output directory is gitignored build residue, so a page left behind by
    a render that no longer owns it survives every later build. Sphinx then
    reads it, finds it in no toctree, and reds the nitpicky gate -- which the
    deploy runs before it uploads, so stale residue fails a publish. Five pages
    from a removed preview surface did exactly that.

    Only pages absent from ``keep`` are unlinked, mirroring the legal
    reference's sweep: a page this render still owns keeps its inode and mtime
    so :func:`_write_if_changed` can leave unchanged bytes untouched, rather
    than recreating the whole tree and making Sphinx re-read it every build.
    """
    for path in scan_directory(out_dir, require_root=True):
        if path.suffix != ".rst":
            continue
        if path.is_symlink() or not path.is_file() or path.parent != out_dir:
            raise CasillaReferenceError(f"refusing to remove unsafe generated casilla path: {path}")
        if path in keep:
            continue
        path.unlink()


def _write_if_changed(path: Path, rst: str) -> None:
    """Write the page only when its content changed, forcing LF newlines.

    The default newline translation emits CRLF on Windows, which doc8's
    CheckCarriageReturn (D004) then flags on every regeneration; force LF so the
    generated page is byte-identical across platforms (the glossary precedent).
    """
    if not (path.is_file() and path.read_bytes() == rst.encode(UTF_8)):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(rst, encoding=UTF_8, newline="\n")

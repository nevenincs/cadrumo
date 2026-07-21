"""Post-build Pagefind index pass over the built documentation HTML.

Runs AFTER Sphinx has emitted ``docs/_build/html``: it indexes the built
pages with Pagefind's bundled (vendored, offline) binary, producing the
chunked, per-language search index into the build output. The index is an
uncommitted build artifact - it is regenerated on every docs build, exactly
like the generated CLI reference, and never committed.

This pass is deliberately a STANDALONE step, not a Sphinx ``setup()`` hook:
it must run after the build, and wiring it into ``conf.py`` would couple it
to every Sphinx invocation - including the nitpicky ``-n -W`` gate, which
this pass must leave untouched. The docs build driver (or ``just docs``)
calls :func:`build_search_index` after a successful Sphinx build.

The Pagefind binary is vendored as a pinned wheel (``pagefind[extended]`` -
the extended binary bundles the Spanish/Catalan/Hungarian/English stemmers
needed for the per-language index splits). Because the binary lives inside
the installed wheel, the pass makes NO network fetch and the build stays
offline-hermetic.

Injection seam for the custom-record step: :func:`build_search_index`
accepts an optional ``inject`` callback that is invoked with the open
:class:`~pagefind.index.PagefindIndex` AFTER ``add_directory`` and BEFORE the
index is written. The custom-record injection (the unified search records
plus the sweep-derived relevance weights) plugs in there via
``index.add_custom_record(...)``; this module owns only the directory pass
and the write, never the record content.

Orama fallback trigger: Pagefind is the chosen backend because it is the only
surveyed engine that satisfies every hard constraint at once - MIT, offline,
native es/ca/hu/en stemming with per-language index splits, lazy chunked
scaling, and a first-class custom-record API. The documented fallback is
Orama (Apache-2.0, pure JS). Switch to Orama ONLY if the Pagefind binary
proves unvendorable for the offline-hermetic build - i.e. if the
``pagefind[extended]`` wheel (which bundles the platform binary) cannot be
pinned for a target platform, or a future platform has no published bundled
wheel and the build would need a network fetch. In this environment the
vendoring succeeded (the ``win_amd64`` extended wheel is pinned and the
bundled binary runs offline), so the fallback is not triggered; it remains
the documented escape hatch if a platform-coverage gap appears. Orama's cost
is a sourced Catalan Snowball stemmer (Orama bundles none) and whole-index
loading instead of lazy chunking.
"""

from __future__ import annotations

import asyncio
import os
import shutil
import tempfile
from collections.abc import Awaitable, Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pagefind.index import PagefindIndex

#: Callback that injects custom records into the open index after the
#: directory pass. The custom-record step supplies this; this module calls it.
InjectCallback = Callable[["PagefindIndex"], Awaitable[None]]


class PagefindUnavailableError(RuntimeError):
    """Raised when the vendored Pagefind package cannot be imported.

    A clear, named boundary so a missing/broken vendor surfaces as an
    actionable error (re-pin the wheel) rather than an opaque ImportError
    deep in the build.
    """


class PagefindConfigurationError(RuntimeError):
    """Raised when the shipped Pagefind configuration is absent or invalid."""


@dataclass(frozen=True)
class SearchIndexResult:
    """Outcome of a Pagefind index pass."""

    html_root: Path
    page_count: int
    output_subdir: str


def _default_config_path() -> Path:
    """Return the shipped Pagefind configuration path."""
    return Path(__file__).resolve().parents[2] / "docs" / "pagefind.yml"


def _load_index_config(config_path: Path, output_path: Path):
    """Read validated selectors from the shipped YAML configuration.

    The Python Pagefind API does not discover ``pagefind.yml`` itself. Keep
    the CLI configuration authoritative by loading its two selector settings
    and passing them through as ``IndexConfig``.
    """
    import yaml
    from pagefind.index import IndexConfig

    try:
        raw_config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise PagefindConfigurationError(f"Pagefind config not found: {config_path}") from exc
    except OSError as exc:
        raise PagefindConfigurationError(f"Pagefind config could not be read: {config_path}: {exc}") from exc
    except yaml.YAMLError as exc:
        raise PagefindConfigurationError(f"Pagefind config is not valid YAML: {config_path}: {exc}") from exc

    if not isinstance(raw_config, dict):
        raise PagefindConfigurationError(f"Pagefind config must be a mapping: {config_path}")

    root_selector = raw_config.get("root_selector")
    if not isinstance(root_selector, str) or not root_selector.strip():
        raise PagefindConfigurationError(
            f"Pagefind config requires a non-empty string root_selector: {config_path}",
        )

    exclude_selectors = raw_config.get("exclude_selectors")
    if not isinstance(exclude_selectors, list) or any(
        not isinstance(selector, str) or not selector.strip() for selector in exclude_selectors
    ):
        raise PagefindConfigurationError(
            f"Pagefind config requires exclude_selectors as a list of non-empty strings: {config_path}",
        )

    return IndexConfig(
        root_selector=root_selector,
        exclude_selectors=exclude_selectors,
        output_path=str(output_path),
    )


@contextmanager
def _indexable_html_tree(html_root: Path) -> Iterator[Path]:
    """Yield an ephemeral input tree without generated source-code pages.

    Pagefind should search human docs and CLI pages, not Sphinx's generated
    API or ``_modules`` source listings. Those files remain in the built site
    for direct links. Mirror only indexable HTML pages at their original
    relative paths. Prefer hard links; copy when the temporary directory is
    on another volume.
    """
    with tempfile.TemporaryDirectory(prefix="aeat-pagefind-input-", dir=html_root.parent) as temp_dir:
        input_root = Path(temp_dir) / "html"
        input_root.mkdir()
        for source in html_root.rglob("*.html"):
            relative = source.relative_to(html_root)
            if relative.parts and relative.parts[0] in {"_modules", "api"}:
                continue
            target = input_root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            try:
                os.link(source, target)
            except OSError:
                shutil.copy2(source, target)
        yield input_root


def _require_pagefind() -> None:
    """Confirm the vendored Pagefind package is importable, else raise.

    Raises:
        PagefindUnavailableError: If ``pagefind`` is not installed (the
            ``pagefind[extended]`` wheel was not vendored into the env).
    """
    try:
        import pagefind.index  # noqa: F401
    except ImportError as exc:  # pragma: no cover - exercised via the gate test
        raise PagefindUnavailableError(
            "the vendored Pagefind package is not importable; install the "
            "pinned `pagefind[extended]` wheel (it bundles the offline binary)"
        ) from exc


async def _run_index(
    html_root: Path,
    *,
    config_path: Path,
    inject: InjectCallback | None,
) -> int:
    """Index ``html_root`` with Pagefind and write the per-language index.

    Returns the number of pages Pagefind indexed from the directory pass.
    """
    from pagefind.index import PagefindIndex

    config = _load_index_config(config_path, html_root / "pagefind")
    with _indexable_html_tree(html_root) as input_root:
        async with PagefindIndex(config=config) as index:
            response = await index.add_directory(str(input_root))
            if inject is not None:
                # Injection seam: the custom-record step adds the unified search
                # records and relevance weights here, before the index is written.
                await inject(index)
    # The directory-pass response is a dict carrying the indexed page count.
    if isinstance(response, dict):
        return int(response.get("page_count", 0) or 0)
    return int(getattr(response, "page_count", 0) or 0)


def build_search_index(
    html_root: Path,
    *,
    config_path: Path | None = None,
    inject: InjectCallback | None = None,
) -> SearchIndexResult:
    """Run the post-build Pagefind index pass over the built HTML.

    Args:
        html_root: The Sphinx HTML output directory (``docs/_build/html``).
            Pagefind reads a temporary mirror of this tree and writes the
            chunked index into ``<html_root>/pagefind/``.
        config_path: The shipped ``docs/pagefind.yml`` selector configuration.
            Defaults to that source-controlled file.
        inject: Optional custom-record injection callback (the custom-record
            step supplies it). Called with the open index after the directory
            pass and before the index is written.

    Returns:
        A :class:`SearchIndexResult` with the indexed page count.

    Raises:
        PagefindUnavailableError: If the vendored Pagefind package is absent.
        PagefindConfigurationError: If the selector configuration is absent or
            invalid.
        FileNotFoundError: If ``html_root`` does not exist.
    """
    _require_pagefind()
    if not html_root.is_dir():
        raise FileNotFoundError(f"built HTML root not found: {html_root}")
    resolved_config_path = _default_config_path() if config_path is None else config_path
    page_count = asyncio.run(_run_index(html_root, config_path=resolved_config_path, inject=inject))
    return SearchIndexResult(
        html_root=html_root,
        page_count=page_count,
        output_subdir="pagefind",
    )

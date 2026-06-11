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
from collections.abc import Awaitable, Callable
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


@dataclass(frozen=True)
class SearchIndexResult:
    """Outcome of a Pagefind index pass."""

    html_root: Path
    page_count: int
    output_subdir: str


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
    inject: InjectCallback | None,
) -> int:
    """Index ``html_root`` with Pagefind and write the per-language index.

    Returns the number of pages Pagefind indexed from the directory pass.
    """
    from pagefind.index import PagefindIndex

    output_path = html_root / "pagefind"
    async with PagefindIndex() as index:
        response = await index.add_directory(str(html_root))
        if inject is not None:
            # Injection seam: the custom-record step adds the unified search
            # records and relevance weights here, before the index is written.
            await inject(index)
        # Write the chunked, per-language index into <html_root>/pagefind/ so
        # the built site serves it alongside its pages (an uncommitted artifact).
        await index.write_files(output_path=str(output_path))
    # The directory-pass response is a dict carrying the indexed page count.
    if isinstance(response, dict):
        return int(response.get("page_count", 0) or 0)
    return int(getattr(response, "page_count", 0) or 0)


def build_search_index(
    html_root: Path,
    *,
    inject: InjectCallback | None = None,
) -> SearchIndexResult:
    """Run the post-build Pagefind index pass over the built HTML.

    Args:
        html_root: The Sphinx HTML output directory (``docs/_build/html``).
            Pagefind reads ``pagefind.yml`` from this root for the
            root/exclude selectors and writes the chunked index into
            ``<html_root>/pagefind/``.
        inject: Optional custom-record injection callback (the custom-record
            step supplies it). Called with the open index after the directory
            pass and before the index is written.

    Returns:
        A :class:`SearchIndexResult` with the indexed page count.

    Raises:
        PagefindUnavailableError: If the vendored Pagefind package is absent.
        FileNotFoundError: If ``html_root`` does not exist.
    """
    _require_pagefind()
    if not html_root.is_dir():
        raise FileNotFoundError(f"built HTML root not found: {html_root}")
    page_count = asyncio.run(_run_index(html_root, inject=inject))
    return SearchIndexResult(
        html_root=html_root,
        page_count=page_count,
        output_subdir="pagefind",
    )

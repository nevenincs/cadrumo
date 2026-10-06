"""Canonical storage paths for compiled documentation output."""

from __future__ import annotations

import os
from collections.abc import Mapping
from pathlib import Path

from cadrumo.core.storage_environment import configured_storage_root, resolve_storage_path

DOCS_BUILD_ROOT_ENV = "CADRUMO_DOCS_BUILD_ROOT"
DEFAULT_DOCS_BUILD_ROOT = "development/build/docs"
DOCS_SITE_PREFIX_ENV = "CADRUMO_DOCS_SITE_PREFIX"


def docs_build_root(
    repo_root: Path | None = None,
    *,
    environ: Mapping[str, str] | None = None,
) -> Path:
    """Resolve the compiled docs root under Cadrumo storage by default."""
    environment = os.environ if environ is None else environ
    storage_root = configured_storage_root(environ=environment, repository_root=repo_root)
    configured = environment.get(DOCS_BUILD_ROOT_ENV, "").strip() or DEFAULT_DOCS_BUILD_ROOT
    return resolve_storage_path(configured, root=storage_root)


def docs_html_root(
    repo_root: Path | None = None,
    *,
    environ: Mapping[str, str] | None = None,
) -> Path:
    """Return the canonical Sphinx HTML output directory."""
    return docs_build_root(repo_root, environ=environ) / "html"


def docs_site_prefix(environ: Mapping[str, str] | None = None) -> str:
    """Resolve this root's own path inside the served site.

    The built root and the served site are not the same layout. A packaged
    desktop site puts one language at the apex and the others under
    ``<language>/``, so a page of a localized root is addressed with that prefix
    and resolves the site's one search index one level up from its own root. A
    root that is its own whole site -- a local single-language build, or a
    published layout where every language is a peer directory carrying its own
    index -- has no prefix, which is the default.

    The prefix is read from the environment rather than derived from the build
    language, because whether a language sits at the apex is a property of the
    LAYOUT being produced and not of the language: the same English root is the
    apex of a package and a peer directory of the published site.

    Args:
        environ: The environment to read; the process environment by default.

    Returns:
        The empty string, or a single path segment ending in ``/``.

    Raises:
        ValueError: If the value is absolute, climbs, or names more than one
            segment, since a reader's search controller resolves the site apex
            by walking back exactly the segments this names.
    """
    environment = os.environ if environ is None else environ
    raw = environment.get(DOCS_SITE_PREFIX_ENV, "").strip()
    if not raw:
        return ""
    segment = raw.rstrip("/")
    if not segment or "/" in segment or "\\" in segment or segment in {".", ".."}:
        raise ValueError(
            f"{DOCS_SITE_PREFIX_ENV} must be empty or one path segment naming this root's "
            f"directory in the served site; got {raw!r}",
        )
    return f"{segment}/"


def pin_docs_build_root(repo_root: Path | None = None) -> Path:
    """Freeze the resolved output root before a build isolates product storage."""
    resolved = docs_build_root(repo_root)
    os.environ[DOCS_BUILD_ROOT_ENV] = str(resolved)
    return resolved

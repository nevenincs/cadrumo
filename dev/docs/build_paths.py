"""Canonical storage paths for compiled documentation output."""

from __future__ import annotations

import os
from collections.abc import Mapping, Sequence
from pathlib import Path

from cadrumo.core.storage_environment import configured_storage_root, resolve_storage_path

DOCS_BUILD_ROOT_ENV = "CADRUMO_DOCS_BUILD_ROOT"
DEFAULT_DOCS_BUILD_ROOT = "development/build/docs"
DOCS_SITE_PREFIX_ENV = "CADRUMO_DOCS_SITE_PREFIX"
#: The address the site is served from, above the language directories.
DOCS_BASE_URL_ENV = "CADRUMO_DOCS_BASE_URL"


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


def docs_site_prefixes(
    languages: Sequence[str],
    *,
    build_language: str,
    source_language: str,
    environ: Mapping[str, str] | None = None,
) -> dict[str, str]:
    """Return every language's own path inside the served site: the whole layout.

    A single-language build is told its own prefix and needs no other to resolve
    the site's one index (:func:`docs_site_prefix`). The language switcher needs
    the whole layout, because it writes a link from the page it is on to every
    other root, and one compile of every language needs it for the same reason.

    The configured prefix decides this root's own place, and two layouts put
    the other roots in different places:

    - A build given no prefix is the apex of what it produces, so the language
      it builds in carries no directory and every other language carries its
      own. A local single-language build is its own whole site this way.
    - A build given a prefix sits in a directory of its own, and what stands at
      the apex beside it is the site's address: a site served from an address
      of its own is the published one, which serves every language under its own
      code and nothing at its apex, while a site with no address of its own is
      the packaged copy, whose apex serves the language the pages are authored
      in. The authored language given a directory of its own is therefore the
      first kind as well: no root is left to stand at the apex.

    Each language's own prefix is therefore the one its own build is given, and
    ``prefixes[build_language]`` is what :func:`docs_site_prefix` returns.

    Args:
        languages: The languages the site publishes.
        build_language: The language this build or compile builds in.
        source_language: The language the pages are authored in, which is the
            one a packaged copy serves at its apex.
        environ: The environment to read; the process environment by default.

    Returns:
        Each language's prefix, as :func:`docs_site_prefix` returns one.

    Raises:
        ValueError: As :func:`docs_site_prefix` raises it.
    """
    environment = os.environ if environ is None else environ
    if not docs_site_prefix(environment):
        at_apex = build_language
    elif environment.get(DOCS_BASE_URL_ENV, "").strip() or build_language == source_language:
        # A root told its own directory is never the apex, whatever else is
        # known: the authored language given a directory says, as an address
        # does, that no root stands above the directories.
        at_apex = None
    else:
        at_apex = source_language
    return {language: "" if language == at_apex else f"{language}/" for language in languages}


def pin_docs_build_root(repo_root: Path | None = None) -> Path:
    """Freeze the resolved output root before a build isolates product storage."""
    resolved = docs_build_root(repo_root)
    os.environ[DOCS_BUILD_ROOT_ENV] = str(resolved)
    return resolved

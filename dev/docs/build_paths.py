"""Canonical storage paths for compiled documentation output."""

from __future__ import annotations

import os
from collections.abc import Mapping
from pathlib import Path

from cadrumo.core.storage_environment import configured_storage_root, resolve_storage_path

DOCS_BUILD_ROOT_ENV = "CADRUMO_DOCS_BUILD_ROOT"
DEFAULT_DOCS_BUILD_ROOT = "development/build/docs"


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


def pin_docs_build_root(repo_root: Path | None = None) -> Path:
    """Freeze the resolved output root before a build isolates product storage."""
    resolved = docs_build_root(repo_root)
    os.environ[DOCS_BUILD_ROOT_ENV] = str(resolved)
    return resolved

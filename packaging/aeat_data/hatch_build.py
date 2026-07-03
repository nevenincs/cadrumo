"""Hatchling build hook that force-includes the corpus source binaries.

The ``aeat-data`` companion ships exactly the corpus source binaries the slim
``aeat`` wheel excludes, read from the ONE source tree at
``src/aeat/_data/corpus`` and mapped to the mirrored ``aeat_data/_data/corpus``
layout the runtime corpus-locator seam resolves. Filtering to the binary
suffixes is why this is a build hook rather than a static ``force-include``
directive: a whole-directory force-include cannot drop the derived surfaces
(extracted text, normative html, json) that stay in the ``aeat`` wheel.

The hook targets a source-tree build (``uv build`` / ``uv build --wheel`` run
from ``packaging/aeat_data/``), where the corpus tree is reachable two levels
up. When the wheel is instead built from an extracted sdist, the binaries are
already embedded under ``aeat_data/_data/corpus`` and carried by the
``packages = ["aeat_data"]`` directive, so the hook no-ops.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from hatchling.builders.hooks.plugin.interface import BuildHookInterface

_CORPUS_BINARY_SUFFIXES = frozenset({".pdf", ".xls", ".xlsx"})
_TARGET_PREFIX = "aeat_data/_data/corpus"


class CustomBuildHook(BuildHookInterface):
    """Force-include the corpus source binaries under the mirrored companion tree."""

    PLUGIN_NAME = "aeat-data-corpus"

    def initialize(self, version: str, build_data: dict[str, Any]) -> None:
        """Inject each corpus source binary into the build's force-include map."""
        corpus_root = Path(self.root).resolve().parents[1] / "src" / "aeat" / "_data" / "corpus"
        if not corpus_root.is_dir():
            # Wheel built from an extracted sdist: the binaries are already
            # embedded under aeat_data/_data/corpus and swept in by packages=.
            return
        force_include: dict[str, str] = build_data.setdefault("force_include", {})
        for path in sorted(corpus_root.rglob("*")):
            if not path.is_file() or path.suffix.lower() not in _CORPUS_BINARY_SUFFIXES:
                continue
            relative = path.relative_to(corpus_root)
            if "tests" in relative.parts:
                # Test-pool binaries are not runtime corpus data; the aeat wheel
                # sheds every tests/ subtree, and the companion mirrors that.
                continue
            force_include[str(path)] = f"{_TARGET_PREFIX}/{relative.as_posix()}"

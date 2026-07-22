"""Hatchling build hook: force-include the ``official`` corpus source binaries.

The ``cadrumo-data-official`` companion ships exactly the corpus source binaries
under ``_data/corpus/aeat_official`` and ``_data/corpus/normatives`` — the
official AEAT diseños de registro / workbooks (``*.pdf``/``*.xls``/``*.xlsx``)
and the normative PDFs — read from the ONE source tree at
``src/cadrumo/_data/corpus`` and mapped to the mirrored ``cadrumo_data/_data/corpus``
layout the runtime corpus-locator seam resolves. It is one of two disjoint
sub-cap companions (the other, ``cadrumo-data-manuals``, ships ``corpus/manuals``);
together they cover every corpus source binary the compact ``cadrumo`` wheel excludes,
each staying under PyPI's 100 MB per-file cap so no size grant is needed.

Both companions ship subtrees of the SAME ``cadrumo_data`` PEP 420 implicit
namespace package (NEITHER ships ``cadrumo_data/__init__.py``, which would collide
on a joint install), so ``importlib.resources.files("cadrumo_data")`` resolves a
``MultiplexedPath`` spanning both installed portions.

Filtering to this companion's owned subtrees and to the binary suffixes is why
this is a build hook rather than a static ``force-include``: a whole-directory
force-include cannot drop the derived surfaces (extracted text, normative html,
json) that stay in the ``cadrumo`` wheel, nor the sibling companion's subtree.

The hook targets a source-tree build (``uv build`` run from
``packaging/cadrumo_data_official/``), where the corpus tree is reachable two levels
up. When the wheel is instead built from an extracted sdist, the binaries are
already embedded under ``cadrumo_data/_data/corpus`` and the hook force-includes
them from there.

See Also:
    :class:`CustomBuildHook`
        Hatchling hook that injects this companion's owned corpus binaries into
        the build ``force_include`` map.
    :func:`_corpus_root`
        Source-tree versus embedded-sdist resolver used before scanning owned
        binaries.
    :mod:`~core.resources`
        Runtime corpus locator seam that reads the mirrored ``cadrumo_data`` tree
        produced by this hook.
    :mod:`~dev.packaging.smoke_split_install`
        Three-wheel cohort lane proving the command-bearing wheel declares and
        installs both mandatory companion portions.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, override

from hatchling.builders.config import BuilderConfig
from hatchling.builders.hooks.plugin.interface import BuildHookInterface

_CORPUS_BINARY_SUFFIXES = frozenset({".docx", ".pdf", ".xls", ".xlsm", ".xlsx", ".zip"})
_TARGET_PREFIX = "cadrumo_data/_data/corpus"

# The corpus top-level subtrees this companion owns. The sibling
# ``cadrumo-data-manuals`` owns ``manuals``; the two sets are disjoint and their
# union is every corpus subtree carrying source binaries.
_OWNED_SUBDIRS = frozenset({"aeat_official", "normatives"})


def _corpus_root(hook_root: Path) -> Path | None:
    """Return the corpus tree root for a source-tree or embedded-sdist build.

    A source-tree build (from ``packaging/cadrumo_data_official/``) reaches the ONE
    source corpus two levels up; a wheel built from an extracted sdist finds the
    binaries already embedded under ``cadrumo_data/_data/corpus``. Returns ``None``
    when neither is present (nothing to force-include).
    """
    source_tree = hook_root.resolve().parents[1] / "src" / "cadrumo" / "_data" / "corpus"
    if source_tree.is_dir():
        return source_tree
    embedded = hook_root / "cadrumo_data" / "_data" / "corpus"
    if embedded.is_dir():
        return embedded
    return None


class CustomBuildHook(BuildHookInterface[BuilderConfig]):
    """Force-include this companion's corpus source binaries under the mirrored tree."""

    PLUGIN_NAME = "cadrumo-data-official-corpus"

    @override
    def initialize(self, version: str, build_data: dict[str, Any]) -> None:
        """Inject the owned corpus source binaries into the build's force-include map."""
        corpus_root = _corpus_root(Path(self.root))
        if corpus_root is None:
            return
        force_include: dict[str, str] = build_data.setdefault("force_include", {})
        for path in sorted(corpus_root.rglob("*")):
            if not path.is_file() or path.suffix.lower() not in _CORPUS_BINARY_SUFFIXES:
                continue
            relative = path.relative_to(corpus_root)
            if relative.parts[0] not in _OWNED_SUBDIRS:
                # Belongs to the sibling companion; each ships exactly its subtree.
                continue
            if "tests" in relative.parts:
                # Test-pool binaries are not runtime corpus data; the cadrumo wheel
                # sheds every tests/ subtree, and the companions mirror that.
                continue
            force_include[str(path)] = f"{_TARGET_PREFIX}/{relative.as_posix()}"

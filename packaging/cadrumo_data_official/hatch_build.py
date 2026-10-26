"""Hatchling build hook for the official corpus companion.

This companion owns source binaries under ``_data/corpus/aeat_official`` and ``_data/corpus/eu_official``.
Together the manuals, official and normatives companions form a disjoint,
exhaustive partition under the same implicit ``cadrumo_data`` namespace.
Derived surfaces remain in the command-bearing wheel. Resource paths and
source bytes are preserved for source-tree and embedded-sdist builds.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any, TypeGuard, cast, override

from hatchling.builders.config import BuilderConfig
from hatchling.builders.hooks.plugin.interface import BuildHookInterface
from hatchling.plugin.manager import PluginManager

_CORPUS_BINARY_SUFFIXES = frozenset({".docx", ".pdf", ".xls", ".xlsm", ".xlsx", ".zip"})
_TARGET_PREFIX = "cadrumo_data/_data/corpus"

# The corpus top-level subtrees this companion owns. The sibling
# The companions own disjoint corpus subtrees; their
# union is every corpus subtree carrying source binaries.
_OWNED_SUBDIRS = frozenset({"aeat_official", "eu_official"})


def _is_string_mapping(value: object) -> TypeGuard[dict[str, str]]:
    """Recognize Hatch's force-include mapping without trusting its Any payload."""
    return isinstance(value, dict) and all(
        isinstance(key, str) and isinstance(item, str) for key, item in value.items()
    )


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


def _runtime_build_hook_base() -> Any:
    """Specialize Hatchling's hook base across its supported type API revisions.

    Hatchling 1.32.3 exposes ``BuildHookInterface[BuilderConfig[PluginManager],
    PluginManager]``. Hatchling 1.32.4 reduces the interface to
    ``BuildHookInterface[BuilderConfig]``. The admitted build requirement covers
    both, so select the matching runtime base before the hook class is defined.
    Unknown shapes fail closed before the hook changes build data.
    """
    hook_parameter_count = len(getattr(BuildHookInterface, "__parameters__", ()))
    config_parameter_count = len(getattr(BuilderConfig, "__parameters__", ()))
    runtime_hook_interface = cast(Any, BuildHookInterface)
    runtime_builder_config = cast(Any, BuilderConfig)
    if (hook_parameter_count, config_parameter_count) == (1, 0):
        return runtime_hook_interface[runtime_builder_config]
    if (hook_parameter_count, config_parameter_count) == (2, 1):
        return runtime_hook_interface[runtime_builder_config[PluginManager], PluginManager]
    raise TypeError(
        "unsupported Hatchling BuildHookInterface/BuilderConfig generic contract: "
        f"{hook_parameter_count}/{config_parameter_count} parameters"
    )


if TYPE_CHECKING:

    class _CustomBuildHookBase(BuildHookInterface[BuilderConfig]):
        """Static view of the installed Hatchling hook protocol."""
else:
    _CustomBuildHookBase = _runtime_build_hook_base()


class CustomBuildHook(_CustomBuildHookBase):
    """Force-include this companion's corpus source binaries under the mirrored tree."""

    PLUGIN_NAME = "cadrumo-data-official-corpus"

    @override
    def initialize(self, version: str, build_data: dict[str, Any]) -> None:
        """Inject the owned corpus source binaries into the build's force-include map."""
        corpus_root = _corpus_root(Path(self.root))
        if corpus_root is None:
            return
        force_include = build_data.setdefault("force_include", {})
        if not _is_string_mapping(force_include):
            raise TypeError("hatch build_data force_include must map string paths to string destinations")
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

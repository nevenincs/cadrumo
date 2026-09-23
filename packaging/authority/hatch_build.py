"""Hatchling build hook: force-include the published authority pair.

The published registry authority — the ``authority.current.json`` descriptor and
the single content-addressed ``authority-<sha256>.sqlite3`` it names — is
generated output that is nevertheless shipped runtime input. It therefore lives
outside the package source tree, in a gitignored ``.authority/`` directory at the
repository root, while the distributions must continue to publish it at
``cadrumo/_data/registry/authority/`` byte for byte.

A static ``include``/``only-include`` pattern cannot express that. Those patterns
narrow the builder's file selection, and the selection never offers a path the
repository's ignore rules exclude: pointing them at ``.authority/`` produces an
archive carrying no authority member at all, and no error. ``force_include`` is
the only selection-independent admission path, which is why this is a hook.

A *static* ``force-include`` table is equally unusable, because the mapping would
have to name two different source layouts at once. In a source-tree build the
pair sits at ``.authority/``; an sdist instead carries it already at the mapped
destination, and a table naming ``.authority/`` raises ``FileNotFoundError:
Forced include not found`` the moment a wheel is built from that sdist.
:func:`_authority_root` resolves the two layouts, mirroring the
source-tree-versus-embedded-sdist split of
``packaging/cadrumo_data_manuals/hatch_build.py``.

Selection is descriptor-driven: exactly the descriptor and the one database it
names, never the directory. Retirement of a superseded generation is deferred
while a reader still holds it open, so the directory may legitimately carry a
second database, and a whole-directory include would add its full weight to
every artifact. The directory also always carries the publication lock sidecar
``authority.current.json.lock``, and carries a transient
``authority-candidate-*`` staging directory while a publication is in flight.
Neither is distribution payload. Naming the two selected files admits the
payload and nothing else, without the hook having to enumerate what to reject.

See Also:
    :class:`CustomBuildHook`
        Hatchling hook that injects the selected pair into the build
        ``force_include`` map for whichever target is building.
    :func:`_authority_root`
        Source-tree versus embedded-sdist resolver.
    :func:`_selected_pair`
        Descriptor parse and content verification performed before admission.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any, TypeGuard, cast, override

from hatchling.builders.config import BuilderConfig
from hatchling.builders.hooks.plugin.interface import BuildHookInterface
from hatchling.plugin.manager import PluginManager

#: Overrides where a source-tree build reads the published authority from.
#: Unset, the pair is read from ``.authority/`` at the build root.
_AUTHORITY_ROOT_ENV = "CADRUMO_AUTHORITY_ROOT"

#: The gitignored authoring location, relative to the repository root.
_SOURCE_TREE_DIRECTORY = ".authority"

#: Where every distribution publishes the pair, relative to its own archive
#: root. The wheel installs ``src/cadrumo`` as ``cadrumo``; the sdist keeps the
#: ``src`` layout so a wheel built from it lands the pair at the same place.
_WHEEL_DESTINATION = "cadrumo/_data/registry/authority"
_SDIST_DESTINATION = "src/cadrumo/_data/registry/authority"

_DESCRIPTOR_NAME = "authority.current.json"

#: A published database is named for the SHA-256 of its own bytes. Admitting
#: only this shape keeps a hand-placed or partially written file out of the
#: archive even when a descriptor names it.
_DATABASE_NAME = re.compile(r"authority-[0-9a-f]{64}\.sqlite3")


def _is_object_mapping(value: object) -> TypeGuard[dict[object, object]]:
    """Narrow a decoded or framework-provided mapping to object values."""
    return isinstance(value, dict)


def _is_string_mapping(value: object) -> TypeGuard[dict[str, str]]:
    """Recognize Hatch's force-include mapping without trusting its Any payload."""
    if not _is_object_mapping(value):
        return False
    return all(isinstance(key, str) and isinstance(item, str) for key, item in value.items())


def _is_descriptor_mapping(value: object) -> TypeGuard[dict[str, object]]:
    """Recognize a decoded JSON object with string member names."""
    if not _is_object_mapping(value):
        return False
    return all(isinstance(key, str) for key in value)


def _runtime_build_hook_base() -> Any:
    """Specialize Hatchling's hook base across its supported type API revisions.

    Hatchling 1.32.3 exposes ``BuildHookInterface[BuilderConfig[PluginManager],
    PluginManager]``.  Hatchling 1.32.4 removes the configuration generic and
    reduces the hook interface to ``BuildHookInterface[BuilderConfig]``.  The
    declared build requirement admits both releases, so evaluating either
    spelling unconditionally prevents one of the supported isolated backends
    from importing this hook.

    The dynamic values only bridge the third-party runtime type API.  The
    ``TYPE_CHECKING`` base below keeps the 1.32.3 protocol fully described to
    static checkers, and unknown future shapes fail before any build data is
    changed.
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

    class _CustomBuildHookBase(BuildHookInterface[BuilderConfig[PluginManager], PluginManager]):
        """Static view of the Hatchling 1.32.3 hook protocol."""
else:
    _CustomBuildHookBase = _runtime_build_hook_base()


def _authority_root(build_root: Path) -> Path:
    """Return the published pair directory, compiling a fresh source tree if needed.

    A source-tree build reads the gitignored ``.authority/`` beside the project,
    or the directory ``CADRUMO_AUTHORITY_ROOT`` names. A build from an extracted
    sdist finds the pair already embedded at the published path and must read it
    from there, because the sdist carries no ``.authority/``. When a real source
    tree has no publication yet, the canonical compiler publishes one to its
    repo-root ``.authority/`` before packaging continues.

    A source tree counts as published only when its descriptor exists. A
    publication that died after creating the directory leaves it without one,
    and treating that directory as published would refuse every later build
    instead of completing the publication it interrupted.
    """
    override = os.environ.get(_AUTHORITY_ROOT_ENV)
    if override:
        candidate = Path(override)
        if not candidate.is_dir():
            raise FileNotFoundError(f"configured ${_AUTHORITY_ROOT_ENV} directory is unavailable: {candidate}")
        return candidate
    source_tree = build_root / _SOURCE_TREE_DIRECTORY
    if (source_tree / _DESCRIPTOR_NAME).is_file():
        return source_tree
    embedded = build_root / _SDIST_DESTINATION
    if embedded.is_dir():
        return embedded
    return _publish_source_tree_authority(build_root, source_tree)


def _publish_source_tree_authority(build_root: Path, destination: Path) -> Path:
    """Compile the canonical authority and return its publication directory."""
    import_paths = (str(build_root), str(build_root / "src"))
    original_path = sys.path.copy()
    try:
        sys.path[:0] = import_paths
        from dev.registry.compiler.authority import AuthoritySourceSet
        from dev.registry.pipeline.authority_publication import publish_sqlite_authority_candidate

        sources = AuthoritySourceSet.bundled()
        publish_sqlite_authority_candidate(
            registry_root=sources.registry_root,
            source_root=sources.source_evidence_root,
            profile_schema_path=sources.profile_schema_path,
            destination=destination,
        )
        return destination
    finally:
        sys.path[:] = original_path


def _selected_pair(root: Path) -> tuple[Path, Path]:
    """Return the descriptor and the verified database it selects.

    The descriptor is the publication edge, so its claim about the payload is
    checked here rather than trusted. A build that shipped a descriptor naming
    bytes the archive does not carry would install an authority the runtime
    refuses to open, and that failure would surface at first use rather than at
    build time.
    """
    descriptor = root / _DESCRIPTOR_NAME
    if not descriptor.is_file():
        raise FileNotFoundError(f"published authority has no descriptor: {descriptor}")
    document = json.loads(descriptor.read_text(encoding="utf-8"))
    if not _is_descriptor_mapping(document):
        raise TypeError(f"authority descriptor is not a mapping: {descriptor}")
    name = document.get("database")
    if not isinstance(name, str) or _DATABASE_NAME.fullmatch(name) is None:
        raise ValueError(f"authority descriptor names an invalid database: {name!r}")
    database = root / name
    if database.resolve().parent != root.resolve():
        raise ValueError(f"authority descriptor escapes its directory: {name!r}")
    if not database.is_file():
        raise FileNotFoundError(f"authority descriptor selects a missing database: {database}")
    payload = database.read_bytes()
    digest = hashlib.sha256(payload).hexdigest()
    if name != f"authority-{digest}.sqlite3":
        raise ValueError(f"authority database contents do not match its content-addressed name: {name!r}")
    if document.get("database_sha256") != digest:
        raise ValueError("authority descriptor digest does not match the selected database bytes")
    if document.get("database_size") != len(payload):
        raise ValueError("authority descriptor size does not match the selected database bytes")
    return descriptor, database


class CustomBuildHook(_CustomBuildHookBase):
    """Force-include the descriptor-selected authority pair at the published path."""

    PLUGIN_NAME = "cadrumo-authority"

    @override
    def initialize(self, version: str, build_data: dict[str, Any]) -> None:
        """Inject the selected descriptor and database into the force-include map."""
        build_root = Path(self.root)
        root = _authority_root(build_root)
        descriptor, database = _selected_pair(root)
        destination = _SDIST_DESTINATION if self.target_name == "sdist" else _WHEEL_DESTINATION
        force_include = build_data.setdefault("force_include", {})
        if not _is_string_mapping(force_include):
            raise TypeError("hatch build_data force_include must map string paths to string destinations")
        for path in (descriptor, database):
            force_include[str(path)] = f"{destination}/{path.name}"

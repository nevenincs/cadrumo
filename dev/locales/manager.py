"""Locale discovery, guarded catalogue editing, and scaffolding coordination."""

import re
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any

import yaml

from cadrumo.core.directory_scan import iter_directory
from cadrumo.core.external_constants import UTF_8_ENCODING, OutputLanguage
from cadrumo.core.logging import get_logger
from cadrumo.core.product_identity import normalise_product_identity_references
from dev.first_party_source import is_test_source

from ._subtree_move import (
    LocaleMoveConflict,
    LocaleSubtreeMovePlan,
    LocaleSubtreeMoveResult,
    normalise_key_prefix,
    plan_locale_subtree_move,
)
from .errors import LocaleError
from .locale_audit import LocaleAuditResult, _audit_locale_file, _audit_placeholder_mismatches, _covered_by_namespace
from .locale_nodes import LocaleNode
from .locale_tree import (
    _apply_mapping_edits,
    _collect_required_leaves,
    _flatten_leaf_values,
    _flatten_raw_locale_leaves,
    _normalise_product_identity_mapping,
    _remove_existing_locale_leaf,
    _remove_optional_locale_leaf,
    _remove_required_locale_leaf,
    _resolve_leaf_parent,
    _set_locale_mapping_value,
    _set_nested_leaf,
)
from .locale_yaml import (
    _deep_merge_dicts,
    _parse_locale,
    _parse_raw_locale,
    _rewrite_locale_mapping,
    discover_locale_codes,
    locale_catalogue_source,
)
from .wizard_translation_audit import wizard_descriptor_keys
from .write_guard import CatalogueWriteGuard, catalogue_write_guard

_log = get_logger(__name__)


class LocaleManager:
    """API for managing locale files, scaffolding, and structural health."""

    def __init__(self, src_dir: Path, locales_dir: Path, extra_src_dirs: tuple[Path, ...] = ()):
        """Initialise the manager with the source tree and locale file directory.

        Args:
            src_dir: Root directory of the Python source tree to scan for translation keys.
            locales_dir: Directory containing ``*.yml`` locale files.
            extra_src_dirs: Further roots outside the package that reference
                catalogue keys. Empty by default so a caller scanning an
                isolated fixture tree never picks up the live checkout; the CLI
                and the parity gate pass the documentation generators' root,
                whose keys would otherwise read as extra keys absent from the
                codebase.
        """
        self.src_dir = src_dir
        self.locales_dir = locales_dir
        self.extra_src_dirs = tuple(d for d in extra_src_dirs if d.is_dir())
        #: Memo for :meth:`get_codebase_keys`, scoped to this manager so it can
        #: never outlive the ``src_dir`` it describes.
        self._codebase_keys: frozenset[str] | None = None
        self._codebase_namespaces: frozenset[str] | None = None
        # ``docs_chrome`` is the documentation generators' accessor. It exists
        # because ``tr()`` resolves the ambient locale while a docs build must
        # render one explicit language per page, so the generators cannot use
        # ``tr()`` -- but the keys it takes are ordinary catalogue keys and must
        # be as visible to this scan as any other, or scaffold prunes them and
        # the parity gate reports them as keys no code requests.
        self.pattern = re.compile(
            r'\b(?:tr|t|docs_chrome)\(\s*["\'](\w+(?:\.\w+)+)["\']',
            re.UNICODE,
        )

    def get_codebase_keys(self) -> set[str]:
        """Extract all concrete dotted translation keys from the codebase.

        Scanned once per manager. The walk measured 15.00s cold then 9.06s and
        9.08s warm, returning 41,926 keys, and ``scaffold()`` and ``audit()``
        each call it -- so a scaffold-then-audit on one manager paid it twice
        for an identical answer.

        The memo is per INSTANCE rather than per process, which is what makes
        it safe by construction: a caller wanting a fresh scan builds a new
        manager, and no cache can outlive the object whose ``src_dir`` it
        describes. A process-level memo keyed on ``src_dir`` would be unsound
        here, because tests build managers over planted temporary source trees.
        Every one of the 34 functions that constructs a manager was checked for
        a filesystem mutation issued after construction; none does. Note also
        that this reads SOURCE while ``scaffold()`` writes CATALOGUES, so the
        answer cannot move across the one sequence that calls it twice.

        A fresh ``set`` is returned per call so no caller can mutate another's
        view; copying 41,926 strings costs milliseconds against a 9s scan.

        Only production modules are scanned: test files are excluded so a
        fixture payload or assertion literal can never inject a phantom
        required key that no production code requests.

        Combines six discovery paths:

        1. Regex scanner — ``tr("…")`` / ``t("…")`` literal call sites.
        2. AST scanner — programmatic emissions such as
           ``WizardValidationError("wizard.errors.select_unknown")``,
           ``message_key=`` kwargs, and ``build_entry`` portal keys.
        3. F-string registry — bounded f-string patterns whose value sets
           are fully known at import time (e.g. wizard choice labels
           keyed by enum values). See :mod:`locales.fstring_registry`.
        4. Command-spec scanner — the keys the live CLI registry declares in
           its ``TranslationKey`` fields. A spec table builds an option's help
           key from the option name, so no literal for it exists anywhere and
           a text scan cannot tell it from a key nothing uses. See
           :mod:`locales._command_spec_scanner`.
        5. Registry scanner — keys declared as data by a committed registry
           rather than by a Python call site: named literally by the category
           profile fact, and derived from declared structure by the user-profile
           and Modelo schemas. The first three paths read Python source only,
           so these were invisible to every parity check and sat unresolved in
           all four catalogues. See
           :mod:`locales._registry_scanner`.
        6. Desktop chrome declaration - the keys the desktop shell's
           TypeScript frontend reads from its generated strings file. No
           Python call site names them, so they are declared once by the
           generator. See :mod:`locales.desktop_chrome`.

        Dynamic namespaces (open-ended f-string and concatenation forms)
        are returned by :meth:`get_codebase_namespaces` and checked
        through a separate parity assertion that verifies at least one
        concrete locale key exists under each declared prefix.
        """
        from dev.quality.unread_inputs import report_unread

        from ._ast_scanner import scan_source_trees
        from ._command_spec_scanner import scan_command_spec_keys
        from ._registry_scanner import scan_modelo_schema_keys, scan_profile_schema_keys, scan_registry_keys
        from .desktop_chrome import DESKTOP_CHROME_KEYS
        from .fstring_registry import get_registered_keys
        from .manager_chrome import MANAGER_CHROME_KEYS

        if self._codebase_keys is not None:
            return set(self._codebase_keys)

        keys: set[str] = set()
        unread: list[str] = []
        source_roots = (self.src_dir, *self.extra_src_dirs)
        for root in source_roots:
            for py_file in iter_directory(root, pattern="*.py", recursive=True):
                if is_test_source(py_file, root=root):
                    continue
                try:
                    content = py_file.read_text(encoding=UTF_8_ENCODING)
                except (OSError, UnicodeDecodeError) as exc:
                    # Read strictly and say so. The lenient decode dropped bytes,
                    # so a key literal could be cut in half and never matched, and
                    # the read failure was logged at debug level - invisible in a
                    # normal run. This set decides which keys the codebase uses, so
                    # a key missed here is a live translation on a deletion path.
                    unread.append(f"{py_file}: {type(exc).__name__}: {exc}")
                    continue
                for match in self.pattern.finditer(content):
                    keys.add(match.group(1))
        # The roots form one logical source corpus. Parse and index them in one
        # scanner invocation so cross-module analysis runs once instead of once
        # per root (the package, docs, and harness each contribute to the same
        # required-key set).
        keys.update(scan_source_trees(source_roots))
        keys.update(get_registered_keys())
        keys.update(scan_command_spec_keys())
        keys.update(scan_registry_keys())
        keys.update(scan_profile_schema_keys())
        keys.update(scan_modelo_schema_keys())
        keys.update(wizard_descriptor_keys())
        keys.update(DESKTOP_CHROME_KEYS)
        keys.update(MANAGER_CHROME_KEYS)
        report_unread(
            "locale key scan",
            "any key they use is absent from this set and would look unused",
            unread,
        )
        self._codebase_keys = frozenset(keys)
        return keys

    def get_codebase_namespaces(self) -> set[str]:
        """Extract dynamic-namespace markers (``<prefix>.*``) from the codebase.

        Returns every prefix discovered through f-string or string
        concatenation patterns whose tail is computed at runtime.
        Each marker passes the parity check when at least one
        concrete locale key starts with its prefix.
        """
        if self._codebase_namespaces is not None:
            return set(self._codebase_namespaces)
        from ._ast_scanner import scan_namespace_markers

        markers: set[str] = set()
        for root in (self.src_dir, *self.extra_src_dirs):
            markers.update(scan_namespace_markers(root))
        self._codebase_namespaces = frozenset(markers)
        return markers

    def audit(self) -> LocaleAuditResult:
        """Audit scalar, key-set, placeholder, and codebase parity.

        Inter-locale key parity is computed from the union of every catalogue,
        so no language is privileged as a canonical reference. Placeholder
        parity is evaluated only for keys shared by all catalogues.

        Returns:
            Immutable structured findings for CLI rendering and quality gates.
        """
        locale_leaves = self._load_audit_leaves()
        key_sets = {name: set(leaves) for name, leaves in locale_leaves.items()}
        all_locale_keys = set().union(*key_sets.values()) if key_sets else set()
        codebase_keys = self.get_codebase_keys()
        namespace_prefixes = self._audit_namespace_prefixes()

        file_results = tuple(
            _audit_locale_file(
                locale_file,
                leaves,
                key_sets[locale_file],
                codebase_keys=codebase_keys,
                all_locale_keys=all_locale_keys,
                namespace_prefixes=namespace_prefixes,
            )
            for locale_file, leaves in locale_leaves.items()
        )
        placeholder_mismatches = _audit_placeholder_mismatches(key_sets, locale_leaves)
        return LocaleAuditResult(file_results, placeholder_mismatches)

    def _discover_locales(self) -> set[str]:
        """Discover available locale codes across sharded directories and legacy files."""
        return discover_locale_codes(self.locales_dir)

    def _load_audit_leaves(self) -> dict[str, dict[str, object]]:
        """Flatten every catalogue's raw leaves keyed by locale file name."""
        leaves_by_locale: dict[str, dict[str, object]] = {}
        for locale in sorted(self._discover_locales()):
            source = locale_catalogue_source(self.locales_dir, locale)
            if source is None:
                continue
            leaves_by_locale[f"{locale}.yml"] = _flatten_raw_locale_leaves(self._load_raw_locale(source))
        return leaves_by_locale

    def _audit_namespace_prefixes(self) -> tuple[str, ...]:
        """Return dynamic-namespace prefixes used to exempt codebase-extra keys."""
        return tuple(
            marker.rstrip("*").rstrip(".")
            for marker in self.get_codebase_namespaces()
            if marker.rstrip("*").rstrip(".")
        )

    def get_yaml_keys(self, d: dict[str, LocaleNode], current_path: str = "") -> set[str]:
        """Recursively extract all dot-notated keys from a nested dictionary."""
        keys = set()
        for k, v in d.items():
            path = f"{current_path}.{k}" if current_path else str(k)
            if isinstance(v, dict):
                keys.update(self.get_yaml_keys(v, path))
            else:
                keys.add(path)
        return keys

    def load_locale(self, path: Path) -> dict[str, LocaleNode]:
        """Load a catalogue from a directory or single YAML file."""
        if path.is_dir():
            merged: dict[str, LocaleNode] = {}
            for shard_file in sorted(path.rglob("*.yml")):
                with open(shard_file, encoding=UTF_8_ENCODING) as f:
                    data = _parse_locale(f)
                _deep_merge_dicts(merged, data)
            return merged
        with open(path, encoding=UTF_8_ENCODING) as f:
            return _parse_locale(f)

    def _load_raw_locale(self, path: Path) -> dict[str, object]:
        """Load a catalogue for auditing without refusing non-string leaves."""
        if path.is_dir():
            merged: dict[str, object] = {}
            for shard_file in sorted(path.rglob("*.yml")):
                with open(shard_file, encoding=UTF_8_ENCODING) as f:
                    shard: dict[str, Any] = dict(_parse_raw_locale(f))
                merged.update(_deep_merge_dicts(dict(merged), shard))
            return merged
        with open(path, encoding=UTF_8_ENCODING) as f:
            return _parse_raw_locale(f)

    def _build_nested_dict(
        self,
        keys: set[str],
        existing_data: dict[str, LocaleNode],
        namespace_prefixes: tuple[str, ...] = (),
    ) -> dict[str, LocaleNode]:
        """Build a sorted, nested dictionary strictly conforming to the required keys."""
        existing_flat = _collect_required_leaves(keys, existing_data)
        for key, value in _flatten_leaf_values(existing_data).items():
            if key in existing_flat or not _covered_by_namespace(key, namespace_prefixes):
                continue
            existing_flat[key] = value

        new_data: dict[str, LocaleNode] = {}
        for key in sorted(keys):
            if key in existing_flat:
                _set_nested_leaf(new_data, key, existing_flat[key])
        for key in sorted(existing_flat):
            if key in keys:
                continue
            _set_nested_leaf(new_data, key, existing_flat[key])
        return new_data

    def scaffold(self) -> None:
        """Parse codebase, generate locale files, auto-sort, and prune extra keys."""
        codebase_keys = self.get_codebase_keys()
        namespace_prefixes = tuple(
            marker.rstrip("*").rstrip(".")
            for marker in self.get_codebase_namespaces()
            if marker.rstrip("*").rstrip(".")
        )

        with catalogue_write_guard(self.locales_dir) as guard:
            for locale in sorted(self._discover_locales()):
                loc_dir = self.locales_dir / locale
                loc_file = self.locales_dir / f"{locale}.yml"

                if loc_dir.is_dir():
                    _scaffold_locale_shards(self, guard, loc_dir, codebase_keys, namespace_prefixes)
                elif loc_file.is_file():
                    try:
                        data = _parse_locale(guard.read_text(loc_file))
                    except (OSError, yaml.YAMLError, LocaleError) as exc:
                        _log.warning(
                            "locale scaffold: failed to parse %s; starting from empty mapping (%s)",
                            loc_file,
                            exc,
                        )
                        data = {}
                        guard.observe(loc_file)

                    new_data = self._build_nested_dict(codebase_keys, data, namespace_prefixes)
                    _rewrite_locale_mapping(guard, loc_file, new_data)

    def canonicalize_product_identity_references(
        self,
        *,
        locale: OutputLanguage | None = None,
    ) -> tuple[Path, ...]:
        """Normalize product identity in one selected or every catalogue."""
        updated_paths: list[Path] = []
        locales = [locale.value] if locale is not None else sorted(self._discover_locales())
        with catalogue_write_guard(self.locales_dir) as guard:
            for loc in locales:
                loc_dir = self.locales_dir / loc
                loc_file = self.locales_dir / f"{loc}.yml"
                if loc_dir.is_dir():
                    for shard_file in sorted(loc_dir.rglob("*.yml")):
                        data = _parse_locale(guard.read_text(shard_file))
                        normalized = _normalise_product_identity_mapping(data)
                        if normalized != data:
                            _rewrite_locale_mapping(guard, shard_file, normalized)
                            updated_paths.append(shard_file)
                elif loc_file.is_file():
                    data = _parse_locale(guard.read_text(loc_file))
                    normalized = _normalise_product_identity_mapping(data)
                    if normalized != data:
                        _rewrite_locale_mapping(guard, loc_file, normalized)
                        updated_paths.append(loc_file)
        return tuple(updated_paths)

    def _locale_path(self, locale: str) -> Path:
        """Resolve a locale code to a contained locale file or directory path."""
        if locale != Path(locale).name or Path(locale).suffix:
            raise LocaleError(f"Invalid locale code: {locale!r}")
        allowed_locales = self._discover_locales()
        if locale not in allowed_locales:
            raise LocaleError(f"Locale file not found: {locale!r}")

        loc_dir = (self.locales_dir / locale).resolve()
        loc_file = (self.locales_dir / f"{locale}.yml").resolve()
        locales_root = self.locales_dir.resolve()

        target = loc_dir if loc_dir.is_dir() else loc_file
        try:
            target.relative_to(locales_root)
        except ValueError as exc:
            raise LocaleError(f"Locale path escapes locale root: {locale!r}") from exc
        if not target.exists():
            raise LocaleError(f"Locale file not found: {target}")
        return target

    def set_locale_value(self, locale: str, dotted_key: str, value: str) -> Path:
        """Set one locale leaf while preserving the YAML layout."""
        if not value.strip():
            raise LocaleError(f"Cannot set {dotted_key!r}: a locale value must not be blank")
        value = normalise_product_identity_references(value)
        parts = dotted_key.split(".")
        if not dotted_key or any(not part for part in parts):
            raise LocaleError(f"Invalid locale key: {dotted_key!r}")

        target = self._locale_path(locale)
        if target.is_dir():
            from cadrumo.core.i18n.routing import route_key_to_shard

            rel_shard = route_key_to_shard(dotted_key)
            shard_path = target / rel_shard
            with catalogue_write_guard(self.locales_dir) as guard:
                if shard_path.is_file():
                    data = _parse_locale(guard.read_text(shard_path))
                else:
                    guard.observe(shard_path)
                    data = {}
                cursor = _resolve_leaf_parent(data, parts, dotted_key=dotted_key)
                cursor[parts[-1]] = value
                _rewrite_locale_mapping(guard, shard_path, data)
            return shard_path

        with catalogue_write_guard(self.locales_dir) as guard:
            data = _parse_locale(guard.read_text(target))
            cursor = _resolve_leaf_parent(data, parts, dotted_key=dotted_key)
            cursor[parts[-1]] = value
            _rewrite_locale_mapping(guard, target, data)
        return target

    def set_locale_values(self, locale: str, values: Mapping[str, str | None]) -> Path:
        """Set a validated batch of leaves with one atomic catalogue rewrite."""
        target = self._locale_path(locale)
        if target.is_dir():
            from cadrumo.core.i18n.routing import route_key_to_shard

            by_shard: dict[Path, dict[str, str | None]] = {}
            for dotted_key, raw_val in values.items():
                rel_shard = route_key_to_shard(dotted_key)
                by_shard.setdefault(rel_shard, {})[dotted_key] = raw_val

            with catalogue_write_guard(self.locales_dir) as guard:
                for rel_shard, shard_vals in sorted(by_shard.items()):
                    shard_path = target / rel_shard
                    if shard_path.is_file():
                        data = _parse_locale(guard.read_text(shard_path))
                    else:
                        guard.observe(shard_path)
                        data = {}
                    for dotted_key, raw_value in sorted(shard_vals.items()):
                        _set_locale_mapping_value(data, dotted_key, raw_value)
                    _rewrite_locale_mapping(guard, shard_path, data)
            return target

        with catalogue_write_guard(self.locales_dir) as guard:
            data = _parse_locale(guard.read_text(target))
            for dotted_key, raw_value in sorted(values.items()):
                _set_locale_mapping_value(data, dotted_key, raw_value)
            _rewrite_locale_mapping(guard, target, data)
        return target

    def remove_locale_value(self, locale: str, dotted_key: str) -> Path:
        """Remove one existing locale leaf."""
        parts = dotted_key.split(".")
        if not dotted_key or any(not part for part in parts):
            raise LocaleError(f"Invalid locale key: {dotted_key!r}")

        target = self._locale_path(locale)
        if target.is_dir():
            from cadrumo.core.i18n.routing import route_key_to_shard

            rel_shard = route_key_to_shard(dotted_key)
            shard_path = target / rel_shard
            if not shard_path.is_file():
                raise LocaleError(f"Locale key not found: {dotted_key!r}")
            with catalogue_write_guard(self.locales_dir) as guard:
                data = _parse_locale(guard.read_text(shard_path))
                _remove_existing_locale_leaf(data, parts, dotted_key)
                _rewrite_locale_mapping(guard, shard_path, data)
            return shard_path

        with catalogue_write_guard(self.locales_dir) as guard:
            data = _parse_locale(guard.read_text(target))
            _remove_existing_locale_leaf(data, parts, dotted_key)
            _rewrite_locale_mapping(guard, target, data)
        return target

    def locale_catalogue_keys(self, locale: str) -> set[str]:
        """Return every dotted leaf key one shipped catalogue carries."""
        return self.get_yaml_keys(self.load_locale(self._locale_path(locale)))

    def remove_locale_values(self, locale: str, dotted_keys: Iterable[str]) -> Path:
        """Atomically remove validated locale leaves from one catalogue."""
        keys = tuple(sorted(set(dotted_keys)))
        if not keys:
            raise LocaleError("At least one locale key is required for batch removal")

        target = self._locale_path(locale)
        if target.is_dir():
            from cadrumo.core.i18n.routing import route_key_to_shard

            by_shard: dict[Path, list[str]] = {}
            for k in keys:
                by_shard.setdefault(route_key_to_shard(k), []).append(k)

            with catalogue_write_guard(self.locales_dir) as guard:
                for rel_shard, shard_keys in by_shard.items():
                    shard_path = target / rel_shard
                    if not shard_path.is_file():
                        continue
                    data = _parse_locale(guard.read_text(shard_path))
                    for dotted_key in shard_keys:
                        _remove_optional_locale_leaf(data, dotted_key)
                    _rewrite_locale_mapping(guard, shard_path, data)
            return target

        with catalogue_write_guard(self.locales_dir) as guard:
            data = _parse_locale(guard.read_text(target))
            for dotted_key in keys:
                _remove_required_locale_leaf(data, dotted_key)
            _rewrite_locale_mapping(guard, target, data)
        return target

    def move_locale_subtree(
        self,
        source_prefix: str,
        destination_prefixes: Sequence[str],
        *,
        keep_source: bool = False,
        drop_undistributed: bool = False,
        on_conflict: LocaleMoveConflict = LocaleMoveConflict.REFUSE,
        dry_run: bool = False,
        permitted_destination_keys: Mapping[str, frozenset[str]] | None = None,
    ) -> LocaleSubtreeMoveResult:
        """Relocate a dotted key subtree in every catalogue, preserving values.

        The whole operation -- every locale, every shard, the destination
        writes and the source releases -- lands inside ONE write guard, so a
        move cannot leave the four catalogues disagreeing about where a key
        lives. That is the property that makes this different from a scripted
        sequence of ``set`` and ``remove`` calls, each of which is atomic
        alone and collectively is not.

        Args:
            source_prefix: The namespace whose leaves are relocated.
            destination_prefixes: One namespace for a rename, several for a
                split.
            keep_source: Copy rather than move, leaving the source in place.
            drop_undistributed: Release a source leaf no destination accepted.
            on_conflict: What to do where a destination already holds a
                different value.
            dry_run: Plan and report without writing.
            permitted_destination_keys: Per-destination allowlist routing each
                leaf to the destination that declares it.

        Returns:
            The plan that was decided and the catalogue files it rewrote.

        Raises:
            LocaleError: The prefixes are malformed, the source holds no
                leaves, a destination conflict was refused, or a source leaf
                would be released without any destination having accepted it.
        """
        source = normalise_key_prefix(source_prefix)
        targets: dict[str, Path] = {}
        leaves_by_locale: dict[str, Mapping[str, str | None]] = {}
        for locale in sorted(self._discover_locales()):
            catalogue = locale_catalogue_source(self.locales_dir, locale)
            if catalogue is None:
                continue
            targets[locale] = catalogue
            leaves_by_locale[locale] = _flatten_leaf_values(self.load_locale(catalogue))

        plan = plan_locale_subtree_move(
            leaves_by_locale,
            source,
            destination_prefixes,
            keep_source=keep_source,
            drop_undistributed=drop_undistributed,
            on_conflict=on_conflict,
            permitted_destination_keys=permitted_destination_keys,
        )
        _refuse_unsound_move(plan)
        if dry_run:
            return LocaleSubtreeMoveResult(plan=plan, dry_run=True, written_paths=())

        written: list[str] = []
        with catalogue_write_guard(self.locales_dir) as guard:
            for locale, target in targets.items():
                written.extend(
                    str(path)
                    for path in self._apply_leaf_edits(
                        guard,
                        target,
                        plan.edits_for(locale),
                        plan.removals_for(locale),
                    )
                )
        return LocaleSubtreeMoveResult(plan=plan, dry_run=False, written_paths=tuple(written))

    def _apply_leaf_edits(
        self,
        guard: CatalogueWriteGuard,
        target: Path,
        edits: Mapping[str, str | None],
        removals: Sequence[str],
    ) -> tuple[Path, ...]:
        """Write and release leaves in one catalogue, one rewrite per shard.

        Destination writes and source releases are applied to the same parsed
        mapping before it is serialised, because a rename lands both on the
        same shard: applying them as two rewrites would make the second refuse
        on the digest the first invalidated.
        """
        if not edits and not removals:
            return ()
        if target.is_dir():
            from cadrumo.core.i18n.routing import route_key_to_shard

            by_shard: dict[Path, tuple[dict[str, str | None], list[str]]] = {}
            for key, value in edits.items():
                shard_edits, _shard_removals = by_shard.setdefault(route_key_to_shard(key), ({}, []))
                shard_edits[key] = value
            for key in removals:
                _shard_edits, shard_removals = by_shard.setdefault(route_key_to_shard(key), ({}, []))
                shard_removals.append(key)

            written: list[Path] = []
            for rel_shard, (shard_edits, shard_removals) in sorted(by_shard.items()):
                shard_path = target / rel_shard
                if shard_path.is_file():
                    data = _parse_locale(guard.read_text(shard_path))
                else:
                    guard.observe(shard_path)
                    data = {}
                _apply_mapping_edits(data, shard_edits, shard_removals)
                _rewrite_locale_mapping(guard, shard_path, data)
                written.append(shard_path)
            return tuple(written)

        data = _parse_locale(guard.read_text(target))
        _apply_mapping_edits(data, edits, removals)
        _rewrite_locale_mapping(guard, target, data)
        return (target,)


def _refuse_unsound_move(plan: LocaleSubtreeMovePlan) -> None:
    """Refuse a planned move that would lose a value or clobber one."""
    if not plan.entries and not plan.removals:
        raise LocaleError(f"No locale keys found under {plan.source_prefix!r}")
    if plan.conflicts:
        sample = ", ".join(sorted({entry.destination_key for entry in plan.conflicts})[:5])
        raise LocaleError(
            f"{len(plan.conflicts)} destination key(s) already carry a different value: {sample}. "
            "Re-run with --on-conflict skip to keep the destination values, "
            "or --on-conflict overwrite to replace them.",
        )
    if plan.undistributed and not plan.keep_source and not plan.drop_undistributed:
        sample = ", ".join(sorted({key for _locale, key in plan.undistributed})[:5])
        raise LocaleError(
            f"{len(plan.undistributed)} source key(s) match no destination: {sample}. "
            "Re-run with --copy to keep the source subtree, "
            "or --drop-undistributed to release them.",
        )


def _scaffold_locale_shards(
    self: LocaleManager,
    guard: CatalogueWriteGuard,
    loc_dir: Path,
    codebase_keys: set[str],
    namespace_prefixes: tuple[str, ...],
) -> None:
    """Scaffold locale shards."""
    from cadrumo.core.i18n.routing import route_key_to_shard

    existing_full = self.load_locale(loc_dir)
    existing_leaves = _flatten_leaf_values(existing_full)

    keys_by_shard: dict[Path, set[str]] = {}
    for key in codebase_keys:
        rel_shard = route_key_to_shard(key)
        keys_by_shard.setdefault(rel_shard, set()).add(key)

    for key in existing_leaves:
        if _covered_by_namespace(key, namespace_prefixes):
            rel_shard = route_key_to_shard(key)
            keys_by_shard.setdefault(rel_shard, set()).add(key)

    all_shards = set(keys_by_shard.keys())
    for f in loc_dir.rglob("*.yml"):
        all_shards.add(f.relative_to(loc_dir))

    for rel_shard in sorted(all_shards):
        _scaffold_locale_shard(self, guard, loc_dir, rel_shard, keys_by_shard, namespace_prefixes)


def _scaffold_locale_shard(
    self: LocaleManager,
    guard: CatalogueWriteGuard,
    loc_dir: Path,
    rel_shard: Path,
    keys_by_shard: dict[Path, set[str]],
    namespace_prefixes: tuple[str, ...],
) -> None:
    """Scaffold locale shard."""
    shard_path = loc_dir / rel_shard
    target_keys = keys_by_shard.get(rel_shard, set())
    if shard_path.is_file():
        try:
            shard_data = _parse_locale(guard.read_text(shard_path))
        except Exception:
            shard_data = {}
            guard.observe(shard_path)
    else:
        guard.observe(shard_path)
        shard_data = {}

    new_data = self._build_nested_dict(target_keys, shard_data, namespace_prefixes)
    if new_data:
        _rewrite_locale_mapping(guard, shard_path, new_data)
    elif shard_path.is_file():
        _rewrite_locale_mapping(guard, shard_path, {})

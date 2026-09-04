"""Locale file management: loading, scaffolding, and structural health checks.

:class:`LocaleManager` owns codebase translation-key discovery and locale YAML
updates. :class:`StrictUniqueKeyLoader` enforces parse-time duplicate-key
rejection, while :data:`LocaleNode` documents the recursive locale-tree shape
shared by the manager and parity tests.
"""

import json
import re
import sys
from collections.abc import Hashable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from enum import Enum, auto
from pathlib import Path
from typing import IO, Any, cast, override

import yaml

from cadrumo.core.directory_scan import iter_directory
from cadrumo.core.external_constants import UTF_8_ENCODING, OutputLanguage
from cadrumo.core.i18n import extract_placeholders
from cadrumo.core.logging import get_logger
from cadrumo.core.product_identity import normalise_product_identity_references

from ._registry_scanner import scan_modelo_schema_keys, scan_profile_schema_keys, scan_registry_keys
from ._revision_drift import RevisionMoveCandidate, classify_revision_moves
from ._subtree_move import (
    LocaleMoveConflict,
    LocaleSubtreeMovePlan,
    LocaleSubtreeMoveResult,
    normalise_key_prefix,
    plan_locale_subtree_move,
)
from ._write_guard import CatalogueWriteGuard, catalogue_write_guard
from .errors import LocaleError

# YAML locale values are either leaf strings or nested dicts of the same shape.
type LocaleNode = str | dict[str, "LocaleNode"] | None

_log = get_logger(__name__)
_INTENTIONAL_IDENTICAL_FILENAME = "_intentional_identical.json"

_MODELO_SCHEMA_PREFIX = "modelo.schema."
"""The one key family whose catalogues accept an explicitly absent value.

Declared here rather than beside its other reader because the scaffold decides
what an unvalued key becomes, and that decision has to agree with the status
report's view of which keys may legitimately be null. Two copies of the literal
would let the writer and the reader disagree about the same key.
"""


class _MissingLocaleLeaf(Enum):
    """Single-member sentinel for a key absent from the catalogue.

    An ``object()`` sentinel forces the resolver's return type to widen to
    ``object``, which erases the node type for every caller. An enum member
    narrows under an identity test, so the union stays meaningful.
    """

    TOKEN = auto()


_MISSING_LOCALE_LEAF = _MissingLocaleLeaf.TOKEN


def _load_intentional_identical(path: Path) -> dict[str, dict[str, object]]:
    """Load the translation-honesty allowlist, tolerating its absence."""
    if not path.is_file():
        return {}
    try:
        loaded = json.loads(path.read_text(encoding=UTF_8_ENCODING))
    except (OSError, json.JSONDecodeError) as exc:
        raise LocaleError(f"Cannot read {path.name}: {exc}") from exc
    if not isinstance(loaded, dict):
        raise LocaleError(f"{path.name} must contain a JSON object")
    # CAST-RATIONALE-JSON-BOUNDARY: the decoded object carries no key or value
    # types, and the isinstance guard above establishes only that it is a
    # mapping. Each entry is checked again below before being copied.
    decoded = cast("dict[str, object]", loaded)
    return {locale: dict(entries) for locale, entries in decoded.items() if isinstance(entries, dict)}


@dataclass(frozen=True)
class LocaleScalarViolation:
    """One locale key whose YAML leaf is not a string."""

    locale_file: str
    key: str
    value_type: str


@dataclass(frozen=True)
class LocalePlaceholderVariant:
    """The placeholder set used by one locale for a shared key."""

    locale_file: str
    placeholders: frozenset[str]


@dataclass(frozen=True)
class LocalePlaceholderMismatch:
    """All differing placeholder variants for one shared locale key."""

    key: str
    variants: tuple[LocalePlaceholderVariant, ...]


@dataclass(frozen=True)
class LocaleFileAudit:
    """Structured audit findings owned by one locale catalogue.

    ``revision_moves`` is a READING of the two key-set findings, never a
    replacement for them: a rename leaves its keys in ``codebase_missing`` and
    ``codebase_extra`` so this catalogue stays un-``ok`` until the move is
    performed. The two ``move_accounted_*`` sets name the keys that reading
    explains, so a report can print each of them once as a relocation instead
    of twice as unrelated work.
    """

    locale_file: str
    codebase_missing: tuple[str, ...]
    codebase_extra: tuple[str, ...]
    inter_locale_missing: tuple[str, ...]
    scalar_violations: tuple[LocaleScalarViolation, ...]
    revision_moves: tuple[RevisionMoveCandidate, ...] = ()
    move_accounted_missing: frozenset[str] = frozenset()
    move_accounted_extra: frozenset[str] = frozenset()

    @property
    def ok(self) -> bool:
        """Return whether this catalogue has no file-local findings."""
        return not (self.codebase_missing or self.codebase_extra or self.inter_locale_missing or self.scalar_violations)


@dataclass(frozen=True)
class LocaleAuditResult:
    """Complete production locale audit across every configured catalogue."""

    files: tuple[LocaleFileAudit, ...]
    placeholder_mismatches: tuple[LocalePlaceholderMismatch, ...]

    @property
    def ok(self) -> bool:
        """Return whether every scalar, key, and placeholder contract passes."""
        return all(file.ok for file in self.files) and not self.placeholder_mismatches


#: libyaml's C scanner where the wheel provides it, PyYAML's Python one where
#: it does not. Only scanning and parsing are C-accelerated; the constructor
#: below stays Python and keeps running for every mapping, which is what lets
#: the duplicate-key refusal survive the swap unchanged.
_CatalogueLoaderBase: type[yaml.SafeLoader] = getattr(yaml, "CSafeLoader", yaml.SafeLoader)


class StrictUniqueKeyLoader(_CatalogueLoaderBase):  # type: ignore[valid-type,misc]
    """YAML loader that raises an error on duplicate keys.

    The catalogues are ~3 MB each, and parsing one measured 9.016s on the pure
    Python base against 0.865s on the C one -- a 10.4x difference paid by every
    caller that reads a catalogue, of which the test layer has many.

    Both bases were confirmed to produce an EQUAL document for the largest
    shipped catalogue, and to raise ``LocaleError`` with the identical message
    and line number on a planted duplicate key, before the base was swapped. A
    faster parser that quietly stopped refusing duplicates would trade this
    module's whole purpose for speed.
    """

    @override
    def construct_mapping(self, node: yaml.MappingNode, deep: bool = False) -> dict[Hashable, Any]:
        """Construct a mapping node, raising ``LocaleError`` on duplicate keys.

        Args:
            node: The YAML mapping node to construct.
            deep: Whether to construct values recursively before returning.

        Returns:
            A plain ``dict`` of the mapping's key-value pairs.

        Raises:
            LocaleError: When a duplicate key is found in the mapping node.
        """
        mapping = {}
        for key_node, value_node in node.value:
            key = self.construct_object(key_node, deep=deep)
            if key in mapping:
                raise LocaleError(f"Duplicate key '{key}' found at line {key_node.start_mark.line + 1}")
            value = self.construct_object(value_node, deep=deep)
            mapping[key] = value
        return mapping


def _parse_locale(source: IO[str] | str) -> dict[str, LocaleNode]:
    """Parse catalogue YAML strictly from an open handle or an in-memory string.

    The string form is what a guarded read produces: the bytes are read and
    fingerprinted once by :class:`CatalogueWriteGuard`, then parsed from memory,
    so the parse cannot see a different file than the one the write is checked
    against.
    """
    loader = StrictUniqueKeyLoader(source)
    try:
        data = loader.get_single_data()
    finally:
        loader.dispose()
    return data if data is not None else {}


def _deep_merge_dicts(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    """Recursively merge overlay dictionary into base dictionary in place."""
    for k, v in overlay.items():
        if k in base and isinstance(base[k], dict) and isinstance(v, dict):
            _deep_merge_dicts(base[k], v)
        else:
            base[k] = v
    return base


def locale_catalogue_source(locales_dir: Path, locale: str) -> Path | None:
    """Return the path :meth:`LocaleManager.load_locale` should read for ``locale``.

    A catalogue ships either as a per-locale shard DIRECTORY or as a single
    flat ``<locale>.yml`` file, and both shapes are live. Every caller that
    wants "the committed catalogue for this locale" must resolve that here
    rather than constructing a path, because a caller that hardcodes one shape
    does not degrade -- it raises :exc:`FileNotFoundError` the moment the tree
    carries the other, and a gate that raises is a gate that has stopped
    checking. Four such call sites went dead exactly that way when the flat
    catalogues were resharded, taking the parity and honesty ratchets with
    them while the suite still reported them as failures rather than as
    silence.

    Returns ``None`` when neither shape is present, so a caller iterating
    discovered locales can skip rather than fabricate a path that cannot be
    read.
    """
    shard_dir = locales_dir / locale
    if shard_dir.is_dir():
        return shard_dir
    flat_file = locales_dir / f"{locale}.yml"
    if flat_file.is_file():
        return flat_file
    return None


def discover_locale_codes(locales_dir: Path) -> set[str]:
    """Return every locale code carried as a shard directory or legacy flat file.

    This is the discovery half of the pair completed by
    :func:`locale_catalogue_source`: discovery answers which catalogues exist,
    resolution answers which path to read for one of them. A caller that wants
    "every committed catalogue" needs both, and must not substitute a glob for
    a single shape. A glob is the more dangerous mistake of the two, because
    the hardcoded-path failure at least raises: a glob for the shape the tree
    does not carry returns an empty result, and an empty result reports as a
    clean pass.
    """
    locales: set[str] = set()
    if not locales_dir.is_dir():
        return locales
    for item in locales_dir.iterdir():
        if item.name.startswith(("_", ".")):
            continue
        if item.is_dir():
            locales.add(item.name)
        elif item.is_file() and item.suffix == ".yml":
            locales.add(item.stem)
    return locales


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

        Combines four discovery paths:

        1. Regex scanner — ``tr("…")`` / ``t("…")`` literal call sites.
        2. AST scanner — programmatic emissions such as
           ``WizardValidationError("wizard.errors.select_unknown")``,
           ``message_key=`` kwargs, and ``build_entry`` portal keys.
        3. F-string registry — bounded f-string patterns whose value sets
           are fully known at import time (e.g. wizard choice labels
           keyed by enum values). See :mod:`locales._fstring_registry`.
        4. Registry scanner — keys declared as data by a committed registry
           rather than by a Python call site: named literally by the category
           profile registry, and derived from declared structure by the
           user-profile schema. The first three paths read Python source
           only, so these were invisible to every parity check and sat
           unresolved in all four catalogues. See
           :mod:`locales._registry_scanner`.

        Dynamic namespaces (open-ended f-string and concatenation forms)
        are returned by :meth:`get_codebase_namespaces` and checked
        through a separate parity assertion that verifies at least one
        concrete locale key exists under each declared prefix.
        """
        from ._ast_scanner import scan_source_tree
        from ._fstring_registry import get_registered_keys

        if self._codebase_keys is not None:
            return set(self._codebase_keys)

        keys: set[str] = set()
        unread: list[str] = []
        for root in (self.src_dir, *self.extra_src_dirs):
            for py_file in iter_directory(root, pattern="*.py", recursive=True):
                if _is_test_module(py_file):
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
            keys.update(scan_source_tree(root))
        keys.update(get_registered_keys())
        keys.update(scan_registry_keys())
        keys.update(scan_profile_schema_keys())
        keys.update(scan_modelo_schema_keys())
        if unread:
            sys.stderr.write(
                f"locale key scan: {len(unread)} module(s) could not be read; any key they use is absent "
                "from this set and would look unused: " + repr(unread) + chr(10)
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
        from ._ast_scanner import scan_namespace_markers

        markers: set[str] = set()
        for root in (self.src_dir, *self.extra_src_dirs):
            markers.update(scan_namespace_markers(root))
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
            leaves_by_locale[f"{locale}.yml"] = _flatten_raw_locale_leaves(self.load_locale(source))
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
        from cadrumo.core.i18n.routing import route_key_to_shard

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

    def set_locale_values(self, locale: str, values: dict[str, str | None]) -> Path:
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
                        parts = dotted_key.split(".")
                        if not dotted_key or any(not part for part in parts):
                            raise LocaleError(f"Invalid locale key: {dotted_key!r}")
                        if raw_value is None:
                            if not dotted_key.startswith("modelo.schema."):
                                raise LocaleError(
                                    f"Only Modelo schema keys may carry an absent locale value: {dotted_key!r}"
                                )
                            value: LocaleNode = None
                        else:
                            if not raw_value.strip():
                                raise LocaleError(f"Cannot set {dotted_key!r}: a locale value must not be blank")
                            value = normalise_product_identity_references(raw_value)
                        _set_nested_leaf(data, dotted_key, value)
                    _rewrite_locale_mapping(guard, shard_path, data)
            return target

        with catalogue_write_guard(self.locales_dir) as guard:
            data = _parse_locale(guard.read_text(target))
            for dotted_key, raw_value in sorted(values.items()):
                parts = dotted_key.split(".")
                if not dotted_key or any(not part for part in parts):
                    raise LocaleError(f"Invalid locale key: {dotted_key!r}")
                if raw_value is None:
                    if not dotted_key.startswith("modelo.schema."):
                        raise LocaleError(f"Only Modelo schema keys may carry an absent locale value: {dotted_key!r}")
                    value: LocaleNode = None
                else:
                    if not raw_value.strip():
                        raise LocaleError(f"Cannot set {dotted_key!r}: a locale value must not be blank")
                    value = normalise_product_identity_references(raw_value)
                _set_nested_leaf(data, dotted_key, value)
            _rewrite_locale_mapping(guard, target, data)
        return target

    def allow_identical(self, locale: str, dotted_key: str, reason: str) -> Path:
        """Record one key as deliberately identical to its source, with a reason."""
        if not reason.strip():
            raise LocaleError(f"Cannot allow {dotted_key!r}: a non-empty reason is required")
        parts = dotted_key.split(".")
        if not dotted_key or any(not part for part in parts):
            raise LocaleError(f"Invalid locale key: {dotted_key!r}")
        if parts[0].startswith("_"):
            raise LocaleError(f"Cannot allow {dotted_key!r}: keys prefixed with '_' are allowlist metadata")

        target = self._locale_path(locale)
        allowlist_path = self.locales_dir / _INTENTIONAL_IDENTICAL_FILENAME

        full_data = self.load_locale(target)
        if dotted_key not in self.get_yaml_keys(full_data):
            name = target.name if target.is_file() else locale
            raise LocaleError(f"Locale key not found in {name}: {dotted_key!r}; run locale scaffold first")
        with catalogue_write_guard(self.locales_dir) as guard:
            guard.observe(allowlist_path)
            allowlist = _load_intentional_identical(allowlist_path)
            allowlist.setdefault(locale, {})[dotted_key] = reason.strip()
            guard.write_text(
                allowlist_path,
                json.dumps(allowlist, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
            )
        return allowlist_path

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
                cursor: LocaleNode = data
                for part in parts:
                    if not isinstance(cursor, dict) or part not in cursor:
                        raise LocaleError(f"Locale key not found: {dotted_key!r}")
                    cursor = cursor[part]
                if isinstance(cursor, dict):
                    raise LocaleError(f"Cannot remove {dotted_key!r}: it resolves to a namespace")

                parent = _resolve_leaf_parent(data, parts, dotted_key=dotted_key)
                del parent[parts[-1]]
                _prune_empty_namespaces(data, parts[:-1])
                _rewrite_locale_mapping(guard, shard_path, data)
            return shard_path

        with catalogue_write_guard(self.locales_dir) as guard:
            data = _parse_locale(guard.read_text(target))
            cursor: LocaleNode = data
            for part in parts:
                if not isinstance(cursor, dict) or part not in cursor:
                    raise LocaleError(f"Locale key not found: {dotted_key!r}")
                cursor = cursor[part]
            if isinstance(cursor, dict):
                raise LocaleError(f"Cannot remove {dotted_key!r}: it resolves to a namespace")

            parent = _resolve_leaf_parent(data, parts, dotted_key=dotted_key)
            del parent[parts[-1]]
            _prune_empty_namespaces(data, parts[:-1])
            _rewrite_locale_mapping(guard, target, data)
        return target

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
                        parts = dotted_key.split(".")
                        cursor: LocaleNode = data
                        for part in parts:
                            if not isinstance(cursor, dict) or part not in cursor:
                                break
                            cursor = cursor[part]
                        else:
                            if not isinstance(cursor, dict):
                                parent = _resolve_leaf_parent(data, parts, dotted_key=dotted_key)
                                del parent[parts[-1]]
                                _prune_empty_namespaces(data, parts[:-1])
                    _rewrite_locale_mapping(guard, shard_path, data)
            return target

        with catalogue_write_guard(self.locales_dir) as guard:
            data = _parse_locale(guard.read_text(target))
            for dotted_key in keys:
                parts = dotted_key.split(".")
                if not dotted_key or any(not part for part in parts):
                    raise LocaleError(f"Invalid locale key: {dotted_key!r}")
                cursor: LocaleNode = data
                for part in parts:
                    if not isinstance(cursor, dict) or part not in cursor:
                        raise LocaleError(f"Locale key not found: {dotted_key!r}")
                    cursor = cursor[part]
                if isinstance(cursor, dict):
                    raise LocaleError(f"Cannot remove {dotted_key!r}: it resolves to a namespace")

                parent = _resolve_leaf_parent(data, parts, dotted_key=dotted_key)
                del parent[parts[-1]]
                _prune_empty_namespaces(data, parts[:-1])
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


def _apply_mapping_edits(
    data: dict[str, LocaleNode],
    edits: Mapping[str, str | None],
    removals: Sequence[str],
) -> None:
    """Set every edit and delete every removal inside one parsed catalogue mapping."""
    for dotted_key, value in sorted(edits.items()):
        _set_nested_leaf(data, dotted_key, value)
    for dotted_key in sorted(removals):
        parts = dotted_key.split(".")
        cursor: LocaleNode = data
        for part in parts:
            if not isinstance(cursor, dict) or part not in cursor:
                break
            cursor = cursor[part]
        else:
            if not isinstance(cursor, dict):
                parent = _resolve_leaf_parent(data, parts, dotted_key=dotted_key)
                del parent[parts[-1]]
                _prune_empty_namespaces(data, parts[:-1])


def _audit_locale_file(
    locale_file: str,
    leaves: dict[str, object],
    keys: set[str],
    *,
    codebase_keys: set[str],
    all_locale_keys: set[str],
    namespace_prefixes: tuple[str, ...],
) -> LocaleFileAudit:
    """Compute one catalogue's key-set, scalar, and revision-move findings."""
    violations = tuple(
        LocaleScalarViolation(locale_file, key, type(value).__name__)
        for key, value in sorted(leaves.items())
        if not isinstance(value, str) and not (value is None and key.startswith("modelo.schema."))
    )
    codebase_missing = tuple(sorted(codebase_keys - keys))
    codebase_extra = tuple(
        sorted(key for key in keys - codebase_keys if not _covered_by_namespace(key, namespace_prefixes))
    )
    moves = classify_revision_moves(locale_file, codebase_missing, codebase_extra)
    return LocaleFileAudit(
        locale_file=locale_file,
        codebase_missing=codebase_missing,
        codebase_extra=codebase_extra,
        inter_locale_missing=tuple(sorted(all_locale_keys - keys)),
        scalar_violations=violations,
        revision_moves=moves.candidates,
        move_accounted_missing=moves.accounted_missing,
        move_accounted_extra=moves.accounted_extra,
    )


def _audit_placeholder_mismatches(
    key_sets: dict[str, set[str]],
    locale_leaves: dict[str, dict[str, object]],
) -> tuple[LocalePlaceholderMismatch, ...]:
    """Return placeholder-parity mismatches across keys shared by every catalogue."""
    shared_keys = set.intersection(*key_sets.values()) if key_sets else set()
    mismatches: list[LocalePlaceholderMismatch] = []
    for key in sorted(shared_keys):
        values = {name: leaves[key] for name, leaves in locale_leaves.items()}
        if not all(isinstance(value, str) for value in values.values()):
            continue
        variants = tuple(
            LocalePlaceholderVariant(name, extract_placeholders(value))
            for name, value in sorted(values.items())
            if isinstance(value, str)
        )
        if len({variant.placeholders for variant in variants}) > 1:
            mismatches.append(LocalePlaceholderMismatch(key, variants))
    return tuple(mismatches)


def _collect_required_leaves(
    keys: set[str],
    existing_data: dict[str, LocaleNode],
) -> dict[str, LocaleNode]:
    """Resolve each dotted ``key`` against ``existing_data`` to its leaf value.

    Returns a flat ``{dotted_key: value}`` map holding only keys that have a
    value. A key that resolves to a non-dict leaf carries its existing
    translation; a MISSING key -- absent, or bottoming out at an interior node
    -- is handled by what the catalogues actually accept for "no translation
    yet", which is not one answer:

    * A Modelo-schema key carries ``None``. That is the representation
      :meth:`LocaleManager.set_locale_values` already reserves for exactly
      these keys: it holds inter-locale key parity without fabricating text,
      and the Modelo resolver then applies its documented Spanish-source
      fallback.
    * Any other key is OMITTED. The parity check reports it as missing, which
      is an honest statement that the author still owes four values, and
      ``set`` creates it with the first real one.

    **Neither writes the key's own dotted path as its value, and that is the
    whole change.** Doing so was described here as the scaffold convention for
    "no translation yet", but no consumer in the tree accepts it: the
    translation-honesty ratchet refuses a key-echo outright, and three separate
    coverage gates fail on one. A convention nothing reads is not a convention,
    and this was its only producer -- so every echo the catalogues carried was
    written here and forbidden everywhere else.

    The failure directions are not symmetric, which is why omission is right
    rather than merely tidier. An omitted key costs the authoring lane a
    missing-key report it can clear with the values only it knows. An echoed
    key costs EVERY lane a red honesty gate it did not cause, cannot clear
    without those same values, and meets while working on something else.
    """
    resolved: dict[str, LocaleNode] = {}
    for key in keys:
        leaf = _resolve_leaf(existing_data, key.split("."))
        if leaf is not _MISSING_LOCALE_LEAF:
            resolved[key] = leaf
        elif key.startswith(_MODELO_SCHEMA_PREFIX):
            resolved[key] = None
    return resolved


def _resolve_leaf(existing_data: dict[str, LocaleNode], parts: list[str]) -> LocaleNode | _MissingLocaleLeaf:
    """Walk ``parts`` and distinguish an authored null from a missing leaf."""
    curr: LocaleNode = existing_data
    for part in parts:
        if not isinstance(curr, dict) or part not in curr:
            return _MISSING_LOCALE_LEAF
        curr = curr[part]
    return _MISSING_LOCALE_LEAF if isinstance(curr, dict) else curr


def _prune_empty_namespaces(root: dict[str, LocaleNode], parts: list[str]) -> None:
    """Delete namespaces left empty by a removal, innermost first.

    Walks the parsed mapping rather than the file's lines, so a namespace whose
    key YAML quotes is pruned like any other. Stops at the first ancestor that
    still holds something: an empty parent is a namespace nothing addresses,
    while a populated one is still in use by its remaining children.
    """
    for depth in range(len(parts), 0, -1):
        cursor: LocaleNode = root
        for part in parts[: depth - 1]:
            if not isinstance(cursor, dict):
                return
            cursor = cursor.get(part)
        if not isinstance(cursor, dict):
            return
        child = cursor.get(parts[depth - 1])
        if not isinstance(child, dict) or child:
            return
        del cursor[parts[depth - 1]]


def _set_nested_leaf(root: dict[str, LocaleNode], dotted_key: str, value: LocaleNode) -> None:
    """Write ``value`` at ``dotted_key`` inside ``root``, creating sub-dicts as needed."""
    parts = dotted_key.split(".")
    curr: dict[str, LocaleNode] = root
    for part in parts[:-1]:
        child = curr.get(part)
        if not isinstance(child, dict):
            child = {}
            curr[part] = child
        curr = child
    curr[parts[-1]] = value


def _resolve_leaf_parent(
    data: dict[str, LocaleNode],
    parts: list[str],
    *,
    dotted_key: str,
) -> dict[str, LocaleNode]:
    """Walk to the mapping that owns ``parts[-1]``, refusing every wrong shape.

    Each refusal names what the path actually resolved to, so an operator who
    addressed a namespace or a leaf's child is told which of those happened.

    **A namespace that does not exist yet is CREATED rather than refused**, and
    the batch writer beside this one has always done so through
    :func:`_set_nested_leaf`; the two disagreed about the same operation. The
    refusal here said "run locale scaffold first", which was only ever true
    because the scaffold answered it by writing the key's own dotted path as a
    placeholder -- a value the honesty ratchet and three coverage gates all
    refuse. So the one route to a new key ran through a value nothing accepts.
    Creating the namespace is what lets the scaffold stop fabricating: an author
    adds a ``tr()`` call and supplies the four values directly, and no
    unvalued key exists at any point.

    The shape refusals below are unchanged. Addressing a namespace as a leaf, or
    a leaf's child, is still a mistake about the catalogue rather than a key
    that does not exist yet.
    """
    cursor: LocaleNode = data
    for part in parts[:-1]:
        if isinstance(cursor, dict) and part not in cursor:
            cursor[part] = {}
        if not isinstance(cursor, dict):
            raise LocaleError(f"Cannot set {dotted_key!r}: parent path resolves to a leaf")
        cursor = cursor[part]
    if not isinstance(cursor, dict):
        raise LocaleError(f"Cannot set {dotted_key!r}: parent path resolves to a leaf")
    if isinstance(cursor.get(parts[-1]), dict):
        raise LocaleError(f"Cannot set {dotted_key!r}: it resolves to a namespace")
    return cursor


def _normalise_product_identity_node(value: LocaleNode) -> LocaleNode:
    """Recursively normalize stale human-command references."""
    if isinstance(value, dict):
        return _normalise_product_identity_mapping(value)
    if isinstance(value, str):
        return normalise_product_identity_references(value)
    return value


def _normalise_product_identity_mapping(value: dict[str, LocaleNode]) -> dict[str, LocaleNode]:
    """Normalize a locale mapping while preserving its mapping type."""
    return {key: _normalise_product_identity_node(child) for key, child in value.items()}


def _rewrite_locale_mapping(guard: CatalogueWriteGuard, path: Path, data: dict[str, LocaleNode]) -> None:
    """Replace a locale mapping after strict parsing, through the write guard.

    The locale CLI may be interrupted by an operator or orchestration timeout.
    Writing directly to the catalogue would expose a truncated YAML file between
    ``open(..., "w")`` and the final flush, so serialize in memory and persist
    through the guard, which performs the atomic replace and first refuses the
    write if the catalogue moved since this edit read it.
    """
    serialised = yaml.dump(data, allow_unicode=True, sort_keys=True, default_flow_style=False)
    guard.write_text(path, serialised)


def _flatten_leaf_values(mapping: dict[str, LocaleNode], prefix: str = "") -> dict[str, str | None]:
    """Return leaf locale values keyed by dotted path."""
    flattened: dict[str, str | None] = {}
    for key, value in mapping.items():
        path = f"{prefix}.{key}" if prefix else str(key)
        if isinstance(value, dict):
            flattened.update(_flatten_leaf_values(value, path))
        else:
            flattened[path] = value
    return flattened


def _flatten_raw_locale_leaves(value: object, prefix: str = "") -> dict[str, object]:
    """Flatten parsed YAML without coercing invalid scalar types to strings."""
    if isinstance(value, dict):
        flattened: dict[str, object] = {}
        for key, child in value.items():
            path = f"{prefix}.{key}" if prefix else str(key)
            flattened.update(_flatten_raw_locale_leaves(child, path))
        return flattened
    return {prefix or "<root>": value}


def _covered_by_namespace(key: str, namespace_prefixes: tuple[str, ...]) -> bool:
    """Return whether a dotted locale key belongs to a dynamic namespace."""
    return any(f".{prefix}." in f".{key}." for prefix in namespace_prefixes)


def _is_test_module(path: Path) -> bool:
    """Return whether ``path`` is a test module rather than production code.

    Mirrors the AST scanner's exclusion so both key-discovery paths agree
    on what counts as a production call site.
    """
    return path.name.startswith(("test_", "_test_")) or "tests" in path.parts

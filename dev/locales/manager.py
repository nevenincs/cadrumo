"""Locale file management: loading, scaffolding, and structural health checks.

:class:`LocaleManager` owns codebase translation-key discovery and locale YAML
updates. :class:`StrictUniqueKeyLoader` enforces parse-time duplicate-key
rejection, while :data:`LocaleNode` documents the recursive locale-tree shape
shared by the manager and parity tests.
"""

import json
import re
from collections.abc import Hashable, Iterable
from dataclasses import dataclass
from enum import Enum, auto
from pathlib import Path
from typing import IO, Any, cast, override

import yaml

from cadrumo.core import iter_directory, normalise_product_identity_references, scan_directory
from cadrumo.core.external_constants import UTF_8_ENCODING, OutputLanguage
from cadrumo.core.i18n import extract_placeholders
from cadrumo.core.logging import get_logger

from ._errors import LocaleError
from ._registry_scanner import scan_modelo_schema_keys, scan_profile_schema_keys, scan_registry_keys
from ._write_guard import CatalogueWriteGuard, catalogue_write_guard

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
    """Structured audit findings owned by one locale catalogue."""

    locale_file: str
    codebase_missing: tuple[str, ...]
    codebase_extra: tuple[str, ...]
    inter_locale_missing: tuple[str, ...]
    scalar_violations: tuple[LocaleScalarViolation, ...]

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

        keys: set[str] = set()
        for root in (self.src_dir, *self.extra_src_dirs):
            for py_file in iter_directory(root, pattern="*.py", recursive=True):
                if _is_test_module(py_file):
                    continue
                try:
                    content = py_file.read_text(encoding=UTF_8_ENCODING, errors="ignore")
                except OSError as exc:
                    _log.debug("locale key scan: skipping %s (%s)", py_file, exc)
                    continue
                for match in self.pattern.finditer(content):
                    keys.add(match.group(1))
            keys.update(scan_source_tree(root))
        keys.update(get_registered_keys())
        keys.update(scan_registry_keys())
        keys.update(scan_profile_schema_keys())
        keys.update(scan_modelo_schema_keys())
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

    def _load_audit_leaves(self) -> dict[str, dict[str, object]]:
        """Flatten every catalogue's raw leaves keyed by locale file name."""
        locale_paths = scan_directory(self.locales_dir, pattern="*.yml")
        return {path.name: _flatten_raw_locale_leaves(self.load_locale(path)) for path in locale_paths}

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
        if isinstance(d, dict):
            for k, v in d.items():
                path = f"{current_path}.{k}" if current_path else k
                if isinstance(v, dict):
                    keys.update(self.get_yaml_keys(v, path))
                else:
                    keys.add(path)
        return keys

    def load_locale(self, path: Path) -> dict[str, LocaleNode]:
        """Load a locale YAML file strictly, failing on duplicates.

        For read-only callers. A read that precedes a write must instead go
        through :meth:`CatalogueWriteGuard.read_text` and
        :func:`_parse_locale_text`, so the write can be refused if the file
        moves underneath it.
        """
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
        codebase_keys = self.get_codebase_keys()
        namespace_prefixes = tuple(
            marker.rstrip("*").rstrip(".")
            for marker in self.get_codebase_namespaces()
            if marker.rstrip("*").rstrip(".")
        )

        with catalogue_write_guard(self.locales_dir) as guard:
            for f in scan_directory(self.locales_dir, pattern="*.yml"):
                try:
                    data = _parse_locale(guard.read_text(f))
                except (OSError, yaml.YAMLError, LocaleError) as exc:
                    _log.warning(
                        "locale scaffold: failed to parse %s; starting from empty mapping (%s)",
                        f,
                        exc,
                    )
                    data = {}
                    guard.observe(f)

                new_data = self._build_nested_dict(codebase_keys, data, namespace_prefixes)

                _rewrite_locale_mapping(guard, f, new_data)

    def canonicalize_product_identity_references(
        self,
        *,
        locale: OutputLanguage | None = None,
    ) -> tuple[Path, ...]:
        """Normalize product identity in one selected or every catalogue.

        Args:
            locale: One supported output language to update. When omitted, update
                every catalogue as the pre-selector command did.

        Returns:
            Paths whose parsed locale content changed.
        """
        locale_paths = (
            (self._locale_path(locale.value),)
            if locale is not None
            else scan_directory(self.locales_dir, pattern="*.yml")
        )
        updated_paths: list[Path] = []
        with catalogue_write_guard(self.locales_dir) as guard:
            for locale_path in locale_paths:
                data = _parse_locale(guard.read_text(locale_path))
                normalized = _normalise_product_identity_mapping(data)
                if normalized == data:
                    continue
                _rewrite_locale_mapping(guard, locale_path, normalized)
                updated_paths.append(locale_path)
        return tuple(updated_paths)

    def _locale_path(self, locale: str) -> Path:
        """Resolve a locale code to a contained locale file path."""
        if locale != Path(locale).name or Path(locale).suffix:
            raise LocaleError(f"Invalid locale code: {locale!r}")
        allowed_locales = {path.stem for path in iter_directory(self.locales_dir, pattern="*.yml")}
        if locale not in allowed_locales:
            raise LocaleError(f"Locale file not found: {locale!r}")

        locale_path = (self.locales_dir / f"{locale}.yml").resolve()
        locales_root = self.locales_dir.resolve()
        try:
            locale_path.relative_to(locales_root)
        except ValueError as exc:
            raise LocaleError(f"Locale path escapes locale root: {locale!r}") from exc
        if not locale_path.is_file():
            raise LocaleError(f"Locale file not found: {locale_path}")
        return locale_path

    def set_locale_value(self, locale: str, dotted_key: str, value: str) -> Path:
        """Set one locale leaf while preserving the YAML layout.

        A blank value is refused: an empty or whitespace-only leaf reads
        as authored prose to nothing and as a silent gap to the operator,
        so it must never enter a catalogue through the CLI.
        """
        if not value.strip():
            raise LocaleError(f"Cannot set {dotted_key!r}: a locale value must not be blank")
        locale_path = self._locale_path(locale)
        value = normalise_product_identity_references(value)
        parts = dotted_key.split(".")
        if not dotted_key or any(not part for part in parts):
            raise LocaleError(f"Invalid locale key: {dotted_key!r}")

        with catalogue_write_guard(self.locales_dir) as guard:
            # Both branches go through the parsed mapping. A line-oriented
            # writer cannot address a key YAML quotes -- every casilla id is
            # written ``'1076':`` -- so an append that scanned text refused any
            # key under a quoted ancestor while this same call updated one that
            # already existed. One authority, so the two cannot diverge again.
            data = _parse_locale(guard.read_text(locale_path))
            cursor = _resolve_leaf_parent(data, parts, dotted_key=dotted_key)
            cursor[parts[-1]] = value
            _rewrite_locale_mapping(guard, locale_path, data)
        return locale_path

    def set_locale_values(self, locale: str, values: dict[str, str | None]) -> Path:
        """Set a validated batch of leaves with one atomic catalogue rewrite.

        ``None`` is reserved for an explicitly absent optional Modelo-schema
        translation.  It keeps inter-locale key parity without fabricating text;
        the Modelo resolver then applies its Spanish-source fallback policy.
        """
        locale_path = self._locale_path(locale)
        with catalogue_write_guard(self.locales_dir) as guard:
            data = _parse_locale(guard.read_text(locale_path))
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
            _rewrite_locale_mapping(guard, locale_path, data)
        return locale_path

    def allow_identical(self, locale: str, dotted_key: str, reason: str) -> Path:
        """Record one key as deliberately identical to its source, with a reason.

        The allowlist exempts a string from the translation-honesty ratchet.
        It is for strings that are legitimately the same in both languages —
        a brand name, a bare modelo code — never a mute button for a string
        nobody has translated yet, so the reason is mandatory.

        Args:
            locale: Locale code owning the exemption.
            dotted_key: Dotted locale key to exempt.
            reason: Why this string is legitimately identical to its source.

        Returns:
            The allowlist path that was rewritten.

        Raises:
            LocaleError: When the reason is blank, the key is metadata, or
                the key is absent from the locale's catalogue.
        """
        if not reason.strip():
            raise LocaleError(f"Cannot allow {dotted_key!r}: a non-empty reason is required")
        parts = dotted_key.split(".")
        if not dotted_key or any(not part for part in parts):
            raise LocaleError(f"Invalid locale key: {dotted_key!r}")
        if parts[0].startswith("_"):
            raise LocaleError(f"Cannot allow {dotted_key!r}: keys prefixed with '_' are allowlist metadata")

        locale_path = self._locale_path(locale)
        allowlist_path = self.locales_dir / _INTENTIONAL_IDENTICAL_FILENAME
        with catalogue_write_guard(self.locales_dir) as guard:
            if dotted_key not in self.get_yaml_keys(_parse_locale(guard.read_text(locale_path))):
                raise LocaleError(
                    f"Locale key not found in {locale_path.name}: {dotted_key!r}; run locale scaffold first"
                )

            guard.observe(allowlist_path)
            allowlist = _load_intentional_identical(allowlist_path)
            allowlist.setdefault(locale, {})[dotted_key] = reason.strip()
            guard.write_text(
                allowlist_path,
                json.dumps(allowlist, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
            )
        return allowlist_path

    def remove_locale_value(self, locale: str, dotted_key: str) -> Path:
        """Remove one existing locale leaf.

        Resolved and deleted through the PARSED mapping, the same authority
        the setters use. The previous implementation validated structurally and
        then deleted by scanning YAML text, and the two disagreed on any key
        YAML quotes: every casilla id is written ``'1076':``, so the scan never
        matched it and the verb refused a leaf it had just resolved. There was
        then no sanctioned way to return such a leaf to absent, because
        hand-editing a catalogue is forbidden.
        """
        locale_path = self._locale_path(locale)
        parts = dotted_key.split(".")
        if not dotted_key or any(not part for part in parts):
            raise LocaleError(f"Invalid locale key: {dotted_key!r}")

        with catalogue_write_guard(self.locales_dir) as guard:
            data = _parse_locale(guard.read_text(locale_path))
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
            _rewrite_locale_mapping(guard, locale_path, data)
        return locale_path

    def remove_locale_values(self, locale: str, dotted_keys: Iterable[str]) -> Path:
        """Atomically remove validated locale leaves from one catalogue."""
        locale_path = self._locale_path(locale)
        keys = tuple(sorted(set(dotted_keys)))
        if not keys:
            raise LocaleError("At least one locale key is required for batch removal")

        with catalogue_write_guard(self.locales_dir) as guard:
            data = _parse_locale(guard.read_text(locale_path))
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
            _rewrite_locale_mapping(guard, locale_path, data)
        return locale_path


def _audit_locale_file(
    locale_file: str,
    leaves: dict[str, object],
    keys: set[str],
    *,
    codebase_keys: set[str],
    all_locale_keys: set[str],
    namespace_prefixes: tuple[str, ...],
) -> LocaleFileAudit:
    """Compute one catalogue's key-set and scalar findings."""
    violations = tuple(
        LocaleScalarViolation(locale_file, key, type(value).__name__)
        for key, value in sorted(leaves.items())
        if not isinstance(value, str) and not (value is None and key.startswith("modelo.schema."))
    )
    return LocaleFileAudit(
        locale_file=locale_file,
        codebase_missing=tuple(sorted(codebase_keys - keys)),
        codebase_extra=tuple(
            sorted(key for key in keys - codebase_keys if not _covered_by_namespace(key, namespace_prefixes))
        ),
        inter_locale_missing=tuple(sorted(all_locale_keys - keys)),
        scalar_violations=violations,
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
        if part not in curr or not isinstance(curr[part], dict):
            curr[part] = {}
        child = curr[part]
        assert isinstance(child, dict)  # narrowed by the line above
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

"""Locale file management: loading, scaffolding, and structural health checks."""

import re
from collections.abc import Iterator
from pathlib import Path
from typing import override

import yaml

from ..core.errors import AeatError
from ..core.external_constants import UTF_8_ENCODING
from ..core.logging import get_logger

# YAML locale values are either leaf strings or nested dicts of the same shape.
type LocaleNode = str | dict[str, "LocaleNode"]

_log = get_logger(__name__)
_YAML_KEY_PATTERN = re.compile(r"^(?P<indent> *)(?P<key>[\w-]+):(?P<rest>.*)$")


class LocaleError(AeatError):
    """Raised on locale management and parsing errors."""


class StrictUniqueKeyLoader(yaml.SafeLoader):
    """YAML loader that raises an error on duplicate keys."""

    @override
    def construct_mapping(self, node: yaml.MappingNode, deep: bool = False) -> dict:
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


class LocaleManager:
    """API for managing locale files, scaffolding, and structural health."""

    def __init__(self, src_dir: Path, locales_dir: Path):
        """Initialise the manager with the source tree and locale file directory.

        Args:
            src_dir: Root directory of the Python source tree to scan for translation keys.
            locales_dir: Directory containing ``*.yml`` locale files.
        """
        self.src_dir = src_dir
        self.locales_dir = locales_dir
        self.pattern = re.compile(r'\b(?:tr|t)\(\s*["\'](\w+(?:\.\w+)+)["\']', re.UNICODE)

    def get_codebase_keys(self) -> set[str]:
        """Extract all concrete dotted translation keys from the codebase.

        Combines three discovery paths:

        1. Regex scanner — ``tr("…")`` / ``t("…")`` literal call sites.
        2. AST scanner — programmatic emissions such as
           ``WizardValidationError("wizard.errors.select_unknown")``,
           ``message_key=`` kwargs, and ``build_entry`` portal keys.
        3. F-string registry — bounded f-string patterns whose value sets
           are fully known at import time (e.g. wizard choice labels
           keyed by enum values). See :mod:`aeat.locales._fstring_registry`.

        Dynamic namespaces (open-ended f-string and concatenation forms)
        are returned by :meth:`get_codebase_namespaces` and checked
        through a separate parity assertion that verifies at least one
        concrete locale key exists under each declared prefix.
        """
        from ._ast_scanner import scan_source_tree
        from ._fstring_registry import get_registered_keys

        keys: set[str] = set()
        for py_file in self.src_dir.rglob("*.py"):
            if py_file.name == "test_parity.py" or py_file.name == "manager.py":
                continue
            try:
                content = py_file.read_text(encoding=UTF_8_ENCODING, errors="ignore")
            except OSError as exc:
                _log.debug("locale key scan: skipping %s (%s)", py_file, exc)
                continue
            for match in self.pattern.finditer(content):
                keys.add(match.group(1))
        keys.update(scan_source_tree(self.src_dir))
        keys.update(get_registered_keys())
        return keys

    def get_codebase_namespaces(self) -> set[str]:
        """Extract dynamic-namespace markers (``<prefix>.*``) from the codebase.

        Returns every prefix discovered through f-string or string
        concatenation patterns whose tail is computed at runtime.
        Each marker passes the parity check when at least one
        concrete locale key starts with its prefix.
        """
        from ._ast_scanner import scan_namespace_markers

        return scan_namespace_markers(self.src_dir)

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
        """Load a locale YAML file strictly, failing on duplicates."""
        with open(path, encoding=UTF_8_ENCODING) as f:
            loader = StrictUniqueKeyLoader(f)
            try:
                data = loader.get_single_data()
            finally:
                loader.dispose()
            return data if data is not None else {}

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

        for f in self.locales_dir.glob("*.yml"):
            try:
                data = self.load_locale(f)
            except (OSError, yaml.YAMLError, LocaleError) as exc:
                _log.warning(
                    "locale scaffold: failed to parse %s; starting from empty mapping (%s)",
                    f,
                    exc,
                )
                data = {}

            new_data = self._build_nested_dict(codebase_keys, data, namespace_prefixes)

            with open(f, "w", encoding=UTF_8_ENCODING) as f_obj:
                yaml.dump(new_data, f_obj, allow_unicode=True, sort_keys=True, default_flow_style=False)

    def _locale_path(self, locale: str) -> Path:
        """Resolve a locale code to a contained locale file path."""
        if locale != Path(locale).name or Path(locale).suffix:
            raise LocaleError(f"Invalid locale code: {locale!r}")
        allowed_locales = {path.stem for path in self.locales_dir.glob("*.yml")}
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
        """Set one locale leaf while preserving the YAML layout."""
        locale_path = self._locale_path(locale)
        parts = dotted_key.split(".")
        if not dotted_key or any(not part for part in parts):
            raise LocaleError(f"Invalid locale key: {dotted_key!r}")

        cursor: LocaleNode = self.load_locale(locale_path)
        for part in parts[:-1]:
            if not isinstance(cursor, dict) or part not in cursor:
                raise LocaleError(f"Locale key not found: {dotted_key!r}; run locale scaffold first")
            cursor = cursor[part]
        if not isinstance(cursor, dict):
            raise LocaleError(f"Cannot set {dotted_key!r}: parent path resolves to a leaf")
        leaf_exists = parts[-1] in cursor
        existing = cursor.get(parts[-1])
        if isinstance(existing, dict):
            raise LocaleError(f"Cannot set {dotted_key!r}: it resolves to a namespace")

        if leaf_exists:
            _replace_existing_yaml_leaf(locale_path, parts, value)
        else:
            _append_yaml_leaf(locale_path, parts, value)
        return locale_path

    def remove_locale_value(self, locale: str, dotted_key: str) -> Path:
        """Remove one existing locale leaf while preserving the YAML layout."""
        locale_path = self._locale_path(locale)
        parts = dotted_key.split(".")
        if not dotted_key or any(not part for part in parts):
            raise LocaleError(f"Invalid locale key: {dotted_key!r}")

        cursor: LocaleNode = self.load_locale(locale_path)
        for part in parts:
            if not isinstance(cursor, dict) or part not in cursor:
                raise LocaleError(f"Locale key not found: {dotted_key!r}")
            cursor = cursor[part]
        if isinstance(cursor, dict):
            raise LocaleError(f"Cannot remove {dotted_key!r}: it resolves to a namespace")

        _remove_existing_yaml_leaf(locale_path, parts)
        return locale_path


def _collect_required_leaves(
    keys: set[str],
    existing_data: dict[str, LocaleNode],
) -> dict[str, LocaleNode]:
    """Resolve each dotted ``key`` against ``existing_data`` to its leaf value.

    Returns a flat ``{dotted_key: value}`` map. A key that resolves to a
    non-dict leaf carries its existing translation; a key that is
    missing or whose path bottoms out at a dict (i.e. an interior node,
    not a leaf) carries its own dotted path as a placeholder — the
    scaffold convention for "no translation yet".
    """
    resolved: dict[str, LocaleNode] = {}
    for key in keys:
        leaf = _resolve_leaf(existing_data, key.split("."))
        resolved[key] = leaf if leaf is not None else key
    return resolved


def _resolve_leaf(existing_data: dict[str, LocaleNode], parts: list[str]) -> LocaleNode | None:
    """Walk ``parts`` through ``existing_data`` and return the leaf value, or None."""
    curr: LocaleNode = existing_data
    for part in parts:
        if not isinstance(curr, dict) or part not in curr:
            return None
        curr = curr[part]
    return None if isinstance(curr, dict) else curr


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


def _yaml_quoted_scalar(value: str) -> str:
    """Render a scalar as a single-physical-line YAML quoted string.

    Single-quoted style cannot carry a literal line break on one physical
    line (the parser folds raw breaks into spaces), so values containing
    control characters are rendered double-quoted with escape sequences.
    Either form occupies exactly one line, which the line-based leaf
    writers (:func:`_replace_existing_yaml_leaf`, :func:`_append_yaml_leaf`)
    rely on.
    """
    if any(ch in value for ch in ("\n", "\r", "\t")):
        escaped = (
            value.replace("\\", "\\\\")
            .replace('"', '\\"')
            .replace("\n", "\\n")
            .replace("\r", "\\r")
            .replace("\t", "\\t")
        )
        return '"' + escaped + '"'
    escaped = value.replace("'", "''")
    return "'" + escaped + "'"


def _yaml_leaf_end(lines: list[str], start: int, indent: int) -> int:
    """Return the slice end for a scalar leaf and its indented continuation."""
    end = start + 1
    while end < len(lines):
        match = _YAML_KEY_PATTERN.match(lines[end])
        if match is not None and len(match.group("indent")) <= indent:
            break
        end += 1
    return end


def _iter_yaml_key_matches(lines: list[str]) -> Iterator[tuple[int, re.Match[str], int, str, str, list[str]]]:
    """Yield YAML key lines with their active dotted path parts."""
    stack: list[tuple[int, str]] = []

    for index, line in enumerate(lines):
        match = _YAML_KEY_PATTERN.match(line)
        if match is None:
            continue

        indent = len(match.group("indent"))
        key = match.group("key")
        rest = match.group("rest")
        while stack and stack[-1][0] >= indent:
            stack.pop()

        yield index, match, indent, key, rest, [item for _, item in stack] + [key]

        if not rest.strip():
            stack.append((indent, key))


def _replace_existing_yaml_leaf(path: Path, parts: list[str], value: str) -> None:
    """Replace a single existing leaf line without rebuilding the whole YAML file."""
    lines = path.read_text(encoding=UTF_8_ENCODING).splitlines(keepends=True)

    for index, match, indent, key, _rest, current_parts in _iter_yaml_key_matches(lines):
        if current_parts == parts:
            line = lines[index]
            newline = "\r\n" if line.endswith("\r\n") else "\n"
            replacement = match.group("indent") + key + ": " + _yaml_quoted_scalar(value) + newline
            lines[index : _yaml_leaf_end(lines, index, indent)] = [replacement]
            path.write_text("".join(lines), encoding=UTF_8_ENCODING)
            return

    raise LocaleError(f"Locale key not found in YAML text: {'.'.join(parts)!r}")


def _append_yaml_leaf(path: Path, parts: list[str], value: str) -> None:
    """Append a missing leaf below an existing mapping parent."""
    if len(parts) < 2:
        raise LocaleError(f"Cannot append top-level locale leaf: {'.'.join(parts)!r}")

    parent_parts = parts[:-1]
    leaf = parts[-1]
    lines = path.read_text(encoding=UTF_8_ENCODING).splitlines(keepends=True)

    for index, _match, indent, _key, rest, current_parts in _iter_yaml_key_matches(lines):
        if current_parts == parent_parts:
            if rest.strip():
                raise LocaleError(f"Cannot append {'.'.join(parts)!r}: parent resolves to a leaf")
            insertion_index = _yaml_leaf_end(lines, index, indent)
            newline = _preferred_newline(lines, index)
            lines.insert(
                insertion_index,
                " " * (indent + 2) + leaf + ": " + _yaml_quoted_scalar(value) + newline,
            )
            path.write_text("".join(lines), encoding=UTF_8_ENCODING)
            return

    raise LocaleError(f"Locale parent key not found in YAML text: {'.'.join(parent_parts)!r}")


def _remove_existing_yaml_leaf(path: Path, parts: list[str]) -> None:
    """Remove a single existing leaf line without rebuilding the whole YAML file."""
    lines = path.read_text(encoding=UTF_8_ENCODING).splitlines(keepends=True)

    for index, _match, indent, _key, rest, current_parts in _iter_yaml_key_matches(lines):
        if current_parts == parts:
            if not rest.strip():
                raise LocaleError(f"Cannot remove {'.'.join(parts)!r}: it resolves to a namespace")
            del lines[index : _yaml_leaf_end(lines, index, indent)]
            path.write_text("".join(lines), encoding=UTF_8_ENCODING)
            return

    raise LocaleError(f"Locale key not found in YAML text: {'.'.join(parts)!r}")


def _preferred_newline(lines: list[str], fallback_index: int) -> str:
    """Return the newline style used near ``fallback_index``."""
    if lines:
        sample = lines[min(fallback_index, len(lines) - 1)]
        if sample.endswith("\r\n"):
            return "\r\n"
    return "\n"


def _flatten_leaf_values(mapping: dict[str, LocaleNode], prefix: str = "") -> dict[str, str]:
    """Return leaf locale values keyed by dotted path."""
    flattened: dict[str, str] = {}
    for key, value in mapping.items():
        path = f"{prefix}.{key}" if prefix else str(key)
        if isinstance(value, dict):
            flattened.update(_flatten_leaf_values(value, path))
        else:
            flattened[path] = value
    return flattened


def _covered_by_namespace(key: str, namespace_prefixes: tuple[str, ...]) -> bool:
    """Return whether a dotted locale key belongs to a dynamic namespace."""
    return any(f".{prefix}." in f".{key}." for prefix in namespace_prefixes)

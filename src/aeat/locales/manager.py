import re
from pathlib import Path

import yaml

from aeat.core.errors import AeatError
from aeat.core.logging import get_logger

# YAML locale values are either leaf strings or nested dicts of the same shape.
type LocaleNode = str | dict[str, "LocaleNode"]

_log = get_logger(__name__)


class LocaleError(AeatError):
    """Raised on locale management and parsing errors."""


class StrictUniqueKeyLoader(yaml.SafeLoader):
    """YAML loader that raises an error on duplicate keys."""

    def construct_mapping(self, node, deep=False):
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
        self.src_dir = src_dir
        self.locales_dir = locales_dir
        self.pattern = re.compile(r'\b(?:tr|t)\(\s*["\'](\w+(?:\.\w+)+)["\']', re.UNICODE)

    def get_codebase_keys(self) -> set[str]:
        """Extract all concrete dotted translation keys from the codebase.

        Combines the regex scanner (``tr("…")`` / ``t("…")`` literal
        call sites) with the AST scanner's concrete-key extractor that
        catches programmatic emissions like
        ``WizardValidationError("wizard.errors.select_unknown")``.

        Dynamic namespaces (f-string and concatenation forms) are
        returned by :meth:`get_codebase_namespaces` and checked
        through a separate parity assertion that verifies at least one
        concrete locale key exists under each declared prefix.
        """

        from aeat.locales._ast_scanner import scan_source_tree

        keys: set[str] = set()
        for py_file in self.src_dir.rglob("*.py"):
            if py_file.name == "test_parity.py" or py_file.name == "manager.py":
                continue
            try:
                content = py_file.read_text(encoding="utf-8", errors="ignore")
            except OSError as exc:
                _log.debug("locale key scan: skipping %s (%s)", py_file, exc)
                continue
            for match in self.pattern.finditer(content):
                keys.add(match.group(1))
        keys.update(scan_source_tree(self.src_dir))
        return keys

    def get_codebase_namespaces(self) -> set[str]:
        """Extract dynamic-namespace markers (``<prefix>.*``) from the codebase.

        Returns every prefix discovered through f-string or string
        concatenation patterns whose tail is computed at runtime.
        Each marker passes the parity check when at least one
        concrete locale key starts with its prefix.
        """

        from aeat.locales._ast_scanner import scan_namespace_markers

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

    def get_parity_keys(self) -> set[str]:
        """Return the locale-key set required for inter-locale parity."""

        keys = self.get_codebase_keys()
        namespace_prefixes = tuple(
            marker.rstrip("*").rstrip(".")
            for marker in self.get_codebase_namespaces()
            if marker.rstrip("*").rstrip(".")
        )
        for locale_path in self.locales_dir.glob("*.yml"):
            data = self.load_locale(locale_path)
            keys.update(key for key in self.get_yaml_keys(data) if _covered_by_namespace(key, namespace_prefixes))
        return keys

    def load_locale(self, path: Path) -> dict[str, LocaleNode]:
        """Load a locale YAML file strictly, failing on duplicates."""
        with open(path, encoding="utf-8") as f:
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

    def scaffold(self, *, sync_locale_parity: bool = False) -> None:
        """Parse codebase, generate locale files, auto-sort, and prune extra keys."""
        codebase_keys = self.get_parity_keys() if sync_locale_parity else self.get_codebase_keys()
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

            with open(f, "w", encoding="utf-8") as f_obj:
                yaml.dump(new_data, f_obj, allow_unicode=True, sort_keys=True, default_flow_style=False)


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

import re
from pathlib import Path
from typing import Any

import yaml

from aeat.core.logging import get_logger

_log = get_logger(__name__)


class StrictUniqueKeyLoader(yaml.SafeLoader):
    """YAML loader that raises an error on duplicate keys."""

    def construct_mapping(self, node, deep=False):
        mapping = {}
        for key_node, value_node in node.value:
            key = self.construct_object(key_node, deep=deep)
            if key in mapping:
                raise ValueError(f"Duplicate key '{key}' found at line {key_node.start_mark.line + 1}")
            value = self.construct_object(value_node, deep=deep)
            mapping[key] = value
        return mapping


class LocaleManager:
    """API for managing locale files, scaffolding, and structural health."""

    def __init__(self, src_dir: Path, locales_dir: Path):
        self.src_dir = src_dir
        self.locales_dir = locales_dir
        self.pattern = re.compile(r'\b(?:tr|t)\(\s*["\']([a-zA-Z0-9_]+(?:\.[a-zA-Z0-9_]+)+)["\']')

    def get_codebase_keys(self) -> set[str]:
        """Extract all dot-notated translation keys from the codebase."""
        keys = set()
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
        return keys

    def get_yaml_keys(self, d: dict[str, Any], current_path: str = "") -> set[str]:
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

    def load_locale(self, path: Path) -> dict[str, Any]:
        """Load a locale YAML file strictly, failing on duplicates."""
        with open(path, encoding="utf-8") as f:
            data = yaml.load(f, Loader=StrictUniqueKeyLoader)  # noqa: S506
            return data if data is not None else {}

    def _build_nested_dict(self, keys: set[str], existing_data: dict[str, Any]) -> dict[str, Any]:
        """Build a sorted, nested dictionary strictly conforming to the required keys."""
        # 1. Gather all values from existing data to preserve translations
        existing_flat = {}
        for key in keys:
            parts = key.split(".")
            curr = existing_data
            missing = False
            for p in parts:
                if not isinstance(curr, dict) or p not in curr:
                    missing = True
                    break
                curr = curr[p]

            if not missing and not isinstance(curr, dict):
                existing_flat[key] = curr
            else:
                existing_flat[key] = key  # Default to its own dot-notated path

        # 2. Rebuild the nested structure from scratch to prune extras and ensure type safety
        new_data: dict[str, Any] = {}
        for key in sorted(keys):
            parts = key.split(".")
            curr = new_data
            for part in parts[:-1]:
                if part not in curr:
                    curr[part] = {}
                curr = curr[part]
            curr[parts[-1]] = existing_flat[key]

        return new_data

    def scaffold(self) -> None:
        """Parse codebase, generate locale files, auto-sort, and prune extra keys."""
        codebase_keys = self.get_codebase_keys()

        for f in self.locales_dir.glob("*.yml"):
            try:
                data = self.load_locale(f)
            except Exception:
                data = {}

            new_data = self._build_nested_dict(codebase_keys, data)

            with open(f, "w", encoding="utf-8") as f_obj:
                yaml.dump(new_data, f_obj, allow_unicode=True, sort_keys=True, default_flow_style=False)

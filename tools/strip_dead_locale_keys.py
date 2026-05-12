"""Remove ``setup.wizard``, ``cli.setup``, and ``cli.init`` keys from locale files.

Run as ``uv run --no-sync python tools/strip_dead_locale_keys.py``.
Loads each ``src/aeat/locales/{lang}.yml`` file, deletes the dead
top-level keys, and rewrites the file.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


def _drop_dead_keys(tree: dict[str, Any]) -> None:
    setup_block = tree.get("setup")
    if isinstance(setup_block, dict):
        setup_block.pop("wizard", None)
        # ``setup.verifier`` is also dead — the new wizard verifier
        # publishes keys under wizard.setup.verifier.*.
        setup_block.pop("verifier", None)
        if not setup_block:
            tree.pop("setup", None)
    cli_block = tree.get("cli")
    if isinstance(cli_block, dict):
        cli_block.pop("init", None)
        cli_block.pop("setup", None)


def main() -> None:
    root = Path("src/aeat/locales")
    for lang in ("en", "es", "ca", "hu"):
        path = root / f"{lang}.yml"
        with path.open(encoding="utf-8") as fh:
            data = yaml.safe_load(fh) or {}
        _drop_dead_keys(data)
        with path.open("w", encoding="utf-8") as fh:
            yaml.safe_dump(data, fh, allow_unicode=True, sort_keys=True, default_flow_style=False)


if __name__ == "__main__":
    main()

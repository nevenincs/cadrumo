"""Exercise the installed indexer's current corpus admission contract."""

from __future__ import annotations

import json
import tomllib
from pathlib import Path

from vaultspec_rag.api import scan_codebase

from dev._paths import REPO_ROOT


def assert_source_is_indexable(source: Path, text_path: Path, root: Path) -> None:
    """Admit the real source through its enrolled hook, without indexing its duplicate sidecar."""
    declarations = tomllib.loads((REPO_ROOT / ".vaultragpreprocess.toml").read_text(encoding="utf-8"))
    rules = [rule for rule in declarations["rule"] if rule["pattern"].endswith("*" + source.suffix)]
    assert len(rules) == 1
    rule = rules[0]
    assert source not in scan_codebase(root).files
    settings = {**rule, "pattern": source.relative_to(root).as_posix()}
    configuration = "version = 2\n\n[[rule]]\n" + "\n".join(
        f"{key} = {json.dumps(value)}" for key, value in settings.items()
    )
    (root / ".vaultragpreprocess.toml").write_text(configuration + "\n", encoding="utf-8")
    admitted = scan_codebase(root).files
    assert source in admitted
    assert text_path not in admitted
    text = text_path.read_text(encoding="utf-8")
    assert text != "" and "\x00" not in text

from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

PROJECT_ROOT = Path(__file__).resolve().parents[4]
RUNTIME_SURFACES = (
    PROJECT_ROOT / "src" / "aeat",
    PROJECT_ROOT / "env",
)
TEXT_SUFFIXES = {".py", ".yml", ".yaml", ".example"}

_AEAT = "ae" + "at"
_CONFIG = "con" + "fig"
_PROFILE = "pro" + "file"
_AUTH = "au" + "th"

RETIRED_COMMAND_PHRASES = tuple(
    " ".join(parts)
    for parts in (
        (_AEAT, _CONFIG, "init"),
        (_CONFIG, "init"),
        (_AEAT, _CONFIG, _PROFILE, "view"),
        (_CONFIG, _PROFILE, "view"),
        (_AEAT, _CONFIG, _PROFILE, "set"),
        (_CONFIG, _PROFILE, "set"),
        (_AEAT, _CONFIG, _PROFILE, "get"),
        (_CONFIG, _PROFILE, "get"),
        (_AEAT, _CONFIG, _PROFILE, "remove"),
        (_CONFIG, _PROFILE, "remove"),
        (_AEAT, _CONFIG, _PROFILE, "use"),
        (_CONFIG, _PROFILE, "use"),
        (_AEAT, _PROFILE, "set"),
        (_AEAT, _CONFIG, "doctor"),
        (_CONFIG, "doctor"),
        (_CONFIG, "doctor" + "-logs"),
        (_CONFIG, "repair" + "-logs"),
        (_AEAT, _CONFIG, _AUTH, "--provider"),
        (_CONFIG, _AUTH, "--provider"),
        (_AEAT, _CONFIG, _AUTH, "setup"),
        (_CONFIG, _AUTH, "setup"),
    )
)


def _runtime_text_files() -> list[Path]:
    files: list[Path] = []
    for root in RUNTIME_SURFACES:
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if path.suffix not in TEXT_SUFFIXES:
                continue
            if "__pycache__" in path.parts:
                continue
            if path.name.startswith("test_") or path.name == "conftest.py":
                continue
            files.append(path)
    return sorted(files)


def test_retired_cli_command_phrases_do_not_leak_into_runtime_surfaces() -> None:
    leaks: list[str] = []

    for path in _runtime_text_files():
        text = path.read_text(encoding="utf-8")
        for phrase in RETIRED_COMMAND_PHRASES:
            if phrase in text:
                leaks.append(f"{path.relative_to(PROJECT_ROOT)}: {phrase}")

    assert leaks == []

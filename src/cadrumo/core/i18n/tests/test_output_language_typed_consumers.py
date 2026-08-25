"""Regression-test ratchet: every public-surface field referencing the language axis must consume OutputLanguage.

The output-language typing contract requires every field on public surfaces
(settings, CLI arguments, data-class fields)
referencing the output language axis must either consume `OutputLanguage` directly
or carry an explicit exemption comment. Internal helpers (cache keys,
normalisation functions) are exempt by name.

This gate prevents future drift: any new bare-str language field gets caught
as a test failure before it can merge.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from ...directory_scan import scan_directory

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def _read_file(path: Path) -> str:
    """Read a Python source file."""
    return path.read_text(encoding="utf-8")


def _has_output_language_import(src: str) -> bool:
    """Check if the file imports OutputLanguage."""
    return re.search(r"from\s+\.external_constants\s+import.*OutputLanguage|OutputLanguage", src) is not None


def _find_language_axis_fields(src: str) -> list[tuple[int, str]]:
    """Find lines with output_language / output language field references.

    Returns list of (line_number, line_text) tuples.
    """
    lines = src.split("\n")
    results = []
    for i, line in enumerate(lines, start=1):
        if re.search(r"output_language|output[_-]language", line, re.IGNORECASE) and not re.search(
            r"#.*exempt|#.*cache.*key|#.*internal",
            line,
        ):
            results.append((i, line))
    return results


def test_settings_layer_output_language_typed_or_exempt() -> None:
    """Settings field at src/cadrumo/core/config.py must consume OutputLanguage."""
    config_file = Path(__file__).resolve().parents[2] / "config.py"
    src = _read_file(config_file)

    assert _has_output_language_import(src), f"{config_file} must import OutputLanguage from external_constants"
    assert "cadrumo_output_language: Annotated[OutputLanguage | None" in src or "OutputLanguage | None" in src, (
        f"{config_file} cadrumo_output_language field must be typed as OutputLanguage | None"
    )


def test_cli_sites_output_language_typed_or_exempt() -> None:
    """CLI Typer flag arguments must type output_language as OutputLanguage."""
    cli_dir = Path(__file__).resolve().parents[3] / "entrypoints" / "cli"
    assert cli_dir.exists(), f"{cli_dir} must exist"

    for py_file in scan_directory(cli_dir, pattern="*.py"):
        if py_file.name.startswith("test_"):
            continue
        src = _read_file(py_file)
        fields = _find_language_axis_fields(src)

        for line_num, line in fields:
            if "str" in line and "--output-language" in line.lower():
                assert "OutputLanguage" in src, (
                    f"{py_file}:{line_num} must import OutputLanguage for --output-language flag"
                )


def test_no_new_bare_str_language_fields() -> None:
    """Regression gate: forbid new bare-str language fields on public surfaces.

    Sweep src/cadrumo/ (excluding tests and internal helpers) for new output_language
    references in bare str form. The gate is a grep-based check that surfaces drift
    at test time.
    """
    src_root = Path(__file__).resolve().parents[3]
    violations = []

    for py_file in scan_directory(src_root, pattern="*.py", recursive=True, prune_directories={"__pycache__"}):
        if "test_" in py_file.name:
            continue
        try:
            src = _read_file(py_file)
        except (OSError, UnicodeDecodeError):
            continue

        fields = _find_language_axis_fields(src)
        for line_num, line in fields:
            if re.search(r":\s*str\s*=|:\s*str\s*\|", line) and "output_language" in line.lower():
                violations.append((py_file.relative_to(src_root), line_num, line.strip()))

    assert not violations, (
        f"Found {len(violations)} bare-str output-language fields. "
        f"All must be typed as OutputLanguage or exempted:\n"
        + "\n".join(f"{file_path}:{line_number}: {line}" for file_path, line_number, line in violations[:10])
    )

"""Hard-cut guards for runtime legal authority surfaces."""

from __future__ import annotations

import re
from collections.abc import Iterable
from pathlib import Path

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.domain_core]

PROJECT_ROOT = Path(__file__).resolve().parents[2]

DELETED_AUTHORITY_PATHS: tuple[Path, ...] = (
    PROJECT_ROOT / "corpus" / "casillas",
    PROJECT_ROOT / "src" / "aeat" / "domain" / "casillas",
    PROJECT_ROOT / "src" / "aeat" / "entrypoints" / "cli" / "casillas.py",
    PROJECT_ROOT / "src" / "aeat" / "entrypoints" / "cli" / "_test_casillas.py",
    PROJECT_ROOT / "src" / "aeat" / "domain" / "schema",
    PROJECT_ROOT / "src" / "aeat" / "adapters" / "inbound" / "schema",
    PROJECT_ROOT / "src" / "aeat" / "adapters" / "outbound" / "aeat" / "export" / "_formats" / "_generate.py",
    PROJECT_ROOT / "src" / "aeat" / "adapters" / "outbound" / "aeat" / "export" / "_formats" / "_ingest.py",
    PROJECT_ROOT / "tests" / "fixtures" / "dr_specs",
    PROJECT_ROOT / "docs" / "api" / "aeat.domain.casillas.rst",
    PROJECT_ROOT / "docs" / "api" / "aeat.entrypoints.cli.casillas.rst",
)

AUTHORITY_SCAN_ROOTS: tuple[Path, ...] = (
    PROJECT_ROOT / "registry" / "aeat",
    PROJECT_ROOT / "src" / "aeat" / "domain" / "calculations",
    PROJECT_ROOT / "src" / "aeat" / "application" / "verification",
    PROJECT_ROOT / "src" / "aeat" / "adapters" / "outbound" / "aeat" / "export" / "_formats",
    PROJECT_ROOT / "src" / "aeat" / "entrypoints" / "cli" / "registry.py",
    PROJECT_ROOT / "env" / ".env.example",
    PROJECT_ROOT / "pyproject.toml",
)

BANNED_AUTHORITY_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("casilla package import", re.compile(r"aeat\.domain\.casillas")),
    ("casilla corpus path", re.compile(r"corpus[\\/]+casillas")),
    ("casilla env setting", re.compile(r"\bAEAT_CASILLAS\b|\baeat_casillas\b")),
    ("casilla corpus writer", re.compile(r"\bsave_casillas\b")),
    ("schema extraction cache setting", re.compile(r"\bAEAT_SCHEMA\b|\baeat_schema\b")),
    ("schema extraction cache path", re.compile(r"schema-cache")),
    ("hydrate authority", re.compile(r"\b(?:hydrate|hydration|_hydrate)\b", re.IGNORECASE)),
    (
        "generated authority provenance",
        re.compile(r"\b(?:auto-?generated|generated provenance|generated legal)\b", re.IGNORECASE),
    ),
    ("dr fixture promotion path", re.compile(r"\b(?:dr_specs|ingest_dr_spec)\b", re.IGNORECASE)),
    ("schema promotion wording", re.compile(r"\b(?:schema regeneration|schema-generation)\b", re.IGNORECASE)),
    ("phase metadata", re.compile(r"\bphase\s+\d+\b", re.IGNORECASE)),
    ("wave metadata", re.compile(r"\bwave\s+\d+\b", re.IGNORECASE)),
    ("issue metadata", re.compile(r"\b(?:issue|ticket|epic)\s*#?\d+\b|(?<!PKCS)#\d+\b", re.IGNORECASE)),
    ("review-process metadata", re.compile(r"\b(?:ADR|PR|pull request|development flow|dev metadata)\b")),
)


def _authority_files() -> Iterable[Path]:
    for root in AUTHORITY_SCAN_ROOTS:
        if root.is_file():
            yield root
            continue

        for candidate in root.rglob("*"):
            if not candidate.is_file():
                continue
            if candidate.suffix not in {".py", ".toml"}:
                continue
            if candidate.name.startswith("test_") or candidate.name.startswith("_test_"):
                continue
            yield candidate


@pytest.mark.parametrize("path", DELETED_AUTHORITY_PATHS, ids=lambda path: path.as_posix())
def test_deleted_casilla_authority_paths_do_not_exist(path: Path) -> None:
    assert not path.exists(), f"{path.relative_to(PROJECT_ROOT)} must not be restored"


def test_runtime_authority_surfaces_do_not_encode_process_or_legacy_metadata() -> None:
    failures: list[str] = []

    for path in _authority_files():
        content = path.read_text(encoding="utf-8")
        relative = path.relative_to(PROJECT_ROOT).as_posix()
        for label, pattern in BANNED_AUTHORITY_PATTERNS:
            for match in pattern.finditer(content):
                line_no = content.count("\n", 0, match.start()) + 1
                failures.append(f"{relative}:{line_no}: {label}: {match.group(0)!r}")

    assert not failures, "\n".join(failures)

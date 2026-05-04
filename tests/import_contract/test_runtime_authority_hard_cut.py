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
    PROJECT_ROOT / "src" / "aeat" / "adapters" / "inbound" / "borrador" / "_tarifa.py",
    PROJECT_ROOT / "src" / "aeat" / "domain" / "sync",
    PROJECT_ROOT / "src" / "aeat" / "application" / "sync",
    PROJECT_ROOT / "tests" / "fixtures" / "dr_specs",
    PROJECT_ROOT / "docs" / "api" / "aeat.domain.casillas.rst",
    PROJECT_ROOT / "docs" / "api" / "aeat.entrypoints.cli.casillas.rst",
)

AUTHORITY_SCAN_ROOTS: tuple[Path, ...] = (
    PROJECT_ROOT / "registry" / "aeat",
    PROJECT_ROOT / "src" / "aeat" / "domain" / "calculations",
    PROJECT_ROOT / "src" / "aeat" / "application" / "verification",
    PROJECT_ROOT / "src" / "aeat" / "application" / "filing",
    PROJECT_ROOT / "src" / "aeat" / "application" / "review",
    PROJECT_ROOT / "src" / "aeat" / "application" / "workflow",
    PROJECT_ROOT / "src" / "aeat" / "adapters" / "inbound" / "borrador",
    PROJECT_ROOT / "src" / "aeat" / "core" / "errors",
    PROJECT_ROOT / "src" / "aeat" / "core" / "config.py",
    PROJECT_ROOT / "src" / "aeat" / "adapters" / "outbound" / "aeat" / "export" / "_formats",
    PROJECT_ROOT / "src" / "aeat" / "entrypoints" / "cli" / "registry.py",
    PROJECT_ROOT / "env" / ".env.example",
    PROJECT_ROOT / "pyproject.toml",
)

TEST_SCHEMA_SCAN_ROOTS: tuple[Path, ...] = (
    PROJECT_ROOT / "src" / "aeat" / "domain" / "calculations" / "registry",
    PROJECT_ROOT / "src" / "aeat" / "entrypoints" / "cli",
    PROJECT_ROOT / "tests",
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
    (
        "obsolete ruleset error surface",
        re.compile(r"\b(?:FormulasError|RulesetValidationError|MissingRulesetError|ruleset)\b", re.IGNORECASE),
    ),
    ("sync authority import", re.compile(r"aeat\.(?:domain|application)\.sync")),
    ("sync authority setting", re.compile(r"\bAEAT_SYNC|\baeat_sync\b")),
    ("sync workflow stage", re.compile(r"\bSYNCING_CATALOGUES\b|\bsync_first\b")),
    (
        "wire modelo authority",
        re.compile(r"\b(?:WireModeloDefinition|WireCasilla|WireFilingEntry|WireFilingHistory)\b"),
    ),
    (
        "divergence authority",
        re.compile(r"\b(?:DivergenceKind|DivergenceRecord|FORMULA_CHANGED|CASILLA_ADDED|CASILLA_REMOVED)\b"),
    ),
    (
        "healing authority",
        re.compile(r"\b(?:self-healing|auto-?heal|auto_heal|HealingDispatcher)\b", re.IGNORECASE),
    ),
    (
        "hardcoded tarifa authority",
        re.compile(r"\b(?:_TARIFA_ESTATAL|SUPPORTED_EJERCICIOS|validate_tarifa_estatal|apply_tarifa)\b"),
    ),
    ("phase metadata", re.compile(r"\bphase\s+\d+\b", re.IGNORECASE)),
    ("wave metadata", re.compile(r"\bwave\s+\d+\b", re.IGNORECASE)),
    ("issue metadata", re.compile(r"\b(?:issue|ticket|epic)\s*#?\d+\b|(?<!PKCS)#\d+\b", re.IGNORECASE)),
    ("review-process metadata", re.compile(r"\b(?:ADR|PR|pull request|development flow|dev metadata)\b")),
)

BANNED_TEST_SCHEMA_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("test-owned modelo object", re.compile(r"\bModeloDefinition\s*\(")),
    ("test-owned modelo revision object", re.compile(r"\bModeloRevision\s*\(")),
    ("test-owned casilla object", re.compile(r"\bCasillaDefinition\s*\(")),
    ("test-owned legal reference object", re.compile(r"\bLegalReference\s*\(")),
    ("test-owned source reference object", re.compile(r"\bSourceReference\s*\(")),
    ("test-owned registry catalogue object", re.compile(r"\bRegistryCatalogues\s*\(")),
    ("test-owned wire modelo object", re.compile(r"\bWireModeloDefinition\s*\(")),
    ("test-owned wire casilla object", re.compile(r"\bWireCasilla\s*\(")),
    ("test-owned modelo TOML", re.compile(r"^\s*\[modelo\]\s*$", re.MULTILINE)),
    ("test-owned casilla TOML", re.compile(r"^\s*\[\[revisions\.[^\]]+\.casillas\]\]\s*$", re.MULTILINE)),
    ("test-owned legal TOML", re.compile(r"^\s*\[legal\.", re.MULTILINE)),
    ("test-owned source TOML", re.compile(r"^\s*\[sources\.", re.MULTILINE)),
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


def _test_schema_files() -> Iterable[Path]:
    this_file = Path(__file__).resolve()
    for root in TEST_SCHEMA_SCAN_ROOTS:
        for candidate in root.rglob("*test*.py"):
            if candidate.resolve() == this_file:
                continue
            if candidate.is_file():
                yield candidate


@pytest.mark.parametrize("path", DELETED_AUTHORITY_PATHS, ids=lambda path: path.as_posix())
def test_deleted_casilla_authority_paths_do_not_exist(path: Path) -> None:
    assert not path.exists(), f"{path.relative_to(PROJECT_ROOT)} must not be restored"


def test_runtime_authority_surfaces_do_not_encode_process_or_obsolete_metadata() -> None:
    failures: list[str] = []

    for path in _authority_files():
        content = path.read_text(encoding="utf-8")
        relative = path.relative_to(PROJECT_ROOT).as_posix()
        for label, pattern in BANNED_AUTHORITY_PATTERNS:
            for match in pattern.finditer(content):
                line_no = content.count("\n", 0, match.start()) + 1
                failures.append(f"{relative}:{line_no}: {label}: {match.group(0)!r}")

    assert not failures, "\n".join(failures)


def test_tests_do_not_define_modelo_or_casilla_schema_authority() -> None:
    failures: list[str] = []

    for path in _test_schema_files():
        content = path.read_text(encoding="utf-8")
        relative = path.relative_to(PROJECT_ROOT).as_posix()
        for label, pattern in BANNED_TEST_SCHEMA_PATTERNS:
            for match in pattern.finditer(content):
                line_no = content.count("\n", 0, match.start()) + 1
                failures.append(f"{relative}:{line_no}: {label}: {match.group(0)!r}")

    assert not failures, "\n".join(failures)

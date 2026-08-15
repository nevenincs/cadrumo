"""Spanish IVA is the sole application-owned stem for this tax concept."""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

from ..core import scan_directory

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_PACKAGE_ROOT = Path(__file__).resolve().parents[1]
_REPOSITORY_ROOT = _PACKAGE_ROOT.parents[1]
_RETIRED_STEM = re.compile(r"(^|[._:/-])vat([._:/-]|$)", re.IGNORECASE)
_DUPLICATED_IVA = re.compile(r"(?<![A-Za-z0-9])iva(?:[._:/-]+|\s+(?:\(\s*)?)iva\b", re.IGNORECASE)
_ENGLISH_VAT = re.compile(r"\bvat\b", re.IGNORECASE)
_MIXED_IVA_ALIAS = re.compile(
    r"(?<![A-Za-z0-9])(?:vat[._:/-]+iva|iva[._:/-]+vat)(?=$|[._:/-])",
    re.IGNORECASE,
)
_EXTERNAL_IVA_LOCATOR = re.compile(
    r"(?:https?://\S+|/Sede/\S+|(?:sede\.)?agenciatributaria\.gob\.es/\S+|IVA/IVA_\d{4}/\S+)",
    re.IGNORECASE,
)
_IDENTITY_TOKEN = re.compile(r"^[A-Za-z0-9_.:/-]+$")
_EXTERNAL_IDENTITY_TOKENS = {
    "adapters/inbound/einvoice/_parsers.py": frozenset({"vat", "vatid"}),
    "entrypoints/cli/_config/tests/test_apoderado_scopes_payload.py": frozenset({"VAT"}),
}
_EXTERNAL_VAT_PROSE_VALUES = {
    "adapters/inbound/einvoice/_parsers.py": frozenset({"vat"}),
    "domain/calculations/registry/tests/test_registry_locales_parity.py": frozenset(
        {
            "Output VAT amount at the standard rate (21%)",
            "Total output VAT calculated at the standard 21% rate.",
        },
    ),
    "domain/iva/tests/test_rate_grounding.py": frozenset(
        {
            "(^|[._:/-])vat([._:/-]|$)",
            "from 1 july 2025, the standard rate of vat in estonia is 24% instead of 22%",
            "reduced vat rate 13,5%",
        },
    ),
    "domain/iva/tests/test_saturation.py": frozenset({"verify the customer VAT ID"}),
    "entrypoints/cli/_config/tests/test_apoderado_scopes_payload.py": frozenset({"VAT"}),
    "tests/fixtures/justificantes/_generate_modelo_390_english.py": frozenset(
        {
            "Deductible VAT",
            "Deductible VAT from internal transactions of current goods and services",
        },
    ),
}
_EXTERNAL_VAT_PROSE_FRAGMENTS = {
    "adapters/inbound/einvoice/_parsers.py": frozenset({"``VAT``"}),
    "application/command_search/tests/test_command_ranking_golden.py": frozenset({"file my quarterly VAT"}),
    "entrypoints/cli/tests/test_ledger_evidence_confirm_resolution_cli.py": frozenset(
        {"<cbc:ID>VAT</cbc:ID>"},
    ),
}
_EXTERNAL_SOURCE_PREFIXES = ("http://", "https://", "/Sede/")


def _source_files() -> tuple[Path, ...]:
    return tuple(
        sorted(path for path in scan_directory(_PACKAGE_ROOT, pattern="*.py", recursive=True) if path != Path(__file__))
    )


def _package_files() -> tuple[Path, ...]:
    return tuple(
        sorted(
            path
            for path in scan_directory(_PACKAGE_ROOT, pattern="*", recursive=True)
            if path.is_file() and "__pycache__" not in path.parts
        )
    )


def _declared_names(tree: ast.AST) -> tuple[tuple[int, str], ...]:
    names: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            names.append((node.lineno, node.id))
        elif isinstance(node, ast.Attribute):
            names.append((node.lineno, node.attr))
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.append((node.lineno, node.name))
        elif isinstance(node, ast.alias):
            names.append((node.lineno, node.name))
            if node.asname is not None:
                names.append((node.lineno, node.asname))
    return tuple(names)


def test_python_paths_and_identifiers_use_the_canonical_iva_stem() -> None:
    violations: list[str] = []
    for path in _source_files():
        relative = path.relative_to(_PACKAGE_ROOT).as_posix()
        if _RETIRED_STEM.search(relative):
            violations.append(relative)
        if _DUPLICATED_IVA.search(relative):
            violations.append(relative)
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        if relative.startswith("domain/iva/") and "/tests/" not in relative:
            violations.extend(
                f"{relative}:{node.lineno}:{node.name}"
                for node in ast.walk(tree)
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                and node.name.lstrip("_").startswith("iva_")
            )
        violations.extend(
            f"{relative}:{line}:{name}" for line, name in _declared_names(tree) if _RETIRED_STEM.search(name)
        )
    assert violations == []


def test_non_python_package_paths_use_the_canonical_iva_stem() -> None:
    violations = [
        relative
        for path in _package_files()
        if path.suffix != ".py"
        and (
            _RETIRED_STEM.search(relative := path.relative_to(_PACKAGE_ROOT).as_posix())
            or _DUPLICATED_IVA.search(relative)
        )
    ]
    assert violations == []


def test_internal_identity_tokens_use_the_canonical_iva_stem() -> None:
    violations: list[str] = []
    for path in _source_files():
        relative = path.relative_to(_PACKAGE_ROOT).as_posix()
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        violations.extend(
            f"{relative}:{node.lineno}:{node.value}"
            for node in ast.walk(tree)
            if isinstance(node, ast.Constant)
            and isinstance(node.value, str)
            and _IDENTITY_TOKEN.fullmatch(node.value)
            and (_RETIRED_STEM.search(node.value) or _DUPLICATED_IVA.search(node.value))
            and not node.value.startswith(_EXTERNAL_SOURCE_PREFIXES)
            and node.value not in _EXTERNAL_IDENTITY_TOKENS.get(relative, ())
        )
    assert violations == []


def test_internal_prose_does_not_duplicate_or_alias_the_iva_stem() -> None:
    violations: list[str] = []
    used_external_values: set[tuple[str, str]] = set()
    used_external_fragments: set[tuple[str, str]] = set()
    for path in _source_files():
        relative = path.relative_to(_PACKAGE_ROOT).as_posix()
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        violations.extend(
            f"{relative}:{node.lineno}:{node.value}"
            for node in ast.walk(tree)
            if isinstance(node, ast.Constant)
            and isinstance(node.value, str)
            and (_DUPLICATED_IVA.search(node.value) or _MIXED_IVA_ALIAS.search(node.value))
            and not node.value.startswith(_EXTERNAL_SOURCE_PREFIXES)
        )
        for node in ast.walk(tree):
            if (
                not isinstance(node, ast.Constant)
                or not isinstance(node.value, str)
                or not _ENGLISH_VAT.search(node.value)
            ):
                continue
            value = node.value
            if value in _EXTERNAL_VAT_PROSE_VALUES.get(relative, ()):
                used_external_values.add((relative, value))
                continue
            for fragment in _EXTERNAL_VAT_PROSE_FRAGMENTS.get(relative, ()):
                if fragment in value:
                    value = value.replace(fragment, "")
                    used_external_fragments.add((relative, fragment))
            if _ENGLISH_VAT.search(value):
                violations.append(f"{relative}:{node.lineno}:{node.value}")
    assert violations == []
    assert used_external_values == {
        (relative, value) for relative, values in _EXTERNAL_VAT_PROSE_VALUES.items() for value in values
    }
    assert used_external_fragments == {
        (relative, fragment) for relative, fragments in _EXTERNAL_VAT_PROSE_FRAGMENTS.items() for fragment in fragments
    }


def test_authored_repository_prose_uses_iva_without_a_mixed_alias() -> None:
    violations: list[str] = []
    for root_name in (
        ".vault/adr",
        ".vault/audit",
        ".vault/plan",
        ".vault/reference",
        ".vault/research",
        "dev",
        "docs",
        "src/cadrumo",
    ):
        root = _REPOSITORY_ROOT / root_name
        for path in scan_directory(root, pattern="*", recursive=True):
            if (
                not path.is_file()
                or "_data" in path.parts
                or path.suffix
                not in {
                    ".md",
                    ".po",
                    ".rst",
                    ".toml",
                    ".yaml",
                    ".yml",
                }
            ):
                continue
            relative = path.relative_to(_REPOSITORY_ROOT).as_posix()
            for line_number, line in enumerate(
                path.read_text(encoding="utf-8", errors="replace").splitlines(),
                start=1,
            ):
                authored_text = _EXTERNAL_IVA_LOCATOR.sub("", line)
                if _DUPLICATED_IVA.search(authored_text) or _MIXED_IVA_ALIAS.search(authored_text):
                    violations.append(f"{relative}:{line_number}:{line.strip()}")
    assert violations == []

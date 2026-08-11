"""Spanish IVA is the sole application-owned stem for this tax concept."""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_PACKAGE_ROOT = Path(__file__).resolve().parents[1]
_REPOSITORY_ROOT = _PACKAGE_ROOT.parents[1]
_RETIRED_STEM = re.compile(r"(^|[._:/-])vat([._:/-]|$)", re.IGNORECASE)
_DUPLICATED_IVA = re.compile(
    r"(?<![A-Za-z0-9])iva(?:[._:/-]+|\s+\(\s*)iva(?=$|[._:/)-])",
    re.IGNORECASE,
)
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
_EXTERNAL_VAT_PROSE_PATHS = frozenset({"adapters/inbound/einvoice/_parsers.py"})
_EXTERNAL_SOURCE_PREFIXES = ("http://", "https://", "/Sede/")


def _source_files() -> tuple[Path, ...]:
    return tuple(sorted(path for path in _PACKAGE_ROOT.rglob("*.py") if path != Path(__file__)))


def _package_files() -> tuple[Path, ...]:
    return tuple(
        sorted(path for path in _PACKAGE_ROOT.rglob("*") if path.is_file() and "__pycache__" not in path.parts)
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
        if "/tests/" not in relative and not relative.startswith("tests/"):
            violations.extend(
                f"{relative}:{node.lineno}:{node.value}"
                for node in ast.walk(tree)
                if isinstance(node, ast.Constant)
                and isinstance(node.value, str)
                and _ENGLISH_VAT.search(node.value)
                and relative not in _EXTERNAL_VAT_PROSE_PATHS
            )
    assert violations == []


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
        for path in sorted(root.rglob("*")):
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

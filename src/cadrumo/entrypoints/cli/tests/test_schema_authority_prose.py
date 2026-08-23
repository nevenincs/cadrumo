"""Prevent registry-era schema-authority prose from surviving the CommandSpec cutover."""

from __future__ import annotations

import ast
import io
import re
import tokenize
from pathlib import Path

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_CLI_ROOT = Path(__file__).resolve().parents[1]
_STALE = re.compile(
    r"(?:schema\s+decorator|decorat(?:ed|or).{0,80}commandspec|"
    r"registered\s+(?:result\s+|output\s+|payload\s+)?schemas?|"
    r"(?:result-?)?schema\s+registr(?:y|ies)|"
    r"registered\s+result\s+DTO|registered\s+JSON\s+payload|"
    r"schemas?\s+(?:is\s+|are\s+)?registered|registers\s+its\s+own\s+schema|"
    r"(?:schema|result|model|command).{0,80}not\s+registered|"
    r"not\s+registered.{0,80}(?:schema|result|model|command)|"
    r"(?:typer|command)\s+registrations?|"
    r"registrations?\s+(?:with|through|on)\s+typer)",
    re.IGNORECASE | re.DOTALL,
)


def _stale_blocks(source: str) -> tuple[str, ...]:
    """Return stale mechanism claims from prose blocks, never executable identifiers."""
    tree = ast.parse(source)
    blocks = [
        value
        for node in ast.walk(tree)
        if isinstance(node, ast.Module | ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef)
        and (value := ast.get_docstring(node, clean=False)) is not None
    ]
    blocks.extend(
        token.string.removeprefix("#").strip()
        for token in tokenize.generate_tokens(io.StringIO(source).readline)
        if token.type == tokenize.COMMENT
    )
    return tuple(block for block in blocks if _STALE.search(block))


def test_stale_schema_authority_detector_rejects_each_retired_mechanism() -> None:
    """Independent plants prove decorator, registry, and negative-registration wording is caught."""
    plants = (
        '"""OutputSchema decorated with CommandSpec."""',
        '"""The registered result schema is authoritative."""',
        '"""This schema is registered at import time."""',
        "# Shared models (not registered)",
        '"""Each subclass registers its own schema."""',
        '"""Typer registration for this command family."""',
        '"""The central CLI schema registry owns this payload."""',
        '"""The current result-schema registry is authoritative."""',
        '"""Render the registered result DTO."""',
        '"""Convert records into registered JSON payload fragments."""',
    )
    assert all(_stale_blocks(plant) for plant in plants)


@pytest.mark.parametrize(
    "path",
    tuple(path for path in sorted(_CLI_ROOT.rglob("*.py")) if "tests" not in path.relative_to(_CLI_ROOT).parts),
    ids=lambda path: path.relative_to(_CLI_ROOT).as_posix(),
)
def test_payload_prose_names_only_deferred_commandspec_schema_ownership(path: Path) -> None:
    """Payload prose must not claim a decorator or mutable schema registry exists."""
    stale = _stale_blocks(path.read_text(encoding="utf-8"))
    assert stale == (), f"{path.relative_to(_CLI_ROOT)} carries stale schema-authority prose: {stale!r}"

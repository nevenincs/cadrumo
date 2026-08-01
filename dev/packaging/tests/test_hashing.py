"""Independent contracts for streamed packaging artifact hashing."""

from __future__ import annotations

import ast
import hashlib
import importlib
from pathlib import Path
from typing import Final

import pytest

from dev.packaging._hashing import sha256_path

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


#: Smoke entrypoints re-homed onto the canonical helper. Each is invoked as
#: ``python -m dev.packaging.<module>``, so it can import the package helper.
#: ``smoke_homebrew`` is deliberately absent: CI runs it as a bare script path
#: under ``uv run --no-project``, where the repository root is not importable.
_REHOMED_SMOKE_MODULES: Final[tuple[str, ...]] = ("smoke_mcpb", "smoke_plugin_install")


def test_sha256_path_hashes_real_multichunk_bytes(tmp_path: Path) -> None:
    """A file crossing the stream boundary has the standard-library digest."""
    payload = b"cohort-byte-contract\n" * 60_000
    artifact = tmp_path / "cohort-artifact.bin"
    artifact.write_bytes(payload)

    assert sha256_path(artifact) == hashlib.sha256(payload).hexdigest()


@pytest.mark.parametrize("module_name", _REHOMED_SMOKE_MODULES)
def test_rehomed_smoke_module_declares_no_private_digest_helper(module_name: str) -> None:
    """A re-homed smoke entrypoint must not grow its own streamed digest back.

    Each of these modules previously carried a byte-identical private copy of
    ``sha256_path``. Asserting only that the canonical import is present would
    still pass if a second local helper reappeared beside it, so the check is on
    the absence of any function that streams ``hashlib.sha256`` itself.
    """
    source = (Path(__file__).resolve().parents[1] / f"{module_name}.py").read_text(encoding="utf-8")
    tree = ast.parse(source)

    redeclared = [
        node.name
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef)
        and any(
            isinstance(inner, ast.Call)
            and isinstance(inner.func, ast.Attribute)
            and inner.func.attr == "sha256"
            and isinstance(inner.func.value, ast.Name)
            and inner.func.value.id == "hashlib"
            for inner in ast.walk(node)
        )
    ]

    assert redeclared == []


@pytest.mark.parametrize("module_name", _REHOMED_SMOKE_MODULES)
def test_rehomed_smoke_module_uses_the_canonical_helper(module_name: str) -> None:
    """The re-homed module resolves file digests through the one owner."""
    module = importlib.import_module(f"dev.packaging.{module_name}")

    assert module.sha256_path is sha256_path

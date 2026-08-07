"""The gated inference subpackage persists nothing, enforced structurally.

These are the assertions the encryption exemption rests on, and the dependency
runs one way only: the operator ruling exempts IN-MEMORY reading, rasterising
and local inference from encryption **because the code persists nothing**, and
the only thing establishing that it persists nothing is enforcement like this.
Remove these and the exemption becomes self-referential -- a correctly reasoned
permission resting on a property nothing checks.

They complement the import contract rather than duplicating it. The contract
bars an *import* of ``adapters.persistence``; these bar the *behaviours* an
inference path is under standing pressure to reach for, which a module can
perform without importing that package at all: writing a rasterised page to
disk, opening a temp file under a debug branch, constructing a store.

Each is written to fail for the reason it exists, and the mutation that would
trip it is named in its docstring so a later reader can run it rather than
trust this file.
"""

from __future__ import annotations

import ast

import pytest

from . import SRC_CADRUMO, ast_for_path, leaf_name, non_test_python_files_under, repo_relative

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_LLM_PACKAGE = SRC_CADRUMO / "llm"

_FORBIDDEN_WRITE_CALLS = {
    "write_text",
    "write_bytes",
    "mkstemp",
    "mkdtemp",
    "NamedTemporaryFile",
    "TemporaryDirectory",
    "TemporaryFile",
    "SpooledTemporaryFile",
}
_FORBIDDEN_STORE_CALLS = {
    "AttachmentStore",
    "secure_object_repository_for_active_bucket",
    "secure_object_repository_for_bucket",
    "save_envelope",
    "save_encrypted_envelope",
}
_FORBIDDEN_TOKENS = (
    "NamedTemporaryFile",
    "mkstemp",
    "TemporaryDirectory",
)


def _subpackage_modules() -> list:
    """Return every non-test module in the subpackage.

    Fails loudly on an empty result. The whole point of the enumerated-surface
    lesson this campaign learned is that a check over nothing reports success
    identically to a check over clean code -- so a rename or relocation that
    empties this path must break these tests rather than silently pass them.
    """
    modules = list(non_test_python_files_under(_LLM_PACKAGE, include_data=True))
    assert modules, (
        f"{repo_relative(_LLM_PACKAGE)} resolved to zero non-test modules; the package was "
        "renamed, moved or emptied and these assertions are now vacuous. Fix the path -- "
        "do not delete this check."
    )
    return modules


def test_the_subpackage_is_not_empty_so_these_assertions_are_not_vacuous() -> None:
    """Positive control. Without it, every assertion below could pass over nothing."""
    assert len(_subpackage_modules()) >= 5


def test_no_module_writes_a_file_or_opens_a_temp_path() -> None:
    """No rasterised page, debug dump or temp file reaches disk, at any log level.

    A rendered invoice page IS the invoice. The rule this enforces names
    "no temp files, no scratch directories, no plaintext side stores, no
    on-disk caches, no logs", and its own worked failure is exactly this shape:
    an early design routed decrypted bytes through a temp file for a subprocess
    to read by path, and it was rejected.

    Mutation that must trip this: add ``tempfile.NamedTemporaryFile()`` to any
    module in the subpackage, including under a ``if logger.isEnabledFor(DEBUG)``
    branch. The branch is irrelevant -- a debug-only escape hatch is still an
    escape hatch, which is why this is an AST scan and not a runtime test.
    """
    offences: list[str] = []
    for path in _subpackage_modules():
        relative = repo_relative(path)
        text = path.read_text(encoding="utf-8")
        offences.extend(f"{relative}: contains {token!r}" for token in _FORBIDDEN_TOKENS if token in text)
        tree = ast_for_path(path)
        assert tree is not None, f"{relative} must be parseable"
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and leaf_name(node.func) in _FORBIDDEN_WRITE_CALLS:
                offences.append(f"{relative}:{node.lineno}: calls {leaf_name(node.func)}")
    assert offences == [], (
        "the inference subpackage must write nothing to disk -- no page raster, no debug dump, "
        f"no temp file, at any log level. Offences: {offences}"
    )


def test_no_module_constructs_a_store_or_resolves_secure_storage() -> None:
    """The subpackage holds no repository handle and constructs no store.

    It receives already-resolved bytes in memory and returns a typed payload.
    The three persistence-touching stores stay on the core side of the boundary
    and are injected, never built here.

    Mutation that must trip this: construct an ``AttachmentStore`` or call
    ``secure_object_repository_for_active_bucket`` anywhere in the subpackage.
    """
    offences: list[str] = []
    for path in _subpackage_modules():
        relative = repo_relative(path)
        tree = ast_for_path(path)
        assert tree is not None, f"{relative} must be parseable"
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and leaf_name(node.func) in _FORBIDDEN_STORE_CALLS:
                offences.append(f"{relative}:{node.lineno}: calls {leaf_name(node.func)}")
    assert offences == [], f"the inference subpackage must resolve no secure storage. Offences: {offences}"

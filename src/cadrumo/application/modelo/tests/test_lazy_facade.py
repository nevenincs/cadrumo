"""Import isolation and exact public-contract tests for the modelo facade."""

from __future__ import annotations

import ast
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_OLD_PUBLIC_CONTRACT_SHA256 = "b4ec03419e7fba4ce5059017dbbd44df2f81b6976e28964f2f879f9caa0c5dce"
_OLD_PUBLIC_CONTRACT_SIZE = 430
_FORBIDDEN_IMPORT_PREFIXES = (
    "cadrumo.application.storage.calc_sheets",
    "cadrumo.adapters.persistence.storage",
)


def _run_python(source: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603 - fixed interpreter and test-owned source
        [sys.executable, "-c", source],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )


def test_old_public_contract_is_the_new_lazy_export_fixed_point() -> None:
    """The ordered pre-migration ``__all__`` is preserved by every lazy table."""
    import cadrumo.application.modelo as modelo

    encoded_contract = json.dumps(modelo.__all__, separators=(",", ":")).encode()

    assert len(modelo.__all__) == _OLD_PUBLIC_CONTRACT_SIZE
    assert hashlib.sha256(encoded_contract).hexdigest() == _OLD_PUBLIC_CONTRACT_SHA256
    assert set(modelo.__all__) == set(modelo._LAZY_EXPORTS)
    assert set(modelo.__all__).issubset(dir(modelo))


def test_lazy_public_names_have_exact_static_owner_bindings() -> None:
    """Type-checker imports and runtime dispatch name the same canonical owners."""
    import cadrumo.application.modelo as modelo

    facade_tree = ast.parse(Path(modelo.__file__).read_text(encoding="utf-8"))
    type_checking_block = next(
        statement
        for statement in facade_tree.body
        if isinstance(statement, ast.If)
        and isinstance(statement.test, ast.Name)
        and statement.test.id == "TYPE_CHECKING"
    )
    static_owners = {
        alias.asname or alias.name: "." * statement.level + (statement.module or "")
        for statement in type_checking_block.body
        if isinstance(statement, ast.ImportFrom)
        for alias in statement.names
    }

    assert static_owners == modelo._LAZY_EXPORTS


def test_importing_modelo_facade_initializes_no_owned_submodule() -> None:
    """Bare facade import pays none of its 61 owning-module initialization cost."""
    completed = _run_python(
        "import json, sys; import cadrumo.application.modelo; "
        "print(json.dumps(sorted(name for name in sys.modules "
        "if name.startswith('cadrumo.application.modelo.'))))"
    )

    assert completed.returncode == 0, completed.stderr
    assert json.loads(completed.stdout) == []


def test_importing_lightweight_child_excludes_calculation_storage_graphs() -> None:
    """A lightweight modelo child imports without initializing calculation storage."""
    completed = _run_python(
        "import json, sys; import cadrumo.application.modelo._decimal_parsing; "
        "print(json.dumps(sorted(name for name in sys.modules "
        f"if name.startswith({_FORBIDDEN_IMPORT_PREFIXES!r}))))"
    )

    assert completed.returncode == 0, completed.stderr
    leaked = json.loads(completed.stdout)
    assert leaked == []


def test_each_public_name_resolves_from_its_declared_owner() -> None:
    """Every lazy facade member is the exact object exported by its owner."""
    import cadrumo.application.modelo as modelo

    for name, module_path in modelo._LAZY_EXPORTS.items():
        value = getattr(modelo, name)
        owner = modelo._LAZY_MODULE_LOADERS[module_path]()
        assert value is getattr(owner, name), name

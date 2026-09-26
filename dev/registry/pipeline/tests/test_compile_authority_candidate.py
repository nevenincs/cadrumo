"""The candidate compiler's process entry refuses an unusable registry with its own status."""

from __future__ import annotations

from pathlib import Path

import pytest

from .. import compile_authority_candidate
from ..candidate_compile_process import CANDIDATE_COMPILER_MODULE, run_candidate_compiler

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_the_spawned_module_name_is_this_entry() -> None:
    """The spawn names its module by a literal, which must stay this entry's import name."""
    assert compile_authority_candidate.__name__ == CANDIDATE_COMPILER_MODULE


def test_an_unusable_registry_is_refused_on_stderr_and_nothing_is_staged(tmp_path: Path) -> None:
    """The parent resolves every input before spawning, so the child sees existing but unusable ones."""
    empty = tmp_path / "registry"
    empty.mkdir()
    schema = tmp_path / "schema.toml"
    schema.write_text("", encoding="utf-8")
    output = tmp_path / "staged"

    result = run_candidate_compiler(
        registry_root=empty,
        source_root=empty,
        profile_schema_path=schema,
        output=output,
    )

    assert result.returncode == 1, result.diagnostics
    assert not result.succeeded
    assert "RegistryValidationError" in result.diagnostics
    assert not output.exists() or not any(output.iterdir())

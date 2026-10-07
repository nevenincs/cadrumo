"""CMake publication reuses the canonical compiler dependency identity."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

import cadrumo
from dev.registry.compiler import compiler_source_tree

from .. import authority_build

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_compiler_change_forces_publication_without_changing_legal_currency(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    generated = tmp_path / "generated"
    generated.mkdir()
    (tmp_path / "inputs-authority-compiler.txt").write_text("", encoding="utf-8")
    monkeypatch.setattr(authority_build, "build_paths", lambda build: {"generated": generated})
    compiler = "compiler-one"
    monkeypatch.setattr(authority_build, "compiler_source_tree_digest", lambda: compiler)
    commands: list[list[str]] = []

    def run(command: list[str], **kwargs: object) -> SimpleNamespace:
        commands.append(command)
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(authority_build, "run_command", run)
    authority_build.publish(tmp_path)
    authority_build.publish(tmp_path)
    compiler = "changed-domain-profile-schema"
    authority_build.publish(tmp_path)
    assert ["--if-stale" in command for command in commands] == [False, True, False]


def test_canonical_compiler_identity_covers_schema_but_excludes_analysis(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    package = tmp_path / "src/cadrumo"
    schema = package / "domain/user_profile/schema.py"
    schema.parent.mkdir(parents=True)
    schema.write_text("original schema", encoding="utf-8")
    analysis = tmp_path / "dev/registry/analysis/diagnostics.py"
    analysis.parent.mkdir(parents=True)
    analysis.write_text("unrelated tooling", encoding="utf-8")
    (tmp_path / "pyproject.toml").write_text("manifest", encoding="utf-8")
    (tmp_path / "uv.lock").write_text("lock", encoding="utf-8")
    monkeypatch.setattr(cadrumo, "__file__", str(package / "__init__.py"))
    monkeypatch.setattr(compiler_source_tree, "_DEVELOPMENT_ROOT", tmp_path / "dev/registry")
    monkeypatch.setattr(compiler_source_tree, "_REPOSITORY_ROOT", tmp_path)

    def identity() -> str:
        compiler_source_tree.compiler_source_tree_digest.cache_clear()
        return compiler_source_tree.compiler_source_tree_digest()

    try:
        baseline = identity()
        analysis.write_text("changed unrelated tooling", encoding="utf-8")
        assert identity() == baseline
        schema.write_text("changed schema", encoding="utf-8")
        assert identity() != baseline
    finally:
        compiler_source_tree.compiler_source_tree_digest.cache_clear()

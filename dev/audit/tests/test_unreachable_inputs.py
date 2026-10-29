"""Incomplete source and data corpora cannot produce a reachability verdict."""

from __future__ import annotations

from pathlib import Path

import pytest

from ..unreachable_code import scan_unreachable_code
from ..unreachable_memo import parse_module
from ..unreachable_models import Confidence, UnreachableCodeOutcome
from ..unreachable_reporting import filter_by_confidence, result_as_json
from ..unreachable_tree import EntryPoint, OutsideCorpus, ShippedTreeSpec

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def _spec(root: Path) -> ShippedTreeSpec:
    package = root / "src" / "pkg"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text("", encoding="utf-8")
    (package / "cli.py").write_text("def main(): pass\n", encoding="utf-8")
    (root / "dev").mkdir()
    return ShippedTreeSpec(
        repo_root=root,
        src_root=root / "src",
        packages=("pkg",),
        entry_points=(EntryPoint("pkg.cli", "main"),),
        outside=(OutsideCorpus("dev", root / "dev"),),
        data_globs=("_data/**/*.json",),
    )


@pytest.mark.parametrize("source", [b"def (: \n", b"\xff\xfe"])
def test_broken_reference_source_is_unavailable_with_its_reason(tmp_path: Path, source: bytes) -> None:
    spec = _spec(tmp_path)
    path = tmp_path / "dev" / "broken.py"
    path.write_bytes(source)

    result = scan_unreachable_code(spec)

    assert result.outcome is UnreachableCodeOutcome.ERROR
    assert "broken.py" in result.reason
    assert "SyntaxError" in result.reason
    assert not result.is_green
    assert filter_by_confidence(result, Confidence.EXACT).outcome is UnreachableCodeOutcome.ERROR
    assert "broken.py" in result_as_json(result)


@pytest.mark.parametrize("source", [b"{broken", b"\xff\xfe"])
def test_broken_data_is_unavailable_instead_of_unused_members(tmp_path: Path, source: bytes) -> None:
    spec = _spec(tmp_path)
    data = tmp_path / "src" / "pkg" / "_data"
    data.mkdir()
    (data / "broken.json").write_bytes(source)

    result = scan_unreachable_code(spec)

    assert result.outcome is UnreachableCodeOutcome.ERROR
    assert "broken.json" in result.reason
    assert "coverage is unproven" in result.reason
    assert result.symbols == ()


def test_missing_reference_corpus_cannot_look_empty(tmp_path: Path) -> None:
    spec = _spec(tmp_path)
    (tmp_path / "dev").rmdir()

    result = scan_unreachable_code(spec)

    assert result.outcome is UnreachableCodeOutcome.ERROR
    assert "does not exist" in result.reason


@pytest.mark.parametrize("source", [b"\xef\xbb\xbfVALUE = 1\n", b"# coding: latin-1\nVALUE = 'caf\xe9'\n"])
def test_source_parsing_honours_python_encoding_rules(tmp_path: Path, source: bytes) -> None:
    path = tmp_path / "encoded.py"
    path.write_bytes(source)

    assert parse_module(path).body


def test_a_same_named_function_in_another_module_is_not_a_console_entrypoint(tmp_path: Path) -> None:
    spec = _spec(tmp_path)
    package = tmp_path / "src" / "pkg"
    (package / "cli.py").write_text("from . import work\ndef main(): pass\n", encoding="utf-8")
    (package / "work.py").write_text("def main(): pass\n", encoding="utf-8")

    result = scan_unreachable_code(spec)

    assert result.outcome is UnreachableCodeOutcome.FINDINGS
    assert {(finding.module, finding.name) for finding in result.symbols} == {("pkg.work", "main")}


def _write_repository(root: Path, sources: dict[str, str]) -> None:
    for relative, source in sources.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(source, encoding="utf-8")
    (root / "dev").mkdir(exist_ok=True)
    (root / "packaging").mkdir(exist_ok=True)


def _pyproject(script: str) -> str:
    return (
        f'[project]\nname = "example"\n[project.scripts]\nexample = "{script}"\n'
        "[tool.hatch.build.targets.wheel]\nexclude = []\n"
    )


def test_every_source_package_is_audited_and_a_scriptless_one_supplies_edges(tmp_path: Path) -> None:
    """A package without a console script is both a consumer and a subject of the audit."""
    _write_repository(
        tmp_path,
        {
            "src/cadrumo/__init__.py": "",
            "src/cadrumo/cli.py": "from cadrumo_client.bridge import run\ndef main(): run()\n",
            "src/cadrumo/facts.py": "def active(): pass\ndef orphan(): pass\n",
            "src/cadrumo_client/__init__.py": "",
            "src/cadrumo_client/bridge.py": (
                "from cadrumo.facts import active\ndef run(): active()\ndef stray(): pass\n"
            ),
            "src/cadrumo_client/idle.py": "def never(): pass\n",
            "conftest.py": "",
            "pyproject.toml": _pyproject("cadrumo.cli:main"),
        },
    )

    spec = ShippedTreeSpec.from_repository(tmp_path)
    result = scan_unreachable_code(spec)

    assert spec.packages == ("cadrumo", "cadrumo_client")
    assert result.packages == ("cadrumo", "cadrumo_client")
    assert result.outcome is UnreachableCodeOutcome.FINDINGS
    assert result.roots == ("cadrumo.cli:main",)
    assert result.shipped_modules == 6
    assert {finding.module for finding in result.modules} == {"cadrumo_client.idle"}
    assert {(finding.module, finding.name) for finding in result.symbols} == {
        ("cadrumo.facts", "orphan"),
        ("cadrumo_client.bridge", "stray"),
    }


def test_each_audited_package_reads_its_own_shipped_payloads(tmp_path: Path) -> None:
    """A locale catalogue of the second package clears that package's data-shaped member."""
    from ..unreachable_references import _data_tokens

    _write_repository(
        tmp_path,
        {
            "src/first/__init__.py": "",
            "src/first/locales/es.json": '{"key": "first_token"}\n',
            "src/second/__init__.py": "",
            "src/second/locales/es.json": '{"key": "second_token"}\n',
        },
    )
    spec = ShippedTreeSpec(
        repo_root=tmp_path,
        src_root=tmp_path / "src",
        packages=("first", "second"),
        entry_points=(),
        data_globs=("locales/**/*.json",),
    )

    assert {"first_token", "second_token"} <= _data_tokens(spec)


def test_packaging_hooks_clear_resolved_consumers_but_not_lookalikes_or_tests(tmp_path: Path) -> None:
    """Build-hook edges count; matching tokens and packaging tests cannot clear code."""
    _write_repository(
        tmp_path,
        {
            "src/cadrumo/__init__.py": "",
            "src/cadrumo/cli.py": "from . import facts\ndef main(): pass\n",
            "src/cadrumo/facts.py": (
                "def prepare_temporary_directory(): pass\ndef lookalike(): pass\ndef test_only(): pass\n"
            ),
            "src/cadrumo/build_support.py": "def stage(): pass\n",
            "src/cadrumo/probe_support.py": "def check(): pass\n",
            "packaging/authority/hatch_build.py": (
                "def initialize():\n"
                "    from cadrumo.coreless import lookalike\n"
                "    from cadrumo.facts import prepare_temporary_directory\n"
                "    from cadrumo.build_support import stage\n"
                "    prepare_temporary_directory()\n"
                "    stage()\n"
                "    lookalike()\n"
                "    return {'lookalike': 'lookalike'}\n"
            ),
            "src/cadrumo/coreless.py": "def lookalike(): pass\n",
            "packaging/tests/test_hook.py": (
                "from cadrumo.facts import test_only\nfrom cadrumo.probe_support import check\ntest_only()\ncheck()\n"
            ),
            "conftest.py": "",
            "pyproject.toml": _pyproject("cadrumo.cli:main"),
        },
    )

    spec = ShippedTreeSpec.from_repository(tmp_path)
    result = scan_unreachable_code(spec)

    assert any(corpus.label == "packaging" and corpus.root == tmp_path / "packaging" for corpus in spec.outside)
    assert result.outcome is UnreachableCodeOutcome.FINDINGS
    symbols = {(finding.module, finding.name): finding for finding in result.symbols}
    assert ("cadrumo.facts", "prepare_temporary_directory") not in symbols
    assert ("cadrumo.build_support", "stage") not in symbols
    assert ("cadrumo.facts", "lookalike") in symbols
    assert symbols["cadrumo.facts", "test_only"].used_by == ("tests",)
    modules = {finding.module: finding for finding in result.modules}
    assert "cadrumo.build_support" not in modules
    assert modules["cadrumo.probe_support"].used_by == ("tests",)
    assert result.dev_cleared == 0


def test_a_package_outside_the_declared_source_scope_is_refused(tmp_path: Path) -> None:
    """Auditing around an undeclared package would understate where the gate stops."""
    _write_repository(
        tmp_path,
        {
            "src/cadrumo/__init__.py": "",
            "src/cadrumo/cli.py": "def main(): pass\n",
            "src/stowaway/__init__.py": "",
            "pyproject.toml": _pyproject("cadrumo.cli:main"),
        },
    )

    with pytest.raises(ValueError, match="stowaway"):
        ShippedTreeSpec.from_repository(tmp_path)


def test_a_console_script_outside_the_audited_packages_is_refused(tmp_path: Path) -> None:
    """A root the walk cannot load would silently shrink the reachable set."""
    _write_repository(
        tmp_path,
        {
            "src/cadrumo/__init__.py": "",
            "src/cadrumo/cli.py": "def main(): pass\n",
            "pyproject.toml": _pyproject("cadrumo_mcp.mcp.main:main"),
        },
    )

    with pytest.raises(ValueError, match=r"cadrumo_mcp\.mcp\.main:main"):
        ShippedTreeSpec.from_repository(tmp_path)

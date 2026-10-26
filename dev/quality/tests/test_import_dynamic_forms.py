"""Import forms the subordinate checker must see beyond import statements.

Each case plants one spelling in an isolated source tree and runs the real
dynamic checks and occurrence collection over it: interpreter payloads
(``python -c`` source and ``python -m`` modules), ``runpy.run_module``,
dynamic loaders evaluated in a definition's enclosing scope, and the per-call
``__import__`` classification.
"""

from __future__ import annotations

import configparser
from pathlib import Path

import pytest

from dev.quality.import_binding_inventory import read_modules
from dev.quality.import_check_models import Authority, Finding, ForbiddenContract, ImportOccurrence, RootPackage
from dev.quality.import_dynamic_checks import check_dynamic_imports
from dev.quality.import_occurrences import collect_import_occurrences
from dev.quality.import_record_provenance import RecordTargetProvenance

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_FORBIDDEN_EDGE = ("sample.loader", "sample.forbidden")


def _run(tmp_path: Path, loader: str) -> tuple[list[Finding], tuple[ImportOccurrence, ...]]:
    """Run the real dynamic checks and occurrence collection over a planted loader."""
    root = tmp_path / "sample"
    root.mkdir()
    (root / "__init__.py").write_text("", encoding="utf-8")
    (root / "hidden").mkdir()
    (root / "hidden" / "__init__.py").write_text("", encoding="utf-8")
    sources = {
        "allowed.py": "value = 1\n",
        "forbidden.py": "value = 2\n",
        "hidden/_private.py": "value = 3\n",
        "loader.py": loader,
    }
    for relative, source in sources.items():
        (root / relative).write_text(source, encoding="utf-8")
    authority = Authority(
        tmp_path,
        tmp_path / "authority.ini",
        configparser.ConfigParser(),
        ("sample",),
        (RootPackage("sample", root),),
        (),
        (ForbiddenContract("boundary", "boundary", ("sample.loader",), ("sample.forbidden",)),),
    )
    modules, findings = read_modules(authority)
    provenance = RecordTargetProvenance(modules)
    check_dynamic_imports(authority, modules, findings, provenance)
    return findings, collect_import_occurrences(authority, modules, provenance)


def _check(tmp_path: Path, loader: str) -> tuple[list[str], set[tuple[str, str, str]]]:
    """Return blocking finding categories and occurrence edges for a planted loader."""
    findings, occurrences = _run(tmp_path, loader)
    return [finding.category for finding in findings if not finding.advisory], {
        (item.source_module, item.target_module, item.import_form) for item in occurrences
    }


@pytest.mark.parametrize(
    "loader",
    [
        "import subprocess, sys\nsubprocess.run([sys.executable, '-c', 'import sample.forbidden'])\n",
        "import subprocess, sys\nsubprocess.run((sys.executable, '-I', '-c', 'from sample.forbidden import value'))\n",
        (
            "import subprocess, sys\n"
            "CODE = 'from pathlib import Path; ' + 'from sample.forbidden import value'\n"
            "def run():\n"
            "    return subprocess.run([sys.executable, '-c', CODE, 'argument'])\n"
        ),
        (
            "import subprocess, sys, textwrap\n"
            "def run(root):\n"
            "    code = textwrap.dedent(\n"
            "        f'''\n"
            "        from pathlib import Path\n"
            "        from sample.forbidden import value\n"
            "        print(Path({str(root)!r}), value)\n"
            "        '''\n"
            "    )\n"
            "    return subprocess.run([sys.executable, '-c', code])\n"
        ),
        "def launch(*argv): ...\nlaunch('-c', 'import json; import sample.forbidden')\n",
        "import subprocess, sys\nsubprocess.run([sys.executable, '-c', \"__import__('sample.forbidden')\"])\n",
    ],
    ids=["literal", "from-import", "concatenated-name", "dedented-fstring", "call-arguments", "payload-loader"],
)
def test_interpreter_code_payload_is_an_import_of_the_launching_module(tmp_path: Path, loader: str) -> None:
    _categories, edges = _check(tmp_path, loader)

    assert (*_FORBIDDEN_EDGE, "string") in edges


def test_interpreter_module_payload_is_an_import_of_the_launching_module(tmp_path: Path) -> None:
    _categories, edges = _check(
        tmp_path, "import subprocess, sys\nsubprocess.run([sys.executable, '-m', 'sample.forbidden', '--help'])\n"
    )

    assert (*_FORBIDDEN_EDGE, "string") in edges


@pytest.mark.parametrize(
    "loader",
    [
        "import subprocess\nsubprocess.run(['bash', '-c', 'echo import sample.forbidden'])\n",
        "import subprocess, sys\nsubprocess.run([sys.executable, '-c', 'import sample.allowed'])\n",
        "import subprocess, sys\nsubprocess.run([sys.executable, '-m', 'pytest', '-m', 'not slow'])\n",
        "import subprocess, sys\nsubprocess.run([sys.executable, '-c'])\n",
        "import subprocess, sys\ndef run(name):\n    return subprocess.run([sys.executable, '-m', f'sample.{name}'])\n",
        (
            "import subprocess, sys\n"
            "def run(name):\n"
            "    return subprocess.run([sys.executable, '-c', f'import sample.{name}'])\n"
        ),
    ],
    ids=[
        "shell-text",
        "permitted-target",
        "third-party-and-marker",
        "flag-without-payload",
        "open-module-name",
        "open-code-import",
    ],
)
def test_interpreter_payloads_that_name_no_forbidden_module_record_no_edge(tmp_path: Path, loader: str) -> None:
    categories, edges = _check(tmp_path, loader)

    assert _FORBIDDEN_EDGE not in {(source, target) for source, target, _form in edges}
    assert categories == []


def test_interpreter_payload_reaching_a_private_owner_is_reported(tmp_path: Path) -> None:
    categories, _edges = _check(
        tmp_path, "import subprocess, sys\nsubprocess.run([sys.executable, '-c', 'import sample.hidden._private'])\n"
    )

    assert categories and set(categories) == {"PRIVATE_CROSS_PACKAGE"}


def test_interpreter_payload_naming_a_missing_first_party_module_is_reported(tmp_path: Path) -> None:
    categories, _edges = _check(
        tmp_path, "import subprocess, sys\nsubprocess.run([sys.executable, '-c', 'import sample.missing'])\n"
    )

    assert categories == ["STATIC_TARGET_UNRESOLVED"]


@pytest.mark.parametrize(
    "loader",
    [
        "import runpy\nrunpy.run_module('sample.forbidden')\n",
        "import runpy as launcher\nlauncher.run_module(mod_name='sample.forbidden', run_name='__main__')\n",
        "from runpy import run_module as run\nrun('sample.forbidden')\n",
        "import runpy\nrun = runpy.run_module\nrun('sample.forbidden')\n",
    ],
    ids=["attribute", "module-alias-keyword", "from-alias", "assigned-alias"],
)
def test_run_module_with_a_literal_target_is_a_dynamic_import(tmp_path: Path, loader: str) -> None:
    categories, edges = _check(tmp_path, loader)

    assert (*_FORBIDDEN_EDGE, "dynamic") in edges
    assert categories == []


def test_run_module_reaching_a_private_owner_is_reported(tmp_path: Path) -> None:
    categories, _edges = _check(tmp_path, "import runpy\nrunpy.run_module('sample.hidden._private')\n")

    assert categories and set(categories) == {"PRIVATE_CROSS_PACKAGE"}


def test_run_module_with_an_open_target_is_unresolved(tmp_path: Path) -> None:
    categories, _edges = _check(tmp_path, "import runpy, sys\nrunpy.run_module(sys.argv[1])\n")

    assert categories == ["UNRESOLVED_DYNAMIC_TARGET"]


@pytest.mark.parametrize(
    "loader",
    [
        (
            "import importlib\n"
            "def register(module):\n"
            "    return lambda function: function\n"
            "@register(importlib.import_module('sample.forbidden'))\n"
            "def handler():\n"
            "    return None\n"
        ),
        ("import importlib\ndef handler(module=importlib.import_module('sample.forbidden')):\n    return module\n"),
        (
            "import importlib\n"
            "async def handler(*, module=importlib.import_module('sample.forbidden')):\n"
            "    return module\n"
        ),
        "import importlib\nclass Handler(importlib.import_module('sample.forbidden').Base):\n    pass\n",
        "import importlib\nclass Handler(metaclass=importlib.import_module('sample.forbidden').Meta):\n    pass\n",
    ],
    ids=["decorator", "default", "keyword-only-default", "base-class", "class-keyword"],
)
def test_dynamic_import_evaluated_by_a_definition_header_is_recorded(tmp_path: Path, loader: str) -> None:
    _categories, edges = _check(tmp_path, loader)

    assert (*_FORBIDDEN_EDGE, "dynamic") in edges


def test_definition_header_import_is_recorded_in_the_enclosing_scope(tmp_path: Path) -> None:
    _findings, occurrences = _run(
        tmp_path,
        (
            "import importlib\n"
            "class Outer:\n"
            "    def method(self, module=importlib.import_module('sample.forbidden')):\n"
            "        return module\n"
        ),
    )

    assert {item.lexical_scope for item in occurrences} == {"Outer"}


@pytest.mark.parametrize(
    ("loader", "expected"),
    [
        ("value = __import__('sample.allowed')\nprint(value)\n", ["RAW_FIRST_PARTY_IMPORT"]),
        ("print(__import__('sample.allowed'))\n", ["RAW_FIRST_PARTY_IMPORT"]),
        ("import importlib\n__import__('os')\nimportlib.import_module('sample.allowed')\n", []),
        ("import importlib\nimportlib.import_module('sample.allowed')\n__import__('os')\n", []),
    ],
    ids=["raw-then-call", "raw-inside-call", "raw-before-loader", "loader-before-raw"],
)
def test_raw_import_classification_belongs_to_each_call(tmp_path: Path, loader: str, expected: list[str]) -> None:
    categories, _edges = _check(tmp_path, loader)

    assert categories == expected

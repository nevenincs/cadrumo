"""Planted-defect proofs for the single import-quality gate.

Every policy proof below writes only to ``tmp_path`` and invokes the real
``just check-import-boundaries`` recipe.  The temporary authority is copied from the
live ``.importlinter`` file; its roots and layer declarations are materialised
by reading that file, so this test contains no second dependency matrix.
"""

from __future__ import annotations

import configparser
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from dev._paths import REPO_ROOT, UTF_8
from dev.exit_codes import TOOL_BROKEN, TOOL_MISSING
from dev.quality.import_checker import (
    Authority,
    RootPackage,
    check_authority,
    has_architectural_warning,
    read_authority,
)
from dev.quality.import_gate import run_import_gate, run_import_linter, run_subordinate

pytestmark = [pytest.mark.integration, pytest.mark.hex_core]

_IMPORTLINTER_CONFIG = REPO_ROOT / ".importlinter"
_ROOT_ENV = "CADRUMO_IMPORT_GATE_ROOT"
_LINTER_ENV = "CADRUMO_IMPORT_GATE_LINT_IMPORTS"
_CHECKER_ENV = "CADRUMO_IMPORT_GATE_CHECKER"
_FORCE_CHECKER_ENV = "CADRUMO_IMPORT_GATE_FORCE_CHECKER_EXCEPTION"


def _write_package(root: Path, dotted: str, source: str = "") -> None:
    path = root / "src" / Path(*dotted.split("."))
    path.mkdir(parents=True, exist_ok=True)
    init = path / "__init__.py"
    if source or not init.exists():
        init.write_text(source, encoding=UTF_8, newline="\n")


def _write_module(root: Path, dotted: str, source: str) -> None:
    parts = dotted.split(".")
    for index in range(1, len(parts)):
        _write_package(root, ".".join(parts[:index]))
    path = root / "src" / Path(*parts[:-1]) / f"{parts[-1]}.py"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(source, encoding=UTF_8, newline="\n")


def _layer_names(value: str) -> tuple[str, ...]:
    return tuple(token.strip().strip("()") for token in value.replace("\n", " ").split(":") if token.strip())


def _words(value: str) -> tuple[str, ...]:
    return tuple(token for line in value.splitlines() for token in line.split())


def _fixture_root(tmp_path: Path) -> Path:
    """Copy the live authority and materialise its declared topology."""
    config = configparser.ConfigParser(interpolation=None)
    config.read(_IMPORTLINTER_CONFIG, encoding=UTF_8)
    (tmp_path / ".importlinter").write_text(
        _IMPORTLINTER_CONFIG.read_text(encoding=UTF_8),
        encoding=UTF_8,
        newline="\n",
    )

    for package in _words(config["importlinter"].get("root_packages", "")):
        _write_package(tmp_path, package)

    for name in config.sections():
        section = config[name]
        if not name.startswith("importlinter:contract:") or section.get("type", "").lower() != "layers":
            continue
        for container in _words(section.get("containers", "")):
            for layer in _layer_names(section.get("layers", "")):
                dotted = f"{container}.{layer}"
                _write_package(tmp_path, dotted)

    # Contract module expressions are still authority data, not a policy
    # table.  Materialise their named package prefixes so an otherwise clean
    # fixture fails only when the planted edge is reached.
    for name in config.sections():
        section = config[name]
        if not name.startswith("importlinter:contract:"):
            continue
        for key in ("source_modules", "forbidden_modules"):
            for expression in _words(section.get(key, "")):
                prefix = expression.rstrip(".*")
                if prefix and prefix.replace("_", "a").replace(".", "a").isalnum():
                    _write_package(tmp_path, prefix)
    return tmp_path


def _run_real_gate(root: Path, **updates: str) -> tuple[int, str]:
    environment = os.environ.copy()
    environment[_ROOT_ENV] = str(root)
    environment.update(updates)
    just_executable = shutil.which("just")
    assert just_executable is not None, "the real just driver is required for planted-defect proofs"
    result = subprocess.run(  # noqa: S603 - resolved just executable, fixed argv, no shell
        [just_executable, "check-import-boundaries"],
        cwd=REPO_ROOT,
        env=environment,
        capture_output=True,
        text=True,
        encoding=UTF_8,
        errors="replace",
        check=False,
        timeout=120,
    )
    return result.returncode, (result.stdout + result.stderr)


def _assert_category(root: Path, category: str) -> str:
    returncode, output = _run_real_gate(root)
    assert returncode != 0, output
    assert f"[{category}]" in output, output
    return output


def test_subordinate_cli_cannot_be_used_as_a_contributor_verdict() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "dev.quality.import_checker"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        encoding=UTF_8,
        errors="replace",
        check=False,
    )

    assert result.returncode == TOOL_BROKEN
    assert "[INTERNAL_CHECKER]" in (result.stdout + result.stderr)


@pytest.mark.parametrize(
    ("name", "module", "source", "targets"),
    (
        (
            "source-to-dev-production",
            "cadrumo.core.bad",
            "import dev.exit_codes\n",
            (),
        ),
        (
            "source-to-dev-test-module",
            "cadrumo.core.tests.test_bad",
            "import dev.exit_codes\n",
            (),
        ),
        (
            "source-to-dev-conftest",
            "cadrumo.conftest",
            "import dev.exit_codes\n",
            (),
        ),
        (
            "core-to-domain",
            "cadrumo.core.bad",
            "from ..domain.module import VALUE\n",
            ("cadrumo.domain.module",),
        ),
        (
            "core-to-application",
            "cadrumo.core.bad",
            "from ..application.module import VALUE\n",
            ("cadrumo.application.module",),
        ),
        (
            "core-to-adapter",
            "cadrumo.core.bad",
            "from ..adapters.module import VALUE\n",
            ("cadrumo.adapters.module",),
        ),
        (
            "core-to-entrypoint",
            "cadrumo.core.bad",
            "from ..entrypoints.module import VALUE\n",
            ("cadrumo.entrypoints.module",),
        ),
        (
            "product-to-separate-harness-root",
            "cadrumo.entrypoints.bad",
            "import cadrumo_harness.mcp.module\n",
            ("cadrumo_harness.mcp.module",),
        ),
        (
            "domain-to-application",
            "cadrumo.domain.bad",
            "from ..application.module import VALUE\n",
            ("cadrumo.application.module",),
        ),
        (
            "domain-to-adapter",
            "cadrumo.domain.bad",
            "from ..adapters.module import VALUE\n",
            ("cadrumo.adapters.module",),
        ),
        (
            "application-to-concrete-adapter",
            "cadrumo.application.bad",
            "from ..adapters.concrete import VALUE\n",
            ("cadrumo.adapters.concrete",),
        ),
        (
            "adapter-to-concrete-sibling",
            "cadrumo.adapters.inbound.bad",
            "from ..outbound.concrete import VALUE\n",
            ("cadrumo.adapters.outbound.concrete",),
        ),
        (
            "non-entrypoint-to-entrypoint",
            "cadrumo.adapters.bad",
            "from ..entrypoints.feature import VALUE\n",
            ("cadrumo.entrypoints.feature",),
        ),
        (
            "cli-to-tui",
            "cadrumo.entrypoints.cli.bad",
            "from ..tui.feature import VALUE\n",
            ("cadrumo.entrypoints.tui.feature",),
        ),
        (
            "tui-to-cli",
            "cadrumo.entrypoints.tui.bad",
            "from ..cli.feature import VALUE\n",
            ("cadrumo.entrypoints.cli.feature",),
        ),
        (
            "owner-test-to-forbidden-layer",
            "cadrumo.domain.tests.test_bad",
            "from ...application.module import VALUE\n",
            ("cadrumo.application.module",),
        ),
        (
            "function-local-forbidden-import",
            "cadrumo.domain.bad",
            "def load():\n    from ..application.module import VALUE\n    return VALUE\n",
            ("cadrumo.application.module",),
        ),
        (
            "type-checking-forbidden-import",
            "cadrumo.domain.bad",
            "from typing import TYPE_CHECKING\n\nif TYPE_CHECKING:\n    from ..application.module import VALUE\n",
            ("cadrumo.application.module",),
        ),
    ),
)
def test_graph_defect_fails_through_real_gate(
    tmp_path: Path,
    name: str,
    module: str,
    source: str,
    targets: tuple[str, ...],
) -> None:
    del name
    root = _fixture_root(tmp_path)
    for target in targets:
        _write_module(root, target, "VALUE = 1\n")
    _write_module(root, module, source)
    _assert_category(root, "GRAPH_AUTHORITY")


def test_undeclared_source_root_fails_authority_preflight(tmp_path: Path) -> None:
    root = _fixture_root(tmp_path)
    _write_package(root, "undeclared_root")
    _assert_category(root, "UNCLASSIFIED_ROOT")


def test_undeclared_source_module_fails_authority_preflight(tmp_path: Path) -> None:
    root = _fixture_root(tmp_path)
    (root / "src" / "stray.py").write_text("VALUE = 1\n", encoding=UTF_8, newline="\n")
    _assert_category(root, "UNCLASSIFIED_ROOT")


def test_declared_source_module_collision_fails_authority_preflight(tmp_path: Path) -> None:
    root = _fixture_root(tmp_path)
    (root / "src" / "cadrumo.py").write_text("VALUE = 1\n", encoding=UTF_8, newline="\n")
    _assert_category(root, "AUTHORITY_CONFIG")


def test_undeclared_source_package_fails_authority_preflight(tmp_path: Path) -> None:
    root = _fixture_root(tmp_path)
    _write_package(root, "cadrumo.unclassified_package")
    _assert_category(root, "UNCLASSIFIED_PACKAGE")


def test_authority_must_include_type_checking_edges(tmp_path: Path) -> None:
    root = _fixture_root(tmp_path)
    config = configparser.ConfigParser(interpolation=None)
    config.read(root / ".importlinter", encoding=UTF_8)
    config["importlinter"]["exclude_type_checking_imports"] = "True"
    with (root / ".importlinter").open("w", encoding=UTF_8, newline="\n") as stream:
        config.write(stream)

    _assert_category(root, "AUTHORITY_CONFIG")


def test_invalid_authority_config_fails_closed(tmp_path: Path) -> None:
    root = _fixture_root(tmp_path)
    (root / ".importlinter").write_text("[importlinter\n", encoding=UTF_8, newline="\n")
    _assert_category(root, "AUTHORITY_CONFIG")


@pytest.mark.parametrize(
    ("name", "module", "source", "target", "category"),
    (
        (
            "absolute-intra-cadrumo",
            "cadrumo.core.consumer",
            "import cadrumo.domain.module\n",
            "cadrumo.domain.module",
            "ABSOLUTE_INTRA_CADRUMO",
        ),
        (
            "static-first-party-target-missing",
            "dev.quality.consumer",
            "import cadrumo.domain.missing\n",
            "",
            "STATIC_TARGET_UNRESOLVED",
        ),
        (
            "absolute-intra-cadrumo-dynamic",
            "cadrumo.core.consumer",
            "import importlib\nimportlib.import_module('cadrumo.domain.module')\n",
            "cadrumo.domain.module",
            "ABSOLUTE_INTRA_CADRUMO",
        ),
        (
            "unsupported-first-party-wildcard",
            "dev.quality.consumer",
            "from . import *\n",
            "",
            "UNSUPPORTED_IMPORT",
        ),
        (
            "unsupported-relative-escape",
            "cadrumo.core.consumer",
            "from .... import VALUE\n",
            "",
            "UNSUPPORTED_IMPORT",
        ),
        (
            "unsupported-dynamic-call",
            "dev.quality.consumer",
            "import importlib\nimportlib.import_module()\n",
            "",
            "UNSUPPORTED_DYNAMIC",
        ),
        (
            "dunder-init-submodule",
            "dev.quality.consumer",
            "import cadrumo.domain.module.__init__\n",
            "",
            "DUNDER_INIT_SUBMODULE",
        ),
        (
            "dunder-init-from-submodule",
            "dev.quality.consumer",
            "from cadrumo.domain.module.__init__ import VALUE\n",
            "",
            "DUNDER_INIT_SUBMODULE",
        ),
        (
            "package-facade",
            "dev.quality.consumer",
            "from . import VALUE\n",
            "",
            "PACKAGE_FACADE",
        ),
        (
            "forwarding-module",
            "dev.quality.consumer",
            "from .forward import VALUE\n",
            "dev.quality.forward",
            "FORWARDING_MODULE",
        ),
        (
            "reexport-or-alias",
            "dev.quality.consumer",
            "from .reexport import VALUE_ALIAS\n",
            "dev.quality.reexport",
            "REEXPORT_OR_ALIAS",
        ),
        (
            "active-package-initializer",
            "dev.quality.consumer",
            "from .module import VALUE\n",
            "dev.quality.module",
            "ACTIVE_INITIALIZER",
        ),
        (
            "private-cross-package",
            "dev.audit.consumer",
            "from ..quality._private import VALUE\n",
            "dev.quality._private",
            "PRIVATE_CROSS_PACKAGE",
        ),
        (
            "literal-dynamic-private-target",
            "dev.quality.consumer",
            "import importlib\nimportlib.import_module('cadrumo.domain._private')\n",
            "cadrumo.domain._private",
            "PRIVATE_CROSS_PACKAGE",
        ),
        (
            "finite-computed-dynamic-private-target",
            "dev.quality.consumer",
            (
                "import importlib\n"
                "target = 'cadrumo.domain._private' if True else 'third.party'\n"
                "importlib.import_module(target)\n"
            ),
            "cadrumo.domain._private",
            "PRIVATE_CROSS_PACKAGE",
        ),
        (
            "unresolved-computed-dynamic-target",
            "dev.quality.consumer",
            "import importlib\nimport os\ntarget = os.environ['MODULE']\nimportlib.import_module(target)\n",
            "",
            "UNRESOLVED_DYNAMIC_TARGET",
        ),
        (
            "raw-first-party-import",
            "dev.quality.consumer",
            "__import__('cadrumo.domain.module')\n",
            "cadrumo.domain.module",
            "RAW_FIRST_PARTY_IMPORT",
        ),
        (
            "literal-dynamic-first-party-target-missing",
            "dev.quality.consumer",
            "import importlib\nimportlib.import_module('cadrumo.domain.missing')\n",
            "",
            "DYNAMIC_TARGET_UNRESOLVED",
        ),
        (
            "local-package-facade",
            "dev.quality.consumer",
            "def load():\n    from . import VALUE\n    return VALUE\n",
            "",
            "PACKAGE_FACADE",
        ),
        (
            "type-checking-package-facade",
            "dev.quality.consumer",
            "from typing import TYPE_CHECKING\n\nif TYPE_CHECKING:\n    from . import VALUE\n",
            "",
            "PACKAGE_FACADE",
        ),
    ),
)
def test_subordinate_defect_fails_through_real_gate(
    tmp_path: Path,
    name: str,
    module: str,
    source: str,
    target: str,
    category: str,
) -> None:
    del name
    root = _fixture_root(tmp_path)
    if target:
        _write_module(root, target, "VALUE = 1\n")
    if category == "FORWARDING_MODULE":
        _write_module(root, "dev.quality.module", "VALUE = 1\n")
        _write_module(root, "dev.quality.forward", "from .module import VALUE\n")
    elif category == "REEXPORT_OR_ALIAS":
        _write_module(root, "dev.quality.module", "VALUE = 1\n")
        _write_module(
            root,
            "dev.quality.reexport",
            "from .module import VALUE\ndef local():\n    return VALUE\nVALUE_ALIAS = VALUE\n",
        )
    elif category == "ACTIVE_INITIALIZER":
        _write_package(root, "dev.quality", "from .module import VALUE\n")
        _write_module(root, "dev.quality.module", "VALUE = 1\n")
    _write_module(root, module, source)
    _assert_category(root, category)


def test_finite_iterable_dynamic_target_is_resolved_by_the_subordinate_checker(tmp_path: Path) -> None:
    root = _fixture_root(tmp_path)
    _write_module(
        root,
        "dev.quality.consumer",
        (
            "import importlib\n"
            "targets = ('cadrumo.domain._private', 'third.party')\n"
            "for target in targets:\n"
            "    importlib.import_module(target)\n"
        ),
    )
    _write_module(root, "cadrumo.domain._private", "VALUE = 1\n")

    _assert_category(root, "PRIVATE_CROSS_PACKAGE")


def test_aliased_dynamic_loader_is_resolved_by_the_subordinate_checker(tmp_path: Path) -> None:
    root = _fixture_root(tmp_path)
    _write_module(
        root,
        "dev.quality.consumer",
        ("from importlib import import_module as load_module\nload_module('cadrumo.domain._private')\n"),
    )
    _write_module(root, "cadrumo.domain._private", "VALUE = 1\n")

    _assert_category(root, "PRIVATE_CROSS_PACKAGE")


def test_module_alias_dynamic_loader_is_resolved_by_the_subordinate_checker(tmp_path: Path) -> None:
    root = _fixture_root(tmp_path)
    _write_module(
        root,
        "dev.quality.consumer",
        ("import importlib as il\nloader = il.import_module\nloader('cadrumo.domain._private')\n"),
    )
    _write_module(root, "cadrumo.domain._private", "VALUE = 1\n")

    _assert_category(root, "PRIVATE_CROSS_PACKAGE")


def test_dotted_dynamic_loader_alias_is_resolved_by_the_subordinate_checker(tmp_path: Path) -> None:
    root = _fixture_root(tmp_path)
    _write_module(
        root,
        "dev.quality.consumer",
        ("import importlib.import_module as loader\nloader('cadrumo.domain._private')\n"),
    )
    _write_module(root, "cadrumo.domain._private", "VALUE = 1\n")

    _assert_category(root, "PRIVATE_CROSS_PACKAGE")


def test_relative_dynamic_target_uses_the_importing_package(tmp_path: Path) -> None:
    root = _fixture_root(tmp_path)
    _write_module(
        root,
        "cadrumo.core.consumer",
        "import importlib\nimportlib.import_module('.dynamic', __package__)\n",
    )
    _write_module(root, "cadrumo.core.dynamic", "VALUE = 1\n")

    returncode, output = _run_real_gate(root)

    assert returncode == 0, output


def test_finite_object_module_projection_is_resolved_by_the_subordinate_checker(tmp_path: Path) -> None:
    root = _fixture_root(tmp_path)
    _write_module(
        root,
        "dev.quality.consumer",
        (
            "from dataclasses import dataclass\n"
            "import importlib\n\n"
            "@dataclass(frozen=True)\n"
            "class Target:\n"
            "    module: str\n\n"
            "target = Target('cadrumo.domain._private')\n"
            "importlib.import_module(target.module)\n"
        ),
    )
    _write_module(root, "cadrumo.domain._private", "VALUE = 1\n")

    _assert_category(root, "PRIVATE_CROSS_PACKAGE")


def test_relative_object_module_projection_uses_its_explicit_package_anchor(tmp_path: Path) -> None:
    root = _fixture_root(tmp_path)
    _write_module(
        root,
        "cadrumo.core.consumer",
        (
            "from dataclasses import dataclass\n"
            "import importlib\n\n"
            "@dataclass(frozen=True)\n"
            "class Target:\n"
            "    module: str\n"
            "    qualname: str\n"
            "    package: str | None = None\n\n"
            "target = Target('.dynamic', 'VALUE', __package__)\n"
            "importlib.import_module(target.module, target.package)\n"
        ),
    )
    _write_module(root, "cadrumo.core.dynamic", "VALUE = 1\n")

    returncode, output = _run_real_gate(root)

    assert returncode == 0, output


def test_unknown_object_module_projection_fails_closed(tmp_path: Path) -> None:
    root = _fixture_root(tmp_path)
    _write_module(
        root,
        "dev.quality.consumer",
        "import importlib\n\nclass Target: pass\ntarget = Target()\nimportlib.import_module(target.module)\n",
    )

    _assert_category(root, "UNRESOLVED_DYNAMIC_TARGET")


def test_separate_harness_root_keeps_absolute_product_imports(tmp_path: Path) -> None:
    root = _fixture_root(tmp_path)
    _write_module(
        root,
        "cadrumo_harness.mcp.consumer",
        "from cadrumo.core.module import VALUE\n",
    )
    _write_module(root, "cadrumo.core.module", "VALUE = 1\n")

    returncode, output = _run_real_gate(root)

    assert returncode == 0, output
    assert "ABSOLUTE_INTRA_CADRUMO" not in output


def test_invalid_utf8_in_governed_file_fails_closed(tmp_path: Path) -> None:
    root = _fixture_root(tmp_path)
    path = root / "src" / "dev" / "quality" / "unreadable.py"
    path.write_bytes(b"\xff\xfe\xfd")
    _assert_category(root, "READ_FAILURE")


def test_syntax_failure_in_governed_file_fails_closed(tmp_path: Path) -> None:
    root = _fixture_root(tmp_path)
    _write_module(root, "dev.quality.unparseable", "def broken(:\n")
    _assert_category(root, "PARSE_FAILURE")


def test_missing_import_linter_executable_is_nonzero_through_real_recipe(tmp_path: Path) -> None:
    root = _fixture_root(tmp_path)
    returncode, output = _run_real_gate(root, **{_LINTER_ENV: "cadrumo-import-linter-does-not-exist"})
    assert returncode != 0, output
    assert "[TOOL_MISSING]" in output
    assert run_import_gate(root, lint_executable="cadrumo-import-linter-does-not-exist") == TOOL_MISSING


def test_missing_subordinate_checker_executable_is_nonzero_through_real_recipe(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _fixture_root(tmp_path)
    returncode, output = _run_real_gate(root, **{_CHECKER_ENV: "cadrumo-import-checker-does-not-exist"})
    assert returncode != 0, output
    assert "[TOOL_MISSING]" in output
    monkeypatch.setenv(_CHECKER_ENV, "cadrumo-import-checker-does-not-exist")
    assert run_import_gate(root) == TOOL_MISSING


def test_abnormal_import_linter_status_is_tool_broken(tmp_path: Path) -> None:
    root = _fixture_root(tmp_path)

    assert run_import_gate(root, lint_executable=sys.executable) == TOOL_BROKEN


def test_import_linter_timeout_is_tool_broken(tmp_path: Path) -> None:
    root = _fixture_root(tmp_path)
    authority = read_authority(root).authority
    assert authority is not None

    component = run_import_linter(authority, executable=sys.executable, timeout=0)

    assert component.returncode == TOOL_BROKEN
    assert "[TOOL_BROKEN]" in component.output


def test_import_linter_exception_is_tool_broken(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = _fixture_root(tmp_path)
    authority = read_authority(root).authority
    assert authority is not None

    def fail(*args: object, **kwargs: object) -> object:
        del args, kwargs
        raise RuntimeError("forced Import Linter failure")

    monkeypatch.setattr("dev.quality.import_gate.subprocess.run", fail)
    component = run_import_linter(authority, executable=sys.executable)

    assert component.returncode == TOOL_BROKEN
    assert "[TOOL_BROKEN]" in component.output


def test_forced_checker_exception_is_nonzero_through_real_recipe(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _fixture_root(tmp_path)
    returncode, output = _run_real_gate(root, **{_FORCE_CHECKER_ENV: "1"})
    assert returncode != 0, output
    assert "[INTERNAL_CHECKER]" in output
    monkeypatch.setenv(_FORCE_CHECKER_ENV, "1")
    assert run_import_gate(root) == TOOL_BROKEN


def test_subordinate_timeout_is_tool_broken(tmp_path: Path) -> None:
    root = _fixture_root(tmp_path)

    authority = read_authority(root).authority
    assert authority is not None

    component, _ = run_subordinate(authority, timeout=0)

    assert component.returncode == TOOL_BROKEN
    assert "[TOOL_BROKEN]" in component.output


def test_component_failures_run_in_authority_then_subordinate_order(tmp_path: Path) -> None:
    root = _fixture_root(tmp_path)
    _write_module(root, "cadrumo.core.consumer", "import cadrumo.domain.module\n")
    _write_module(root, "cadrumo.domain.module", "VALUE = 1\n")
    returncode, output = _run_real_gate(root, **{_LINTER_ENV: "cadrumo-import-linter-does-not-exist"})
    assert returncode != 0, output
    assert "[TOOL_MISSING]" in output
    assert "[ABSOLUTE_INTRA_CADRUMO]" in output
    assert "[SUBORDINATE_CHECKER]" in output
    assert output.index("[GRAPH_AUTHORITY]") < output.index("[SUBORDINATE_CHECKER]")


def test_zero_file_subordinate_scan_is_tool_broken(tmp_path: Path) -> None:
    empty = tmp_path / "empty"
    empty.mkdir()
    authority = Authority(
        repository=tmp_path,
        config_path=tmp_path / ".importlinter",
        parser=configparser.ConfigParser(interpolation=None),
        root_packages=("empty",),
        roots=(RootPackage("empty", empty),),
        classifications=(),
    )
    result = check_authority(authority)
    assert result.returncode == TOOL_BROKEN
    assert any(finding.category == "ZERO_FILES" for finding in result.findings)


def test_warning_and_advisory_native_diagnostics_are_not_clean() -> None:
    assert has_architectural_warning("Warnings:\n- architectural advisory\n")
    assert has_architectural_warning("Warnings: 1\n")
    assert not has_architectural_warning("Warnings: 0\n")
    assert not has_architectural_warning("No warnings were emitted.\n")


def test_zero_status_with_a_native_warning_fails_the_graph_component(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _fixture_root(tmp_path)
    authority = read_authority(root).authority
    assert authority is not None

    def fake_run(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        del args, kwargs
        return subprocess.CompletedProcess([], 0, "Warnings: 1\n", "")

    monkeypatch.setattr("dev.quality.import_gate.subprocess.run", fake_run)

    component = run_import_linter(authority, executable=sys.executable)

    assert component.returncode == 1
    assert "Warnings: 1" in component.output


def test_clean_fixture_has_a_nonzero_governed_scan_and_passes_the_component(tmp_path: Path) -> None:
    root = _fixture_root(tmp_path)
    returncode, output = _run_real_gate(root)
    assert returncode == 0, output
    assert "check-import-boundaries: passed" in output
    assert "governed Python file" not in output

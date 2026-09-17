"""Planted-defect proofs for the single import-quality gate.

Every policy proof below writes only to ``tmp_path`` and invokes the real
``just check-import-boundaries`` recipe.  The temporary authority is copied from the
live ``.importlinter`` file; its roots and layer declarations are materialised
by reading that file, so this test contains no second dependency matrix.
"""

from __future__ import annotations

import configparser
import json
import os
import shutil
import subprocess
import sys
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pytest

from dev._paths import REPO_ROOT, UTF_8
from dev.exit_codes import FAILED, TOOL_BROKEN, TOOL_MISSING
from dev.packaging.command_execution import run_command
from dev.quality.import_checker import (
    Authority,
    RootPackage,
    check_authority,
    has_architectural_warning,
    read_authority,
)
from dev.quality.import_gate import run_import_gate, run_import_linter, run_subordinate
from dev.quality.import_health import build_import_health, module_is_test_scoped, render_import_health
from dev.quality.import_load_probe import main

pytestmark = [pytest.mark.integration, pytest.mark.hex_core]

_IMPORTLINTER_CONFIG = REPO_ROOT / ".importlinter"
_INVENTORY_MODULE = REPO_ROOT / "src" / "cadrumo" / "tests" / "module_target_inventory.py"
_ROOT_ENV = "CADRUMO_IMPORT_GATE_ROOT"
_LINTER_ENV = "CADRUMO_IMPORT_GATE_LINT_IMPORTS"
_CHECKER_ENV = "CADRUMO_IMPORT_GATE_CHECKER"
_FORCE_CHECKER_ENV = "CADRUMO_IMPORT_GATE_FORCE_CHECKER_EXCEPTION"


@pytest.mark.parametrize(
    "module",
    (
        "cadrumo.conftest",
        "cadrumo.application.conftest",
        "cadrumo.adapters.outbound.llm.conftest",
    ),
)
def test_conftest_modules_are_test_scoped(module: str) -> None:
    assert module_is_test_scoped(module)


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

    # The loadability worker reads its finite target set through the audited
    # tree's own inventory loader, as the live repository provides it.
    inventory = tmp_path / "src" / "cadrumo" / "tests" / _INVENTORY_MODULE.name
    inventory.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(_INVENTORY_MODULE, inventory)
    return tmp_path


def _compile_load_targets(root: Path) -> None:
    """Regenerate the fixture's load-target metadata through the probe's owning generator.

    An unreadable authority has no census to compile; those fixtures prove the
    authority refusal itself.
    """
    read = read_authority(root)
    if read.authority is None or read.findings:
        return
    assert main(["--root", str(root), "--compile-targets"]) == 0


def _run_real_gate(root: Path, **updates: str) -> tuple[int, str]:
    """Compile the fixture's load-target metadata, then run the real recipe."""
    _compile_load_targets(root)
    return _run_gate_recipe(root, **updates)


def _run_gate_recipe(root: Path, **updates: str) -> tuple[int, str]:
    """Run the real recipe against ``root`` exactly as the tree stands."""
    environment = os.environ.copy()
    environment[_ROOT_ENV] = str(root)
    environment.update(updates)
    just_executable = shutil.which("just")
    assert just_executable is not None, "the real just driver is required for planted-defect proofs"
    result = run_command(
        [just_executable, "check-import-boundaries"],
        cwd=REPO_ROOT,
        environment=environment,
        errors="replace",
        timeout_seconds=120,
    )
    return result.returncode, (result.stdout + result.stderr)


def _section(payload: dict[str, object], key: str) -> dict[str, object]:
    value = payload[key]
    assert isinstance(value, dict), payload
    return {str(name): item for name, item in value.items()}


def _health_payload(output: str) -> dict[str, object]:
    """Return the gate's machine-readable import_health payload."""
    for line in reversed(output.splitlines()):
        stripped = line.strip()
        if not stripped.startswith("{"):
            continue
        try:
            decoded = json.loads(stripped)
        except json.JSONDecodeError:
            continue
        if isinstance(decoded, dict) and decoded.get("event") == "import_health":
            return {str(key): value for key, value in decoded.items()}
    raise AssertionError(f"the gate emitted no import_health payload:\n{output}")


def _component_block(output: str, label: str) -> str:
    """Return one component's replayed evidence block from the gate output."""
    start = output.find(f"[{label}] exit")
    assert start >= 0, output
    markers = ("[GRAPH_AUTHORITY] exit", "[LOADABILITY] exit", "[SUBORDINATE_CHECKER] exit", "VERDICT:")
    ends = [index for marker in markers if (index := output.find(marker, start + 1)) > start]
    return output[start : min(ends)] if ends else output[start:]


def _assert_blocking_detection(returncode: int, output: str, payload: dict[str, object]) -> None:
    """Require a blocking verdict produced by fully operational components.

    A nonzero exit alone is not detection: a broken probe or setup failure also
    exits nonzero while proving nothing about the planted defect.
    """
    assert returncode == FAILED, output
    assert payload["classification"] == "blocking_findings", output
    graph = _section(payload, "graph_authority")
    assert graph["status"] == "authoritative", output
    assert graph["operational_reasons"] == [], output
    loadability = _section(payload, "loadability")
    assert loadability["status"] in {"loaded", "failed"}, output
    attempted = loadability["attempted"]
    assert isinstance(attempted, int) and attempted > 0, output


def _assert_graph_detection(root: Path, module: str) -> None:
    returncode, output = _run_real_gate(root)
    payload = _health_payload(output)
    _assert_blocking_detection(returncode, output, payload)
    broken = _section(payload, "graph_authority")["contracts_broken"]
    assert isinstance(broken, int) and broken >= 1, output
    assert f"{module} -> " in _component_block(output, "GRAPH_AUTHORITY"), output


def _assert_subordinate_detection(root: Path, category: str) -> None:
    returncode, output = _run_real_gate(root)
    payload = _health_payload(output)
    _assert_blocking_detection(returncode, output, payload)
    by_code = _section(payload, "hard_findings")["by_code"]
    assert isinstance(by_code, dict) and category in by_code, output
    assert f"[{category}]" in _component_block(output, "SUBORDINATE_CHECKER"), output


def _assert_operational_refusal(root: Path, category: str, reason: str) -> None:
    """Require a fail-closed refusal whose operational reason names the specific cause."""
    returncode, output = _run_real_gate(root)
    payload = _health_payload(output)
    assert returncode == TOOL_BROKEN, output
    assert payload["classification"] == "tool_failure", output
    assert f"[{category}]" in output, output
    reasons = _section(payload, "graph_authority")["operational_reasons"]
    assert isinstance(reasons, list) and any(reason in str(item) for item in reasons), output


def _assert_authority_refusal(root: Path, category: str) -> None:
    _assert_operational_refusal(root, category, f"[{category}]")


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
            "source-to-dev-function-local",
            "cadrumo.domain.tests.test_bad",
            "def load():\n    import dev.exit_codes\n\n    return dev.exit_codes\n",
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
            "product-to-harness-package",
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
    _assert_graph_detection(root, module)


def test_undeclared_source_root_fails_authority_preflight(tmp_path: Path) -> None:
    root = _fixture_root(tmp_path)
    _write_package(root, "undeclared_root")
    _assert_authority_refusal(root, "UNCLASSIFIED_ROOT")


def test_undeclared_source_module_fails_authority_preflight(tmp_path: Path) -> None:
    root = _fixture_root(tmp_path)
    (root / "src" / "stray.py").write_text("VALUE = 1\n", encoding=UTF_8, newline="\n")
    _assert_authority_refusal(root, "UNCLASSIFIED_ROOT")


def test_declared_source_module_collision_fails_authority_preflight(tmp_path: Path) -> None:
    root = _fixture_root(tmp_path)
    (root / "src" / "cadrumo.py").write_text("VALUE = 1\n", encoding=UTF_8, newline="\n")
    _assert_authority_refusal(root, "AUTHORITY_CONFIG")


def test_undeclared_source_package_fails_authority_preflight(tmp_path: Path) -> None:
    root = _fixture_root(tmp_path)
    _write_package(root, "cadrumo.unclassified_package")
    _assert_authority_refusal(root, "UNCLASSIFIED_PACKAGE")


def test_authority_must_include_type_checking_edges(tmp_path: Path) -> None:
    root = _fixture_root(tmp_path)
    config = configparser.ConfigParser(interpolation=None)
    config.read(root / ".importlinter", encoding=UTF_8)
    config["importlinter"]["exclude_type_checking_imports"] = "True"
    with (root / ".importlinter").open("w", encoding=UTF_8, newline="\n") as stream:
        config.write(stream)

    _assert_authority_refusal(root, "AUTHORITY_CONFIG")


def test_invalid_authority_config_fails_closed(tmp_path: Path) -> None:
    root = _fixture_root(tmp_path)
    (root / ".importlinter").write_text("[importlinter\n", encoding=UTF_8, newline="\n")
    _assert_authority_refusal(root, "AUTHORITY_CONFIG")


@pytest.mark.parametrize(
    ("name", "module", "source", "target", "category"),
    (
        (
            "static-first-party-target-missing",
            "dev.quality.consumer",
            "import cadrumo.domain.missing\n",
            "",
            "STATIC_TARGET_UNRESOLVED",
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
    _assert_subordinate_detection(root, category)


@pytest.mark.parametrize(
    "source",
    (
        "import cadrumo.domain.module\n",
        "import importlib\nimportlib.import_module('cadrumo.domain.module')\n",
    ),
)
def test_absolute_canonical_import_spelling_is_advisory(tmp_path: Path, source: str) -> None:
    root = _fixture_root(tmp_path)
    _write_module(root, "cadrumo.domain.module", "VALUE = 1\n")
    _write_module(root, "cadrumo.core.consumer", source)

    returncode, output = _run_real_gate(root)

    assert returncode == 0, output
    assert "[ADVISORY:CANONICAL_IMPORT_SPELLING]" in output


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

    _assert_subordinate_detection(root, "PRIVATE_CROSS_PACKAGE")


def test_aliased_dynamic_loader_is_resolved_by_the_subordinate_checker(tmp_path: Path) -> None:
    root = _fixture_root(tmp_path)
    _write_module(
        root,
        "dev.quality.consumer",
        ("from importlib import import_module as load_module\nload_module('cadrumo.domain._private')\n"),
    )
    _write_module(root, "cadrumo.domain._private", "VALUE = 1\n")

    _assert_subordinate_detection(root, "PRIVATE_CROSS_PACKAGE")


def test_module_alias_dynamic_loader_is_resolved_by_the_subordinate_checker(tmp_path: Path) -> None:
    root = _fixture_root(tmp_path)
    _write_module(
        root,
        "dev.quality.consumer",
        ("import importlib as il\nloader = il.import_module\nloader('cadrumo.domain._private')\n"),
    )
    _write_module(root, "cadrumo.domain._private", "VALUE = 1\n")

    _assert_subordinate_detection(root, "PRIVATE_CROSS_PACKAGE")


def test_dotted_dynamic_loader_alias_is_resolved_by_the_subordinate_checker(tmp_path: Path) -> None:
    root = _fixture_root(tmp_path)
    _write_module(
        root,
        "dev.quality.consumer",
        ("import importlib.import_module as loader\nloader('cadrumo.domain._private')\n"),
    )
    _write_module(root, "cadrumo.domain._private", "VALUE = 1\n")

    _assert_subordinate_detection(root, "PRIVATE_CROSS_PACKAGE")


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

    _assert_subordinate_detection(root, "PRIVATE_CROSS_PACKAGE")


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

    _assert_subordinate_detection(root, "UNRESOLVED_DYNAMIC_TARGET")


def test_harness_package_keeps_absolute_product_imports(tmp_path: Path) -> None:
    root = _fixture_root(tmp_path)
    _write_module(
        root,
        "cadrumo_harness.mcp.consumer",
        "from cadrumo.core.module import VALUE\n",
    )
    _write_module(root, "cadrumo.core.module", "VALUE = 1\n")

    returncode, output = _run_real_gate(root)

    assert returncode == 0, output
    assert "CANONICAL_IMPORT_SPELLING" not in output


def test_invalid_utf8_in_governed_file_fails_closed(tmp_path: Path) -> None:
    root = _fixture_root(tmp_path)
    path = root / "src" / "dev" / "quality" / "unreadable.py"
    path.write_bytes(b"\xff\xfe\xfd")
    _assert_operational_refusal(root, "READ_FAILURE", "cannot read governed file")


def test_syntax_failure_in_governed_file_fails_closed(tmp_path: Path) -> None:
    root = _fixture_root(tmp_path)
    _write_module(root, "dev.quality.unparseable", "def broken(:\n")
    _assert_operational_refusal(root, "PARSE_FAILURE", "cannot parse governed file")


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
    _write_module(root, "dev.quality.consumer", "from . import *\n")
    returncode, output = _run_real_gate(root, **{_LINTER_ENV: "cadrumo-import-linter-does-not-exist"})
    assert returncode != 0, output
    assert "[TOOL_MISSING]" in output
    assert "[UNSUPPORTED_IMPORT]" in output
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
    payload = _health_payload(output)
    assert payload["verdict"] == "clean", output
    loadability = _section(payload, "loadability")
    attempted = loadability["attempted"]
    assert isinstance(attempted, int) and attempted > 0, output
    assert loadability["status"] == "loaded", output
    assert loadability["loaded"] == attempted and loadability["failed"] == 0, output


def test_the_isolated_worker_imports_the_audited_tree_rather_than_the_tool_tree(tmp_path: Path) -> None:
    root = _fixture_root(tmp_path)
    # The tool tree defines a module of the same name that loads cleanly; only
    # the audited copy raises, so this failure proves which tree was imported.
    _write_module(root, "cadrumo.core.config", "raise RuntimeError('planted import-time failure')\n")

    returncode, output = _run_real_gate(root)
    payload = _health_payload(output)

    _assert_blocking_detection(returncode, output, payload)
    loadability = _section(payload, "loadability")
    assert loadability["status"] == "failed" and loadability["failed"] == 1, output
    failures = loadability["failure_sample"]
    assert isinstance(failures, list) and len(failures) == 1, output
    failure = failures[0]
    assert isinstance(failure, dict), output
    assert failure["module"] == "cadrumo.core.config", output
    assert failure["error"] == "RuntimeError", output
    assert failure["message"] == "planted import-time failure", output


@pytest.mark.parametrize("metadata", ("missing", "stale"))
def test_a_loadability_setup_failure_is_not_detection_of_a_planted_defect(tmp_path: Path, metadata: str) -> None:
    root = _fixture_root(tmp_path)
    if metadata == "stale":
        _compile_load_targets(root)
    _write_module(root, "cadrumo.domain.module", "VALUE = 1\n")
    _write_module(root, "cadrumo.core.bad", "from ..domain.module import VALUE\n")

    returncode, output = _run_gate_recipe(root)
    payload = _health_payload(output)

    # The planted edge is still reported, so a nonzero-exit oracle would accept this run.
    assert returncode != 0, output
    assert "cadrumo.core.bad -> " in _component_block(output, "GRAPH_AUTHORITY"), output
    assert returncode == TOOL_BROKEN, output
    assert _section(payload, "loadability")["status"] == "unavailable", output
    reasons = _section(payload, "graph_authority")["operational_reasons"]
    expected = "cannot read metadata target inventory" if metadata == "missing" else "is stale"
    assert isinstance(reasons, list) and any(expected in str(item) for item in reasons), output
    with pytest.raises(AssertionError):
        _assert_blocking_detection(returncode, output, payload)


def _approve_occurrences(root: Path, *, target_roots: frozenset[str]) -> int:
    """Write a well-formed ratchet approving every live occurrence into ``target_roots``."""
    authority = read_authority(root).authority
    assert authority is not None
    occurrences = [
        occurrence
        for occurrence in check_authority(authority).occurrences
        if occurrence.target_module.partition(".")[0] in target_roots
    ]
    today = date.today()
    entries = [
        {
            "capability": "fixture-debt",
            "contract": occurrence.contract,
            "created_on": today.isoformat(),
            "expires_on": (today + timedelta(days=30)).isoformat(),
            "fingerprint": occurrence.fingerprint,
            "import_form": occurrence.import_form,
            "imported_symbols": list(occurrence.imported_symbols),
            "lexical_scope": occurrence.lexical_scope,
            "multiplicity": 1,
            "owner": "fixture owner",
            "reason": "fixture approval",
            "source_module": occurrence.source_module,
            "status": "active",
            "target_module": occurrence.target_module,
        }
        for occurrence in occurrences
    ]
    ratchet = root / "dev" / "quality" / "metadata" / "import_boundary_ratchet.json"
    ratchet.parent.mkdir(parents=True, exist_ok=True)
    ratchet.write_text(
        json.dumps({"entries": entries, "schema_version": 1}, indent=2) + "\n",
        encoding=UTF_8,
        newline="\n",
    )
    return len(entries)


def _health_verdict(root: Path) -> tuple[int, str]:
    """Reconcile the real graph and checker evidence for ``root`` against its ratchet."""
    read = read_authority(root)
    assert read.authority is not None and not read.findings, read.findings
    authority = read.authority
    linter = run_import_linter(authority)
    checker = check_authority(authority)
    payload, exit_status = build_import_health(
        authority=authority,
        authority_findings=read.findings,
        linter_returncode=linter.returncode,
        linter_output=linter.output,
        checker=checker,
        loadability={"attempted": 0, "failed": 0, "loaded": 0, "root_cause_count": 0, "scope": "fixture"},
        load_returncode=0,
        source_snapshot_before="fixture",
        source_snapshot_after="fixture",
        component_durations={},
    )
    return exit_status, render_import_health(payload) + "\n" + json.dumps(payload, sort_keys=True)


def _ratchet_report(output: str) -> tuple[dict[str, object], dict[str, object]]:
    """Return the ratchet counts and details from a ``_health_verdict`` rendering."""
    payload = json.loads(output.rsplit("\n", 1)[1])
    assert isinstance(payload, dict), output
    ratchet = payload["ratchet"]
    assert isinstance(ratchet, dict), output
    counts = ratchet["counts"]
    details = ratchet["details"]
    assert isinstance(counts, dict) and isinstance(details, dict), output
    return {str(key): value for key, value in counts.items()}, {str(key): value for key, value in details.items()}


def _module_path(root: Path, dotted: str) -> Path:
    parts = dotted.split(".")
    return root / "src" / Path(*parts[:-1]) / f"{parts[-1]}.py"


def _retire_as_source_removed(root: Path) -> None:
    """Mark every fixture ratchet entry retired because its source module was deleted."""
    ratchet = root / "dev" / "quality" / "metadata" / "import_boundary_ratchet.json"
    document = json.loads(ratchet.read_text(encoding=UTF_8))
    for entry in document["entries"]:
        entry["status"] = "retired"
        entry["retirement"] = {"kind": "source_module_removed", "verified_at": datetime.now(tz=UTC).isoformat()}
    ratchet.write_text(json.dumps(document, indent=2) + "\n", encoding=UTF_8, newline="\n")


def test_a_ratchet_entry_retires_without_composition_evidence_once_its_source_module_is_deleted(
    tmp_path: Path,
) -> None:
    root = _fixture_root(tmp_path)
    source = "cadrumo.domain.tests.test_layer_debt"
    _write_module(root, "cadrumo.application.module", "VALUE = 1\n")
    _write_module(root, source, "from ...application.module import VALUE\n")
    assert _approve_occurrences(root, target_roots=frozenset({"cadrumo"})) == 1
    _module_path(root, source).unlink()

    exit_status, output = _health_verdict(root)
    counts, details = _ratchet_report(output)
    assert exit_status == 1, output
    assert counts["retirement_candidates"] == 1, output
    assert details["source_module_removed"] == details["retirement_candidates"], output

    _retire_as_source_removed(root)
    exit_status, output = _health_verdict(root)
    counts, _ = _ratchet_report(output)
    assert exit_status == 0, output
    assert "VERDICT: clean" in output
    assert "Retired with removed source module: 1 occurrence(s)" in output
    assert counts["retired_source_removed"] == 1, output
    assert counts["retired_verified"] == 0 and counts["malformed"] == 0, output


def test_a_source_removed_retirement_cannot_hide_a_present_source_or_a_renamed_violation(tmp_path: Path) -> None:
    root = _fixture_root(tmp_path)
    source = "cadrumo.domain.tests.test_layer_debt"
    _write_module(root, "cadrumo.application.module", "VALUE = 1\n")
    _write_module(root, source, "from ...application.module import VALUE\n")
    assert _approve_occurrences(root, target_roots=frozenset({"cadrumo"})) == 1
    _retire_as_source_removed(root)

    exit_status, output = _health_verdict(root)
    counts, _ = _ratchet_report(output)
    assert exit_status == 1, output
    assert counts["regressed_retired"] == 1 and counts["retired_source_removed"] == 0, output

    _write_module(root, source, "VALUE = 2\n")
    exit_status, output = _health_verdict(root)
    counts, details = _ratchet_report(output)
    assert exit_status == 1, output
    assert counts["malformed"] == 1 and counts["retired_source_removed"] == 0, output
    malformed = details["malformed"]
    assert isinstance(malformed, list), output
    assert any(f"{source} was removed, but it still exists" in str(item) for item in malformed), output

    _module_path(root, source).unlink()
    _write_module(root, "cadrumo.domain.tests.test_layer_debt_renamed", "from ...application.module import VALUE\n")
    exit_status, output = _health_verdict(root)
    counts, _ = _ratchet_report(output)
    assert exit_status == 1, output
    assert counts["retired_source_removed"] == 1 and counts["new_unapproved"] == 1, output


def test_a_ratchet_cannot_approve_a_shipped_test_module_reaching_a_repository_only_root(tmp_path: Path) -> None:
    root = _fixture_root(tmp_path)
    _write_module(root, "cadrumo.application.module", "VALUE = 1\n")
    _write_module(root, "cadrumo.domain.tests.test_layer_debt", "from ...application.module import VALUE\n")

    assert _approve_occurrences(root, target_roots=frozenset({"cadrumo"})) == 1
    exit_status, output = _health_verdict(root)
    assert exit_status == 0, output
    assert "VERDICT: passing_with_debt" in output
    assert "Repository-only reach (not ratchetable): 0 occurrence(s)" in output

    _write_module(root, "cadrumo.domain.tests.test_repository_reach", "import dev.exit_codes\n")
    repository_reach = _approve_occurrences(root, target_roots=frozenset({"cadrumo", "dev"})) - 1
    assert repository_reach >= 1
    exit_status, output = _health_verdict(root)
    assert exit_status == 1, output
    assert f"Repository-only reach (not ratchetable): {repository_reach} occurrence(s)" in output
    assert "Approved debt: 1 occurrence(s)" in output
    assert "src/cadrumo/domain/tests/test_repository_reach.py:1 imports dev.exit_codes" in output
    assert "a shipped root reaching a repository-only root is not debt" in output


def test_a_dynamic_shipped_import_of_a_repository_only_root_fails_the_verdict(tmp_path: Path) -> None:
    root = _fixture_root(tmp_path)
    _write_module(
        root,
        "cadrumo.domain.tests.test_dynamic_reach",
        'import importlib\n\nimportlib.import_module("dev.exit_codes")\n',
    )

    exit_status, output = _health_verdict(root)

    assert exit_status == 1, output
    assert "Repository-only reach (not ratchetable): 1 occurrence(s)" in output
    assert "src/cadrumo/domain/tests/test_dynamic_reach.py:3 imports dev.exit_codes" in output

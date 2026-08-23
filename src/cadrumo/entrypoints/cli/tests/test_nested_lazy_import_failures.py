"""Real-import failure contracts for nested lazy groups and leaves.

The loader kernel is exercised in fresh interpreters against modules written to
an isolated temporary package.  That gives each case Python's real import
semantics (including syntax compilation and transitive lookup) without replacing
``import_module`` or a command resolver with a test double.
"""

from __future__ import annotations

import json
import subprocess
import sys
import textwrap
from pathlib import Path
from typing import cast

import pytest

from ....core.errors import ErrorCategory, get_error_exit_code
from ....core.i18n import SUPPORTED_OUTPUT_LANGUAGES
from ._command_group_import_support import (
    AFFECTED_GROUP,
    EXPECTED_ERROR_CODE,
    REQUIRED_DEPENDENCY,
    run_cli_with_blocked_package,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


_PROBE = textwrap.dedent(
    r"""
    import json
    import sys
    import typer

    from cadrumo.entrypoints.cli._command_suggestions import (
        CadrumoTyperGroup,
        LazyImportTarget,
        LazySubcommand,
        register_lazy_subcommand,
        resolve_command_path,
    )
    from typer._click.core import Context
    from typer.main import get_command
    from typer.testing import CliRunner

    package_root, target_module, declared_optional, action, target_position = sys.argv[1:]
    sys.path.insert(0, package_root)

    class RequiredUnavailable(RuntimeError):
        pass

    required_calls = []
    optional_calls = []

    def required(name, error):
        required_calls.append((name, error.name))
        raise RequiredUnavailable(f"required:{name}:{error.name}") from error

    def optional(name, error):
        optional_calls.append((name, error.name))
        unavailable = typer.Typer(name=name, invoke_without_command=True)

        @unavailable.callback()
        def refuse():
            typer.echo(f"explicit-unavailable:{name}:{error.name}")
            raise typer.Exit(23)

        return unavailable

    root = typer.Typer(name="s12-root", cls=CadrumoTyperGroup)

    @root.callback()
    def root_callback():
        pass

    parent = LazySubcommand(
        "parent",
        LazyImportTarget(
            target_module if target_position == "group" else "s12probe.parent",
            optional_dependencies=frozenset(filter(None, [declared_optional]))
            if target_position == "group"
            else frozenset(),
        ),
        child_registry_key="s12-parent",
        optional_unavailable=optional if target_position == "group" else None,
        required_unavailable=required if target_position == "group" else None,
        help="Parent metadata help.",
    )
    register_lazy_subcommand(
        "s12-root",
        parent,
    )
    selected = LazySubcommand(
        "selected",
        LazyImportTarget(
            target_module,
            optional_dependencies=frozenset(filter(None, [declared_optional])),
        ),
        optional_unavailable=optional,
        required_unavailable=required,
        help="Selected metadata help.",
    )
    register_lazy_subcommand("s12-parent", selected)
    register_lazy_subcommand(
        "s12-parent",
        LazySubcommand("sibling", LazyImportTarget("s12probe.sibling"), help="Sibling metadata help."),
    )

    result = {}
    try:
        if action == "root-help":
            command = get_command(root)
            ctx = Context(command, info_name="s12-root")
            command.get_help(ctx)
            ctx.close()
        elif action == "parent-help":
            command = get_command(root)
            root_ctx = Context(command, info_name="s12-root")
            parent = command.get_command(root_ctx, "parent")
            root_ctx.close()
            parent_ctx = Context(parent, info_name="parent")
            parent.get_help(parent_ctx)
            parent_ctx.close()
        elif action == "parent-completion":
            command = get_command(root)
            root_ctx = Context(command, info_name="s12-root")
            parent = command.get_command(root_ctx, "parent")
            root_ctx.close()
            parent_ctx = Context(parent, info_name="parent")
            result["completion"] = [item.value for item in parent.shell_complete(parent_ctx, "sel")]
            parent_ctx.close()
        elif action == "resolve":
            path = ("parent",) if target_position == "group" else ("parent", "selected")
            command = resolve_command_path(root, path)
            result["resolved"] = command.name
        elif action == "dispatch":
            path = ["parent"] if target_position == "group" else ["parent", "selected"]
            invoked = CliRunner().invoke(root, path)
            result.update(exit_code=invoked.exit_code, output=invoked.output)
            if invoked.exception is not None:
                result["invocation_exception"] = type(invoked.exception).__name__
        elif action == "repeat":
            failures = []
            for _ in range(2):
                try:
                    (parent if target_position == "group" else selected).load()
                except BaseException as error:
                    failures.append(
                        {
                            "type": type(error).__name__,
                            "cause_type": type(error.__cause__).__name__ if error.__cause__ else None,
                            "cause_name": getattr(error.__cause__, "name", None),
                        }
                    )
            result["failures"] = failures
        elif action == "repeat-optional":
            subject = parent if target_position == "group" else selected
            first = subject.load()
            second = subject.load()
            result["same"] = first is second
        else:
            raise AssertionError(action)
    except BaseException as error:
        result.update(
            error_type=type(error).__name__,
            error_name=getattr(error, "name", None),
            cause_type=type(error.__cause__).__name__ if error.__cause__ else None,
            cause_name=getattr(error.__cause__, "name", None),
            error_text=str(error),
        )

    result.update(
        parent_imported="s12probe.parent" in sys.modules,
        target_imported=target_module in sys.modules,
        sibling_imported="s12probe.sibling" in sys.modules,
        required_calls=required_calls,
        optional_calls=optional_calls,
        materialized=(parent if target_position == "group" else selected).is_materialized,
    )
    print(json.dumps(result, sort_keys=True))
    """
)

_OPTIONAL_LOCALE_PROBE = textwrap.dedent(
    r"""
    import json
    import os
    import sys
    import tempfile
    from pathlib import Path

    locale = sys.argv[1]
    os.environ["CADRUMO_OUTPUT_LANGUAGE"] = locale

    from typer.testing import CliRunner
    import typer
    from cadrumo.entrypoints.cli import _optional_import_surface, _required_import_failure
    from cadrumo.entrypoints.cli._command_suggestions import (
        CadrumoTyperGroup,
        LazyImportTarget,
        LazySubcommand,
        register_lazy_subcommand,
    )
    from cadrumo.entrypoints.cli._errors import decorate_typer_app

    root_dir = Path(tempfile.mkdtemp(prefix="s12-optional-locale-"))
    (root_dir / "s12_optional_locale_target.py").write_text("import playwright\n", encoding="utf-8")
    sys.path.insert(0, str(root_dir))

    class _BlockedPlaywright:
        def find_spec(self, fullname, path=None, target=None):
            if fullname.split(".")[0] == "playwright":
                raise ModuleNotFoundError(f"No module named {fullname!r}", name=fullname)
            return None

    sys.meta_path.insert(0, _BlockedPlaywright())
    surface = typer.Typer(name="s12-locale-root", cls=CadrumoTyperGroup)

    @surface.callback()
    def root_callback():
        pass

    register_lazy_subcommand(
        "s12-locale-root",
        LazySubcommand(
            "live",
            LazyImportTarget("s12_optional_locale_target", optional_dependencies=frozenset({"playwright"})),
            decorate=decorate_typer_app,
            optional_unavailable=_optional_import_surface,
            required_unavailable=_required_import_failure,
            help="Live feature metadata.",
        ),
    )
    help_result = CliRunner().invoke(surface, ["live", "--help"])
    dispatch_result = CliRunner().invoke(surface, ["live"])
    print(json.dumps({
        "help_exit": help_result.exit_code,
        "help": help_result.output,
        "dispatch_exit": dispatch_result.exit_code,
        "dispatch": dispatch_result.output,
    }))
    """
)


def _write_probe_package(root: Path, target_source: str) -> str:
    package = root / "s12probe"
    package.mkdir()
    (package / "__init__.py").write_text("", encoding="utf-8")
    (package / "parent.py").write_text(
        textwrap.dedent(
            """
            import typer
            from cadrumo.entrypoints.cli._command_suggestions import CadrumoTyperGroup
            app = typer.Typer(name="parent", cls=CadrumoTyperGroup)

            @app.callback()
            def parent_callback():
                pass
            """
        ),
        encoding="utf-8",
    )
    (package / "sibling.py").write_text("raise AssertionError('sibling imported')\n", encoding="utf-8")
    (package / "target.py").write_text(textwrap.dedent(target_source), encoding="utf-8")
    return "s12probe.target"


def _run_probe(
    tmp_path: Path,
    *,
    target_source: str,
    action: str,
    declared_optional: str = "",
    target_position: str = "leaf",
) -> dict[str, object]:
    target = _write_probe_package(tmp_path, target_source)
    completed = subprocess.run(  # noqa: S603 - trusted interpreter and fixed probe source
        [sys.executable, "-c", _PROBE, str(tmp_path), target, declared_optional, action, target_position],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=60,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    parsed = json.loads(completed.stdout.strip().splitlines()[-1])
    assert isinstance(parsed, dict)
    assert all(isinstance(key, str) for key in parsed)
    return cast(dict[str, object], parsed)


@pytest.mark.parametrize("action", ["root-help", "parent-help", "parent-completion"])
def test_help_and_completion_do_not_import_nested_leaf_or_sibling(tmp_path: Path, action: str) -> None:
    result = _run_probe(
        tmp_path,
        target_source="raise AssertionError('selected leaf imported')\n",
        action=action,
    )

    assert result["target_imported"] is False
    assert result["sibling_imported"] is False
    assert result["materialized"] is False
    if action == "root-help":
        assert result["parent_imported"] is False
    else:
        assert result["parent_imported"] is True
    if action == "parent-completion":
        assert result["completion"] == ["selected"]


@pytest.mark.parametrize(("target_position", "node_name"), [("group", "parent"), ("leaf", "selected")])
def test_exact_declared_optional_failure_resolves_and_dispatches_explicit_surface(
    tmp_path: Path,
    target_position: str,
    node_name: str,
) -> None:
    result = _run_probe(
        tmp_path,
        target_source="import s12_declared_optional_dependency\n",
        declared_optional="s12_declared_optional_dependency",
        action="dispatch",
        target_position=target_position,
    )

    assert result["exit_code"] == 23
    assert result["output"] == f"explicit-unavailable:{node_name}:s12_declared_optional_dependency\n"
    assert result["optional_calls"] == [[node_name, "s12_declared_optional_dependency"]]
    assert result["required_calls"] == []
    assert result["sibling_imported"] is False
    assert result["materialized"] is True
    assert "No such command" not in str(result["output"])


@pytest.mark.parametrize(
    ("target_source", "expected_type", "expected_name"),
    [
        (
            "import s12_unclassified_required_dependency\n",
            "RequiredUnavailable",
            "s12_unclassified_required_dependency",
        ),
        ("raise ImportError('non-module import defect')\n", "ImportError", None),
        ("raise RuntimeError('module initialisation defect')\n", "RuntimeError", None),
        ("def broken(:\n    pass\n", "SyntaxError", None),
    ],
)
@pytest.mark.parametrize("target_position", ["group", "leaf"])
def test_internal_transitive_and_non_module_import_defects_fail_loudly(
    tmp_path: Path,
    target_source: str,
    expected_type: str,
    expected_name: str | None,
    target_position: str,
) -> None:
    result = _run_probe(
        tmp_path,
        target_source=target_source,
        declared_optional="s12_declared_optional_dependency",
        action="resolve",
        target_position=target_position,
    )

    assert result["error_type"] == expected_type
    assert result["sibling_imported"] is False
    assert result["materialized"] is False
    assert "unknown CLI path" not in str(result["error_text"])
    if expected_type == "RequiredUnavailable":
        assert result["cause_type"] == "ModuleNotFoundError"
        assert result["cause_name"] == expected_name
        assert result["optional_calls"] == []


@pytest.mark.parametrize(("target_position", "node_name"), [("group", "parent"), ("leaf", "selected")])
def test_same_namespace_internal_miss_is_not_the_exact_declared_dependency(
    tmp_path: Path,
    target_position: str,
    node_name: str,
) -> None:
    dependency = tmp_path / "s12_declared_optional_dependency"
    dependency.mkdir()
    (dependency / "__init__.py").write_text("", encoding="utf-8")
    result = _run_probe(
        tmp_path,
        target_source="import s12_declared_optional_dependency.broken_internal\n",
        declared_optional="s12_declared_optional_dependency",
        action="resolve",
        target_position=target_position,
    )

    assert result["error_type"] == "RequiredUnavailable"
    assert result["cause_name"] == "s12_declared_optional_dependency.broken_internal"
    assert result["optional_calls"] == []
    assert result["required_calls"] == [[node_name, "s12_declared_optional_dependency.broken_internal"]]


@pytest.mark.parametrize(("target_position", "node_name"), [("group", "parent"), ("leaf", "selected")])
def test_missing_transitive_dependency_inside_declared_optional_fails_loudly(
    tmp_path: Path,
    target_position: str,
    node_name: str,
) -> None:
    dependency = tmp_path / "s12_declared_optional_dependency"
    dependency.mkdir()
    (dependency / "__init__.py").write_text("import s12_absent_transitive_dependency\n", encoding="utf-8")
    result = _run_probe(
        tmp_path,
        target_source="import s12_declared_optional_dependency\n",
        declared_optional="s12_declared_optional_dependency",
        action="resolve",
        target_position=target_position,
    )

    assert result["error_type"] == "RequiredUnavailable"
    assert result["cause_type"] == "ModuleNotFoundError"
    assert result["cause_name"] == "s12_absent_transitive_dependency"
    assert result["optional_calls"] == []
    assert result["required_calls"] == [[node_name, "s12_absent_transitive_dependency"]]
    assert result["materialized"] is False


@pytest.mark.parametrize(("target_position", "node_name"), [("group", "parent"), ("leaf", "selected")])
def test_required_failure_is_retried_and_each_refusal_preserves_original_cause(
    tmp_path: Path,
    target_position: str,
    node_name: str,
) -> None:
    result = _run_probe(
        tmp_path,
        target_source="import s12_required_dependency\n",
        action="repeat",
        target_position=target_position,
    )

    assert result["failures"] == [
        {"cause_name": "s12_required_dependency", "cause_type": "ModuleNotFoundError", "type": "RequiredUnavailable"},
        {"cause_name": "s12_required_dependency", "cause_type": "ModuleNotFoundError", "type": "RequiredUnavailable"},
    ]
    assert result["required_calls"] == [
        [node_name, "s12_required_dependency"],
        [node_name, "s12_required_dependency"],
    ]
    assert result["materialized"] is False


@pytest.mark.parametrize(("target_position", "node_name"), [("group", "parent"), ("leaf", "selected")])
def test_optional_unavailable_surface_is_cached_after_first_classification(
    tmp_path: Path,
    target_position: str,
    node_name: str,
) -> None:
    result = _run_probe(
        tmp_path,
        target_source="import s12_declared_optional_dependency\n",
        declared_optional="s12_declared_optional_dependency",
        action="repeat-optional",
        target_position=target_position,
    )

    assert result["same"] is True
    assert result["optional_calls"] == [[node_name, "s12_declared_optional_dependency"]]
    assert result["materialized"] is True


@pytest.mark.parametrize("locale", SUPPORTED_OUTPUT_LANGUAGES)
def test_required_nested_import_failure_keeps_localized_json_envelope(locale: str) -> None:
    completed = run_cli_with_blocked_package(
        REQUIRED_DEPENDENCY,
        ["--language", locale, "--format", "json", "app", AFFECTED_GROUP, "--help"],
        language=locale,
    )

    assert completed.returncode == get_error_exit_code(ErrorCategory.FAIL)
    document = json.loads(completed.stderr.strip().splitlines()[-1])
    assert document["status"] == "error"
    assert document["error"]["code"] == EXPECTED_ERROR_CODE
    assert document["error"]["context"] == {"group": AFFECTED_GROUP, "module": REQUIRED_DEPENDENCY}
    assert document["error"]["message"]
    assert "errors.fail.fail_cli_command_group_unavailable" not in document["error"]["message"]
    assert "No such command" not in completed.stderr
    assert "Traceback" not in completed.stderr


@pytest.mark.parametrize("locale", SUPPORTED_OUTPUT_LANGUAGES)
def test_exact_optional_failure_renders_localized_explicit_unavailable_surface(locale: str) -> None:
    completed = subprocess.run(  # noqa: S603 - trusted interpreter and fixed probe source
        [sys.executable, "-c", _OPTIONAL_LOCALE_PROBE, locale],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=60,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    result = json.loads(completed.stdout.strip().splitlines()[-1])

    assert result["help_exit"] == 0
    assert result["dispatch_exit"] == get_error_exit_code(ErrorCategory.ERROR)
    assert "cli.root.unavailable_optional_extra_help" not in result["help"]
    assert "errors.optional_extra_required" not in result["dispatch"]
    assert "browser" in result["help"]
    assert "browser" in result["dispatch"]
    assert "No such command" not in result["dispatch"]

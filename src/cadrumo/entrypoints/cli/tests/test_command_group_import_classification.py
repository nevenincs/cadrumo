"""Guards for how a command group's lazy import failure is classified.

Every heavy command group imports lazily, the first time an operator dispatches
into its subtree, so the loader is the one place that decides how an import
failure is reported. It has exactly two honest answers, and conflating them is
the regression these tests exist to prevent:

* A missing **optional extra** is a configuration choice a bare install makes.
  The subtree degrades to a placeholder whose help names the extra and whose
  refusal carries the ``pip install cadrumo[<extra>]`` remedy.
* A missing **required dependency** is a broken installation. It MUST refuse
  loudly during command resolution, naming the module and the reinstall remedy.

Degrading the second case is a silent-degradation defect, not a cosmetic one.
It happened: ``textual`` became a required dependency while a stale environment
lacked it, and the whole ``app modelo`` subtree answered ``--help`` with a
plausible "not available in the current configuration" placeholder and every
subcommand with "no such command". The dependency failure was invisible for a
day because nothing on the operator-facing surface named a cause.

The end-to-end coverage runs in a fresh interpreter with a real
:mod:`importlib` meta-path finder that refuses the blocked package, so the
module is genuinely unimportable exactly as it would be on an incomplete
install — the production condition, not a simulation of it. A subprocess is
required because the blocked package must be unimportable *before* the command
module is first imported, and the in-process test session has already imported
it.

Assertions are structural throughout — registered error code, category, exit
code, and context keys — never the localised prose, which is free to change.
"""

from __future__ import annotations

import json
import subprocess
import sys
import textwrap
from importlib.metadata import requires

import pytest
from typer.testing import CliRunner

from ....core import OPTIONAL_EXTRAS, optional_extra_for_module
from ....core.errors import ErrorCategory, get_error_exit_code, get_registered_error_code
from ....core.redaction import CLI_PROFILE_ID_PLACEHOLDER
from .. import _surface_for_import_failure
from .._errors import CliCommandGroupUnavailableError, decorate_typer_app

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

#: The end-to-end guards spawn the real entry point in a fresh interpreter;
#: the classification guards exercise pure in-process logic.
_END_TO_END = pytest.mark.integration
_CLASSIFICATION = pytest.mark.unit

#: A required ``[project]`` dependency that the ``app modelo`` subtree imports
#: transitively. This is the exact package whose absence produced the silent
#: degradation the module docstring describes.
_REQUIRED_DEPENDENCY = "textual"

#: The command group whose subtree imports :data:`_REQUIRED_DEPENDENCY`.
_AFFECTED_GROUP = "modelo"

_EXPECTED_ERROR_CODE = "FAIL_CLI_COMMAND_GROUP_UNAVAILABLE"


def _run_cli_with_blocked_package(package: str, argv: list[str]) -> subprocess.CompletedProcess[str]:
    """Run the real ``aeat`` entry point with ``package`` made unimportable.

    The meta-path finder is installed before :mod:`cadrumo.entrypoints.cli` is
    imported, so the blocked package is absent for the whole run — the same
    state an incomplete install presents. It raises rather than returning
    ``None`` so a deep ``from package import name`` fails identically to a
    genuinely absent distribution.
    """
    code = textwrap.dedent(
        f"""
        import os, sys
        os.environ["CADRUMO_OUTPUT_LANGUAGE"] = "en"

        class _Blocked:
            def find_spec(self, fullname, path=None, target=None):
                if fullname.split(".")[0] == {package!r}:
                    raise ModuleNotFoundError(f"No module named {{fullname!r}}", name=fullname)
                return None

        sys.meta_path.insert(0, _Blocked())
        sys.argv = ["aeat", *{argv!r}]
        from cadrumo.entrypoints.cli import main
        main()
        """,
    )
    return subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        # The CLI forces UTF-8 stdio; the default locale decoder is cp1252 on
        # Windows and chokes on an accented refusal from the child process.
        encoding="utf-8",
        errors="replace",
        timeout=180,
        check=False,
    )


@_END_TO_END
def test_missing_required_dependency_refuses_instead_of_degrading() -> None:
    """A required dependency's absence refuses loudly, naming module and remedy.

    This is the regression gate for the silent degradation. Before the fix this
    invocation exited 0 and printed a subcommand-less help page; the group had
    quietly lost all 23 of its subcommands while reporting nothing wrong.
    """
    completed = _run_cli_with_blocked_package(
        _REQUIRED_DEPENDENCY,
        ["--format", "json", "app", _AFFECTED_GROUP, "--help"],
    )

    assert completed.returncode == get_error_exit_code(ErrorCategory.FAIL), (
        f"expected the FAIL exit code, got {completed.returncode}: {completed.stdout}{completed.stderr}"
    )
    document = json.loads(completed.stderr.strip().splitlines()[-1])
    error = document["error"]
    assert error["code"] == _EXPECTED_ERROR_CODE
    assert error["category"] == ErrorCategory.FAIL.value
    # The refusal must name the actual failure and an actionable remedy.
    assert error["context"]["module"] == _REQUIRED_DEPENDENCY
    assert error["context"]["group"] == _AFFECTED_GROUP
    assert error["suggestion"], "a required-dependency refusal must carry a remedy"
    # The failure rides the shared envelope spine, not a bespoke channel.
    assert document["status"] == "error"
    assert document["notices"] == []


@_END_TO_END
def test_missing_required_dependency_does_not_render_a_placeholder_group() -> None:
    """The degraded surface is gone: no subcommand-less group help is rendered.

    Complements the JSON gate above by covering the plain-text surface an
    operator actually sees, and by asserting the *absence* of the specific shape
    that made the defect invisible — a successful help render for a group whose
    subcommand list has silently emptied.
    """
    completed = _run_cli_with_blocked_package(_REQUIRED_DEPENDENCY, ["app", _AFFECTED_GROUP, "--help"])

    assert completed.returncode != 0, completed.stdout
    assert "Usage: aeat app modelo" not in completed.stdout
    assert _REQUIRED_DEPENDENCY in completed.stderr
    assert "Traceback" not in completed.stderr, completed.stderr


@_CLASSIFICATION
def test_missing_required_dependency_raises_the_typed_refusal() -> None:
    """The loader's classifier raises the typed refusal for a required module.

    Exercises the classification seam directly with a real
    :exc:`ModuleNotFoundError`, so the raised type, its registered code, and its
    structured attributes are pinned independently of any rendering.
    """
    error = ModuleNotFoundError(f"No module named {_REQUIRED_DEPENDENCY!r}", name=_REQUIRED_DEPENDENCY)

    with pytest.raises(CliCommandGroupUnavailableError) as raised:
        _surface_for_import_failure(_AFFECTED_GROUP, error)

    refusal = raised.value
    assert refusal.module == _REQUIRED_DEPENDENCY
    assert refusal.group == _AFFECTED_GROUP
    assert refusal.__cause__ is error, "the refusal must preserve the underlying import failure"
    code = get_registered_error_code(refusal)
    assert code.code == _EXPECTED_ERROR_CODE
    assert code.category is ErrorCategory.FAIL


@_END_TO_END
def test_missing_optional_extra_still_degrades_gracefully() -> None:
    """A registered optional extra keeps its graceful placeholder surface.

    The legitimate half of the distinction. A bare install omits these packages
    by design, so the subtree must stay resolvable, render help, and refuse with
    the install hint rather than crashing the CLI.
    """
    extra = next(candidate for candidate in OPTIONAL_EXTRAS if candidate.extra == "browser")
    error = ModuleNotFoundError(f"No module named {extra.import_name!r}", name=extra.import_name)

    surface = _surface_for_import_failure("live", error)
    decorate_typer_app(surface)

    help_result = CliRunner().invoke(surface, ["--help"])
    assert help_result.exit_code == 0, help_result.output

    refusal = CliRunner().invoke(surface, [])
    assert refusal.exit_code == get_error_exit_code(ErrorCategory.ERROR), refusal.output
    # The refusal names the exact install command, never a bare "unavailable".
    assert extra.install_hint in refusal.output


@_CLASSIFICATION
def test_optional_extra_classification_covers_every_registered_extra() -> None:
    """Each registered extra owns its import name and that name's submodules."""
    for extra in OPTIONAL_EXTRAS:
        assert optional_extra_for_module(extra.import_name) is extra
        assert optional_extra_for_module(f"{extra.import_name}.deep.submodule") is extra


@_CLASSIFICATION
def test_required_dependencies_never_classify_as_optional_extras() -> None:
    """No declared core requirement is claimed by the optional-extra registry.

    Derived from the installed distribution's own metadata rather than a
    hand-kept list, so a package promoted from an extra into ``[project]``
    dependencies without updating the registry fails here instead of silently
    re-enabling the graceful-degradation path for a required package.
    """
    declared = requires("cadrumo") or []
    core_requirements = [requirement for requirement in declared if "extra ==" not in requirement]
    assert core_requirements, "the distribution must declare core requirements"

    misclassified = {
        name: owner.extra
        for requirement in core_requirements
        if (name := _distribution_name(requirement)) and (owner := optional_extra_for_module(name)) is not None
    }
    assert misclassified == {}, f"required dependencies classified as optional extras: {misclassified}"

    # The package whose absence caused the incident, pinned explicitly: its
    # distribution and import names coincide, so this is an exact check.
    assert optional_extra_for_module(_REQUIRED_DEPENDENCY) is None


@_CLASSIFICATION
def test_unknown_module_classifies_as_a_required_failure() -> None:
    """An unrecognised module is treated as required, never silently degraded.

    Fail-closed is the load-bearing property: a module the registry cannot
    account for — a first-party module, a typo, a transitive dependency — must
    refuse rather than degrade, because only a *declared* optional extra is
    legitimately absent.
    """
    assert optional_extra_for_module("cadrumo.adapters.inbound.tui") is None
    assert optional_extra_for_module("some_unlisted_package") is None
    assert optional_extra_for_module("") is None


@_CLASSIFICATION
def test_required_dependency_refusal_redacts_a_sensitive_module_name() -> None:
    """A module name carrying a profile id is redacted in the refusal.

    Classification reads the raw name; only the operator-facing value is
    redacted, so a sensitive identifier cannot ride out through the refusal.
    """
    profile_id = "123e4567-e89b-12d3-a456-426614174000"
    error = ModuleNotFoundError(f"No module named {profile_id!r}", name=profile_id)

    with pytest.raises(CliCommandGroupUnavailableError) as raised:
        _surface_for_import_failure(_AFFECTED_GROUP, error)

    assert profile_id not in raised.value.module
    assert CLI_PROFILE_ID_PLACEHOLDER in raised.value.module


def _distribution_name(requirement: str) -> str:
    """Return the bare distribution name from a PEP 508 requirement string."""
    for separator in (";", "[", "=", "<", ">", "!", "~", " ", "("):
        requirement = requirement.split(separator, 1)[0]
    return requirement.strip()

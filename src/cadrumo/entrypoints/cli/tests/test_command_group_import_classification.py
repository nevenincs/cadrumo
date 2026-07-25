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

This module owns the classification seam itself — pure in-process logic over a
real :exc:`ModuleNotFoundError`, so the raised type, its registered code, and
its structured attributes are pinned independently of any rendering. The
rendered operator surface is guarded from the integration lane by
``test_command_group_import_failure_surface``; both modules share their
vocabulary through :mod:`._command_group_import_support`.

Assertions are structural throughout — registered error code, category, exit
code, and context keys — never the localised prose, which is free to change.
"""

from __future__ import annotations

from importlib.metadata import requires

import pytest

from ....core import OPTIONAL_EXTRAS, optional_extra_for_module
from ....core.errors import ErrorCategory, get_registered_error_code
from ....core.redaction import CLI_PROFILE_ID_PLACEHOLDER
from .. import _surface_for_import_failure
from .._errors import CliCommandGroupUnavailableError
from ._command_group_import_support import AFFECTED_GROUP, EXPECTED_ERROR_CODE, REQUIRED_DEPENDENCY

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def test_missing_required_dependency_raises_the_typed_refusal() -> None:
    """The loader's classifier raises the typed refusal for a required module.

    Exercises the classification seam directly with a real
    :exc:`ModuleNotFoundError`, so the raised type, its registered code, and its
    structured attributes are pinned independently of any rendering.
    """
    error = ModuleNotFoundError(f"No module named {REQUIRED_DEPENDENCY!r}", name=REQUIRED_DEPENDENCY)

    with pytest.raises(CliCommandGroupUnavailableError) as raised:
        _surface_for_import_failure(AFFECTED_GROUP, error)

    refusal = raised.value
    assert refusal.module == REQUIRED_DEPENDENCY
    assert refusal.group == AFFECTED_GROUP
    assert refusal.__cause__ is error, "the refusal must preserve the underlying import failure"
    code = get_registered_error_code(refusal)
    assert code.code == EXPECTED_ERROR_CODE
    assert code.category is ErrorCategory.FAIL


def test_optional_extra_classification_covers_every_registered_extra() -> None:
    """Each registered extra owns its import name and that name's submodules."""
    for extra in OPTIONAL_EXTRAS:
        assert optional_extra_for_module(extra.import_name) is extra
        assert optional_extra_for_module(f"{extra.import_name}.deep.submodule") is extra


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
    assert optional_extra_for_module(REQUIRED_DEPENDENCY) is None


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


def test_required_dependency_refusal_redacts_a_sensitive_module_name() -> None:
    """A module name carrying a profile id is redacted in the refusal.

    Classification reads the raw name; only the operator-facing value is
    redacted, so a sensitive identifier cannot ride out through the refusal.
    """
    profile_id = "123e4567-e89b-12d3-a456-426614174000"
    error = ModuleNotFoundError(f"No module named {profile_id!r}", name=profile_id)

    with pytest.raises(CliCommandGroupUnavailableError) as raised:
        _surface_for_import_failure(AFFECTED_GROUP, error)

    assert profile_id not in raised.value.module
    assert CLI_PROFILE_ID_PLACEHOLDER in raised.value.module


def _distribution_name(requirement: str) -> str:
    """Return the bare distribution name from a PEP 508 requirement string."""
    for separator in (";", "[", "=", "<", ">", "!", "~", " ", "("):
        requirement = requirement.split(separator, 1)[0]
    return requirement.strip()

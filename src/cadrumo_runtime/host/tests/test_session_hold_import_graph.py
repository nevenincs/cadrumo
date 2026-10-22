"""The desktop's session hold imports only what connecting and holding need.

A window starts one `session hold` child before the person has signed in,
and every exchange the window makes with the runtime goes through it. The
child once imported the profile-view model graph, the profile mutation
contracts and the credential custody stack before it could connect: about
370 Cadrumo modules, paid by the person waiting at the sign-in form. The
hold now imports the transport, the wire contracts and its own relay; the
view and mutation models load on the first language read or write.

This gate pins that PROPERTY: the module graph the hold holds once its entry
module is imported. It asserts no wall-clock budget, which would be flaky on
a contended machine and fail for reasons unrelated to the graph.
"""

from __future__ import annotations

import importlib
import json
import sys

import pytest

from cadrumo.tests.audited_process import run_audited_process

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_HOLD_MODULE = "cadrumo_runtime.host.session_hold"

_FORBIDDEN_AT_IMPORT: tuple[str, ...] = (
    # The profile-view operation and the health graph it binds its status to.
    "cadrumo.application.user_profile.view_operation",
    "cadrumo.application.workflow.profile_health",
    "cadrumo.domain.deadlines.profiles",
    # The profile mutation contracts and the setup-answer vocabulary.
    "cadrumo.application.user_profile.profile_operation_contracts",
    "cadrumo.domain.user_profile.setup_answers",
    # The credential custody stack that only an enrollment needs.
    "cadrumo_client.transport.enrollment_client",
    "cadrumo.adapters.persistence.storage.custody.automation_client_credentials",
    "cadrumo.adapters.persistence.storage.crypto.aead",
    "cryptography",
    # The pinned tax authority and the operation graph.
    "cadrumo.domain.calculations.registry.authority",
    "cadrumo.application.operations.composition",
    "cadrumo.entrypoints.operation_composition",
)

# The import graph is about 510 modules where the eager hold held about 715.
# The ceiling leaves room for small protocol growth and fails on a subtree.
_IMPORT_MODULE_CEILING = 570


def _imported_modules(prelude: str = "") -> frozenset[str]:
    """Import the hold's entry module in a fresh interpreter and report its module graph.

    A real isolated subprocess, because the desktop launches the hold that way
    and it is the only clean module table. ``prelude`` runs first so a caller
    can prove the gate still bites.
    """
    source = f"{prelude}\nimport {_HOLD_MODULE}\nimport json, sys\nprint(json.dumps(sorted(sys.modules)))"
    completed = run_audited_process(
        [sys.executable, "-I", "-B", "-c", source],
        capture_output=True,
        text=True,
        check=True,
    )
    names = json.loads(completed.stdout)
    assert isinstance(names, list), "the hold child must print a JSON list of module names"
    assert all(isinstance(name, str) for name in names), "module names must be strings"
    return frozenset(str(name) for name in names)


def test_an_imported_hold_excludes_the_view_mutation_and_custody_graphs() -> None:
    """Connecting imports no profile-view model, mutation contract, custody stack or authority."""
    modules = _imported_modules()

    assert _HOLD_MODULE in modules, (
        f"the child did not import {_HOLD_MODULE}; the probe observed nothing, "
        "so the exclusions below would pass vacuously"
    )
    present = sorted(target for target in _FORBIDDEN_AT_IMPORT if target in modules)
    assert present == [], (
        f"the session hold imported {present} before connecting. Every window starts this "
        "process while the person signs in, so an eager import on its path is paid by the "
        "person waiting. Import it inside the request that uses it."
    )
    assert len(modules) <= _IMPORT_MODULE_CEILING, (
        f"the session hold holds {len(modules)} modules at import, above {_IMPORT_MODULE_CEILING}; "
        "find the subtree that joined its startup path"
    )


@pytest.mark.parametrize(
    "prelude_target",
    ["cadrumo.application.user_profile.view_operation", "cadrumo_client.transport.enrollment_client"],
)
def test_the_exclusion_probe_bites(prelude_target: str) -> None:
    """A heavy import re-added ahead of the hold is reported by the exclusion check.

    The prelude stands in for a hold module that imports the target again,
    which is the regression this gate exists to catch.
    """
    modules = _imported_modules(prelude=f"import {prelude_target}")

    assert prelude_target in modules
    assert any(target in modules for target in _FORBIDDEN_AT_IMPORT)


def test_every_forbidden_target_still_resolves() -> None:
    """A renamed module is absent from every graph, which would retire its entry silently."""
    unresolvable: list[str] = []
    for target in _FORBIDDEN_AT_IMPORT:
        try:
            importlib.import_module(target)
        except ImportError:
            unresolvable.append(target)

    assert not unresolvable, (
        f"these forbidden import targets no longer resolve: {unresolvable}. Re-point each "
        "at the module that now owns the subsystem, or drop it deliberately."
    )

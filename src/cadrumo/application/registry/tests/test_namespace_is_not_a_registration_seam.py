"""The Modelo 100 cross-domain gate does not depend on this namespace.

This package root once ran ``import_module("cadrumo.domain.renta")`` at
module scope so the renta first-slice routing cross-domain snapshot check
would be registered before anything built a Modelo 100 snapshot. The
registration is the snapshot builder's job now: it imports the registering
module by name at the start of every build, so no composition root has to
import a peer domain for the gate to run.

Both tests run in fresh interpreters. An in-process test cannot make either
claim: by the time pytest reaches this module it has already imported this
namespace and, through some sibling, most of the tree, so the module-level
registration list reflects the session rather than the import path under
test.
"""

from __future__ import annotations

import subprocess
import sys
import textwrap

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_CHECK_MODULE = "cadrumo.domain.renta.first_slice_routing_integrity"


def _run_python(script: str) -> subprocess.CompletedProcess[str]:
    """Run a dedented ``script`` in a fresh interpreter."""

    return subprocess.run(
        [sys.executable, "-c", textwrap.dedent(script)],
        capture_output=True,
        text=True,
        timeout=300,
    )


def test_m100_gate_runs_without_this_namespace_ever_being_imported() -> None:
    """An M100 build registers and arms the renta gate on its own.

    The subprocess never imports this package. It confirms the registration
    list is empty and the check module unloaded up front, builds the
    committed Modelo 100 snapshot, and then interrogates the callable the
    registry ended up holding: it must come from the renta check module, it
    must return no failures for the revision it just validated, and it must
    return failures when the casillas its routing targets name are taken
    away. Registration without teeth would satisfy the first claim alone.
    """

    result = _run_python(
        f"""
        import sys

        from cadrumo.domain.calculations.registry.authority import bundled_authority
        from cadrumo.domain.calculations.registry.ledger_renta_gastos_estimacion_directa_bindings import renta_first_slice_binding_target_casillas
        from cadrumo.domain.calculations.registry.validate_cross_domain_snapshot import (
            _CROSS_DOMAIN_SNAPSHOT_CHECKS,
        )

        assert "cadrumo.application.registry" not in sys.modules, (
            "this interpreter must reach the snapshot build without the namespace"
        )
        assert "{_CHECK_MODULE}" not in sys.modules, (
            "the renta check module must not be loaded before the build"
        )
        assert _CROSS_DOMAIN_SNAPSHOT_CHECKS == [], (
            "no cross-domain check may be registered before the build"
        )

        snapshot = bundled_authority().snapshot("100", filing_year=2025, period="0A")
        assert snapshot.modelo.id == "100"
        assert "cadrumo.application.registry" not in sys.modules, (
            "building the snapshot must not pull in the namespace either"
        )

        registered = {{
            (check.__module__, check.__name__): check for check in _CROSS_DOMAIN_SNAPSHOT_CHECKS
        }}
        key = ("{_CHECK_MODULE}", "check_first_slice_routing")
        assert key in registered, (
            "the renta first-slice routing check must be registered by the build; "
            f"registered={{sorted(registered)}}"
        )
        check = registered[key]

        targets = renta_first_slice_binding_target_casillas(snapshot.revision)
        assert targets, (
            "the committed modelo 100 revision must declare first-slice binding "
            "targets, or the failure case below asserts nothing"
        )
        casilla_ids = frozenset(casilla.id for casilla in snapshot.revision.casillas)
        binding_ids = frozenset(binding.id for binding in snapshot.revision.bindings)

        assert check("100", casilla_ids, targets, binding_ids) == [], (
            "the registered check must pass against the revision it just validated"
        )
        assert check("100", frozenset(), targets, binding_ids), (
            "the registered check must report failures when its routing targets "
            "are absent from the revision"
        )

        print("M100_FIRST_SLICE_GATE_LIVE")
        """,
    )

    assert result.returncode == 0, f"subprocess failed:\nstdout={result.stdout}\nstderr={result.stderr}"
    assert "M100_FIRST_SLICE_GATE_LIVE" in result.stdout, result.stdout


def test_importing_this_namespace_registers_nothing() -> None:
    """The namespace root is inert: importing it has no registration effect.

    The complement of the test above, and what keeps the deleted
    ``import_module`` deleted. A re-introduced peer-domain import at module
    scope would load a renta module here and, if it registered, populate the
    cross-domain list -- both of which this asserts against.
    """

    result = _run_python(
        """
        import sys

        import cadrumo.application.registry as namespace

        from cadrumo.domain.calculations.registry.validate_cross_domain_snapshot import (
            _CROSS_DOMAIN_SNAPSHOT_CHECKS,
        )

        assert namespace.__all__ == (), namespace.__all__
        renta_modules = sorted(name for name in sys.modules if name.startswith("cadrumo.domain.renta"))
        assert renta_modules == [], (
            f"importing the namespace must load no renta module, got {renta_modules}"
        )
        assert _CROSS_DOMAIN_SNAPSHOT_CHECKS == [], (
            "importing the namespace must register no cross-domain check"
        )

        print("NAMESPACE_REGISTERS_NOTHING")
        """,
    )

    assert result.returncode == 0, f"subprocess failed:\nstdout={result.stdout}\nstderr={result.stderr}"
    assert "NAMESPACE_REGISTERS_NOTHING" in result.stdout, result.stdout

"""The M130 retenciones gate registers from the module that performs it.

The retenciones-a-cuenta routing check used to reach the registry only
because ``application.aggregation`` imported its module for two constants it
needed anyway. That is registration by coincidence: a process that never
touches aggregation validated an M130 snapshot with the gate absent, and
nothing said so. The registry now declares the module that performs the
registration and the snapshot builder imports it by name, the same shape the
Modelo 100 gate uses.

These tests run in fresh interpreters. In a pytest session the registration
list is already populated by siblings, and ``application.aggregation`` is
already imported, so an in-process assertion would pass whether or not the
registry declared anything at all.

The refusal test sets the DECLARED peer-module tuple before building. That
is the one deliberate lever, and it is disclosed rather than left to read as
an ordinary fixture: in a process that installs the declared modules the
required check is always registered, so no other route reaches the state.
Nothing is faked by it -- the real installer imports a real module and the
real guard judges the real registration list.
"""

from __future__ import annotations

import subprocess
import sys
import textwrap

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_RETENCIONES_MODULE = "cadrumo.domain.renta.retenciones_routing_integrity"
_FIRST_SLICE_MODULE = "cadrumo.domain.renta.first_slice_routing_integrity"


def _run_python(script: str) -> subprocess.CompletedProcess[str]:
    """Run a dedented ``script`` in a fresh interpreter."""

    return subprocess.run(
        [sys.executable, "-c", textwrap.dedent(script)],
        capture_output=True,
        text=True,
        timeout=300,
    )


def test_m130_gate_registers_and_bites_without_aggregation_imported() -> None:
    """Building M130 arms the retenciones gate on a path that never sees aggregation.

    The subprocess confirms the check module is unloaded and nothing is
    registered, builds the committed M130 snapshot, and then interrogates the
    callable the registry holds: it must come from the retenciones module,
    pass against the revision it just validated, and report a failure when
    the output casilla its binding redirects onto is taken away. The
    constants come from the module under test rather than from literals
    copied into this file, so a renumbered casilla moves both together.
    """

    result = _run_python(
        f"""
        import sys

        from cadrumo.domain.calculations.registry.authority import bundled_authority
        from cadrumo.domain.calculations.registry.validate_cross_domain_snapshot import (
            _CROSS_DOMAIN_SNAPSHOT_CHECKS,
        )

        assert not [name for name in sys.modules if name.startswith("cadrumo.application.aggregation")], (
            "this interpreter must reach the snapshot build without aggregation"
        )
        assert "{_RETENCIONES_MODULE}" not in sys.modules, (
            "the retenciones check module must not be loaded before the build"
        )
        assert _CROSS_DOMAIN_SNAPSHOT_CHECKS == [], (
            "no cross-domain check may be registered before the build"
        )

        snapshot = bundled_authority().snapshot("130", filing_year=2025, period="1T")
        assert snapshot.modelo.id == "130"
        assert not [name for name in sys.modules if name.startswith("cadrumo.application.aggregation")], (
            "building the snapshot must not pull in aggregation either"
        )

        registered = {{
            (check.__module__, check.__name__): check for check in _CROSS_DOMAIN_SNAPSHOT_CHECKS
        }}
        key = ("{_RETENCIONES_MODULE}", "check_m130_retenciones_output_casilla")
        assert key in registered, (
            "the M130 retenciones routing check must be registered by the build; "
            f"registered={{sorted(registered)}}"
        )
        check = registered[key]

        from cadrumo.domain.renta.retenciones_routing_integrity import (
            RENTA_130_RETENCIONES_BINDING_ID,
            RENTA_130_RETENCIONES_OUTPUT_CASILLA,
        )

        casilla_ids = frozenset(casilla.id for casilla in snapshot.revision.casillas)
        binding_ids = frozenset(binding.id for binding in snapshot.revision.bindings)
        assert RENTA_130_RETENCIONES_BINDING_ID in binding_ids, (
            "the committed M130 revision must declare the retenciones binding, or "
            "the failure case below asserts nothing"
        )
        assert RENTA_130_RETENCIONES_OUTPUT_CASILLA in casilla_ids

        assert check("130", casilla_ids, frozenset(), binding_ids) == [], (
            "the registered check must pass against the revision it just validated"
        )
        stripped = casilla_ids - {{RENTA_130_RETENCIONES_OUTPUT_CASILLA}}
        assert check("130", stripped, frozenset(), binding_ids), (
            "the registered check must report a failure when the casilla its "
            "binding redirects onto is absent from the revision"
        )

        print("M130_RETENCIONES_GATE_LIVE")
        """,
    )

    assert result.returncode == 0, f"subprocess failed:\nstdout={result.stdout}\nstderr={result.stderr}"
    assert "M130_RETENCIONES_GATE_LIVE" in result.stdout, result.stdout


def test_m130_refuses_when_only_the_m100_gate_is_registered() -> None:
    """M130's requirement is its own, and the M100 gate does not stand in for it.

    Declaring only the first-slice module leaves the registration list
    non-empty with a real renta check that has no claim over M130 routing --
    the same shape that let the M100 requirement pass silently. The build
    must refuse and name the retenciones module.
    """

    result = _run_python(
        f"""
        import cadrumo.domain.calculations.registry._snapshot_internals as internals

        internals._CROSS_DOMAIN_CHECK_MODULES = ({_FIRST_SLICE_MODULE!r},)

        from cadrumo.domain.calculations.registry.authority import bundled_authority
        from cadrumo.domain.calculations.registry.errors import RegistryValidationError

        try:
            bundled_authority().snapshot("130", filing_year=2025, period="1T")
        except RegistryValidationError as error:
            print("REFUSED")
            print(error)
        else:
            print("BUILT")
        """,
    )

    assert result.returncode == 0, f"subprocess failed:\nstdout={result.stdout}\nstderr={result.stderr}"
    assert "REFUSED" in result.stdout, f"M130 built without its required gate:\n{result.stdout}"
    assert _RETENCIONES_MODULE in result.stdout, result.stdout

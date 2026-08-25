"""The Modelo 100 cross-domain snapshot gate registers deterministically.

The registry validator runs peer-domain referential-integrity checks
through the abstract ``CrossDomainSnapshotCheck`` Protocol. The concrete
renta first-slice routing check lives in
``cadrumo.domain.renta._first_slice_routing_integrity`` and registers itself
as an import side effect.

That registration must NOT depend on import order. ``_build_validated_snapshot``
calls ``_install_cross_domain_snapshot_checks`` before the referential-
integrity gate runs; the installer imports every peer-domain check module
named in ``_CROSS_DOMAIN_CHECK_MODULES`` by name. The registry never
imports ``renta`` statically (that would reverse the dependency direction
the cross-domain dependency fix, defect F7) -- it owns only the list of peer
module names. A Modelo 100 snapshot therefore validates the BOE-prescribed
first-slice routing gate regardless of whether the importing process ever
imported ``cadrumo.domain.renta`` first.

These tests run in fresh subprocesses so the registry's module-level
``_CROSS_DOMAIN_SNAPSHOT_CHECKS`` list reflects exactly the import path
under test -- a guarantee no in-process test can give once any sibling
test in the session has populated that list.
"""

from __future__ import annotations

import subprocess
import sys
import textwrap

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _run_python(*fragments: str) -> subprocess.CompletedProcess[str]:
    """Run dedented ``fragments`` in a fresh interpreter as one script.

    Each fragment is dedented independently so fragments authored at
    different indentation levels compose into one valid top-level
    script.
    """

    source = "\n".join(textwrap.dedent(fragment) for fragment in fragments)
    return subprocess.run(
        [sys.executable, "-c", source],
        capture_output=True,
        text=True,
        timeout=300,
    )


def test_m100_build_on_renta_free_import_path_registers_the_gate() -> None:
    """An M100 build registers the renta gate without ``renta`` pre-imported.

    The subprocess imports only the registry -- it never imports
    ``cadrumo.domain.renta`` itself -- and confirms zero cross-domain checks
    are registered up front. Building a Modelo 100 snapshot then runs
    ``_install_cross_domain_snapshot_checks`` during snapshot construction,
    which imports the peer-domain check module by name. The build must
    succeed with the renta first-slice routing check registered, proving
    the registration is import-order-independent rather than a side effect
    of some upstream ``import cadrumo.domain.renta``.
    """

    result = _run_python(
        """
        import sys

        from cadrumo.core.resources import resources
        from cadrumo.domain.calculations.registry.validate_references import _CROSS_DOMAIN_SNAPSHOT_CHECKS

        assert "cadrumo.domain.renta" not in sys.modules, (
            "renta must not be imported before the snapshot build on this path"
        )
        assert _CROSS_DOMAIN_SNAPSHOT_CHECKS == [], (
            "no cross-domain checks must be registered before the snapshot build"
        )

        snapshot = resources().modelos.authority.snapshot("100", filing_year=2025, period="0A")
        assert snapshot.modelo.id == "100"
        assert _CROSS_DOMAIN_SNAPSHOT_CHECKS, (
            "building an M100 snapshot must register the renta first-slice "
            "routing cross-domain check"
        )
        print("M100_GATE_REGISTERED")
        """,
    )

    assert result.returncode == 0, f"subprocess failed:\nstdout={result.stdout}\nstderr={result.stderr}"
    assert "M100_GATE_REGISTERED" in result.stdout, result.stdout


def test_m100_build_succeeds_when_renta_is_imported() -> None:
    """Importing ``renta`` registers the check; the M100 build then passes.

    Companion to the loud-failure case: it proves the guard is satisfied
    by the registration side effect rather than by a blanket refusal to
    build M100. The subprocess imports ``cadrumo.domain.renta`` before
    building, so the first-slice routing check is registered and the
    committed M100 snapshot passes the referential-integrity gate.
    """

    result = _run_python(
        """
        import cadrumo.domain.renta  # noqa: F401  -- registration side effect

        from cadrumo.core.resources import resources
        from cadrumo.domain.calculations.registry.validate_references import _CROSS_DOMAIN_SNAPSHOT_CHECKS

        assert _CROSS_DOMAIN_SNAPSHOT_CHECKS, (
            "importing renta must register at least one cross-domain check"
        )

        snapshot = resources().modelos.authority.snapshot("100", filing_year=2025, period="0A")
        assert snapshot.modelo.id == "100"
        print("M100_BUILD_OK")
        """,
    )

    assert result.returncode == 0, f"subprocess failed:\nstdout={result.stdout}\nstderr={result.stderr}"
    assert "M100_BUILD_OK" in result.stdout, result.stdout


def test_non_m100_build_on_renta_free_path_does_not_require_the_gate() -> None:
    """A non-M100 snapshot built without ``renta`` must not be blocked.

    The loud-failure guard is scoped to Modelo 100 -- the only modelo with
    a known-required renta cross-domain gate. A non-100 modelo (here
    Modelo 303) built on a renta-free import path must pass the
    referential-integrity gate without the cross-domain registration
    requirement firing.
    """

    result = _run_python(
        """
        import sys

        from cadrumo.core.resources import resources
        from cadrumo.domain.calculations.registry.validate_references import _CROSS_DOMAIN_SNAPSHOT_CHECKS

        assert "cadrumo.domain.renta" not in sys.modules, (
            "renta must not be imported on this path"
        )
        assert _CROSS_DOMAIN_SNAPSHOT_CHECKS == [], (
            "no cross-domain checks must be registered without renta imported"
        )

        snapshot = resources().modelos.authority.snapshot("303", filing_year=2025, period="1T")
        assert snapshot.modelo.id == "303"
        print("M303_BUILD_OK")
        """,
    )

    assert result.returncode == 0, f"subprocess failed:\nstdout={result.stdout}\nstderr={result.stderr}"
    assert "M303_BUILD_OK" in result.stdout, result.stdout

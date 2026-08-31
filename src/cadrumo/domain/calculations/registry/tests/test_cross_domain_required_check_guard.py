"""Modelo 100 refuses unless the check it names is the one registered.

The snapshot builder installs the peer-domain check modules the registry
declares, and the referential-integrity guard then refuses an M100 snapshot
whose required cross-domain gate is missing. Asking only whether ANY check
is registered is not that question: a process that has imported
``application.aggregation`` registers the M130 retenciones check, so the
list is non-empty, the guard is satisfied, and the first-slice routing gate
the guard's own message names can be absent with nothing raising.

Each test runs in a fresh interpreter and sets the DECLARED peer-module
tuple before building -- the same declaration a change to the renta package
would alter, and the only lever that reaches this state, because in a
process that installs the declared module the required check is always
registered. Nothing is faked: the real installer imports the real module it
is told to, and the real guard judges the real registration list.
"""

from __future__ import annotations

import subprocess
import sys
import textwrap

import pytest

from .._snapshot_internals import _CROSS_DOMAIN_CHECK_MODULES
from ..validate_cross_domain_snapshot import (
    _CROSS_DOMAIN_CHECK_IDENTITIES,
    _CROSS_DOMAIN_SNAPSHOT_CHECKS,
    REQUIRED_CROSS_DOMAIN_CHECK_IDENTITIES,
    missing_required_cross_domain_check,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_REQUIRED_MODULE = "cadrumo.domain.renta.first_slice_routing_integrity"
_OTHER_MODULE = "cadrumo.domain.renta._retenciones_routing_integrity"


def _build_m100_with_declared_modules(declared: str) -> subprocess.CompletedProcess[str]:
    """Build the committed M100 snapshot with ``declared`` peer modules installed."""

    script = f"""
        import cadrumo.domain.calculations.registry._snapshot_internals as internals

        internals._CROSS_DOMAIN_CHECK_MODULES = {declared}

        from cadrumo.domain.calculations.registry.authority import bundled_authority
        from cadrumo.domain.calculations.registry.errors import RegistryValidationError
        from cadrumo.domain.calculations.registry.validate_cross_domain_snapshot import (
            _CROSS_DOMAIN_SNAPSHOT_CHECKS,
        )

        try:
            bundled_authority().snapshot("100", filing_year=2025, period="0A")
        except RegistryValidationError as error:
            registered = sorted(check.__module__ for check in _CROSS_DOMAIN_SNAPSHOT_CHECKS)
            print("REFUSED", registered)
            print(error)
        else:
            registered = sorted(check.__module__ for check in _CROSS_DOMAIN_SNAPSHOT_CHECKS)
            print("BUILT", registered)
        """
    return subprocess.run(
        [sys.executable, "-c", textwrap.dedent(script)],
        capture_output=True,
        text=True,
        timeout=300,
    )


def test_m100_refuses_when_a_different_peer_check_is_registered() -> None:
    """A non-empty registration list must not satisfy the M100 requirement.

    The declared peer module is the M130 retenciones check, so the build
    reaches the guard with exactly one registered check -- a real one, from
    the renta domain, that has no claim over first-slice routing. The guard
    must refuse and name the check it actually requires.
    """

    result = _build_m100_with_declared_modules(f"({_OTHER_MODULE!r},)")

    assert result.returncode == 0, f"subprocess failed:\nstdout={result.stdout}\nstderr={result.stderr}"
    assert "REFUSED" in result.stdout, (
        f"the guard accepted an M100 snapshot without its required check:\n{result.stdout}"
    )
    assert _OTHER_MODULE in result.stdout, result.stdout
    assert _REQUIRED_MODULE in result.stdout, f"the refusal must name the required check module:\n{result.stdout}"


def test_m100_still_refuses_loudly_when_nothing_is_registered() -> None:
    """The empty-registration case keeps its own distinct refusal.

    Narrowing the guard to a named check must not lose the case where no
    peer-domain check was registered at all: that is a different failure
    with a different cause, and its message says so.
    """

    result = _build_m100_with_declared_modules("()")

    assert result.returncode == 0, f"subprocess failed:\nstdout={result.stdout}\nstderr={result.stderr}"
    assert "REFUSED []" in result.stdout, (
        f"an M100 build with no cross-domain check registered must refuse:\n{result.stdout}"
    )
    assert "no cross-domain checks" in result.stdout, result.stdout


def test_m100_builds_when_the_required_check_is_registered() -> None:
    """The committed declaration satisfies the requirement it declares.

    The complement of both refusals, and what keeps the narrowed guard from
    being a blanket M100 refusal: with the real declared module installed,
    the committed snapshot builds.
    """

    result = _build_m100_with_declared_modules(f"({_REQUIRED_MODULE!r},)")

    assert result.returncode == 0, f"subprocess failed:\nstdout={result.stdout}\nstderr={result.stderr}"
    assert "BUILT" in result.stdout, result.stdout
    assert _REQUIRED_MODULE in result.stdout, result.stdout


def test_a_foreign_check_does_not_satisfy_the_m100_requirement() -> None:
    """The decision itself, over the exact state that used to pass silently.

    The registered identity is the real M130 retenciones check module -- a
    genuine peer-domain gate with no claim over first-slice routing. A
    population test reads this state as satisfied; the requirement names what
    is missing.
    """

    missing = missing_required_cross_domain_check("100", {_OTHER_MODULE})

    assert missing == _REQUIRED_MODULE


def test_the_required_identity_satisfies_the_m100_requirement() -> None:
    """The required owner being registered is what clears the requirement."""

    assert missing_required_cross_domain_check("100", {_REQUIRED_MODULE}) is None


def test_a_modelo_with_no_declared_requirement_is_never_gated() -> None:
    """Only a modelo that declares a required check may be refused for one.

    Modelo 303 declares none, so an empty registration set must not refuse it
    -- the guard has no claim there, and one that reddened anyway would train
    its readers to work around it.
    """

    assert "303" not in REQUIRED_CROSS_DOMAIN_CHECK_IDENTITIES
    assert missing_required_cross_domain_check("303", frozenset()) is None


def test_every_required_check_module_is_one_the_builder_installs() -> None:
    """The requirement and the install list are the same set.

    They are derived from one declaration, and this asserts the property that
    derivation exists to hold: a required check the builder never imports
    would refuse every build of its modelo, and an installed module nothing
    requires would be dead capacity.
    """

    assert set(REQUIRED_CROSS_DOMAIN_CHECK_IDENTITIES.values()) == set(_CROSS_DOMAIN_CHECK_MODULES)


def test_the_identity_index_and_the_check_list_hold_the_same_checks() -> None:
    """One writer records both, so they may never disagree.

    The guard reads identities while every other consumer reads the list; a
    check present in one and absent from the other would make the guard judge
    a different population than the one that runs.
    """

    indexed = [check for checks in _CROSS_DOMAIN_CHECK_IDENTITIES.values() for check in checks]

    assert len(indexed) == len(_CROSS_DOMAIN_SNAPSHOT_CHECKS)
    assert {id(check) for check in indexed} == {id(check) for check in _CROSS_DOMAIN_SNAPSHOT_CHECKS}
    for identity, checks in _CROSS_DOMAIN_CHECK_IDENTITIES.items():
        for check in checks:
            assert check.__module__ == identity

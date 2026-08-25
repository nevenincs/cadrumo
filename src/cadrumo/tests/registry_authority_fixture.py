"""Canonical bundled-registry-authority fixture for tests in both trees."""

from __future__ import annotations

from collections.abc import Callable

import pytest

from cadrumo.domain.calculations.registry.authority import ValidatedRegistryAuthority, bundled_authority


def bundled_registry_authority_fixture(*, name: str) -> Callable[[], ValidatedRegistryAuthority]:
    """Build a fixture handing back the bundled :class:`ValidatedRegistryAuthority`.

    The same one-line body was written under two names in two trees, which a
    name-keyed reading of the suite reports as two fixtures and a body-keyed
    one reports as a single behaviour aliased twice. Only the body is shared
    here: ``name`` stays per-caller, so each module still declares the name
    its own request sites use.

    The scope is fixed at ``module`` rather than offered as an argument
    because all three callers want module scope, and a scope passed in as a
    variable is a value no static reading of the suite can resolve -- the
    fixture census refuses such a fixture outright rather than guess. A
    caller that genuinely needs another scope adds the argument then, and
    settles how the census should read it at the same time.

    Sharing the body claims no saving in load time and none should be read
    into it. Every route to the bundled authority -- this one,
    ``resources().modelos.authority``, and a direct ``bundled_authority()``
    call -- resolves through one memo keyed on the registry and
    source-evidence fingerprints, so the second and later calls in a process
    hand back the identical object (measured at 0.03s against 30s for the
    first). What this consolidates is the number of places the behaviour is
    spelled, not the number of times it runs.

    Args:
        name: The fixture name pytest discovers, matching the caller's
            request sites.

    Returns:
        A fixture function to bind at module level under ``name``.
    """

    @pytest.fixture(name=name, scope="module")
    def _bundled_registry_authority() -> ValidatedRegistryAuthority:
        return bundled_authority()

    return _bundled_registry_authority


__all__ = ["bundled_registry_authority_fixture"]

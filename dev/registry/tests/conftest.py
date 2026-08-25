"""Shared fixtures for development registry tests."""

import pytest

from cadrumo.core.resources import resources
from cadrumo.domain.calculations.registry.authority import bundled_revision_inspection


@pytest.fixture(scope="session")
def registry_authority():
    """The session registry authority, as the src-tree conftest provides it.

    `test_the_static_closure_matches_what_a_real_load_imports` confronts the
    import graph's closure with what a REAL load leaves in `sys.modules`, so it
    needs an authority that has actually loaded. The fixture it asks for is
    defined in the registry package's own conftest, which pytest never applies
    to this directory -- collection here errored on the missing name instead of
    running the check. Same object, same session scope.
    """
    return resources().modelos.authority


@pytest.fixture
def m200_inspection_snapshot():
    return bundled_revision_inspection("200", filing_year=2025, period="0A")


@pytest.fixture
def m130_inspection_snapshot():
    """A real revision authority that declares NO projection endpoint.

    Modelo 200 gained 578 projection declarations, and semantic-map validation
    checks a map against them as a bijection, so a synthetic map can no longer
    be validated against it except to test that very bijection.
    """
    return bundled_revision_inspection("130", filing_year=2026, period="1T")

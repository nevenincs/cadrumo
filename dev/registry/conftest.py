"""Pytest controls for the development registry compiler.

The mutable registry compiler has process-local loader and fingerprint caches.
Their session boundary belongs to this development-only tree: shipped Cadrumo
tests consume the published authority and must not import the authoring
compiler merely to clear its caches.

This tree is also the registry family's TEST HOST, and a host composes the
outward ports the code under test resolves. ``compose_runtime_ports`` is
session-scoped and AUTOUSE, and an autouse fixture reaches only the tests
inside its own directory tree - so it covers ``src/cadrumo`` and nothing else.
A registry test that drives a real application service therefore ran against an
uncomposed host: ``aggregate_renta_ledger_expenses`` reads the profile record
for its seguro-de-enfermedad person counts, that reaches
``profile_login_session_port()``, and an unbound port is an
``InternalInvariantError`` rather than an absent profile. Refusing is correct -
collapsing "no infrastructure" into "no profile" would let a miscomposed host
file a total with silently zeroed person counts - so the host is what has to
change, not the refusal.

The fixture is IMPORTED rather than reimplemented, exactly as
``dev/ci/tests/conftest.py`` imports it for the same reason: a second copy
would restate the shipped composition in a place that cannot notice when it
changes. Binding it into this module's namespace is what makes it visible to
pytest here; a ``pytest_plugins`` declaration outside the root conftest is
refused at collection.
"""

from collections.abc import Iterator

import pytest

from cadrumo import conftest as runtime_conftest

compose_runtime_ports = runtime_conftest.compose_runtime_ports


@pytest.fixture(scope="session", autouse=True)
def _isolate_registry_caches() -> Iterator[None]:
    """Clear development compiler caches at each pytest session boundary."""
    from .compiler.loader import load_registry_tree_cached
    from .compiler.loader_fingerprints import clear_fingerprint_cache

    def _reset() -> None:
        load_registry_tree_cached.cache_clear()
        clear_fingerprint_cache()

    _reset()
    yield
    _reset()


@pytest.fixture
def authored_history_fact_scope() -> Iterator[None]:
    """Scope governed facts against the AUTHORED history rather than the filing span."""
    from cadrumo.domain.calculations.registry.governed_fact_scope import validating_governed_facts

    from .tests.profile_schema_support import authored_history_authority

    with validating_governed_facts(authored_history_authority()):
        yield


@pytest.fixture
def governed_fact_scope() -> Iterator[None]:
    """Resolve registry tokens in one requesting test against the compiled authored facts.

    Governed-fact resolvers refuse to run without an explicit authority scope.
    Only a test whose body constructs registry-validated values requests this
    fixture, and the scope ends with that test, so no other test inherits it.
    """
    from cadrumo.domain.calculations.registry.governed_fact_scope import validating_governed_facts

    from .compiler.authority import compiled_bundled_authority

    with validating_governed_facts(compiled_bundled_authority()):
        yield

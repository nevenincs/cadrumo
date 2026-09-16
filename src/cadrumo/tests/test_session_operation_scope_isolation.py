"""The session authority lease scopes only the tests that ask for it.

A lease entered in the session's own context would stay in scope for every
later test in the worker, so a test that never took a lease would pass or fail
by the order it happened to run in. The cases below run in file order on one
worker: the first requests the session operation, the ones after it do not.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from ..domain.calculations.registry.authority import PinnedAuthorityOperation
from ..domain.calculations.registry.governed_fact_scope import governed_facts_in_scope

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


@pytest.fixture
def through_a_fixture(operation: PinnedAuthorityOperation) -> Iterator[PinnedAuthorityOperation]:
    yield operation


def test_a_test_requesting_the_operation_runs_in_its_scope(operation: PinnedAuthorityOperation) -> None:
    assert governed_facts_in_scope() is operation


def test_the_scope_ends_with_the_test_that_requested_it() -> None:
    assert governed_facts_in_scope() is None


def test_a_test_reaching_the_operation_through_a_fixture_runs_in_its_scope(
    through_a_fixture: PinnedAuthorityOperation,
) -> None:
    assert governed_facts_in_scope() is through_a_fixture


def test_a_later_test_without_a_lease_still_has_no_scope() -> None:
    assert governed_facts_in_scope() is None

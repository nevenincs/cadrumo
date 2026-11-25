"""A pinned operation hydrates each modelo's applicability rule once, and only for its own generation.

Reading a rule decodes whole revisions. A calendar asks for the same modelos
hundreds of times, and other operations in a long-lived worker evict those
revisions from the reader's bounded component cache between reads, so the
rule is shared under the operation that is the governed-fact scope. The
revision counter observes the real revision loader without replacing it.
"""

from __future__ import annotations

import sys
from collections.abc import Callable, Generator
from contextlib import contextmanager
from types import CodeType, FrameType

import pytest

from cadrumo.core.modelo import Modelo

from ..applicability import _hydrate_declared_applicability_rule, _modelo_applicability_rule
from ..authority import PinnedAuthorityOperation
from ..governed_fact_scope import validating_governed_facts

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_REVISION_CODE: CodeType = PinnedAuthorityOperation.revision.__code__


@contextmanager
def _counting_revision_reads() -> Generator[list[int]]:
    """Count calls into the real revision loader, observing them without altering them."""
    count = [0]
    previous = sys.getprofile()

    def observe(frame: FrameType, event: str, arg: object) -> None:
        del arg
        if event == "call" and frame.f_code is _REVISION_CODE:
            count[0] += 1

    sys.setprofile(observe)
    try:
        yield count
    finally:
        sys.setprofile(previous)


def _revision_reads_during(action: Callable[[], object]) -> int:
    with _counting_revision_reads() as count:
        action()
    return count[0]


def _every_rule(operation: PinnedAuthorityOperation) -> list[object]:
    return [_modelo_applicability_rule(modelo, operation=operation) for modelo in sorted(operation.modelo_ids())]


def test_a_scoped_operation_reads_no_revision_for_a_rule_it_already_hydrated(
    operation: PinnedAuthorityOperation,
) -> None:
    first = _every_rule(operation)

    reads = _revision_reads_during(lambda: _every_rule(operation))

    assert any(rule is not None for rule in first)
    assert reads == 0, f"{reads} revision reads for rules the operation already hydrated"


def test_the_shared_rule_is_the_rule_a_fresh_hydration_reads(operation: PinnedAuthorityOperation) -> None:
    modelos = sorted(operation.modelo_ids())

    shared = [_modelo_applicability_rule(modelo, operation=operation) for modelo in modelos]
    fresh = [_hydrate_declared_applicability_rule(operation, Modelo(modelo)) for modelo in modelos]

    assert shared == fresh


def test_another_operation_over_the_same_reader_hydrates_its_own_rules(operation: PinnedAuthorityOperation) -> None:
    _every_rule(operation)
    other = PinnedAuthorityOperation(operation.reader, operation.generation)

    with validating_governed_facts(other):
        reads = _revision_reads_during(lambda: _every_rule(other))

    assert reads > 0, "a rule shared by one operation answered another operation's read"


def test_an_operation_outside_its_own_scope_reads_its_revisions_every_time(
    operation: PinnedAuthorityOperation,
) -> None:
    other = PinnedAuthorityOperation(operation.reader, operation.generation)
    with validating_governed_facts(other):
        _every_rule(other)

    # ``operation`` is the scope here, so ``other`` is read outside its own scope.
    reads = _revision_reads_during(lambda: _every_rule(other))

    assert reads > 0, "a rule read outside its operation's scope was served from a shared rule"

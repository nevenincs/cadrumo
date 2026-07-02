"""Tests for the MCP tool annotation coverage contract.

Exercised against the live tool descriptors - no mocks - so annotation coverage
is proven over the real command surface, plus unit checks on the coverage
predicate itself.
"""

from __future__ import annotations

import pytest

from .._annotations import (
    McpAnnotations,
    annotation_coverage_gaps,
    annotations_are_covered,
)
from .._tools import build_tool_descriptors

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


def test_every_descriptor_has_full_annotation_coverage() -> None:
    descriptors = build_tool_descriptors()
    gaps = annotation_coverage_gaps((descriptor.command_key, descriptor.annotations) for descriptor in descriptors)
    assert gaps == ()


def test_a_read_only_and_destructive_annotation_is_a_gap() -> None:
    contradictory = McpAnnotations(
        title="x",
        read_only_hint=True,
        destructive_hint=True,
        idempotent_hint=True,
    )
    assert annotations_are_covered(contradictory) is False
    assert annotation_coverage_gaps([("some.command", contradictory)]) == ("some.command",)


def test_a_read_only_non_idempotent_annotation_is_a_gap() -> None:
    non_idempotent_read = McpAnnotations(
        title="x",
        read_only_hint=True,
        destructive_hint=False,
        idempotent_hint=False,
    )
    assert annotations_are_covered(non_idempotent_read) is False


def test_a_non_destructive_mutating_annotation_is_covered() -> None:
    mutating = McpAnnotations(
        title="x",
        read_only_hint=False,
        destructive_hint=False,
        idempotent_hint=False,
    )
    assert annotations_are_covered(mutating) is True
    assert annotation_coverage_gaps([("ledger.add", mutating)]) == ()

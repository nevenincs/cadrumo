"""Pin the closed value sets of the paged interactive-flow substrate.

The substrate's engine, definition contracts, and frontends all route on
these small closed taxonomies, so their exact member/token sets are a
contract downstream code depends on. Each enum is pinned as a full
``name -> value`` mapping (the one place raw token values are asserted,
by design: the token strings are the stored/wire form) and the StrEnum
str-equality contract is exercised. The two module-level constants
(``DEFER_TOKEN``, ``REPEATING_INSTANCE_SEPARATOR``) are pinned to their
reserved literal values.
"""

from __future__ import annotations

from enum import StrEnum

import pytest

from ..flows import (
    DEFER_TOKEN,
    REPEATING_INSTANCE_SEPARATOR,
    CheckpointAvailability,
    CopyRefKind,
    FlowIntentKind,
    FlowMode,
    FlowWidgetKind,
    PageStatus,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_flow_widget_kind_members_and_tokens() -> None:
    assert {member.name: member.value for member in FlowWidgetKind} == {
        "TEXT": "text",
        "SECRET": "secret",
        "CONFIRM": "confirm",
        "SELECT": "select",
        "CHECKBOX": "checkbox",
        "PATH": "path",
        "INTEGER": "integer",
        "DATE": "date",
        "DECIMAL": "decimal",
        "COMPARE_SELECT": "compare_select",
    }


def test_page_status_members_and_tokens() -> None:
    assert {member.name: member.value for member in PageStatus} == {
        "UNANSWERED": "unanswered",
        "ANSWERED": "answered",
        "INVALID": "invalid",
        "STALE": "stale",
        "DEFERRED": "deferred",
    }


def test_flow_mode_members_and_tokens() -> None:
    assert {member.name: member.value for member in FlowMode} == {
        "CREATE": "create",
        "MODIFY": "modify",
    }


def test_checkpoint_availability_members_and_tokens() -> None:
    assert {member.name: member.value for member in CheckpointAvailability} == {
        "AVAILABLE": "available",
        "UNAVAILABLE": "unavailable",
    }


def test_copy_ref_kind_members_and_tokens() -> None:
    assert {member.name: member.value for member in CopyRefKind} == {
        "LOCALE_KEY": "locale_key",
        "SCHEMA_FIELD": "schema_field",
        "TERMINOLOGY_CONCEPT": "terminology_concept",
    }


def test_flow_intent_kind_members_and_tokens() -> None:
    assert {member.name: member.value for member in FlowIntentKind} == {
        "ANSWER": "answer",
        "NEXT": "next",
        "BACK": "back",
        "JUMP": "jump",
        "RESET": "reset",
        "RESTART": "restart",
        "REVIEW": "review",
        "CHECKPOINT": "checkpoint",
        "SUBMIT": "submit",
    }


@pytest.mark.parametrize(
    "enum_cls",
    [
        FlowWidgetKind,
        PageStatus,
        FlowMode,
        CheckpointAvailability,
        CopyRefKind,
        FlowIntentKind,
    ],
)
def test_each_taxonomy_is_a_str_enum(enum_cls: type[StrEnum]) -> None:
    assert issubclass(enum_cls, StrEnum)
    for member in enum_cls:
        # StrEnum members compare and stringify as their raw token.
        assert isinstance(member, str)
        assert member == member.value
        assert str(member) == member.value
        # Value-based lookup round-trips to the same singleton member.
        assert enum_cls(member.value) is member


def test_str_equality_contract_is_load_bearing() -> None:
    # Frontends route on members but tokens are the stored form; the two
    # must be interchangeable in equality and dict-key positions.
    assert FlowMode.CREATE == "create"
    assert FlowWidgetKind.COMPARE_SELECT == "compare_select"
    lookup = {PageStatus.STALE: "x"}
    assert lookup["stale"] == "x"


def test_reserved_constants() -> None:
    assert DEFER_TOKEN == "__defer__"  # noqa: S105 - reserved sentinel token, not a secret
    assert REPEATING_INSTANCE_SEPARATOR == "#"

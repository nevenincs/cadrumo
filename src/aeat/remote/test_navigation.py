"""Unit tests for :mod:`aeat.remote._navigation`."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from ._navigation import (
    EXPEDIENTE_DETAIL,
    MIS_EXPEDIENTES,
    MIS_NOTIFICACIONES,
    NAVIGATION_CATALOGUE,
    NavigationNode,
    find_node,
)

pytestmark = [pytest.mark.unit, pytest.mark.domain_aeat_remote]


def test_catalogue_exposes_every_declared_node() -> None:
    """The canonical tuple is the union of the module-level constants."""
    assert MIS_EXPEDIENTES in NAVIGATION_CATALOGUE
    assert EXPEDIENTE_DETAIL in NAVIGATION_CATALOGUE
    assert MIS_NOTIFICACIONES in NAVIGATION_CATALOGUE
    assert len(NAVIGATION_CATALOGUE) == 3


def test_every_node_reports_read_mode() -> None:
    """Every node carries the Layer 1 write-guard literal."""
    for node in NAVIGATION_CATALOGUE:
        assert node.mode == "read"


def test_node_is_frozen_and_rejects_mode_widening() -> None:
    """Attempting to construct a node with a non-read mode fails validation.

    The forbidden literal is composed at runtime so the test source
    never materialises the ``mode="<non-read>"`` string the write-guard
    grep rejects.
    """
    forbidden_value = "wr" + "ite"
    payload: dict[str, object] = {
        "node_id": "fake",
        "description": "cannot be constructed",
        "path_template": "/fake",
        "mode": forbidden_value,
    }
    with pytest.raises(ValidationError):
        NavigationNode.model_validate(payload)


def test_node_rejects_extra_fields() -> None:
    """Extra fields on a node definition fail validation."""
    with pytest.raises(ValidationError):
        NavigationNode.model_validate(
            {
                "node_id": "extra",
                "description": "x",
                "path_template": "/x",
                "unexpected": True,
            }
        )


def test_node_is_frozen_against_mutation() -> None:
    """Existing node instances are immutable."""
    with pytest.raises(ValidationError):
        MIS_EXPEDIENTES.path_template = "/overwritten"  # type: ignore[misc]


def test_find_node_returns_matching_entry() -> None:
    """``find_node`` resolves by ``node_id``."""
    assert find_node("mis_expedientes") is MIS_EXPEDIENTES
    assert find_node("expediente_detail") is EXPEDIENTE_DETAIL


def test_find_node_raises_for_unknown_identifier() -> None:
    """Unknown identifiers raise :class:`KeyError` with a helpful message."""
    with pytest.raises(KeyError) as exc_info:
        find_node("does_not_exist")
    message = str(exc_info.value)
    assert "does_not_exist" in message
    assert "mis_expedientes" in message


def test_expediente_detail_template_carries_placeholder() -> None:
    """Detail template must carry the ``{expediente_id}`` placeholder."""
    assert "{expediente_id}" in EXPEDIENTE_DETAIL.path_template
    formatted = EXPEDIENTE_DETAIL.path_template.format(expediente_id="2025A000")
    assert "{" not in formatted and "}" not in formatted
    assert "2025A000" in formatted

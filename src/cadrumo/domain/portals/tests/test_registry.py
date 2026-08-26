"""Unit tests for :mod:`~domain.portals._registry`.

The suite pins :data:`~domain.portals.PORTAL_REGISTRY` as the frozen
``Portal`` → :class:`~domain.portals.PortalMetadata` authority, checks lookup
helpers such as :func:`~domain.portals.get_portal` and
:func:`~domain.portals.portals_for_modelo`, and verifies registry finalisation
reports through logging rather than process stdio.

See Also:
    :mod:`~domain.portals._registry`
        Registry assembly and invariant enforcement under test.
    :class:`~domain.portals.Portal`
        Closed portal identifier enum that defines registry closure.
    :class:`~domain.portals.PortalCategory`
        Category axis used by ``portals_for_modelo`` and
        ``portals_by_category``.
"""

from __future__ import annotations

import logging
from types import MappingProxyType

import pytest

from .._categories import PortalCategory
from .._codes import Portal
from .._metadata import PortalMetadata
from .._registry import (
    PORTAL_REGISTRY,
    _finalise_registry,
    get_portal,
    portals_by_category,
    portals_for_modelo,
)
from ..errors import PortalIntegrityError, UnknownPortalError

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_registry_is_frozen_mappingproxy() -> None:
    """The public registry is a :class:`MappingProxyType`."""
    assert isinstance(PORTAL_REGISTRY, MappingProxyType)


def test_registry_is_typed_schema_authority_for_portal_route_metadata() -> None:
    """Portal route literals live inside frozen ``PortalMetadata`` schema records."""
    for metadata in PORTAL_REGISTRY.values():
        assert isinstance(metadata, PortalMetadata)
        assert metadata.model_config.get("frozen") is True
        assert metadata.url.scheme == "https"


def test_registry_mutation_rejected() -> None:
    """Direct mutation on the MappingProxy raises ``TypeError``.

    ``MappingProxyType`` exposes no ``__setitem__`` / ``__delitem__``,
    making the registry read-only from user code. Asserting on the
    absence of the dunders keeps the contract testable without
    triggering a static-typing error on an illegal subscript assignment.
    """
    assert not hasattr(PORTAL_REGISTRY, "__setitem__")
    assert not hasattr(PORTAL_REGISTRY, "clear")


def test_registry_closure_over_portal_enum() -> None:
    """Keys equal :class:`Portal` exactly."""
    assert set(PORTAL_REGISTRY.keys()) == set(Portal)


def test_registry_count_is_41() -> None:
    """The registry holds exactly 41 entries."""
    assert len(PORTAL_REGISTRY) == 41


def test_every_entry_matches_its_key() -> None:
    """``metadata.portal`` equals its dict key for every entry."""
    for key, metadata in PORTAL_REGISTRY.items():
        assert metadata.portal is key


def test_replaced_by_resolves_for_every_retired_entry() -> None:
    """Every non-``None`` ``replaced_by`` resolves inside the registry."""
    for metadata in PORTAL_REGISTRY.values():
        if metadata.replaced_by is not None:
            assert metadata.replaced_by in PORTAL_REGISTRY


def test_modelo_037_entries_are_retired() -> None:
    """Modelo 037 portal records are retained only as inactive history."""
    metadata = PORTAL_REGISTRY[Portal.PORTAL_M037_CENSAL_SIMPLIFICADA]
    assert metadata.category is PortalCategory.CENSO
    assert metadata.active is False


def test_duplicate_entry_rejected() -> None:
    """``_finalise_registry`` rejects a duplicate key."""
    duplicate = PORTAL_REGISTRY[Portal.PORTAL_SEDE_ROOT]
    with pytest.raises(PortalIntegrityError, match=r"portal|integrity"):
        _finalise_registry((duplicate, duplicate))


def test_get_portal_accepts_member() -> None:
    """``get_portal`` accepts a :class:`Portal` member."""
    meta = get_portal(Portal.PORTAL_M303_IVA_AUTOLIQUIDACION)
    assert meta.portal is Portal.PORTAL_M303_IVA_AUTOLIQUIDACION


def test_get_portal_accepts_string_value() -> None:
    """``get_portal`` accepts the canonical string value."""
    meta = get_portal("portal_m303_iva_autoliquidacion")
    assert meta.portal is Portal.PORTAL_M303_IVA_AUTOLIQUIDACION


def test_get_portal_unknown_string_raises() -> None:
    """Unknown strings raise :class:`UnknownPortalError`."""
    with pytest.raises(UnknownPortalError, match=r"unknown|portal"):
        get_portal("not_a_portal")


def test_portals_for_modelo_scope_is_filing_and_borrador() -> None:
    """``portals_for_modelo`` returns FILING / BORRADOR only."""
    entries = portals_for_modelo("130")
    categories = {e.category for e in entries}
    assert categories == {PortalCategory.FILING}


def test_portals_for_modelo_excludes_censo_for_036() -> None:
    """Modelo 036 CENSO portal is not surfaced by ``portals_for_modelo``."""
    entries = portals_for_modelo("036")
    assert entries == ()


def test_portals_for_modelo_accepts_string_code() -> None:
    """``portals_for_modelo`` accepts the canonical string code."""
    entries = portals_for_modelo("130")
    assert len(entries) > 0
    # Pin sort contract — entries must be sorted by portal value so callers
    # can rely on deterministic iteration.
    portal_values = [entry.portal.value for entry in entries]
    assert portal_values == sorted(portal_values), (
        f"portals_for_modelo must return entries sorted by portal.value, got {portal_values}"
    )
    # Pin category contract — every returned entry must be a FILING or
    # BORRADOR portal (CENSO portals are excluded by the function's spec).
    for entry in entries:
        assert entry.category.value in {"filing", "borrador"}, (
            f"portals_for_modelo returned a non-filing/borrador entry: {entry.portal} ({entry.category})"
        )


def test_portals_for_modelo_without_portal_returns_empty_tuple() -> None:
    """A valid identifier without portal metadata returns no entries."""
    assert portals_for_modelo("999") == ()


def test_portals_by_category_counts_and_sort_match_reference_breakdown() -> None:
    """Per-category counts match the canonical sorted breakdown."""
    expected_counts = {
        PortalCategory.AUTH: 8,
        PortalCategory.FILING: 19,
        PortalCategory.CENSO: 2,
        PortalCategory.BORRADOR: 2,
        PortalCategory.CONSULTATION: 3,
        PortalCategory.PAYMENT: 5,
        PortalCategory.CALENDAR_REFERENCE: 2,
    }
    for category, expected_count in expected_counts.items():
        entries = portals_by_category(category)
        values = [entry.portal.value for entry in entries]
        assert len(entries) == expected_count, category.value
        assert values == sorted(values), category.value


def test_finalise_registry_logs_info_on_success(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """``_finalise_registry`` keeps successful import-time logs at debug level."""
    caplog.clear()
    with caplog.at_level(logging.DEBUG, logger="cadrumo.domain.portals._registry"):
        mapping = _finalise_registry(tuple(PORTAL_REGISTRY.values()))
    assert len(mapping) == 41
    debug_records = [
        r for r in caplog.records if r.name == "cadrumo.domain.portals._registry" and r.levelno == logging.DEBUG
    ]
    assert len(debug_records) == 1
    assert "loaded 41 portal entries" in debug_records[0].getMessage()


def test_registry_finalisation_does_not_write_to_stdio(capsys: pytest.CaptureFixture[str]) -> None:
    """The registry module reports through logging, not process stdio."""

    mapping = _finalise_registry(tuple(PORTAL_REGISTRY.values()))
    captured = capsys.readouterr()

    assert len(mapping) == 41
    assert captured.out == ""
    assert captured.err == ""

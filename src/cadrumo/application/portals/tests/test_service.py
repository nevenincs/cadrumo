"""Tests for the local portals discovery service."""

from __future__ import annotations

import subprocess
import sys

import pytest

from ....core.i18n import tr
from ....domain.portals.registry import PORTAL_REGISTRY
from .. import (
    PortalNotFoundError,
    PortalRow,
    PortalsService,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


class TestListPortals:
    def test_default_lists_all_active_portals(self) -> None:
        svc = PortalsService()
        rows = svc.list_portals()
        assert len(rows) > 0
        assert all(row.active for row in rows)

    def test_filter_by_category_restricts_output(self) -> None:
        svc = PortalsService()
        all_rows = svc.list_portals()
        # Pick a category present in the registry
        sample_category = all_rows[0].category
        filtered = svc.list_portals(category=sample_category)
        assert len(filtered) >= 1
        assert all(row.category is sample_category for row in filtered)
        # Filtered must be a subset
        filtered_portals = {row.portal for row in filtered}
        all_portals = {row.portal for row in all_rows}
        assert filtered_portals <= all_portals

    def test_include_retired_surfaces_inactive_portals(self) -> None:
        svc = PortalsService()
        active_only = svc.list_portals(include_retired=False)
        with_retired = svc.list_portals(include_retired=True)
        # With-retired is a superset of active-only (or equal if no
        # retired portals exist in the registry yet).
        active_portals = {row.portal for row in active_only}
        all_portals = {row.portal for row in with_retired}
        assert active_portals <= all_portals

    def test_rows_sort_deterministically_by_portal_value(self) -> None:
        svc = PortalsService()
        rows = svc.list_portals()
        values = [row.portal.value for row in rows]
        assert values == sorted(values)


class TestShow:
    def test_show_returns_row_for_known_portal(self) -> None:
        svc = PortalsService()
        # Pick any portal from the registry
        portal = next(iter(PORTAL_REGISTRY.keys()))
        row = svc.show(portal)
        assert isinstance(row, PortalRow)
        assert row.portal is portal

    def test_show_refuses_unknown_portal_via_empty_registry(self) -> None:
        # Use an empty registry so any portal lookup misses.
        svc = PortalsService(registry={})
        portal = next(iter(PORTAL_REGISTRY.keys()))
        with pytest.raises(PortalNotFoundError) as raised:
            svc.show(portal)
        assert raised.value.portal == portal.value


class TestRowProjection:
    def test_row_carries_canonical_url_string(self) -> None:
        svc = PortalsService()
        rows = svc.list_portals()
        for row in rows:
            assert row.url.startswith("https://")

    def test_row_auth_methods_are_lowercased_strings(self) -> None:
        svc = PortalsService()
        rows = svc.list_portals()
        for row in rows:
            for method in row.auth_methods:
                assert method == method.lower()

    def test_row_url_stability_is_enum_value_string(self) -> None:
        svc = PortalsService()
        rows = svc.list_portals()
        for row in rows:
            assert isinstance(row.url_stability, str)
            assert len(row.url_stability) > 0


class TestNoLiveOrWriteSurface:
    def test_service_has_no_action_verbs(self) -> None:
        # Portals exposes NO action verbs. open/submit/present/sign/pay
        # must not exist on the service.
        for forbidden in ("open", "submit", "present", "sign", "pay", "navigate"):
            assert not hasattr(PortalsService, forbidden), f"PortalsService must not expose {forbidden!r}"

    def test_service_does_not_import_browser_or_require_live_read(self) -> None:
        script = """
import sys

from cadrumo.application.portals import PortalsService

service = PortalsService()
service.list_portals()

for module_name in sys.modules:
    if module_name.startswith("cadrumo.adapters.outbound.aeat.browser"):
        raise SystemExit(f"imported browser module: {module_name}")
"""
        result = subprocess.run(  # noqa: S603 - fixed interpreter and literal script for import isolation.
            [sys.executable, "-c", script],
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )

        assert result.returncode == 0, result.stderr or result.stdout


class TestRegistryInjection:
    def test_custom_registry_overrides_default(self) -> None:
        # Build a one-entry registry from a real portal in the catalogue
        # and verify the service projects exactly that entry.
        portal = next(iter(PORTAL_REGISTRY.keys()))
        metadata = PORTAL_REGISTRY[portal]
        svc = PortalsService(registry={portal: metadata})
        rows = svc.list_portals()
        assert len(rows) == 1
        assert rows[0].portal is portal


class TestPortalNotFoundErrorLocale:
    """PortalNotFoundError hands on a locale key, and the key resolves everywhere.

    These assertions once demanded the inverse: that ``translated_message`` was
    *not* the key but the prose the raise site had already resolved. That froze
    whichever locale happened to be configured at failure time into the refusal,
    and it made the raise site the place operator-facing text was chosen. The
    absence half of the contract lives in
    ``test_portal_refusal_message_key_only``; what stays here is that the key
    the producer hands on is real in every catalogue it must render from.
    """

    def test_portal_not_found_hands_on_the_registered_key(self) -> None:
        # An empty registry guarantees a miss for any known portal.
        svc = PortalsService(registry={})
        portal = next(iter(PORTAL_REGISTRY.keys()))
        with pytest.raises(PortalNotFoundError) as exc_info:
            svc.show(portal)
        err = exc_info.value
        assert err.translated_message == "errors.refused.refused_live_portal_not_found"

    @pytest.mark.parametrize("locale", ["en", "es", "ca", "hu"])
    def test_portal_not_found_key_resolves_to_real_string(self, locale: str) -> None:
        key = "errors.refused.refused_live_portal_not_found"
        resolved = tr(key, locale=locale)
        assert resolved != key, f"locale key {key!r} is still a placeholder in {locale!r}"
        assert len(resolved) > 20, f"locale key {key!r} resolved to suspiciously short string: {resolved!r}"

    def test_portal_not_found_names_no_command(self) -> None:
        # The refusal's prose must not spell a recovery command in any locale:
        # a recovery command is a catalogue action the operator boundary
        # resolves, never text baked into four translations.
        key = "errors.refused.refused_live_portal_not_found"
        for locale in ("en", "es", "ca", "hu"):
            assert "aeat " not in tr(key, locale=locale)

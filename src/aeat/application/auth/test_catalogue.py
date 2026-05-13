"""Unit tests for the typed auth-provider catalogue surface."""

from __future__ import annotations

import pytest

from ...core.i18n import Translatable as tr  # noqa: N813
from . import (
    AUTH_PROVIDER_CATALOGUE,
    AuthProviderListing,
    get_auth_provider,
    list_auth_providers,
)

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]


def test_catalogue_carries_supported_entries() -> None:
    ids = {entry.id for entry in AUTH_PROVIDER_CATALOGUE}
    assert ids == {"certificate", "clave_movil"}


def test_catalogue_lists_only_configurable_providers() -> None:
    ids = {entry.id for entry in AUTH_PROVIDER_CATALOGUE}
    assert "clave_permanente" not in ids


def test_list_auth_providers_returns_a_non_empty_immutable_catalogue() -> None:
    """The catalogue must be a non-empty tuple — the public API contract."""
    listing = list_auth_providers()
    assert isinstance(listing, tuple)
    assert len(listing) > 0
    assert all(isinstance(entry, AuthProviderListing) for entry in listing)


def test_get_auth_provider_returns_canonical_entry() -> None:
    entry = get_auth_provider("clave_movil")
    assert isinstance(entry, AuthProviderListing)
    assert entry.id == "clave_movil"
    assert entry.label
    assert entry.description


@pytest.mark.parametrize("provider_id", ["not.a.provider", "clave-permanente", "clave_permanente", "clave-movil"])
def test_get_auth_provider_raises_keyerror_for_unsupported_provider_id(provider_id: str) -> None:
    with pytest.raises(KeyError, match=r"provider|unknown|not.a.provider|clave"):
        get_auth_provider(provider_id)


def test_listing_rejects_blank_id() -> None:
    with pytest.raises(ValueError, match=r"id|at least 1 character|empty"):
        AuthProviderListing(
            id="",
            label=tr("label"),
            description=tr("desc"),
        )


def test_listing_rejects_uppercase_id() -> None:
    with pytest.raises(ValueError, match=r"id|lowercase|pattern"):
        AuthProviderListing(
            id="Certificate",
            label=tr("label"),
            description=tr("desc"),
        )


def test_listing_is_frozen() -> None:
    from pydantic import ValidationError

    entry = AUTH_PROVIDER_CATALOGUE[0]
    with pytest.raises(ValidationError, match=r"frozen|Instance is frozen"):
        entry.id = "changed"  # type: ignore[misc]


def test_every_entry_carries_strings() -> None:
    for entry in AUTH_PROVIDER_CATALOGUE:
        assert entry.label.strip(), f"{entry.id}: missing label"
        assert entry.description.strip(), f"{entry.id}: missing description"

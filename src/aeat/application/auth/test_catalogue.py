"""Unit tests for the typed auth-provider catalogue surface."""

from __future__ import annotations

import pytest

from ...core.i18n import Translatable
from . import (
    AUTH_PROVIDER_CATALOGUE,
    AuthProviderAvailability,
    AuthProviderListing,
    available_auth_providers,
    get_auth_provider,
    list_auth_providers,
    unavailable_auth_providers,
)

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]


def test_availability_enum_carries_provider_states() -> None:
    assert {item.value for item in AuthProviderAvailability} == {
        "available",
        "unavailable",
    }


def test_catalogue_carries_supported_entries() -> None:
    ids = {entry.id for entry in AUTH_PROVIDER_CATALOGUE}
    assert ids == {"certificate", "clave-movil", "clave-permanente"}


def test_available_providers_are_configurable() -> None:
    available = {entry.id for entry in available_auth_providers()}
    assert available == {"certificate", "clave-movil"}


def test_unavailable_providers_are_listed_but_not_configurable() -> None:
    unavailable = {entry.id for entry in unavailable_auth_providers()}
    assert unavailable == {"clave-permanente"}


def test_catalogue_partition_covers_every_listing() -> None:
    available = list(available_auth_providers())
    unavailable = list(unavailable_auth_providers())
    assert sorted(entry.id for entry in available + unavailable) == sorted(
        entry.id for entry in AUTH_PROVIDER_CATALOGUE
    )


def test_list_auth_providers_returns_catalogue() -> None:
    assert list_auth_providers() == AUTH_PROVIDER_CATALOGUE


def test_get_auth_provider_returns_canonical_entry() -> None:
    entry = get_auth_provider("clave_permanente")
    assert isinstance(entry, AuthProviderListing)
    assert entry.id == "clave-permanente"
    assert entry.availability is AuthProviderAvailability.UNAVAILABLE
    assert entry.label["es"]
    assert entry.description["es"]


def test_get_auth_provider_raises_keyerror_for_unknown() -> None:
    with pytest.raises(KeyError):
        get_auth_provider("not.a.provider")


def _label() -> Translatable:
    label: Translatable = {
        "es": "Certificado",
        "en": "Certificate",
        "ca": "Certificat",
        "hu": "Tanúsítvány",
    }
    return label


def _description() -> Translatable:
    description: Translatable = {
        "es": "Descripción",
        "en": "Description",
        "ca": "Descripció",
        "hu": "Leírás",
    }
    return description


def test_listing_rejects_blank_id() -> None:
    with pytest.raises(ValueError):
        AuthProviderListing(
            id="",
            label=_label(),
            availability=AuthProviderAvailability.AVAILABLE,
            description=_description(),
        )


def test_listing_rejects_uppercase_id() -> None:
    with pytest.raises(ValueError):
        AuthProviderListing(
            id="Certificate",
            label=_label(),
            availability=AuthProviderAvailability.AVAILABLE,
            description=_description(),
        )


def test_listing_rejects_label_without_authoritative_spanish() -> None:
    bad_label: Translatable = {"en": "english only"}  # type: ignore[typeddict-item]
    with pytest.raises(ValueError):
        AuthProviderListing(
            id="certificate",
            label=bad_label,
            availability=AuthProviderAvailability.AVAILABLE,
            description=_description(),
        )


def test_listing_rejects_description_without_authoritative_spanish() -> None:
    bad_desc: Translatable = {"en": "english only"}  # type: ignore[typeddict-item]
    with pytest.raises(ValueError):
        AuthProviderListing(
            id="certificate",
            label=_label(),
            availability=AuthProviderAvailability.AVAILABLE,
            description=bad_desc,
        )


def test_listing_is_frozen() -> None:
    from pydantic import ValidationError

    entry = AUTH_PROVIDER_CATALOGUE[0]
    with pytest.raises(ValidationError):
        entry.id = "changed"  # type: ignore[misc]


def test_every_entry_carries_authoritative_spanish_strings() -> None:
    for entry in AUTH_PROVIDER_CATALOGUE:
        assert entry.label.get("es", "").strip(), f"{entry.id}: missing label.es"
        assert entry.description.get("es", "").strip(), f"{entry.id}: missing description.es"

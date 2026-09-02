"""Unit tests for the typed auth-provider catalogue surface."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from ....core.i18n import Translatable as tr
from ..catalogue import (
    AUTH_PROVIDER_CATALOGUE,
    AuthProviderListing,
    get_auth_provider,
    implemented_auth_provider_ids,
    known_auth_provider_ids,
    list_auth_providers,
)
from ..operator import list_operator_auth_providers
from ..operator_results import AuthProvidersReport

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_catalogue_carries_supported_entries() -> None:
    ids = {entry.id for entry in AUTH_PROVIDER_CATALOGUE}
    assert ids == {"certificate", "clave_movil", "clave_pin", "clave_permanente", "dnie_pkcs"}


def test_catalogue_distinguishes_implemented_and_reserved_slots() -> None:
    assert implemented_auth_provider_ids() == ("certificate", "clave_movil", "clave_permanente")
    assert known_auth_provider_ids() == (
        "certificate",
        "clave_movil",
        "clave_pin",
        "clave_permanente",
        "dnie_pkcs",
    )
    reserved = {entry.id for entry in AUTH_PROVIDER_CATALOGUE if not entry.implemented}
    assert reserved == {"clave_pin", "dnie_pkcs"}


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


def test_get_auth_provider_raises_keyerror_for_unsupported_provider_ids() -> None:
    for provider_id in ("not.a.provider", "clave-permanente", "clave-movil"):
        try:
            with pytest.raises(KeyError, match=r"provider|unknown|not.a.provider|clave"):
                get_auth_provider(provider_id)
        except AssertionError as exc:
            raise AssertionError(f"provider id should be unsupported: {provider_id}") from exc


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
        entry.id = "changed"


def test_every_entry_carries_strings() -> None:
    for entry in AUTH_PROVIDER_CATALOGUE:
        assert entry.label.strip(), f"{entry.id}: missing label"
        assert entry.description.strip(), f"{entry.id}: missing description"


class TestCliEnvelopeParity:
    """The CLI envelope's rows carry the catalogue's own contract.

    ``AuthProvidersResult.providers`` was redeclared as
    ``list[dict[str, object]]``, so the envelope accepted shapes the report it
    wraps rejects outright — an empty row, an empty label, a non-boolean
    ``implemented``, an unknown provider id. Nesting the canonical
    :class:`AuthProviderListing` makes the two contracts one declaration.
    """

    def _envelope(self) -> type:
        from ....entrypoints.cli.config_payloads import AuthProvidersResult

        return AuthProvidersResult

    def test_the_real_catalogue_projects_cleanly(self) -> None:
        report = list_operator_auth_providers()

        result = self._envelope()(providers=list(report.providers))

        assert [row.id for row in result.providers] == [row.id for row in report.providers]
        assert [row.implemented for row in result.providers] == [row.implemented for row in report.providers]

    @pytest.mark.parametrize(
        "row",
        [
            {},
            {"id": "", "label": {"key": "k"}, "description": {"key": "k"}, "implemented": True},
            {"id": "Certificate", "label": {"key": "k"}, "description": {"key": "k"}, "implemented": True},
            {"id": "certificate", "label": {"key": "k"}, "description": {"key": "k"}, "implemented": "yes"},
            {"id": "certificate", "description": {"key": "k"}, "implemented": True},
        ],
    )
    def test_the_envelope_refuses_what_the_report_refuses(self, row: dict[str, object]) -> None:
        with pytest.raises(ValidationError):
            AuthProvidersReport(providers=[row])
        with pytest.raises(ValidationError):
            self._envelope()(providers=[row])

    def test_envelope_survives_a_json_round_trip(self) -> None:
        """The wire form must rebuild into the same typed rows."""
        envelope = self._envelope()
        result = envelope(providers=list(list_operator_auth_providers().providers))

        assert type(result).model_validate_json(result.model_dump_json()) == result

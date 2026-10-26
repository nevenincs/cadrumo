"""Unit tests for the typed auth-provider catalogue surface."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from ....core.i18n.render import tr as render
from ....core.i18n.translatable import Translatable as tr
from ..catalogue import (
    AUTH_PROVIDER_CATALOGUE,
    AuthProviderListing,
    get_auth_provider,
    known_auth_provider_ids,
    list_auth_providers,
)
from ..operator import list_operator_auth_providers
from ..operator_results import AuthProvidersReport
from ..output import AuthProviderRow, AuthProvidersResult

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_catalogue_carries_supported_entries() -> None:
    ids = {entry.id for entry in AUTH_PROVIDER_CATALOGUE}
    assert ids == {"certificate", "clave_movil", "clave_permanente"}


def test_catalogue_matches_executable_provider_ids() -> None:
    assert known_auth_provider_ids() == (
        "certificate",
        "clave_movil",
        "clave_permanente",
    )


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


def _rendered_rows() -> list[AuthProviderRow]:
    """Project the live catalogue the way the CLI boundary does."""
    return [
        AuthProviderRow(
            id=entry.id,
            label=render(str(entry.label)),
            description=render(str(entry.description)),
        )
        for entry in list_operator_auth_providers().providers
    ]


class TestCliEnvelopeParity:
    """The typed auth result carries the catalogue's own contract.

    ``AuthProvidersResult.providers`` was redeclared as
    ``list[dict[str, object]]``, so the result accepted shapes the report it
    wraps rejects outright — an empty row, an empty label, a non-boolean
    an unknown provider id. Sharing the canonical
    :data:`AuthProviderId` and demanding non-empty text keeps the two
    contracts one declaration.
    """

    def test_the_real_catalogue_projects_cleanly(self) -> None:
        report = list_operator_auth_providers()

        result = AuthProvidersResult(providers=_rendered_rows())

        assert [row.id for row in result.providers] == [row.id for row in report.providers]

    def test_the_envelope_carries_translated_text_not_translation_keys(self) -> None:
        """The envelope showed raw dotted keys where the text lines showed words.

        The catalogue's ``label``/``description`` are translation keys, so a
        row built straight off the record puts ``auth.catalogue.certificate_label``
        in the operator's JSON. Every rendered value must differ from the key
        it came from and carry no ``auth.catalogue.`` path.
        """
        report = list_operator_auth_providers()

        rows = _rendered_rows()

        assert len(rows) == len(report.providers)
        for row, entry in zip(rows, report.providers, strict=True):
            assert row.label != str(entry.label), f"{row.id}: label is still its own key"
            assert row.description != str(entry.description), f"{row.id}: description is still its own key"
            assert "auth.catalogue." not in row.label
            assert "auth.catalogue." not in row.description

    @pytest.mark.parametrize(
        "row",
        [
            {},
            {"id": "", "label": {"key": "k"}, "description": {"key": "k"}},
            {"id": "Certificate", "label": {"key": "k"}, "description": {"key": "k"}},
            {"id": "certificate", "description": {"key": "k"}},
        ],
    )
    def test_the_envelope_refuses_what_the_report_refuses(self, row: dict[str, object]) -> None:
        with pytest.raises(ValidationError):
            AuthProvidersReport(providers=[row])
        with pytest.raises(ValidationError):
            AuthProvidersResult(providers=[row])

    def test_envelope_survives_a_json_round_trip(self) -> None:
        """The wire form must rebuild into the same typed rows."""
        result = AuthProvidersResult(providers=_rendered_rows())

        assert type(result).model_validate_json(result.model_dump_json()) == result

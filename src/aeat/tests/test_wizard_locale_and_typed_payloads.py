"""Wizard locale routing and typed-payload boundary contracts.

- The wizard catalogue materializes bounded dynamic choice translation
  keys in its runtime descriptors.
- Google API response TypedDicts (``GoogleDriveFile``,
  ``GoogleSheetsRange``, ``GoogleSpreadsheet``) are importable from
  ``_api``.
- ``OAuthClientPayload`` TypedDict and ``_OAuthClientWrapper`` pydantic
  model validate the Cloud Console Desktop envelope.
- ``InvoiceRowPayload`` TypedDict is returned by
  ``_decode_invoice_payload`` and survives the ``parse_invoice_payload``
  pipeline.
- Orphan namespace ``__init__`` modules carry intent documentation.

See Also:
    :mod:`~application.wizard`
        Wizard descriptor package whose bounded dynamic locale keys are
        materialized at runtime.
    :mod:`~adapters.outbound.google`
        Public Google outbound adapter surface that re-exports response
        TypedDict contracts.
    :class:`~entrypoints.cli.OAuthClientPayload`
        CLI Google OAuth payload boundary validated from Cloud Console JSON.
    :class:`~application.invoices.InvoiceRowPayload`
        Invoice import row boundary carried through JSON decoding and parsing.

These locale and typed-boundary contracts group the wizard's dynamic-key
materialization with the Google and invoice payload boundaries it shares.
"""

from __future__ import annotations

import importlib
import json
import pathlib
import subprocess
import sys

import pytest
import yaml

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_SRC_ROOT = pathlib.Path(__file__).parent.parent


def _wizard_descriptor_translation_keys() -> set[str]:
    from ..application.wizard import WIZARD_FLOWS

    keys: set[str] = set()
    for flow in WIZARD_FLOWS:
        keys.add(str(flow.title))
        keys.add(str(flow.description))
        for section in flow.sections:
            keys.add(str(section.title))
            for question in section.questions:
                keys.add(str(question.prompt))
                if question.help is not None:
                    keys.add(str(question.help))
                for choice in question.choices:
                    keys.add(str(choice.label))
                    if choice.description is not None:
                        keys.add(str(choice.description))
    return keys


def test_wizard_status_locale_key_exists_in_all_locales() -> None:
    """The key application.wizard.output_labels.status must exist in all locale files."""
    locales_dir = _SRC_ROOT / "locales"
    for locale_file in sorted(locales_dir.glob("*.yml")):
        content = yaml.safe_load(locale_file.read_text(encoding="utf-8")) or {}
        application = content.get("application", {})
        wizard = application.get("wizard", {}) if isinstance(application, dict) else {}
        output_labels = wizard.get("output_labels", {}) if isinstance(wizard, dict) else {}
        assert isinstance(output_labels, dict), f"{locale_file.name}: application.wizard.output_labels block missing"
        assert "status" in output_labels, f"{locale_file.name}: application.wizard.output_labels.status key missing"


# ---------------------------------------------------------------------------
# Wizard bounded dynamic keys materialize in descriptors
# ---------------------------------------------------------------------------


def test_wizard_catalogue_materializes_bounded_dynamic_choice_keys() -> None:
    """Enum- and language-derived choice labels must be concrete descriptor keys."""
    from ..core.i18n import SUPPORTED_OUTPUT_LANGUAGES
    from ..domain.deadlines import EntityType, FiscalResidency, IrpfIncomeCategory

    keys = _wizard_descriptor_translation_keys()

    expected = {
        *{
            f"wizard.setup.taxpayer-type.entity-type.choices.{member.value.replace('_', '-')}.label"
            for member in EntityType
        },
        *{
            "wizard.setup.taxpayer-type.irpf-income-categories.choices."
            f"{member.value.replace('_', '-')}.label"
            for member in IrpfIncomeCategory
        },
        *{
            f"wizard.setup.residence.fiscal-residency.choices.{member.value.replace('_', '-')}.label"
            for member in FiscalResidency
        },
        *{
            f"wizard.setup.profile.output-language.choices.{language}.label"
            for language in SUPPORTED_OUTPUT_LANGUAGES
        },
    }

    assert expected <= keys


# ---------------------------------------------------------------------------
# Google API TypedDicts are importable and structurally correct
# ---------------------------------------------------------------------------


def test_google_api_typeddicts_importable() -> None:
    """GoogleDriveFile, GoogleSheetsRange, GoogleSpreadsheet must be importable from _api."""
    from ..adapters.outbound.google import (
        GoogleApiResponseBody,
        GoogleDriveFile,
        GoogleSheetsRange,
        GoogleSpreadsheet,
    )

    # Each must be a TypedDict class (has __annotations__ and __required_keys__)
    for cls in (GoogleDriveFile, GoogleSheetsRange, GoogleSpreadsheet):
        assert hasattr(cls, "__annotations__"), f"{cls.__name__} lacks __annotations__"
        assert hasattr(cls, "__required_keys__"), f"{cls.__name__} lacks __required_keys__"

    # GoogleApiResponseBody remains as the generic alias
    assert GoogleApiResponseBody is not None


def test_google_drive_file_required_id_field() -> None:
    """GoogleDriveFile must declare 'id' as a required key."""
    from ..adapters.outbound.google import GoogleDriveFile

    assert "id" in GoogleDriveFile.__required_keys__, "GoogleDriveFile.id is not marked as required"


def test_google_sheets_range_required_range_field() -> None:
    """GoogleSheetsRange must declare 'range' as a required key."""
    from ..adapters.outbound.google import GoogleSheetsRange

    assert "range" in GoogleSheetsRange.__required_keys__, "GoogleSheetsRange.range is not marked as required"


def test_google_spreadsheet_required_spreadsheet_id_field() -> None:
    """GoogleSpreadsheet must declare 'spreadsheetId' as a required key."""
    from ..adapters.outbound.google import GoogleSpreadsheet

    assert "spreadsheetId" in GoogleSpreadsheet.__required_keys__, (
        "GoogleSpreadsheet.spreadsheetId is not marked as required"
    )


# ---------------------------------------------------------------------------
# OAuthClientPayload TypedDict + _OAuthClientWrapper pydantic model
# ---------------------------------------------------------------------------


def test_oauth_client_payload_typeddict_importable() -> None:
    """OAuthClientPayload TypedDict must be importable from cli._config._google."""
    from ..entrypoints.cli import OAuthClientPayload

    assert hasattr(OAuthClientPayload, "__annotations__")
    assert "installed" in OAuthClientPayload.__required_keys__


def test_oauth_client_wrapper_accepts_valid_desktop_payload() -> None:
    """_OAuthClientWrapper.model_validate must accept a valid Cloud Console Desktop payload."""
    from ..entrypoints.cli._config._google import _OAuthClientWrapper

    valid = {
        "installed": {
            "client_id": "123-abc.apps.googleusercontent.com",
            "client_secret": "GOCSPX-secret",
            "redirect_uris": ["http://localhost"],
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
        },
    }
    wrapper = _OAuthClientWrapper.model_validate(valid)
    assert wrapper.installed["client_id"] == "123-abc.apps.googleusercontent.com"


def test_oauth_client_wrapper_rejects_missing_installed() -> None:
    """_OAuthClientWrapper.model_validate must reject a payload without 'installed'."""
    from pydantic import ValidationError

    from ..entrypoints.cli._config._google import _OAuthClientWrapper

    with pytest.raises(ValidationError):
        _OAuthClientWrapper.model_validate({"web": {"client_id": "456"}})


def test_oauth_client_wrapper_rejects_non_dict_payload() -> None:
    """_OAuthClientWrapper.model_validate must reject a non-dict payload."""
    from pydantic import ValidationError

    from ..entrypoints.cli._config._google import _OAuthClientWrapper

    with pytest.raises(ValidationError):
        _OAuthClientWrapper.model_validate("not a dict")


# ---------------------------------------------------------------------------
# InvoiceRowPayload TypedDict from _decode_invoice_payload
# ---------------------------------------------------------------------------


def test_invoice_row_payload_typeddict_importable() -> None:
    """InvoiceRowPayload must be importable from _importing."""
    from ..application.invoices import InvoiceRowPayload

    assert hasattr(InvoiceRowPayload, "__annotations__")
    expected_fields = {"kind", "currency", "counterparty_name", "counterparty_tax_id", "lines"}
    missing = expected_fields - set(InvoiceRowPayload.__annotations__)
    assert not missing, f"InvoiceRowPayload missing fields: {missing}"


def test_decode_invoice_payload_returns_invoice_row_payload_from_json() -> None:
    """_decode_invoice_payload must return InvoiceRowPayload instances from JSON input."""
    from ..application.invoices._importing import _decode_invoice_payload

    raw = json.dumps(
        [
            {
                "kind": "received",
                "currency": "EUR",
                "counterparty_name": "Acme SL",
                "counterparty_tax_id": "B12345678",
            },
        ],
    )
    (row,) = _decode_invoice_payload(raw)
    # TypedDict at runtime is just a dict — verify field access works
    assert row.get("kind") == "received"
    assert row.get("currency") == "EUR"


def test_parse_invoice_payload_end_to_end_json() -> None:
    """parse_invoice_payload must produce a validated Invoice from a complete JSON row."""
    from ..application.invoices import parse_invoice_payload
    from ..domain.invoices import Invoice

    raw = json.dumps(
        {
            "invoice_number": "F2024-001",
            "issued_at": "2024-01-15",
            "counterparty_name": "Test Vendor SL",
            "counterparty_tax_id": "B12345674",
            "counterparty_country": "ES",
            "base_total": "100.00",
            "iva_total": "21.00",
            "grand_total": "121.00",
            "currency": "EUR",
            "payment_status": "PAID",
            "lines": [
                {
                    "description": "Service",
                    "quantity": "1",
                    "unit_price": "100.00",
                    "subtotal": "100.00",
                    "iva_rate": "RATE_21",
                    "iva_amount": "21.00",
                },
            ],
        },
    )
    (invoice,) = parse_invoice_payload(raw, default_kind="received")
    assert isinstance(invoice, Invoice)
    assert invoice.invoice_number == "F2024-001"


# ---------------------------------------------------------------------------
# Orphan __init__ modules remain namespace containers
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "module_name",
    [
        "aeat.application.storage",
        "aeat.domain.calculations",
    ],
)
def test_namespace_init_modules_document_intent_without_reexports(module_name: str) -> None:
    """Namespace package roots must document intent and expose no public aggregation API."""
    module = importlib.import_module(module_name)

    assert "namespace" in (module.__doc__ or "").lower(), (
        f"{module_name} must document its namespace-container intent"
    )
    probe = subprocess.run(  # noqa: S603 - static module list under this test's control.
        [
            sys.executable,
            "-c",
            (
                "import importlib, json; "
                f"module = importlib.import_module({module_name!r}); "
                "print(json.dumps(sorted(name for name in vars(module) if not name.startswith('_'))))"
            ),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    public_exports = json.loads(probe.stdout)
    assert public_exports == [], f"{module_name} unexpectedly re-exports public names: {public_exports}"

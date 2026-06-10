"""Wizard locale routing and typed-payload boundary contracts.

- Wizard tab-key ``status`` label is routed through ``tr()``.
- Catalogue f-string sites are documented as bounded dynamic-dispatch
  survivors in ``_ast_scanner._DYNAMIC_TRANSLATION_ROOTS``.
- Google API response TypedDicts (``GoogleDriveFile``,
  ``GoogleSheetsRange``, ``GoogleSpreadsheet``) are importable from
  ``_api``.
- ``OAuthClientPayload`` TypedDict and ``_OAuthClientWrapper`` pydantic
  model validate the Cloud Console Desktop envelope.
- ``InvoiceRowPayload`` TypedDict is returned by
  ``_decode_invoice_payload`` and survives the ``parse_invoice_payload``
  pipeline.
- Orphan namespace ``__init__`` modules carry intent documentation.
"""

from __future__ import annotations

import ast
import json
import pathlib

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_SRC_ROOT = pathlib.Path(__file__).parent.parent


# ---------------------------------------------------------------------------
# Wizard status tab-key label routed through tr()
# ---------------------------------------------------------------------------


def test_wizard_status_label_uses_tr() -> None:
    """wizard/_commands.py must use tr() for the status tab-key label."""
    commands_path = _SRC_ROOT / "application" / "wizard" / "_commands.py"
    source = commands_path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(commands_path))

    # Walk for the specific string constant "status" passed bare to echo
    bare_status_in_fstring: list[int] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if not (isinstance(func, ast.Attribute) and func.attr == "echo"):
            continue
        for arg in node.args:
            if not isinstance(arg, ast.JoinedStr):
                continue
            for part in arg.values:
                # A bare "status\t" constant — not inside a tr() call node
                if isinstance(part, ast.Constant) and isinstance(part.value, str) and part.value.startswith("status"):
                    bare_status_in_fstring.append(node.lineno)

    assert not bare_status_in_fstring, (
        f"wizard/_commands.py lines {bare_status_in_fstring} still use bare 'status' "
        "literal in echo f-string — wrap with tr('application.wizard.output_labels.status')"
    )


def test_wizard_status_locale_key_exists_in_all_locales() -> None:
    """The key application.wizard.output_labels.status must exist in all locale files."""
    locales_dir = _SRC_ROOT / "locales"
    for locale_file in sorted(locales_dir.glob("*.yml")):
        content = locale_file.read_text(encoding="utf-8")
        # Locate the output_labels block and verify status: appears within it
        idx = content.find("output_labels:")
        assert idx != -1, f"{locale_file.name}: output_labels block missing"
        block = content[idx : idx + 300]
        assert "status:" in block, f"{locale_file.name}: application.wizard.output_labels.status key missing"


# ---------------------------------------------------------------------------
# Wizard f-string dynamic dispatch documented in _ast_scanner
# ---------------------------------------------------------------------------


def test_wizard_root_in_dynamic_translation_roots() -> None:
    """'wizard' must appear in _ast_scanner._DYNAMIC_TRANSLATION_ROOTS."""
    from ..locales._ast_scanner import _DYNAMIC_TRANSLATION_ROOTS

    assert "wizard" in _DYNAMIC_TRANSLATION_ROOTS, (
        "'wizard' is not in _DYNAMIC_TRANSLATION_ROOTS — catalogue f-string dynamic-dispatch survivors are undocumented"
    )


def test_catalogue_fstring_prefixes_detected_by_scanner() -> None:
    """The AST scanner must emit namespace markers for wizard.setup.* f-strings in _catalogue.py."""
    catalogue_path = _SRC_ROOT / "application" / "wizard" / "_catalogue.py"
    source = catalogue_path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(catalogue_path))

    # Import the internal function directly to scan just the catalogue module
    from ..locales._ast_scanner import _extract_fstring_prefixes

    markers = _extract_fstring_prefixes(tree)
    wizard_markers = {m for m in markers if m.startswith("wizard.")}
    assert wizard_markers, (
        "No wizard.* namespace markers detected in _catalogue.py — "
        "f-string dynamic-dispatch sites are not being picked up by the scanner"
    )


# ---------------------------------------------------------------------------
# Google API TypedDicts are importable and structurally correct
# ---------------------------------------------------------------------------


def test_google_api_typeddicts_importable() -> None:
    """GoogleDriveFile, GoogleSheetsRange, GoogleSpreadsheet must be importable from _api."""
    from ..adapters.outbound.google._api import (
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
    from ..adapters.outbound.google._api import GoogleDriveFile

    assert "id" in GoogleDriveFile.__required_keys__, "GoogleDriveFile.id is not marked as required"


def test_google_sheets_range_required_range_field() -> None:
    """GoogleSheetsRange must declare 'range' as a required key."""
    from ..adapters.outbound.google._api import GoogleSheetsRange

    assert "range" in GoogleSheetsRange.__required_keys__, "GoogleSheetsRange.range is not marked as required"


def test_google_spreadsheet_required_spreadsheet_id_field() -> None:
    """GoogleSpreadsheet must declare 'spreadsheetId' as a required key."""
    from ..adapters.outbound.google._api import GoogleSpreadsheet

    assert "spreadsheetId" in GoogleSpreadsheet.__required_keys__, (
        "GoogleSpreadsheet.spreadsheetId is not marked as required"
    )


# ---------------------------------------------------------------------------
# OAuthClientPayload TypedDict + _OAuthClientWrapper pydantic model
# ---------------------------------------------------------------------------


def test_oauth_client_payload_typeddict_importable() -> None:
    """OAuthClientPayload TypedDict must be importable from cli._config._google."""
    from ..entrypoints.cli._config._google import OAuthClientPayload

    assert hasattr(OAuthClientPayload, "__annotations__")
    assert "installed" in OAuthClientPayload.__annotations__


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
        }
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
    from ..application.invoices._importing import InvoiceRowPayload

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
            }
        ]
    )
    rows = _decode_invoice_payload(raw)
    assert len(rows) == 1
    row = rows[0]
    # TypedDict at runtime is just a dict — verify field access works
    assert row.get("kind") == "received"
    assert row.get("currency") == "EUR"


def test_parse_invoice_payload_end_to_end_json() -> None:
    """parse_invoice_payload must produce a validated Invoice from a complete JSON row."""
    from ..application.invoices._importing import parse_invoice_payload
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
                }
            ],
        }
    )
    invoices = parse_invoice_payload(raw, default_kind="received")
    assert len(invoices) == 1
    assert isinstance(invoices[0], Invoice)
    assert invoices[0].invoice_number == "F2024-001"


# ---------------------------------------------------------------------------
# Orphan __init__ modules carry intent documentation
# ---------------------------------------------------------------------------


def test_application_storage_init_has_intent_docstring() -> None:
    """aeat.application.storage.__init__ must document its namespace-container intent."""
    init_path = _SRC_ROOT / "application" / "storage" / "__init__.py"
    content = init_path.read_text(encoding="utf-8")
    assert "namespace" in content.lower(), (
        "aeat.application.storage.__init__ is docstring-only and must document its namespace-container intent"
    )


def test_domain_calculations_init_has_intent_docstring() -> None:
    """aeat.domain.calculations.__init__ must document its namespace-container intent."""
    init_path = _SRC_ROOT / "domain" / "calculations" / "__init__.py"
    content = init_path.read_text(encoding="utf-8")
    assert "namespace" in content.lower(), (
        "aeat.domain.calculations.__init__ is docstring-only and must document its namespace-container intent"
    )


def test_application_storage_init_has_no_explicit_imports() -> None:
    """aeat.application.storage.__init__ must contain no import statements."""
    init_path = _SRC_ROOT / "application" / "storage" / "__init__.py"
    content = init_path.read_text(encoding="utf-8")
    tree = ast.parse(content, filename=str(init_path))
    import_nodes = [node for node in ast.walk(tree) if isinstance(node, (ast.Import, ast.ImportFrom))]
    assert not import_nodes, (
        f"aeat.application.storage.__init__ contains {len(import_nodes)} import statement(s) "
        "— this is a namespace container and must not re-export anything"
    )


def test_domain_calculations_init_has_no_explicit_imports() -> None:
    """aeat.domain.calculations.__init__ must contain no import statements."""
    init_path = _SRC_ROOT / "domain" / "calculations" / "__init__.py"
    content = init_path.read_text(encoding="utf-8")
    tree = ast.parse(content, filename=str(init_path))
    import_nodes = [node for node in ast.walk(tree) if isinstance(node, (ast.Import, ast.ImportFrom))]
    assert not import_nodes, (
        f"aeat.domain.calculations.__init__ contains {len(import_nodes)} import statement(s) "
        "— this is a namespace container and must not re-export anything"
    )

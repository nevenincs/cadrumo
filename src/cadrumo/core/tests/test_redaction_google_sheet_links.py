"""Only canonical Sheet success links survive; credentials and logs stay redacted."""

import pytest

from ..redaction.rules import redact_for_cli_output, redact_for_log, redact_structured_for_cli_output

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]
_ID = "synthetic_Sheet-identity_abcdefghijklmnopqrst"
_URL = f"https://docs.google.com/spreadsheets/d/{_ID}/edit"


def test_structured_success_preserves_link_only_with_matching_sibling_id() -> None:
    payload = {"publication": {"spreadsheet_id": _ID, "spreadsheet_url": _URL}}
    assert redact_structured_for_cli_output(payload) == payload
    for sibling in ({}, {"spreadsheet_id": "another_sheet_identity"}):
        redacted = redact_structured_for_cli_output({**sibling, "spreadsheet_url": _URL})
        assert redacted["spreadsheet_url"] == "https://docs.google.com"


def test_exact_text_success_line_preserves_copyable_link() -> None:
    assert redact_for_cli_output(f"spreadsheet_url\t{_URL}") == f"spreadsheet_url\t{_URL}"
    assert redact_for_cli_output(_URL) == "https://docs.google.com"
    assert redact_for_cli_output(f"callback\t{_URL}") == "callback\thttps://docs.google.com"


@pytest.mark.parametrize(
    "url",
    [
        _URL + "?code=private-code",
        _URL + "#access_token=private-token",
        _URL.replace("https://", "http://"),
        _URL.replace("docs.google.com", "docs.google.com.evil.test"),
        _URL.replace("docs.google.com", "evil.test"),
        _URL.replace("docs.google.com", "user:password@docs.google.com"),
        _URL.replace("docs.google.com", "docs.google.com:443"),
        _URL.replace("/edit", "/export"),
        _URL.replace(_ID, "a" * 201),
        _URL.replace(_ID, "bad%2Fidentity"),
        _URL + "\nprivate-content",
        "https://accounts.google.com/o/oauth2/auth?code=private-code",
        "http://127.0.0.1:45678/?code=private-code&state=private-state",
    ],
)
def test_modified_or_credential_bearing_urls_never_receive_success_exemption(url: str) -> None:
    payload = {"spreadsheet_id": _ID, "spreadsheet_url": url}
    assert redact_structured_for_cli_output(payload)["spreadsheet_url"] != url
    assert redact_for_cli_output(f"spreadsheet_url\t{url}") != f"spreadsheet_url\t{url}"
    assert "private-code" not in redact_for_cli_output(f"spreadsheet_url\t{url}")


def test_logs_and_error_text_keep_host_only_even_for_canonical_link() -> None:
    assert redact_for_log(_URL) == "https://docs.google.com"
    assert redact_for_log(f"spreadsheet_url\t{_URL}") == "spreadsheet_url\thttps://docs.google.com"
    assert redact_structured_for_cli_output({"callback": _URL}) == {"callback": "https://docs.google.com"}

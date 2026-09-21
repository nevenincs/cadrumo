"""Focused tests for installed CLI receipt parsing."""

from __future__ import annotations

from ..cli_journey import _decode_cli_document


def test_cli_document_decoder_recovers_error_envelope_after_stderr_diagnostic() -> None:
    document = _decode_cli_document(
        "",
        'diagnostic before envelope\n{"schema_version":"2","status":"error","error":{"code":"REFUSED"}}\n',
    )

    assert document["status"] == "error"
    assert document["error"]["code"] == "REFUSED"

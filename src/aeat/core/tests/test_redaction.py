from __future__ import annotations

import pytest

from ..classification import (
    OutputSensitivityClass,
    SensitivityClass,
    default_output_policy_for,
    default_policy_for,
)
from ..redaction import (
    CLI_BUCKET_ID_PLACEHOLDER,
    CLI_OBJECT_KEY_PLACEHOLDER,
    CLI_PROFILE_ID_PLACEHOLDER,
    redact_for_cli_output,
    redact_structured_for_cli_output,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_PROFILE_ID = "123e4567-e89b-12d3-a456-426614174000"
# A UUID whose first segment (``1470176e`` = 7 digits + a letter) matches the
# NIF pattern; the reveal opt-out must emit it verbatim, not NIF-hashed.
_NIF_SHAPED_UUID = "1470176e-780c-46df-8b21-c6f540f142a0"
_NIF = "12345678Z"
_JWT = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.aaaaaaaaaaaa.bbbbbbbbbbbb"
_URL = "https://example.test/private/path?token=secret"
_OBJECT_KEY = "wallet:2026-secret"
_OTHER_OBJECT_KEY = "wallet:2026-other"


def test_cli_output_text_redacts_sensitive_canaries() -> None:
    rendered = redact_for_cli_output(
        " ".join(
            (
                f"profile_id={_PROFILE_ID}",
                f"target_profile_id\t{_PROFILE_ID}",
                "source_profile_id\toperator",
                "active_profile=operator",
                "bucket_id=bucket-alpha",
                f"nif={_NIF}",
                f"bearer {_JWT}",
                f"url={_URL}",
                f"object_key={_OBJECT_KEY}",
            ),
        ),
    )

    assert _PROFILE_ID not in rendered
    assert _NIF not in rendered
    assert _JWT not in rendered
    assert _URL not in rendered
    assert _OBJECT_KEY not in rendered
    assert f"profile_id={CLI_PROFILE_ID_PLACEHOLDER}" in rendered
    assert f"target_profile_id\t{CLI_PROFILE_ID_PLACEHOLDER}" in rendered
    assert f"source_profile_id\t{CLI_PROFILE_ID_PLACEHOLDER}" in rendered
    assert "active_profile=operator" in rendered
    assert f"bucket_id={CLI_BUCKET_ID_PLACEHOLDER}" in rendered
    assert f"object_key={CLI_OBJECT_KEY_PLACEHOLDER}" in rendered
    assert "https://example.test" in rendered
    assert "private/path" not in rendered
    assert "sha256:" in rendered
    assert "token:sha256:" in rendered


def test_cli_output_structured_redacts_keyed_values_and_string_leaves() -> None:
    payload = {
        "profile_id": _PROFILE_ID,
        "active_profile": _PROFILE_ID,
        "bucket_id": "bucket-alpha",
        "object_key": _OBJECT_KEY,
        "label": "operator",
        "display": {"active_profile": "operator"},
        "nested": {
            _PROFILE_ID: "profile keyed",
            _NIF: "tax keyed",
            _URL: "url keyed",
            f"bearer {_JWT}": "token keyed",
            _OBJECT_KEY: "object keyed",
            _OTHER_OBJECT_KEY: "second object keyed",
            "tax_id": _NIF,
            "callback": _URL,
            "authorization": f"bearer {_JWT}",
            "notes": ("attachment:raw-key", "public note"),
        },
    }

    redacted = redact_structured_for_cli_output(payload)

    assert redacted == {
        "profile_id": CLI_PROFILE_ID_PLACEHOLDER,
        "active_profile": CLI_PROFILE_ID_PLACEHOLDER,
        "bucket_id": CLI_BUCKET_ID_PLACEHOLDER,
        "object_key": CLI_OBJECT_KEY_PLACEHOLDER,
        "label": "operator",
        "display": {"active_profile": "operator"},
        "nested": {
            CLI_PROFILE_ID_PLACEHOLDER: "profile keyed",
            "sha256:1c9f9632": "tax keyed",
            "https://example.test": "url keyed",
            "token:sha256:0a2c77ea": "token keyed",
            CLI_OBJECT_KEY_PLACEHOLDER: "object keyed",
            f"{CLI_OBJECT_KEY_PLACEHOLDER}#2": "second object keyed",
            "tax_id": "sha256:1c9f9632",
            "callback": "https://example.test",
            "authorization": "token:sha256:0a2c77ea",
            "notes": (CLI_OBJECT_KEY_PLACEHOLDER, "public note"),
        },
    }
    assert payload["profile_id"] == _PROFILE_ID
    assert payload["nested"]["notes"][0] == "attachment:raw-key"
    assert payload["nested"][_OTHER_OBJECT_KEY] == "second object keyed"


def test_cli_public_output_policy_is_emit_only_while_diagnostic_persists() -> None:
    cli_policy = default_output_policy_for(OutputSensitivityClass.CLI_PUBLIC)
    diagnostic_output_policy = default_output_policy_for(OutputSensitivityClass.DIAGNOSTIC)
    diagnostic_storage_policy = default_policy_for(SensitivityClass.DIAGNOSTIC)

    assert cli_policy.persisted_as is None
    assert diagnostic_output_policy.persisted_as is SensitivityClass.DIAGNOSTIC
    assert diagnostic_output_policy.redaction_rules == diagnostic_storage_policy.redaction_rules


def test_cli_output_text_does_not_corrupt_tabular_column_header() -> None:
    """A tab-delimited column header must survive the identifier redactor.

    The ``filing-record list`` header places ``bucket_id`` immediately before
    the ``modelo`` column name. The ``label<TAB>value`` heuristic previously
    rewrote ``modelo`` into ``<bucket-id>``, corrupting the header. The header
    carries no values and must pass through verbatim.
    """

    header = "filing_record_id\tbucket_id\tmodelo\tyear\tperiod\tstatus\tfiled_at\tfiled_by"

    rendered = redact_for_cli_output(header)

    assert rendered == header
    assert "\tmodelo\t" in rendered
    assert CLI_BUCKET_ID_PLACEHOLDER not in rendered


def test_cli_output_text_still_redacts_two_cell_key_value_rows() -> None:
    """The header guard must not weaken redaction of genuine ``key<TAB>value`` rows."""

    rendered = redact_for_cli_output(f"bucket_id\t{_PROFILE_ID}")

    assert _PROFILE_ID not in rendered
    assert rendered == f"bucket_id\t{CLI_BUCKET_ID_PLACEHOLDER}"


def test_cli_output_reveal_identifiers_unredacts_only_profile_and_bucket() -> None:
    """The reveal opt-out exposes profile/bucket ids but keeps PII and keys redacted."""

    line = " ".join(
        (
            f"profile_id={_PROFILE_ID}",
            f"bucket_id\t{_PROFILE_ID}",
            f"nif={_NIF}",
            f"object_key={_OBJECT_KEY}",
            f"url={_URL}",
        ),
    )

    revealed = redact_for_cli_output(line, reveal_identifiers=True)

    assert f"profile_id={_PROFILE_ID}" in revealed
    assert f"bucket_id\t{_PROFILE_ID}" in revealed
    assert CLI_PROFILE_ID_PLACEHOLDER not in revealed
    assert CLI_BUCKET_ID_PLACEHOLDER not in revealed
    # Identity, secure-object keys, and URL paths stay redacted regardless.
    assert _NIF not in revealed
    assert "sha256:" in revealed
    assert _OBJECT_KEY not in revealed
    assert CLI_OBJECT_KEY_PLACEHOLDER in revealed
    assert "private/path" not in revealed


def test_cli_output_structured_reveal_identifiers_unredacts_only_profile_and_bucket() -> None:
    """JSON-shaped reveal exposes profile/bucket ids and keeps PII / keys redacted."""

    payload = {
        "profile_id": _PROFILE_ID,
        "bucket_id": _PROFILE_ID,
        "object_key": _OBJECT_KEY,
        "tax_id": _NIF,
        "callback": _URL,
        "modelo": "130",
    }

    default_redacted = redact_structured_for_cli_output(payload)
    revealed = redact_structured_for_cli_output(payload, reveal_identifiers=True)

    assert default_redacted["profile_id"] == CLI_PROFILE_ID_PLACEHOLDER
    assert default_redacted["bucket_id"] == CLI_BUCKET_ID_PLACEHOLDER

    assert revealed["profile_id"] == _PROFILE_ID
    assert revealed["bucket_id"] == _PROFILE_ID
    assert revealed["modelo"] == "130"
    # Object key, tax id, and URL stay redacted in the reveal path.
    assert revealed["object_key"] == CLI_OBJECT_KEY_PLACEHOLDER
    assert revealed["tax_id"] != _NIF
    assert revealed["tax_id"].startswith("sha256:")
    assert revealed["callback"] == "https://example.test"


def test_cli_output_reveal_keeps_nif_shaped_uuid_verbatim() -> None:
    """A revealed bucket/profile UUID must not be NIF-hashed in text or JSON.

    The first UUID segment ``1470176e`` matches the NIF pattern. The reveal
    opt-out parks the value behind a sentinel so the downstream free-text passes
    cannot corrupt it.
    """

    text = redact_for_cli_output(
        f"bucket_id\t{_NIF_SHAPED_UUID} nif={_NIF}",
        reveal_identifiers=True,
    )
    assert f"bucket_id\t{_NIF_SHAPED_UUID}" in text
    assert "sha256:e03f" not in text  # the NIF-hash of the UUID segment
    assert "nif=sha256:" in text  # the genuine NIF is still hashed

    structured = redact_structured_for_cli_output(
        {"bucket_id": _NIF_SHAPED_UUID, "profile_id": _NIF_SHAPED_UUID},
        reveal_identifiers=True,
    )
    assert structured == {"bucket_id": _NIF_SHAPED_UUID, "profile_id": _NIF_SHAPED_UUID}

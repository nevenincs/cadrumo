from __future__ import annotations

import hashlib

import pytest

from ..classification import (
    OutputSensitivityClass,
    RedactionRule,
    RedactionStrategy,
    SensitivityClass,
    default_output_policy_for,
    default_policy_for,
)
from ..redaction import (
    CLI_BUCKET_ID_PLACEHOLDER,
    CLI_OBJECT_KEY_PLACEHOLDER,
    CLI_PROFILE_ID_PLACEHOLDER,
    default_rules_for_class,
    redact,
    redact_for_cli_output,
    redact_structured,
    redact_structured_for_cli_output,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_PROFILE_ID = "986c0dc9-56dc-422b-9d8f-698661b9eb1e"  # was '123e4567-e89b-12d3-a456-426614174000'
# A UUID whose first segment (``1470176e`` = 7 digits + a letter) matches the
# NIF pattern; the reveal opt-out must emit it verbatim, not NIF-hashed.
_NIF_SHAPED_UUID = "1470176e-780c-46df-8b21-c6f540f142a0"
_NIF = "12345678Z"
# Entity tax identities carrying the check character AEAT's algorithm
# computes, and a same-shaped reference that does not (an invoice number
# ``F1234567B`` is exactly the CIF shape).
_CIF = "B12345674"
_CIF_OTHER = "A58818501"
_CIF_LOOKALIKE = "F1234567B"
# Bank accounts across countries -- foreign accounts are declarable, so the
# arm is not ES-only. ``_IBAN_BAD_CHECKSUM`` carries the IBAN shape with
# check digits that fail mod-97, and ``_HEX_DIGEST`` is a real 32-character
# digest lifted from the bundled corpus: both are the collision class a
# shape-only bank-account pattern would swallow.
_IBAN_ES = "ES7921000813610123456789"
_IBAN_DE = "DE89370400440532013000"
_IBAN_GB = "GB29NWBK60161331926819"
_IBAN_BAD_CHECKSUM = "ES9921000418450200051332"
_HEX_DIGEST = "EB58612F0394953A4B516B938AD3FEB1"
# Operator ruling, recorded as a standing negative control: "ibans are
# sensitive, boe citations are not". A legal citation must reach the operator
# intact, so a pattern that starts hashing one is too wide by definition.
_BOE_CITATION = "BOE-A-2024-26694"
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


def test_cli_output_text_bucket_id_tabular_heuristic_cases() -> None:
    """Headers pass through, but genuine ``key<TAB>value`` rows still redact."""

    for line, expected, forbidden in (
        (
            "filing_record_id\tbucket_id\tmodelo\tyear\tperiod\tstatus\tfiled_at\tfiled_by",
            "filing_record_id\tbucket_id\tmodelo\tyear\tperiod\tstatus\tfiled_at\tfiled_by",
            (CLI_BUCKET_ID_PLACEHOLDER,),
        ),
        (
            f"bucket_id\t{_PROFILE_ID}",
            f"bucket_id\t{CLI_BUCKET_ID_PLACEHOLDER}",
            (_PROFILE_ID,),
        ),
    ):
        rendered = redact_for_cli_output(line)

        assert rendered == expected
        for fragment in forbidden:
            assert fragment not in rendered


def test_cli_output_history_row_redacts_nif_shaped_uuid_as_one_identifier() -> None:
    """A bare history-row UUID becomes one profile placeholder before NIF redaction."""

    line = f"2026-01-01T00:00:00+00:00\tCREATED\tPROFILE\t{_NIF_SHAPED_UUID}\toperator"

    rendered = redact_for_cli_output(line)

    assert rendered == (f"2026-01-01T00:00:00+00:00\tCREATED\tPROFILE\t{CLI_PROFILE_ID_PLACEHOLDER}\toperator")
    assert "sha256:<profile-id>" not in rendered


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

    revealed_text = redact_for_cli_output(line, reveal_identifiers=True)

    assert f"profile_id={_PROFILE_ID}" in revealed_text
    assert f"bucket_id\t{_PROFILE_ID}" in revealed_text
    assert CLI_PROFILE_ID_PLACEHOLDER not in revealed_text
    assert CLI_BUCKET_ID_PLACEHOLDER not in revealed_text
    # Identity, secure-object keys, and URL paths stay redacted regardless.
    assert _NIF not in revealed_text
    assert "sha256:" in revealed_text
    assert _OBJECT_KEY not in revealed_text
    assert CLI_OBJECT_KEY_PLACEHOLDER in revealed_text
    assert "private/path" not in revealed_text

    payload = {
        "profile_id": _PROFILE_ID,
        "bucket_id": _PROFILE_ID,
        "object_key": _OBJECT_KEY,
        "tax_id": _NIF,
        "callback": _URL,
        "modelo": "130",
    }

    default_redacted = redact_structured_for_cli_output(payload)
    revealed_structured = redact_structured_for_cli_output(payload, reveal_identifiers=True)

    assert default_redacted["profile_id"] == CLI_PROFILE_ID_PLACEHOLDER
    assert default_redacted["bucket_id"] == CLI_BUCKET_ID_PLACEHOLDER

    assert revealed_structured["profile_id"] == _PROFILE_ID
    assert revealed_structured["bucket_id"] == _PROFILE_ID
    assert revealed_structured["modelo"] == "130"
    # Object key, tax id, and URL stay redacted in the reveal path.
    assert revealed_structured["object_key"] == CLI_OBJECT_KEY_PLACEHOLDER
    revealed_tax_id = revealed_structured["tax_id"]
    assert isinstance(revealed_tax_id, str)
    assert revealed_tax_id != _NIF
    assert revealed_tax_id.startswith("sha256:")
    assert revealed_structured["callback"] == "https://example.test"

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


# ── entity tax identity (CIF) ───────────────────────────────────────────────


def _expected_sha256_prefix(value: str) -> str:
    """Derive the documented ``SHA256_PREFIX`` form independently of the rules.

    Computed here from the strategy's stated contract — the first eight hex
    characters of the value's SHA-256 digest — rather than copied from an
    observed run, so a change to how the redactor derives the digest fails
    this test instead of being ratified by it.
    """
    return f"sha256:{hashlib.sha256(value.encode('utf-8')).hexdigest()[:8]}"


def test_cli_output_hashes_an_entity_tax_identity() -> None:
    """A sociedad's CIF is hashed exactly as a natural person's NIF is.

    The two arrive on the same field (``identity.tax_id``) and reach the
    same export header, so protecting one and not the other would make the
    operator's entity type decide their privacy.
    """
    for cif in (_CIF, _CIF.lower(), _CIF_OTHER):
        redacted = redact_for_cli_output(f"tax_id={cif}")
        assert cif not in redacted
        assert redacted == f"tax_id={_expected_sha256_prefix(cif)}"


def test_cli_output_leaves_a_cif_shaped_document_reference_verbatim() -> None:
    """A lookalike that fails its check character is not an identity.

    The CIF shape is letter-led over fifteen letters, which is also the
    shape of an ordinary document reference. Hashing those would make a
    ledger row unidentifiable to the operator to protect nothing, so the
    check character is what admits a match.
    """
    for lookalike in (_CIF_LOOKALIKE, "B12345678", "A12345678"):
        assert redact_for_cli_output(f"ref={lookalike}") == f"ref={lookalike}"


# ── bank accounts (operator ruling) ─────────────────────────────────────────


def test_cli_output_hashes_a_bank_account_in_any_country() -> None:
    """An IBAN is hashed whether the account is Spanish or foreign.

    Foreign accounts are declarable in this domain, so an ES-only arm would
    protect the domestic case and leak the one a taxpayer holds abroad.
    """
    for iban in (_IBAN_ES, _IBAN_DE, _IBAN_GB):
        redacted = redact_for_cli_output(f"cuenta={iban}")
        assert iban not in redacted
        assert redacted == f"cuenta={_expected_sha256_prefix(iban)}"


def test_a_boe_citation_survives_the_funnel_untouched() -> None:
    """A legal citation must reach the operator intact.

    The standing negative control for every identifier pattern here, not an
    incidental case: a citation is how an operator checks the law behind a
    number, and a pattern wide enough to hash one is too wide by definition.

    A citation is held out by SHAPE rather than by any checksum -- it never
    matches in the first place -- so this case guards against a future
    widening of the pattern itself, which is a different failure from the
    checksum gate the next test covers.
    """
    assert redact_for_cli_output(f"ref={_BOE_CITATION}") == f"ref={_BOE_CITATION}"
    assert redact_for_cli_output(f"see {_BOE_CITATION} art. 29") == f"see {_BOE_CITATION} art. 29"


def test_bank_account_lookalikes_that_fail_the_checksum_survive() -> None:
    """The mod-97 gate, not the shape, is what admits a bank account.

    Both survivors carry the IBAN shape exactly: one is a real 32-character
    hex digest taken from the bundled corpus, the other has check digits that
    fail mod-97. A shape-only pattern would hash each into unidentifiability,
    which is the cost that made matching on the checksum worth it.
    """
    for survivor in (_IBAN_BAD_CHECKSUM, _HEX_DIGEST):
        assert redact_for_cli_output(f"ref={survivor}") == f"ref={survivor}"


def test_redacting_an_already_redacted_line_changes_nothing() -> None:
    """Redaction is idempotent, which the LLM cache relies on when re-read.

    A digest that a later rule matched again would corrupt a stored payload
    on every subsequent read, so the property is asserted rather than assumed.
    """
    line = f"nif={_NIF} cif={_CIF} iban={_IBAN_ES} ref={_BOE_CITATION}"
    once = redact_for_cli_output(line)
    assert redact_for_cli_output(once) == once
    for raw in (_NIF, _CIF, _IBAN_ES):
        assert raw not in once
    assert _BOE_CITATION in once


def test_cif_rule_is_enrolled_in_every_policy_that_carries_the_nif_rule() -> None:
    """Enrolment is the only thing that makes a rule reachable.

    A rule resolves through the policy's ``redaction_rules`` name tuple, so
    a rule declared but never enrolled is inert everywhere — which is how a
    CIF reached the log, error, and LLM-cache paths in cleartext while the
    rule catalogue claimed to cover it.
    """
    for sensitivity in SensitivityClass:
        names = {rule.name for rule in default_rules_for_class(sensitivity)}
        if "nif-hash" in names:
            assert "cif-hash" in names, f"{sensitivity.name} hashes a NIF but not a CIF"
            assert "iban-hash" in names, f"{sensitivity.name} hashes a NIF but not a bank account"


def test_structured_redaction_hashes_a_cif_leaf() -> None:
    """The structured path is the one that reaches persisted artefacts.

    The LLM disk cache redacts through this path before materializing its
    JSON file, so a leaf the rules miss is written to disk in cleartext.
    """
    redacted = redact_structured(
        {
            "party_tax_id": _CIF,
            "refund_iban": _IBAN_ES,
            "note": f"invoice {_CIF_LOOKALIKE} under {_BOE_CITATION}",
        },
        rules=default_rules_for_class(SensitivityClass.DIAGNOSTIC),
    )
    assert redacted == {
        "party_tax_id": _expected_sha256_prefix(_CIF),
        "refund_iban": _expected_sha256_prefix(_IBAN_ES),
        "note": f"invoice {_CIF_LOOKALIKE} under {_BOE_CITATION}",
    }


def test_structured_redaction_hashes_a_tax_id_written_as_a_mapping_key() -> None:
    """A key is as readable as a value once the JSON is on disk.

    The gap this pins was latent rather than live: the walker redacted
    dict values and skipped dict keys, and no payload model on the
    observability or LLM-cache path declares a ``dict[str, ...]`` field,
    so nothing exercised it. A single added field keyed by anything
    taxpayer-derived would have written cleartext into the persisted
    artefact while the value beside it was hashed.
    """
    redacted = redact_structured(
        {_NIF: "seen", _IBAN_ES: {"nested": _CIF}},
        rules=default_rules_for_class(SensitivityClass.DIAGNOSTIC),
    )
    assert redacted == {
        _expected_sha256_prefix(_NIF): "seen",
        _expected_sha256_prefix(_IBAN_ES): {"nested": _expected_sha256_prefix(_CIF)},
    }
    assert _NIF not in repr(redacted)
    assert _IBAN_ES not in repr(redacted)


def test_structured_redaction_keeps_two_colliding_keys_distinct() -> None:
    """A redacted log must not lose an entry to a key collision.

    Hashing rules keep distinct inputs distinct, but the collapsing
    strategies do not: ``HOST_ONLY`` maps every URL sharing a host onto
    that host, and ``ELLIPSIS`` maps every match onto one string. Letting
    the second key overwrite the first would silently drop a record from
    a diagnostic artefact, so the duplicate is suffixed instead.
    """
    host_only = RedactionRule(
        name="host-only",
        pattern=r"https?://\S+",
        strategy=RedactionStrategy.HOST_ONLY,
    )
    redacted = redact_structured(
        {"https://aeat.es/expediente/a": 1, "https://aeat.es/expediente/b": 2},
        rules=(host_only,),
    )
    assert len(redacted) == 2, f"a colliding key overwrote another entry: {redacted}"
    assert set(redacted.values()) == {1, 2}

    ellipsis = RedactionRule(name="ellipsis", pattern=r"secret-\w+", strategy=RedactionStrategy.ELLIPSIS)
    collapsed = redact_structured({"secret-alpha": 1, "secret-beta": 2}, rules=(ellipsis,))
    assert len(collapsed) == 2, f"a colliding key overwrote another entry: {collapsed}"


def test_iso_instant_survives_the_diagnostic_funnel_unchanged() -> None:
    """A serialised UTC timestamp is not a tax identity.

    ``model_dump(mode="json")`` writes the ``Z``-suffixed fractional form, and
    its seconds-plus-microseconds field is a valid NIF by shape AND by check
    character -- so the rule hashed it, the stamp stopped parsing, and every
    model that re-validated it on the way to storage refused the record.
    """
    rules = default_rules_for_class(SensitivityClass.DIAGNOSTIC)

    for stamp in (
        "2026-08-08T09:32:12.345678Z",
        "2026-08-08T09:32:12.345678+00:00",
        "2026-08-08T09:32:12Z",
        "2026-08-08 09:32:12.345678Z",
    ):
        assert redact(stamp, rules=rules) == stamp, f"the funnel corrupted the timestamp {stamp!r}"


def test_identities_beside_a_timestamp_are_still_redacted() -> None:
    """Positive control: the exemption covers the stamp, not the line."""
    rules = default_rules_for_class(SensitivityClass.DIAGNOSTIC)

    line = "2026-08-08T09:32:12.345678Z declarante 12345678Z presented the filing"
    redacted = redact(line, rules=rules)

    assert "2026-08-08T09:32:12.345678Z" in redacted, "the timestamp must survive"
    assert "12345678Z" not in redacted, "a real identity beside a timestamp must still be redacted"
    assert "sha256:" in redacted, "the identity must be replaced by its hash"

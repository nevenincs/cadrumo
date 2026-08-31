"""Tests for EnvelopeDocument boundary validation at the master-key layer.

:class:`EnvelopeDocument` wraps the ``json.loads`` result in
:func:`_extract_profile_tax_ids` with a typed Pydantic model.  These
tests assert:

- A well-formed envelope JSON validates and exposes typed fields.
- Malformed or missing JSON raises ``ValidationError`` via
  ``model_validate_json``.
- ``_extract_profile_tax_ids`` correctly extracts ``identity.tax_id``
  facts from a real envelope byte payload.
- Malformed bytes cause ``_extract_profile_tax_ids`` to return ``None``
  rather than raising.
"""

from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from ..master_key import EnvelopeDocument, _extract_profile_tax_ids

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]


def _make_envelope_bytes(payload: object) -> bytes:
    """Serialise an envelope dict to UTF-8 JSON bytes."""
    return json.dumps({"payload": payload}, ensure_ascii=False).encode("utf-8")


class TestEnvelopeDocumentValidation:
    """``EnvelopeDocument`` accepts well-formed envelopes and rejects malformed ones."""

    def test_validates_full_envelope(self) -> None:
        raw = _make_envelope_bytes(
            {
                "facts": [
                    {"path": "identity.tax_id", "value": "12345678Z"},
                    {"path": "identity.name", "value": "Ana García"},
                ],
            },
        )
        doc = EnvelopeDocument.model_validate_json(raw)
        assert doc.payload is not None
        assert len(doc.payload.facts) == 2
        assert doc.payload.facts[0].path == "identity.tax_id"
        assert doc.payload.facts[0].value == "12345678Z"

    def test_validates_envelope_with_no_payload(self) -> None:
        raw = json.dumps({}).encode("utf-8")
        doc = EnvelopeDocument.model_validate_json(raw)
        assert doc.payload is None

    def test_validates_envelope_with_empty_facts(self) -> None:
        raw = _make_envelope_bytes({"facts": []})
        doc = EnvelopeDocument.model_validate_json(raw)
        assert doc.payload is not None
        assert doc.payload.facts == []

    def test_rejects_non_object_json(self) -> None:
        """A bare JSON array is not a valid envelope document."""
        with pytest.raises(ValidationError):
            EnvelopeDocument.model_validate_json(b"[1, 2, 3]")

    def test_rejects_malformed_json_bytes(self) -> None:
        """Truncated / invalid JSON bytes must raise ValidationError."""
        with pytest.raises((ValidationError, ValueError)):
            EnvelopeDocument.model_validate_json(b"{not valid json")

    def test_rejects_facts_non_list(self) -> None:
        """A ``facts`` field that is not a list must raise ValidationError."""
        raw = _make_envelope_bytes({"facts": "not-a-list"})
        with pytest.raises(ValidationError):
            EnvelopeDocument.model_validate_json(raw)

    def test_fact_missing_path_raises(self) -> None:
        """A fact dict without a ``path`` key must raise ValidationError."""
        raw = _make_envelope_bytes({"facts": [{"value": "12345678Z"}]})
        with pytest.raises(ValidationError):
            EnvelopeDocument.model_validate_json(raw)


class TestExtractProfileTaxIds:
    """``_extract_profile_tax_ids`` correctly parses real envelope bytes."""

    def test_extracts_tax_id_from_valid_envelope(self) -> None:
        raw = _make_envelope_bytes(
            {
                "facts": [
                    {"path": "identity.tax_id", "value": "12345678Z"},
                    {"path": "identity.name", "value": "Pedro"},
                ],
            },
        )
        result = _extract_profile_tax_ids(raw)
        assert result == ("12345678Z",)

    def test_extracts_multiple_tax_ids(self) -> None:
        raw = _make_envelope_bytes(
            {
                "facts": [
                    {"path": "identity.tax_id", "value": "12345678Z"},
                    {"path": "identity.tax_id", "value": "87654321X"},
                ],
            },
        )
        result = _extract_profile_tax_ids(raw)
        assert result == ("12345678Z", "87654321X")

    def test_returns_none_when_no_tax_id_facts(self) -> None:
        raw = _make_envelope_bytes({"facts": [{"path": "identity.name", "value": "María"}]})
        result = _extract_profile_tax_ids(raw)
        assert result is None

    def test_returns_none_when_no_payload(self) -> None:
        raw = json.dumps({}).encode("utf-8")
        result = _extract_profile_tax_ids(raw)
        assert result is None

    def test_returns_none_on_malformed_bytes(self) -> None:
        result = _extract_profile_tax_ids(b"not-json-at-all")
        assert result is None

    def test_returns_none_on_truncated_json(self) -> None:
        result = _extract_profile_tax_ids(b'{"payload": {')
        assert result is None

    def test_returns_none_on_empty_bytes(self) -> None:
        result = _extract_profile_tax_ids(b"")
        assert result is None

    def test_ignores_non_string_tax_id_values(self) -> None:
        """Non-string ``value`` for tax_id facts must be filtered out."""
        raw = _make_envelope_bytes(
            {
                "facts": [
                    {"path": "identity.tax_id", "value": 12345},
                    {"path": "identity.tax_id", "value": "12345678Z"},
                ],
            },
        )
        result = _extract_profile_tax_ids(raw)
        assert result == ("12345678Z",)

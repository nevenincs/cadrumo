"""Focused unit tests for archive._registry key-extractor closures.

Three private closures back the `extract_object_key` slot on every
``payload_field`` :class:`ArchiveAdapter`:

- ``_extract_constant_key(constant)`` — ignores the payload and
  always returns the same constant. Used by namespaces with a
  single record (e.g. invoice catalogue → ``"catalogue"``).
- ``_extract_field(field_name)`` — reads ``payload[field_name]``
  and rejects missing / non-string / empty values.
- ``_extract_first_entry_field(entries_field, entry_field)`` —
  reads ``payload[entries_field][0][entry_field]`` and rejects
  missing / empty list / non-dict entry / missing entry field.

The closures are wired into the built-in adapter registry through
:func:`_register_built_in_adapters`. A regression in any error
branch (e.g. silently returning ``""`` for a missing field instead
of raising :exc:`ArchiveAdapterMissingError`) would surface as a
corrupt archive bundle whose object keys collapse to empty
strings, rather than failing loudly during export.

Tests pin the happy-path return values and the typed error
branches; assertions are structural / error-path assertions, not
calculation tautologies.
"""

from __future__ import annotations

import pytest

from ._errors import ArchiveAdapterMissingError
from ._registry import _extract_constant_key, _extract_field, _extract_first_entry_field

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]


# ---------------------------------------------------------------------------
# _extract_constant_key
# ---------------------------------------------------------------------------


def test_extract_constant_key_ignores_payload_and_returns_constant() -> None:
    extract = _extract_constant_key("catalogue")

    assert extract({}) == "catalogue"
    assert extract({"any": "value"}) == "catalogue"


def test_extract_constant_key_with_different_constants_returns_different_keys() -> None:
    """Each call to the factory captures its own constant; the
    returned closures do not share state."""
    extract_a = _extract_constant_key("alpha")
    extract_b = _extract_constant_key("beta")

    assert extract_a({}) == "alpha"
    assert extract_b({}) == "beta"


def test_extract_constant_key_does_not_raise_on_missing_keys() -> None:
    """A constant extractor must never raise; the payload is
    ignored entirely, including when it lacks fields the namespace's
    other tooling expects."""
    extract = _extract_constant_key("catalogue")

    # Even None-valued or absent fields are fine.
    assert extract({"unrelated_field": None}) == "catalogue"


# ---------------------------------------------------------------------------
# _extract_field
# ---------------------------------------------------------------------------


def test_extract_field_returns_string_value_from_payload() -> None:
    extract = _extract_field("draft_id")

    assert extract({"draft_id": "draft-123"}) == "draft-123"


def test_extract_field_raises_when_key_missing() -> None:
    extract = _extract_field("draft_id")

    with pytest.raises(ArchiveAdapterMissingError, match="draft_id"):
        extract({})


def test_extract_field_raises_when_value_is_none() -> None:
    """A None value is treated as missing — the closure is strict
    against the field's type contract."""
    extract = _extract_field("draft_id")

    with pytest.raises(ArchiveAdapterMissingError, match="draft_id"):
        extract({"draft_id": None})


def test_extract_field_raises_when_value_is_non_string_type() -> None:
    """Numbers, dicts, lists, bools — anything but ``str`` raises."""
    extract = _extract_field("draft_id")

    for non_string in (42, ["draft-123"], {"id": "draft-123"}, True):
        with pytest.raises(ArchiveAdapterMissingError, match="draft_id"):
            extract({"draft_id": non_string})


def test_extract_field_raises_on_empty_string() -> None:
    """The closure rejects the empty string explicitly — an empty
    archive key would round-trip through restore as the empty
    object name, silently merging records."""
    extract = _extract_field("draft_id")

    with pytest.raises(ArchiveAdapterMissingError, match="draft_id"):
        extract({"draft_id": ""})


def test_extract_field_with_different_field_names_returns_different_keys() -> None:
    extract_invoice = _extract_field("invoice_id")
    extract_draft = _extract_field("draft_id")

    payload = {"invoice_id": "inv-1", "draft_id": "draft-1"}
    assert extract_invoice(payload) == "inv-1"
    assert extract_draft(payload) == "draft-1"


# ---------------------------------------------------------------------------
# _extract_first_entry_field
# ---------------------------------------------------------------------------


def test_extract_first_entry_field_returns_field_from_first_entry() -> None:
    extract = _extract_first_entry_field("entries", "modelo")

    payload = {"entries": [{"modelo": "100"}, {"modelo": "303"}]}
    assert extract(payload) == "100"


def test_extract_first_entry_field_raises_when_entries_field_missing() -> None:
    extract = _extract_first_entry_field("entries", "modelo")

    with pytest.raises(ArchiveAdapterMissingError, match="entries"):
        extract({})


def test_extract_first_entry_field_raises_on_empty_list() -> None:
    extract = _extract_first_entry_field("entries", "modelo")

    with pytest.raises(ArchiveAdapterMissingError, match="entries"):
        extract({"entries": []})


def test_extract_first_entry_field_raises_when_entries_is_not_list() -> None:
    """A scalar / dict / string under the entries key violates the
    nested-list contract."""
    extract = _extract_first_entry_field("entries", "modelo")

    for non_list in ("not-a-list", {"modelo": "100"}, 42, None):
        with pytest.raises(ArchiveAdapterMissingError, match="entries"):
            extract({"entries": non_list})


def test_extract_first_entry_field_raises_when_first_entry_is_not_dict() -> None:
    """A non-dict first element (string / number / list) violates
    the nested-object contract."""
    extract = _extract_first_entry_field("entries", "modelo")

    for non_dict in ("not-a-dict", ["modelo"], 42):
        with pytest.raises(ArchiveAdapterMissingError, match="entries"):
            extract({"entries": [non_dict, {"modelo": "100"}]})


def test_extract_first_entry_field_raises_when_inner_field_missing() -> None:
    extract = _extract_first_entry_field("entries", "modelo")

    with pytest.raises(ArchiveAdapterMissingError, match="modelo"):
        extract({"entries": [{"unrelated": "field"}]})


def test_extract_first_entry_field_raises_when_inner_field_value_is_empty() -> None:
    extract = _extract_first_entry_field("entries", "modelo")

    with pytest.raises(ArchiveAdapterMissingError, match="modelo"):
        extract({"entries": [{"modelo": ""}]})


def test_extract_first_entry_field_raises_when_inner_field_value_is_non_string() -> None:
    extract = _extract_first_entry_field("entries", "modelo")

    for non_string in (42, None, ["100"], {"value": "100"}):
        with pytest.raises(ArchiveAdapterMissingError, match="modelo"):
            extract({"entries": [{"modelo": non_string}]})


def test_extract_first_entry_field_only_reads_first_element() -> None:
    """The closure is named ``first_entry_field`` — subsequent
    entries do not affect the result, and a malformed [1] does not
    raise as long as [0] is well-formed."""
    extract = _extract_first_entry_field("entries", "modelo")

    payload = {"entries": [{"modelo": "100"}, "malformed-second-entry"]}
    assert extract(payload) == "100"

"""The persistence boundary for records the UTF-8 encoding ruling changed.

The capsule label is the record that proves the ruling, because it is the one
digest-bound custody record carrying operator-chosen text: a Spanish taxpayer's
profile label routinely holds an eñe or an accent, so it is exactly where an
ASCII-escaping encoder and a UTF-8 one produce different bytes, different
lengths against the same declared ceiling, and different ``self_digest``
values.

These are boundary tests, not encoder tests: each one pushes a populated record
through the real no-follow filesystem primitives the capsule uses and reads it
back, so a save-drops-field or load-re-defaults-field regression cannot hide.
The encoder's own contract is pinned in ``core/tests/test_hashing.py``.
"""

from __future__ import annotations

import json
from pathlib import Path
from uuid import UUID

import pytest

from ......core.hashing import canonical_json_bytes
from .._capsule_records import (
    PROFILE_CUSTODY_LABEL_MAX_BYTES,
    ProfileCustodyCapsuleLabel,
    parse_profile_custody_capsule_label,
)
from ..errors import ProfileCustodyRecordError
from .._filesystem import (
    read_profile_custody_local_record,
    write_profile_custody_local_record,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

_PROFILE_ID = UUID("6f1d5f6a-6f0f-4a1e-9a2e-3c7b8d9e0f11")

#: An operator label exercising the accented characters, the eñe and the
#: ordinal marker a Spanish profile name actually contains.
_ACCENTED_LABEL = "Muñoz Peñaranda — Gestoría 3º Coruña"


def _label(**overrides: object) -> ProfileCustodyCapsuleLabel:
    """Build a label with every defaultable field set to a NON-default value.

    ``label_revision`` and ``previous_label_digest`` both default to their
    first-revision values, so a second revision carrying a real predecessor
    digest is what makes a dropped-on-save field visible.
    """
    first = ProfileCustodyCapsuleLabel.create(profile_id=_PROFILE_ID, label="Primera etiqueta")
    fields: dict[str, object] = {
        "profile_id": _PROFILE_ID,
        "label": _ACCENTED_LABEL,
        "label_revision": 2,
        "previous_label_digest": first.self_digest,
    }
    fields.update(overrides)
    return ProfileCustodyCapsuleLabel.create(**fields)  # type: ignore[arg-type]


def _write_and_read(tmp_path: Path, payload: bytes) -> bytes:
    target = tmp_path / "profile-label.v1.json"
    write_profile_custody_local_record(target, payload, publish_once=True)
    return read_profile_custody_local_record(target, maximum_bytes=PROFILE_CUSTODY_LABEL_MAX_BYTES)


def test_accented_label_round_trips_through_the_real_filesystem_boundary(tmp_path: Path) -> None:
    """Strict equality across a real write and read, every field non-default."""
    record = _label()

    restored = parse_profile_custody_capsule_label(_write_and_read(tmp_path, record.canonical_json_bytes()))

    assert restored == record
    assert restored.label == _ACCENTED_LABEL
    assert restored.label_revision == 2
    assert restored.previous_label_digest is not None


def test_the_accented_label_is_stored_as_utf8_not_ascii_escapes(tmp_path: Path) -> None:
    """The ruling, pinned at the boundary: no ``\\uXXXX`` reaches the disk."""
    record = _label()

    stored = _write_and_read(tmp_path, record.canonical_json_bytes())

    assert "ñ".encode() in stored
    assert b"\\u00f1" not in stored
    assert stored.decode("utf-8").count("\\u") == 0
    # The same record ASCII-escaped is materially longer, so the two encodings
    # cannot share this record's declared byte ceiling.
    escaped = json.dumps(record.model_dump(mode="json"), sort_keys=True, separators=(",", ":")).encode("ascii")
    assert len(escaped) > len(stored)


def test_the_accented_digest_is_stable_across_independent_constructions() -> None:
    """Two constructions of one label agree, so the digest is a property of the value."""
    first = _label()
    second = _label()

    assert first.self_digest == second.self_digest
    assert first.content_digest == second.content_digest
    # Re-validating the record's own canonical bytes re-derives the digest and
    # compares it, so an encoder that stopped agreeing with itself fails here.
    assert ProfileCustodyCapsuleLabel.model_validate_json(first.canonical_json_bytes()) == first


def test_a_label_whose_stored_bytes_lose_a_field_refuses_to_load(tmp_path: Path) -> None:
    """Anti-tautology: delete a persisted field on disk and prove load refuses.

    If this ever passes with the boundary broken, every roundtrip above is
    tautological.
    """
    record = _label()
    document = json.loads(record.canonical_json_bytes().decode("utf-8"))
    del document["previous_label_digest"]

    stored = _write_and_read(tmp_path, canonical_json_bytes(document))

    with pytest.raises(ProfileCustodyRecordError):
        parse_profile_custody_capsule_label(stored)


def test_a_label_re_escaped_to_ascii_on_disk_refuses_to_load(tmp_path: Path) -> None:
    """The old spelling is not read back tolerantly; it is corruption now.

    This is the cutover's teeth. A record written by the previous
    ASCII-escaping encoder decodes to the same *values*, so a lenient reader
    would accept it and silently carry a payload whose bytes no longer
    reproduce its digest.
    """
    record = _label()
    ascii_escaped = json.dumps(
        record.model_dump(mode="json"),
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("ascii")

    assert ascii_escaped != record.canonical_json_bytes()

    stored = _write_and_read(tmp_path, ascii_escaped)

    with pytest.raises(ProfileCustodyRecordError):
        parse_profile_custody_capsule_label(stored)


def test_a_label_carrying_a_duplicate_member_on_disk_refuses_to_load(tmp_path: Path) -> None:
    """The strict decode hooks are wired into the real parse path."""
    record = _label()
    text = record.canonical_json_bytes().decode("utf-8")
    doubled = text.replace('{"content_digest":', '{"label_revision":2,"content_digest":', 1)

    stored = _write_and_read(tmp_path, doubled.encode("utf-8"))

    with pytest.raises(ProfileCustodyRecordError):
        parse_profile_custody_capsule_label(stored)

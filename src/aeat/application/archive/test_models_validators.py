"""Focused unit tests for archive._models pydantic v2 validators.

Three validator branches gate the archive wire format:

- ``ArchiveRecord._require_aware`` on ``written_at`` — rejects
  naive datetimes so the bundle's tz-aware contract holds even
  when the SQLite backend strips tzinfo at the column boundary.
- ``ArchiveRecord._exactly_one_key`` cross-field validator —
  enforces mutual exclusivity between ``object_key`` (natural
  key for payload-keyed adapters) and ``hashed_object_key_b64``
  (HMAC digest for hashed-passthrough adapters). Neither / both
  raises ``ValueError``.
- ``ArchiveBundle._require_aware`` on ``created_at`` — same
  tz-aware contract for the bundle wrapper.

Plus the shared ``_STRICT_FROZEN`` config invariants
(``strict=True, frozen=True, extra="forbid"``) which determine
whether the wire format rejects unexpected fields silently or
loudly. A regression that silently downgraded any of these
invariants (e.g. flipping ``frozen`` to ``False``) would let
in-flight bundle records mutate inside the restore pipeline,
producing inconsistent restore reports against the original
bundle.

Assertions are pydantic-validator-contract assertions, not
calculation tautologies. The branches tested here are exactly
the documented failure surfaces.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest
from pydantic import ValidationError

from ...core.classification import SensitivityClass
from ._models import ArchiveBundle, ArchiveRecord

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]


def _record_kwargs(**overrides: Any) -> dict[str, Any]:
    """Return baseline ArchiveRecord kwargs with optional overrides."""
    base: dict[str, Any] = {
        "namespace": "aeat.domain.invoices",
        "object_key": "catalogue",
        "classification": SensitivityClass.FINANCIAL,
        "schema_version": 1,
        "written_at": datetime(2026, 4, 5, 12, 0, tzinfo=UTC),
        "envelope_json": {"payload": {}},
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# ArchiveRecord._require_aware — written_at tz-aware enforcement
# ---------------------------------------------------------------------------


def test_archive_record_accepts_tz_aware_written_at() -> None:
    record = ArchiveRecord(**_record_kwargs())

    assert record.written_at.tzinfo is not None
    assert record.written_at.utcoffset() is not None


def test_archive_record_rejects_naive_written_at() -> None:
    """A datetime without tzinfo raises — the wire-format contract
    is that every bundle datetime is tz-aware."""
    with pytest.raises(ValidationError, match="timezone-aware"):
        ArchiveRecord(**_record_kwargs(written_at=datetime(2026, 4, 5, 12, 0)))


# ---------------------------------------------------------------------------
# ArchiveRecord._exactly_one_key — mutual exclusivity
# ---------------------------------------------------------------------------


def test_archive_record_accepts_payload_keyed_object_key_only() -> None:
    record = ArchiveRecord(**_record_kwargs(object_key="catalogue", hashed_object_key_b64=None))

    assert record.object_key == "catalogue"
    assert record.hashed_object_key_b64 is None


def test_archive_record_accepts_hashed_passthrough_only() -> None:
    """The hashed-passthrough strategy carries the base64 HMAC
    digest in ``hashed_object_key_b64`` with ``object_key=None``."""
    record = ArchiveRecord(
        **_record_kwargs(object_key=None, hashed_object_key_b64="abc123=="),
    )

    assert record.object_key is None
    assert record.hashed_object_key_b64 == "abc123=="


def test_archive_record_rejects_both_keys_set() -> None:
    """object_key and hashed_object_key_b64 are mutually exclusive."""
    with pytest.raises(ValidationError, match="either object_key or hashed_object_key_b64, not both"):
        ArchiveRecord(
            **_record_kwargs(object_key="catalogue", hashed_object_key_b64="abc123=="),
        )


def test_archive_record_rejects_neither_key_set() -> None:
    """Every record must declare exactly one key — neither raises."""
    with pytest.raises(ValidationError, match="must set one of object_key or hashed_object_key_b64"):
        ArchiveRecord(**_record_kwargs(object_key=None, hashed_object_key_b64=None))


# ---------------------------------------------------------------------------
# ArchiveBundle._require_aware — created_at tz-aware enforcement
# ---------------------------------------------------------------------------


def test_archive_bundle_accepts_tz_aware_created_at() -> None:
    bundle = ArchiveBundle(
        bundle_id="2026-04-05-export",
        created_at=datetime(2026, 4, 5, 12, 0, tzinfo=UTC),
        records=(),
    )

    assert bundle.created_at.tzinfo is not None


def test_archive_bundle_rejects_naive_created_at() -> None:
    with pytest.raises(ValidationError, match="timezone-aware"):
        ArchiveBundle(
            bundle_id="2026-04-05-export",
            created_at=datetime(2026, 4, 5, 12, 0),
            records=(),
        )


# ---------------------------------------------------------------------------
# Strict / frozen / extra-forbid model config invariants
# ---------------------------------------------------------------------------


def test_archive_record_is_strict_and_rejects_extra_fields() -> None:
    """``extra="forbid"`` keeps wire-format bundles canonical —
    unrecognised fields surface as ValidationError rather than
    silently round-tripping garbage data."""
    with pytest.raises(ValidationError, match="extra"):
        ArchiveRecord.model_validate(_record_kwargs(extra_field="should not be allowed"))


def test_archive_record_is_frozen() -> None:
    """``frozen=True`` prevents post-construction mutation so
    records cannot drift inside the restore pipeline."""
    record = ArchiveRecord(**_record_kwargs())

    with pytest.raises(ValidationError, match="frozen"):
        record.namespace = "aeat.domain.tampered"


def test_archive_bundle_is_strict_and_rejects_extra_fields() -> None:
    with pytest.raises(ValidationError, match="extra"):
        ArchiveBundle.model_validate(
            {
                "bundle_id": "2026-04-05-export",
                "created_at": datetime(2026, 4, 5, 12, 0, tzinfo=UTC),
                "records": (),
                "extra_field": "should not be allowed",
            }
        )


def test_archive_bundle_is_frozen() -> None:
    bundle = ArchiveBundle(
        bundle_id="2026-04-05-export",
        created_at=datetime(2026, 4, 5, 12, 0, tzinfo=UTC),
        records=(),
    )

    with pytest.raises(ValidationError, match="frozen"):
        bundle.bundle_id = "tampered"


def test_archive_record_rejects_negative_schema_version() -> None:
    """Field-level ``ge=1`` constraint rejects non-positive
    schema versions — wire-format consumers refuse zero/negative."""
    with pytest.raises(ValidationError, match="schema_version"):
        ArchiveRecord(**_record_kwargs(schema_version=0))


def test_archive_record_rejects_empty_namespace() -> None:
    """The ``min_length=1`` Field constraint rejects empty
    namespace strings."""
    with pytest.raises(ValidationError, match="namespace"):
        ArchiveRecord(**_record_kwargs(namespace=""))


def test_archive_bundle_rejects_empty_bundle_id() -> None:
    with pytest.raises(ValidationError, match="bundle_id"):
        ArchiveBundle(
            bundle_id="",
            created_at=datetime(2026, 4, 5, 12, 0, tzinfo=UTC),
            records=(),
        )

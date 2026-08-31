"""Typed row-source identity contract on filing binding values."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError

from ....adapters.persistence.profile.filing_drafts import ModeloDraftRepository
from ....adapters.persistence.storage.secure_object_namespaces import FILING_DRAFTS_NAMESPACE
from ....core.aggregation import BindingSourceKind
from ....core.period import Period
from ....tests.secure_sql import isolated_runtime_profile, read_db_at_rest_bytes
from ...calculations.registry.schema_references import RegistrySnapshotRef
from ...calculations.row_source_identity import RowSourceIdentity
from ..errors import FilingValidationError
from ..schema import (
    ModeloBindingValue,
    ModeloDraft,
    ModeloDraftStatus,
    ModeloValueKind,
    compute_modelo_draft_id,
    registry_schema_version,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_RAW_IDENTITY = "opaque-activity-row-canary"
_FINGERPRINT = "a" * 64


def _identity(*, source: BindingSourceKind = BindingSourceKind.INVENTORY) -> RowSourceIdentity:
    return RowSourceIdentity(
        source_kind=source,
        source_row_identity=_RAW_IDENTITY,
        fingerprint=_FINGERPRINT,
    )


def _value(**overrides: object) -> ModeloBindingValue:
    payload: dict[str, object] = {
        "binding_id": "inventory-operation-0181",
        "value": Decimal("125.00"),
        "kind": ModeloValueKind.COMPUTED,
        "source": BindingSourceKind.INVENTORY,
        "legal_refs": ("ley-35-2006:art-30",),
        "source_refs": ("aeat-renta-2025-manual",),
        "row_index": 2,
        "row_source_identity": _identity(),
    }
    payload.update(overrides)
    return ModeloBindingValue.model_validate(payload)


def test_identity_bearing_row_is_frozen_and_securely_projected() -> None:
    value = _value()

    assert value.row_index == 2
    assert value.row_source_identity == _identity()
    assert value.secure_row_source_identity_payload() == {
        "binding_id": "inventory-operation-0181",
        "row_index": 2,
        "source_kind": "inventory",
        "source_row_identity": _RAW_IDENTITY,
        "fingerprint": _FINGERPRINT,
    }
    with pytest.raises(ValidationError):
        value.row_index = 3  # type: ignore[misc]


def test_ordinary_serialization_and_repr_redact_raw_identity() -> None:
    value = _value()

    ordinary = value.model_dump()
    text = f"{value!r} {value!s} {ordinary!r} {value.model_dump_json()}"

    assert "row_source_identity" not in ordinary
    assert _RAW_IDENTITY not in text
    assert _FINGERPRINT not in text


def test_explicit_secure_projection_roundtrips_with_reattached_identity() -> None:
    value = _value()
    secure = value.model_dump(mode="json", context={"secure_modelo_binding_value": True})

    assert ModeloBindingValue.model_validate_json(json.dumps(secure)) == value


@pytest.mark.parametrize(
    "overrides",
    [
        {"row_index": None},
        {"row_index": 0},
        {"source": BindingSourceKind.MANUAL_INPUT},
        {"row_source_identity": _identity(source=BindingSourceKind.FOREIGN_ASSET)},
    ],
)
def test_identity_refuses_scalar_nonpositive_and_source_mismatched_coordinates(
    overrides: dict[str, object],
) -> None:
    with pytest.raises(ValidationError) as exc_info:
        _value(**overrides)

    rendered = f"{exc_info.value!s} {exc_info.value!r}"
    assert _RAW_IDENTITY not in rendered
    assert _FINGERPRINT not in rendered


def test_unidentified_m720_style_row_remains_explicitly_supported() -> None:
    value = _value(
        binding_id="modelo-720-asset-row-valuation",
        source=BindingSourceKind.FOREIGN_ASSET,
        row_source_identity=None,
    )

    assert value.row_index == 2
    assert value.row_source_identity is None
    assert value.secure_row_source_identity_payload() is None


def test_row_identity_participates_in_draft_content_address() -> None:
    period = Period.from_year_and_code(2025, "0A")
    snapshot = RegistrySnapshotRef(
        modelo="100",
        revision_id="2025",
        modelo_year=2025,
        period="0A",
    )
    original = _value()
    changed = _value(
        row_source_identity=RowSourceIdentity(
            source_kind=BindingSourceKind.INVENTORY,
            source_row_identity=_RAW_IDENTITY,
            fingerprint="b" * 64,
        ),
    )

    def draft_id(value: ModeloBindingValue) -> str:
        return compute_modelo_draft_id(
            modelo="100",
            period=period,
            profile_tax_id="12345678Z",
            snapshot_ref=snapshot,
            values=(),
            binding_values=(value,),
        )

    assert draft_id(original) != draft_id(changed)


def test_identity_bearing_draft_roundtrips_only_inside_encrypted_v2_storage(tmp_path: Path) -> None:
    period = Period.from_year_and_code(2025, "0A")
    snapshot = RegistrySnapshotRef(
        modelo="100",
        revision_id="2025",
        modelo_year=2025,
        period="0A",
    )
    binding_value = _value()
    draft_id = compute_modelo_draft_id(
        modelo="100",
        period=period,
        profile_tax_id="12345678Z",
        snapshot_ref=snapshot,
        values=(),
        binding_values=(binding_value,),
    )
    instant = datetime(2026, 8, 23, tzinfo=UTC)
    draft = ModeloDraft(
        draft_id=draft_id,
        modelo="100",
        period=period,
        profile_tax_id="12345678Z",
        subject_tax_id="12345678Z",
        snapshot_ref=snapshot,
        status=ModeloDraftStatus.BORRADOR,
        values=(),
        binding_values=(binding_value,),
        created_at=instant,
        updated_at=instant,
        schema_version=registry_schema_version(modelo="100", revision_id="2025"),
    )

    with isolated_runtime_profile(
        tmp_path=tmp_path,
        bucket_id="29174940-7297-45c4-a76b-62764085ed43",
    ) as profile:
        repository = ModeloDraftRepository(bucket_id=profile.bucket_id)
        repository.save(draft)

        assert repository.load(draft_id) == draft
        changed_binding = _value(
            row_source_identity=RowSourceIdentity(
                source_kind=BindingSourceKind.INVENTORY,
                source_row_identity=_RAW_IDENTITY,
                fingerprint="b" * 64,
            ),
        )
        changed_id = compute_modelo_draft_id(
            modelo="100",
            period=period,
            profile_tax_id="12345678Z",
            snapshot_ref=snapshot,
            values=(),
            binding_values=(changed_binding,),
        )
        changed_draft = draft.model_copy(
            update={"draft_id": changed_id, "binding_values": (changed_binding,)},
        )
        write = repository.to_secure_object_write(changed_draft)
        repository.secure_object_repository.save_many((write,))

        assert repository.load(changed_id) == changed_draft
        stale = changed_draft.model_copy(update={"draft_id": "0" * 16})
        with pytest.raises(FilingValidationError, match="not this draft's content address"):
            repository.to_secure_object_write(stale)
        assert repository.schema_version == 2
        assert FILING_DRAFTS_NAMESPACE.schema_version == 2
        at_rest = read_db_at_rest_bytes(profile.paths.database_file)
        assert _RAW_IDENTITY.encode() not in at_rest
        assert _FINGERPRINT.encode() not in at_rest

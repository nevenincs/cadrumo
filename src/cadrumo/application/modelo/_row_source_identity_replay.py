"""Join encrypted calculation row identities onto replayed filing rows."""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from ...core import STRICT_FROZEN_CONFIG, BindingSourceKind
from ...core.identity import ContentDigest
from ...domain import canonical_decimal_string
from ...domain.calculations import RowBindingKey
from ...domain.calculations.registry import BindingId
from ...domain.filing import ModeloBindingValue, ModeloDraft, compute_modelo_draft_id
from ...domain.modelos import CalculationRevision, ModeloValidationError


class ModeloRowSourceFingerprint(BaseModel):
    """Safe public provenance for one replayed row coordinate."""

    model_config = ConfigDict(**{**STRICT_FROZEN_CONFIG, "hide_input_in_errors": True})

    binding_id: BindingId
    row_index: int = Field(ge=1)
    source_kind: BindingSourceKind
    fingerprint: ContentDigest


def attach_revision_row_source_identities(
    *,
    draft: ModeloDraft,
    revision: CalculationRevision,
) -> ModeloDraft:
    """Attach every persisted row identity to its exact replayed draft row."""
    revision_row_keys: set[RowBindingKey] = {
        (binding_id, int(row_index))
        for binding_id, rows in revision.row_binding_values.items()
        for row_index in rows
    }
    draft_row_keys = {
        (value.binding_id, value.row_index)
        for value in draft.binding_values
        if value.row_index is not None
    }
    if not revision_row_keys.issubset(draft_row_keys):
        raise ModeloValidationError("row source identity replay is missing a revision row coordinate")
    identity_keys = set(revision.row_source_identities)
    if not identity_keys.issubset(revision_row_keys):
        raise ModeloValidationError("row source identity replay contains an orphan revision coordinate")

    enriched: list[ModeloBindingValue] = []
    attached: set[RowBindingKey] = set()
    for value in draft.binding_values:
        key = (value.binding_id, value.row_index) if value.row_index is not None else None
        identity = revision.row_source_identities.get(key) if key is not None else None
        if key is not None and key in revision_row_keys:
            revision_value = revision.row_binding_values[key[0]][str(key[1])]
            draft_value = value.value
            canonical_draft_value = (
                canonical_decimal_string(draft_value) if isinstance(draft_value, Decimal) else str(draft_value).strip()
            )
            if canonical_draft_value != revision_value.strip():
                raise ModeloValidationError("row source identity replay value does not match persisted revision row")
        if identity is None:
            enriched.append(value)
            continue
        assert key is not None
        if value.row_source_identity is not None and value.row_source_identity != identity:
            raise ModeloValidationError("row source identity replay refuses a substituted attached identity")
        payload = value.model_dump()
        payload["row_source_identity"] = identity
        enriched.append(ModeloBindingValue.model_validate(payload))
        attached.add(key)
    if attached != identity_keys:
        raise ModeloValidationError("row source identity replay did not attach every persisted identity coordinate")

    binding_values = tuple(enriched)
    draft_id = compute_modelo_draft_id(
        modelo=draft.modelo,
        period=draft.period,
        profile_tax_id=draft.profile_tax_id,
        snapshot_ref=draft.snapshot_ref,
        values=draft.values,
        binding_values=binding_values,
    )
    return draft.model_copy(update={"binding_values": binding_values, "draft_id": draft_id})


def row_source_fingerprints_for_review(draft: ModeloDraft) -> tuple[ModeloRowSourceFingerprint, ...]:
    """Return deterministic fingerprint-only row provenance for review surfaces."""
    return tuple(
        ModeloRowSourceFingerprint(
            binding_id=value.binding_id,
            row_index=value.row_index,
            source_kind=identity.source_kind,
            fingerprint=identity.fingerprint,
        )
        for value in sorted(draft.binding_values, key=lambda item: (item.binding_id, item.row_index or 0))
        if value.row_index is not None and (identity := value.row_source_identity) is not None
    )


def revision_row_source_fingerprints_for_review(
    revision: CalculationRevision | None,
) -> tuple[ModeloRowSourceFingerprint, ...]:
    """Project encrypted revision identities onto the canonical safe review shape."""
    if revision is None:
        return ()
    return tuple(
        ModeloRowSourceFingerprint(
            binding_id=binding_id,
            row_index=row_index,
            source_kind=identity.source_kind,
            fingerprint=identity.fingerprint,
        )
        for (binding_id, row_index), identity in sorted(revision.row_source_identities.items())
    )


__all__ = [
    "ModeloRowSourceFingerprint",
    "attach_revision_row_source_identities",
    "revision_row_source_fingerprints_for_review",
    "row_source_fingerprints_for_review",
]

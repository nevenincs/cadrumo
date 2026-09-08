"""Join encrypted calculation row identities onto replayed filing rows."""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, Field

from ...core.aggregation import BindingSourceKind
from ...core.identity import ContentDigest
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...domain.calculations.registry.ids import BindingId
from ...domain.calculations.row_source_identity import RowBindingKey
from ...domain.filing.schema import ModeloBindingValue, ModeloDraft, compute_modelo_draft_id
from ...domain.identifiers import canonical_decimal_string
from ...domain.modelos.calculation_revision import CalculationRevision
from ...domain.modelos.errors import ModeloValidationError


class ModeloRowSourceFingerprint(BaseModel):
    """Safe public provenance for one replayed row coordinate."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

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
    revision_row_keys, identity_keys = _validate_replay_coordinates(draft=draft, revision=revision)
    binding_values, attached = _replay_binding_values(
        draft=draft,
        revision=revision,
        revision_row_keys=revision_row_keys,
    )
    if attached != identity_keys:
        raise ModeloValidationError("row source identity replay did not attach every persisted identity coordinate")
    return _rebuild_replayed_draft(draft=draft, binding_values=binding_values)


def _validate_replay_coordinates(
    *,
    draft: ModeloDraft,
    revision: CalculationRevision,
) -> tuple[set[RowBindingKey], set[RowBindingKey]]:
    """Ensure revision rows and persisted identities have matching coordinates."""
    revision_row_keys: set[RowBindingKey] = {
        (binding_id, int(row_index)) for binding_id, rows in revision.row_binding_values.items() for row_index in rows
    }
    draft_row_keys = {
        (value.binding_id, value.row_index) for value in draft.binding_values if value.row_index is not None
    }
    if not revision_row_keys.issubset(draft_row_keys):
        raise ModeloValidationError("row source identity replay is missing a revision row coordinate")
    identity_keys = set(revision.row_source_identities)
    if not identity_keys.issubset(revision_row_keys):
        raise ModeloValidationError("row source identity replay contains an orphan revision coordinate")
    return revision_row_keys, identity_keys


def _canonical_replay_value(value: object) -> str:
    """Render one draft row value in the same comparison form as persistence."""
    return canonical_decimal_string(value) if isinstance(value, Decimal) else str(value).strip()


def _replay_binding_value(
    *,
    value: ModeloBindingValue,
    revision: CalculationRevision,
    revision_row_keys: set[RowBindingKey],
) -> tuple[ModeloBindingValue, RowBindingKey | None]:
    """Validate and enrich one draft binding value, returning its attached coordinate."""
    key = (value.binding_id, value.row_index) if value.row_index is not None else None
    identity = revision.row_source_identities.get(key) if key is not None else None
    if key is not None and key in revision_row_keys:
        revision_value = revision.row_binding_values[key[0]][str(key[1])]
        if _canonical_replay_value(value.value) != revision_value.strip():
            raise ModeloValidationError("row source identity replay value does not match persisted revision row")
    if identity is None:
        return value, None
    if key is None:
        raise ModeloValidationError("row source identity replay requires the casilla key it attaches to")
    if value.row_source_identity is not None and value.row_source_identity != identity:
        raise ModeloValidationError("row source identity replay refuses a substituted attached identity")
    payload = value.model_dump()
    payload["row_source_identity"] = identity
    return ModeloBindingValue.model_validate(payload), key


def _replay_binding_values(
    *,
    draft: ModeloDraft,
    revision: CalculationRevision,
    revision_row_keys: set[RowBindingKey],
) -> tuple[tuple[ModeloBindingValue, ...], set[RowBindingKey]]:
    """Replay all draft binding values and record every identity coordinate attached."""
    enriched: list[ModeloBindingValue] = []
    attached: set[RowBindingKey] = set()

    for value in draft.binding_values:
        enriched_value, attached_key = _replay_binding_value(
            value=value,
            revision=revision,
            revision_row_keys=revision_row_keys,
        )
        enriched.append(enriched_value)
        if attached_key is not None:
            attached.add(attached_key)
    return tuple(enriched), attached


def _rebuild_replayed_draft(*, draft: ModeloDraft, binding_values: tuple[ModeloBindingValue, ...]) -> ModeloDraft:
    """Recompute the content identity after attaching replayed row identities."""
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

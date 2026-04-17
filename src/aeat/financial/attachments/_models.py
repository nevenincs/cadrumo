"""Strict immutable models for the attachment service."""

from __future__ import annotations

from collections.abc import Iterable, Iterator, Mapping
from datetime import datetime
from types import MappingProxyType
from typing import Any, Self

from pydantic import BaseModel, ConfigDict, Field, field_serializer, field_validator, model_validator

from ._enums import AttachmentKind, AttachmentSource

_STRICT_FROZEN = ConfigDict(strict=True, frozen=True, extra="forbid")

_HEX_DIGITS = frozenset("0123456789abcdef")


def _normalize_hex_digest(value: str, *, field_name: str) -> str:
    """Normalise and validate a 64-character lowercase hex digest."""
    normalized = value.strip().lower()
    if len(normalized) != 64 or any(char not in _HEX_DIGITS for char in normalized):
        raise ValueError(f"{field_name} must be a 64-character lowercase hex digest")
    return normalized


def _dedupe_preserve_order(values: Iterable[str], *, field_name: str) -> tuple[str, ...]:
    """Trim, validate, and deduplicate linked-ID tuples preserving first-seen order."""
    seen: dict[str, None] = {}
    for raw in values:
        if not isinstance(raw, str):
            raise ValueError(f"{field_name} must contain strings only")
        trimmed = raw.strip()
        if not trimmed:
            raise ValueError(f"{field_name} must not contain blank identifiers")
        seen.setdefault(trimmed, None)
    return tuple(seen)


class Attachment(BaseModel):
    """Immutable attachment manifest tying bytes to transactions/invoices."""

    model_config = _STRICT_FROZEN

    attachment_id: str = Field(min_length=64, max_length=64)
    kind: AttachmentKind
    source: AttachmentSource
    source_reference: str = Field(min_length=1)
    sha256: str = Field(min_length=64, max_length=64)
    mime_type: str = Field(min_length=1)
    bytes_size: int = Field(ge=0)
    captured_at: datetime
    linked_transaction_ids: tuple[str, ...] = ()
    linked_invoice_ids: tuple[str, ...] = ()
    metadata: Mapping[str, str] = Field(default_factory=dict)
    notes: str = ""

    @field_validator("attachment_id")
    @classmethod
    def _normalize_attachment_id(cls, value: str) -> str:
        """Enforce the 64-char lowercase hex shape for catalogue keys."""
        return _normalize_hex_digest(value, field_name="attachment_id")

    @field_validator("sha256")
    @classmethod
    def _normalize_sha256(cls, value: str) -> str:
        """Enforce the 64-char lowercase hex shape for the byte digest."""
        return _normalize_hex_digest(value, field_name="sha256")

    @field_validator("source_reference", "mime_type")
    @classmethod
    def _normalize_required_text(cls, value: str) -> str:
        """Trim required text fields, rejecting whitespace-only values."""
        trimmed = value.strip()
        if not trimmed:
            raise ValueError("value must not be blank")
        return trimmed

    @field_validator("notes")
    @classmethod
    def _normalize_notes(cls, value: str) -> str:
        """Trim stored notes while allowing the empty string."""
        return value.strip()

    @field_validator("captured_at", mode="before")
    @classmethod
    def _parse_captured_at(cls, value: Any) -> datetime:
        """Parse ISO-8601 strings into aware datetimes and reject naive values."""
        if isinstance(value, str):
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        elif isinstance(value, datetime):
            parsed = value
        else:
            raise ValueError("captured_at must be a datetime or ISO-8601 string")
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            raise ValueError("captured_at must be timezone-aware")
        return parsed

    @field_validator("linked_transaction_ids", mode="before")
    @classmethod
    def _normalize_linked_transactions(cls, value: Any) -> tuple[str, ...]:
        """Normalize linked-transaction tuples with dedup and trimming."""
        if value is None:
            return ()
        if isinstance(value, str | bytes):
            raise ValueError("linked_transaction_ids must be an iterable of strings, not a scalar")
        if not isinstance(value, Iterable):
            raise ValueError("linked_transaction_ids must be iterable")
        return _dedupe_preserve_order(value, field_name="linked_transaction_ids")

    @field_validator("linked_invoice_ids", mode="before")
    @classmethod
    def _normalize_linked_invoices(cls, value: Any) -> tuple[str, ...]:
        """Normalize linked-invoice tuples with dedup and trimming."""
        if value is None:
            return ()
        if isinstance(value, str | bytes):
            raise ValueError("linked_invoice_ids must be an iterable of strings, not a scalar")
        if not isinstance(value, Iterable):
            raise ValueError("linked_invoice_ids must be iterable")
        return _dedupe_preserve_order(value, field_name="linked_invoice_ids")

    @field_validator("metadata", mode="before")
    @classmethod
    def _normalize_metadata(cls, value: Any) -> Mapping[str, str]:
        """Validate the ``metadata`` escape hatch: strings only, non-empty keys."""
        if value is None:
            return MappingProxyType({})
        if not isinstance(value, Mapping):
            raise ValueError("metadata must be a mapping of string keys to string values")
        normalized: dict[str, str] = {}
        for raw_key, raw_val in value.items():
            if not isinstance(raw_key, str):
                raise ValueError("metadata keys must be strings")
            key = raw_key.strip()
            if not key:
                raise ValueError("metadata keys must not be blank")
            if not isinstance(raw_val, str):
                raise ValueError(f"metadata value for {key!r} must be a string")
            normalized[key] = raw_val
        return MappingProxyType(normalized)

    @field_serializer("metadata")
    def _serialize_metadata(self, value: Mapping[str, str]) -> dict[str, str]:
        """Serialize the frozen metadata mapping back to a JSON object."""
        return dict(value)

    @model_validator(mode="after")
    def _enforce_attachment_id_matches_sha256(self) -> Self:
        """Ensure ``attachment_id`` is the SHA-256 of the stored bytes."""
        if self.attachment_id != self.sha256:
            raise ValueError("attachment_id must equal sha256")
        return self


class AttachmentCatalogue(BaseModel):
    """In-memory immutable catalogue keyed by ``attachment_id``."""

    model_config = _STRICT_FROZEN

    attachments: Mapping[str, Attachment] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def _coerce_catalogue_input(cls, data: Any) -> Any:
        """Accept either a bare mapping or an iterable of attachments."""
        if isinstance(data, cls):
            return data
        if isinstance(data, Mapping):
            if "attachments" in data:
                return data
            if all(isinstance(key, str) for key in data):
                return {"attachments": dict(data)}
        if isinstance(data, Iterable) and not isinstance(data, str | bytes):
            attachments: dict[str, Attachment] = {}
            for item in data:
                attachment = item if isinstance(item, Attachment) else Attachment.model_validate(item)
                if attachment.attachment_id in attachments:
                    raise ValueError(f"duplicate attachment_id: {attachment.attachment_id}")
                attachments[attachment.attachment_id] = attachment
            return {"attachments": attachments}
        return data

    @model_validator(mode="after")
    def _validate_mapping_keys(self) -> Self:
        """Ensure every mapping key matches the embedded attachment ID."""
        for key, attachment in self.attachments.items():
            if key != attachment.attachment_id:
                raise ValueError(f"catalogue key {key!r} does not match attachment_id {attachment.attachment_id!r}")
        return self

    @field_validator("attachments")
    @classmethod
    def _freeze_attachments(cls, value: Mapping[str, Attachment]) -> Mapping[str, Attachment]:
        """Freeze the catalogue mapping to preserve immutability."""
        return MappingProxyType(dict(value))

    @field_serializer("attachments")
    def _serialize_attachments(self, value: Mapping[str, Attachment]) -> dict[str, Attachment]:
        """Serialize the immutable mapping back to a JSON object."""
        return dict(value)

    @classmethod
    def from_attachments(cls, attachments: Iterable[Attachment | Mapping[str, Any]]) -> Self:
        """Build a catalogue from an iterable, rejecting duplicates explicitly.

        Args:
            attachments: Attachments or attachment payloads to load.

        Returns:
            A validated immutable attachment catalogue.
        """
        return cls.model_validate(tuple(attachments))

    def __iter__(self):  # type: ignore[override]
        """Iterate over catalogue attachments."""
        return iter(self.attachments.values())

    def __len__(self) -> int:
        """Return the number of attachments in the catalogue."""
        return len(self.attachments)

    def __contains__(self, attachment_id: object) -> bool:
        """Return whether the catalogue contains ``attachment_id``."""
        if isinstance(attachment_id, Attachment):
            return attachment_id.attachment_id in self.attachments
        if isinstance(attachment_id, str):
            return attachment_id in self.attachments
        return False

    def get(self, attachment_id: str) -> Attachment | None:
        """Return one attachment by ID if present.

        Args:
            attachment_id: Stable attachment identifier (SHA-256 hex digest).

        Returns:
            The matching attachment, or ``None`` when absent.
        """
        return self.attachments.get(attachment_id)

    def values(self) -> Iterator[Attachment]:
        """Iterate over catalogue attachments."""
        return iter(self.attachments.values())

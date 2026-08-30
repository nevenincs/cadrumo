"""Strict immutable pydantic models for the attachment service.

Defines :class:`Attachment` (one manifest entry) and :class:`AttachmentCatalogue`
(an immutable in-memory mapping of attachments keyed by ``attachment_id``).
Both models reject extra fields and freeze after validation so they can be
shared safely across application code without defensive copying.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator, Mapping
from datetime import datetime
from types import MappingProxyType
from typing import Self, override

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, field_serializer, field_validator, model_validator

from ...core import OBJECT_TUPLE_ADAPTER, STR_KEYED_MAPPING_ADAPTER, Hex64Str
from ...core import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from ...core.errors.hierarchy import CoreValidationError
from ...core.identity import BucketId, ContentDigest
from ...core.time import UtcInstant, parse_iso_datetime, validate_utc_aware
from .enums import AttachmentKind, AttachmentSource
from .errors import AttachmentValidationError

_HEX_DIGITS = frozenset("0123456789abcdef")
_LINK_ONLY_MIME_TYPE = "text/uri-list"
_STRING_METADATA_MAPPING: TypeAdapter[dict[str, str]] = TypeAdapter(dict[str, str], config=ConfigDict(strict=True))


def normalize_media_type(value: str) -> str:
    """Return the canonical MIME token without display-only parameters.

    Manifests preserve their original, trimmed MIME value as provenance. Content
    classification instead compares this normalized token, so case and valid
    parameters cannot change an evidence boundary's meaning.
    """
    return value.split(";", 1)[0].strip().lower()


def is_link_only_mime_type(value: str) -> bool:
    """Return whether ``value`` names the link-only URI-list media type.

    MIME syntax permits a parameter section (``type/subtype; param=value``),
    so the comparison is against the parsed media type — the token before any
    ``;`` — not the full string. ``text/uri-list; charset=utf-8`` is as
    link-only as the bare form and must be refused by every boundary that
    guards evidence-byte manifests.
    """
    return normalize_media_type(value) == _LINK_ONLY_MIME_TYPE


def _normalize_hex_digest(value: str, *, field_name: str) -> str:
    """Normalise and validate a 64-character lowercase hex digest.

    Args:
        value: Untrusted digest candidate.
        field_name: Field name used in the raised error message.

    Returns:
        The validated digest, lowercased and stripped of surrounding whitespace.

    Raises:
        AttachmentValidationError: When ``value`` is not a 64-character hex string.
    """
    normalized = value.strip().lower()
    if len(normalized) != 64 or any(char not in _HEX_DIGITS for char in normalized):
        raise AttachmentValidationError(f"{field_name} must be a 64-character lowercase hex digest")
    return normalized


def _dedupe_preserve_order(values: Iterable[object], *, field_name: str) -> tuple[str, ...]:
    """Trim, validate, and deduplicate linked-ID tuples preserving first-seen order.

    Args:
        values: Iterable of candidate identifiers.
        field_name: Field name used in raised error messages.

    Returns:
        Deduplicated tuple of trimmed identifiers in first-seen order.

    Raises:
        AttachmentValidationError: When any element is not a string or is blank.
    """
    seen: dict[str, None] = {}
    for raw in values:
        if not isinstance(raw, str):
            raise AttachmentValidationError(f"{field_name} must contain strings only")
        trimmed = raw.strip()
        if not trimmed:
            raise AttachmentValidationError(f"{field_name} must not contain blank identifiers")
        seen.setdefault(trimmed, None)
    return tuple(seen)


class Attachment(BaseModel):
    """Immutable attachment manifest tying bytes to transactions and invoices.

    Each attachment is content-addressed: ``attachment_id`` is the SHA-256 of
    the stored bytes, and the model enforces that ``attachment_id == sha256``
    so the manifest cannot drift from the byte payload it references.

    The manifest also records the originating channel (:class:`domain.attachments.AttachmentSource`),
    the document kind (:class:`domain.attachments.AttachmentKind`), and
    optional cross-references back to transaction and invoice identifiers so
    the evidence layer is traversable in either direction.

    Attributes:
        attachment_id: 64-character lowercase hex SHA-256 digest. Equals
            :attr:`sha256`.
        kind: Document kind. See :class:`domain.attachments.AttachmentKind`.
        source: Channel the bytes were captured from. See
            :class:`domain.attachments.AttachmentSource`.
        source_reference: Channel-specific reference (e.g. a Gmail message id,
            a Drive file id, a local path).
        sha256: 64-character lowercase hex SHA-256 of the stored bytes.
        mime_type: Trimmed non-empty MIME type string.
        bytes_size: Size in bytes of the stored payload.
        captured_at: Timezone-aware capture timestamp.
        linked_transaction_ids: Transaction identifiers this attachment supports.
        linked_invoice_ids: Invoice identifiers this attachment supports.
        bucket_id: Owning profile bucket for secure evidence attachment.
        captured_by: Actor that captured or imported the evidence when known.
        source_command: Backend/CLI command source that captured it when known.
        metadata: Frozen string-to-string mapping for channel-specific metadata.
        notes: Free-form trimmed notes; the empty string is allowed.
    """

    model_config = _STRICT_FROZEN

    attachment_id: Hex64Str
    kind: AttachmentKind
    source: AttachmentSource
    source_reference: str = Field(min_length=1)
    sha256: ContentDigest
    mime_type: str = Field(min_length=1)
    bytes_size: int = Field(ge=0)
    captured_at: UtcInstant
    linked_transaction_ids: tuple[str, ...] = ()
    linked_invoice_ids: tuple[str, ...] = ()
    bucket_id: BucketId | None = None
    captured_by: str | None = None
    source_command: str | None = None
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
            raise AttachmentValidationError("value must not be blank")
        return trimmed

    @field_validator("mime_type")
    @classmethod
    def _reject_link_only_mime_type(cls, value: str) -> str:
        """Reject manifests that claim to store a link instead of document bytes."""
        if is_link_only_mime_type(value):
            raise AttachmentValidationError("attachment mime_type must carry document bytes, not a link-only URI list")
        return value

    @field_validator("bucket_id", "captured_by", "source_command")
    @classmethod
    def _normalize_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        trimmed = value.strip()
        if not trimmed:
            raise AttachmentValidationError("value must not be blank")
        return trimmed

    @field_validator("notes")
    @classmethod
    def _normalize_notes(cls, value: str) -> str:
        """Trim stored notes while allowing the empty string."""
        return value.strip()

    @field_validator("captured_at", mode="before")
    @classmethod
    def _parse_captured_at(cls, value: object) -> datetime:
        """Parse ISO-8601 strings into aware datetimes and reject naive values."""
        if isinstance(value, str):
            parsed = parse_iso_datetime(value)
        elif isinstance(value, datetime):
            parsed = value
        else:
            raise AttachmentValidationError("captured_at must be a datetime or ISO-8601 string")
        try:
            return validate_utc_aware(parsed)
        except CoreValidationError as exc:
            raise AttachmentValidationError(str(exc)) from exc

    @field_validator("linked_transaction_ids", mode="before")
    @classmethod
    def _normalize_linked_transactions(cls, value: object) -> tuple[str, ...]:
        """Normalize linked-transaction tuples with dedup and trimming."""
        if value is None:
            return ()
        if isinstance(value, str | bytes):
            raise AttachmentValidationError("linked_transaction_ids must be an iterable of strings, not a scalar")
        if not isinstance(value, Iterable):
            raise AttachmentValidationError("linked_transaction_ids must be iterable")
        return _dedupe_preserve_order(OBJECT_TUPLE_ADAPTER.validate_python(value), field_name="linked_transaction_ids")

    @field_validator("linked_invoice_ids", mode="before")
    @classmethod
    def _normalize_linked_invoices(cls, value: object) -> tuple[str, ...]:
        """Normalize linked-invoice tuples with dedup and trimming."""
        if value is None:
            return ()
        if isinstance(value, str | bytes):
            raise AttachmentValidationError("linked_invoice_ids must be an iterable of strings, not a scalar")
        if not isinstance(value, Iterable):
            raise AttachmentValidationError("linked_invoice_ids must be iterable")
        return _dedupe_preserve_order(OBJECT_TUPLE_ADAPTER.validate_python(value), field_name="linked_invoice_ids")

    @field_validator("metadata", mode="before")
    @classmethod
    def _normalize_metadata(cls, value: object) -> Mapping[str, str]:
        """Validate the ``metadata`` escape hatch: strings only, non-empty keys."""
        if value is None:
            return MappingProxyType(dict[str, str]())
        if not isinstance(value, Mapping):
            raise AttachmentValidationError("metadata must be a mapping of string keys to string values")
        normalized: dict[str, str] = {}
        try:
            metadata = _STRING_METADATA_MAPPING.validate_python(value)
        except ValueError as exc:
            raise AttachmentValidationError("metadata must be a mapping of string keys to string values") from exc
        for raw_key, raw_val in metadata.items():
            key = raw_key.strip()
            if not key:
                raise AttachmentValidationError("metadata keys must not be blank")
            if not raw_val:
                raise AttachmentValidationError(f"metadata value for {key!r} must not be blank")
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
            raise AttachmentValidationError("attachment_id must equal sha256")
        return self


class AttachmentCatalogue(BaseModel):
    """In-memory immutable catalogue keyed by ``attachment_id``.

    Accepts construction from either a bare mapping, an iterable of
    :class:`Attachment` instances, or attachment payload dictionaries via
    :meth:`from_attachments`. Every mapping key is verified to match the
    embedded :attr:`Attachment.attachment_id` so lookups cannot drift from
    the manifest content.

    Attributes:
        attachments: Frozen mapping from ``attachment_id`` to :class:`Attachment`.
    """

    model_config = _STRICT_FROZEN

    attachments: Mapping[str, Attachment] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def _coerce_catalogue_input(cls, data: object) -> object:
        """Accept either a bare mapping or an iterable of attachments."""
        if isinstance(data, cls):
            return data
        if isinstance(data, Mapping):
            payload = STR_KEYED_MAPPING_ADAPTER.validate_python(data)
            if "attachments" in payload:
                return payload
            return {"attachments": payload}
        if isinstance(data, Iterable) and not isinstance(data, str | bytes):
            attachments: dict[str, Attachment] = {}
            for item in OBJECT_TUPLE_ADAPTER.validate_python(data):
                attachment = item if isinstance(item, Attachment) else Attachment.model_validate(item)
                if attachment.attachment_id in attachments:
                    raise AttachmentValidationError(f"duplicate attachment_id: {attachment.attachment_id}")
                attachments[attachment.attachment_id] = attachment
            return {"attachments": attachments}
        return data

    @model_validator(mode="after")
    def _validate_mapping_keys(self) -> Self:
        """Ensure every mapping key matches the embedded attachment ID."""
        for key, attachment in self.attachments.items():
            if key != attachment.attachment_id:
                raise AttachmentValidationError(
                    f"catalogue key {key!r} does not match attachment_id {attachment.attachment_id!r}",
                )
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
    def from_attachments(cls, attachments: Iterable[Attachment | Mapping[str, object]]) -> Self:
        """Build a catalogue from an iterable, rejecting duplicates explicitly.

        Args:
            attachments: Attachments or attachment payloads to load.

        Returns:
            A validated immutable attachment catalogue.
        """
        return cls.model_validate(tuple(attachments))

    @override
    def __iter__(self) -> Iterator[Attachment]:  # pyright: ignore[reportIncompatibleMethodOverride]  # ty: ignore[invalid-method-override]  # pyrefly: ignore[bad-override]  # reason: intentional Pydantic catalogue iteration adapter; the established public API yields Attachment records, not BaseModel field-value tuples
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
        """Return one :class:`Attachment` by ID if present.

        Args:
            attachment_id: Stable attachment identifier (SHA-256 hex digest).

        Returns:
            The matching :class:`Attachment`, or ``None`` when absent.
        """
        return self.attachments.get(attachment_id)

    def values(self) -> Iterator[Attachment]:
        """Iterate over catalogue attachments.

        Returns:
            Iterator over :class:`Attachment` instances.
        """
        return iter(self.attachments.values())

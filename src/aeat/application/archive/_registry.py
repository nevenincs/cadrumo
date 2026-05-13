"""Registry of archive adapters keyed by secure-object namespace.

Each :class:`ArchiveAdapter` carries the metadata the export and
restore pipelines need for one namespace: the sensitivity class the
namespace stores at, the envelope schema version this consumer
supports, a human-facing label, and a key-recovery strategy.

Two key strategies are supported:

- ``payload_field`` — natural key is recoverable from the decoded
  envelope payload (e.g. invoice catalogue's ``"catalogue"`` constant
  or a filing draft's ``draft_id`` field). Default for new adapters.
- ``hashed_passthrough`` — natural key is NOT recoverable from the
  payload (path-keyed namespaces such as
  ``aeat.application.setup.profile``). The export emits the row's
  raw HMAC digest as base64; restore writes it back through
  :meth:`SecureObjectRepository.save_with_raw_key` without re-hashing.
  Same-master-key round-trip only.
"""

from __future__ import annotations

from collections.abc import Callable
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from ...core.classification import SensitivityClass
from ..profile._storage_namespaces import _PROFILE_NAMESPACE
from ._errors import ArchiveAdapterMissingError

_STRICT_FROZEN = ConfigDict(strict=True, frozen=True, extra="forbid", arbitrary_types_allowed=True)


class KeyStrategy(StrEnum):
    """How the archive walker resolves the object key for a record."""

    PAYLOAD_FIELD = "payload_field"
    HASHED_PASSTHROUGH = "hashed_passthrough"


class ArchiveAdapter(BaseModel):
    """Per-namespace metadata for export/restore.

    Attributes:
        namespace: The :class:`SecureObjectRepository` namespace
            (e.g. ``"aeat.domain.invoices"``).
        classification: The :class:`SensitivityClass` the namespace
            stores at. Must match what the per-domain repository
            declares to ``save()``.
        schema_version: The maximum envelope schema version this
            consumer supports.
        label: Human-readable label rendered by the CLI (e.g.
            ``"invoice catalogue"``).
        key_strategy: Whether the natural key is extracted from the
            payload (:attr:`KeyStrategy.PAYLOAD_FIELD`) or whether the
            raw HMAC digest is round-tripped opaquely
            (:attr:`KeyStrategy.HASHED_PASSTHROUGH`).
        extract_object_key: Required for ``PAYLOAD_FIELD`` adapters;
            ignored for ``HASHED_PASSTHROUGH`` adapters. Callable that
            takes the parsed ``envelope.payload`` dict and returns the
            natural object key.
    """

    model_config = _STRICT_FROZEN

    namespace: str = Field(min_length=1)
    classification: SensitivityClass
    schema_version: int = Field(ge=1)
    label: str = Field(min_length=1)
    key_strategy: KeyStrategy = Field(default=KeyStrategy.PAYLOAD_FIELD)
    extract_object_key: Callable[[dict[str, Any]], str] | None = None


_REGISTRY: dict[str, ArchiveAdapter] = {}


def register_archive_adapter(adapter: ArchiveAdapter) -> None:
    """Register ``adapter`` under its namespace.

    Args:
        adapter: The adapter to register. Re-registering the same
            namespace replaces any prior adapter.
    """
    _REGISTRY[adapter.namespace] = adapter


def archive_adapter_for(namespace: str) -> ArchiveAdapter:
    """Return the adapter registered for ``namespace``.

    Raises:
        :exc:`ArchiveAdapterMissingError`: If ``namespace`` has no
            registered adapter; the export and restore pipelines do
            not synthesise defaults.
    """
    adapter = _REGISTRY.get(namespace)
    if adapter is None:
        raise ArchiveAdapterMissingError(f"no archive adapter registered for namespace {namespace!r}")
    return adapter


def all_archive_adapters() -> tuple[ArchiveAdapter, ...]:
    """Return every registered adapter, ordered by namespace."""
    return tuple(_REGISTRY[namespace] for namespace in sorted(_REGISTRY))


def _extract_constant_key(constant: str) -> Callable[[dict[str, Any]], str]:
    """Return a key extractor that ignores the payload and yields ``constant``."""

    def extract(_payload: dict[str, Any]) -> str:
        return constant

    return extract


def _extract_field(field_name: str) -> Callable[[dict[str, Any]], str]:
    """Return a key extractor that reads ``payload[field_name]`` as a non-empty string."""

    def extract(payload: dict[str, Any]) -> str:
        value = payload.get(field_name)
        if not isinstance(value, str) or not value:
            raise ArchiveAdapterMissingError(
                f"archive payload is missing required key field {field_name!r}; cannot derive object key",
            )
        return value

    return extract


def _extract_first_entry_field(entries_field: str, entry_field: str) -> Callable[[dict[str, Any]], str]:
    """Return a key extractor that reads ``payload[entries_field][0][entry_field]``.

    Used by namespaces whose natural key lives on the first nested
    record (e.g. filing history, where ``modelo`` is on every entry but
    is also the namespace's per-record key).
    """

    def extract(payload: dict[str, Any]) -> str:
        entries = payload.get(entries_field)
        if not isinstance(entries, list) or not entries:
            raise ArchiveAdapterMissingError(
                f"archive payload's {entries_field!r} list is empty; cannot derive object key",
            )
        first = entries[0]
        if not isinstance(first, dict):
            raise ArchiveAdapterMissingError(
                f"archive payload's {entries_field!r}[0] is not a JSON object; cannot derive object key",
            )
        value = first.get(entry_field)
        if not isinstance(value, str) or not value:
            raise ArchiveAdapterMissingError(
                f"archive payload's {entries_field!r}[0].{entry_field!r} is missing or empty; cannot derive object key",
            )
        return value

    return extract


def _register_built_in_adapters() -> None:
    """Register adapters for namespaces shipped by this repository.

    Adding a new namespace is as simple as appending one entry here
    (or calling :func:`register_archive_adapter` from a domain module
    at import time, which the framework also accepts).

    Out of scope today: namespaces whose object key is derived from
    sources outside the envelope payload (e.g. blob digests),
    namespaces holding ephemeral state (auth sessions, LLM cache,
    workflow runs, CLI state), and namespaces holding caches
    regenerable from upstream data. These are tracked as follow-ups.
    """
    register_archive_adapter(
        ArchiveAdapter(
            namespace="aeat.domain.invoices",
            classification=SensitivityClass.FINANCIAL,
            schema_version=1,
            label="invoice catalogue",
            extract_object_key=_extract_constant_key("catalogue"),
        )
    )
    register_archive_adapter(
        ArchiveAdapter(
            namespace="aeat.domain.transactions",
            classification=SensitivityClass.FINANCIAL,
            schema_version=1,
            label="transaction catalogue",
            extract_object_key=_extract_constant_key("catalogue"),
        )
    )
    register_archive_adapter(
        ArchiveAdapter(
            namespace="aeat.domain.filing.drafts",
            classification=SensitivityClass.FINANCIAL,
            schema_version=1,
            label="filing drafts",
            extract_object_key=_extract_field("draft_id"),
        )
    )
    register_archive_adapter(
        ArchiveAdapter(
            namespace="aeat.domain.filing.amendments",
            classification=SensitivityClass.AUDIT,
            schema_version=1,
            label="filing amendments (complementaria)",
            extract_object_key=_extract_field("amendment_id"),
        )
    )
    register_archive_adapter(
        ArchiveAdapter(
            namespace="aeat.domain.justificante.metadata",
            classification=SensitivityClass.AUDIT,
            schema_version=1,
            label="justificante metadata (receipts)",
            extract_object_key=_extract_field("csv"),
        )
    )
    register_archive_adapter(
        ArchiveAdapter(
            namespace="aeat.domain.submission.records",
            classification=SensitivityClass.AUDIT,
            schema_version=1,
            label="submission records",
            extract_object_key=_extract_field("submission_id"),
        )
    )
    register_archive_adapter(
        ArchiveAdapter(
            namespace="aeat.domain.usage_ratios",
            classification=SensitivityClass.FINANCIAL,
            schema_version=1,
            label="usage ratio profile",
            extract_object_key=_extract_constant_key("profile"),
        )
    )
    register_archive_adapter(
        ArchiveAdapter(
            namespace="aeat.domain.attachments.manifests",
            classification=SensitivityClass.FINANCIAL,
            schema_version=1,
            label="attachment manifests",
            extract_object_key=_extract_field("attachment_id"),
        )
    )
    register_archive_adapter(
        ArchiveAdapter(
            namespace="aeat.application.filing.history",
            classification=SensitivityClass.AUDIT,
            schema_version=1,
            label="filing history",
            extract_object_key=_extract_first_entry_field("entries", "modelo"),
        )
    )
    # Path-keyed namespaces: the natural key is the install/storage
    # path, which lives only in the row's HashedLookup column. These
    # adapters use HASHED_PASSTHROUGH so the export emits the raw
    # digest and the restore writes it back through
    # ``save_with_raw_key``. Same-master-key round-trip only.
    for namespace, label, classification in (
        (_PROFILE_NAMESPACE, "config profile (autonomo identity)", SensitivityClass.IDENTITY),
        ("aeat.persistence.profile.assets", "profile assets ledger", SensitivityClass.FINANCIAL),
        (
            "aeat.persistence.profile.assets.amortization",
            "profile amortization ledger",
            SensitivityClass.FINANCIAL,
        ),
        ("aeat.persistence.profile.inventory", "profile inventory ledger", SensitivityClass.FINANCIAL),
        ("aeat.persistence.profile.tax_residence", "profile tax residence", SensitivityClass.IDENTITY),
    ):
        register_archive_adapter(
            ArchiveAdapter(
                namespace=namespace,
                classification=classification,
                schema_version=1,
                label=label,
                key_strategy=KeyStrategy.HASHED_PASSTHROUGH,
                extract_object_key=None,
            )
        )


_register_built_in_adapters()


__all__ = [
    "ArchiveAdapter",
    "KeyStrategy",
    "all_archive_adapters",
    "archive_adapter_for",
    "register_archive_adapter",
]

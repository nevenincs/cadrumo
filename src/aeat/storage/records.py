"""Public pydantic v2 record models for the storage layer.

These types are the boundary-crossing surface of :mod:`aeat.storage`. Callers
outside the subpackage always work with these records — never with the
internal SQLAlchemy mapper classes from :mod:`aeat.storage._orm`.

Every record is declared with ``ConfigDict(strict=True, frozen=True)`` per the
project pydantic mandate.

Note:
    Translatable string fields (``name``, ``label``) are plain ``str`` today.
    Once the trilingual primitive from issue #20 lands, these fields will be
    migrated to the shared ``Translatable`` shape.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class PortalAuthMethod(StrEnum):
    """Closed catalogue of supported AEAT portal authentication methods."""

    CLAVE = "clave"
    CERTIFICATE = "certificate"
    DNIE = "dnie"
    NONE = "none"


class _StrictFrozen(BaseModel):
    """Shared base enforcing strict parsing and immutability."""

    model_config = ConfigDict(strict=True, frozen=True)


class ModeloRecord(_StrictFrozen):
    """Public record for a row in the ``modelos`` table.

    Attributes:
        id: Surrogate primary key. ``None`` for records not yet persisted.
        identifier: Stable natural key (e.g. ``MODELO_130``).
        name: Human-readable modelo name (translatable, see module note).
    """

    id: int | None = Field(default=None, ge=1)
    identifier: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=255)


class PortalRecord(_StrictFrozen):
    """Public record for a row in the ``portals`` table.

    Attributes:
        id: Surrogate primary key. ``None`` for records not yet persisted.
        identifier: Stable natural key (e.g. ``SEDE_ELECTRONICA_ROOT``).
        base_url: Canonical URL for the portal.
        auth_method: Authentication method (closed enum).
        modelo_id: Optional foreign key to :class:`ModeloRecord`.
        label: Human-readable label (translatable, see module note).
    """

    id: int | None = Field(default=None, ge=1)
    identifier: str = Field(min_length=1, max_length=64)
    base_url: str = Field(min_length=1, max_length=512)
    auth_method: PortalAuthMethod
    modelo_id: int | None = Field(default=None, ge=1)
    label: str = Field(min_length=1, max_length=255)


class CorpusArtifactRecord(_StrictFrozen):
    """Public record for a row in the ``corpus_artifacts`` table.

    Attributes:
        id: Surrogate primary key. ``None`` for records not yet persisted.
        year: Tax year this artifact belongs to.
        modelo_id: Foreign key to the owning :class:`ModeloRecord`.
        file_path: Project-relative path to the on-disk artifact.
        sha256: Hex digest of the artifact bytes.
        source_url: URL the artifact was fetched from.
        fetched_at: Timestamp when the artifact was fetched (UTC).
    """

    id: int | None = Field(default=None, ge=1)
    year: int = Field(ge=1900, le=2100)
    modelo_id: int = Field(ge=1)
    file_path: str = Field(min_length=1, max_length=1024)
    sha256: str = Field(min_length=64, max_length=64)
    source_url: str = Field(min_length=1, max_length=1024)
    fetched_at: datetime

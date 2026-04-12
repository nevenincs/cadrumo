"""Internal SQLAlchemy ORM mapper classes.

These classes back the declarative schema consumed by Alembic autogenerate.
They are intentionally kept out of the :mod:`aeat.storage` public API — the
public surface exposes pydantic v2 records (see :mod:`aeat.storage.records`)
and repositories bridge between the two.

Note:
    Translatable columns (e.g. modelo names, portal labels) are plain ``str``
    today. Once the trilingual primitive from issue #20 lands, these columns
    will be migrated to the shared ``Translatable`` shape. Each such column
    carries an inline ``TODO(#20)`` marker.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Declarative base for every ORM mapper class in this package."""


class ModeloRow(Base):
    """Row in the ``modelos`` table.

    Attributes:
        id: Surrogate integer primary key.
        identifier: Stable natural key (e.g. ``MODELO_130``).
        name: Human-readable modelo name.
    """

    __tablename__ = "modelos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    identifier: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    # TODO(#20): replace with Translatable once the i18n primitive lands.
    name: Mapped[str] = mapped_column(String(255), nullable=False)


class PortalRow(Base):
    """Row in the ``portals`` table.

    Attributes:
        id: Surrogate integer primary key.
        identifier: Stable natural key (e.g. ``SEDE_ELECTRONICA_ROOT``).
        base_url: Canonical URL for the portal.
        auth_method: Authentication method as a short string code.
        modelo_id: Optional foreign key to :class:`ModeloRow`.
    """

    __tablename__ = "portals"
    __table_args__ = (
        CheckConstraint(
            "auth_method IN ('clave', 'certificate', 'dnie', 'none')",
            name="ck_portals_auth_method",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    identifier: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    base_url: Mapped[str] = mapped_column(String(512), nullable=False)
    auth_method: Mapped[str] = mapped_column(String(32), nullable=False)
    modelo_id: Mapped[int | None] = mapped_column(
        ForeignKey("modelos.id", ondelete="SET NULL"),
        nullable=True,
    )
    # TODO(#20): replace with Translatable once the i18n primitive lands.
    label: Mapped[str] = mapped_column(String(255), nullable=False)

    modelo: Mapped[ModeloRow | None] = relationship("ModeloRow", lazy="joined")


class CorpusArtifactRow(Base):
    """Row in the ``corpus_artifacts`` table.

    Attributes:
        id: Surrogate integer primary key.
        year: Tax year this artifact belongs to.
        modelo_id: Foreign key to the owning :class:`ModeloRow`.
        file_path: Project-relative path to the on-disk artifact.
        sha256: Hex digest of the artifact bytes.
        source_url: URL the artifact was fetched from.
        fetched_at: Timestamp when the artifact was fetched (UTC).
    """

    __tablename__ = "corpus_artifacts"
    __table_args__ = (
        UniqueConstraint(
            "year",
            "modelo_id",
            "file_path",
            name="uq_corpus_artifacts_identity",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    modelo_id: Mapped[int] = mapped_column(
        ForeignKey("modelos.id", ondelete="CASCADE"),
        nullable=False,
    )
    file_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    source_url: Mapped[str] = mapped_column(String(1024), nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    modelo: Mapped[ModeloRow] = relationship("ModeloRow", lazy="joined")


metadata = Base.metadata
"""Alembic ``target_metadata`` for autogenerate."""

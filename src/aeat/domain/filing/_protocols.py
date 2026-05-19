"""Cross-module Protocols consumed by :mod:`aeat.application.filing`.

Every upstream collaborator (modelo identity, casilla schemas, deadline
engine) is represented by a :class:`typing.Protocol` so the filing
application package does not take a hard import on any sibling subpackage.
Concrete implementations are wired at runtime by the entrypoint.

These Protocols are intentionally minimal: they describe only the
attributes :mod:`aeat.application.filing` actually consumes. They do not
attempt to model the full surface of the upstream subpackages.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import date
from decimal import Decimal
from typing import Protocol, runtime_checkable


@runtime_checkable
class ModeloIdentity(Protocol):
    """The minimal modelo identity surface consumed by builders."""

    @property
    def id(self) -> str:
        """Return the stable string ID of the modelo."""
        ...

    @property
    def display_name(self) -> str:
        """Return a short human-readable name for the modelo."""
        ...

    @property
    def cadence(self) -> str:
        """Return the filing cadence (e.g. ``"quarterly"``)."""
        ...


@runtime_checkable
class CasillaSchema(Protocol):
    """The minimal casilla schema surface consumed by builders.

    Attributes:
        id: Stable casilla ID (e.g. ``"01"``).
        value_type: One of ``"decimal"``, ``"int"``, ``"str"``,
            ``"bool"``, ``"date"``.
        required: Whether the casilla must be present in a valid
            draft.
        formula: ID of the formula declared on this casilla, or
            ``None`` for literal casillas.
        formula_inputs: Tuple of casilla IDs this casilla depends
            on. Empty for literal casillas.
        legal_refs: Regulatory citations grounding this casilla's
            definition (BOE / AEAT permalinks).
        source_refs: Source-material citations backing this casilla.
        min_value / max_value: Inclusive ``Decimal`` bounds for
            numeric casillas; ``None`` if unbounded.
        default: Default value used when the casilla is required
            and no input was supplied.
    """

    @property
    def id(self) -> str:
        """Return the casilla identifier."""
        ...

    @property
    def value_type(self) -> str:
        """Return the casilla value-type tag."""
        ...

    @property
    def required(self) -> bool:
        """Return whether the casilla must be present in a valid draft."""
        ...

    @property
    def formula(self) -> str | None:
        """Return the formula ID, or ``None`` if this is a literal casilla."""
        ...

    @property
    def formula_inputs(self) -> tuple[str, ...]:
        """Return the casilla IDs this casilla's formula depends on."""
        ...

    @property
    def legal_refs(self) -> tuple[str, ...]:
        """Return the regulatory citation IDs grounding this casilla."""
        ...

    @property
    def source_refs(self) -> tuple[str, ...]:
        """Return the source-material citation IDs for this casilla."""
        ...

    @property
    def min_value(self) -> Decimal | None:
        """Return the inclusive lower bound, if any."""
        ...

    @property
    def max_value(self) -> Decimal | None:
        """Return the inclusive upper bound, if any."""
        ...

    @property
    def default(self) -> object | None:
        """Return the default value used when no input is supplied."""
        ...


@runtime_checkable
class CasillaCollection(Protocol):
    """A collection of casilla schemas keyed by ID."""

    @property
    def schema_version(self) -> str:
        """Return the version of the underlying casilla DB."""
        ...

    def __iter__(self) -> object:  # pragma: no cover - Protocol
        """Iterate the collection."""
        ...

    def get(self, casilla_id: str) -> CasillaSchema | None:
        """Return the casilla schema for ``casilla_id``, or ``None``."""
        ...

    def all(self) -> Sequence[CasillaSchema]:
        """Return every casilla schema in the collection."""
        ...


@runtime_checkable
class CasillaSchemaProvider(Protocol):
    """Resolves a casilla collection for a given modelo."""

    def get_collection(self, modelo: str) -> CasillaCollection:
        """Return the casilla collection for ``modelo``."""
        ...


@runtime_checkable
class DeadlineStatus(Protocol):
    """Result of a deadline check for a (modelo, period) tuple."""

    @property
    def due_date(self) -> date:
        """Return the AEAT-published due date."""
        ...

    @property
    def is_overdue(self) -> bool:
        """Return ``True`` when the reference date is past ``due_date``."""
        ...


@runtime_checkable
class DeadlineChecker(Protocol):
    """Checks the filing deadline for a (modelo, period) tuple."""

    def check(self, modelo: str, period: str) -> DeadlineStatus:
        """Return the :class:`DeadlineStatus` for ``modelo`` and ``period``."""
        ...


@runtime_checkable
class ModeloProfile(Protocol):
    """The taxpayer profile a draft is built for.

    Only the attributes :mod:`aeat.application.filing` actually consumes are
    declared here; downstream callers may use richer profile
    objects as long as they expose these attributes.
    """

    @property
    def tax_id(self) -> str:
        """Return the taxpayer's NIF / NIE."""
        ...

    @property
    def display_name(self) -> str:
        """Return a short human-readable label for the taxpayer."""
        ...


# A typed alias for the raw input mapping passed into builders.
# Mapping not dict so callers may pass any read-only mapping.
ModeloInputs = Mapping[str, object]
"""Read-only input mapping for casilla values handed to a filing builder."""

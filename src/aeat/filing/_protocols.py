"""Cross-module Protocols consumed by :mod:`aeat.filing`.

Every upstream collaborator (modelos #6, casilla schemas #9 / #23,
deadline engine #38) is represented by a runtime-checkable
Protocol so :mod:`aeat.filing` does not take a hard import on any
in-flight sibling subpackage. Concrete implementations live in
the test suite for now and will be replaced on rebase once the
upstream subpackages land.

These Protocols are intentionally minimal: they describe only the
attributes :mod:`aeat.filing` actually consumes. They are not
attempting to model the full surface of the upstream subpackages.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import date
from typing import Protocol, runtime_checkable


@runtime_checkable
class ModeloIdentity(Protocol):
    """The minimal modelo identity surface consumed by builders."""

    @property
    def id(self) -> str:
        """Return the stable string ID of the modelo (e.g. ``"130"``)."""

    @property
    def display_name(self) -> str:
        """Return a short human-readable name for the modelo."""

    @property
    def cadence(self) -> str:
        """Return the filing cadence (e.g. ``"quarterly"``)."""


@runtime_checkable
class CasillaSchema(Protocol):
    """The minimal casilla schema surface consumed by builders.

    Attributes:
        id: Stable casilla ID (e.g. ``"01"``).
        value_type: One of ``"decimal"``, ``"int"``, ``"str"``,
            ``"bool"``, ``"date"``.
        required: Whether the casilla must be present in a valid
            draft.
        formula_inputs: Tuple of casilla IDs this casilla depends
            on. Empty for literal casillas.
        min_value / max_value: Inclusive bounds for numeric
            casillas; ``None`` if unbounded.
        default: Default value used when the casilla is required
            and no input was supplied.
    """

    @property
    def id(self) -> str: ...
    @property
    def value_type(self) -> str: ...
    @property
    def required(self) -> bool: ...
    @property
    def formula_inputs(self) -> tuple[str, ...]: ...
    @property
    def min_value(self) -> float | int | None: ...
    @property
    def max_value(self) -> float | int | None: ...
    @property
    def default(self) -> object | None: ...


@runtime_checkable
class CasillaCollection(Protocol):
    """A collection of casilla schemas keyed by ID."""

    @property
    def schema_version(self) -> str:
        """Return the version of the underlying casilla DB."""

    def __iter__(self) -> object:  # pragma: no cover - Protocol
        ...

    def get(self, casilla_id: str) -> CasillaSchema | None: ...

    def all(self) -> Sequence[CasillaSchema]: ...


@runtime_checkable
class CasillaSchemaProvider(Protocol):
    """Resolves a casilla collection for a given modelo."""

    def get_collection(self, modelo: str) -> CasillaCollection: ...


@runtime_checkable
class DeadlineStatus(Protocol):
    """Result of a deadline check for a (modelo, period) tuple."""

    @property
    def due_date(self) -> date: ...
    @property
    def is_overdue(self) -> bool: ...


@runtime_checkable
class DeadlineChecker(Protocol):
    """Checks the filing deadline for a (modelo, period) tuple."""

    def check(self, modelo: str, period: str) -> DeadlineStatus: ...


@runtime_checkable
class FilingProfile(Protocol):
    """The taxpayer profile a draft is built for.

    Only the attributes :mod:`aeat.filing` actually consumes are
    declared here; downstream callers may use richer profile
    objects as long as they expose these attributes.
    """

    @property
    def tax_id(self) -> str: ...
    @property
    def display_name(self) -> str: ...
    @property
    def applicable_modelos(self) -> tuple[str, ...]: ...


# A typed alias for the raw input mapping passed into builders.
# Mapping not dict so callers may pass any read-only mapping.
FilingInputs = Mapping[str, object]

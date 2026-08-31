"""Cross-module Protocols consumed by :mod:`application.filing`.

Every upstream collaborator (modelo identity, casilla schemas, deadline
engine) is represented by a :class:`typing.Protocol` so the filing
application package does not take a hard import on any sibling subpackage.
Concrete implementations are wired at runtime by the entrypoint.

These Protocols are intentionally minimal: they describe only the
attributes :mod:`application.filing` actually consumes. They do not
attempt to model the full surface of the upstream subpackages.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:  # pragma: no cover — type-only import
    from ...core.casilla_id import CasillaId
    from ...core.identity import SubjectTaxId
    from ...core.period import Period
    from ..calculations.registry.ids import BindingId, FormulaId, LegalRefId, RelationId, SourceRefId
    from ..calculations.registry.schema_surfaces import CasillaConstraints


@runtime_checkable
class CasillaSchema(Protocol):
    """The minimal casilla schema surface consumed by builders.

    Attributes:
        casilla_id: Stable canonical ``casilla.id`` (e.g. ``"01"``).
        value_type: One of ``"decimal"``, ``"int"``, ``"str"``,
            ``"bool"``, ``"date"``.
        required: Whether the casilla must be present in a valid
            draft.
        formula: ID of the formula declared on this casilla, or
            ``None`` for literal casillas.
        formula_input_casilla_ids: Tuple of casilla IDs this casilla depends
            on. Empty for literal casillas.
        legal_refs: Regulatory citations grounding this casilla's
            definition (BOE / AEAT permalinks).
        source_refs: Source-material citations backing this casilla.
        constraints: Complete registry-owned numeric and text constraint
            contract, or ``None`` when the casilla is unconstrained.
        default: Default value used when the casilla is required
            and no input was supplied.
    """

    @property
    def casilla_id(self) -> CasillaId:
        """Return the canonical ``casilla.id`` identifier."""
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
    def formula(self) -> FormulaId | None:
        """Return the formula ID, or ``None`` if this is a literal casilla."""
        ...

    @property
    def formula_input_casilla_ids(self) -> tuple[CasillaId, ...]:
        """Return the casilla IDs this casilla's formula depends on."""
        ...

    @property
    def legal_refs(self) -> tuple[LegalRefId, ...]:
        """Return the regulatory citation IDs grounding this casilla."""
        ...

    @property
    def source_refs(self) -> tuple[SourceRefId, ...]:
        """Return the source-material citation IDs for this casilla."""
        ...

    @property
    def constraints(self) -> CasillaConstraints | None:
        """Return the complete registry-owned constraint contract, if any."""
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

    def get(self, casilla_id: CasillaId) -> CasillaSchema | None:
        """Return the :class:`CasillaSchema` for ``casilla_id``, or ``None``."""
        ...

    def all(self) -> Sequence[CasillaSchema]:
        """Return every casilla schema in the collection.

        Returns:
            Sequence of every :class:`CasillaSchema` in the collection.
        """
        ...


@runtime_checkable
class CasillaSchemaProvider(Protocol):
    """Resolves a casilla collection for a given modelo."""

    def get_collection(self, modelo: str) -> CasillaCollection:
        """Return the casilla collection for ``modelo``.

        Returns:
            The :class:`CasillaCollection` for the given modelo code.
        """
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
    """Checks the filing deadline for a typed modelo period."""

    def check(self, modelo: str, period: Period) -> DeadlineStatus:
        """Return the :class:`DeadlineStatus` for ``modelo`` and ``period``."""
        ...


@runtime_checkable
class ModeloProfile(Protocol):
    """The taxpayer profile a draft is built for.

    Only the attributes :mod:`application.filing` actually consumes are
    declared here; downstream callers may use richer profile
    objects as long as they expose these attributes.
    """

    @property
    def tax_id(self) -> SubjectTaxId:
        """Return the taxpayer's NIF / NIE."""
        ...

    @property
    def display_name(self) -> str:
        """Return a short human-readable label for the taxpayer."""
        ...


# The canonical input contract for casilla, binding, and relation values handed
# to a filing builder. Mapping not dict so callers may pass any
# read-only mapping. This is the single definition of ``ModeloInputs``
# in the codebase; the application/workflow layer re-exports it.
type ModeloInputScalar = str | int | Decimal | bool | date
"""A single casilla, binding-row, or relation value accepted by the filing builder.

Casilla inputs are canonical strings or decimals; year casillas (for
example modelo 390 casilla ``decl.ejercicio``) are plain integers, and registry
bindings additionally accept booleans (``boolean`` data type) and
dates (``text`` data type). ``build_draft`` parses and range-checks
every scalar against the registry casilla / binding schema.
"""

type ModeloInputValue = ModeloInputScalar | Sequence[ModeloInputScalar] | Mapping[str, ModeloInputScalar]
"""A filing-input value.

Most casilla and binding inputs are a single :data:`ModeloInputScalar`.
Repeating-row registry bindings (for example the modelo 131 repeating
activity rows) accept a ``Sequence`` of row scalars, or a ``Mapping``
of explicit row key to scalar.
"""

type ModeloInputs = Mapping[CasillaId | BindingId | RelationId, ModeloInputValue]
"""Read-only input mapping for casilla, binding, and relation values handed to a
filing builder.

Keys are casilla, binding, or relation IDs; values are :data:`ModeloInputValue`.
A workflow inputs-provider that only ever yields flat scalars still
satisfies this contract, so the workflow layer re-exports this symbol
rather than defining a narrower divergent alias.
"""


@runtime_checkable
class ModeloDraftRepositoryProtocol(Protocol):
    """Narrow domain-facing contract for the filing-draft repository.

    :class:`~cadrumo.adapters.persistence.profile.filing_drafts.ModeloDraftRepository`
    structurally conforms to this Protocol; domain service code that only
    needs to load or save drafts should depend inward on this port.
    """

    @property
    def bucket_id(self) -> str | None:
        """Return the profile bucket id when this repository resolved one."""
        ...

    def load(self, record_id: str) -> object:
        """Load a persisted draft by id, or return ``None`` if absent."""
        ...

    def save(self, payload: object) -> None:
        """Persist ``payload`` in the encrypted object store."""
        ...

    def list_draft_ids(self) -> tuple[str, ...]:
        """Return every draft id persisted in this repository."""
        ...


@runtime_checkable
class ModeloAmendmentRepositoryProtocol(Protocol):
    """Narrow domain-facing contract for the filing-amendment repository.

    :class:`~cadrumo.adapters.persistence.profile.filing_amendments.ModeloAmendmentRepository`
    structurally conforms to this Protocol; domain service code that only
    needs to load, save, or list amendments should depend inward on this
    port.
    """

    @property
    def bucket_id(self) -> str | None:
        """Return the profile bucket id when this repository resolved one."""
        ...

    def load(self, amendment_id: str) -> object | None:
        """Load a persisted amendment by id, or return ``None`` if absent."""
        ...

    def save(self, amendment: object) -> None:
        """Persist ``amendment`` in the encrypted object store."""
        ...

    def list_amendment_ids(self) -> tuple[str, ...]:
        """Return every amendment id persisted in this repository."""
        ...

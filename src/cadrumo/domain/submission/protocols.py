"""Narrow Protocol ports for the submission engine.

The submission engine is composed of read-only sub-systems that the
test suite exercises with concrete, hand-rolled Protocol-conforming
classes (no mocks, no patches). Each Protocol declares only the
surface the engine actually consumes, decoupling submission from the
richer surfaces of its sibling subpackages.

- :class:`AuthProviderProbe` — narrow auth-provider surface for the preflight gate.
- :class:`DeadlineWindowChecker` — narrow surface over
  :mod:`cadrumo.domain.deadlines` used by preflight.
- :class:`ModeloFindingLike` / :class:`ModeloDraftLike` /
  :class:`ModeloDraftLoader` — narrow filing draft surfaces;
  :class:`domain.filing.ModeloDraft` structurally conforms to
  :class:`ModeloDraftLike`.
- :class:`SubmissionRepositoryProtocol` — the read-side persistence port.

Every declaration here is a ``runtime_checkable`` ``Protocol``. The record
types these ports carry — :class:`ModeloDraftStatus` and
:class:`ModeloFinding` — live beside the other submission records in
:mod:`cadrumo.domain.submission.models`.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator, Mapping
from datetime import date
from pathlib import Path
from typing import TYPE_CHECKING, Protocol, runtime_checkable

from ...core.auth_provider import AuthProviderDescription
from ...core.errors.severity import BaseSeverity
from .models import ModeloPresentado

if TYPE_CHECKING:  # pragma: no cover — type-only import
    from ...core.identity import SubjectTaxId
    from ...core.period import Period


@runtime_checkable
class AuthProviderProbe(Protocol):
    """Narrow submission-facing auth-provider surface."""

    @property
    def kind(self) -> object:
        """Provider kind identifier consumed by the preflight gate."""
        ...

    def describe(self) -> AuthProviderDescription:
        """Return the active provider's :class:`core.AuthProviderDescription`."""
        ...


@runtime_checkable
class DeadlineWindowChecker(Protocol):
    """Narrow surface over :mod:`cadrumo.domain.deadlines` for the preflight gate."""

    def is_window_open(self, modelo: str, period: Period, today: date) -> bool:
        """Return ``True`` iff the AEAT filing window for ``modelo`` / ``period`` is open on ``today``."""
        ...


@runtime_checkable
class ModeloFindingLike(Protocol):
    """Narrow structural port over one ``draft.findings`` entry.

    Both real implementations declare ``severity`` as a REQUIRED field with
    no default: :class:`cadrumo.domain.submission.models.ModeloFinding`, and
    :class:`domain.filing.ModeloValidationFinding`. Typing
    :attr:`ModeloDraftLike.findings` through this Protocol (rather than
    ``tuple[object, ...]``) lets the preflight gate read ``.severity``
    directly instead of through a ``getattr(..., None)`` guess -- a field
    rename now fails loud instead of silently excluding every finding from
    the error-severity gate.
    """

    @property
    def severity(self) -> BaseSeverity:
        """Return the severity the preflight error-findings gate reads."""
        ...


@runtime_checkable
class ModeloDraftLike(Protocol):
    """Narrow surface over a filing draft.

    :class:`domain.filing.ModeloDraft` structurally conforms to
    this Protocol so the engine can accept either the real draft or any
    Protocol-conforming hand-rolled class in tests.

    Attributes are declared as read-only properties so pyrefly treats them
    covariantly and frozen pydantic models satisfy the protocol without
    invariance errors.
    """

    @property
    def draft_id(self) -> str:
        """Return the draft's stable identifier."""
        ...

    @property
    def modelo(self) -> str:
        """Return the AEAT modelo this draft files."""
        ...

    @property
    def period(self) -> Period:
        """Return the filing period the draft covers."""
        ...

    @property
    def profile_tax_id(self) -> SubjectTaxId:
        """Return the NIF / NIE of the taxpayer the draft is built for."""
        ...

    @property
    def status(self) -> object:
        """Return the draft's lifecycle status.

        Declared as :class:`object` so any draft implementation satisfies the
        Protocol; the preflight gate compares against
        :class:`cadrumo.domain.submission.models.ModeloDraftStatus`.
        """
        ...

    @property
    def values(self) -> Mapping[str, str] | Iterable[object]:
        """Return the draft's casilla values, keyed or iterable by implementation."""
        ...

    @property
    def findings(self) -> tuple[ModeloFindingLike, ...]:
        """Return the validation findings the error-severity gate reads."""
        ...


@runtime_checkable
class ModeloDraftLoader(Protocol):
    """Loads a :class:`ModeloDraftLike` from a draft path on disk."""

    def load(self, _draft_path: Path, /) -> ModeloDraftLike:
        """Load and return the :class:`ModeloDraftLike` at ``draft_path``."""
        ...


@runtime_checkable
class SubmissionRepositoryProtocol(Protocol):
    """Narrow domain-facing repository contract for the submission engine.

    The concrete
    :class:`~cadrumo.adapters.persistence.profile.submission.SubmissionRepository`
    lives in the persistence adapter and inherits from the adapter-layer
    :class:`~cadrumo.adapters.persistence.storage.SecureBoundRepository`. This
    Protocol captures only the surface the engine consumes so the domain
    depends inward on this port, and the application layer constructs the
    concrete repository and injects it into :class:`SubmissionEngine`.
    """

    def load(self, record_id: str, /) -> ModeloPresentado | None:
        """Load a persisted :class:`ModeloPresentado` by id, or return None if absent."""
        ...

    def iter_submissions(self) -> Iterator[ModeloPresentado]:
        """Yield every persisted submission in lexicographic id order.

        Returns:
            Iterator over :class:`ModeloPresentado` records.
        """
        ...

    def list_submission_ids(self) -> tuple[str, ...]:
        """Return every submission id persisted in this repository."""
        ...

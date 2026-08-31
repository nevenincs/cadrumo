"""Narrow Protocol surfaces and value types for the submission engine.

The submission engine is composed of read-only sub-systems that the
test suite exercises with concrete, hand-rolled Protocol-conforming
classes (no mocks, no patches). Each Protocol declares only the
surface the engine actually consumes, decoupling submission from the
richer surfaces of its sibling subpackages.

- :class:`AuthProviderProbe` — narrow auth-provider surface for the preflight gate.
- :class:`DeadlineWindowChecker` — narrow surface over
  :mod:`cadrumo.domain.deadlines` used by preflight.
- :class:`ModeloFinding` / :class:`ModeloDraftLike` /
  :class:`ModeloDraftLoader` — narrow filing draft surfaces;
  :class:`domain.filing.ModeloDraft` structurally conforms to
  :class:`ModeloDraftLike`.

Every record is either a strict+frozen pydantic v2 model or a
``runtime_checkable`` ``Protocol``; no dataclasses; no bare dicts.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator, Mapping
from datetime import date
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING, Protocol, runtime_checkable

from pydantic import BaseModel

from ...core.auth_provider import AuthProviderDescription
from ...core.errors.severity import BaseSeverity
from ...core.models import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from ._models import ModeloPresentado

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


class ModeloFinding(BaseModel):
    """Minimal finding record consumed by the preflight gate.

    Distinct from :class:`domain.filing.ModeloValidationFinding`,
    which carries the validator's full provenance graph; the submission
    engine reads only ``severity`` to decide whether the draft is
    blocked.

    Attributes:
        severity: The finding severity; ``ERROR`` blocks submission.
        message: Multilingual finding message.
    """

    model_config = _STRICT_FROZEN

    severity: BaseSeverity
    message: str


@runtime_checkable
class ModeloFindingLike(Protocol):
    """Narrow structural port over one ``draft.findings`` entry.

    Both real implementations declare ``severity`` as a REQUIRED field with
    no default: :class:`ModeloFinding` above, and
    :class:`domain.filing.ModeloValidationFinding`. Typing
    :attr:`ModeloDraftLike.findings` through this Protocol (rather than
    ``tuple[object, ...]``) lets the preflight gate read ``.severity``
    directly instead of through a ``getattr(..., None)`` guess -- a field
    rename now fails loud instead of silently excluding every finding from
    the error-severity gate.
    """

    @property
    def severity(self) -> BaseSeverity: ...


class ModeloDraftStatus(StrEnum):
    """Lifecycle status of a modelo draft, spanning preparation and submission.

    The state machine carries a draft from creation through validation,
    operator approval, submission, and the AEAT-side terminal states.
    The preflight engine consumes only :attr:`APROBADO` and
    :attr:`APROBACION_CADUCADA` on its happy path; the broader filing /
    submission stack consumes the full lifecycle. Member names and
    values mirror the AEAT Sede labels.

    Attributes:
        BORRADOR: New draft, not yet validated.
        VALIDADO: Validation rules executed without errors.
        LISTO_PARA_PRESENTAR: Draft fully prepared for an attempt.
        APROBADO: Operator-approved for submission.
        APROBACION_CADUCADA: Approval timestamp aged out.
        PRESENTADA: A submission attempt is recorded.
        ACEPTADA: AEAT acknowledged the filing.
        RECHAZADA: AEAT rejected the filing.
        ENMENDADO: Superseded by an amendment record.
        ANULADO: Operator cancelled before submission.
    """

    BORRADOR = "BORRADOR"
    VALIDADO = "VALIDADO"
    LISTO_PARA_PRESENTAR = "LISTO_PARA_PRESENTAR"
    APROBADO = "APROBADO"
    APROBACION_CADUCADA = "APROBACION_CADUCADA"
    PRESENTADA = "PRESENTADA"
    ACEPTADA = "ACEPTADA"
    RECHAZADA = "RECHAZADA"
    ENMENDADO = "ENMENDADO"
    ANULADO = "ANULADO"


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
    def draft_id(self) -> str: ...

    @property
    def modelo(self) -> str: ...

    @property
    def period(self) -> Period: ...

    @property
    def profile_tax_id(self) -> SubjectTaxId: ...

    @property
    def status(self) -> object: ...

    @property
    def values(self) -> Mapping[str, str] | Iterable[object]: ...

    @property
    def findings(self) -> tuple[ModeloFindingLike, ...]: ...


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

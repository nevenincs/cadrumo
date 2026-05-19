"""Narrow Protocol surfaces and value types for the submission engine.

The submission engine is composed of read-only sub-systems that the
test suite exercises with concrete, hand-rolled Protocol-conforming
classes (no mocks, no patches). Each Protocol declares only the
surface the engine actually consumes, decoupling submission from the
richer surfaces of its sibling subpackages.

- ``AuthProviderProbe`` — narrow auth-provider surface for the preflight gate.
- ``DeadlineWindowChecker`` — narrow surface over
  :mod:`aeat.domain.deadlines` used by preflight.
- ``ModeloFinding`` / ``ModeloDraftLike`` / ``ModeloDraftLoader`` — narrow
  filing draft surfaces; :class:`aeat.application.filing.ModeloDraft`
  structurally conforms to ``ModeloDraftLike``.

Every record is either a strict+frozen pydantic v2 model or a
``runtime_checkable`` ``Protocol``; no dataclasses; no bare dicts.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import date
from enum import StrEnum
from pathlib import Path
from typing import Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict

from ...core.errors import BaseSeverity

_STRICT_FROZEN = ConfigDict(strict=True, frozen=True, extra="forbid")


@runtime_checkable
class AuthProviderDescriptionLike(Protocol):
    """Submission-facing shape returned by an auth provider.

    Attributes:
        kind: Provider identifier (kept as ``object`` so the protocol does
            not couple submission to the auth subpackage's enum).
        label: Human-readable provider name.
        configured: Whether the provider's required settings are present.
        available: Whether a session can currently be established.
        subject: Subject DN (or equivalent identity string), if known.
        expires_on: Expiry date for the underlying credential, if known.
    """

    @property
    def kind(self) -> object:
        """Provider kind identifier."""
        ...

    @property
    def label(self) -> str:
        """Human-readable provider name."""
        ...

    @property
    def configured(self) -> bool:
        """Whether the provider's required settings are present."""
        ...

    @property
    def available(self) -> bool:
        """Whether a session can currently be established."""
        ...

    @property
    def subject(self) -> str | None:
        """Subject DN or identity string when known, else ``None``."""
        ...

    @property
    def expires_on(self) -> date | None:
        """Expiry date for the underlying credential, when known."""
        ...


@runtime_checkable
class AuthProviderProbe(Protocol):
    """Narrow submission-facing auth-provider surface."""

    @property
    def kind(self) -> object:
        """Provider kind identifier consumed by the preflight gate."""
        ...

    def describe(self) -> AuthProviderDescriptionLike:
        """Return a safe description of the active auth provider."""
        ...


@runtime_checkable
class DeadlineWindowChecker(Protocol):
    """Narrow surface over :mod:`aeat.domain.deadlines` for the preflight gate."""

    def is_window_open(self, modelo: str, period: str, today: date) -> bool:
        """Return ``True`` iff the AEAT filing window for ``modelo`` /
        ``period`` is open on ``today``."""
        ...


class ModeloFinding(BaseModel):
    """Minimal finding record consumed by the preflight gate.

    Distinct from :class:`aeat.application.filing.ModeloValidationFinding`,
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


class ModeloDraftStatus(StrEnum):
    """Lifecycle status of a modelo draft, spanning preparation and submission.

    The state machine carries a draft from creation through validation,
    operator approval, submission, and the AEAT-side terminal states.
    The preflight engine consumes only :attr:`APPROVED` and
    :attr:`APPROVAL_STALE` on its happy path; the broader filing /
    submission stack consumes the full lifecycle.

    Attributes:
        DRAFT: New draft, not yet validated.
        VALIDATED: Validation rules executed without errors.
        READY_TO_SUBMIT: Draft fully prepared for an attempt.
        APPROVED: Operator-approved for submission.
        APPROVAL_STALE: Approval timestamp aged out.
        SUBMITTED: A submission attempt is recorded.
        ACKNOWLEDGED: AEAT acknowledged the filing.
        REJECTED: AEAT rejected the filing.
        AMENDED: Superseded by an amendment record.
        CANCELLED: Operator cancelled before submission.
    """

    DRAFT = "DRAFT"
    VALIDATED = "VALIDATED"
    READY_TO_SUBMIT = "READY_TO_SUBMIT"
    APPROVED = "APPROVED"
    APPROVAL_STALE = "APPROVAL_STALE"
    SUBMITTED = "SUBMITTED"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    REJECTED = "REJECTED"
    AMENDED = "AMENDED"
    CANCELLED = "CANCELLED"


@runtime_checkable
class ModeloDraftLike(Protocol):
    """Narrow surface over a filing draft.

    :class:`aeat.application.filing.ModeloDraft` structurally conforms to
    this Protocol so the engine can accept either the real draft or any
    Protocol-conforming hand-rolled class in tests.

    Attributes are declared as read-only properties so pyright treats them
    covariantly and frozen pydantic models satisfy the protocol without
    invariance errors.
    """

    @property
    def draft_id(self) -> str: ...

    @property
    def modelo(self) -> str: ...

    @property
    def period(self) -> str: ...

    @property
    def profile_tax_id(self) -> str: ...

    @property
    def status(self) -> object: ...

    @property
    def values(self) -> Mapping[str, str] | Iterable[object]: ...

    @property
    def findings(self) -> tuple[object, ...]: ...


@runtime_checkable
class ModeloDraftLoader(Protocol):
    """Loads a :class:`ModeloDraftLike` from a draft path on disk."""

    def load(self, draft_path: Path) -> ModeloDraftLike:
        """Load and return the :class:`ModeloDraftLike` at ``draft_path``."""
        ...

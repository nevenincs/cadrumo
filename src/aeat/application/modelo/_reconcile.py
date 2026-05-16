"""Modelo reconciliation: compare a work unit against external evidence.

`modelo_reconcile` accepts a modelo work unit and one source of external
evidence (either an AEAT justificante PDF or a filed-declaration PDF)
and produces a :class:`ModeloReconciliationReport` recording whether
the work unit's most recent calculation matches the external evidence.

The service is local-only: it never contacts AEAT and never invokes
``require_live_read``. It composes the existing low-level reconciler in
:mod:`aeat.application.filing.reconciliation._reconcile` with a parser
for the supplied source kind.

The CLI verb ``aeat app modelo reconcile`` (per the app-modelo-shape
ADR amendment) is a thin delegate over this service.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from ...core.errors import AeatError

_STRICT_FROZEN = ConfigDict(strict=True, frozen=True, extra="forbid")


class ModeloReconciliationSourceKind(StrEnum):
    """Closed set of external-evidence kinds the operator can supply."""

    JUSTIFICANTE = "justificante"
    DECLARATION = "declaration"


class ModeloReconciliationVerdict(StrEnum):
    """Closed verdict catalogue for :class:`ModeloReconciliationReport`.

    Drawn from the 2026-05-15 amendment to the app-modelo-shape ADR:
    ``matches`` / ``mismatches`` / ``evidence_invalid``, plus
    ``not_yet_found`` for the case where no matching external record
    is present yet.
    """

    MATCHES = "matches"
    MISMATCHES = "mismatches"
    EVIDENCE_INVALID = "evidence_invalid"
    NOT_YET_FOUND = "not_yet_found"


class ModeloReconciliationDiff(BaseModel):
    """One per-casilla disagreement between work unit and evidence."""

    model_config = _STRICT_FROZEN

    field_name: str = Field(min_length=1)
    work_unit_value: str = ""
    evidence_value: str = ""
    kind: str = Field(min_length=1)


class ModeloReconciliationCommand(BaseModel):
    """Strict input contract for ``modelo_reconcile``.

    Exactly one of ``from_justificante`` or ``from_declaration`` must be
    supplied. The CLI handler enforces the exclusivity before constructing
    the command; the model itself records the chosen source.
    """

    model_config = _STRICT_FROZEN

    work_unit_id: str = Field(min_length=1, max_length=128)
    source_kind: ModeloReconciliationSourceKind
    source_path: Path


class ModeloReconciliationReport(BaseModel):
    """Outcome of ``modelo_reconcile``.

    The verdict summarises the comparison at the work-unit level. The
    diff list enumerates per-casilla disagreements (empty on
    ``matches``). The wrapped reconciler report is the lower-level
    field-by-field comparison from
    :mod:`aeat.application.filing.reconciliation._reconcile`.
    """

    model_config = _STRICT_FROZEN

    work_unit_id: str = Field(min_length=1, max_length=128)
    bucket_id: str = Field(min_length=1, max_length=128)
    source_kind: ModeloReconciliationSourceKind
    source_path: str
    verdict: ModeloReconciliationVerdict
    diffs: tuple[ModeloReconciliationDiff, ...] = ()
    reconciled_at: datetime
    narrative: str = ""


class ReconciliationEvidenceInvalidError(AeatError):
    """Raised when the supplied external evidence cannot be parsed.

    The complementaria-external-filing-path ADR mandates this error for
    malformed justificantes. The CLI surfaces it as a refusal with the
    canonical recovery hint; downstream consumers branch on it without
    string-matching the message.
    """


class ReconciliationDeclarationSourceUnsupportedError(AeatError):
    """Raised when ``from_declaration`` is requested before the declaration
    parser ships.

    The app-modelo-shape ADR amendment lists ``--from-declaration PATH``
    as a required surface variant. Until the parser lands, the service
    refuses cleanly rather than silently degrading.
    """


__all__ = [
    "ModeloReconciliationCommand",
    "ModeloReconciliationDiff",
    "ModeloReconciliationReport",
    "ModeloReconciliationSourceKind",
    "ModeloReconciliationVerdict",
    "ReconciliationDeclarationSourceUnsupportedError",
    "ReconciliationEvidenceInvalidError",
]

"""Pure comparator from ``FilingDraft`` and ``RemoteFiling`` to ``ReconciliationReport``.

The reconciler is intentionally async-free and free of any I/O. The
caller fetches the AEAT-side data via a
:class:`aeat.remote.RemoteFilingFetcher` (or any other read-only
mechanism) and hands the already-typed
:class:`aeat.remote.RemoteFiling` (or ``None``) to
:func:`reconcile`. The function returns a frozen
:class:`ReconciliationReport` deterministically derived from the two
inputs, the rounding tolerance, and the wall-clock timestamp.

Flow:

1. When ``remote`` is ``None`` (or the legacy empty-tuple shape) the
   function emits a single
   :attr:`FilingDivergenceKind.FILING_NOT_YET_FOUND` sentinel delta
   and returns
   :attr:`ReconciliationStatus.NOT_YET_FOUND` with ``remote_ref=None``.
2. Otherwise the comparator builds the local and remote casilla maps,
   walks the union of casilla identifiers, and classifies each entry
   into one of the six :class:`FilingDivergenceKind` variants
   (rounding-only when ``abs(local - remote) <= tolerance``).
3. The filing-level status check folds in a
   :attr:`FilingDivergenceKind.FILING_STATUS_DIVERGENCE` entry when
   the local approval state and the remote status disagree, including
   when the remote status is ``RECHAZADA`` / ``ANULADA`` / ``UNKNOWN``.
4. The aggregate :class:`ReconciliationStatus` is derived from the
   per-delta kinds via the static :data:`KIND_TO_STATUS` table; the
   triad is mutually exclusive.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Final

from ...remote import RemoteFiling, RemoteFilingRef, RemoteFilingStatus
from .._schema import FilingDraft, FilingDraftStatus, FilingValueKind
from ._kind import FilingDivergenceKind
from ._narrative import compose_delta_narrative, compose_report_narrative
from ._schema import (
    KIND_TO_STATUS,
    CasillaDelta,
    FilingDraftRef,
    ReconciliationReport,
    ReconciliationStatus,
)
from ._tolerance import RECONCILIATION_TOLERANCE

_FILING_SCOPE_SENTINEL: Final[str] = "*"
"""Casilla id placeholder for filing-scoped (non-casilla) divergences."""


def _utcnow() -> datetime:
    """Return the current UTC wall-clock time (injection seam for tests)."""
    return datetime.now(tz=UTC)


def _coerce_to_decimal(value: object) -> Decimal | None:
    """Convert an arbitrary value to :class:`Decimal` when feasible."""
    if value is None:
        return None
    if isinstance(value, Decimal):
        return value
    if isinstance(value, bool):
        # bool is an int subclass; treat it as non-monetary.
        return None
    if isinstance(value, int):
        return Decimal(value)
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        try:
            return Decimal(text)
        except (InvalidOperation, ValueError):
            return None
    return None


def _format_scalar(value: object) -> str | None:
    """Render a scalar as the report's ``str | None`` payload."""
    if value is None:
        return None
    if isinstance(value, Decimal):
        return format(value, "f")
    return str(value)


def _build_local_map(draft: FilingDraft) -> dict[str, object]:
    """Project the draft's casilla values into a comparable mapping.

    Skips :attr:`FilingValueKind.EMPTY` entries — an empty casilla on
    the local side is semantically the same as the casilla being
    absent, and treating it otherwise would surface phantom
    :attr:`FilingDivergenceKind.CASILLA_EXTRA_LOCAL` divergences for
    every blank line in the draft.
    """
    local: dict[str, object] = {}
    for value in draft.values:
        if value.kind is FilingValueKind.EMPTY:
            continue
        if value.value is None:
            continue
        local[value.casilla_id] = value.value
    return local


def _build_remote_map(filing: RemoteFiling) -> dict[str, object]:
    """Project the remote filing's casillas into a comparable mapping."""
    remote: dict[str, object] = {}
    for casilla in filing.casillas:
        if casilla.coerced_value is None:
            continue
        remote[casilla.casilla_id] = casilla.coerced_value
    return remote


def _classify_pair(
    *,
    casilla_id: str,
    local: object,
    remote: object,
    tolerance: Decimal,
) -> CasillaDelta:
    """Build the :class:`CasillaDelta` for a casilla present on one or both sides."""
    local_decimal = _coerce_to_decimal(local) if local is not None else None
    remote_decimal = _coerce_to_decimal(remote) if remote is not None else None
    local_text = _format_scalar(local)
    remote_text = _format_scalar(remote)

    if local is None:
        kind = FilingDivergenceKind.CASILLA_MISSING_LOCAL
        delta = None
    elif remote is None:
        kind = FilingDivergenceKind.CASILLA_EXTRA_LOCAL
        delta = None
    else:
        if local_decimal is not None and remote_decimal is not None:
            delta = local_decimal - remote_decimal
            if abs(delta) <= tolerance and delta != 0:
                kind = FilingDivergenceKind.ROUNDING_ONLY
            else:
                kind = FilingDivergenceKind.CASILLA_VALUE_MISMATCH
        else:
            # Non-decimal types: equality on the formatted text.
            delta = None
            if local_text == remote_text:
                kind = FilingDivergenceKind.ROUNDING_ONLY
            else:
                kind = FilingDivergenceKind.CASILLA_VALUE_MISMATCH

    narrative = compose_delta_narrative(
        casilla_id=casilla_id,
        kind=kind,
        local_value=local_text,
        remote_value=remote_text,
        delta=delta,
    )
    return CasillaDelta(
        casilla_id=casilla_id,
        kind=kind,
        local_value=local_text,
        remote_value=remote_text,
        delta=delta,
        narrative=narrative,
    )


_REMOTE_TERMINAL_CLEAN: frozenset[RemoteFilingStatus] = frozenset(
    {
        RemoteFilingStatus.PRESENTADA,
        RemoteFilingStatus.SUBSANADA,
        RemoteFilingStatus.COMPLEMENTARIA,
    }
)


def _draft_status_text(status: FilingDraftStatus) -> str:
    return status.value


def _remote_status_text(status: RemoteFilingStatus) -> str:
    return status.value


def _filing_status_delta(
    *,
    draft: FilingDraft,
    filing: RemoteFiling,
) -> CasillaDelta | None:
    """Surface a filing-status divergence when the two sides disagree.

    The local approval state ``APPROVED`` implies the draft is queued
    for or already at AEAT — the only remote statuses that match are
    the terminal-clean members
    (``PRESENTADA`` / ``SUBSANADA`` / ``COMPLEMENTARIA``). Any other
    remote status (``EN_TRAMITACION`` / ``RECHAZADA`` / ``ANULADA`` /
    ``UNKNOWN``) yields a divergence so Kent sees the mismatch.

    The local lifecycle states ``SUBMITTED`` / ``ACKNOWLEDGED``
    similarly demand the remote to be terminal-clean. Lifecycle states
    that pre-date upload (``DRAFT`` / ``VALIDATED`` / ``READY_TO_SUBMIT``
    / ``APPROVAL_STALE``) flag any remote presence as divergent because
    AEAT shouldn't have a record of a draft Kent has not committed to.
    """
    expected_clean: frozenset[FilingDraftStatus] = frozenset(
        {
            FilingDraftStatus.APPROVED,
            FilingDraftStatus.SUBMITTED,
            FilingDraftStatus.ACKNOWLEDGED,
            FilingDraftStatus.AMENDED,
        }
    )
    pre_upload: frozenset[FilingDraftStatus] = frozenset(
        {
            FilingDraftStatus.DRAFT,
            FilingDraftStatus.VALIDATED,
            FilingDraftStatus.READY_TO_SUBMIT,
            FilingDraftStatus.APPROVAL_STALE,
        }
    )

    local_text = _draft_status_text(draft.status)
    remote_text = _remote_status_text(filing.status)

    diverges = (
        (draft.status in expected_clean and filing.status not in _REMOTE_TERMINAL_CLEAN)
        or (draft.status in pre_upload)
        or (draft.status is FilingDraftStatus.REJECTED and filing.status is not RemoteFilingStatus.RECHAZADA)
        or (draft.status is FilingDraftStatus.CANCELLED and filing.status is not RemoteFilingStatus.ANULADA)
    )

    if not diverges:
        return None

    narrative = compose_delta_narrative(
        casilla_id=_FILING_SCOPE_SENTINEL,
        kind=FilingDivergenceKind.FILING_STATUS_DIVERGENCE,
        local_value=local_text,
        remote_value=remote_text,
        delta=None,
    )
    return CasillaDelta(
        casilla_id=_FILING_SCOPE_SENTINEL,
        kind=FilingDivergenceKind.FILING_STATUS_DIVERGENCE,
        local_value=local_text,
        remote_value=remote_text,
        delta=None,
        narrative=narrative,
    )


def _aggregate_status(deltas: tuple[CasillaDelta, ...]) -> ReconciliationStatus:
    """Reduce per-delta kinds to the report's terminal-triad member."""
    seen_kinds = {delta.kind for delta in deltas}
    if FilingDivergenceKind.FILING_NOT_YET_FOUND in seen_kinds:
        return ReconciliationStatus.NOT_YET_FOUND
    for kind in seen_kinds:
        if KIND_TO_STATUS[kind] is ReconciliationStatus.DIVERGENT:
            return ReconciliationStatus.DIVERGENT
    return ReconciliationStatus.MATCH


def reconcile(
    draft: FilingDraft,
    remote: RemoteFiling | None,
    *,
    tolerance: Decimal = RECONCILIATION_TOLERANCE,
    now: Callable[[], datetime] = _utcnow,
) -> ReconciliationReport:
    """Compare ``draft`` against ``remote`` and emit a frozen report.

    Args:
        draft: The local :class:`aeat.filing.FilingDraft` to reconcile.
        remote: The AEAT-side :class:`aeat.remote.RemoteFiling` to
            anchor the comparison against, or ``None`` when AEAT has
            no expediente for the expected ``(modelo, period)``.
        tolerance: Maximum absolute monetary delta still classified as
            :attr:`FilingDivergenceKind.ROUNDING_ONLY`. Defaults to
            :data:`RECONCILIATION_TOLERANCE`.
        now: Injection seam for the wall-clock timestamp used in
            ``reconciled_at``. Tests hand a frozen callable here.

    Returns:
        A frozen :class:`ReconciliationReport` whose ``status`` is one
        of :attr:`ReconciliationStatus.MATCH`,
        :attr:`ReconciliationStatus.DIVERGENT`, or
        :attr:`ReconciliationStatus.NOT_YET_FOUND`. The triad is
        mutually exclusive: ``NOT_YET_FOUND`` short-circuits per-casilla
        comparison.
    """
    timestamp = now()
    draft_ref = FilingDraftRef(
        draft_id=draft.draft_id,
        modelo=draft.modelo,
        period=draft.period,
        profile_tax_id=draft.profile_tax_id,
        status=draft.status,
    )

    if remote is None:
        sentinel_narrative = compose_delta_narrative(
            casilla_id=_FILING_SCOPE_SENTINEL,
            kind=FilingDivergenceKind.FILING_NOT_YET_FOUND,
            local_value=None,
            remote_value=None,
            delta=None,
        )
        sentinel = CasillaDelta(
            casilla_id=_FILING_SCOPE_SENTINEL,
            kind=FilingDivergenceKind.FILING_NOT_YET_FOUND,
            local_value=None,
            remote_value=None,
            delta=None,
            narrative=sentinel_narrative,
        )
        report_narrative = compose_report_narrative(
            status=ReconciliationStatus.NOT_YET_FOUND,
            modelo=draft.modelo,
            period=draft.period,
            delta_count=1,
        )
        return ReconciliationReport(
            status=ReconciliationStatus.NOT_YET_FOUND,
            casilla_deltas=(sentinel,),
            remote_ref=None,
            draft_ref=draft_ref,
            reconciled_at=timestamp,
            narrative=report_narrative,
        )

    local_map = _build_local_map(draft)
    remote_map = _build_remote_map(remote)
    every_id = sorted(set(local_map) | set(remote_map))

    deltas: list[CasillaDelta] = []
    for casilla_id in every_id:
        local_value = local_map.get(casilla_id)
        remote_value = remote_map.get(casilla_id)
        if local_value is None and remote_value is None:
            continue
        # Skip exact-equal pairs (same Decimal value) — no delta to report.
        local_decimal = _coerce_to_decimal(local_value) if local_value is not None else None
        remote_decimal = _coerce_to_decimal(remote_value) if remote_value is not None else None
        if local_decimal is not None and remote_decimal is not None and local_decimal == remote_decimal:
            continue
        # For non-decimal pairs that string-compare equal, skip too.
        if (
            local_decimal is None
            and remote_decimal is None
            and local_value is not None
            and remote_value is not None
            and _format_scalar(local_value) == _format_scalar(remote_value)
        ):
            continue
        deltas.append(
            _classify_pair(
                casilla_id=casilla_id,
                local=local_value,
                remote=remote_value,
                tolerance=tolerance,
            )
        )

    status_delta = _filing_status_delta(draft=draft, filing=remote)
    if status_delta is not None:
        deltas.append(status_delta)

    delta_tuple = tuple(deltas)
    status = _aggregate_status(delta_tuple)
    report_narrative = compose_report_narrative(
        status=status,
        modelo=draft.modelo,
        period=draft.period,
        delta_count=len(delta_tuple),
    )
    remote_ref = RemoteFilingRef(
        expediente_id=remote.expediente_id,
        modelo=remote.modelo,
        period=remote.period,
        captured_at=timestamp,
    )
    return ReconciliationReport(
        status=status,
        casilla_deltas=delta_tuple,
        remote_ref=remote_ref,
        draft_ref=draft_ref,
        reconciled_at=timestamp,
        narrative=report_narrative,
    )


__all__ = ["reconcile"]

"""Modelo 130 dry-run submitter (pago fraccionado IRPF autonomos).

Walks the AEAT Modelo 130 portal, fills casilla-keyed inputs from
``draft.values``, takes screenshots at every step, and records a
Playwright trace. The :meth:`dry_run` path aborts before the final
"Firmar y Enviar" click and writes a form-state snapshot.

The submitter consumes the narrow
:class:`aeat.submission._submitters._contract.BrowserSessionLike`
Protocol — the production ``aeat.browser.BrowserSession`` structurally
conforms, while unit tests pass a deterministic Protocol
implementation.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path

from ...logging import get_logger
from .._errors import SubmissionFormFillError
from .._models import SubmissionAttempt, SubmissionStatus
from .._protocols import (
    CasillaCatalogue,
    FilingDraftLike,
    Portal,
)
from . import Submitter
from ._contract import BrowserSessionLike

_logger = get_logger(__name__)

_MODELO = "130"


class Modelo130Submitter(Submitter):
    """Concrete :class:`Submitter` for AEAT Modelo 130.

    Attributes:
        artifact_dir: Directory under which screenshots, traces, and
            form-state snapshots are written. Each attempt creates a
            subdirectory keyed on the attempt id.
    """

    def __init__(self, *, artifact_dir: Path) -> None:
        """Construct a Modelo 130 submitter.

        Args:
            artifact_dir: Directory for per-attempt artefacts.
        """
        self.artifact_dir = artifact_dir

    @property
    def modelo(self) -> str:
        """Return the modelo identifier (``"130"``)."""
        return _MODELO

    def _attempt_dir(self, draft_id: str, suffix: str) -> Path:
        """Return (and create) the artefact directory for one attempt."""
        path = self.artifact_dir / f"{draft_id}-{suffix}"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def _casilla_selector(self, casilla_id: str) -> str:
        """Return the CSS selector for a casilla input on the portal."""
        return f"input[name='casilla_{casilla_id}']"

    async def _apply_amendment_controls(
        self,
        *,
        amendment_kind: str | None,
        original_csv: str | None,
    ) -> None:
        """Log the amendment intent until the exact AEAT field map lands.

        Issue #93 owns the amendment engine, not the final Modelo 130
        selector map. The transport still carries the legally relevant
        metadata through this submitter so the later browser-mapping
        rebase is a contained diff.
        """
        if amendment_kind is None:
            return
        _logger.warning(
            "modelo130 amendment transport requested kind=%s original_csv=%s; "
            "exact portal field mapping is still pending",
            amendment_kind,
            original_csv,
        )

    async def _walk_form(
        self,
        *,
        draft: FilingDraftLike,
        session: BrowserSessionLike,
        casilla_catalogue: CasillaCatalogue,
        portal: Portal,
        attempt_dir: Path,
        amendment_kind: str | None,
        original_csv: str | None,
    ) -> None:
        """Shared portal walk used by both :meth:`dry_run` and :meth:`submit`."""
        await session.navigate(portal.presentation_url)
        await session.screenshot(attempt_dir / "01-landing.png")
        await self._apply_amendment_controls(
            amendment_kind=amendment_kind,
            original_csv=original_csv,
        )

        casillas = casilla_catalogue.casillas_for_modelo(_MODELO)
        known_ids = {c.id for c in casillas}
        for casilla_id, value in _iter_draft_values(draft):
            if casilla_id not in known_ids:
                raise SubmissionFormFillError(f"draft references unknown casilla {casilla_id!r} for modelo {_MODELO}")
            await session.fill(self._casilla_selector(casilla_id), value)

        await session.screenshot(attempt_dir / "02-form-filled.png")

    async def dry_run(
        self,
        *,
        draft: FilingDraftLike,
        session: BrowserSessionLike,
        casilla_catalogue: CasillaCatalogue,
        portal: Portal,
        amendment_kind: str | None = None,
        original_csv: str | None = None,
    ) -> SubmissionAttempt:
        """Run the full form-fill walk and abort before "Firmar y Enviar"."""
        started = datetime.now(UTC)
        attempt_dir = self._attempt_dir(draft.draft_id, "dry-run")
        trace_path = attempt_dir / "trace.zip"

        _logger.info("modelo130 dry-run start: draft=%s", draft.draft_id)
        await session.trace_start(f"modelo130-dry-run-{draft.draft_id}")
        try:
            await self._walk_form(
                draft=draft,
                session=session,
                casilla_catalogue=casilla_catalogue,
                portal=portal,
                attempt_dir=attempt_dir,
                amendment_kind=amendment_kind,
                original_csv=original_csv,
            )
            await session.snapshot_form_state(attempt_dir / "form_state.json")
            _logger.info("modelo130 dry-run: aborting before 'Firmar y Enviar'")
        finally:
            await session.trace_stop(trace_path)

        ended = datetime.now(UTC)
        return SubmissionAttempt(
            attempt_id=f"{draft.draft_id}-dry-run",
            started_at=started,
            ended_at=ended,
            status=SubmissionStatus.PENDING,
            browser_trace_path=trace_path,
        )


def _iter_draft_values(draft: FilingDraftLike) -> tuple[tuple[str, str], ...]:
    """Normalize both protocol-style mappings and real FilingDraft tuples."""
    values = draft.values
    if isinstance(values, Mapping):
        return tuple((str(casilla_id), str(value)) for casilla_id, value in values.items())
    normalized: list[tuple[str, str]] = []
    for entry in values:
        casilla_id = getattr(entry, "casilla_id", None)
        value = getattr(entry, "value", None)
        if not isinstance(casilla_id, str):
            raise SubmissionFormFillError("draft values entry is missing casilla_id")
        normalized.append((casilla_id, "" if value is None else str(value)))
    return tuple(normalized)

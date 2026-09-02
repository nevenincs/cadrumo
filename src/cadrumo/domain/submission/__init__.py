"""Public facade for local-only submission audit records.

This package exposes preflight gates, historical/imported audit records,
repository storage, and narrow protocol types for submission-adjacent flows.
:class:`SubmissionEngine` is read-only: it runs :class:`Preflight` and reads
persisted :class:`ModeloPresentado` records. It does not present to AEAT, create
submission records, or transition a draft or revision into ``presentado``.

:class:`Preflight` checks approved draft status, absence of error findings, the
deadline window unless skipped, and auth-provider readiness. The engine depends
on deadline and auth-provider probes; :class:`ModeloDraftLoader` remains an
exported adapter contract, not a dependency consumed by :class:`SubmissionEngine`.

:class:`ModeloPresentado` is a strict local-only historical/imported audit
record persisted through the :class:`SubmissionRepositoryProtocol` port —
implemented by the adapter
:class:`~cadrumo.adapters.persistence.profile.submission.SubmissionRepository` — as
encrypted AUDIT data under ``cadrumo.domain.submission.records``. It is distinct from
:class:`~ModeloRecord`:
:func:`application.modelo.file_modelo_revision` creates a local work-unit filing
record with ``aeat_accepted=False`` and no external evidence, while
:func:`application.modelo.import_external_filing_evidence` imports historical
filing evidence into the audit trail.

Live AEAT writes are blocked by
:meth:`core.access_gate.AeatAccessGate.require_live_write`, which raises
:exc:`core.access_gate.LiveSubmitForbiddenError`; preflight denials raise
:exc:`SubmissionPreflightError`.

Major declarations:

* :class:`SubmissionEngine` — runs preflight and reads historical audit records.
* :class:`Preflight` and :exc:`SubmissionPreflightError` — the
  pre-submission checks and their refusal.
* :class:`ModeloPresentado`, :class:`SubmissionAttempt`, and
  :class:`SubmissionStatus` — the persisted lifecycle records, keyed by
  :func:`make_submission_id`.
* :class:`SubmissionRepositoryProtocol` — the read-side persistence port
  (the concrete repository lives in the persistence adapter).
* The :class:`ModeloDraftLoader`, :class:`ModeloDraftLike`,
  :class:`DeadlineWindowChecker`, and :class:`AuthProviderProbe` protocols —
  exported narrow contracts that keep the domain free of live adapters.

See Also:
    :func:`application.modelo.file_modelo_revision`
        Local work-unit filing action that creates
        :class:`~ModeloRecord` entries without AEAT
        acceptance.
    :mod:`application.live`
        Read-only AEAT evidence capture and justificante verification surface;
        it is not a live-submit path.
    :func:`application.modelo.import_external_filing_evidence`
        Historical filing-evidence import into the submission audit trail.
    :mod:`domain.justificante`
        Receipt metadata that can seed imported submission-audit baselines
        without becoming casilla-value authority.
    :func:`application.modelo.import_external_filing_evidence`
        Separate work-unit path that stamps
        :class:`~ExternalEvidence` on current filing records;
        it does not create :class:`ModeloPresentado` audit records.
    :mod:`domain.filing`
        Draft construction and review records used before preflight or evidence
        import.
    :class:`core.access_gate.AeatAccessGate`
        Core live-write refusal authority that keeps these audit records local.
"""

from __future__ import annotations

__all__: tuple[str, ...] = ()

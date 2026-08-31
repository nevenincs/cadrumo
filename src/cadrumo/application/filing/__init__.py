"""Public application facade for registry-backed filing drafts.

This package builds, reviews, approves, exports, verifies, imports, and
summarises local filing artefacts. All draft creation and validation consume
a :class:`RegistrySnapshot` to resolve the
active :class:`ModeloRevision`, its casilla
schema, relation inputs, and formula graph.

Major entry points:

* :func:`build_draft` constructs a validated
  :class:`ModeloDraft` from registry-backed inputs.
* :func:`approve_draft`, :func:`unapprove_draft`, and
  :func:`refresh_review_status` manage local review state and approval basis.
* :func:`export_draft` writes a local fichero-BOE artefact, and
  :func:`verify_export` re-reads that file through the registry export parser.
* :func:`import_filing_from_justificante` reconstructs a draft-level local
  receipt baseline and companion
  :class:`ModeloPresentado` audit record from a
  justificante PDF without treating the receipt as a casilla-value authority.
* :func:`build_complementaria`, :func:`list_amendments`, and
  :func:`load_amendment` build and read governed
  :class:`ModeloComplementaria` and
  :class:`ModeloSustitutiva` amendment records.
* :class:`ModeloHistoryRepository` persists encrypted lightweight
  :class:`ModeloHistory` summaries for local
  filing-history views.
* :func:`build_runtime_schema_provider` supplies the runtime registry view used
  by draft construction, review, export, and verification.

The facade deliberately separates local filing state from live submission.
Remote AEAT submission is not exposed here; attempted live writes are refused
by :class:`LiveSubmitForbiddenError`.

Imports from external PDFs stay evidence-scoped. A justificante import creates a
local draft plus submission-audit baseline, while casilla-complete declaration
and borrador parsing enter through the inbound adapter surfaces before
application services decide how that evidence participates in a work-unit
workflow.

Work-unit filing records for calculation revisions live in
:mod:`modelo` and :mod:`domain.modelos`. This package owns
draft-level construction, review, export, verification, justificante import,
local amendment construction, and lightweight local history; it does not create
:class:`ModeloRecord` entries or stamp :class:`ExternalEvidence`.

See Also:
    :mod:`modelo`
        Operator-facing modelo facade that carries calculation revisions into
        this filing surface.
    :func:`file_modelo_revision`
        Work-unit action that records a verified calculation revision as a
        current local :class:`ModeloRecord`.
    :func:`import_external_filing_evidence`
        External-evidence import path that creates an evidenced
        :class:`ModeloRecord` baseline for amendments.
    :mod:`domain.justificante`
        Receipt-metadata domain used by justificante PDF imports and
        receipt-bound external evidence.
    :mod:`domain.filing`
        Canonical draft records, values, provenance, validation findings, and
        review helpers.
    :mod:`domain.submission`
        Local-only submission audit records populated by justificante import;
        this is not an AEAT live-submit path.
    :mod:`domain.calculations.registry`
        Registry authority, snapshots, export layouts, and formula execution
        used by this application facade.
"""

from __future__ import annotations

__all__: tuple[str, ...] = ()

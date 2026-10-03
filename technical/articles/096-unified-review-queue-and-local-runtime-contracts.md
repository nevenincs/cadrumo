# Unified review queue and local runtime contracts

[Technical overview](../README.md) · [Article index](README.md) · [Snapshot and reading guide](../reading-guide.md)

> This page describes the analyzed source snapshot. Its findings and limitations are not a certification of the current branch.

**Report:** `STAGE-2-096` · **Topic:** [Operations, profiles and workflows](../topics/operations-profiles-and-workflows.md)

<!-- preserved:article -->
**Scope:** 30 files under `src/cadrumo/application/review` and `src/cadrumo/application/runtime`, totaling 5,292 lines, 196,454 bytes, and 40,876 measured `o200k_base` proxy tokens. All eight bounded-reader pages and assigned ranges were read. Static inspection only; no application execution or tests were run. Runtime transport types describe protocol boundaries; this chunk does not establish behavior of platform-specific transport or storage adapters.

## Capabilities and mechanisms

The review package gathers pending bank transactions, invoice evidence, and filing-draft findings into one typed queue. Transaction severity follows classification state: validation failures are critical, processed but unclassified rows high, untouched rows normal, and final dispositions disappear. A separate confidence filter includes transactions with a non-null confidence strictly below its threshold regardless of classification state; it excludes invoices and draft findings. Invoice triage prioritizes unmatched and overdue invoices as high, with pending and partially-paid invoices normal. Draft review keeps only documents matching the active profile tax ID, checks their stored authority coordinates, deduplicates findings by draft/code/casilla, and emits placeholder rows for unfinished drafts. Approved drafts are recomputed against current inputs so an approval that has aged out can appear as a stale-review item without mutating its stored record. Queue source selection and ordering (`src/cadrumo/application/review/_aggregator.py`), transaction and invoice adapters (`src/cadrumo/application/review/source_adapters.py`), draft ownership and stale-approval review (`src/cadrumo/application/review/source_adapters.py`)

The queue’s filter parser accepts constrained `key=value` clauses and then resolves them into frozen, strict, typed specifications for ledger, invoice, or declaration review. It rejects malformed clauses, unknown or repeated keys, invalid enum values, and ledger period/year mismatches; model validators also check that directly constructed typed fields agree with the original clause set. The operator projection maps public source-kind selectors to internal item kinds, translates catalogue summaries, attaches legal references to filing findings, and orders by descending severity followed by time and identity. Closed Pydantic item and row models make the source-specific fields explicit while keeping source records in the internal item rather than serializing them into the operator row. Filter grammar (`src/cadrumo/application/review/filter.py`), ledger filter consistency (`src/cadrumo/application/review/filter.py`), operator projection and selector resolution (`src/cadrumo/application/review/operator.py`), typed review items (`src/cadrumo/application/review/models.py`)

Two registered review reads expose the queue and exact-item lookup. Requests are credential-free and profile-addressed; the executor requires the request, operation identity, and active bucket to agree, builds source ports for that profile and pinned authority operation, and captures a read-only result. The private and public snapshot models revalidate row scope, filters, uniqueness, ordering, item identity, and terminal receipt identity. Both definitions use journaled read capabilities and registered result projectors; the projector accepts only the exact result type and a successful no-effect receipt. Scope validators and receipt checks (`src/cadrumo/application/review/read_operation.py`), queue executor (`src/cadrumo/application/review/read_operation.py`), registered read definitions and projectors (`src/cadrumo/application/review/read_operation.py`)

The runtime package defines credential-free, discriminated local request and reply contracts for status, profile admission, session management, operations, enrollment, and owner stop control. Profile identifiers, session IDs, worker IDs, boot IDs, and connection IDs are routing coordinates; the contracts explicitly do not treat them as proof or bearer authority. Native peer evidence comes from the transport, deadlines are finite monotonic budgets, and status remains separate from authenticated profile access. The worker protocol enumerates exact lease, submission, operation, projection, observation, and management commands; application authorization is delegated through a held owner guard and returned permits are connection-bound rather than transferable. Runtime request and reply unions (`src/cadrumo/application/runtime/profile_access.py`), native byte channel and peer contract (`src/cadrumo/application/runtime/contracts.py`), worker command surface (`src/cadrumo/application/runtime/profile_worker.py`), worker authorization owner (`src/cadrumo/application/runtime/worker_authorization.py`)

Large requests and responses use finite, digest-pinned chunk protocols. Submission payloads are capped at 16 MiB, split into canonical-base64 chunks no larger than 16 KiB, accepted only at the next exact offset, and decoded as strict UTF-8 only after total length and digest verification; the mutable upload buffer is wiped and closed on success or failure. Result projection pages apply the same byte bounds and canonical document digest, requiring a digest for continuation and refusing a changed document. The contracts bind upload begin/chunk/finish/abort to the original connection and session, while the worker creates an operation only after finish. Submission payload assembly (`src/cadrumo/application/runtime/submission_payload.py`), worker upload commands (`src/cadrumo/application/runtime/profile_worker.py`), projection page validation (`src/cadrumo/application/runtime/projection_pages.py`)

Automation approval custody is split across exact invocation bindings and a bounded session inventory. A session is bound to a worker, boot, profile, connection, human session, operation, enrollment request, and review digest. The inventory caps concurrent approvals at eight, expires them against a monotonic clock, permits only one active phase per entry, retires on failure/disconnect/session revocation, and defers close until a busy phase returns. The publication protocol separately requires the exact approval operation, human START authority, and a matching held COMMIT permit. Approval binding (`src/cadrumo/application/runtime/approval_binding.py`), approval ownership and expiry (`src/cadrumo/application/runtime/approval_sessions.py`), approval phase and publication contracts (`src/cadrumo/application/runtime/worker_enrollment.py`)

Protected enrollment delivery is a volatile broker to one bound native client. It pins the initial profile binding, request, review digest, and offer expiry; validates the persisted candidate’s identity and digest before handing work off; allows a single borrowed command; and requires a typed client acknowledgement or possession response before completion. Candidate material is dropped when borrowing ends, and an ambiguous, timed-out, refused, malformed, or disconnected exchange fences the offer. Owner stop uses a dedicated connection and fresh native-login checks, issues a one-minute preview for the full shared runtime, then consumes it on confirmation while checking boot identity and both wall and monotonic clocks. Enrollment recipient exchange (`src/cadrumo/application/runtime/enrollment_recipient.py`), completion and offer fencing (`src/cadrumo/application/runtime/enrollment_recipient.py`), global stop consent (`src/cadrumo/application/runtime/owner_control.py`)

## Knowledge, security, and implementation assessment

Review knowledge comes from profile-bound transaction and invoice catalogues and encrypted draft-review ports, plus a pinned authority operation used to validate draft coordinates and recompute stale approvals. The reported item contains stable IDs, status, severity, a next command, and legal references for findings. Runtime knowledge is supplied by OS-authenticated peer/login evidence, exact profile worker leases, current access-policy decisions, operation registrations, and protected-client acknowledgements; installation metadata or manager state alone do not confer access. Review source ports and authority checks (`src/cadrumo/application/review/source_adapters.py`), native login witness contract (`src/cadrumo/application/runtime/login.py`), manager-state distinction (`src/cadrumo/application/runtime/management.py`)

Strong safeguards include strict frozen message models, exhaustive request/reply unions, typed allowlisted refusals without peer-controlled diagnostics, finite absolute deadlines, bounded message sizes, request/result correlation, profile and connection scope checks, no-effect receipts for reads, digest integrity for transfers, secret-ready frames, and explicit effect/settlement distinctions. Human approval proof and publication are distinct phases; worker authorization and native owner consent are rechecked rather than inferred from IDs. Runtime shutdown code distinguishes acceptance from drain, containment, and settled work. The host must still settle its native callback owner: isolating a worker does not stop a parent KDF callback thread, as the approval-session ownership documentation itself cautions. Safe refusal and byte-channel boundaries (`src/cadrumo/application/runtime/contracts.py`), deadline bounds (`src/cadrumo/application/runtime/deadline_budget.py`), approval cleanup caveat (`src/cadrumo/application/runtime/approval_sessions.py`), drain result contract (`src/cadrumo/application/runtime/profile_access.py`)

Two review-source details merit cross-layer attention. First, failure to resolve the profile tax ID is logged at debug level and converted to `None`, which makes `drafts_pending` return an empty tuple; if callers do not separately report this condition, a source-access failure can look like “no drafts to review.” Second, invoice classification computes distinctions such as unmatched, overdue, pending, and partially paid, but `_to_invoice_item` discards its `reason`; the generic queue summary therefore does not explain which invoice condition generated the row unless the consumer consults the embedded source through another authorized view. Tax-ID resolution fallback (`src/cadrumo/application/review/source_adapters.py`), invoice classification and item construction (`src/cadrumo/application/review/source_adapters.py`)

This is a contract-and-projection chunk, not the complete runtime deployment. Actual OS peer verification, storage encryption, profile admission wiring, callback containment, and client secure-store behavior live behind other adapters or host implementations and cannot be established from these records alone. No assigned tests were run, so race behavior, framing, and refusal/effect correspondence remain statically assessed.

## Dependencies and follow-up

Trace the review adapters into the profile-scoped encrypted repositories and test that an unavailable profile identity is surfaced distinctly from an empty queue. Follow stale-approval recomputation into `application.filing.draft_review` and its schema, ledger, invoice, and profile ports. For runtime assurance, connect these contracts to the native listener and OS peer verifier, profile worker launcher/containment owner, protected credential client, manager adapters, and submission/projection frontends. Prioritize tests for expired or retired approval phases, enrollment client disconnect during a borrowed command, bad/out-of-order upload chunks and digest mismatch, profile/session scope changes between request and projection, and owner-stop confirmation replay or clock skew.

## Complete assigned-file coverage

All 30 assigned files were read fully across pages 1–8; no portions remain unread.

- review/__init__.py (`src/cadrumo/application/review/__init__.py`)
- review/_aggregator.py (`src/cadrumo/application/review/_aggregator.py`)
- review/enums.py (`src/cadrumo/application/review/enums.py`)
- review/errors.py (`src/cadrumo/application/review/errors.py`)
- review/filter.py (`src/cadrumo/application/review/filter.py`)
- review/models.py (`src/cadrumo/application/review/models.py`)
- review/operator.py (`src/cadrumo/application/review/operator.py`)
- review/read_operation.py (`src/cadrumo/application/review/read_operation.py`)
- review/source_adapters.py (`src/cadrumo/application/review/source_adapters.py`)
- runtime/__init__.py (`src/cadrumo/application/runtime/__init__.py`)
- runtime/access_management.py (`src/cadrumo/application/runtime/access_management.py`)
- runtime/approval_binding.py (`src/cadrumo/application/runtime/approval_binding.py`)
- runtime/approval_sessions.py (`src/cadrumo/application/runtime/approval_sessions.py`)
- runtime/contracts.py (`src/cadrumo/application/runtime/contracts.py`)
- runtime/deadline_budget.py (`src/cadrumo/application/runtime/deadline_budget.py`)
- runtime/enrollment_access.py (`src/cadrumo/application/runtime/enrollment_access.py`)
- runtime/enrollment_recipient.py (`src/cadrumo/application/runtime/enrollment_recipient.py`)
- runtime/installation.py (`src/cadrumo/application/runtime/installation.py`)
- runtime/login.py (`src/cadrumo/application/runtime/login.py`)
- runtime/management.py (`src/cadrumo/application/runtime/management.py`)
- runtime/management_status.py (`src/cadrumo/application/runtime/management_status.py`)
- runtime/operation_access.py (`src/cadrumo/application/runtime/operation_access.py`)
- runtime/owner_control.py (`src/cadrumo/application/runtime/owner_control.py`)
- runtime/profile_access.py (`src/cadrumo/application/runtime/profile_access.py`)
- runtime/profile_worker.py (`src/cadrumo/application/runtime/profile_worker.py`)
- runtime/projection_pages.py (`src/cadrumo/application/runtime/projection_pages.py`)
- runtime/submission_payload.py (`src/cadrumo/application/runtime/submission_payload.py`)
- runtime/transport.py (`src/cadrumo/application/runtime/transport.py`)
- runtime/worker_authorization.py (`src/cadrumo/application/runtime/worker_authorization.py`)
- runtime/worker_enrollment.py (`src/cadrumo/application/runtime/worker_enrollment.py`)
<!-- /preserved:article -->

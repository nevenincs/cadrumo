# Local submission preflight and audit records

[Technical overview](../architecture.md) · [Article index](catalogue.md) · [Snapshot and reading guide](../reading-guide.md)

> This page describes the analyzed source snapshot. Its findings and limitations are not a certification of the current branch.

**Report:** `STAGE-2-150` · **Topic:** [Business and taxpayer domain](../topics/business-and-taxpayer-domain.md)

<!-- preserved:article -->
## Scope

This chunk covers six files (933 lines; 8,163 measured tokens) under `domain/submission`: the package contract, preflight engine and gates, strict records and validators, narrow protocols, and domain exceptions. It contains no transport or persistence adapter implementation. The record module documents how its audit models are persisted by a separate encrypted adapter, while the engine accepts that adapter through a protocol.

## Product capabilities

`Preflight` evaluates whether a draft is eligible to proceed through a local submission workflow. Its four ordered gates require an approved draft, no error-severity findings, an open filing window unless the caller explicitly skips that check, and a configured/available authentication provider unless skipped. It receives `today` and both skip decisions explicitly, so date-sensitive behavior is deterministic within this boundary. Failures raise a typed `SubmissionPreflightError`, with localized-message keys and bounded context describing the failed condition (gate order and checks (`src/cadrumo/domain/submission/preflight.py`); engine contract (`src/cadrumo/domain/submission/engine.py`)).

The record layer models historical or imported submission evidence, rather than authorizing a new filing. `ModeloPresentado` captures the canonical Modelo and filing period, taxpayer identity, aggregate status, optional justificante CSV/PDF, timestamps, and a non-empty ordered tuple of attempts. Each attempt has a digest-shaped coordinate, UTC timestamps, status, optional error detail, and optional browser trace path (record fields (`src/cadrumo/domain/submission/models.py`); aggregate record (`src/cadrumo/domain/submission/models.py`)). These records let other flows preserve a local audit history for past filings even though live AEAT submission is described as forbidden. The protocol surface allows an application to inject a secure repository without coupling the domain to its adapter (repository port (`src/cadrumo/domain/submission/protocols.py`)).

## Mechanism and encoded knowledge

The preflight implementation fails closed on the first unmet gate. It normalizes a status enum or string through a shared enum helper before comparing with `APROBADO`; it reads each finding’s required typed severity directly, so malformed or renamed finding data is not silently omitted. The deadline port receives the draft’s Modelo and Period plus the supplied reference date. The auth probe’s typed provider description must be both configured and available; only expected domain errors from describing the provider are translated into a preflight refusal. Logs record gate outcomes without including the draft’s casilla values or taxpayer identifier.

Skipping deadline and auth checks is part of the public API, not an implicit behavior. Package documentation says workflow callers use both skips for local verification and local mark-as-filed operations, because they do not touch AEAT; callers doing a live AEAT operation should leave them enabled. The domain itself cannot prove that the caller selected the right purpose: a caller can pass the skip flags for any purpose. The authorization decision therefore depends on application-level workflow policy and the separate core live-write access gate, not on `SubmissionEngine` alone.

The strict, frozen Pydantic models enforce several useful audit invariants. Identifiers have constrained lowercase hexadecimal forms; Modelo strings are resolved through the canonical enum instead of accepting any length-valid code. UTC-aware timestamps and nonnegative attempt chronology are checked. An accepted aggregate filing requires CSV, PDF path, and acknowledgement time; acknowledgement cannot predate the first submission. Each attempt ID must bind to its parent submission and one-based tuple position. Attempt starts must be ordered, `submitted_at` must equal the first attempt’s start, and the aggregate status must be compatible with the last attempt. The compatibility table allows an earlier presentation to later receive acceptance or rejection, while a failed terminal attempt cannot support those positive outcomes (cross-field validators (`src/cadrumo/domain/submission/models.py`), attempt/status coherence (`src/cadrumo/domain/submission/models.py`)).

## Security and quality assessment

The design is intentionally read-only around AEAT. A local audit record can store a filesystem path to a justificante or Playwright trace, but this chunk does not open, validate, redact, or control those referenced files. The initializer says the concrete repository stores audit records as encrypted data; that protection must be verified in the adapter and filesystem policy. Error messages can retain free-form `error_message` text, so upstream import/storage boundaries should avoid placing credentials or unnecessary personal data there. The engine logs draft identifiers and filing coordinates at debug level; logging configuration and retention are outside this chunk.

There is a concrete interface/documentation gap: `SubmissionEngine` is described as reading historical `ModeloPresentado` records, and it accepts and stores a `SubmissionRepositoryProtocol`, but its only public operation in this chunk is `preflight`; the repository is never used. The protocol declares `load`, iteration, and ID listing, yet no corresponding engine methods exist (engine methods (`src/cadrumo/domain/submission/engine.py`), repository methods (`src/cadrumo/domain/submission/protocols.py`)). This is either stale package/API documentation or an incomplete read facade. The actual read route may be elsewhere, so callers and adapters should be traced before treating historical records as inaccessible.

The model describes an attempt’s status as terminal and requires `ended_at`, but the enum also permits `EN_TRAMITACION` and `PENDIENTE_DE_PRESENTAR`; the validator checks timestamp order, not whether the status is compatible with a completed interval. This means an “in progress” attempt can be serialized with an end timestamp and an aggregate record can accept it when it is the last attempt (status enum and attempt model (`src/cadrumo/domain/submission/models.py`), attempt timestamp validator (`src/cadrumo/domain/submission/models.py`), aggregate compatibility validator (`src/cadrumo/domain/submission/models.py`)). Imported-record compatibility might require these states, but the current type does not distinguish an open attempt from a completed one. Separately, the chronology validator orders attempt start times but does not require each prior attempt to end before the next starts. If the history contract assumes sequential attempts, overlapping intervals remain representable.

## Dependencies and follow-up

The submission domain depends on core Modelo/Period identity, UTC and validation boundaries, severity and auth-provider contracts, plus injected deadline/auth/repository ports. Application workflow code decides when gate skips are legitimate; a separate access gate is documented as the authority for refusing live writes. Persistence encryption and referenced-file protections belong to adapters.

Trace the engine’s intended history-read API and reconcile it with the package documentation and repository port. Confirm application callers bind skip flags to local-only purposes and cannot bypass the live-write gate. Decide whether imported in-progress attempts are valid records; if so, model an explicit open/terminal distinction, and otherwise reject status/end-time combinations that contradict the lifecycle. Confirm whether sequential attempts require non-overlapping intervals. No tests are included in this chunk, so this review does not validate those caller or adapter invariants at runtime.

## Complete assigned-file coverage

- `src/cadrumo/domain/submission/__init__.py`
- `src/cadrumo/domain/submission/engine.py`
- `src/cadrumo/domain/submission/errors.py`
- `src/cadrumo/domain/submission/models.py`
- `src/cadrumo/domain/submission/preflight.py`
- `src/cadrumo/domain/submission/protocols.py`
<!-- /preserved:article -->

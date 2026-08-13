---
tags:
  - '#audit'
  - '#aeat-liabilities-sanciones'
date: '2026-08-13'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:0f919ffdca4d6b7d1e45ebe09d909e0690822b8d2e28459b33b666e5d5c97583'
related:
  - "[[2026-08-07-aeat-liabilities-sanciones-plan]]"
  - "[[2026-08-13-aeat-liabilities-sanciones-notification-documents-adr]]"
---



# `aeat-liabilities-sanciones` audit: `notification documents implementation close review`

## Scope

Reviewed the combined P10 through P12 implementation against the accepted
notification-documents decision and the plan's CLI, notice, no-total,
comparecencia, test, locale, harness and user-documentation requirements. The
review covered the complete current feature diff while preserving unrelated
shared-worktree changes. It also re-read the legally binding
`assert_notification_content_readable` path and confirmed that the predicate
still admits exactly `leida is True` before any request crosses the wire.

## Findings


### history-envelope-roundtrip | high | The history schema rejects its own JSON representation

`NotificationDocumentHistoryResult.documents` is declared as a strict tuple,
despite `_app_live_payloads` explicitly requiring list-typed sequence fields
because `model_dump(mode="json")` serialises tuples as JSON arrays. A direct
round trip of the new result produces `documents: []` and
`NotificationDocumentHistoryResult.model_validate(...)` refuses it with a
`tuple_type` validation error. This violates the shared envelope contract and
means the P10/P11 JSON-schema gate cannot establish that the new history leaf
emits a payload its registered schema accepts.

### history-text-underreport | high | Default text history omits most reported figures

`notifications_document_history` places the full `SancionReadingPayload` in
JSON but renders only `importe_a_ingresar` in the default text route. The base,
minimum percentage, resulting sanction, both reductions, difference,
liquidation key, reference and tax concept are omitted, and consecutive
documents have no row boundary beyond repeated labels. The plan promises each
document's own reported figures, while manual CLI use is the primary operator
surface; the current text route therefore under-delivers the feature and can
hide the figures an operator needs to reconcile. The integration test asserts
only JSON fields and does not exercise the default text output, so it cannot
detect this regression.

### unparsed-recovery-dead-end | medium | The notice tells operators to perform an unavailable read

The unparsed-document notice instructs the operator to "read the stored
document itself", but the new `document view` command returns only metadata,
the parse refusal and an attachment digest. No notification-document command
opens, renders or exports the encrypted bytes, and the service deliberately
returns no path. For exactly the documents whose deterministic parser refuses,
the prescribed safety recovery is therefore unavailable from the documented
surface. This makes the diagnostic actionable in wording only and leaves the
operator unable to inspect the authoritative artefact through this feature.

### close-verification-incomplete | medium | Required close gates have no completed evidence

The combined focused run for the CLI integration, schema, no-total,
write-guard, rule-surface and documented-command gates did not complete within
two minutes and produced no test result. The direct schema probe already found
a concrete failure, so P10 through P12 cannot be closed from the current tree.
The plan rows also remain unchecked and the feature has no matching P10-P12
execution records at review time; implementation presence is not completion
evidence.

## Recommendations


- For `history-envelope-roundtrip`, use the payload module's canonical
  list-typed sequence shape and prove the registered schema accepts the exact
  `model_dump(mode="json")` representation emitted by the command.
- For `history-text-underreport`, render every per-document reported field from
  the same typed history entries used by JSON, add an unambiguous document row
  boundary, and add a real CLI test over the default text route.
- For `unparsed-recovery-dead-end`, provide a secure, explicitly designed way
  to inspect bytes already in encrypted custody or change the notice and user
  documentation to name a recovery action that actually exists. Do not expose
  a cleartext path or weaken the custody decision.
- For `close-verification-incomplete`, rerun every P10-P12 named gate after the
  findings are resolved, exercise the real text and JSON CLI commands, and
  create the required execution records before changing plan closure state.

## Resolution

- `history-envelope-roundtrip` resolved: the history sequence now uses the
  canonical list shape accepted after JSON serialization.
- `history-text-underreport` resolved: default text renders every field in the
  typed per-document reading, and the live CLI integration asserts each field.
- `unparsed-recovery-dead-end` resolved without weakening custody: the notice
  now directs the operator to the original already-opened notification in the
  AEAT sede and states that this command does not render or export PDF bytes.
- `close-verification-incomplete` resolved for the feature surface: focused
  integration tests pass, the docs build passes, live help exposes all three
  verbs, execution records exist, and the remaining global failures are
  recorded as unrelated shared-worktree drift rather than hidden.

## Fresh-context close review resolution

The inherited review confirmed every P10-P12 row has a matching execution
record, the three live CLI names exist, the comparecencia guard remains exact,
and history declares no aggregate. Its one medium finding was the global
documented-command conformance failure in the quickstart. That command now
renders through the existing executable quickstart sequence, so the exact S51
gate can pass without an exception or baseline change.

## Manual operator verification outside the test framework

The completed implementation was exercised through a disposable encrypted-file
profile using separate live `aeat` processes and production application/storage
services. No pytest fixture, monkeypatch, fake, stub or test runner participated.

- Created and selected a synthetic natural-person profile through
  `aeat config profile create` under an isolated storage root.
- Built two real PDF byte streams with extractable text layers, parsed them
  through `NotificationDocumentReader`, and stored them through the production
  `NotificationDocumentService` and encrypted `AttachmentStore`.
- Ran `document view` and `document history` as separate CLI processes in text
  and JSON modes. Both records round-tripped with exact decimal values; text
  included every per-document field and JSON exposed no aggregate-shaped field.
- Re-persisted identical bytes through the production service. The operation
  reported `already_in_custody=true`, kept the original record and timestamp,
  and left the document count at two.
- Scanned every file below the isolated storage root byte-for-byte. None
  contained PDF magic, the synthetic NIF, or the sanction label plaintext.
- Confirmed an unknown certificado refuses with
  `REFUSED_LIVE_NOTIFICATION_DOCUMENT_NOT_FOUND` and exit code 2.
- Drove `assert_notification_content_readable` directly with `True`, `False`
  and `None`: only `True` was admitted. Source-order inspection confirmed the
  guard executes before browser construction and the fetch signature exposes
  no force or override parameter.
- Seeded a real `DeudasService` snapshot, then ran `deudas list`, `latest` and
  `view` through separate CLI processes. Two directionally distinct rows
  returned exact magnitudes, periods, situations and `mode=read`.
- Confirmed the deudas landing guard admits the consulta endpoint and refuses
  payment, aplazamiento and off-domain landings.
- Confirmed no deuda or notification-document persistence type is imported by
  calculation or modelo consumers.
- Ran the feature page's CLI-sequence checker and inspected the generated HTML.
  This exposed and then closed a missing `credential-store` reason on the two
  local static frames; the rendered page now carries pull, view and history.

The broader strict single-page Sphinx command still reports concurrent golden
drift on unrelated filing-spine, Modelo 303, troubleshooting and verification
pages plus the user-scope API toctree warning. The notification page's own
sequence check is clean and its generated HTML was inspected directly.

## Fresh-context close review

### Verdict

The notification-document implementation is structurally complete against
P10 through P12, but the campaign is **not eligible for an unqualified green
completion claim from the current shared tree**. The three operator routes are
present in live help; focused real-storage behaviour, the comparecencia guard,
schema registration, write classification and no-total invariant pass; the
guide cites the exact routes and states the already-read and no-balance
boundaries; and all sixteen checked P10-P12 rows have one matching execution
record plus their phase summaries. The remaining closure exception is the
plan's explicitly named documented-command conformance gate, which is still
red in the current tree.

### fresh-context-command-conformance | medium | A checked required gate is still globally red

The exact integration command named by P12.S51 completed with 352 passing
cases and one failure. The failure is outside this feature, in the quickstart
page's newly introduced inline `aeat app modelo work status` invocation, while
the notification-document sequence itself resolves successfully. That
separation makes the feature implementation usable; it does not make the plan's
statement that the required gate passes true. P12.S51's execution record is
internally candid in its description but still says "Delivered and verified"
in its outcome, and the checked row therefore overstates current repository
readiness. Resolve the quickstart violation and rerun the exact gate before
claiming a globally green campaign close, or explicitly qualify closeout as
feature-surface complete with a repository-level blocker.

### Fresh-context evidence

- Live `document --help` exposed exactly `pull`, `view` and `history` and no
  superseded verb names.
- The focused notification adapter, CLI and no-total suites passed 50 tests.
- Focused schema, profile-write classification and sequence-contract checks
  passed 9 tests.
- Direct source inspection confirmed
  `assert_notification_content_readable` returns only when `leida is True` and
  refuses `False` and `None` before document retrieval.
- History carries a list of per-document readings, renders every reported
  field in text, declares no aggregate amount field and always emits the
  standing not-a-balance notice.
- Plan-to-record comparison found sixteen checked P10-P12 rows and sixteen
  uniquely matching execution records. The P10, P11 and P12 summaries are also
  present.
- The notification-document sequence marks only `pull` as authenticated live
  AEAT; `view` and `history` are documented and implemented as local encrypted
  custody reads.
- The documentation build has a recorded successful 17-test run in P12.S51.
  A fresh rerun was started during this review but was stopped without a result
  when the close verdict was requested; this review does not substitute that
  interrupted run for the recorded evidence.

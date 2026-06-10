---
tags:
  - '#adr'
  - '#ledger-evidence-enforcement'
date: '2026-06-10'
related:
  - "[[2026-06-10-ledger-evidence-enforcement-research]]"
---



# `ledger-evidence-enforcement` adr: `Require encrypted evidence bytes; advisory evidence gate` | (**status:** `accepted`)

## Problem Statement

Manual-ledger evidence attachment is the C2 cluster of the ledger-evidence
campaign. Two structural problems remain after the campaign's discovery pass
(recorded in the sibling research):

1. **A byte-custody leak.** `add_link_attachment`
   (`src/aeat/domain/attachments/_service.py`), reachable through
   `aeat app ledger doclink`, records a Gmail/Drive/URL *reference* as the
   stored payload (`mime_type = "text/uri-list"`) and never fetches the remote
   document. The resulting attachment manifest looks like evidence — it carries
   an id, links to the transaction, emits audit events — but the actual invoice
   or receipt never enters secure storage. If the linked message or file is
   later deleted or access revoked, the "evidence" is an unresolvable pointer.
   This violates the campaign's binding invariant: every evidence record must
   carry encrypted document bytes in the per-profile bucket-scoped
   secure-object store.

2. **No evidence-presence advisory.** Nothing ties a transaction's evidence
   presence to its economic role. A positive-amount business expense with no
   purchase invoice, or a cuota-bearing income with no issued invoice, files
   silently with no operator alert — exactly the silent-under-declaration shape
   the project disciplines forbid.

This ADR settles both, plus the secure-storage assertion, the documentation
re-framing, and the test obligations.

## Considerations

- The binding invariant (encrypted bytes in the bucket, link-only forbidden) is
  a **locked campaign decision**; this ADR does not relitigate it, it specifies
  how to satisfy it for the doclink path.
- The fetch-and-refuse machinery already exists. `resolve_document_link`
  (`src/aeat/adapters/outbound/google/_document_link_resolver.py`) fetches Drive
  bytes within the granted `drive.file` scope and raises a typed, scope-named
  `OutboundStoragePermissionError` for Gmail links, out-of-scope Drive files,
  and arbitrary URLs. The byte-bearing `add_attachment` path already
  fetches/stores and writes a manifest with the real `sha256`/`mime_type`. The
  fix is mostly wiring, not new machinery.
- `no-legacy-compatibility` applies. This is an unreleased pre-beta project;
  there are no stored link-only attachments whose data must survive. The
  link-only path is deleted, not bridged.
- `no-silent-under-declaration` mandates an **advisory, not a hard block**, for
  the evidence-presence gate while legitimately evidence-free transactions
  exist (cash purchases with a paper receipt the operator has not scanned,
  exempt rows, intra-group flows). The calculate-path
  `CalculationSourceDiagnostic` / `source_advisories` surface is the established
  precedent.
- C4 keeps `invoice` and `purchase_invoice_evidence` as distinct source kinds.
  C7 requires evidence linkage to stay audit-cross-referenced.

## Constraints

- **Google credentials and scope.** The fetch path depends on the operator
  having connected Google with the `drive.file` scope. A Drive link to a file
  the app did not create / the operator did not pick is unreachable under that
  scope by design, and Gmail/URL links are unreachable entirely. Under the
  decision below these become **refusals**, so the doclink verb's success
  surface narrows to "Drive files reachable under `drive.file`". This is an
  accepted, deliberate consequence — a scope upgrade to `drive.readonly` /
  `gmail.readonly` is a separate Google-app-verification security decision and
  is out of scope here.
- **Parent feature stability.** `resolve_document_link` and the `AttachmentStore`
  secure substrate are landed and stable. The verify-path advisory builds on the
  landed `verify_modelo_revision` findings aggregation and the landed
  `CalculationSourceDiagnostic` advisory pattern. No frontier dependency.
- The advisory must read the transaction's `direction`, `business_classification`
  and IVA/category fields to decide whether evidence is *expected*; it must not
  fire on rows that legitimately bear no cuota and no deductible base.

## Implementation

### Decision 1 — Replace link-only recording with fetch-and-encrypt-or-refuse

`add_link_attachment` is **removed**. The `aeat app ledger doclink` verb is
repurposed: when given a Gmail/Drive/URL reference it calls
`resolve_document_link(source, reference, credentials)` to obtain the document
bytes, then stores those bytes through the existing byte-bearing path
(`add_attachment` over `AttachmentStore.put_bytes`/`write_manifest`), recording
the original link reference as manifest metadata (`source`, `source_reference`)
and the *real* `sha256` and fetched `mime_type`. The linked attachment id is then
bound to the transaction through `attach_manual_transaction_evidence` exactly as
today, so audit cross-referencing (C7) is preserved.

When `resolve_document_link` raises — a Gmail link, an out-of-scope or
unparseable Drive reference, or a URL — the verb **refuses** with the typed,
scope-named error surfaced as an actionable CLI message. It does **not** fall
back to storing a link. A record that cannot obtain bytes is rejected. The
`text/uri-list` mime path and the link-only manifest shape are deleted outright
(`no-legacy-compatibility`). The narrowed `doclink` surface is documented:
today it succeeds only for Drive files reachable under `drive.file`.

Affected symbols: delete `add_link_attachment`
(`src/aeat/domain/attachments/_service.py`); rewire `ledger_doclink`
(`src/aeat/entrypoints/cli/_ledger_lifecycle_cli.py`) to the resolve →
`add_attachment` → `attach_manual_transaction_evidence` sequence. Namespaces are
unchanged: bytes ride `ATTACHMENT_BLOB_NAMESPACE`, manifests ride
`ATTACHMENT_MANIFEST_NAMESPACE`.

### Decision 2 — Advisory evidence-presence gate by economic role

Introduce a non-blocking advisory on the verify path: a positive-economic-input
transaction with no linked evidence (neither `purchase_invoice_evidence_id` nor
any `attachment_ids`) raises an ADVISORY finding rather than a hard block. The
triggering set is defined narrowly:

- **OUTGOING business/mixed expense** with a positive amount and a deductible
  base (a category that routes a deductible cuota or an IRPF-deductible expense):
  expects a *purchase invoice*.
- **INCOMING cuota-bearing income** with a positive amount whose IVA category is
  legally expected to bear a cuota (excluding the cuota-less categories already
  enumerated for the IVA advisory): expects the *issued invoice*.

Rows that legitimately bear no evidence requirement — non-business/personal,
exempt / zero-rated / not-subject IVA categories, zero-amount, and lifecycle
states other than ACTIVE — are excluded and never fire. The advisory is
surfaced through the same operator-facing channel as the existing
calculate-path advisories (a finding with ADVISORY severity carrying
`legal_refs` where applicable), so it is visible but non-blocking. It stays
advisory while legitimately evidence-free cases exist; the section explicitly
leaves room to upgrade individual category rules to BLOCKING once the
evidence-free escape hatch for that category is closed.

### Decision 3 — Add-time attachment as the documented primary path

The add-time flow (`aeat app ledger add --purchase-invoice-evidence-id ...
--attachment-id ...`) becomes the **primary documented** way to attach evidence;
the post-hoc `aeat app ledger attach` verb stays as the secondary flow. The
docs rewrite (`docs/how-to/ledger-evidence.md`,
`docs/how-to/import-bank-statements.md`) is **user-facing** and therefore rides
the `vaultspec-documentation` workflow, *not* this ADR. This ADR only records
the intent and the target documents.

### Decision 4 — Secure-storage gate (assertion)

After Decision 1 lands, every evidence byte object and manifest rides an
encrypted bucket-scoped secure-object namespace: attachment blobs
(`ATTACHMENT_BLOB_NAMESPACE`), attachment manifests
(`ATTACHMENT_MANIFEST_NAMESPACE`), and purchase-invoice evidence
(`LEDGER_PURCHASE_INVOICE_EVIDENCE_NAMESPACE`). The link-only removal closes the
sole leak, so no plaintext financial document remains on disk outside these
namespaces. A regression test asserts that the doclink path can produce only
byte-bearing manifests (no `text/uri-list` manifest can be written).

### Decision 5 — Roundtrip and anti-tautology tests

Two real-behavior test obligations, no mocks:

- **Fetch-and-encrypt roundtrip.** Using a real `AttachmentStore` over a real
  SQLite-backed `SecureObjectRepository` and a fake Drive *transport* (the
  `service.files().get_media` seam only — the storage and manifest path are
  real), drive `resolve_document_link` → `add_attachment` end to end, then load
  the manifest back and assert the stored bytes equal the fetched bytes and the
  manifest's `sha256`/`mime_type` match. The anti-tautology counterpart mutates
  the on-disk blob and asserts the re-hash verification raises. A Gmail/URL
  reference must raise the refusal error and write **nothing**.
- **Advisory gate.** Build a positive OUTGOING business expense transaction with
  no evidence, run the verify path, and assert exactly one ADVISORY
  evidence-presence finding; build the same transaction *with* a linked
  attachment and assert no such finding; build an exempt / non-business row with
  no evidence and assert no finding (the false-positive guard). The expected
  trigger set is derived from the transaction's economic role, not from the
  formula under test.

## Rationale

The byte-custody leak is the only place the campaign invariant is broken, and
the fix reuses landed machinery (`resolve_document_link`, `add_attachment`,
`AttachmentStore`), so the decision is low-risk wiring plus a deletion rather
than new infrastructure (research findings "single byte-custody leak" and
"a scope-aware fetch adapter already exists"). Refusing rather than degrading to
a link is mandated by `aeat-safety-legal-gates` (no silently under-evidenced
filing) and `no-legacy-compatibility` (delete, do not bridge). The advisory
shape — not a hard block — follows the worked `no-silent-under-declaration`
precedent and the existing `CalculationSourceDiagnostic` surface, keeping
legitimately evidence-free filings permissible while making missing evidence
non-silent.

## Consequences

- **Gain:** the entire ledger evidence surface satisfies the encrypted-bytes
  invariant; "why is this casilla this value" is answerable from secured bytes,
  not a dead pointer.
- **Gain:** operators get a visible, non-blocking nudge to attach evidence on
  the economically significant rows.
- **Cost / honest narrowing:** the `doclink` verb's success surface shrinks to
  Drive files reachable under `drive.file`. Gmail links, arbitrary URLs, and
  out-of-scope Drive files that *used* to "work" (by storing a useless pointer)
  now refuse. This is correct — they never carried evidence — but it is a
  visible behaviour change operators will notice, so the refusal message must
  name the scope-upgrade / manual-download path.
- **Pitfall to avoid:** the advisory must not fire on cuota-less or
  non-business rows; a noisy advisory trains operators to ignore it (the same
  failure mode the IVA advisory refinement fixed). The false-positive guard test
  is load-bearing.
- **Opens:** a future scope-upgrade ADR (`drive.readonly` / `gmail.readonly`)
  could widen the fetchable set; a future decision could upgrade specific
  advisory category rules to BLOCKING once their evidence-free escape hatch is
  closed.

## Codification candidates

- **Rule slug:** `ledger-evidence-bytes-not-links`.
  **Rule:** Every ledger evidence record must carry the document's encrypted
  bytes in a bucket-scoped secure-object namespace; a Gmail/Drive/URL reference
  must be fetched-and-encrypted or the attachment refused — never stored as a
  `text/uri-list` link-only manifest.




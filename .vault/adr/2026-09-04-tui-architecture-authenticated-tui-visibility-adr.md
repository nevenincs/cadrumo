---
tags:
  - '#adr'
  - '#tui-architecture'
date: '2026-09-04'
modified: '2026-09-04'
body_schema: 'body-v2'
body_hash: 'sha256:169fcfeb851dc1aa7ee6f29f34df27b341b3fefade9492d4f893445c0876e548'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
  - '[[2026-08-11-tui-architecture-research]]'
---
# `tui-architecture` adr: `the authenticated TUI shows the operator their own data` | (**status:** `accepted`)

## Problem Statement

The workbench projections were built as though the TUI were an untrusted remote consumer of the application layer. The Ledger entry projection carries a transaction id and a review status and nothing else; the entries screen renders a twelve-character hash beside a status word and prints a standing notice that financial details remain protected. The AEAT Sync census row is documented as a row "without values". Both surfaces exist to let an operator review and correct their own records, and neither can show the records.

The same session contradicts itself. The Profile manager, mounted in the same process behind the same login, renders real field values and edits them, masking only the fields explicitly marked as credential-shaped. Two surfaces reading one decrypted profile take opposite positions on the operator's own data.

The decision this record settles is what the authenticated TUI may display.

## Considerations

- The TUI is the product's editing surface. Modelo inputs, profile facts, ledger classification and evidence review are all performed there.
- It runs in-process in the authenticated session, against a bucket whose data-encryption key the same process already derived. The plaintext is in memory before any screen renders.
- Authentication is the control. Reaching a workbench screen at all requires the credential that unwraps the capsule.
- The secure-storage rule these projections cite protects payloads at rest and in transit -- logs, exceptions, caches, temporary files, transcripts, and off-host transfer. A rendered terminal cell is none of those.
- Withholding a value from the screen protects nothing when the process holding the screen already holds the value.
- An operator cannot review an entry from a truncated hash, and cannot correct a census field whose value is hidden. A surface that refuses to show its subject does not merely inconvenience the operator; it fails at the task it exists for.

## Considered options

- **Keep the projections redacted and add a separate reveal path.** Rejected: it doubles every projection, and the reveal would be granted on the same authentication that already admitted the screen.
- **Redact by field sensitivity class.** Rejected for operator-owned financial data: every ledger amount and counterparty is sensitive in the storage sense and none of it is secret from its owner. The class that survives is credentials, not finances.
- **Show the operator their own data.** Chosen.

## Constraints

- The authenticated TUI displays the operator's own data in full. No workbench projection withholds a value from the screen on the grounds that the value is sensitive.
- Credential and recovery material remain masked in entry fields, because those protect against shoulder-surfing and re-display of a secret the operator is supplying, not against the operator reading their own records.
- The storage and transport rules are untouched and still bind. Nothing here permits a payload to reach a log, an exception message, a cache, a temporary file, an agent transcript, a generated reference, or any off-host service. The decision governs what is PAINTED, not what is persisted or sent.
- Availability states remain distinct. Showing a value never collapses missing, never-captured, unsupported and a proven zero into one another; this record widens what a row may carry and changes nothing about `no-silent-under-declaration`.
- A projection that carries operator data still crosses no boundary it should not: it is built inside the authenticated session and consumed by the screen in the same process.

## Implementation

Ledger entry references carry the transaction facts a reviewer needs -- date, amount and currency, direction, counterparty, description, classification and review status -- and the entries screen renders them. The standing "financial details remain protected" notice is removed rather than reworded, because it describes a policy that no longer exists.

AEAT Sync census rows carry their local and observed values beside the path and status, so a census comparison shows what actually differs. The evidence-comparison and reconciliation rows likewise carry the values being compared.

The workbench search snapshot indexes and displays real labels and values, so a palette result is identifiable without opening the destination.

Surfaces whose projections were shaped by the retired assumption are re-derived from it rather than patched: any model documented as "safe ... without values" is revisited.

## Rationale

Authentication is the boundary that decides who may see the data, and the operator passed it. After that point a redacted screen protects nobody: the process rendering it already holds the plaintext, and the person reading it owns the records. The rule the projections invoked is a storage and transport rule, and applying it to a terminal cell mistook the medium for the channel.

The Profile manager was already right. This record makes the rest of the workbench agree with it.

## Consequences

Ledger, AEAT Sync and search projections widen to carry operator data, and their screens become usable for the review and correction they were built for. Tables gain real columns, which interacts with the open table-width work: several currently paint far short of the viewport partly because they have almost nothing to paint.

Gates that assert an absence of operator data in a rendered surface are asserting the retired policy and are rewritten or removed. Gates that assert an absence of operator data in a log, an exception, a cache or an off-host payload are unaffected and remain required.

The reviewer's earlier verdict that redaction was sound is superseded: it confirmed that nothing protected escaped, which was true and did not establish that the surfaces could do their job.

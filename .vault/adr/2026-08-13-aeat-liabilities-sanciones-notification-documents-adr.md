---
tags:
  - '#adr'
  - '#aeat-liabilities-sanciones'
date: '2026-08-13'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:95a4a15beba0ce1753e8078bfbf57bb6412d7298fd7b3376ab06c41359e18a9e'
related:
  - "[[2026-08-07-aeat-liabilities-sanciones-adr]]"
  - "[[2026-08-12-aeat-liabilities-sanciones-p05-p06-closeout-honesty-audit]]"
  - "[[2026-08-07-dehu-notification-legal-effect-adr]]"
  - "[[2026-08-07-aeat-liabilities-sanciones-research]]"
---

# `aeat-liabilities-sanciones` adr: `Notification documents: fetch, encrypt, parse deterministically` | (**status:** `accepted`)

## Problem Statement

The governing record for this feature decided a read-and-display liability
register over AEAT's *Consultar deudas* recaudación surface. That register is
built, guarded and empty: the closeout honesty review established, with a
same-session positive control, that this taxpayer's liabilities are not in the
recaudación register at all. They sit one stage earlier, as served
notifications — liquidaciones, sanciones and providencias whose amounts,
reduction percentages and appeal windows are printed in the notification's own
PDF and nowhere else the application can reach.

So the standing goal — an operator can see, inside the application, what AEAT
reports as owed — is not blocked on the surface the governing record chose. It
is reachable through a different surface that record never considered, on
different transport, under a legal constraint that record never had to face.

This decision rules on that second surface: whether the application may fetch a
notification's document at all and under what predicate; where the fetched bytes
live; how the figures are extracted from them; and what the application may and
may not assert once it holds them. It does not revisit the deudas register,
which remains correct for the recaudación stage and remains empty until a deuda
arises.

## Considerations

- **The fetch control and the comparecencia control are the same control.**
  AEAT serves a notification's PDF from the detail endpoint under
  `accion=vernotif`. On an already-read notification that redisplays a
  document. On an unread one it is the act by which the notification becomes
  legally served: it starts the appeal and payment periods and AEAT requires
  the taxpayer's own signature. This is not a transport detail with a legal
  footnote; the legal effect *is* what the control does.
- **Service and reading are different events, and only the second licenses a
  fetch.** A notification can be already served — an edictal service whose
  deadlines are running — and still unread. Fetching such a row arguably
  starts no new clock, and that argument is refused anyway: reading someone's
  unread mail is their act, not the application's. The operator ruled
  explicitly that only the user reads genuinely unread messages.
- **The window arithmetic this fetch sits beside is already decided
  elsewhere.** `2026-08-07-dehu-notification-legal-effect-adr` owns the
  rechazo-tácito computation and the `leida` axis it reads. This record
  consumes that axis as the fetch predicate and adds no second interpretation
  of it; the two records must not grow parallel notions of "served".
- **The figures being extracted are filed against.** A sanción's base,
  minimum percentage, resultante and the arts. 188 reductions are the numbers
  an operator reconciles a payment against and, if they contest it, appeals
  on. A probabilistic extractor that is usually right produces a plausible
  wrong number with no signal, which is the silent-wrong-value failure class
  `no-silent-under-declaration` exists to prevent, pointed at the operator's
  own liability rather than at a casilla.
- **The extraction primitives already exist and have a canonical home.**
  `adapters/inbound/pdf/_label_regex.py` owns the label-anchored regex
  primitive, the canonical Spanish printed-amount capture group and the
  Spanish decimal parser; `adapters/inbound/pdf/_pdfplumber.py` owns
  byte-level page-text extraction. The amount group already tolerates the
  NBSP and narrow-NBSP thousands separators AEAT prints, a defect a
  hand-rolled second copy previously shipped as a 1000x underreport. A second
  amount regex or a second text extractor in this feature would be exactly
  the duplicate-authority the discovery mandate exists to prevent.
- **`apply_label_regex` is keyed by `CasillaId` and a sanción PDF has no
  casillas**, so the dispatch loop is not directly reusable while its
  primitives are. That is a real seam, and the honest resolution is to reuse
  the primitives and write a small sanción-specific dispatch — not to widen
  the casilla-keyed contract to carry a non-casilla concept.
- **The bytes are sensitive financial data.** A notification PDF stating a
  taxpayer's sanción is squarely within
  `sensitive-financial-data-secure-storage-only`: no temp file, no scratch
  directory, no plaintext cache, no log line, no path pointer standing in for
  the bytes. The ledger package's `AttachmentStore` resolution in
  `application/ledger/_actions_common.py` is the precedent for reaching the
  encrypted content-addressed store from an application service.
- **A scoped read-POST allowance already exists on this codebase and is a
  transport fact.** The deudas consulta needed one because its listing lives
  behind a form submission, and the IVA wallet reader established the
  mechanism. A POST that retrieves and mutates nothing is a read; what makes
  this particular POST dangerous is not its verb but what AEAT does on
  receiving it for an unread row. The allowance and the legal gate are
  therefore separate controls with separate justifications, and neither
  substitutes for the other.
- **The fetch verb persists to bucket storage**, so its CLI leaf must be
  enrolled in `PROFILE_BOUND_WRITE_VERB_PATHS`
  (`application/storage_write_policy.py`) beside the existing
  `"app live notifications pull"` entry, or the profile-bound write guard
  fails open for it (`aeat-cli-contract`).
- **This notifications reader has failed silently twice.** The closeout audit
  records it returning zero rows against a populated inbox, then a tenth of
  them, both times because the surface answered a narrower question than was
  intended and nothing raised. A new consumer of that reader inherits the
  disposition, not just the data.
- **Summing AEAT's reported figures is an assertion, not a display.** A
  per-document reported amount is AEAT's own figure repeated back. A total
  across documents is a claim by the application that this is what the
  taxpayer owes — false the moment one sanción is paid, appealed, reduced or
  superseded, none of which the notification PDF reports.

## Considered options

1. **Fetch only already-read notifications, store the bytes encrypted, parse
   them with a deterministic label-anchored regex composed on the existing PDF
   primitives, and display per-document figures as reported (chosen).** Smallest
   surface that moves the standing goal; every element has an existing
   precedent in the tree; the legal risk is bounded by a predicate that refuses
   by construction.
2. **Fetch on demand for any notification, warning the operator first.**
   Rejected outright. The warning is displayed to an agent, not to the
   taxpayer, and the act it precedes is irreversible and legally consequential.
   A confirmation prompt cannot supply the taxpayer's signature, and an agent
   that can be talked into the fetch is a worse guarantee than a predicate that
   cannot represent it.
3. **Extract the fields with a vision or language model over the PDF.**
   Rejected by operator directive and on its merits: these are numbers filed
   against, and a model that is usually right produces an unsignalled wrong
   figure. It also collides with
   `sensitive-financial-data-secure-storage-only`, whose off-host clause bars
   transmitting these bytes without an explicit per-invocation consent the
   feature has no reason to ask for.
4. **Store the PDF on disk under the profile directory and keep a path
   pointer.** Rejected: a path pointer to a cleartext file is not a valid home
   for sensitive financial data, and this is precisely the shape the ledger
   evidence contract already refuses.
5. **Defer entirely and wait for the deudas register to populate.** Rejected:
   the closeout audit established the register is empty because the liabilities
   are at an earlier procedural stage, not because they do not exist. Waiting
   is waiting for a state change nobody can schedule, while the data the
   operator needs is already served and readable under a safe predicate.

## Constraints

- **The comparecencia predicate is binding and may only narrow.** No plan Step,
  no later record and no operator convenience may widen
  `assert_notification_content_readable` beyond `leida is True`. A row AEAT does
  not already report as read is refused, including one already served but
  unread. Adding a force flag, an override parameter, an "already served so the
  clock is running anyway" branch, or a batch fetch that walks unread rows are
  each a violation of this record, not an extension of it. The guard runs before
  any request crosses the wire; a guard that objected only after contact would
  already have driven the comparecencia.
- **The parse must be deterministic.** No model, local or remote, may stand
  between the PDF bytes and a persisted figure. Confidence for these fields is
  binary: a label matched or it did not.
- **Field-label coverage is specimen-bounded.** The labels observed on real
  documents are `Clave de liquidación:`, `Referencia:`, `N.I.F.:`, `Base sobre
  la que se liquida la sanción`, `Porcentaje mínimo de sanción`, `Sanción
  resultante`, `Reducción del 30%`, `Reducción del 40%` and `Diferencia`, with
  amounts printed as `3.687,12euros` — no space before the unit. Documents of
  other kinds (providencia de apremio, liquidación de intereses) are not
  covered by this observation set and must not be assumed to share it.
- **An unrecognised document is not an empty one.** A parse that matches no
  label must refuse or report explicitly unparsed, never persist a record of
  zeroes and never report a clean empty result. This is the standing lesson from
  this same reader's two silent failures.
- **No legal grounding is added and none is needed for display-as-reported.**
  The percentages printed on the document are AEAT's own figures repeated back.
  The moment the application interprets one — validating a band against arts.
  191-197, or asserting that a reduction was correctly applied — the
  human-reviewed grounding requirement in `aeat-calculation-grounding` binds,
  and the P06 catalogue entries this feature already carries become the
  citation source rather than decoration.
- **The upstream reader's coverage is not this record's to fix.** The closeout
  audit leaves an open note that the query surface's default window may not
  cover the whole inbox. This feature fetches documents for rows the reader
  returns; it inherits whatever the reader misses and must not paper over that
  by presenting its own output as a complete register.

## Implementation

The capability layers on top of the committed adapter function and adds nothing
to the AEAT contact surface beyond it.

**Transport (already committed).** `fetch_notification_document` and
`assert_notification_content_readable` in
`adapters/outbound/aeat/sede/_notifications.py` are in place, returning a typed
`NotificationDocument` carrying the bytes, their SHA-256 and the source URL,
with the guard executing before the session is touched. This record ratifies
that shape rather than proposing it, and fixes the predicate as an invariant so
a later change cannot quietly relax it.

**Custody.** An application-layer service persists the fetched bytes through the
encrypted content-addressed `AttachmentStore`, resolved the way the ledger
package resolves it, so the bytes are stored under their digest in the
FINANCIAL-sensitivity namespaces and never reach a filesystem path the operator
or a subprocess could read. Persistence is keyed on the certificado id, and a
re-fetch of an already-stored document is a content-addressed no-op rather than
a second copy. The service returns the stored reference and the digest; it never
returns a path.

**Parse.** A deterministic sanción/liquidación parser composes its patterns on
the existing `SPANISH_AMOUNT_GROUP` and parses captured amounts with the
existing `parse_spanish_decimal`, over text lifted by the existing
byte-level pdfplumber extractor. It declares its own label-to-field dispatch
rather than reusing the casilla-keyed one, and emits a typed frozen record with
Spanish-stemmed fields mirroring the printed labels — clave de liquidación,
referencia, base, porcentaje, sanción resultante, the two reducciones and the
diferencia — each optional, each accompanied by whether its label matched. A
document in which no label matches is reported unparsed and refuses to persist a
zeroed record.

**Operator surface.** Two leaves are added to the existing `app live
notifications` group: a fetch leaf taking the certificado id as a positional
argument, and a read-back leaf reading only what is already persisted with no
AEAT contact. The fetch leaf is named with the `pull` stem the CLI contract
requires and is enrolled in `PROFILE_BOUND_WRITE_VERB_PATHS` in the same change,
with the operator-orientation harness document swept in the same commit. Every
diagnostic — the refusal reason, an unparsed document, a re-fetch no-op — rides
the typed `Notice` channel; none becomes a bespoke result field. Help and label
strings get real values in all four locale catalogues through the locale CLI,
never a placeholder and never an en/es-only pair.

**Aggregation, deliberately bounded.** A history view lists the parsed documents
the profile holds with each document's own reported figures, its certificado id
and its date. It computes no total, asserts no balance, and carries a standing
notice that it is a record of what AEAT served, not a payable balance and not
the recaudación register the deudas verbs read. Whether any listed sanción is
paid, appealed, reduced or superseded is not stated on the document and is
therefore not stated by the application.

**Naming.** The domain types and their fields take Spanish stems, matching the
AEAT surface one-to-one as `aeat-naming` requires. The two CLI leaves attach to
the pre-existing English-named `notifications` family, which the governing
record already identified as the rule's carve-out for already-public pre-rule
identifiers; they are verbs on that family rather than a new family, so no new
English-named domain family is created. This is the one naming call in this
record a reviewer might reasonably revisit, and it is recorded rather than
assumed.

## Rationale

Option 1 wins on a knockout criterion the alternatives fail in different
directions. Option 2 fails on the only constraint that is not negotiable: the
fetch control performs a legal act, and no amount of interface ceremony converts
an agent's decision into the taxpayer's signature. Option 3 fails on the nature
of the output — an unsignalled wrong figure on a number that gets filed against
is worse than no figure, and the operator directive and the standing
sensitive-data rule both point the same way independently. Option 4 fails on a
rule this codebase already enforces elsewhere for strictly less sensitive
material. Option 5 fails on the closeout audit's own finding: the register is
empty because the data is upstream of it, so waiting is not patience, it is
choosing not to look where the evidence says the data is.

The chosen option is also the one whose every element already has a working
precedent in this tree — the guard is committed and live-verified, the
attachment store is the ledger's own custody path, the regex primitives are the
canonical extraction home with a known-defect history that argues for reuse over
re-authoring, and the CLI shape mirrors verbs the operator already uses. That
concentration of precedent is what makes the surface small enough to be safe
next to a control this consequential.

## Consequences

**Gains.** For the first time an operator can see, inside the application, the
figures AEAT has actually served against them — the base, the percentage, the
resultante and the reductions — for every notification the taxpayer has already
read. That is the standing goal, reached through the surface the evidence says
holds the data, without touching the payment-adjacent flow at all. The bytes
land in the same encrypted custody every other financial document in this
application uses, so the capability adds no new confidentiality surface.

**Difficulties.** The predicate means the register is permanently partial by construction:
notifications the taxpayer has not read are invisible to it, and that is
correct rather than a gap to close later. Label coverage is bounded by the
documents actually observed, so a differently-templated AEAT document will
report unparsed until its labels are added — visibly, which is the intended
behaviour, but it does mean the feature's usefulness grows by observation rather
than arriving complete.

**Pitfalls this decision heads off.** The obvious cheap paths all lead
somewhere bad: a force flag on the fetch would have made an agent capable of
serving a notification on the taxpayer; a model-based extractor would have
produced confident wrong numbers on figures that get filed against; a temp file
would have put a sanción PDF on operator disk in cleartext; and a summed total
would have asserted a payable balance the source document cannot support. Each
is refused here explicitly so a later contributor meets a decision rather than
an omission.

**Pathway opened.** Once parsed sanción records exist, the divergence
reconciliation the governing record deferred as its rejected option 2 has real
data on one side of the comparison for the first time — AEAT's served figures
against the application's own filed resultados. That remains its own decision
and is not licensed by this record.

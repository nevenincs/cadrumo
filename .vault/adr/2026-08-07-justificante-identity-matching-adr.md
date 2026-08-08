---
tags:
  - '#adr'
  - '#justificante-identity-matching'
date: '2026-08-07'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:3db455d979f5f04b4f4ddc8609b0ae32f5f4f66dfd65e793b213db3e47d69add'
related:
  - "[[2026-08-07-justificante-identity-matching-reference]]"
  - "[[2026-06-10-live-justificante-reconcile-adr]]"
  - "[[2026-05-04-live-filing-data-capture-adr]]"
---

# `justificante-identity-matching` adr: `Justificante presentation_id namespace correction` | (**status:** `accepted`)

## Problem Statement

`2026-08-07-justificante-identity-matching-reference` establishes, against two
real live-captured M303 justificante PDFs, that
`Justificante.matches_filing_target` rejects a valid receipt at every call
site in the tree because each caller supplies the register's `expediente_id`
as the predicate's `presentation_id` argument — a different AEAT identifier
namespace than the receipt's own printed field. The `live-justificante-reconcile`
ADR's register-reconciliation path and the `live-filing-data-capture` ADR's
capture-stamping path both depend on this predicate to auto-stamp local filing
records with AEAT-issued evidence; both are silently inert for M303, and
nothing distinguishes that from "no justificante present" in the resulting
report. A decision is needed on how to correct the comparison without
weakening the guard it exists to provide — the two candidate failure
directions (silent under-match, silent mis-stamp) are asymmetric in severity
per `no-silent-under-declaration` and `sensitive-financial-data-secure-storage-only`.

## Considerations

- Two AEAT identifiers already exist as distinct typed fields on `Justificante`
  (`csv`, `presentation_id`); `expediente_id` is a third, register-sourced
  identifier that never appears on the receipt body — reference, "Two distinct
  AEAT identifier namespaces exist on one receipt".
- All three populating callers pass `expediente_id` into `presentation_id` —
  systemic across the three call sites, not M303-specific — reference,
  "Every caller conflates the two namespaces".
- Two of the three sites already run a genuine, independently-sourced
  `csv == csv` identity check immediately before the broken comparison:
  `register_capture_as_filing_evidence` and, one function up from its own
  call, `register_capture_justificante_metadata` (the actual caller of
  `_justificante_matches_capture_axis`) — reference, "Two of the three sites
  already have a correct, independent CSV check alongside the broken one".
  **This corrects an earlier draft of this record and its reference, which
  had classified only the first of these two as guarded** without verifying
  the second site's actual caller.
- The third site (`_parse_matching_filed_justificante`, register
  reconciliation) has no adjacent check today, but the receipt's CSV is NOT
  unavailable there: `_capture_row_pdf_artefact` already resolves it via
  `extract_csv_from_url(cotejo_url)` while fetching the exact bytes this site
  parses, embeds it in the fetched `pdf_url`, and persists that URL verbatim
  as `FiledDeclaracionArtefact.source_url` — recoverable at comparison time
  with `extract_csv_from_url(artefact.source_url)`, no new persisted field, no
  persistence-boundary change — reference, "The third site's CSV is
  independently resolved during capture and then discarded".
- `extract_csv_from_url` is the sole canonical helper for this extraction
  (its own docstring: "shared more widely, by `_declarations.py` and
  `_parse.py` as well"). As of the most recent verification it is ALREADY
  exported through the sede package's public facade (`__init__.py:97,204`).
  **Correction: this was misattributed in an earlier draft as a peer's
  independent change landed ahead of this ADR.** The exporting docstring
  line ("and is re-exported through the package facade") that this ADR
  earlier cited as evidence of a peer's promotion was itself written by the
  `P01.S11` implementing row's own executor; a broad tree-wide sweep carried
  that uncommitted edit into HEAD before this ADR's review pass read it back,
  which made the executor's own work look like prior, unrelated third-party
  provenance. `P01.S11` was correctly executed and closed against its own
  change, not a peer's; this record now credits it correctly rather than
  crediting the wrong party for a real change.
- **The recovered CSV's provenance chain must stay independent of the
  receipt's own self-reported CSV, and this is not self-evident from the code
  today — it depends on how `source_url` is constructed.** The chain is:
  AEAT's cotejo redirect URL (server-chosen, not client-guessed) →
  `extract_csv_from_url(cotejo_url)` → our constructed `pdf_url` (`f"{origin}
  {_COTEJO_DOCUMENT_PATH}?CSV={csv}"`) → persisted verbatim as
  `FiledDeclaracionArtefact.source_url` → recovered via
  `extract_csv_from_url(artefact.source_url)` at comparison time. This is a
  genuinely independent channel from the receipt's own embedded CSV — the
  receipt's CSV is parsed from the PDF body text
  (`_extract.py`), while the compared value comes from AEAT's cotejo redirect,
  a structurally different source, so agreement is a real cross-channel
  check, not tautological. **That independence rests entirely on
  `source_url` continuing to be constructed from the cotejo URL.** If a
  future change builds `source_url` from a stored digest, a period-level
  template, or the receipt's own parsed CSV, the "check" becomes
  self-referential — comparing the receipt's CSV against a value ultimately
  derived from itself — and would pass unconditionally and silently while
  still reading as a real check. This is the same failure shape as this
  project's `required_text` tautology incident (`aeat-calculation-grounding`):
  a validator and the value it validates sharing one author or one
  derivation defeats the validator invisibly. Any future change to how
  `source_url` is constructed MUST re-establish or re-verify this
  independence and update this bullet to record how.
- `extract_csv_from_url` reads the `CSV` query parameter via
  `urlsplit`/`parse_qs` with **no path check** — fine here because every URL
  it is called against in this decision (`cotejo_url`, our own constructed
  `pdf_url`/`source_url`) is one this codebase built or received directly
  from an authenticated AEAT redirect, never an arbitrary or
  operator-supplied URL. This is stated explicitly so a future caller does
  not point the helper at an untrusted URL on the mistaken assumption that
  the helper itself validates provenance — it validates shape, not origin.
- Because every site can now perform its own genuine CSV equality check
  (two already do; the third can, without new persisted state), no caller has
  any remaining valid use for `matches_filing_target`'s `presentation_id`
  parameter. A parameter no caller can ever correctly populate, and every
  actual populating caller populated wrong, is a defect in the predicate's
  own signature — reference, "No caller has a valid reason to populate
  presentation_id".
- `no-silent-under-declaration` and the worktree rules' distrust of removing
  checks bear on this decision, but they are satisfied here by construction:
  every site ends this decision with the SAME OR STRONGER identity check it
  had going in (two keep an existing CSV check unchanged; the third GAINS one
  it did not have), never a weaker one, at every intermediate landing point —
  no row in the implementing plan may leave a site checked-then-unchecked
  even transiently.
- A separate, narrower `JustificanteCsv` type constraint (`_schema.py:22-29`,
  4-64 chars) diverges from the canonical `core._aeat_csv` CSV shape contract
  (8-32 uppercase alphanumeric, `core/_aeat_csv.py`), which states in its own
  docstring that "every layer meets a CSV and none of them owns it." This ADR
  does not reconcile them; it is exactly the fragmented free-form-identifier
  population the operator's parallel canonical typed-identifier-system effort
  is inventorying, and belongs there.
- Not every identifier-shaped field is a candidate for that effort:
  `Declaracion.estado` and (by the same reasoning, elsewhere in the tree)
  `Deuda.situacion` are AEAT-printed adjudicated-case labels whose vocabulary
  the app does not control and cannot enumerate; typing them as a closed set
  would be wrong, and this ADR does not recommend touching them.
- **The structural binding, not the predicate, is what has always prevented a
  cross-filing artefact mis-pairing at the register-reconciliation site, and
  this decision makes that binding load-bearing rather than incidental.**
  `_capture_row_pdf_artefact` fetches the `justificante_pdf` artefact through
  a Playwright `row_locator` built by `_row_locator_for_expediente`
  (`_declarations.py:1400-1404`), scoped to the ONE register row matching
  `declaration.expediente_id` and re-resolved fresh from the live grid for
  every declaration; AEAT's own server decides which cotejo popup and CSV
  that click opens, not this codebase. The `(observation, artefact)` pairing
  is therefore fixed at construction — before any `Justificante` model or
  predicate exists — and every downstream consumer iterates strictly
  `observation.artefacts`, never a pooled or re-associated set. The
  `presentation_id`/`expediente_id` comparison being removed never actually
  performed this binding; it only ever re-checked PDF content against a
  namespace mismatch that could never agree. Once it is gone,
  `_row_locator_for_expediente` is the SOLE remaining mechanism preventing a
  cross-filing mis-pairing, which raises its own correctness bar: it
  currently filters via
  Playwright `has_text=expediente_id`, a **substring** match. AEAT expediente
  ids are 12-32 character tracking numbers with no known reachable
  substring collision, so this is not evidence of a live defect, but a sole
  mechanism should not rest on substring matching when an exact match is a
  small, available hardening.

## Considered options

1. **Drop the `presentation_id`/`expediente_id` argument everywhere it fires,
   uniformly, treating the two already-guarded sites and the ungrounded
   register-reconciliation site the same way.** Rejected: this was an earlier
   draft of this decision, corrected once the second `_justificante.py` call
   site's own caller was actually read rather than assumed equivalent to the
   first, and once `_capture_row_pdf_artefact` was read and found to already
   resolve a CSV the register-reconciliation site had been assumed not to
   have. Applying it uniformly would have left the third site with NO check
   at all where a real one is available cheaply — the exact silent-mis-stamp
   shape this decision must not produce.
2. **Compare `expediente_id` against `presentation_id` with a normalising
   transform (strip a prefix/suffix, re-derive one from the other).** Rejected:
   no evidence anywhere in the corpus that the two values share a derivable
   relationship; inventing one would be exactly the fabricated-behavior defect
   `aeat-calculation-grounding` forbids for legal semantics, and this is the
   same category of un-grounded invention applied to an identifier grammar.
3. **Keep passing `expediente_id` into `presentation_id` and treat every
   real-world mismatch as a legitimate refusal.** Rejected: the reference
   proves this makes the predicate reject 100% of real receipts, which is a
   permanent, silent under-delivery of the register-reconciliation and
   capture-stamping ADRs' stated purpose — worse than a narrower but correct
   guard.
4. **Chosen — differentiate by site, and add the CSV check the third site is
   currently missing rather than removing its only check.** At the two sites
   already guarded by an independent `csv == csv` comparison
   (`register_capture_as_filing_evidence`, `register_capture_justificante_metadata`),
   drop the redundant, wrong-namespace `presentation_id=...expediente_id`
   argument — strictly subtractive, a real check already covers the axis. At
   the third site (`_parse_matching_filed_justificante`), ADD a `csv == csv`
   check by recovering the CSV from `FiledDeclaracionArtefact.source_url` via
   `extract_csv_from_url` (promoted to the sede package facade first, per
   `aeat-architecture-boundaries`), THEN drop the same wrong-namespace
   argument. No site ever lands in a weaker state than it started in, at any
   intermediate row.
5. **Remove the `presentation_id` parameter from `matches_filing_target`'s
   signature entirely, rather than merely re-documenting it (superseding an
   earlier draft's docstring-strengthening idea).** Chosen. Once every site
   performs its own CSV check (Option 4), no caller anywhere in the tree has a
   valid reason to populate `presentation_id` — it is not a parameter some
   callers use correctly and others misuse; it is a parameter NO caller can
   ever correctly populate, because the receipt-namespace verification
   correctly lives as a caller-owned CSV comparison, not as an optional
   secondary axis threaded through the predicate. A docstring warning on a
   parameter with zero valid call shapes is a weaker guard than removing the
   parameter, which makes the wrong shape a `TypeError` instead of a
   silently-ignorable comment.
6. **Add a typed `identifier_namespace` marker to `matches_filing_target`
   instead of removing `presentation_id`.** Rejected as unnecessary given
   Option 5: once the parameter is gone, there is no namespace left to mark.
   Superseded, not merely deferred.
7. **Route the register-reconciliation site through a NEW `csv` field on
   `FiledDeclaracionObservation` or `FiledDeclaracionArtefact`, populated by
   extending register-row capture to resolve and persist a CSV.** Rejected in
   favor of Option 4's non-persisting recovery: the CSV needed already exists,
   embedded in the already-persisted `source_url` field, so adding a new
   persisted field would duplicate data already on disk, force a
   persistence-boundary migration (strict roundtrip, anti-tautology proof)
   this decision does not need, and create two on-disk representations of the
   same fact that could drift.

## Constraints

- No live AEAT access from this record's implementing rows; every fix is
  verified against committed fixtures
  (`src/cadrumo/tests/fixtures/justificantes/303/*.pdf`) and unit coverage,
  never a fresh live pull. **Correction: these fixtures are `synthetic_generated`
  in all fifteen sidecars, not `real_corpus`** — an earlier draft of this
  record stated otherwise on a relayed, unverified claim. No inference in
  this decision rests on the fixtures being real AEAT-issued bytes; the
  empirical grounding (`presentation_id != expediente_id` on real receipts)
  came from a separate live-captured pair loaded from encrypted storage, not
  from this committed corpus. **Directly re-measured against the real
  production parser** (`parse_justificante_bytes`) rather than trusting the
  relayed figure: ALL FIFTEEN committed `303` fixtures parse to
  `presentation_id = None`, not merely "two" as an earlier relay in this
  campaign stated. Before the fix, `matches_filing_target`'s
  `presentation_id` comparison only fired when the receipt's own
  `presentation_id` was non-empty (`_schema.py:120-126`); against a
  null-`presentation_id` fixture it was a silent no-op returning a MATCH
  regardless of what was passed. A "pinning test" built to demonstrate the
  original defect (predicate rejects a valid receipt because
  `presentation_id != expediente_id`) using any fixture from this corpus
  would therefore have silently NOT exercised the defect at all — it would
  have matched trivially and reported the fix as proven when nothing
  specific to `presentation_id` was ever tested. This corpus's fixtures do
  carry a non-null `csv` (each `SANITIZED303<year>`, shape-valid per
  `is_aeat_csv`), so they remain usable for the corrected code's CSV-equality
  checks; they are simply unusable as a demonstration of the specific
  original `presentation_id`/`expediente_id` defect, which needed the
  separate live-captured receipts to establish.
- A pinning test asserting today's (defective) rejection is being authored in
  parallel by another agent and had not landed as of this decision's most
  recent verification; the implementing row that lands the fix MUST re-check
  for it immediately before executing and, if found, update its assertion to
  the corrected behavior in the same change — it must not be deleted,
  skipped, left asserting the old defect, or duplicated by a second
  independently-authored test.
- Any mutation-proof test in this plan's implementing rows MUST run with
  `pytest-xdist` disabled (`-n0`), including checking for a project
  `addopts` default that injects `-n auto` — xdist workers are separate
  processes and never observe an in-memory mutation performed by the test
  process, which makes an un-forced proof vacuous regardless of its
  assertions.
- No legal-catalogue entries are touched by this decision; it is a pure
  identifier-matching correction with no BOE/AEAT legal-provenance
  implication.
- No implementing row may leave any of the three sites, at any intermediate
  landing point, checked more weakly than it is at HEAD today. The two
  already-guarded sites keep their guard unchanged throughout; the
  ungrounded third site gains its CSV check in the SAME change that removes
  its wrong-namespace argument, never as two separate landings with the
  weaker state shippable in between.
- `Declaracion.estado` and `Deuda.situacion` (AEAT-printed adjudicated-case
  labels with app-uncontrolled vocabulary) are out of scope for typing under
  this or the parallel identifier-system effort; this decision does not
  recommend touching them.
- Reconciling `JustificanteCsv`'s narrower constraint onto `core._aeat_csv`'s
  canonical CSV shape contract is out of scope for this decision; it is
  flagged in the Considerations for the parallel canonical
  typed-identifier-system effort to pick up.

## Implementation

`Justificante.matches_filing_target` DROPS its `presentation_id` parameter
entirely (Option 5). Every caller instead performs its own `csv == csv`
equality check before calling the narrowed predicate on `modelo`,
`filing_year`, `period`, and `tax_id` only:

- `register_capture_as_filing_evidence` (`_justificante.py`) keeps its
  pre-existing `justificante.csv == snapshot.csv` check (`:673-676`)
  unchanged and drops the now-signature-invalid `presentation_id=
  snapshot.expediente_id` argument from its call into
  `_justificante_matches_filing_record`.
- `register_capture_justificante_metadata` (`_justificante.py`) keeps its
  pre-existing `justificante.csv == snapshot.csv` check (`:549-552`)
  unchanged and drops the same now-signature-invalid argument from its call
  into `_justificante_matches_capture_axis`.
- `extract_csv_from_url` (`_declarations_remote.py`) is promoted into the
  sede package's public facade (`__all__` in
  `adapters/outbound/aeat/sede/__init__.py:97,204`) by `P01.S11` itself — a
  precondition of consuming it from `application/live/`, per
  `aeat-architecture-boundaries`. (An earlier draft of this row
  misattributed the promotion to a peer; see the correction in
  Considerations.)
- `_parse_matching_filed_justificante`
  (`_filed_observation_persistence.py`) GAINS a `csv == csv` check it did not
  have: recover the CSV from the `justificante_pdf` artefact's
  `source_url` via the promoted `extract_csv_from_url`, compare against the
  freshly parsed `justificante.csv`, and treat a mismatch as a fifth swallowed
  outcome alongside the four already tracked (see Observability, below) —
  never a hard exception that would crash the enrollment call, matching the
  existing swallow-and-report shape of its sibling failure modes. The
  now-signature-invalid `presentation_id=observation.expediente_id` argument
  is dropped from its call into `_justificante_matches_filed_observation` in
  the SAME change that adds the CSV check — never a separate landing that
  would leave this site checked-then-unchecked in between.
- `_justificante_matches_filed_observation`,
  `_justificante_matches_capture_axis`, and `_justificante_matches_filing_record`
  all lose their now-dead `presentation_id` parameter and argument, following
  the predicate's narrowed signature.
- `_row_locator_for_expediente` (`_declarations.py:1400-1404`) changes its
  `has_text=expediente_id` substring filter to an exact match, anchoring on
  the existing `re` import already used in the same module
  (`_declarations.py:27`) rather than introducing a second selection idiom —
  `has_text=re.compile(rf"^{re.escape(expediente_id)}$")` or equivalent. No
  reusable exact-match `filter(has_text=...)` idiom exists elsewhere in this
  adapter family to import instead (the one other exact-match idiom in the
  file, `page.get_by_text(label_text, exact=True)` at `:794,829`, is a
  different Playwright API shape for a different selection need, not a
  `filter(has_text=...)` call).
- Observability: `_parse_matching_filed_justificante` distinguishes its SIX
  swallowed outcomes — `UNREADABLE_ARTEFACT`, `MANIFEST_MISMATCH`,
  `UNPARSABLE_PDF`, `CSV_UNRESOLVABLE` (a malformed or CSV-less
  `source_url`), `CSV_MISMATCH`, and `FILING_TARGET_MISMATCH` (the receipt
  parsed and its CSV agrees, but its `modelo`/`ejercicio`/`period`/taxpayer
  does not describe this observation — the pre-existing filing-target
  rejection this ADR's earlier draft omitted from its own count). Folding
  `FILING_TARGET_MISMATCH` into a neighbouring reason would recreate exactly
  the collapse this observability work exists to undo — a diagnostic
  taxonomy merging two distinguishable causes reproduces the defect it fixes
  — so it is named as its own member, not absorbed. The two enrollment call
  sites surface a non-blocking `Notice` (via the shared
  `cadrumo.core.json_contract.Notice` channel, per `aeat-cli-contract`) when a
  justificante artefact was present but produced no saved evidence, naming
  which of the six reasons applies. This does not invent a bespoke advisory
  field; it routes through the existing typed channel.

## Rationale

Option 4 (differentiate by site) wins on the knockout criterion this ADR is
bound by — every intermediate and final state stays at least as strict as
HEAD — because it is grounded in what each site actually has, verified per
site rather than assumed uniform: two sites already run a genuine `csv ==
csv` check (reference, "Two of the three sites already have a correct,
independent CSV check"), so dropping their redundant wrong-namespace argument
is strictly subtractive. The third site is not check-less by necessity; its
CSV is computed during capture and thrown away, recoverable from a field
already on disk with zero schema change (reference, "The third site's CSV is
independently resolved during capture and then discarded"). An earlier
draft of this decision proposed dropping the argument uniformly at all
"register-reconciliation" sites on the premise that none had an
independently-known identifier — that premise was wrong for two of the three
sites once their actual callers were read, and this record corrects it rather
than shipping it. Option 3 was rejected because it is the exact
silent-under-declaration shape `no-silent-under-declaration` exists to catch,
just relocated to the evidence-stamping surface instead of a calculation
casilla. Option 2 was rejected for lacking any grounding — inventing an
identifier transform is fabrication, the same failure mode
`aeat-calculation-grounding` names for legal semantics. Option 7 (a new
persisted CSV field) was rejected in favor of Option 4's zero-schema-change
recovery once `source_url` was confirmed to already carry the CSV — adding a
field to duplicate data already on disk is a persistence-boundary change with
no offsetting benefit.

Option 5 (remove `presentation_id` from the signature, superseding an
earlier docstring-only proposal) answers the standing design question this
ADR raised directly: SHOULD a parameter no caller can ever correctly populate
still exist? Once Option 4 lands, `presentation_id` has zero valid call
shapes anywhere in the tree — not "usually misused," structurally unusable
correctly, because the receipt-namespace verification is now uniformly a
caller-owned CSV comparison performed before the predicate runs, never an
argument threaded through it. A docstring warning documents a temptation;
removing the parameter converts the temptation into a `TypeError` a linter
and a reviewer both catch for free, which is strictly stronger and does not
require inventing a new typed-namespace-marker concept (Option 6) to police a
parameter that need not exist at all.

## Consequences

**Gains:** live-captured M303 justificante evidence (and every other modelo
reachable through these three call sites) can auto-stamp local filing records
again. The PRIMARY protection against a cross-filing artefact mis-pairing was
always, and remains, `_row_locator_for_expediente`'s row-scoped Playwright
fetch (Considerations) — this decision does not create that protection, it
was already there and this decision now says so in the record rather than
leaving it implicit. What this decision ADDS is a SECONDARY, defense-in-depth
`csv == csv` check at all three sites, catching a different bug class: a
downstream storage, caching, or selection-layer defect that re-associates a
correctly-fetched artefact with the wrong observation AFTER capture — a bug
in this codebase, not in the AEAT round-trip. The digest check
`load_artefact` already performs is self-referential (it re-hashes decrypted
bytes against the digest that IS the storage key, proving byte integrity, not
correct filing association), so the CSV check is the first content-level
identity check this codebase has ever performed after storage. The
`live-justificante-reconcile` and `live-filing-data-capture` ADRs' stated
purpose stops being silently inert; an operator gets a visible `Notice`
distinguishing "nothing to capture" from "capture rejected" from "CSV
mismatch" instead of an unexplained zero. `matches_filing_target` loses a
parameter no caller could ever populate correctly, closing the recurrence
risk structurally rather than by convention. `_row_locator_for_expediente`
moves from substring to exact matching, closing the one caveat the trace
raised against the mechanism this decision now depends on more visibly.

**Difficulties:** `extract_csv_from_url` raises `SedeParseError` on a
malformed or CSV-less URL, which `_parse_matching_filed_justificante` must
now catch and fold into its existing swallow-and-report shape rather than let
propagate; a missed case there degrades to an unhandled exception instead of
a reported non-match, which the mutation-proof coverage in the plan must
specifically probe. Promoting `extract_csv_from_url` to the sede facade
widens its public surface; any future change to its shape or error contract
now has an application-layer consumer to consider, not only outbound-adapter
ones. The added CSV check is defense-in-depth, not the primary guarantee — a
reviewer reading only this decision without the structural-binding
Consideration above could overstate what it protects against.

**Pathway opened:** the parallel canonical typed-identifier-system effort has
a concrete worked example in this decision — `core._aeat_csv`'s shape
contract and `JustificanteCsv`'s narrower one diverge, flagged but not
reconciled here (Considerations, Constraints).

**Pitfall guarded against:** a future author re-adding a
`presentation_id`-shaped argument at any of these sites, or at a new call
site, cannot compile against the narrowed predicate signature — the removed
parameter is itself the durable guard against that recurrence, backed by the
corrected unit test. Separately, and only guarded by THIS record rather than
by any test: a future contributor refactoring
`_capture_row_pdf_artefact`/`capture_declaration` away from a per-row,
per-click cotejo fetch toward a period-level or batch-level listing URL would
look like an unrelated, reasonable efficiency change while silently
destroying the row-scoped binding this decision's entire safety argument now
depends on more visibly than before. Any change to that fetch shape MUST
re-establish an equivalent row-exact binding before landing, and MUST update
this ADR's Considerations to record how.

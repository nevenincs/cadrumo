---
tags:
  - '#reference'
  - '#canonical-identifiers'
date: '2026-08-07'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:d3966ccba645abd418620030d5c8407a7b504f7dc1c1fa237d75a8f95146e561'
related:
  - "[[2026-08-07-justificante-identity-matching-adr]]"
---
# `canonical-identifiers` reference: `AEAT identifier taxonomy census`

Grounds an ADR deciding a canonical document-identifier type system: one
existing home to extend, the AEAT-issued identifier taxonomy that home does
not yet cover, the app-derived identifiers already covering it, the sites
where two namespaces are conflated, and the traps a retype could trigger.
Discovery ran `vaultspec-rag` semantic search (`--type code`, `--type vault
--doc-type adr`) before every codebase claim below, confirmed against `HEAD`
by direct read; this document does not restate the AST census run separately
(`scratchpad\id_field_inventory.csv` in the coordinating session: 8215
model fields tree-wide, 1420 identifier-shaped by name, 1381 in production,
589 bare `str` with no alias or constraint — the enrollment surface, name-
heuristic-derived and therefore both an undercount on unconventional names
and an overcount on non-identifiers).

## Summary

`core/identity/` is the sole existing home for identity concepts and
already models the alias-from-one-primitive discipline a taxonomy must
extend, not duplicate. Four AEAT-issued identifier concepts (CSV, número
de justificante, expediente id, clave de liquidación) are typed today at
three divergent CSV strengths and a tighter-versus-looser expediente-id
split, with a live three-site conflation (`presentation_id` fed an
`expediente_id` value) whose fix a sibling ADR already accepted and whose
deferred type-level hardening this reference feeds forward. Two modules
duplicate the shared hex-64 primitive instead of aliasing it. Storage-key
orphaning, AEAT shape-tolerance, and adjudicated non-identifiers are the
concrete traps a canonical taxonomy must not trip.

## The existing canonical home: `core/identity/`

`src/cadrumo/core/identity/__init__.py` is the sole public facade for
identity concepts and already declares the intended pattern for a shared
constrained-string primitive: `SnapshotId = _Hex64Str` and
`TransactionId = _Hex64Str` (lines 63, 79) — a semantic alias assigned FROM
`core/_hex.py::Hex64Str`, never a re-declared `StringConstraints(...)` call.
`core/_hex.py`'s own docstring on `Hex64Str` (lines 75-87) states this in so
many words: "every unrelated hex-64 IDENTITY concept … is declared as its OWN
semantic alias assigned FROM this one primitive … never by re-declaring the
`StringConstraints(...)` call." The facade also carries `BucketId`,
`ProfileId`, `ProfileLabel`, `ContentDigest`/`ContentDigestOrAbsent`,
`SubjectTaxId`, `TaxIdIdentityToken`, `IdentityDocument` (a closed
`StrEnum`), and the `same_tax_identifier` / `tax_id_identity_token`
comparison helpers. **Any canonical identifier system extends this module;
it does not create a second home** — a second package would itself be the
duplicate-authority defect the project's rules treat as a blocker.

`core/_aeat_csv.py` is a second, narrower existing primitive: `is_aeat_csv()`
matches one complete 8-32 uppercase-alphanumeric run, `AEAT_CSV_PATTERN`
exported alongside it. It is consumed today only by
`adapters/outbound/aeat/sede/_schema.py::JustificanteRef.csv` (`Field(min_length=8,
max_length=32)` plus a `field_validator` calling `is_aeat_csv`, lines 148-181).
It is not yet promoted into `core/identity/` and not yet a pydantic type
alias — it is a bool-returning shape check plus a compiled pattern, consumed
by hand at one call site.

## The pattern already violated: two hand-rolled hex-64 duplicates

`domain/modelos/_ids.py` (`WorkUnitId`, `CalculationRevisionId`,
`FilingRecordId`, `VerificationReportId`) and `domain/invoices/_ids.py`
(`InvoiceId`) each declare their own module-local
`_HEX_64_PATTERN = r"^[0-9a-f]{64}$"` and their own
`Annotated[str, StringConstraints(strip_whitespace=True, min_length=64,
max_length=64, pattern=_HEX_64_PATTERN)]` rather than aliasing
`core/_hex.py::Hex64Str` the way `SnapshotId`/`TransactionId` already do.
Functionally identical to `Hex64Str` today (same strip/length/pattern), so no
observable defect exists yet — but it is a duplicate declaration of the exact
primitive `core/_hex.py`'s docstring names as the one all such concepts must
alias, standing in the same module tree (`domain/modelos/`) whose own facade
already imports `core/identity/` concepts elsewhere. This is a decision
point for the ADR: fix (alias from `Hex64Str`, five one-line changes, no
persisted-shape change) or explicitly grandfather with a stated reason.

**Correction (2026-08-10): the count in this section's own heading is an
undercount. There are SIX, not two.**

Stated as a correction rather than a silent replacement, because a reader who
sees only "six" cannot tell whether the surface grew or the original
measurement was wrong, and those imply different things about how much weight
this document can carry. The surface did not grow. The measurement was wrong
when it was written, and the two it names are the two that happened to sit in
the modules the survey was reading.

Measured against the finished tree after every relocation this reference's
plan specified had landed:

| site | status |
| --- | --- |
| `domain/modelos/_ids.py` | closed, named here originally |
| `domain/invoices/_ids.py` | closed, named here originally |
| `domain/modelos/_verification_report.py` | closed, NOT named here -- found while editing the file during its own relocation |
| `application/evidence/_ids.py` | OPEN |
| `domain/attachments/_ids.py` | OPEN |
| `application/modelo/_m145_communication_records.py` | OPEN |

Each of the six declares its own `_HEX_64_PATTERN = r"^[0-9a-f]{64}$"` -- the
exact literal `core/_hex.py`'s docstring names as the thing every hex-64
identity concept must alias rather than re-declare. So a future author reading
that discipline and then reading the tree finds live counterexamples, which
teaches that the rule is aspirational.

**Why this matters beyond the count.** The plan's opening Wave is premised on
this section: it exists to collapse "the two hand-rolled hex-64 declarations"
so the taxonomy grows from a clean shared base. Closing that Wave against its
original rows would have satisfied every row while leaving the Wave's own
stated goal unmet -- the delivered-narrower failure arriving at the moment of
closure, when everything is green and the instinct is to close. The three
remaining sites are now rowed rather than absorbed, so the gap is findable.

**How the undercount was found, since the method transfers.** Not by a gate.
By re-running this document's own measurement against the finished state
instead of trusting the commits that closed its rows. Closing on rows tells
you the rows are done. Re-running the measurement the work was premised on
tells you whether the goal is met, and those are different questions that look
identical from a green board.

## The AEAT-issued taxonomy: four identifiers, three typed today, one absent

AEAT issues (at minimum) four distinct identifier concepts across the
justificante and sede/register surfaces. None of the four is named as a
namespace anywhere in the type system today; each is a same-shaped-or-looser
`str` field with no cross-reference to its siblings.

1. **CSV (Código Seguro de Verificación).** AEAT's per-document verifier
   hash, printed on receipts and accepted at the public cotejo endpoint to
   re-serve the document. **Three divergent validation strengths coexist for
   the same concept:**
   - `core/_aeat_csv.py::is_aeat_csv()` / `AEAT_CSV_PATTERN` — 8-32 uppercase
     alphanumeric, pattern-enforced. Consumed by
     `sede/_schema.py::JustificanteRef.csv` (line 171) via a
     `field_validator`.
   - `domain/justificante/_schema.py::JustificanteCsv` (line 22) —
     `Annotated[str, StringConstraints(min_length=4, max_length=64)]`,
     **no pattern at all.** This is `Justificante.csv`'s own field type (line
     76) — the type that actually parses live-captured AEAT PDFs.
   - Unconstrained bare `str` at `application/live/_justificante.py` (two
     sites) and `adapters/inbound/borrador/_schema.py`.
   Normalisation also diverges: the verify adapter path applies
   `.strip().upper()`; `application/overview/_calendar_evidence.py` applies
   `.casefold()`. Two different normal forms for one concept, independent of
   the three validation strengths.
2. **Número de justificante** (`Justificante.presentation_id`,
   `domain/justificante/_schema.py` line 80) — AEAT's internal presentation
   identifier, printed on the receipt. `str | None`, `max_length=64`, no
   pattern, no cross-reference to `csv`.
3. **Expediente id** — the register/procedure-listing identifier. Pattern
   `^[0-9]{4}[A-Z0-9]+$`-shaped (the module's own field docstring calls it
   "the AEAT shape pattern"; the declared bounds are `min_length=12,
   max_length=32`, `sede/_schema.py` lines 100-135, 158-172, 455-471 — 11
   production fields carrying it, every one a bare `str` with the
   per-field-repeated bound rather than a shared alias). The module comment
   frames the bound as an "observed range," not a closed spec — it is
   external AEAT variability, not a value the app controls, so tightening it
   risks rejecting a real AEAT-issued shape not yet seen. One divergent
   instance: `domain/iva_compensation/_carry_forward.py`
   `PeriodComplianceState.expediente_id` (around line 66) declares
   `min_length=1, max_length=32` — **no pattern, no lower shape bound** — the
   identical concept the sede schema constrains far tighter. `"1"` passes
   validation there today.
4. **Clave de liquidación** (`Deuda.clave_liquidacion`) — a fourth AEAT
   identifier, distinct from all three above, with no type distinction from
   plain `str` anywhere it appears. Named here so the ADR must scope it in or
   out explicitly rather than by omission.

**NRC (Número de Referencia Completo)** has **zero Python representation.**
It is located by regex only, adjacent to a payment amount, then discarded —
there is no field, model, or persisted value carrying it anywhere in the
tree today. Enrolling it under a canonical taxonomy is new capture-and-persist
work, not a retype of an existing field, and the ADR must treat it as
explicitly scoped in or out rather than assumed covered by "the taxonomy now
exists."

**Correction (2026-08-10): item 1's claim that the loosest CSV type is the one
proven against real receipts is FALSE, and this document held the evidence
against it the whole time.** The claim that `JustificanteCsv` (4-64, no
pattern) "is the type that actually parses live-captured AEAT PDFs" was
never measured against the captured CSV values this repository already
records. Those values are: `FNBB57PE9KZ5TN4R`, `MZRSYDRL5JMPJPRT` and
`TUD4V9XAUV7QJ8QV`, captured from three separate real IRPF filings (2021,
2022, 2023) and described as byte-identical across two independent capture
rounds - `2026-04-25-aeat-verify-research` and `2026-04-26-aeat-verify-audit`.
Every one is sixteen uppercase alphanumeric characters. Every one satisfies
`core/_aeat_csv.py`'s 8-32 uppercase-alphanumeric contract, with margin on
both sides. **No AEAT-issued value anywhere in this repository requires the
4-64 bound.**

The error is worth naming precisely, because the implementing plan reproduced
it and reached a stronger wrong conclusion. The plan's `W02.P03` re-planning
note searched for captured justificante *PDFs*, found only
`synthetic_generated` fixtures, and concluded that no empirical grounding for
the CSV shape existed or could be obtained. The artefact that carried the
evidence was absent; the evidence itself was not. It sat in the vault's own
research and audit records. A census that looks for the container and
concludes the content does not exist is the failure mode here, and it
converted a decidable question into a documented-contract argument.

The consequent decision, ruled 2026-08-10: `core/_aeat_csv.py`'s 8-32 plus
uppercase-alphanumeric pattern is canonical, and `JustificanteCsv`'s
4-64-no-pattern bound is retired rather than kept as a second opinion. This
is the one place in this campaign where the substitutability pre-filter
selects the TIGHTER type, so the reasoning is recorded rather than assumed:
the filter asks whether the survivor refuses anything legitimate that the
retiree admits. 8-32 refuses nothing observed. What 4-64 admits is `tiny` and
`CSV-ORIG-001` as valid filing evidence.

**The limit on this evidence, stated rather than buried:** three CSVs drawn
from one taxpayer's IRPF filings is a narrow sample, and it does not prove
AEAT never issues another shape. What makes the tighter bound safe is the
margin and the risk asymmetry, not the sample size - every observed value
sits at sixteen characters, mid-window. Anyone revisiting this decision must
weigh that sentence rather than the count of supporting values.

## Classification census: AEAT-issued and app-derived membership

Promoted here from a coordinating session's `classified589.csv` (produced by
a separate AST classification pass over the 589-field surface) because a
plan Step's execution record cannot reconcile against a scratchpad artefact
living in another agent's session — a different agent's scratchpad
directory is not a shared or durable location, so a reconciliation gate
pointing at it is unmeetable by any executor. This table is the durable,
version-controlled substitute; plan Steps reconcile against THIS section,
never the scratchpad path. Per-name counts below are attributed to that
census as reported and are NOT independently re-derived here, except where
marked "verified" — those were confirmed by direct grep against `HEAD` in
this session (command output, not re-typed by hand).

**AEAT-issued names (target: a new `IdentifierNamespace.AEAT_*` member and
alias each), 62 sites across the census's 24 names:**

| field name | approx. sites | target alias | status |
| --- | --- | --- | --- |
| `expediente_id` | 11 (sede) + 1 (iva_compensation) + 1 (wire) = 13 | `AeatExpedienteId` | verified: `sede/_schema.py` lines 100-135, 158-172, 455-471; `iva_compensation/_carry_forward.py` ~line 66; `entrypoints/cli/_app_live_payloads.py:614-638` |
| `csv` | 3 divergent declarations + 2 bare | `AeatCsv` | verified: `core/_aeat_csv.py`, `domain/justificante/_schema.py:22,76`, `sede/_schema.py:148-181` |
| `presentation_id` | 1 (plus the conflation sites) | `AeatPresentationId` | verified: `domain/justificante/_schema.py:80` |
| `clave_liquidacion` | 1 (NOT in the 589 — suffix-less noun, AST heuristic miss) | `AeatClaveLiquidacion` | verified: `Deuda.clave_liquidacion` |
| `certificado_id` | not separately counted | `AeatCertificadoId` | verified: `sede/_notifications.py`, docstring "Nº de certificado, 13-digit or longer" |
| `display_number` | 5 | `AeatBoxNumber` | per census, not independently re-verified |
| `form_number`, `from_number`, `to_number` | not separately counted | `AeatBoxNumber` | per census, not independently re-verified |
| `tax_id` | 6 | `SubjectTaxId` (self/profile-owned) | per census |
| `profile_tax_id` | included above | `SubjectTaxId` | verified already correctly typed at `domain/filing/_schema.py:261,394` — EXCLUDE this site from the retype Step, it is done |
| `spouse_tax_id` | not separately counted | `SubjectTaxId` | per census |
| `supplier_tax_id` | 6 | `TaxIdIdentityToken` (counterparty-facing) | per census |
| `customer_tax_id` | 5 | `TaxIdIdentityToken` | per census |
| `party_tax_id` | 4 | `TaxIdIdentityToken` | per census |
| `counterparty_tax_id` | 2 | `TaxIdIdentityToken` | per census |
| `donor_tax_id`, `member_tax_id` | not separately counted | `TaxIdIdentityToken` | per census |
| `official_tipo_renta_code` (M210) | 5 | `StrEnum`, not `IdentifierNamespace` | per census |
| `operation_kind_code`, `asset_class_code` (M720) | not separately counted | `StrEnum`, not `IdentifierNamespace` | per census |

**App-derived names (target: alias FROM an existing or newly-declared
app-derived primitive), 302 sites across the census's names:**

| field name | approx. sites | target alias | status |
| --- | --- | --- | --- |
| `transaction_id` | 30 | `TransactionId` (exists) | verified: real file list gathered by grep in `application/ledger/`, `application/aggregation/`, `domain/transactions/`, `entrypoints/cli/`, `llm/` (see plan `W04.P06.S29`/`S30` for the file groupings actually used) |
| `bucket_id` | 24 | `BucketId` (exists) | verified: file list spans `adapters/persistence/`, `application/`, `core/`, `domain/`, `entrypoints/cli/` — far wider than the census count suggests many sites are function parameters, not model fields; the plan's `W04.P06.S31` scope is model-field-only, matching the census's own methodology |
| `invoice_id` | 16 | `InvoiceId` (exists) | verified: file list in `application/invoices/`, `domain/invoices/`, `entrypoints/cli/` |
| `bucket_event_id` | 7 | `BucketEventId` (exists, declared in `domain/buckets/_event.py`, NOT `core/identity/`) | verified: `domain/buckets/_event.py:28` aliases `Hex64Str` already; consumers in `application/modelo/_reconciliation_records.py`, `entrypoints/cli/_ledger_payloads.py`, `entrypoints/cli/_modelo_payloads.py` |
| `revision_id` | 12 (UNDETERMINED by the census, deliberately not app-derived-classified) | split between `CalculationRevisionId` and new `RegistryRevisionId` per-site | verified: `registry_snapshot_id_for()` at `domain/calculations/registry/_snapshot_coordinate.py:54` takes the registry version-tag meaning, not hex-64 |
| `short_work_unit_id` | 3 | `Hex16Str` (exists) | per census — **WITHDRAWN 2026-08-13: `Hex16Str` admits only 16 characters and these values are 12; the target alias in this row is wrong and must not be acted on. See the amendment at the end of this document.** |
| `short_calculation_revision_id` | 2 | `Hex16Str` (exists) | per census — **WITHDRAWN 2026-08-13: `Hex16Str` admits only 16 characters and these values are 12; the target alias in this row is wrong and must not be acted on. See the amendment at the end of this document.** |
| `registry_snapshot_id` | 3 | new `RegistrySnapshotId` | per census; explicitly NOT `core.identity.SnapshotId` |
| `registry_revision_id` | not separately counted | new `RegistryRevisionId` | per census |

**Remaining buckets, summarised by count with notable members named:** 128
UNDETERMINED (`revision_id`'s 12 are the only ones individually resolved
above; the rest need the same per-site treatment before enrollment); 72
NOT_AN_IDENTIFIER (`Declaracion.estado`, `Deuda.situacion` are the
adjudicated, must-stay-excluded members; the census's other 70 were not
individually named here); 25 deliberately FREE_TEXT, split into three
sub-populations per the ADR's Amendment: AEAT-bounded prose (`estado`,
`situacion`), counterparty-issued document numbers (`invoice_number`), and
externally-controlled non-AEAT identifiers (`file_id`, `spreadsheet_id`,
`folder_id` from Google; `serial_number` from PKI; `spdx_id`; possibly
`finca_identifier` from Catastro, unconfirmed).

**Known limitation of this table, stated rather than hidden — and see the
second 2026-08-13 amendment, which measures it and finds it understates the
large families without exception:** every count
not marked "verified" is relayed from the coordinating census as reported
in chat, not independently re-derived by an AST tool in this session. A
plan Step consuming this table must still enumerate the exact files it
touches in its own execution record — this table bounds the SET of names
and approximate sizes, not a byte-exact per-file manifest.

**Addition (2026-08-10): the floor is now MEASURED, and it had a second breach
nobody had found.** The decision record establishes that the 589-field count is a
floor rather than a ceiling, and names one proof: `clave_liquidacion` is an
AEAT-issued identifier that does not appear in the 589 at all, because the
generating heuristic matched identifier SUFFIXES (`_id`, `_ref`, `_code`,
`_key`, `_number`, `_csv`) and a plain Spanish noun carries none.

A suffix-independent sweep now exists (`dev/identifier_noun_census.py`), reading
a field's DOCUMENTATION rather than its name and marking every record with
whether the original heuristic would also have caught it. Against the pinned
tree:

| measure | count |
| --- | --- |
| fields documented as an identifier | 162 |
| of those, annotated bare `str` | 103 |
| **invisible to the suffix heuristic** | **101** |
| invisible AND bare `str` | 69 |

**The second breach.** The AEAT verification-code fields are also invisible to
the original sweep, and for the same class of reason: the field is named exactly
`csv`, and that name does not END in the `_csv` suffix the heuristic matched. So
the generating census missed TWO of the four AEAT-issued concepts this campaign
enrolls by name, not one. This was previously unobserved by any pass.

**No implementation debt follows from it, and that is worth stating explicitly
rather than leaving a reader to assume otherwise.** Both missed concepts were
nevertheless enrolled, because this document's own AEAT-issued taxonomy was
built by reading the surfaces rather than by consuming the suffix census. The
second breach therefore falsifies nothing about the enrollment set and opens no
new row; it sharpens the claim about the INSTRUMENT. The lesson is that the fix
for an instrument-shaped blind spot is a differently-shaped instrument, never a
more careful application of the same one.

**What the 101 is not.** It is a CANDIDATE set carrying a material and named
false-positive rate, not 101 missing enrollments. The Spanish authentication
provider's name matches the *clave* vocabulary; delegated-access prose matches
*identity*; an encryption-algorithm field matches *identifier* incidentally.
Wherever this figure is quoted it travels with the word *candidate*, because
"invisible to the heuristic" reads as "missing" the moment the qualifier is one
document away. Triage to a per-record disposition is a separate plan row and is
deliberately not performed inside the scanner, so that the scanner cannot make
its own false positives invisible.

## The conflation: three call sites, one wrong contract

`Justificante.matches_filing_target` (`domain/justificante/_schema.py`,
signature ~line 103) accepts a `presentation_id: str | None` parameter whose
docstring (~line 118) says a caller "must agree whenever the caller supplies
the corresponding expediente identity" — the contract itself names the wrong
namespace. Every production call site passes an `expediente_id` value into
that parameter:

- `application/live/_filed_observation_persistence.py:453` —
  `presentation_id=observation.expediente_id`
- `application/live/_justificante.py:604` —
  `presentation_id=snapshot.expediente_id`
- `application/live/_justificante.py:682` —
  `presentation_id=snapshot.expediente_id`

(`_justificante.py:785` passes a caller-supplied `presentation_id` through
unchanged — not part of the conflation.) A fourth site,
`register_capture_as_filing_evidence`, additionally runs a genuine
`justificante.csv == snapshot.csv` identity check ahead of the broken
comparison — the one place in the tree that already compares like-for-like.

**This defect and its fix are the fully-scoped subject of a sibling ADR,
`justificante-identity-matching` (`.vault/adr/2026-08-07-justificante-
identity-matching-adr.md`), accepted the same day.** That record: (a) removes
the wrong-namespace argument at the two register-reconciliation sites where
no independently-known receipt-namespace value exists in scope, relying
instead on the pre-existing four-field match plus structural artefact
binding; (b) keeps the subtractive fix at the fourth (already-correct) site;
(c) strengthens `matches_filing_target`'s docstring as an interim, non-type-
level guard; and (d) **explicitly defers, as "Option 4," a typed
`identifier_namespace` marker that would refuse a register-namespace value
passed as `presentation_id` at the type level** — naming it as the future
hardening this reference's taxonomy work is positioned to deliver. This
document's ADR must reference that decision, adopt its Site 1-3 removal as
already-settled, and treat Option 4 as the taxonomy's first concrete
consumer — not restate or re-litigate the removal itself.

## Storage-key surfaces a retype can silently orphan

`adapters/persistence/profile/justificante.py:55-56` —
`extract_identifier()` returns `payload.csv` **verbatim** as the encrypted
secure-object key. Any change to CSV's stored representation (tightening the
pattern, changing the normal form) changes this key and orphans every
already-persisted encrypted justificante record. Two known key-grammar
patterns exist beyond this one: a calculation-observations key that folds in
`member_nif` raw and unhashed, and sibling namespaces elsewhere that hash the
tax id instead. The repository is pre-`RELEASED_FORMAT_FLOORS` checkpoint
(`no-legacy-compatibility`), so a shape change is delete-and-replace rather
than a versioned migration — cheaper to execute, but still destructive to any
already-persisted record if the affected keys are not enumerated per
concept before a retype lands.

## Adjudicated non-identifiers

`Declaracion.estado` and `Deuda.situacion` are AEAT-printed status labels
whose vocabulary the app neither controls nor can enumerate — deliberately
bounded free text, not a closed set and not an identity concept. A blanket
sweep of every name matching an identifier heuristic would catch these; the
ADR must exclude them by name, explicitly, not by silent omission from a
worklist.

## Fixed-width and export surfaces: unresolved constraint

Identifiers reach fichero-BOE byte-exact positions and worksheet exports
(`modelo-export-mirrors-official-structure`). This reference did not sweep
those serialisation sites; a shape change reaching one could produce an
invalid official filing rather than a failed test. Record this as an
unresolved constraint the plan must scope around, not as a cleared surface.

## Known gaps in this census

Registry TOML id-shaped values were not swept. Wire, export, and locale
surfaces are still being swept by a sibling discovery effort
(`inventory-aeat-identifiers`). The 589 bare-`str` identifier-shaped
production fields the coordinating AST census counted were not individually
hand-classified — this reference grounds the four AEAT-issued concepts and
the `core/identity/` extension point in depth; it does not claim the
remaining ~580 fields are triaged.

## Amendment (2026-08-13): the two `Hex16Str` census rows are withdrawn

### What the rows claim

The classification census's app-derived table proposes `Hex16Str` as the
target alias for two names:

| field name | approx. sites | target alias | status |
| --- | --- | --- | --- |
| `short_work_unit_id` | 3 | `Hex16Str` (exists) | per census |
| `short_calculation_revision_id` | 2 | `Hex16Str` (exists) | per census |

**Both target aliases are withdrawn as factually wrong.** `core.Hex16Str`
(`src/cadrumo/core/_hex.py:57-60`) is
`StringConstraints(strip_whitespace=True, min_length=16, max_length=16, pattern=HEX_PATTERN_16)`
— exactly sixteen lowercase hex characters. Every value these fields carry
is **twelve**. The proposal does not narrow the population; it refuses all
of it. The rows above are left in place, and marked in the live table, so
the plan rows and the ADR sentence written from them stay legible.

### Why "per census" cannot support the conclusion it was used for

The status cell on both rows reads **"per census"**, and this document's own
census preamble already declares what that marker means: "Per-name counts
below are attributed to that census as reported and are NOT independently
re-derived here, except where marked 'verified'." Neither row is marked
verified.

That honesty clause was correct and it was ignored downstream. The failure
is not that the census lied — it is that **a census counts SITES and this
row's third column is a WIDTH judgement.** The instrument was an AST pass
over field annotations. It read field names and declared types; it never
read a truncation producer, a runtime value, or a selector pattern, so it
had no access to the one fact the alias choice depends on. `Hex16Str` was
reached for on a resemblance that is real but dimension-blind: its own
docstring calls `HEX_PATTERN_16` "the shape of a TRUNCATED digest used as a
short content address", and this population is exactly that — truncated to
a different width.

**The generalisable form: an unverified COUNT may not be promoted into a
TYPE decision.** A count and a constraint are different claims about a
population, and the marker distinguishing them was already present in this
document.

### The measurement, derived at HEAD for this amendment

`rg` over `src/` at HEAD, tests excluded:

- **Zero sites anywhere in the tree truncate to sixteen.** A tree-wide
  search for a `[-16:]` slice returns nothing.
- **Seven production truncation expressions, every one twelve:**
  `application/workflow/_resume.py:598`;
  `application/modelo/_work_addressing.py:189`, `:233`, `:235`;
  `application/modelo/_selectors.py:237`, `:271`; and
  `entrypoints/cli/_modelo_rendering.py:239`, the `short_id()` helper —
  `return value[-12:] if value else None` — which is the sole truncation
  behind every CLI surface.
- **Twelve is a product decision, not a truncation artefact.**
  `application/modelo/_selectors.py:57-66` declares the operator lookup
  type with `pattern=r"^(?:[0-9a-f]{12}|[0-9a-f]{64})$"`, `min_length=12`,
  `max_length=64` — the alternation backing the CLI's "paste either the
  short id you were shown or the full one" contract. Two gates lock it:
  `application/modelo/tests/test_selectors.py:260` resolves a work unit
  from `unit.work_unit_id[-12:]`, and `:273` — docstring "Mutable work may
  be addressed only by the published 12-char handle or full id" — refuses
  anything shorter. Recorded CLI transcripts under `docs/_sequences/how-to/`
  carry twelve-character values (`af6b2264dd9d`, `2d0933eb70d7`).

### The counts are understated too, and the instrument explains it

**Corrected 2026-08-13 (second amendment): the UNDER-COUNT below is confirmed
and widened, but the MECHANISM this subsection proposes is withdrawn — a
wider sample shows the census does see optional fields. Read the second
amendment before citing the explanation offered here.**

The withdrawal is about the target alias, but the site counts do not
survive re-derivation either. Production annotated sites at HEAD, tests
excluded:

| field name | this census | measured at HEAD | of which bare `str` |
| --- | --- | --- | --- |
| `short_work_unit_id` | 3 | 13 (11 fields + 2 parameters) | 8 |
| `short_calculation_revision_id` | 2 | 4 | 2 |
| `short_current_calculation_revision_id` | absent | 5 | 0 |
| `short_filed_calculation_revision_id` | absent | 5 | 0 |

Two observations, both about the instrument rather than the author:

1. **`short_calculation_revision_id`'s "2" is exactly its bare-`str`
   count**, and the two names this table omits entirely are `str | None` at
   every one of their ten sites. A bare-`str` pass cannot see an optional
   field, and a short form is optional precisely because it is absent until
   a revision is calculated. The
   `2026-08-10-canonical-identifiers-revision-id-adjudication-reference`
   named this same failure independently: "the bare-`str` pass alone would
   have understated Class D by a factor of ten. Optionality is where the
   divergent concepts concentrate."
2. **The table names two of the four field names in this family and covers
   5 of its 27 production sites.** A reader sizing the work from these rows
   under-scopes it fivefold, which is a second, quieter way these rows
   mislead even for someone who has already learned the alias is wrong.

### Where this correction already lives, and where the decision is owed

`2026-08-07-canonical-identifiers-adr`'s Amendment (2026-08-13) withdraws
the ADR sentence these rows produced, and rules that no Step may retype the
short-form population onto `Hex16Str`, `WorkUnitId`,
`CalculationRevisionId`, `RevisionId` or any other existing alias. The
`2026-08-10-canonical-identifiers-revision-id-adjudication-reference`
reached the same disposition three days earlier by measurement, classifying
the short-form sites **Class D — "NOT this taxonomy, must not be
retyped."** Scope note: that reference's population was `revision_id`
sites, so its Class D covers the three short *revision* id names and never
literally adjudicated `short_work_unit_id`; the measurement above governs
both, since both flow through the same `[-12:]` producers and the same
selector.

**The correct disposition is UNDECIDED and is not settled here.** A
reference grounds a decision; it does not make one. The ADR amendment names
three costed options — mint a twelve-character primitive in `core`, leave
the population deliberately bare with the reason recorded, or name the
width once as a constant beside `short_id()` without enrolling a display
form into the taxonomy — and leaves the ruling open. Minting a core
primitive is an architectural act.

The category question that must be answered before any of the three is
chosen, and the reason a future author should not simply reach for a new
primitive on finding this row: **a short display form is a RENDERING of an
identifier, not an identifier any minter issues.** If it is not a namespace
member, minting one is a category error however cleanly it validates — and
this population is then correctly out of scope for a document-identifier
taxonomy, which is what Class D already says.

### The placement lesson, recorded because it is reusable

This error had a three-day life and two documents' worth of reach because
of WHERE its correction sat, not because anyone failed to find it. The
sibling `RegistryRevisionId` reversal in the same Phase was corrected in
the **plan row's own text**, so every reader met the withdrawal before
acting. This one was corrected only in an exec record, which a reader
reaches after acting, and the ADR sentence and these rows stayed clean in
the meantime. That is why the withdrawal is stamped on the live table rows
above and not only in this section: a correction a reader meets after
acting is not a correction.

## Amendment (2026-08-13, second): the count column is not reproducible, and "verified" does not attest it

Written to answer one question: is the under-count found in the short-form
rows a property of that family, or of the instrument that produced every
row? **It is the instrument.** The count column understates every large
family in the sample, without exception.

### Instrument

AST over `git show <rev>:<path>` bytes — the object store, not the working
tree, which carries a large uncommitted registry migration. Class-level
annotated declarations (`AnnAssign` in a `ClassDef` body) in
`src/cadrumo/**`, tests excluded: the model-field methodology this table's
own `bucket_id` row states it uses. Function parameters counted separately
and excluded from the totals below. Measured at `c8066b5f97` (2026-08-07,
the census-era commit) so six days of campaign drift cannot be mistaken for
instrument bias; a HEAD re-run moves no figure enough to change a verdict.

Each site is partitioned into exactly one of: **bare** (annotated `str`,
no `Annotated[...]` and no constraint-bearing `Field(...)` — the "589 bare
`str` with no alias or constraint" enrollment surface this document's
preamble defines), **opt** (`str | None` / `Optional[str]`, likewise
unconstrained), and typed-or-constrained. Total is their sum.

### The sample: 18 families, both tables, both status markers

| family | census says | measured total | bare | opt | census ÷ measured | marker |
| --- | --- | --- | --- | --- | --- | --- |
| `bucket_id` | 24 | **233** | 63 | 9 | 9.7x under | verified |
| `transaction_id` | 30 | **64** | 22 | 0 | 2.1x under | verified |
| `revision_id` | 12 | **45** | 14 | 3 | 3.8x under | verified |
| `invoice_id` | 16 | 21 | 8 | 2 | 1.3x under | verified |
| `expediente_id` | 13 | 17 | 5 | 3 | 1.3x under | verified |
| `bucket_event_id` | 7 | 16 | 3 | 4 | 2.3x under | verified |
| `tax_id` | 6 | 11 | 1 | 2 | 1.8x under | per census |
| `short_work_unit_id` | 3 | 11 | 8 | 3 | 3.7x under | per census |
| `csv` | 5 | 7 | 1 | 1 | 1.4x under | verified |
| `supplier_tax_id` | 6 | 7 | 0 | 6 | 1.2x under | per census |
| `customer_tax_id` | 5 | 6 | 0 | 6 | 1.2x under | per census |
| `display_number` | 5 | 5 | 4 | 0 | exact | per census |
| `party_tax_id` | 4 | 4 | 2 | 0 | exact | per census |
| `counterparty_tax_id` | 2 | 4 | 1 | 0 | 2.0x under | per census |
| `short_calculation_revision_id` | 2 | 4 | 2 | 2 | 2.0x under | per census |
| `official_tipo_renta_code` | 5 | 3 | 1 | 0 | **0.6x OVER** | per census |
| `registry_snapshot_id` | 3 | 3 | 1 | 1 | exact | per census |
| `presentation_id` | 1 | 1 | 0 | 0 | exact | verified |

**Every one of the six families larger than fifteen sites is under-counted**,
by 1.3x to 9.7x, and the error grows with family size. Four figures are
exact, and all four are families of five sites or fewer. One family is
over-counted. Nine of the eighteen match no measured quantity at all — not
the total, not the bare count, not the optional count, not any sum of them.

### Correcting this document's first 2026-08-13 amendment

That amendment proposed a mechanism for the short-form under-count: a
bare-`str` pass cannot see an optional field, so optionality is where the
census goes blind. **This wider sample refutes that mechanism, and it is
withdrawn.** Three disproofs:

- `customer_tax_id` is optional at every one of its six sites and has zero
  bare sites; the census counted 5. `supplier_tax_id` is optional at six of
  seven; the census counted 6. A pass blind to optional fields would have
  reported zero for both.
- `short_work_unit_id`'s census figure of 3 is not its bare count either —
  that is 8. It coincides with its *optional* count, the opposite of the
  proposed mechanism.
- Only one figure in eighteen equals its family's bare-only count, and that
  family (`short_calculation_revision_id`) has bare and optional counts both
  equal to 2, so it discriminates nothing.

**What survives from that amendment is the fact, not the explanation:** the
short-form rows do understate, the table does name two of that family's
four field names, and it does cover 5 of its 27 sites. The claim that
optionality explains it does not survive contact with a wider sample. The
first amendment's subsection now carries a pointer here.

Recorded because it is the same error one level up: **I generalised a
mechanism from a single family without sampling a second one.** The census
promoted an unverified count into a type decision; this amendment's
predecessor promoted a single family's coincidence into a mechanism. Both
are the same move.

### "Verified" attests the name and the file list — never the count

The status column's `verified` marker is the one a reader would trust, and
it does not mean what this document's limitation clause implies. Read the
verified cells: "real file list gathered by grep in ...", "file list spans
...", "`domain/buckets/_event.py:28` aliases `Hex64Str` already", "`sede/_schema.py`
lines 100-135". **Every verified cell attests a LOCATION or a CONCEPT. Not
one attests a count.**

The limitation clause then says "every count not marked 'verified' is
relayed from the coordinating census" — which reads as though the marked
counts were re-derived. They were not, and the measurement shows it: six of
the eight verified rows understate, including the two worst in the sample
(`bucket_id` at 9.7x, `revision_id` at 3.8x). **The marker is not a quality
signal for the count column, and reading it as one is how a sized row
inherits an unmeasured number.**

`bucket_id`'s own cell shows the failure happening in real time. It notices
the discrepancy — "far wider than the census count suggests many sites are
function parameters, not model fields" — and rationalises it instead of
re-deriving it. Model fields alone are 233 against a census 24; parameters
(614 more) are not the explanation, they are a second population entirely.

### Verdict

**The census under-scopes generally. Every row sized from this table needs
its size re-derived before execution.** This is the stronger of the two
possible verdicts and the sample does not support the weaker one: the
under-count is not confined to places where optionality concentrates, it is
present in twelve of eighteen families across both tables and both status
markers, and it is universal among the large families where the absolute
cost of under-scoping is highest.

What remains reliable is narrower and still useful:

- **The SET of names is sound** — this is what the census was actually good
  at, and what the table's own limitation clause claims for it ("this table
  bounds the SET of names and approximate sizes"). The known breaches are
  already recorded above: `clave_liquidacion` is absent because the
  heuristic matched suffixes, and the short-form family is missing two of
  its four names.
- **The concept classification is sound** — AEAT-issued versus app-derived
  versus free-text versus not-an-identifier survives every check made
  against it so far.
- **The COUNT column is not attested anywhere in this document** and should
  be read as an order-of-magnitude hint that is reliably a floor, never a
  scope.
- **The TARGET ALIAS column is a judgement, not a measurement**, and has
  been wrong at least once in a way no count could have caught.

### A third instrument defect: one count can mix two populations

Beside under-counting and the unreliable `verified` marker, a third,
distinct failure surfaced executing `W05.P08.S38`/`S40`
(`registry_snapshot_id`). The row's premise, "3 sites", and the
model-field-only re-derivation's "1 site, already constrained" both
measured correctly — they measured DIFFERENT populations under the SAME
name. The two "missing" sites, `registry_snapshot_id()` and
`registry_snapshot_id_for()` in `_snapshot_coordinate.py`, are plain
function return-type annotations, never pydantic model fields; the
survivor, `sede/_schema.py`'s `FiledDeclaracionObservation
.registry_snapshot_id`, already carried its `Field(min_length=1,
max_length=128)` constraint at HEAD before either row touched it
(confirmed by reading the file before editing). The original census's "3"
silently summed a function-signature population and a model-field
population into one number; the field-only instrument correctly excludes
the former, and neither figure is wrong on its own terms. Reconciling a
census count against a re-derived one must therefore check whether the
two are counting the SAME KIND of site before concluding either is
mistaken — under-counting and mixed-population miscounting look identical
from the row's side and are not the same defect.

A related tooling hazard, worth recording here rather than only where it
was hit: a semicolon embedded in a `vault plan step edit --action` prose
string collides with the plan row grammar's action/scope delimiter. The
write-verification round-trip catches the resulting mismatch and refuses
to commit it, but the first write attempt is not rolled back, leaving a
mangled row on disk that a naive retry compounds rather than fixes. The
reliable fix is passing both `--action` and `--scope` explicitly, with no
embedded semicolons in either string. Hit independently by more than one
agent across this campaign's `W05.P08` rows.

### A fourth instrument defect: a matched name can carry the wrong role

Beside under-counting, the unreliable `verified` marker, and mixed-population
counting, a fourth, distinct failure surfaced executing `W06.P09.S45`
(self/profile-owned `tax_id`). The census matches sites by NAME into a
bucket, and a name match is not a role match: two sites the row's own
re-sizing correctly counted as "`tax_id`, self/profile-owned" turned out,
once traced to their owning class, to carry the WRONG role.
`adapters/inbound/einvoice/_record_batch.py`'s `AeatParty.tax_id` is shared
by both `issuer` and `recipients` on one e-invoice record, so which party is
the filer's own depends on the record's direction
(`AeatRecordFamily.SII_FACTURAS_EMITIDAS` versus `_RECIBIDAS`) — no single
static type is correct for every use of that one field.
`application/ledger/_evidence_draft.py`'s `CounterpartyDraftSide.tax_id` is,
by its own class name, a counterparty concept, and belongs with
`W06.P10`'s `TaxIdIdentityToken` bucket despite carrying none of that
bucket's counterparty-prefixed names and despite living inside the same
census `tax_id` row as the self-owned sites beside it.

This is not under-counting — both sites were counted, at the site the row
named. It is not the mixed-population defect either — both are genuine
model fields, not a function-signature/field conflation. The defect is that
a name-keyed census cannot see role, and neither direction of search
recovers it: searching by name finds the site but assigns it the wrong
bucket, and searching by bucket never reaches a site whose name does not
carry the bucket's vocabulary. Every row this campaign sizes by name alone
carries this same latent risk, proportional to how many distinct semantic
roles share one field name across the tree — the fix is per-site tracing to
the owning class before typing, which this row did and which is now the
standing practice, not a corrected instrument.

### A fifth reason a census cannot decide a type: a diagnostic that reports malformed input cannot itself validate that input

Surfaced across `W04.P06.S29`, `S30`, and `S32`, and distinct from all four
defects above: a field can be a genuine, single-role, correctly-counted
member of its census bucket and STILL be wrong to retype, because its
FUNCTION is to hold a value that failed the very constraint the alias would
enforce.

Three concrete instances, one per file family:
`application/ledger/_models.py`'s `BulkClassifyFailure.transaction_id`
echoes the raw, unvalidated CSV cell text specifically BECAUSE the row
failed to parse — every construction site sits in the failure branch of a
`try`/`except` wrapped around the very validation the alias would apply.
`application/ledger/_preflight.py`'s `LedgerPreflightIssue.transaction_id`
carries the literal sentinel `"__period__"` for a period-level issue with
no associated transaction at all — a second, deliberate non-identity
population sharing the field's name. `domain/invoices/_service.py`'s
`LinkInconsistency.invoice_id` is the sharpest case: the function
(`verify_link_consistency`) exists specifically to detect a transaction
whose `invoice_id` does NOT resolve to a real invoice, so typing the field
would make constructing the diagnostic itself raise on exactly the dangling
reference it was written to report.

`application/aggregation/_iva_ledger.py`'s `IvaLedgerAggregationIssue
.transaction_id` is the same family with an extra piece of evidence worth
keeping: most of its construction sites feed a real transaction, but one
feeds `IvaLedgerCandidate.ledger_id` — a module-private alias with a
looser, non-hex64 bound. The field's OWN existing constraint
(`Field(min_length=1, max_length=128)`) matches that looser alias's bound,
not `TransactionId`'s, which is evidence the field's original author sized
it deliberately to admit both populations. `IvaLedgerCandidate` has zero
production construction sites in `src/` today — only tests — which does
NOT make it dead code: it is a live, wired, exported, tested contract that
would silently narrow the moment it gets a caller, the correct reading of
zero-caller code in this repository rather than a license to ignore it.

This is not role confusion (defect four) — a `transaction_id` field
genuinely names a transaction concept at every one of these sites. The
defect is narrower and sharper: the field's DECLARED shape and its ACTUAL
job are in tension, because part of its job is to represent a value that
fails the shape a name-keyed census would assign it. No census, however
carefully it counts or roles-checks, can see this from the field's name or
even from its single declared type — only tracing every construction site
to see what values ACTUALLY reach the field surfaces it. This generalises:
any "issue", "failure", "inconsistency", "diagnostic", or "exclusion"
record that echoes a caller-supplied or foreign-key value back to the
operator is a candidate for this defect and needs the same trace before
retyping, not an assumption that its field name is safe because the count
says "one role, N sites."

### Mechanical or per-family: the split that decides the cost

**Re-deriving the SIZES is mechanical.** One AST pass over the object store
produces every per-family count, partitioned by bare/optional/typed, in a
single run — the instrument described at the top of this amendment did all
eighteen families at once. This is an afternoon's work for the whole table,
not a campaign, and it needs no judgement because it answers "how many
sites carry this name", which has one correct answer.

**Re-validating the TARGET ALIAS column is per-family judgement and cannot
be mechanised.** The withdrawn `Hex16Str` rows are the proof: no count,
however carefully re-derived, would have caught a sixteen-character
primitive proposed for a twelve-character population. That check requires
reading the producer, the width, and the parse contract for each family —
about thirty-three names across the two tables.

**A third question sits between them and is also judgement: what the family
IS.** `bucket_id`'s 24-versus-233 gap is not a counting error to correct
but a scope decision nobody has made — whether a retype covers the model
fields only, or also the 614 function parameters, and whether the 161
already-typed sites are in or out. A re-derived count makes that decision
visible; it does not make it.

The order follows: re-derive the sizes mechanically first, because it is
cheap and it tells you which families are large enough that the alias
judgement and the scope decision are worth spending on.

### What this amendment does not do

No row is corrected here, no count in the tables above is rewritten, and
the plan is untouched. This is a measurement of the instrument, recorded in
the document whose reliability was in question. The rows keep their figures
so the plan rows sized against them stay legible; a reader is told what
those figures are worth.

The sample is eighteen of the census's roughly thirty-three named families,
chosen to span both tables, both status markers, and the full size range
from one site to 233. It is not the whole table. Six families in the
AEAT-issued table (`clave_liquidacion`, `certificado_id`, `form_number`,
`from_number`, `to_number`, `spouse_tax_id`) and the "not separately
counted" rows carry no census figure to test, and the UNDETERMINED,
NOT_AN_IDENTIFIER and FREE_TEXT buckets were not sampled at all.

### Full mechanical re-derivation: every named family, at HEAD

The sizes above were a sample. This is the whole table — all 32 named
families from both census tables, plus the two short-form names the tables
omit — re-derived at HEAD, because HEAD is what anyone executing a row is
working against. The instrument is embedded at the end of this amendment so
this can be re-run rather than re-trusted.

**Columns.** `fields` is class-level annotated declarations (model fields),
the methodology this table's `bucket_id` cell states it uses. `bare` is
annotated `str` with no `Annotated[...]` and no constraint-bearing
`Field(...)`; `opt` is `str | None` / `Optional[str]` likewise unconstrained;
`typed` is everything already aliased or constrained. **`enrol` = bare + opt
is the only number that sizes work** — the rest is already done. `files`
counts distinct files carrying an enrollment site, not all sites, because
that is the retype's real footprint. `params` counts annotated function
parameters, a separate population the census excludes. `drift` is the
change in `fields` since the census-era commit `c8066b5f97`, so instrument
error and six days of campaign churn stay distinguishable.

| family | census | fields | bare | opt | typed | **enrol** | files | params | drift | executable as one commit? |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| `bucket_id` | 24 | 237 | 64 | 10 | 163 | **74** | 28 | 630 | +4 | **scope decision** |
| `transaction_id` | 30 | 65 | 23 | 0 | 42 | **23** | 10 | 88 | +1 | **scope decision** |
| `revision_id` | 12 | 45 | 0 | 2 | 43 | **2** | 2 | 47 | — | **scope decision** |
| `invoice_id` | 16 | 21 | 8 | 2 | 11 | **10** | 9 | 28 | — | **scope decision** |
| `bucket_event_id` | 7 | 17 | 3 | 4 | 10 | **7** | 3 | 4 | +1 | atomic OK |
| `expediente_id` | 13 | 16 | 4 | 3 | 9 | **7** | 4 | 10 | -1 | atomic OK |
| `tax_id` | 6 | 13 | 1 | 3 | 9 | **4** | 4 | 6 | +2 | atomic OK |
| `short_work_unit_id` | 3 | 11 | 8 | 3 | 0 | **11** | 4 | 2 | — | atomic OK |
| `registry_revision_id` | — | 11 | 0 | 0 | 11 | **0** | 0 | 13 | +5 | **scope decision** |
| `csv` | 5 | 7 | 1 | 0 | 6 | **1** | 1 | 6 | — | atomic OK |
| `supplier_tax_id` | 6 | 6 | 0 | 5 | 1 | **5** | 4 | 0 | -1 | atomic OK |
| `display_number` | 5 | 5 | 4 | 0 | 1 | **4** | 4 | 3 | — | atomic OK |
| `customer_tax_id` | 5 | 5 | 0 | 5 | 0 | **5** | 4 | 0 | -1 | atomic OK |
| `short_current_calculation_revision_id` | **absent** | 5 | 0 | 5 | 0 | **5** | 1 | 0 | — | atomic OK |
| `short_filed_calculation_revision_id` | **absent** | 5 | 0 | 5 | 0 | **5** | 1 | 0 | — | atomic OK |
| `profile_tax_id` | incl. | 4 | 2 | 0 | 2 | **2** | 2 | 3 | — | atomic OK |
| `party_tax_id` | 4 | 4 | 2 | 0 | 2 | **2** | 1 | 1 | — | atomic OK |
| `counterparty_tax_id` | 2 | 4 | 1 | 0 | 3 | **1** | 1 | 5 | — | **scope decision** |
| `short_calculation_revision_id` | 2 | 4 | 2 | 2 | 0 | **4** | 4 | 0 | — | atomic OK |
| `official_tipo_renta_code` | 5 | 3 | 1 | 0 | 2 | **1** | 1 | 0 | — | atomic OK |
| `operation_kind_code` | — | 3 | 0 | 0 | 3 | **0** | 0 | 0 | +1 | nothing to enroll |
| `clave_liquidacion` | 1 | 2 | 1 | 0 | 1 | **1** | 1 | 0 | — | atomic OK |
| `certificado_id` | — | 2 | 1 | 0 | 1 | **1** | 1 | 0 | — | atomic OK |
| `form_number` | — | 2 | 0 | 1 | 1 | **1** | 1 | 8 | — | **scope decision** |
| `from_number` | — | 2 | 2 | 0 | 0 | **2** | 2 | 0 | — | atomic OK |
| `to_number` | — | 2 | 2 | 0 | 0 | **2** | 2 | 0 | — | atomic OK |
| `donor_tax_id` | — | 2 | 1 | 0 | 1 | **1** | 1 | 0 | — | atomic OK |
| `presentation_id` | 1 | 1 | 0 | 0 | 1 | **0** | 0 | 0 | — | nothing to enroll |
| `spouse_tax_id` | — | 1 | 1 | 0 | 0 | **1** | 1 | 0 | — | atomic OK |
| `member_tax_id` | — | 1 | 0 | 0 | 1 | **0** | 0 | 0 | — | nothing to enroll |
| `asset_class_code` | — | 1 | 0 | 0 | 1 | **0** | 0 | 0 | — | nothing to enroll |
| `registry_snapshot_id` | 3 | 1 | 0 | 0 | 1 | **0** | 0 | 0 | -2 | nothing to enroll |
| **total** | | **508** | 132 | 50 | 326 | **182** | | 854 | | |

**The executability column is the one judgement in an otherwise mechanical
table, and its rule is stated so it can be disagreed with:** a family is
*scope decision* when annotated parameters outnumber model fields and number
at least five — the population is then genuinely ambiguous and a ruling, not
a count, is what is missing. It is *nothing to enroll* when no bare or
optional site remains. Otherwise it is *atomic OK* at 15 or fewer enrollment
sites across 8 or fewer files, which is within this repository's own
demonstrated commit sizes, and *split required* beyond that. Change the
thresholds and the last two columns move; the first nine are measurements.

### The headline: the size problem is a scope problem

**No family is too large to retype in one commit. Not one row lands in
"split required".** Every family that looks unmanageable — `bucket_id` at
237 field sites, `transaction_id` at 65 — is unmanageable for a different
reason: its population is dominated by function parameters the census never
counted, and nobody has ruled on whether a retype covers them.

Seven families are in that state, and the stakes vary by two orders of
magnitude:

| family | model fields | parameters | ratio |
| --- | ---: | ---: | ---: |
| `bucket_id` | 237 | **630** | 2.7x |
| `transaction_id` | 65 | 88 | 1.4x |
| `revision_id` | 45 | 47 | 1.0x |
| `invoice_id` | 21 | 28 | 1.3x |
| `registry_revision_id` | 11 | 13 | 1.2x |
| `form_number` | 2 | 8 | 4.0x |
| `counterparty_tax_id` | 4 | 5 | 1.3x |

`bucket_id` is the one that matters: 630 annotated parameters against 237
model fields, and 74 enrollment sites across 28 files even on the
model-field-only reading. Its census figure of 24 is not an under-count to
correct — it is a different question answered. **The ruling owed is what the
family IS**, and only after that does a size mean anything.

### Four rows are sized against a population that no longer exists

The re-derivation found families whose enrollment surface is now empty,
which no count-correction would have surfaced:

- **`registry_revision_id`: 11 sites, every one already `RevisionId`** —
  `application/workflow/_resume.py:242,349,520`,
  `application/modelo/_work_review.py:162,201,254`,
  `application/modelo/_work_addressing.py:91,172,259,353,385,412`. Zero
  enrollment sites. The concept is already carried by the canonical type,
  which is what `W05.P07.S36` ruled. Any row still instructing a new
  `RegistryRevisionId` alias would not merely fragment a canonical type — it
  has nothing left to retype.
- **`registry_snapshot_id`: 1 site, already constrained** —
  `adapters/outbound/aeat/sede/_schema.py:448` carries
  `Field(default=None, min_length=1, max_length=128)`. The census counted 3;
  two are gone and the survivor is off the bare enrollment surface.
- **`presentation_id`: 1 site, already typed** — consistent with the
  parameter removal the ADR's 2026-08-10 amendment records.
- **`revision_id`: 45 field sites, 2 enrollment** — the census's 12 is
  neither the population nor the remaining work; `W05.P07.S36` retyped the
  bare half, and 43 sites are already typed.

**A row sized from a census figure cannot tell the difference between work
outstanding and work completed.** Re-deriving sizes surfaces both, and here
it turned up more finished work than unfinished.

### Drift is small; the divergence is instrument, not churn

Only four families moved at all since the census-era commit, and only one
materially: `registry_revision_id` +5 (typed during the campaign),
`bucket_id` +4 on a base of 237, `tax_id` +2, `registry_snapshot_id` -2.
Twenty-eight families are unchanged. **Six days of active campaign work
moved nine field sites across the whole surface**, against census-versus-
measured gaps of 213 (`bucket_id`), 35 (`transaction_id`) and 33
(`revision_id`). The divergence is the instrument, and the earlier verdict
stands unmodified by measuring at HEAD.

### What the six untested AEAT names cost

`clave_liquidacion` (2 sites, 1 to enroll), `certificado_id` (2, 1),
`form_number` (2, 1 — but 8 parameters, so a scope decision),
`from_number` (2, 2), `to_number` (2, 2), `spouse_tax_id` (1, 1). All tiny,
all atomic, none previously sized. Together they are 11 sites and 8
enrollment sites — the whole group is one commit's worth of work, which is
worth knowing before it is scheduled as six rows.

### Totals, and what they mean for scheduling

**508 model-field sites across the 32 named families. 182 are enrollment
sites; 326 are already typed or constrained. 854 annotated parameters sit
outside the census's methodology entirely.**

Two thirds of the surface is already done. Of the 182 remaining, **74 belong
to `bucket_id` alone** and are blocked behind a scope ruling, and a further
36 belong to the other six scope-decision families. **That leaves 72
enrollment sites across 20 families that are executable today**, every one
of them atomic — small, bounded, and needing only the per-family alias
judgement this amendment deliberately does not attempt.

### The instrument, embedded so it outlives this session

Extract a tree from the object store and walk it — never the live worktree,
which carries peer WIP that would inflate every count:

```
git archive <rev> src/cadrumo | tar -x -C <dir>
python probe.py <dir>/src/cadrumo <name1,name2,...>
```

```python
import ast, sys, json, collections
from pathlib import Path

ROOT, NAMES = Path(sys.argv[1]), sys.argv[2].split(",")
CONSTRAINT_KW = {"min_length", "max_length", "pattern", "gt", "ge", "lt", "le", "max_digits"}
R = {n: collections.Counter() for n in NAMES}
E = {n: set() for n in NAMES}   # files carrying an enrollment site

def constrained(stmt):
    v = stmt.value
    if isinstance(v, ast.Call) and CONSTRAINT_KW & {k.arg for k in v.keywords if k.arg}:
        return True
    return ast.unparse(stmt.annotation).startswith("Annotated[")

for path in ROOT.rglob("*.py"):
    if "tests" in path.parts:
        continue
    try:
        tree = ast.parse(path.read_bytes().decode("utf-8"))
    except (SyntaxError, UnicodeDecodeError):
        continue
    rel = path.relative_to(ROOT).as_posix()
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            for stmt in node.body:
                if not (isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name)):
                    continue
                n = stmt.target.id
                if n not in R:
                    continue
                ann = ast.unparse(stmt.annotation)
                if ann == "str" and not constrained(stmt):
                    R[n]["bare"] += 1; E[n].add(rel)
                elif ann in {"str | None", "Optional[str]"} and not constrained(stmt):
                    R[n]["opt"] += 1; E[n].add(rel)
                else:
                    R[n]["typed"] += 1
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for a in (*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs):
                if a.arg in R and a.annotation is not None:
                    R[a.arg]["param"] += 1

print(json.dumps({n: {"fields": R[n]["bare"] + R[n]["opt"] + R[n]["typed"],
                      "bare": R[n]["bare"], "opt": R[n]["opt"], "typed": R[n]["typed"],
                      "enrol": R[n]["bare"] + R[n]["opt"], "params": R[n]["param"],
                      "files": len(E[n])} for n in NAMES}))
```

Whole tree, both revisions, 32 families: about four seconds. **Re-deriving a
size is cheap enough that citing a stale one is a choice.**

### Bounds of this re-derivation

Sizes only. **No target alias was judged**, and this amendment must not be
read as validating any surviving alias proposal — that check needs the
producer, the width and the parse contract read per family, and the
withdrawn `Hex16Str` rows prove no count substitutes for it. Names come from
the two census tables; a concept declared under a name neither table lists
is invisible here exactly as it was to the original census, and
`clave_liquidacion` is the recorded proof that such names exist. Test files
are excluded throughout, so a retype's test-side cost is not sized. The
UNDETERMINED, NOT_AN_IDENTIFIER and FREE_TEXT buckets are out of scope.

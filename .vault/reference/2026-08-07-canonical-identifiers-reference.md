---
tags:
  - '#reference'
  - '#canonical-identifiers'
date: '2026-08-07'
modified: '2026-08-10'
body_schema: 'body-v1'
body_hash: 'sha256:b7863870b62525d94918df7c43f903d0c780f322231fce34179297ce727585c6'
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
| `short_work_unit_id` | 3 | `Hex16Str` (exists) | per census |
| `short_calculation_revision_id` | 2 | `Hex16Str` (exists) | per census |
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

**Known limitation of this table, stated rather than hidden:** every count
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

---
tags:
  - '#adr'
  - '#canonical-identifiers'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:1e748a06ebbe739447d6b13c725c84b4275deb66e2583e65059b041d6fba5f29'
related:
  - "[[2026-08-07-canonical-identifiers-reference]]"
  - "[[2026-08-07-justificante-identity-matching-adr]]"
---
# `canonical-identifiers` adr: `Canonical AEAT document-identifier taxonomy` | (**status:** `accepted`)

## Problem Statement

`2026-08-07-canonical-identifiers-reference` establishes that this codebase
carries at least four distinct AEAT-issued document-identifier concepts
(CSV, número de justificante, expediente id, clave de liquidación), plus
several app-derived content-addressed identity concepts, with no shared
namespace type anywhere: the same CSV concept is validated at three
divergent strengths across three modules, the same expediente-id concept is
bounded tightly in one schema and almost unbounded in another, and three
production call sites pass an expediente-namespace value into a parameter
`Justificante.matches_filing_target` documents as expecting the receipt's
own namespace. `core/identity/` already exists as the canonical home for
identity concepts and already demonstrates the intended alias-from-one-
primitive pattern (`SnapshotId = Hex64Str`), but two sibling modules
(`domain/modelos/_ids.py`, `domain/invoices/_ids.py`) hand-roll that exact
pattern instead of aliasing it, and none of the four AEAT-issued concepts
has been promoted into the facade at all. A decision is needed on the shape
of a canonical identifier taxonomy — a namespace enum, typed aliases, and a
resolver — that closes the conflation without a big-bang retype of the ~589
bare-`str` identifier-shaped fields the reference's companion census
counted, and without regressing any of the five concrete traps the
reference documents: CSV over-tightening against real receipts, storage-key
orphaning, expediente-id over-tightening against unseen AEAT shapes,
enum-typing deliberately-uncontrolled AEAT status prose, and fixed-width
export byte-shape risk.

## Considerations

- `core/identity/__init__.py` is the sole public facade for identity
  concepts (`BucketId`, `ProfileId`, `SnapshotId`, `TransactionId`,
  `SubjectTaxId`, `TaxIdIdentityToken`, `IdentityDocument`) and its own
  `_hex.py` docstring states the alias-from-one-primitive discipline this
  taxonomy must follow — reference, "The existing canonical home:
  `core/identity/`".
- `domain/modelos/_ids.py` and `domain/invoices/_ids.py` already violate
  that discipline today, functionally identical to `Hex64Str` but declared
  independently — reference, "The pattern already violated".
- Three divergent CSV validation strengths and two divergent normalisation
  forms coexist for one AEAT concept; the loosest (`JustificanteCsv`, no
  pattern) is the one proven to parse real live-captured receipts —
  reference, "The AEAT-issued taxonomy", item 1.
- `expediente_id`'s AEAT-facing bound is explicitly framed in its own module
  comment as an observed range on external, non-app-controlled variability,
  not a closed spec — reference, item 3.
- The storage key for justificante secure objects is the CSV value verbatim;
  any change to CSV's representation orphans persisted encrypted records —
  reference, "Storage-key surfaces a retype can silently orphan".
- The sibling ADR `justificante-identity-matching` already fixed the three
  conflation call sites for today and named a typed `identifier_namespace`
  marker as deferred future hardening ("Option 4") rather than adopting it
  itself, explicitly leaving that hardening to a later record — reference,
  "The conflation: three call sites, one wrong contract"; ADR
  `2026-08-07-justificante-identity-matching-adr`, Considered options §4.
- `Declaracion.estado` and `Deuda.situacion` are AEAT-printed prose this app
  neither controls nor can enumerate; an identifier sweep by name-shape
  heuristic alone would wrongly catch them — reference, "Adjudicated
  non-identifiers".
- NRC has zero Python representation today; enrolling it is new
  capture-and-persist work, not a retype — reference, "The AEAT-issued
  taxonomy", closing paragraph.
- Fixed-width fichero-BOE and worksheet export surfaces were not swept by
  the reference and carry byte-exact-format risk on any serialisation
  change — reference, "Fixed-width and export surfaces".
- 589 bare-`str` identifier-shaped production fields exist per the
  coordinating AST census; none were individually hand-classified — a
  single-commit retype of all of them is not executable, and claiming
  completeness over an unclassified set would itself be dishonest.

## Considered options

1. **A closed `IdentifierNamespace` `StrEnum` in `core/`, one typed alias
   per namespace in `core/identity/`, and a resolver function, with staged
   per-concept enrollment and a ratchet gate (chosen).** Each AEAT-issued
   and app-derived identifier concept gets its own namespace member and its
   own `Annotated[str, ...]` alias carrying that member's constraint shape;
   a `resolve_identifier_namespace(value) -> frozenset[IdentifierNamespace]`
   function reports every namespace a bare value's shape is *consistent
   with*, explicitly not a single verdict where two namespaces' formats
   overlap. Enrollment lands namespace-by-namespace, each stage atomic
   across its own consumers per the relocation-atomicity rule. A structural
   test fails whenever a new bare-`str` field is added whose name matches
   the enum's namespace-name vocabulary and is not aliased to a typed
   member — gating the *property* (new identifier-shaped field, not
   enrolled) rather than a field count.
2. **A single generic `TypedIdentifier[NamespaceLiteral]` wrapper class
   carrying both the value and its namespace as one runtime object,
   replacing every `str`-typed identifier field.** Rejected: it changes the
   wire shape of every persisted and CLI-emitted identifier field
   simultaneously (a `str` becomes a two-field object), which is exactly
   the big-bang retype the problem statement rules out, and it does not
   compose with pydantic `StringConstraints`-based validation the codebase
   already uses uniformly for constrained strings — it would introduce a
   second constrained-string mechanism alongside the existing one.
3. **Tighten every namespace to one canonical pattern immediately, matching
   the strictest observed shape (e.g. `is_aeat_csv`'s 8-32 uppercase for
   CSV).** Rejected outright: the reference proves the loosest CSV type is
   the one that actually parses real captured receipts, and `expediente_id`'s
   own module comment frames its bound as observed-not-closed; tightening
   either without new evidence risks rejecting real AEAT-issued documents,
   which is a worse failure than a diagnosed conflation.
4. **A namespace-value-only resolver with no per-namespace type distinction
   (values self-report their namespace by shape).** Rejected: CSV,
   expediente id, and other namespaces have overlapping length/character
   shapes, so shape-only inference is provably ambiguous for at least one
   pair in the taxonomy; a resolver promising a single verdict where the
   shapes overlap would silently mis-resolve. The type itself must carry
   its namespace at any call site where disambiguation matters; the
   resolver's contract is downgraded accordingly (see Implementation).
5. **Defer the whole taxonomy until every consuming surface (registry TOML,
   export, fixed-width, locale) is fully swept.** Rejected: the reference
   already grounds four concrete AEAT-issued concepts and one live
   conflation with a fix depending on this exact hardening (the sibling
   ADR's Option 4); waiting for a complete census before typing anything
   already-grounded leaves the conflation risk open indefinitely for no
   safety gained, and the plan can stage remaining surfaces explicitly as
   known-incomplete rather than blocking on them.

## Constraints

- No production code changes land from this record; it is followed by a
  plan executed under its own gated Steps.
- No legal-catalogue entries are touched; this is a pure identifier-typing
  decision with no BOE/AEAT legal-provenance implication.
- The sibling ADR `justificante-identity-matching`'s Site 1-3 call-site
  removal is adopted as already-settled; this record does not restate or
  re-decide it. This record's implementing plan supplies that sibling
  ADR's deferred "Option 4" — the typed namespace marker — as a later,
  separate Step, not a rollback of the sibling's subtractive fix.
- Any persisted-field retype requires a strict roundtrip test with every
  defaultable field populated non-default, plus an anti-tautology proof
  (corrupt the on-disk value, assert refusal), per the quality-gates rule.
- CSV's stored representation (pattern, normalisation form) MUST NOT change
  in the same Step that promotes it into `core/identity/`; a representation
  change is a separate, evidence-gated Step per Consideration on real-receipt
  parsing and storage-key orphaning.
- `Declaracion.estado` and `Deuda.situacion` are explicitly excluded from
  enrollment; the plan must name them as excluded, not omit them silently.
- NRC and clave de liquidación are explicitly scoped: NRC enrollment is new
  capture-and-persist work and is OUT of this taxonomy's initial scope;
  clave de liquidación IS in scope as a fourth AEAT-issued namespace member
  with a typed alias, since it already has a field to retype
  (`Deuda.clave_liquidacion`).
- Fixed-width fichero-BOE and worksheet export serialisation sites are
  OUT of scope for this taxonomy's initial enrollment; the plan records
  them as a deferred follow-up, not a cleared surface.
- Registry TOML id-shaped values, wire/export/locale surfaces, and the
  589-field census's remaining unclassified fields are OUT of scope for
  complete enrollment; the plan enrolls named concepts only and states this
  gap explicitly rather than implying completeness.

## Implementation

**Namespace enum.** `core/identity/_namespace.py` (new module, re-exported
from the facade) declares:

```python
class IdentifierNamespace(StrEnum):
    AEAT_CSV = "aeat_csv"
    AEAT_PRESENTATION_ID = "aeat_presentation_id"
    AEAT_EXPEDIENTE_ID = "aeat_expediente_id"
    AEAT_CLAVE_LIQUIDACION = "aeat_clave_liquidacion"
    APP_SNAPSHOT_ID = "app_snapshot_id"
    APP_TRANSACTION_ID = "app_transaction_id"
    APP_WORK_UNIT_ID = "app_work_unit_id"
    APP_CALCULATION_REVISION_ID = "app_calculation_revision_id"
    APP_FILING_RECORD_ID = "app_filing_record_id"
    APP_VERIFICATION_REPORT_ID = "app_verification_report_id"
    APP_INVOICE_ID = "app_invoice_id"
```

split explicitly into an `AEAT_*` group (AEAT-issued, external, never
clock-derived, shape bounded by observed AEAT behaviour rather than app
choice) and an `APP_*` group (app-derived, content-addressed or otherwise
minted by this app, clock-free per the standing CLI-contract identity rule).
The two groups are never merged into one member and the enum's own
docstring states the distinction, so a future author cannot accidentally
type an app-derived id as AEAT-issued or vice versa.

**Typed aliases**, each declared once in `core/identity/`, assigned FROM the
shared primitive matching its shape (never a re-declared
`StringConstraints(...)` call, per the existing `Hex64Str` discipline):

- `SnapshotId`, `TransactionId` — already exist, unchanged.
- `WorkUnitId`, `CalculationRevisionId`, `FilingRecordId`,
  `VerificationReportId` — relocated from `domain/modelos/_ids.py` into
  `core/identity/`, re-aliased FROM `Hex64Str` (deletes the duplicate
  pattern declaration; no shape change, so no roundtrip risk).
- `InvoiceId` — relocated from `domain/invoices/_ids.py` the same way.
- `AeatCsv` — a **new, distinctly-named** alias, NOT a retype of
  `JustificanteCsv` or `is_aeat_csv`'s pattern in place. Its initial shape
  is decided empirically per the Constraint above (evidence-gated Step),
  not assumed in this record.
- `AeatPresentationId`, `AeatExpedienteId`, `AeatClaveLiquidacion` — new
  aliases, each keeping its already-registry-observed bound
  (`expediente_id`: 12-32 plus the AEAT shape pattern, taken from the
  tighter `sede/_schema.py` definition, never the looser
  `iva_compensation` one — the tighter bound is evidence-grounded, the
  looser one is the defect this taxonomy corrects).

**Resolver**, honest about its limit per rejected Option 4:

```python
def resolve_identifier_namespace(value: str) -> frozenset[IdentifierNamespace]:
    """Return every namespace whose shape `value` is consistent with.

    Shape-only resolution is ambiguous wherever two namespaces' formats
    overlap (documented per-pair in this function's body). A caller that
    needs a single verdict must hold the value in a namespace-typed field,
    never infer the namespace from the value alone.
    """
```

The function returns a set, and its docstring is the durable, load-bearing
statement of that ambiguity — it does not promise disambiguation shape-only
resolution cannot deliver.

**Staged enrollment**, one committed Step per concept, atomic across that
concept's own consumers (relocation rule):

1. Relocate `WorkUnitId`/`CalculationRevisionId`/`FilingRecordId`/
   `VerificationReportId` and `InvoiceId` into `core/identity/`, aliased
   from `Hex64Str`, deleting the two duplicate `_ids.py` pattern
   declarations. No persisted-shape change; still requires the roundtrip
   regression suite to stay green as the anti-regression proof.
2. Introduce `IdentifierNamespace` and the AEAT-issued aliases
   (`AeatExpedienteId`, `AeatClaveLiquidacion`, `AeatPresentationId`) at
   their current, already-evidenced bounds; retype the 11
   `sede/_schema.py` expediente-id fields and `Deuda.clave_liquidacion`.
   Retype `iva_compensation/_carry_forward.py`'s
   `PeriodComplianceState.expediente_id` onto the SAME tighter
   `AeatExpedienteId` alias, closing that specific divergence — with a
   strict roundtrip proving the tighter bound still accepts every
   already-observed persisted value.
3. Decide CSV's canonical shape empirically (replay the two real captured
   receipt fixtures already in the corpus against candidate patterns before
   choosing one), THEN introduce `AeatCsv`, retype `JustificanteRef.csv`,
   `JustificanteCsv`, and the bare-`str` CSV sites together, and reconcile
   the two normalisation forms (`.strip().upper()` vs `.casefold()`) to
   one. Enumerate every storage key derived from CSV
   (`adapters/persistence/profile/justificante.py:55-56` at minimum) before
   this Step lands, and confirm each either survives the chosen shape
   unchanged or is deliberately migrated under the pre-checkpoint
   delete-and-replace posture.
4. Land `resolve_identifier_namespace` and enroll it as the sibling ADR's
   deferred Option 4: `matches_filing_target`'s `presentation_id` parameter
   becomes typed `AeatPresentationId | AeatCsv | None` rather than bare
   `str | None`, so a caller passing an `AeatExpedienteId`-typed value
   fails at the type-checker boundary instead of only by docstring
   discipline.
5. Land the ratchet gate (see below) LAST, after Steps 1-4 establish the
   enrolled baseline it measures against, so it does not immediately red
   on the plan's own remaining known gaps.

Concepts explicitly OUT of this taxonomy's staged enrollment: NRC (no
existing field), fixed-width/export serialisation sites, registry TOML,
locale/wire surfaces, and the unclassified remainder of the 589-field
census. The plan records these as named follow-ups, never as silently
cleared.

**Ratchet gate.** A structural test enumerates every pydantic `BaseModel`
field in production code whose name matches the namespace vocabulary
(`*_csv`, `*_expediente_id`, `*_presentation_id`, `*_clave_liquidacion`,
plus the existing AST census's broader identifier-name heuristic) and
asserts each is annotated with one of the `core/identity/` namespace
aliases rather than a bare `str`. It is keyed by the *property* — "an
identifier-shaped field must carry a namespace alias" — never by an exact
field count, so it continues to catch a newly-added conflated field after
this plan closes rather than going stale the moment the enrolled count
changes. `Declaracion.estado` and `Deuda.situacion` are the named,
documented exclusions (adjudicated non-identifiers, not identifier-shaped
by the app's own vocabulary despite superficially matching a naive
name-shape sweep). The gate's own bite is proven by a deliberate mutation
(add a throwaway bare-`str` field named `test_expediente_id` to a scratch
model outside `src`, confirm the gate reds, remove it) before the gate is
trusted — a green run after a mutation that missed the target proves
nothing, per the standing gate-discipline rule.

## Rationale

Option 1 wins because it is the only option that closes the conflation
without either a big-bang retype (ruled out by the 589-field surface and the
relocation-atomicity rule, which forbids splitting one symbol's move from
its consumer sweep) or a false disambiguation promise (ruled out by the
CSV/expediente-id overlap the reference documents). Option 2's wrapper class
was rejected because it changes wire shape everywhere at once, which is
strictly worse than staged `Annotated[str, ...]` aliases that preserve the
existing wire shape while adding the namespace constraint — the wrapper
buys nothing the enum-plus-alias pattern does not already deliver, at a much
higher blast radius. Option 3 (immediate tightening) was rejected on direct
evidence: the reference shows the loosest CSV type is the one proven against
real receipts, so tightening first and asking questions later inverts the
correct order — evidence must precede constraint, not the reverse, matching
`no-silent-under-declaration`'s standing instruction that a restrictive
provision used as a default silently captures a population the limiting
rule does not govern. Option 4's shape-only resolver was rejected as
promising more than shape can deliver; adopting the honest degraded
contract (a set, not a verdict) inside Option 1 gets the resolver the
operator asked for without overclaiming. Option 5 (defer entirely) was
rejected because the sibling ADR's own deferred Option 4 is a concrete,
already-identified consumer of exactly this hardening — deferring the
whole taxonomy would leave that named future hardening permanently
unaddressed while the conflation stays live wherever a future caller adds a
new call site.

## Consequences

**Gains:** `core/identity/` stops being under-populated relative to its own
docstring's ambition; the two duplicate hex-64 declarations collapse to one
primitive; the sede/iva_compensation expediente-id divergence closes under
one bound; `matches_filing_target` gains the type-level guard its own
sibling ADR named as future work, without touching that ADR's already-
accepted subtractive fix; a ratchet gate keeps the enrollment from silently
decaying as the codebase grows past this plan's closing commit; the storage
layer's key-composition inconsistency (raw versus pre-hashed PII fold-ins)
gets a deliberate, recorded answer instead of an unexplained split; and the
MCP `output_schema` surface starts advertising real shape constraints to
every consuming agent instead of bare `"string"`, once pinned.

**Cost, named rather than discovered later:** discarding and re-deriving
Cadrumo's own profile database (where a namespace's storage shape changes)
destroys the real Cl@ve-authenticated captures — filings, justificante
artefacts, an IVA-wallet observation — already sitting in that profile.
Re-acquiring them requires the operator to re-authenticate with Cl@ve Móvil
on their own phone; this is a human step the plan must call out as an
OPERATOR action, never something an agent automates or works around.

**Difficulties:** staged enrollment means the taxonomy is genuinely
incomplete at every point before the last Step lands — a reader consulting
`core/identity/` mid-plan sees a partial namespace set, which must be
stated plainly in the plan's own status rather than presented as done. The
CSV empirical-decision Step (3) blocks on real-fixture replay before any
CSV code lands, which is slower than retyping immediately but is the
directly evidence-driven trade the reference's real-receipt finding
demands.

**Pathway opened:** once `IdentifierNamespace` exists, a future NRC capture
feature has a namespace member and alias pattern ready to adopt rather than
inventing one from scratch; the same is true for any future AEAT-issued
identifier this campaign has not yet observed.

**Pitfall guarded against:** a future author adding a new identifier-shaped
field as bare `str` reds the ratchet gate immediately, rather than silently
compounding the 589-field surface this record already treats as too large
to retype in one pass. A future author re-conflating a namespace at a new
`matches_filing_target`-shaped call site is caught at the type checker
once Step 4 lands, closing the exact recurrence the sibling ADR's docstring-
only guard could not.

## Amendment (2026-08-07): schema-rewrite authorisation, wire measurement, and refined census

Landed same-day, before any implementing Step started, on new operator
authorisation and two completed measurement passes (a wire/MCP census and a
full classification of the 589-field surface). No Step from the original
Implementation section had executed, so this amends the same record rather
than opening a second one.

### Operator authorisation and its exact bound

The operator has authorised discarding and re-deriving Cadrumo's OWN
persisted data — the encrypted secure-object stores and profile databases —
where the correct identifier design differs from the current stored shape.
**This authorisation is bounded to Cadrumo's own data only**: it does not
extend to the operating system, the OS keychain, any path outside the app's
own data directory, or any other repository. And it is bounded to
MECHANISM: "discard the data" means routing through the application's own
teardown and re-provisioning authority — `start_config_reset` /
`resume_config_reset` (`application/config_reset.py`) and
`BucketMaintenanceService.delete` (`application/bucket_maintenance/_service.py`)
are the existing sanctioned authorities and this taxonomy work extends them,
never a second teardown path. **A recursive force delete of any directory
remains prohibited with no exception**; a plan row needing records removed
names the bounded target and the app's own path, never a filesystem-level
delete, and never mutates an OS keychain entry.

This releases the storage-key-orphaning trap the original Implementation
section treated as blocking (`W02.P03.S12`'s enumeration is now informational
for the redesign, not a gate on it): **object key composition may now be
DESIGNED CORRECTLY rather than preserved.** The canonical authority for key
composition is `SecureObjectNamespaceDefinition.object_key_grammar` in
`adapters/persistence/storage/_namespace_registry.py` — every namespace's
grammar is declared there, and this taxonomy work extends that one registry
rather than introducing a second key-composition path. The registry already
shows the exact inconsistency to settle deliberately: one namespace's
grammar folds `{member_nif}` raw (`_namespace_registry.py` line 397) while
sibling namespaces fold `{sha256(perceptor_nif)}` / `{sha256(perceptor_tax_id)}`
(lines 417, 431). The underlying SQL `object_key` column is itself a
`HashedLookup` (deterministic HMAC-SHA256 under a master-key-derived
sub-key) applied to the grammar's rendered string before it reaches the row,
so plaintext was never recoverable from a key either way — this is an
unexplained layering inconsistency to resolve once, not an exposure to
remediate. The resolution (uniform pre-hash of PII-shaped fold-ins, or a
documented reason some grammars carry the value raw beneath the outer hash)
is a Constraint below, decided by the plan's key-composition Step rather
than assumed here.

**One real cost, to record rather than discover later:** a live
Cl@ve-authenticated smoke test already captured real filings, justificante
artefacts, and an IVA-wallet observation into the profile this teardown
would discard. Re-acquiring them is a human step — the operator
re-authenticating with Cl@ve Móvil on their phone — not an automated
re-run. Recorded in Consequences.

### The retype is an external contract change (MCP), not merely internal

A completed wire census establishes that `entrypoints/mcp/_tools.py`
generates every advertised MCP tool `output_schema` by calling
`model_json_schema()` on the SAME registered `OutputSchema` classes the CLI
JSON envelope uses — there is no separate hand-maintained MCP schema.
`Field`/`Annotated` constraints (`pattern`, `minLength`, `maxLength`) render
as real JSON Schema keywords in what is advertised to every MCP client. The
existing `test_json_schema_conformance.py` gate is, in its own words, a
"structural-shape gate, not a value gate" — it asserts schema KEY parity
against the Typer command tree, never per-field type or constraint content,
so a retype (looser or stricter) passes that gate silently either direction
with no other coverage found in the CLI or MCP test trees. **This taxonomy
enrollment therefore changes a published external contract**, and the ADR
records that as fact rather than treating enrollment as a pure internal
refactor. Read positively: advertising a real `pattern` teaches every MCP
client the identifier's actual shape instead of "string" — a genuine
improvement, contingent on it being deliberate and pinned (Implementation,
golden-schema Step).

### The 589-field denominator refined, and shown to be a floor

A full classification of the 589-field surface splits it: **302 fields are
APP-DERIVED** and need only mechanical adoption of aliases that ALREADY
EXIST elsewhere in the tree (`TransactionId`, `BucketId`, `InvoiceId`, and
`BucketEventId` — the last confirmed declared as `Hex64Str` in
`domain/buckets/_event.py` and already consumed at several call sites, so
its pattern is proof this alias-adoption tranche is mechanical, not
speculative). **62 fields across 24 names are genuinely AEAT-issued** and
need new namespace types. The remainder splits into 128 undetermined, 72
non-identifiers, and 25 deliberately free text.

**The 589 count is a FLOOR, not a ceiling — confirmed, not merely
suspected.** `clave_liquidacion` (already a named namespace in this ADR's
original Implementation) does not appear in the 589 at all: the AST
heuristic matched identifier-suffix patterns (`_id`, `_ref`, `_code`,
`_key`, `_number`, `_csv`) and `clave_liquidacion` is a plain Spanish noun
with no such suffix, yet its docstring is unambiguously AEAT-issued
identifier prose. A second-pass sweep on a noun-vocabulary heuristic
(`identificador`, `clave`, `número`, `referencia` in field docstrings,
independent of suffix) is therefore a required plan row, not optional
polish — enrolling exactly 589 and calling the surface closed would
reproduce the exact "artefact present, work absent" failure this campaign
is designed to avoid.

**Two traps in the app-derived tranche that a blanket rule would mis-type:**

- **`revision_id` (12 bare sites) is itself a live multi-namespace
  conflation.** `registry_snapshot_id_for()`'s own signature shows
  `revision_id: str` there means the REGISTRY `ModeloRevision.id` — a short
  human-authored version tag — never the hex-64
  `CalculationRevisionId` this ADR's Wave `W01` relocates. The twelve sites
  need per-site adjudication against their actual producer, never a
  blanket "alias every `revision_id` to `CalculationRevisionId`" rule; that
  blanket rule would silently coerce registry and profile-snapshot
  revisions into the wrong namespace, which is a worse regression than
  leaving them bare `str` a while longer.
- **Truncated display ids are not their full-length counterparts.**
  `short_work_unit_id` (3 sites) and `short_calculation_revision_id` (2
  sites) are truncated DISPLAY forms; typing them as `WorkUnitId` /
  `CalculationRevisionId` would reject real data immediately. The existing
  `core._hex.Hex16Str` (already declared, already used for
  `ModeloDraftContentAddress` in `domain/filing/_schema.py`) is the correct
  alias — no new primitive needed.

### Additional namespaces surfaced

**App-derived, no existing alias:** `registry_snapshot_id` (3 sites) is a
composite `modelo:revision_id:filing_year:period` string — explicitly NOT
`core.identity.SnapshotId`, whose own docstring disclaims non-hex minters
(reference, `core/identity/__init__.py` lines 73-76). `registry_revision_id`
is the human-authored registry version tag from the previous paragraph.
Both need their own new `IdentifierNamespace` members and aliases; neither
is hex-64-shaped so neither can alias `Hex64Str` or `Hex16Str`.

**AEAT-issued, new:** `certificado_id` on `RemoteNotification` (docstring:
"Nº de certificado, 13-digit or longer"); AEAT-printed box/form numbers
(`display_number`, `form_number`, `from_number`, `to_number`) which are
distinct from the registry's own `CasillaId` concept and must not be
conflated with it.

**Closed-set codes, StrEnum rather than identifier namespace, per the
typed-constant-axis rule:** M210's `official_tipo_renta_code` (5 sites) and
M720's `operation_kind_code` / `asset_class_code`. These are NOT part of
the `IdentifierNamespace` taxonomy — they are closed AEAT-published
vocabularies and belong in `core/` as `StrEnum`s. The plan must first check
whether the M210 catalogue is already enumerated in registry TOML and
locate it there rather than re-declaring the values in Python if so.

### Tax-identity split, decided here

27 tax-identity-shaped sites split by whose identity they carry, and this
ADR decides the split explicitly rather than leaving it as an open note:
**self/profile-owned fields** (`tax_id`, `profile_tax_id`, `spouse_tax_id`)
are `SubjectTaxId` — checksum-enforced, Spanish-NIF-shaped, because the
filer and their declared family members are presumptively Spanish tax
subjects. **Counterparty-facing fields** (`supplier_tax_id`,
`customer_tax_id`, `party_tax_id`, `counterparty_tax_id`, `donor_tax_id`,
`member_tax_id`) are `TaxIdIdentityToken` — checksum-free, because the
bearer may be a non-resident counterparty. Both types already exist in
`core/identity` and neither is used at any of the 27 sites today. Getting
this split backwards would either reject a legitimate foreign counterparty
(over-applying `SubjectTaxId`) or stop validating the filer's own NIF
(over-applying `TaxIdIdentityToken`); the plan enrolls the two groups as
separate Steps so a reviewer can check the split per site.

### Free text is three distinct sub-populations, not one

Conflating them would misrepresent all three, so the taxonomy names them
separately and enrolls none of them as `IdentifierNamespace` members:

1. **AEAT-bounded prose this app neither controls nor can enumerate**
   (`Declaracion.estado`, `Deuda.situacion`) — unchanged from the original
   Implementation; still explicitly excluded.
2. **Counterparty-issued document numbers** (`invoice_number`) — free text
   the app cannot enumerate because a third party mints it, but NOT
   AEAT-controlled prose; distinct category from (1).
3. **Externally-controlled identifiers from non-AEAT issuing authorities**
   — Google (`file_id`, `spreadsheet_id`, `folder_id`), PKI (`serial_number`,
   an X.509 certificate serial), `spdx_id`, and possibly `finca_identifier`
   (a Catastro referencia catastral, a THIRD external authority, not yet
   confirmed). None of these are AEAT's namespace; none belong in
   `IdentifierNamespace`'s `AEAT_*` group. If any warrant typing at all, it
   is a separate, explicitly out-of-scope decision for a future record.

### Confirmed-clean surfaces (drop from constraint list)

Worksheet and Sheets export carries no identifier cells at all — the
calc-sheet transport exports casilla numbers and formulas, not taxpayer
identity — so a retype cannot reach it structurally; the export constraint
from the original Constraints section is narrowed to fixed-width
fichero-BOE only. The locale catalogues are clean: every tax-id reference
found is prose ABOUT an identifier, never a format declaration. `src/cadrumo/llm/`
is confirmed well-governed, not a leak: LLM-extracted identifiers land in
an unvalidated draft model first, `_agreed_counterparty_tax_id()` REFUSES
confirmation when operator-supplied and extracted NIFs disagree, and the
persisted path runs `validate_spanish_tax_id()` / `validate_iva_number()`
before anything is written — a deliberate two-stage design, not a defect to
enroll.

### Still unsettled, unchanged by this amendment

CSV's canonical shape remains empirically open (Constraints, unchanged) —
and now carries higher stakes: the sibling `justificante-identity-matching`
campaign's correct fix for its own open defect (two filings can exist per
period; the current fix has no way to pick the right one's receipt) depends
on a cotejo-derived CSV field this taxonomy's CSV type gates. The CSV Phase
(`W02.P03` in the plan) is reprioritised ahead of namespace work that does
not block a live defect fix, without changing its evidence-first order
internally. `expediente_id`'s pattern stays permissive by design. `Declaracion.estado`
and `Deuda.situacion` stay un-enumed. Fixed-width fichero-BOE tax-id width
is explicitly OUT of scope: a separate investigation found the Modelo 200
anomaly is a content-misattribution defect (the filer's own NIF bound into
a slot AEAT reserves for a group parent's foreign TIN), not a width
question, and it is getting its own ADR — this record's plan must not touch
`profile_tax_id` width. Registry TOML is architecturally clean (no AEAT
runtime identifier lives in compile-time TOML) but has no measured
denominator equivalent to the Python census; stated as a constraint, not
assumed complete.

### Constraints added by this amendment

- Any row discarding or re-deriving Cadrumo's own persisted records MUST
  name the bounded target and route through `start_config_reset` /
  `resume_config_reset` or `BucketMaintenanceService.delete`, never a
  filesystem-level recursive delete and never a new teardown path.
- No row may mutate an OS keychain entry; a re-login or re-provisioning
  consequence is recorded as a human OPERATOR step, never automated.
- Every identifier-bearing `OutputSchema` class touched by enrollment gets
  a golden-schema pinning test capturing its advertised `model_json_schema()`
  output (both the CLI envelope and, where the class backs an MCP tool, the
  MCP `output_schema`) before and after the retype, so a constraint change
  is a visible, reviewed diff.
- `revision_id` sites are adjudicated per-site against their producer
  before any alias is applied; no blanket `revision_id -> CalculationRevisionId`
  rule.
- Truncated display ids alias `Hex16Str`, never a full-length alias.
- M210 `official_tipo_renta_code` and M720 `operation_kind_code` /
  `asset_class_code` are StrEnums in `core/`, checked against registry TOML
  for an existing catalogue first, never `IdentifierNamespace` members.
- The object-key-grammar pre-hash inconsistency is resolved once, in
  `_namespace_registry.py`, with the reason recorded in that Step's record;
  it is not silently left split.
- A second-pass sweep on a suffix-independent noun heuristic runs before
  the ratchet gate is considered to describe the full surface; the ratchet
  gate itself still gates on the property, not a count, per the original
  Implementation.

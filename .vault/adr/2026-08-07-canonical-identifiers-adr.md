---
tags:
  - '#adr'
  - '#canonical-identifiers'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:d8c9b376e826ca763d1765189911aac35ae77db443a7a382cab3e2c38b674d23'
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
accepted subtractive fix; and a ratchet gate keeps the enrollment from
silently decaying as the codebase grows past this plan's closing commit.

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

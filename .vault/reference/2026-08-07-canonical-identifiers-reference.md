---
tags:
  - '#reference'
  - '#canonical-identifiers'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:11a602c4ff4a1225bc1993eb055ddc8bd425c718352cca1fc2887d41c8183d92'
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

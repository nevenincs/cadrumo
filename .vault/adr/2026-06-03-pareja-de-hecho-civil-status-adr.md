---
tags:
  - '#adr'
  - '#pareja-de-hecho-civil-status'
date: '2026-06-03'
modified: '2026-06-03'
related:
  - "[[2026-06-03-pareja-de-hecho-civil-status-research]]"
  - "[[2026-05-26-cross-domain-continuity-plan]]"
---

# `pareja-de-hecho-civil-status` adr: `Separate pareja_de_hecho_registration record` | (**status:** `accepted`)

## Problem Statement

R9-ANDREA-HIGH testimonial (#627 W09.P41.S346) requires the
profile schema to carry the operator's pareja-de-hecho registration
state so the M100 unidad-familiar surface and per-CCAA deducciones
autonómicas can route correctly. The naive design — adding a fifth
value `PAREJA_DE_HECHO_REGISTRADA` to `RentaMaritalStatus` — is
forbidden because the AEAT `tipo_EstadoCivil` field is a 4-value
closed code (1/2/3/4) and emitting a fifth value breaks the AEAT
PADRE parser.

The codebase already carries `SituacionFamiliar` (LIRPF Art. 82
unidad-familiar domain enum) with `PAREJA_HECHO_REGISTRADA` and
`PAREJA_HECHO_NO_REGISTRADA` members. The wiring gap is at the
SCHEMA side: no profile fact produces a `SituacionFamiliar` value.

## Considerations

Three design options were evaluated in the research doc:

1. **Extend `RentaMaritalStatus` with a fifth value.** Rejected on
   AEAT-fidelity grounds: the wire value would be rejected by the
   AEAT PADRE parser.
2. **Reuse `SituacionFamiliar` directly as the profile fact.**
   Rejected because the CCAA-specific deducciones need structured
   data the enum cannot carry: `ccaa`, `registration_date`,
   `partner_nif`, `registry_name`. A single enum bit cannot satisfy
   the per-CCAA deduction routing.
3. **Author a separate `pareja_de_hecho` profile section.**
   Accepted. Keeps `RentaMaritalStatus` fidelity-true to AEAT;
   carries CCAA-structured data; derives `SituacionFamiliar` at the
   binding-resolver layer.

## Constraints

The new section MUST live alongside `renta_spouse`, not inside it
— a pareja-de-hecho registration is operator-recorded structured
data with its own legal grounding, not a sub-field of the
marriage record. The section is `effective_dated = true` because
the registration status can change over the filing year.

The cross-validation rules MUST refuse the
married-AND-registered-elsewhere case (Art. 234-2.b CCCat /
Art. 1.2 of every autonomic law). The verify-gate ADVISORY for
non-deduction-bearing CCAA registration MUST NOT silently drop;
the operator should see they registered in a jurisdiction that
does not surface a CCAA-specific deduction.

The implementation MUST NOT add a new enum to `RentaMaritalStatus`.
The existing 4-value enum stays the wire contract; the derived
`SituacionFamiliar` is computed at binding-resolution time from
the `(marital_status, pareja_de_hecho.registered)` pair.

## Implementation

The schema author adds the following to
`src/aeat/_data/registry/aeat/user_profile/schema.toml`:

```toml
[[sections]]
key = "pareja_de_hecho"
sensitivity = "identity"
effective_dated = true
description = "Pareja-de-hecho registration state for CCAA-specific
deducciones autonómicas and unidad-familiar conjunta eligibility."

[[sections.fields]]
key = "registered"
type = "boolean"
required = false
description = "True iff the couple is inscribed in an autonomic /
municipal pareja-de-hecho registry."

[[sections.fields]]
key = "ccaa"
type = "enum"
required = false
description = "Autonomous community whose registry holds the
inscription. Drives the per-CCAA deducción routing."
enum_values = ["..."]  # mirror tax_residence.ccaa

[[sections.fields]]
key = "registration_date"
type = "date"
required = false
description = "Date the couple was inscribed (valid_from anchor
for the registered status)."

[[sections.fields]]
key = "partner_tax_id"
type = "string"
required = false
description = "Partner NIF. Required for most CCAA deduction
routings; advisory when partner is deceased."

[[sections.fields]]
key = "registry_name"
type = "string"
required = false
description = "Free-form registry name for export provenance."
```

The application layer authors:

1. A `derive_situacion_familiar(profile)` resolver that maps
   `(marital_status, pareja_de_hecho.registered)` to a
   `SituacionFamiliar` value per the research doc's rules.
2. A profile-validator rule that refuses `registered = true` AND
   `marital_status = "2"` at construction time.
3. An ADVISORY validator that warns when `registered = true` and
   the `ccaa` is outside the deduction-bearing set.
4. A binding resolver on each per-CCAA `DEDUCCION_PAREJA_DE_HECHO_*`
   axis that gates on `pareja_de_hecho.registered AND
   pareja_de_hecho.ccaa == <expected>`.

The legal catalogue gains the per-CCAA registry-establishing law
entries per the research doc's list (Ley 11/2001 Madrid, Llei
25/2010 Cataluña, Ley 5/2002 Andalucía, etc.) with `corpus_ref`
pointing at the BOE text.

The existing `renta_taxpayer.marital_status` field is re-typed
from loose `string` to `enum` constrained to the AEAT 4-value set
(`enum_values = ["1", "2", "3", "4"]`). This closes a latent gap
the subagent's research surfaced as a separate finding.

## Rationale

Splitting the registration record from the marital-status enum
preserves AEAT-wire fidelity (the 4-value `tipo_EstadoCivil` stays
unchanged) while carrying the CCAA-structured data the
per-jurisdiction deduction routing needs. The derived
`SituacionFamiliar` answers the Art. 82 LIRPF unidad-familiar
question without forcing the profile schema to encode the same
information twice.

The choice to keep `RentaMaritalStatus` at 4 values (rather than
5) is grounded in the published AEAT `tipo_EstadoCivil` dictionary
for Renta 2020-2025 — extending the enum would emit a wire value
the PADRE parser rejects. The choice to use a separate section
(rather than embedding pareja-de-hecho fields under `renta_spouse`)
reflects the legal distinction: a marriage and a registered union
are different civil events with different registry trails.

## Consequences

The schema gains five new fields under a new `pareja_de_hecho`
section. The legal catalogue gains 11-15 new CCAA-level entries
(one per CCAA that operates a pareja-de-hecho registry). The
binding-resolver layer gains one new derivation
(`derive_situacion_familiar`) and one new validator rule pair
(refusal + advisory). The M100 calculation chain gains routing for
per-CCAA deducciones that were previously inaccessible.

The implementation lands as multiple atomic commits per the
relocation-atomicity discipline: schema authoring + legal-catalogue
entries first; validator + derivation second; per-CCAA deduction
bindings third (one commit per CCAA's deduction set). Tests at
every layer per `aeat-roundtrip-discipline`.

## Codification candidates

- **Rule slug:** `aeat-wire-enum-stays-aeat-fidelity-true`.
  **Rule:** Domain enums whose string values are AEAT wire-format
  codes (e.g. `RentaMaritalStatus.value` maps to AEAT
  `tipo_EstadoCivil`) MUST NOT be extended with values absent from
  the AEAT-published dictionary. New civil-status or other
  structured-data axes that AEAT does not encode in the wire field
  land as separate profile sections, NOT enum extensions.

  Held until a second wire-enum extension request surfaces and the
  pattern proves itself across two consumers.

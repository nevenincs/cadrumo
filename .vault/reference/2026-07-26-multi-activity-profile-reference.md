---
tags:
  - '#reference'
  - '#multi-activity-profile'
date: '2026-07-26'
modified: '2026-07-26'
related:
  - "[[2026-07-26-censal-profile-autofill-campaign-close-honesty-review-audit]]"
---

# `multi-activity-profile` reference: `What already ships for indexed profile rows, and where the declaration and the reader disagree`

Code grounding for the multi-activity decision, read at `1f4cbe8284`. Sources are
the profile schema, the shipped attribution-member resolver, the accepted
multi-row modelo decision, and the AEAT M036 diseño bundled under
`src/cadrumo/_data/corpus/aeat_official/disenos_registro/modelo_036/`.

The campaign-close honesty review holds the surface counts and the cardinality
evidence. This document holds what was measured afterwards and is recorded
nowhere else.

## Summary

### The read side already ships, for one section

`src/cadrumo/application/aggregation/_atribucion_member.py` is a complete
profile-to-modelo bridge rather than merely a reader. It regex-enumerates indexed
profile facts (`attribution_entity_socios.{index}.{field}`), groups them by row,
checks a required-field set per row, sorts deterministically, stamps per-row
provenance, and emits `Modelo184MemberRow` - the typed row model declared by the
accepted `2026-05-27-multi-row-modelo-declaration-adr`. It registers as a
calculation source resolver owning `BindingSourceKind.ATRIBUCION_MEMBER`.

So the chain *persisted indexed profile facts to indexed reader to typed modelo
rows to calculation* exists, is accepted, and is in production for
`attribution_entity_socios`. The multi-activity work is a second instance of a
shipped pattern rather than a new one.

### The declaration and the reader disagree about what a row must carry

Measured by parsing the schema and reading the resolver:

    schema, attribution_entity_socios required:
        base_imponible_assigned, name, nif, role, share_pct     (5)
    resolver required-field frozenset:
        base_imponible_assigned, name, nif, share_pct           (4)

`role` is declared required and is not enforced by the reader. The resolver's
missing-field computation is driven entirely by its own frozenset, so a row with
no `role` produces no missing-field diagnostic from that path.

This bears on the decision rather than only on that module: the resolver is the
named template for the new work, and copying its structure would carry a
hardcoded required set into a second section. The schema-derived per-row check
landed separately in this campaign, so a reader can derive the set instead of
restating it.

### One field of the profile row is inert

`activities.cnae` has **no reader and no writer** anywhere in the tree - zero
occurrences of the path in source or registry data, against a positive control
showing its sibling `activities.description` at more than a hundred sites. It is
declared in the schema and consumed by nothing.

The AEAT side has no counterpart for it either, so it is not a mapping problem:
the field exists on the profile alone and is used by neither party.

### The AEAT activity row is a triple, and the diseño carries it per slot

`Sección I.A.E.` appears nine times in the M036 diseño - once per numbered
activity slot across the two módulos casillas, plus the primary activity
register. The row AEAT records is *(descripción, sección, grupo/epígrafe, tipo de
actividad)*, and the sección is what disambiguates an epígrafe, which is unique
only within its sección.

### The one indexed writer that ships is not a model for this

`src/cadrumo/application/user_profile/_cotejo_apply.py` writes indexed paths, and
its section is not repeatable - the rows sit inside an `object`-typed field of a
non-repeatable section, addressed through a path convention the schema does not
declare, with a hand-rolled index scan. It works for its case. Generalising it
would put row structure outside the schema, which is the opposite of what the
repeatable declaration exists to express.

### Nothing writes indexed rows for a repeatable section

The gap is symmetric rather than specific to activities: the attribution section
has a reader and no writer, the activities section has neither. Whatever supplies
attribution rows today does not do it through a writer in this tree.

### The adjacent accepted decision, and why it does not cover this

`2026-05-27-multi-row-modelo-declaration-adr` decided how repeating structured
records reach a calculation: a strict discriminated union of typed row models,
supplied per invocation through a CLI flag, validated per type. It governs the
modelo-input side and is the origin of `Modelo184MemberRow`. It decides nothing
about persisted profile rows, which is why a separate record is needed rather
than an amendment to it.

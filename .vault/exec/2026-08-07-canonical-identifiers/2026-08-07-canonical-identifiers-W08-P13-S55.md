---
tags:
  - '#exec'
  - '#canonical-identifiers'
date: '2026-08-13'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:abf8ef7e7ce3e635ef7f1a3d4e223b865599c2fc70073c89dec68029bdb3bffa'
step_id: 'S55'
related:
  - "[[2026-08-07-canonical-identifiers-plan]]"
---

# enumerate every registered `OutputSchema` class carrying an identifier field this plan retyped, cross-referenced against the wire census's roughly-fifty-class sweep

## Scope

- `src/cadrumo/entrypoints/cli/`

## Description

- Walk the live schema registry programmatically rather than by hand: drive the real CLI payload discovery to populate the registry, then resolve every reachable pydantic model and classify each field annotation against the canonical identifier alias objects.
- Read each classified field's advertised constraints out of the owning class's own `model_json_schema()` without following object references, so a nested payload's bounds are attributed to that payload rather than double-counted at every field pointing at it.
- Cross-reference the resulting inventory against the advertised-constraint signature of each alias declaration, and separately scan for identifier-shaped fields still published unconstrained.

## Outcome

The wire census's "roughly fifty classes" is short by roughly a factor of six. Measured at HEAD:

| measure | count |
|---|---|
| registered command paths | 309 |
| distinct registered `OutputSchema` classes | 299 |
| pydantic models reachable from those classes | 544 |
| alias-typed identifier field sites | 214 |
| classes carrying at least one such field | 110 |
| exposable commands over the model-facing surface | 306 |

The 214 sites resolve to six alias families. Aliases that are one object share one family and one advertised shape by construction; every hex-64 identity concept is the one canonical constrained primitive, so it cannot be split by name.

| family | sites | advertised constraints |
|---|---|---|
| hex-64 identity | 137 | `minLength` 64, `maxLength` 64, `pattern` `^[0-9a-f]{64}$` |
| bucket identity | 69 | `minLength` 1, `maxLength` 128 |
| profile identity | 3 | `minLength` 1, `maxLength` 36, UUIDv4 `pattern` |
| AEAT CSV | 2 | `minLength` 8, `maxLength` 32, no `pattern` |
| tax-identity token | 2 | none; bare string |
| AEAT expediente id | 1 | `minLength` 12, `maxLength` 32, leading-year-run `pattern` |

The named field sites are the two calendar payloads carrying the verified justificante CSV, the expediente declaration payload's expediente id, the borrador latest result's snapshot and bucket ids, the profile preflight result's profile id, and the evidence extraction result's supplier and customer tax ids.

Nine enrolled aliases reach no registered schema at all and therefore publish nothing on the operator wire: the truncated hex address, the AEAT box number, certificado id, clave de liquidacion, presentation id, the registry snapshot id, the absent-tolerant content digest, the profile label, and the Spanish tax id. They are still pinned so that a first consumer inherits a reviewed shape rather than an unmeasured one.

## Notes

Three findings, each carried into the report rather than smoothed over.

The AEAT CSV alias does not publish its `pattern`. Its normalising validator precedes its string constraints in the annotation chain, so the pattern constrains the validator's output rather than a consumer's input and is withheld from the validation-mode schema; the length bounds survive. The serialization-mode schema is the mirror image, publishing the pattern and dropping the bounds. The constraint is still enforced at validation time, so this is a publication gap and not an enforcement gap, but the published contract is weaker than the alias declaration reads.

The tax-identity-token sites publish a bare string through a named definition entry, because a validator-only alias carries no string constraints to advertise. The retype is real at the model boundary and invisible to a consumer reading the schema.

A first, discarded enumeration pass undercounted by reading field annotations directly off the model rather than resolving them. A payload class referenced before its own definition leaves an unresolved forward reference on the field, and reading it raw silently drops the entire subtree behind that field, which is how the first pass lost one of the two CSV-bearing calendar payloads. Resolution is now forced, and the same correction is carried into the pinning module.

A separate sweep of the same registered surface found 254 identifier-shaped fields still published with no constraint at all, of which 131 name a concept that already has a canonical alias: bucket, work unit, bucket event, profile, transaction, filing record and snapshot identities among them. That residue is out of this phase's scope and is reported as carry-forward.

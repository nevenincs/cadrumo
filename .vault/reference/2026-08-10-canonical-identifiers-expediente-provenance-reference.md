---
tags:
  - '#reference'
  - '#canonical-identifiers'
date: '2026-08-10'
modified: '2026-08-10'
body_schema: 'body-v1'
body_hash: 'sha256:e889f902176704f375025592d581e2a9faeb0eb05e8da766dc928e67556665bf'
related:
  - "[[2026-08-07-canonical-identifiers-reference]]"
  - "[[2026-08-10-canonical-identifiers-expediente-provenance-adr]]"
---

# `canonical-identifiers` reference: `IVA compensation expediente provenance sites`

Grounding for the expediente-provenance decision. Every figure below was
derived against the working tree on 2026-08-10 by reading each site, not by a
literal sweep - two of the five values are module-level constants passed as
keyword arguments and are invisible to any `field = "literal"` pattern.

## Summary

`IvaCompensationPeriodState.expediente_id` is declared in
`src/cadrumo/domain/iva_compensation/_carry_forward.py` as
`str = Field(min_length=1, max_length=32)`, with no `description`. Its two
neighbouring fields in the same model, `taxpayer_nif` and
`source_artefact_sha256`, each carry a multi-sentence description declaring
exactly which absent case their `None` represents and why a malformed value is
refused there. The one field that is genuinely polymorphic documents nothing.

Five production paths supply that field. Only three are direct construction
sites. The remaining two reach the model through a shared conduit pair -
`persist_observation_envelope_and_iva_history` calling
`iva_compensation_state_from_observation_envelope`, both in
`src/cadrumo/application/calculations/_iva_compensation_history.py` - which
takes `expediente_id: str` as an untyped parameter and passes it straight
through. **By the time the value reaches the model those two provenances are
indistinguishable**, which is why a marker placed on the model alone cannot
recover them.

## The five supplying paths

| provenance | site | value supplied | AEAT-shaped |
| --- | --- | --- | --- |
| AEAT capture | `application/live/_filed_observation_persistence.py` (conduit call) | `observation.expediente_id`, the captured Sede value | yes |
| local filing | `application/modelo/_filed_revision_observation.py` (conduit call) | `_local_iva_history_expediente_id(filing_ref)` = `f"local-{filing_ref[:26]}"` | no |
| casilla reconstruction | `application/calculations/_iva_compensation_annual_partition.py` (direct) | `f"obs-{filing_year}-{period}"` | no |
| operator seed | `application/calculations/_iva_compensation_history.py` (direct) | module constant `"manual-seed"` | no |
| operator correction | `application/calculations/_iva_compensation_history.py` (direct) | module constant `"manual-correction"` | no |

The local-filing helper's own docstring reads "Derive the non-AEAT expediente
marker stored for local IVA history rows", and the parameter that feeds it is
documented as "Local filing record id used as non-AEAT provenance for the IVA
compensation history state". The codebase already names the field's polymorphism
in prose at the one site where a reader is least likely to look for it.

The reconstruction site additionally documents itself as "computational scaffold
for the FIFO partition below - never persisted, never shown", and declares
`taxpayer_nif=None` on the stated reasoning that "a synthetic label in the
identity field reads downstream as if it named one". That reasoning applies
verbatim to `expediente_id` at the same site and was not applied to it.

## Provenance is already encoded, informally, in two other fields

Every one of the five sites also sets `source_observation_key`, and each key
carries a distinguishing prefix or infix:

| provenance | `source_observation_key` |
| --- | --- |
| AEAT capture | `f"303:{ejercicio}:{token}:{expediente_id}"` |
| local filing | `f"{key}:local:{filing_ref[:64]}"` |
| casilla reconstruction | `f"303:{filing_year}:{period}:iva-annual-partition"` |
| operator seed | `f"303:seed:{filing_year}:{token}"` |
| operator correction | `f"303:correction:{filing_year}:{token}"` |

`status` is a third partial encoding of the same axis: `"filed"` at the
reconstruction site, `"seeded"` at both operator sites, `"app_filing"` on the
local-filing path, and the captured AEAT status verbatim on the capture path.
So the provenance distinction is carried three times, twice by string
convention that nothing validates and nothing can parse back.

## Every non-AEAT marker is strictly redundant

This is the load-bearing measurement for substitutability. Compare each
non-AEAT marker against the `source_observation_key` written beside it:

- `"manual-seed"` is a constant. `303:seed:{year}:{token}` carries the same
  fact plus the period. Information in the marker and not in the key: none.
- `"manual-correction"` is a constant, against `303:correction:{year}:{token}`.
  Information lost by dropping it: none.
- `f"obs-{filing_year}-{period}"` against
  `303:{filing_year}:{period}:iva-annual-partition`. The key is a superset.
- `f"local-{filing_ref[:26]}"` against `f"{key}:local:{filing_ref[:64]}"`. The
  key carries the same reference at 64 characters where the marker truncates to
  26, so the marker is a lossier copy of a value already present.

Setting `expediente_id` to `None` at all four non-AEAT sites therefore destroys
no recoverable fact.

## The storage key does NOT fold this field

The objection that sank the earlier retype attempt was orphaning persisted
records. It does not apply here, and the reason is checkable in one line.

`IvaCompensationHistoryRepository.extract_identifier` returns
`iva_compensation_period_key(payload.period)`, and the namespace definition
`IVA_COMPENSATION_HISTORY_NAMESPACE` in
`src/cadrumo/adapters/persistence/storage/_namespace_registry.py` declares
`object_key_grammar="303:{filing_year}:{period}"`. The record is addressed by
period. **Changing this field's representation orphans nothing.**

The namespace that DOES fold an expediente into its key is a different one:
`AEAT_FILED_DECLARATION_OBSERVATIONS_NAMESPACE`, grammar
`"{sha256(modelo,ejercicio,period,expediente_id)}"`, owned by the sede adapter
and holding `FiledDeclaracionObservation` records whose expediente is genuinely
AEAT-issued. A second key-composition path folding an expediente in Python
lives in `src/cadrumo/adapters/outbound/aeat/sede/_observation_store.py`. Both
sit on the AEAT-issued side of the seam and neither is reached by a change to
`IvaCompensationPeriodState`.

## What the tighter alias would refuse today

`AeatExpedienteId` in `src/cadrumo/core/identity/_namespace.py` is
`^[0-9]{4,}[A-Z0-9]+$` at length 12-32, described in its own module as an
OBSERVED range rather than a published AEAT specification. Eight non-conforming
`expediente_id` literals survive tree-wide and all eight construct
`IvaCompensationPeriodState` - the reason that model was deliberately left
un-retyped when its siblings were converted. Those eight are fixtures and
synthetic corpora, not AEAT-issued values; that count is a floor rather than a
census, because a static literal sweep cannot see the two module-level
constants above, which one run surfaced as a ninth.

## Known gaps in this grounding

- The five paths are enumerated by reading callers one layer out from the
  conduit. A caller reached only through a facade re-export and not named in
  this tree's import graph would be missed. The arbiter is a run, not this
  table.
- Whether any OTHER model in the tree carries the same polymorphic-slot shape
  was not swept. This grounding is scoped to `IvaCompensationPeriodState` only,
  and says nothing about whether the pattern recurs.
- No AEAT publication was consulted. The claim that the four non-AEAT values
  are not AEAT-issued rests on their construction sites, which mint them
  locally, and not on an external specification of what AEAT issues.

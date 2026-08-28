---
tags:
  - '#audit'
  - '#tui-architecture'
date: '2026-08-28'
modified: '2026-08-28'
body_schema: 'body-v2'
body_hash: 'sha256:d05f8a055d7fbf837c71e5917b39e1265df0668344eb0f591755a9907c1247d7'
related: []
---

# `tui-architecture` audit: the last families are grounded, and the sweep's real scope

## The families are sound

The parameter families left unswept by this campaign were checked by comparing
each encoded value numerically against every number stated in its cited
provision's bundled corpus. All clean:

| family | where | result |
|---|---|---|
| IVA rates and the RDL 4/2024 transitional companions | `modelos/303` (15 numeric) | all stated |
| patrimonio tariffs | `modelos/714` (15 numeric) | all stated |
| módulos coefficients | `modelos/131` (20 numeric) | all stated |
| IRNR rates | `modelos/210` (8 numeric) | all stated |
| retención percentages | `legal/irpf-retencion-actividades`, `-administradores` | 10 stated, 0 missing |
| recargo de equivalencia | `legal/iva-recargo-equivalencia`, `iva/recargo-rates.toml` | all stated |
| estimación objetiva exclusions | `legal/irpf-estimacion-objetiva` | all stated |

Nine apparent misses in the retención file are non-numeric selector values
(`"A04,A05"`), correctly skipped rather than absent.

Spanish rows in `iva/rates.toml` verify against their `legal_refs`. The 56
other-member-state rows carry no `legal_refs` and are NOT ungrounded: they cite
`source_refs` to two declared EU sources (`eu-eprs-iva-rates-2025-07-01`,
`eu-your-europe-iva-rates-2026-07-13`, both defined in `legal/iva-rates.toml`).
That is the correct channel — a Spanish BOE provision does not establish another
member state's VAT rate. Checking only `legal_refs` reported them as unverified;
that was the probe's error, not the registry's.

## The correction that matters: my sweep covered two subtrees of ten

Every grounding claim this campaign has made — "structural clean across all 458
numeric parameters", "335 every-number-stated" — was produced by probes that walk
`registry/aeat/modelos/**` and `registry/aeat/legal/**` **only**.

`registry/aeat/` also contains `iva/`, `categories/`, `treaties/`, `calendars/`,
`apoderamientos/`, `authorization.d/`, `m303_orden_anual/`, `territories` and
`topics/`. None was ever scanned. The IVA rate tables — among the most-consumed
values in the product — were invisible to the sweep until this pass went looking
for them by name.

They also use a different shape: `[[rates]]` rows keyed on `pct`, not
`[parameters]` tables keyed on `value`. A probe keyed to one shape cannot see the
other, so the omission was silent in both directions.

So the earlier counts are accurate for what they measured and must not be read as
registry-wide. Anyone citing them should say "of the modelo and legal subtrees".

## A residual the file declares about itself

`iva/rates.toml` documents, in its own comments, that it does not date-bound the
zero rate and that nothing downstream does so either. It explains the trade-off:
the flat `kind = "zero"` axis cannot express LIVA art. 91.Cuatro's donativos-only
zero rate, and the IVA domain does not model `donativo` at all, so the case is
unreachable today. Recorded as the author's declared residual, not a finding.

## Next

Sweep the eight unscanned subtrees for regulatory values, starting with
`categories/` and `treaties/` (treaty withholding caps are rate-shaped and
liability-bearing). A shape-agnostic probe is needed: collect any row carrying a
percentage or money field, whatever the table is called.

## Follow-up: the unscanned subtrees are grounded

The eight subtrees named above were swept with a shape-agnostic probe — any row
carrying a rate, percentage or money field, whatever the table is called.

Only three hold regulatory magnitudes at all:

| subtree | numeric rows | grounding |
|---|---|---|
| `treaties/` | 16 | 16 carry `legal_refs` |
| `iva/` | 68 | 12 `legal_refs` (Spanish), 56 `source_refs` (EU tables) |
| `categories/` | 5 | parent-block `citations`, see below |

`calendars/`, `apoderamientos/`, `authorization.d/`, `m303_orden_anual/`,
`territories` and `topics/` yielded no rows matching the numeric field set.

The five `categories/profiles.toml` rows first read as declaring neither channel.
They are grounded: the `[profiles.proportionality]` block carries a `citations`
list — `ley-35-2006:art-30` (LIRPF art. 30.2.1.ª) plus the Manual práctico Renta
and the AEAT help page. The probe looked for `legal_refs` / `source_refs` on the
ROW; the citation sits on the parent block. Checking the wrong scope, not a gap.

Those rows are the RETA cuota-máxima cap schedule, and their test module is worth
reading as a model. It states the direction in its own docstring: the registry
previously shipped a flat 15000 that "matches no ejercicio at all", every real
year is higher, so it "under-stated the allowance and cost the taxpayer
deduction" — and "nothing in this repository watches over-payment... A gate that
only watches under-declaration would never have found it." Its expected values are
declared as "the amounts AEAT prints in the Manual practico Renta for each
ejercicio... external authority, not values re-derived from the code under test."

That is both the reference shape for a non-tautological registry test and an
independent confirmation of this campaign's organising question, arrived at by
someone else.

So grounding across the registry is now swept, with the scope caveat above
retired: the modelo and legal subtrees by the numeric probe, and the remaining
three by this one.

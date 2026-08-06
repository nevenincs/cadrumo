---
name: calculation-source-canonical-mechanism
trigger: always_on
---

# One canonical aggregation mechanism per calculation type

## Rule

Each calculation value channel has exactly one canonical mechanism per
calculation type per the aggregation-taxonomy table: cross-MODELO fold-ins are
relations (`cross_model_output` / `annual_summary` / `previous_period`),
same-modelo static carry is a direct `previous_filing` binding, ledger projection
is a ledger aggregation resolver, cross-member fan-in is a `per_grupo_member`
binding, and M303 compensación is the IVA wallet decision; a new aggregation
surface MUST enroll under an existing row or amend the ADR before shipping —
never model one fold-in two ways at once.

## Why

ADR `2026-06-10-calculation-aggregation-taxonomy-adr` (Implementation §1 table,
Option A) decided this because the engine's value channels had multiple
overlapping mechanisms with implicit canonicality: the M100←M130 fold-in was
declared BOTH as a relation and as a `previous_filing` binding, two entities and
two resolvers with different live-fire status. Picking one canonical mechanism per
type makes mechanism ownership declared data — binding `source` kind maps to
resolver `owned_sources`, greppable and gate-auditable — and prevents the
dual-modelling that hid the dormant-relation silent-blank.

## How

- Good: a cross-modelo fold-in (M100 `0604` ← sum of M130 casilla `19`) is
  modelled as a relation feeding the engine's `relation_values` channel via
  `RelationPrefillSourceResolver`, not as a second `previous_filing` binding.
- Good: same-modelo single-filer carry (M130 cumulative,
  `source_period_offset_from_target = -1`) uses a direct `previous_filing` binding
  resolved by `PreviousFilingSourceResolver`; M353←M322 cross-member fan-in stays
  a `per_grupo_member` binding (the relation schema has no grouping axis).
- Bad: declaring the same fold-in as both a relation and a `previous_filing`
  binding — the overlap the ADR closes; two schema entities for one value invite
  drift and a dormant resolver.
- Bad: inventing a new resolver/source kind for a value an existing taxonomy row
  already covers, instead of enrolling under that row or amending the ADR.

# One canonical aggregation mechanism per calculation type

Each calculation value channel has exactly one canonical mechanism per
calculation type:

| kind | mechanism |
|---|---|
| cross-MODELO fold-in | a relation (`cross_model_output` / `annual_summary` / `previous_period`) |
| same-modelo static carry | a direct `previous_filing` binding |
| ledger projection | a ledger aggregation resolver |
| cross-member fan-in | a `per_grupo_member` binding |
| M303 compensación | the IVA wallet decision |

A new aggregation surface MUST enroll under an existing row, or amend the ADR
before shipping. **Never model one fold-in two ways at once.**

The engine's value channels once had overlapping mechanisms with implicit
canonicality: one cross-modelo fold-in was declared BOTH as a relation and as a
`previous_filing` binding — two entities, two resolvers, different live-fire
status. Picking one canonical mechanism per type makes ownership declared data:
a binding `source` kind maps to a resolver's `owned_sources`, greppable and
gate-auditable.

## How

- **Good:** a cross-modelo fold-in is modelled as a relation feeding the engine's
  relation channel; a same-modelo single-filer carry uses a direct
  `previous_filing` binding; cross-member fan-in stays a `per_grupo_member`
  binding, because the relation schema has no grouping axis.
- **Bad:** declaring the same fold-in as both a relation and a `previous_filing`
  binding; or inventing a new resolver or source kind for a value an existing
  row already covers.

Source: ADR `2026-06-10-calculation-aggregation-taxonomy-adr`. Companions:
`relation-slot-bindings-declare-relation-source`, `no-dormant-source-resolvers`.

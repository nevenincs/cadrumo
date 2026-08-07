---
name: aeat-calculation-aggregation
trigger: always_on
---

# AEAT calculation aggregation: one mechanism, no dormancy, one path

## One canonical mechanism per calculation type

Each calculation value channel has exactly one canonical mechanism:

| kind | mechanism |
|---|---|
| cross-MODELO fold-in | a relation (`cross_model_output` / `annual_summary` / `previous_period`) |
| same-modelo static carry | a direct `previous_filing` binding |
| ledger projection | a ledger aggregation resolver |
| cross-member fan-in | a `per_grupo_member` binding |
| M303 compensación | the IVA wallet decision |

A new aggregation surface MUST enroll under an existing row or amend the ADR
before shipping. **Never model one fold-in two ways at once.**

The engine's channels once had overlapping mechanisms with implicit canonicality:
one cross-modelo fold-in was declared BOTH as a relation and as a
`previous_filing` binding — two entities, two resolvers, different live-fire
status. One canonical mechanism per type makes ownership declared data: a binding
`source` kind maps to a resolver's `owned_sources`, greppable and gate-auditable.

## No dormant resolvers; every source is routed or advised

Every `ModeloSourceResolver` merged to main MUST be enrolled in the live
calculate mesh (`merge_source_resolutions` in
`src/cadrumo/application/modelo/_calculation_actions.py`) or deleted. Every
registry binding `source` kind MUST be a member of the enrolled-or-explicitly-
deferred set (`_BUCKET_AGGREGATION_OWNED_SOURCES` union `DEFERRED_SOURCE_KINDS`,
enforced by `assert_no_novel_source_kinds`). And
`collect_unhandled_source_diagnostics` MUST run on the live calculate path, so an
unrouted source surfaces a non-blocking advisory — never a silent blank.

The safety net was once built and switched off: the diagnostic collector had no
live caller and the owned-sources set described the enrolled set while enforcing
nothing, so a new TOML binding with a novel `source` compiled and silently
resolved to blank.

## Pull and calculate share one aggregation path

A casilla's value MUST be produced by the same aggregation logic whether reached
via the live `calculate` path or the Sheets-pull path. Both surfaces share one
resolver set, and a regression proves they agree for a shared revision — they
both persist to the SAME revision, so a calculate-then-export cycle could
otherwise yield divergent, conflicting values with no detection at save time.

## How

- **Good:** a cross-modelo fold-in is modelled as a relation feeding the engine's
  relation channel; a same-modelo single-filer carry uses a direct
  `previous_filing` binding; cross-member fan-in stays a `per_grupo_member`
  binding, because the relation schema has no grouping axis.
- **Good:** a not-yet-built source kind is added to `DEFERRED_SOURCE_KINDS`
  (canonical in `application/aggregation/_source_mesh.py`) — explicitly deferred
  and advisory-visible.
- **Good:** the relation prefill resolver delegates to
  `resolve_relations_from_local_store` in
  `src/cadrumo/application/calculations/_relation_prefill.py` — the exact
  function the pull path calls — with parity enforced by
  `application/calculations/tests/test_pull_path_calculate_path_casilla_parity.py`.
- **Bad:** declaring the same fold-in as both a relation and a `previous_filing`
  binding; or inventing a new resolver or source kind for a value an existing row
  already covers.
- **Bad:** merging a fully-implemented resolver that is exported but never
  enrolled — dead capacity whose registry kind blanks silently.
- **Bad:** landing a new `source` kind without enrolling a resolver or
  registering it deferred, then silencing the refusal via the manual-input
  allowlist.
- **Bad:** a pull-path assembler that computes a casilla one way while the live
  calculate path computes it another.

Source: ADR `2026-06-10-calculation-aggregation-taxonomy-adr`; audit
`2026-06-10-calculation-engine-foundations-audit` (F4, F5).

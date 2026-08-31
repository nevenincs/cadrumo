---
tags:
  - '#exec'
  - '#semantic-consolidation'
date: '2026-08-31'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:d635c40e45a2a8f2727cabdee1d36d72cdd6769e17252c30b2340db71dbdd5ae'
step_id: 'S25'
related:
  - "[[2026-08-28-semantic-consolidation-plan]]"
---

# Rule on the float-typed zero-to-one scores and the exclusive gt/lt rate bound: whether each earns its own alias or stays open-coded as a distinct rule

## Scope

- `src/cadrumo/`

## Changes

- `M` `src/cadrumo/adapters/inbound/pdf/_shared.py`
- `M` `src/cadrumo/adapters/outbound/aeat/sede/schema.py`
- `M` `src/cadrumo/application/evidence/_service.py`
- `M` `src/cadrumo/core/config_runtime_fields.py`
- `verify:` `UnitFraction` probed at 0.0, 0.5, 1.0, 1.5, -0.1 -- refuses outside the interval
- `verify:` settings temperature bounds now `[Ge(0.0), Le(1.0)]`
- `blocked:` suite verification, see below

## Notes

The census ruled itself. Fifteen float fields carry a zero-to-one-shaped bound
and they are three different things:

- Three are genuine zero-to-one SCORES -- an extraction confidence, a sede
  confidence, an evidence completeness ratio -- and they take `UnitFraction`.
  `completeness_ratio` already used it at three other sites, so this one was the
  straggler rather than a new adoption.
- Seven are DURATIONS in seconds with `gt=0`: lock timeouts, retry backoffs, a
  polling interval, an HTTP timeout. Same operator on the bound, unrelated
  concept, and they stay open-coded. An alias here would say "positive number"
  and teach a reader nothing.
- A search relevance `score` is `ge=0.0` with no upper bound at all, so it is
  not a fraction.

### The divergence the census exposed

Two temperature fields said zero-to-one and the settings default said zero-to-TWO,
for the same value. `client.py:487` feeds
`settings.cadrumo_llm_default_temperature` straight into an `LlmRequest` whose
own `temperature` is bounded at one -- so `CADRUMO_LLM_DEFAULT_TEMPERATURE=1.5`
validated as configuration and then failed at request construction. A
configuration the application called valid and could never use.

Capped at one, where the request caps it. The two remain open-coded rather than
aliased: an LLM sampling temperature is not a share of one and giving it
`UnitFraction` would be the scale confusion this campaign keeps finding, not a
cure for it.

### Verification blocked, again and stated

A peer's `core/` split has left `cadrumo.core.storage_taxonomy_locations` with a
circular import that fails on its own, and `cadrumo.core.hardware` missing --
sixteen `llm` test modules will not collect. Checked that neither is reachable
from this change: `core/unit_proportion.py` has zero storage references, and two
of the three changed modules import cleanly in isolation.

So this rests on direct annotation probes rather than a green suite. Weaker
evidence, recorded as such.

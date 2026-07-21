---
tags:
  - '#audit'
  - '#mcp-progressive-discovery'
date: '2026-07-08'
modified: '2026-07-08'
related:
  - '[[2026-07-08-mcp-progressive-discovery-adr]]'
  - '[[2026-07-08-mcp-progressive-discovery-plan]]'
  - '[[2026-07-08-mcp-progressive-discovery-research]]'
---

# `mcp-progressive-discovery` audit: `measurement`

## Scope

This audit records the measurement outcome of P6 (the Measurement item in the
ADR's Implementation section, plan phase P06, steps S22-S24). It captures the
DETERMINISTIC core-vs-full discovery comparison that is provable today without a
live model, and the discovery selection-quality scoring the live persona harness
will run once a model is driven against the scenario. It audits three shipped
artifacts: the discovery golden scenario `descubrimiento_verbo.toml`, the
discovery scoring helpers in `src/aeat/agent/eval/_live_scoring.py`
(`score_discovery_trajectory`, `compare_surface_discovery`, and the
`DiscoveryScore` / `SurfaceDiscoveryComparison` verdicts), and the gate
`src/aeat/agent/eval/tests/test_discovery_scoring.py`. All numbers below were
measured from the live descriptor set (`build_tool_descriptors`) and the live
surface policy (`advertised_descriptors`, `SurfaceMode`) on 2026-07-08.

## Findings

### advertised-surface-reduction | high | the CORE surface advertises 14 tools where FULL advertises 296

The console exposes 290 per-verb command descriptors. Under `SurfaceMode.FULL`
(the pre-ADR flat surface) `tools/list` advertises every one of them plus the six
always-on non-verb tools - the `harness.load` floor, the two grounding tools, and
the `search` / `execute` / `toolsets` meta trio - for 296 advertised tools. Under
`SurfaceMode.CORE` (the shipped default) only the orientation slice is advertised
up front: 8 per-verb descriptors (the `contract` capability verb plus the seven
`overview.*` obligation verbs `agenda`, `backlog`, `calendar`, `explain`,
`pipeline`, `prepare`, `status`) plus the same six always-on tools, for 14
advertised tools. That is a 282-tool reduction (296 to 14), a 95% smaller
advertised surface, which is the crowd-out the ADR's P1 set out to remove.

### long-tail-verb-still-reachable | high | search reaches modelo.work.calculate at rank 2 with its input schema

The measurement target `modelo.work.calculate` is a genuine modelo-130 workflow
verb that resolves against the live CLI surface but is NOT in the CORE orientation
slice - it is long-tail and absent from the default advertised list. Querying the
`search` meta-tool with a natural-language concept phrase ("calculate the modelo
draft casillas for the quarter") ranks it 2nd of 290 (score 20.17, behind only the
sibling `modelo.casillas` read), and the result carries the verb's 4-key input
schema, so a model that finds it through `search` can invoke it through `execute`
in one further round-trip without a separate schema lookup. The lean CORE surface
therefore loses nothing the operator can reach: the verb universe is discovered,
not listed.

### discovery-selection-quality-scored | medium | rounds-to-correct-verb quantifies the core-vs-full trade

`score_discovery_trajectory` scores how efficiently an observed trajectory reaches
a long-tail verb: `rounds_to_correct_verb` is the 1-based ordinal of the call that
first executes the target, `discovery_calls` isolates the `search` / `execute`
meta round-trips, and `misselections` counts wrong verbs executed before the
target. A minimal CORE trajectory (`search` then `execute` the target) scores two
rounds, both discovery calls; a FULL trajectory (a direct per-verb call) scores
one round, zero discovery calls. `compare_surface_discovery` confirms both
surfaces reach the SAME verb and reports the trade: a `rounds_delta` of exactly 1
(the single extra `search` round-trip) bought against the 282-tool advertised
reduction. A trajectory that never executes the target scores `reached = False`
with a `0` ordinal and a recorded failure, so an unreached verb cannot read as a
cheap discovery (the anti-tautology guard, proven by the FAIL-catch tests).

### live-model-ab-is-the-follow-on | low | the deterministic comparison is provable now; a scored live A/B remains outstanding

The comparison above is deterministic (surface counts, search ranking, and the
scoring arithmetic need no model). What still requires a live run is a scored A/B
of an UNPRIMED model driving the CORE surface versus the FULL surface against the
golden scenarios, feeding real captured trajectories into
`score_discovery_trajectory`. This is honestly recorded as the follow-on: the
feature's acceptance already showed a live Claude session connecting to and
driving the core surface end to end, so the transport and the core surface are
proven live; what remains is wiring that live session's captured trajectory
through the discovery scorer to produce the rounds-to-correct-verb numbers for a
real model, rather than the constructed trajectories the S24 gate scores today.

## Recommendations

- Keep `SurfaceMode.CORE` the shipped default; the 296-to-14 advertised reduction
  with the long-tail verb still reachable at search rank 2 is the ADR's P1 intent
  realised, and the `AEAT_MCP_SURFACE=full` toggle preserves the flat surface for
  the A/B and for opt-out.
- Wire the live persona harness to emit a captured discovery trajectory for the
  `descubrimiento-verbo-long-tail` scenario and feed it through
  `score_discovery_trajectory`, closing the live-model A/B as a follow-on step so
  the rounds-to-correct-verb metric is reported for a real model, not only
  constructed trajectories.
- Re-measure the advertised counts whenever the verb tree grows: the
  `test_discovery_scoring.py` gate asserts the CORE surface stays lean (<= 20) and
  FULL stays large (>= 250) and the target stays long-tail, so a regression that
  leaked verbs into the orientation slice would fail loudly.

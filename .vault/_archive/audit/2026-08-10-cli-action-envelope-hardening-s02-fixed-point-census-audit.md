---
tags:
  - '#audit'
  - '#cli-action-envelope-hardening'
date: '2026-08-10'
modified: '2026-08-10'
body_schema: 'body-v1'
body_hash: 'sha256:eb9b960867fc8d50e64cc2106fd14eef0041815660d797953c45d60ffb9fedc2'
related:
  - "[[2026-08-09-cli-action-envelope-hardening-adr]]"
---

# `cli-action-envelope-hardening` audit: `S02 fixed-point census review`

## Scope

Formal review of W01.P01.S02 against the accepted ADR, reference, and plan.
The review covered discovery evidence and triggers, observed-versus-admitted
state, deterministic passes, unknown-cluster refusal, explicit admission and
rescan closure, S01 compatibility, live noise, and positive and negative
evidence for all seven discovery kinds.

## Findings

### s02-fixed-point-census | high | The fixed-point pass silently expands the S01 production denominator into tests

`census()` preserves S01's production-only source universe, but
`fixed_point_pass()` passes the broader `repository_sources()` snapshot directly
to candidate and discovery collection. The live probe consequently produced
1,977 fixed-point candidates: 1,265 production identities plus 712 test
identities. Its 1,850 discoveries likewise split into 1,086 production and 764
test records. This is not merely performance overhead: it changes the candidate
denominator under a feature whose disposition identity is defined by S01, while
the discovery taxonomy has no explicit test-evidence kind. The default S01
command remains compatible, but the fixed-point result is not a refinement of
that contract.

Resolution: closed on re-review. Production Python now remains the candidate
denominator, production YAML catalogues are a separately typed discovery
source, and test paths are rejected from the fixed-point source set. The first
live pass returned the same 1,265 candidates as S01.

### s02-fixed-point-census | high | Candidate triggers cite an arbitrary global alias match rather than causal evidence

`candidates_by_alias` retains the first candidate for each alias across the
entire snapshot, and `_trigger()` attaches that candidate to every later
discovery using the alias. A bounded probe placed a `suggestion` producer in
one module and a helper/renderer in another; both discoveries in the second
module cited the first module's producer key. The record therefore preserves a
location and a trigger-shaped value, but not the evidence relationship that led
to the discovery. This makes review and explicit admission misleading.

Resolution: closed on re-review. Triggers now carry the local path, enclosing
symbol, and source location, and candidate linkage is resolved only by the same
path, line, and alias. Regression assertions require trigger path and symbol to
equal the discovery's local scope.

### s02-fixed-point-census | high | Helper, renderer, and locale kinds accept proximity and substring false positives

Function discovery uses `ast.walk(node)`, so an inner function's alias and
renderer sink also classify its outer function. Renderer classification needs
only any admitted alias occurrence and any call named like `join`, `format`,
`print`, or another sink anywhere in the function; it does not link the alias
to that sink. A bounded probe classified an outer function whose evidence
existed only in its nested function and classified a function where
`suggestion` was merely assigned while an unrelated list was joined. Locale
discovery uses raw `source.find(command_prefix)`, and classified a YAML comment
that only mentioned an `aeat` command. These are direct counterexamples to the
claimed evidence-preserving seven-kind coverage.

Resolution: closed on re-review. Nested lexical scopes are traversed
independently, renderer sinks require a direct local action-reference argument,
generic `join` and `format` calls are no longer renderer sinks, and locale
discovery parses YAML string values rather than raw text. The bounded negative
fixture now rejects the original outer-scope, unrelated-sink, and comment
counterexamples while retaining the nested direct-flow positive evidence.

### s02-fixed-point-census | high | The CLI cannot consume admitted state to perform the required closing rescan

The programmatic API can admit one in-memory pass and rescan it, but the CLI
always constructs `initial_fixed_point_state()` and exposes no admitted-state
input or reusable snapshot. On the live tree `--fixed-point` reports all 1,850
discoveries as unadmitted, while `--close-fixed-point` can only run from that
same seed state. There is no reproducible command path from review and explicit
admission to the complete closing rescan required by the plan; the printed
snapshot contains only the initial state.

Resolution: closed on re-review for state transport. The CLI now reads and
writes strict canonical JSON-v1 state, checks version, revision, scope, seed
aliases, ordering, and exact fields, and exposes an explicit admission-and-
rescan transition. A state pinned to `HEAD` was rejected immediately when used
with `HEAD^`.

### s02-fixed-point-census | medium | The seven-kind test proves presence but not evidence validity

The synthetic test asserts that the set of discovery kinds equals the enum,
but does not assert the exact source relation for each kind or any negative
case for nested scopes, unrelated sinks, comments, prose, or global alias
collisions. This allowed all three evidence-integrity defects above to pass.

Resolution: closed on re-review. The suite now carries direct negative and
positive relationship tests for lexical scope, renderer dataflow, YAML
comments, local trigger identity, strict state, and reopening after new source.

### s02-fixed-point-census | high | Live alias admission causes an unbounded-noise second pass and the required sequence still cannot close

The new operational state path works, but the required observe, admit, rescan,
and close sequence does not. Phase one completed in 30.6 seconds with 1,265
production candidates, 659 discoveries, and 659 unadmitted records. Phase two
loaded that state, admitted the observations, and rescanned in 60.9 seconds;
admitted action aliases such as generic `result`, `message`, and `applied`
expanded the candidate universe to 2,887 and produced 1,125 discoveries, of
which 489 were new. Phase three loaded the admitted state and correctly refused
closure in 30.7 seconds. Repetition is possible, but there is no live convergence
proof or guard against generic transitive aliases turning ordinary dataflow into
action evidence. The tiny synthetic test closes after one admission and does
not exercise this live expansion. Thus state transport is remediated, but the
campaign still cannot demonstrate a bounded complete rescan closure.

Resolution: closed on final re-review. Cluster acknowledgement now records only
observed cluster keys and preserves the admitted alias vocabulary exactly.
Alias promotion is separate and accepts only a token present in a locally
evidenced `ACTION_ALIAS` discovery. Tests prove generic cluster tokens are not
promoted, an explicitly evidenced `recovery` alias expands and reopens the next
pass, and an unobserved generic `message` alias is rejected. The live
cluster-only rescan retained the 1,265-candidate denominator and 659 discoveries
with zero unadmitted records; a separate-process close reproduced that state.

Validation evidence: all seven targeted tests passed; Ruff passed; and
basedpyright reported zero errors, warnings, or notes. The live command reported
1,977 candidates and 1,850 discoveries, all unadmitted. The discovery-kind
distribution was 1,182 command forms, 356 helpers, 179 refusal sites, 79
renderers, 47 models, five locale families, and two action aliases. These are
observations for noise diagnosis, not exact-count gates. Bounded synthetic
probes reproduced the cross-file trigger, nested-scope, unrelated-sink, and
locale-comment false positives.

Remediation validation: all nine targeted tests passed; Ruff passed; and
basedpyright reported zero errors, warnings, or notes. The default S01 JSON CLI
completed successfully. The strict revision mismatch failed before scanning.
All three operational phases completed within their 90-second bounds, so no
stuck process required inspection or termination. Counts above are diagnostic
measurements explaining expansion, never gates.

Final remediation validation: all ten targeted tests passed in 34.68 seconds;
Ruff passed; and basedpyright reported zero errors, warnings, or notes. The live
cluster-admission phase completed in 60.2 seconds with 1,265 candidates, 659
discoveries, zero unadmitted discoveries, and zero unknown clusters. The
separate phase-three close completed successfully in 30.2 seconds with the same
identity totals. Both were below the 90-second bound. A process inventory after
closure found zero orphan `dev.cli_action_census` processes. These totals are
execution evidence only and remain absent from assertions.

## Recommendations

1. Keep fixed-point candidates on the exact S01 production universe and make
   any additional locale or test evidence an explicitly typed, independently
   reported source family.
2. Preserve the actual AST/source relationship for every trigger; never select
   a representative candidate globally by alias.
3. Make helper and renderer discovery scope-aware and dataflow-linked, and
   parse locale structures so comments and unrelated prose cannot qualify.
4. Add a deterministic admitted-state artifact or equivalent CLI input and
   prove the operational sequence: observe, explicitly admit, fully rescan,
   then close with no new evidence or unknown clusters.
5. Add exact positive and negative relationship tests for every discovery kind
   without asserting today's live totals.

Recommendations 1, 2, 3, and 5 are implemented. Recommendation 4's state
transport is implemented, but closure remains open: constrain action-alias
admission to reviewed semantic vocabulary, or otherwise prove repeated live
passes converge without promoting generic data variables, then rerun the full
operational sequence to zero new evidence.

The remaining recommendation is implemented and verified. No S02 findings
remain open.

---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-08'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:ece31ca424214b3f9bfe8dc8b20da048f640009d1114c46e0a25d025de8deddc'
step_id: 'S114'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---
# Add the singularity gate asserting exactly one production surface constructs an IVA category on the ingestion path, AST-walked against the real tree with no stored baseline and no per-violation allowlist, following the shipped prompter and profile-field singularity precedents. Mutation-proven by teaching the projection bridge or the legend axis to mint and confirming it reds. This lands ONLY after the convergence and never before, because written against today's tree it would either red on two real sites or need those sites carved into a sanctioned set, and a singularity gate with the competing voices allowlisted into it is the gate lying. Sequenced after the convergence it ratchets a true statement, sequenced before it ratchets an aspiration

## Scope

- `src/cadrumo/application/ledger`
- `src/cadrumo/tests`

## Description

- Add the IVA-category singularity gate under `src/cadrumo/tests`, three rules
  recomputed from `ast` against the real production tree every run.
- Rule one: `IvaCategory(...)` is constructed only inside the sanctioned
  authority module.
- Rule two: no function on the ingestion path outside the authority declares a
  return annotation naming the category type, resolving stringised annotations
  so a deferred-evaluation module cannot hide behind one.
- Rule three: no module outside the authority calls a shipped
  category-producing callable, which is the rule with no annotation escape.
- Add two anti-vacuity tests: the authority module must exist, and it must
  carry both halves of the decision it is exempted for.
- Add six discrimination tests feeding each detector the drift it exists to
  catch plus the live shapes it must not flag.

## Outcome

The gate states a property rather than a tally. There is no stored baseline, no
per-violation allowlist and no hardcoded count as a pass condition, so a module
written tomorrow joins the sweep the day it is written and a renamed rival is
caught by shape rather than by name.

Rule two is the load-bearing one and the reason rule one alone was insufficient.
The second rival that was removed never named the category type in its body at
all: it reached a category through a mapping accessor, so a construction walk
reported it clean and only its signature gave it away. The discrimination test
for that rule asserts BOTH halves on one source, so the proof is that rule two
adds reach rather than that two rules happen to agree.

Rule three closes the annotation escape rule two leaves open. An unannotated
function that builds nothing is invisible to the first two rules, and its own
discrimination test asserts both of them report clean on exactly the source
rule three catches.

Two residual limits are documented on the gate rather than papered over: an
unannotated function reaching a category through a first-party helper the gate
does not name, and a module string built at runtime for dynamic import, which no
static walk can see.

Scope is the document-ingestion package deliberately. The persisted-model field
coercion and the registry regulation parser each build a category from data that
is already a category, on paths a document confirm never reaches; folding them
in would make the rules unusable without telling anyone anything.

## Verification

    uv run --no-sync pytest src/cadrumo/tests/test_iva_category_singularity.py -n0 -q -m unit
    11 passed in 43.63s

Mutation proof, run from OUTSIDE the repository so no tracked file was edited
and no mutation window was ever shippable state. A pytest plugin on PYTHONPATH
rebinds the module-set resolver the gate holds and appends one rival module that
exists only in memory, exercising all three rules at once:

    PYTHONPATH=<scratch> uv run --no-sync pytest src/cadrumo/tests/test_iva_category_singularity.py -n0 -q -m unit -s -p rival_category_plugin
    [MUTATION] rival-category plugin LOADED
    [MUTATION] rebinding installed on a real holder
    [MUTATION] APPLIED: invocations=4 modules 1530 -> 1531
    3 failed, 8 passed in 35.57s

    FAILED test_only_the_authority_constructs_an_iva_category
    FAILED test_no_rival_returns_an_iva_category
    FAILED test_no_rival_reaches_a_category_producing_authority

Three rungs, so the green run cannot be mistaken for a proof. The banner proves
the plugin loaded; a hard assertion proves the rebinding found a real holder,
since a no-op rebind would otherwise print APPLIED while every rule passed
untouched; and the module-count delta proves the wrapper was reached and really
changed what the gate reads. The eight tests that stayed green are the
anti-vacuity and discrimination tests, which run against synthetic sources
rather than the tree and are correct to be unaffected.

The mutation ADDS a surface rather than deleting one, deliberately: a deletion
reds by collection error, which proves far less than a rival being detected.

## Notes

The gate names its sanctioned owner in one constant rather than allowlisting
violations, following the shipped prompter singularity precedent. The exemption
is earned rather than asserted: a dedicated anti-vacuity test fails if the
exempted module stops carrying both halves of the decision, so the decision
being quietly moved elsewhere while the name stayed would red rather than leave
the rules exempting an empty shell.

An unrelated integration-lane failure was observed in the batch ingest runner's
inference pacing, where a stub HTTP server answers the reader-reachability probe
with 501. It is on a peer campaign's surface, touches no classification code and
is not owned here.

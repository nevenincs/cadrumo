---
tags:
  - '#exec'
  - '#test-harness-honesty'
date: '2026-07-25'
modified: '2026-07-25'
step_id: 'S04'
related:
  - "[[2026-07-25-test-harness-honesty-plan]]"
---

# Make the packaging preflight recipe state its marker selection explicitly, because it inherits the default marker expression over a mixed-marker directory and silently drops 106 of 330 tests while exiting zero, and the dropped modules are those named for the packaging smoke, Scoop, Homebrew, and Docker workflows the recipe gates

## Scope

- `justfile`
- `dev/packaging/tests/`

## Description

- Replace the packaging preflight recipe's marker-free pytest invocation with the explicit expression `unit or (integration and not serial)`, kept byte-identical to the static lane in the continuous-integration workflow that already runs the same directory.
- Record in the recipe comment why the expression is stated rather than inherited, and name the recipes that own the excluded serial cohort.
- Add `dev/packaging/tests/test_preflight_recipe_selection.py`, a behavioural gate that boots real collect-only subprocesses with each discovered recipe's own arguments and asserts every non-perf test in the directory is selected by some recipe.

## Outcome

The recipe was invoking pytest against a mixed-marker directory with no marker override, so it inherited the default expression from the project pytest configuration. Measured at commit `1307d1ced7`, that collected 238 of 344 tests and deselected 106 while exiting zero. This is the partial-run variant of a marker mismatch and the dangerous one: a fully deselected run exits with the no-tests-collected status a strict caller notices, whereas a partially deselected run exits green under a normal summary. The silently dropped modules were the ones named for the packaging smoke, Scoop, Homebrew, and Docker-selection workflows the recipe gates as a declared dependency of the Linux and Docker smoke targets.

Stating the selection was chosen over failing the recipe on any deselection, on three pieces of evidence. The directory partitions cleanly into 238 unit and 106 integration tests with no other execution marker present, so nothing is ambiguous about what the two halves are. The continuous-integration static lane already runs this exact directory under `unit or (integration and not serial)`, so the expression is proven rather than invented, and adopting it removes a local-against-continuous-integration divergence instead of creating a third lane. And a refuse-on-any-deselection rule cannot hold here, because the excluded serial cases legitimately need a built wheel cohort and an unshared process; enforcing it would either red the recipe permanently or push a wrong marker onto those tests.

After the change the recipe collects 350 of 363 and deselects 13. The 13 are the serial cohort and each has a named owner: the installed-oracle cases belong to the installed-oracles recipe that builds the wheel cohort they consume, and the serving-path benchmark to the performance lane in the dispatch-only full continuous-integration workflow. The totals moved from 344 to 363 because this Step added 19 tests.

The guard asserts coverage rather than zero deselection, because a recipe may narrow its own selection freely; what it may not do is leave the remainder unowned. It discovers every justfile recipe invoking pytest over the directory, collects each one for real, and asserts that the union of their selections covers every test except those carrying the performance marker, whose registered policy already states it is held out of every per-push lane. The exclusion is therefore grounded in a declared marker policy rather than in a per-test allowlist.

Discrimination was proven by measurement, not by reading. Reintroducing the marker-free form into the recipe and re-running the gate produced two failures naming the specific defect: the explicit-marker assertion reported the recipe's actual argument tuple, and the coverage assertion enumerated the 93 tests then selected by no recipe at all. Restoring the fixed form returned all 19 cases to green.

## Notes

The gate is marked as a unit test deliberately. A guard against marker under-selection must sit inside the selection a regressed recipe still runs; marked as an integration test it would be deselected by exactly the defect it exists to catch and could never fire. Its 19 cases were confirmed to collect under the default marker expression for that reason.

Both output readers carry positive and negative controls over verbatim captured pytest output, and every collection is read twice by independent parsers whose results must agree. That cross-check paid for itself immediately: it caught a path-separator normalisation in the node-id reader that collapsed the distinct parametrized cases of one real test into a single entry, a defect that would have silently understated every selection. An earlier hypothesis blaming worker output interleaving was disproved by measurement before the real cause was found, and the docstring records the true reason.

Three findings were confirmed as owned elsewhere and left alone. The whole-tree collection gate reports six collection errors, all import failures inside uncommitted peer work under the modelos domain and the terminal-interface adapter tests; the trees this Step touches collect clean. Three harness self-gates are red on a peer's committed filing-freshness test module for stubs and monkeypatching, and name no file from this Step. The distribution-identity verifier refuses on a drifted pinned inventory digest, which is a peer-owned re-pin, and it sits in the unit half so the recipe was already red on it before this change.

Two further observations were recorded but not acted on. Running the widened selection surfaced a genuine local environment refusal: the clean-source cohort build requires the pinned toolchain version that continuous integration provisions and this workstation has drifted past, which the widened recipe now reports honestly instead of hiding. Separately, a performance-gate policy test asserts a justfile substring that no longer appears verbatim, because the two broad serial passes have since gained an additional marker exclusion; that is outside this Step's scope and was not touched.

Semantic code search was degraded throughout and was not relied on. Its code index reported itself available with an empty degraded-reasons list while holding a small fraction of the tree. Discovery was carried instead by targeted search over the marker, recipe, and lane vocabularies, direct reads of the pytest configuration and the workflow lane definitions, and real collection measurements against the tree.

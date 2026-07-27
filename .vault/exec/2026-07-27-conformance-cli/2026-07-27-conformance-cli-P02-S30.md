---
tags:
  - '#exec'
  - '#conformance-cli'
date: '2026-07-27'
modified: '2026-07-27'
step_id: 'S30'
related:
  - "[[2026-07-27-conformance-cli-plan]]"
---

# split the scenario input figures out of the M303 prorrata oracle expected-by-casilla map and rename the payload to carry its filing year so its genuine expected figure enters the honesty relation

## Scope

- `src/cadrumo/_data/corpus/manual_oracles`

## Description

- Renamed the payload to carry its filing year in the house form the fold's
  attribution reads, `modelo-<id>-<year>-<scenario>.json`, matching the other
  fifteen manual-oracle payloads and the five replay captures.
- Reduced `expected_by_casilla_id` to the single genuine registry output,
  `iva.prorrata-porcentaje` = 56, and rewrote the notes to separate the
  scenario's GIVENS from the manual's DERIVED figures and to record why each of
  the three removed figures is not an expected value.
- Repointed the six test modules that load the payload by name, and moved the
  two annual volume figures and the casilla-44 regularizacion out of the
  payload-sourced reads into named module constants quoting the manual pages, the
  same shape those modules already use for their other manual figures.
- Corrected the grounding gate's docstring, which described the year-less payload
  as a live attribution gap that no longer exists.

## Outcome

The bundled manual-oracle corpus now folds with zero attribution gaps. Before:
20 attributed payloads, one recorded gap `payload_name_lacks_modelo_and_filing_year`,
90 rows, 9 checked revisions, 58 declared groundings, 0 findings, coverage 0.0460.
After: 21 attributed payloads, zero gaps, same 90 rows, same 9 checked revisions,
same 58 declared groundings, still 0 findings, coverage unchanged at 0.0460, zero
unmatched evidence. The payload resolves to modelo 303 filing year 2025, revision
`2023-y-siguientes`, carrying exactly one oracle casilla.

Coverage is unchanged because the newly attributed figure is evidence rather than
a declared grounding claim: `iva.prorrata-porcentaje` is now checked by the
oracle-to-registry direction (it is `input_kind = computed`, formula
`modelo-303-iva-prorrata-porcentaje`, and enrolled in
`modelo-303-2023-y-siguientes-reconcile-when-present`), but the revision does not
list it in `externally_grounded_casilla_ids`. Declaring it would raise the
declared-grounding count and the coverage figure, and both preconditions of the
grounding rule are already satisfied and verified here. That declaration is a
verification-contract change on a filing-grade surface rather than a corpus
payload repair, so it was deliberately not made under this Step and is carried
forward as a ready-to-land follow-up.

Three figures left the expected map, each for a stated reason. The two annual
volume casillas are `input_kind = manual`: they are the scenario's givens, so
asserting them as expected values would assert that the engine reproduces its own
inputs, which is why the corpus previously folded to zero findings while carrying
a malformed map. Modelo 303 casilla 44 carries the manual's -217,60 and is
engine-produced, but by the `prorrata_regularizacion` source resolver rather than
by a registry formula, so it falls outside the registry-formula grounding
relation the expected map feeds; leaving it there after attribution would have
turned a true statement about the resolver into a false finding against the
registry.

No AEAT figure lost its gate. The two volumes and the -217,60 remain pinned end
to end against the real registry snapshot, domain and resolver chain by the same
tests as before, now as named constants citing the manual pages directly. The
manual's own arithmetic was re-derived independently while sizing this Step:
prior-year 32.000 over 44.000 gives the provisional 73%, current-year 25.000 over
45.000 gives the definitive 56%, 1.280 at 73% gives 934,40, at 56% gives 716,80,
and the difference is -217,60 with direction ingreso, all matching the bundled
manual verbatim.

Verification run: ruff check and ruff format clean on all seven edited files; the
seven affected modules 18 passed; the full prorrata surface across 25 modules 178
passed; the M303 and prorrata grounding suites 177 passed.

## Notes

Semantic discovery was waived for this campaign by operator directive: the
vaultspec-rag index is broken and the service is stopped, so grounding was done
with ripgrep plus whole-file reads and confirmed against the loaded registry
snapshot rather than fragment listings.

The payload key set could not be extended. A peer Step is landing a strict frozen
model over these payloads with `extra = "forbid"`, so a new
`scenario_inputs_by_casilla_id` section would have been refused at the boundary
the moment that model lands, and the module that owns it was out of bounds for
this Step. The house convention already answers this: no bundled payload carries
an inputs section, and the sibling M303 2024 payload documents every raw line item
in its notes prose. The givens therefore moved into the notes and into named test
constants rather than into a new key.

The rename removes the motivating case for the attribution-widening Step that was
sequenced after this one: the payload now attributes by filename, and the fold's
gap set is empty, so that Step is a hardening measure against future payloads
rather than a fix for a live gap. The gap-reader Step's shrink-only floor should
be seeded at zero rather than one.

Work landed in an operator-directed sweep commit rather than under its own
message. The staged set was verified as exactly the nine intended paths, but a
sweep commit of all in-flight work landed between staging and committing and
carried it; the sweep's own message names this rework explicitly. The content was
re-verified intact at HEAD afterwards. Nothing was lost and no destructive
recovery was attempted.

A defect outside this Step's scope surfaced while grounding the retained figure
and is reported rather than fixed. The registry formula for
`iva.prorrata-porcentaje` declares `rounding = "integer"`, which the formula
runtime implements as half-up. LIVA art. 104.Dos.2a and the bundled manual both
require rounding upward, "se redondeara en la unidad superior" and "El porcentaje
aplicable se redondea por exceso". The domain function rounds up correctly, so the
same legal quantity is computed two ways with two different roundings. The two
manual examples happen to have fractional parts above one half, so both roundings
agree at 73 and 56 and neither example discriminates, which is why this survived.
A ratio of 55,2 percent yields 55 from the registry formula and 56 from the domain
function; the registry answer understates the deduction percentage. Fixing it needs
a new rounding code rather than a change to the shared `integer` vocabulary, so it
belongs in its own grounded Step.

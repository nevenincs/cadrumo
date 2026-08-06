---
tags:
  - '#exec'
  - '#conformance-cli'
date: '2026-07-27'
modified: '2026-07-27'
body_hash: 'sha256:70f82d87f907d7b0e3842e073364ba13ccff1ccd11e633dd377583eae9b7a7cf'
step_id: 'S25'
related:
  - "[[2026-07-27-conformance-cli-plan]]"
---

# widen the oracle attribution rule to read the payload declared modelo and filing year rather than keying solely on the filename, once the malformed payload and the casilla 44 modelling have landed, so the corpus enters the honesty relation without false positives

## Scope

- `src/cadrumo/domain/calculations/registry/_external_grounding.py`
- `src/cadrumo/domain/calculations/registry/tests/test_external_oracle_payload_boundary.py`
- `src/cadrumo/domain/calculations/registry/tests/test_external_oracle_grounding_enrolled.py`

## Description

This Step fixed no live defect. Its motivating case was gone before it ran: the
one payload the fold could not attribute was the M303 prorrata oracle, and the
preceding Step renamed it to carry its filing year, which closed the gap by
correcting the payload. The attribution gap set was already empty, at zero of
twenty-one, and it is still empty. What landed here removes the CLASS — the
next payload that arrives without a year in its name, and there is no reason to
believe one will not, no longer falls out of the honesty relation on the
strength of its filename alone.

- Add `_attribution_from_payload_name`, which reads the
  `modelo-<id>-<year>-<scenario>` convention off a payload path and returns
  both axes or neither. The convention encodes the two together, so a name that
  fails the shape carries no partial reading to salvage.
- Rewrite `_read_oracle_payload` to attribute from the DECLARED `modelo` and
  `filing_year` first and fall back to the name, rather than keying on the name
  and using the declared axes only as a cross-check once the name had already
  succeeded. The strict payload models landed by the preceding Step are what
  made this available: the manual worked-example corpus requires both axes, so
  for that corpus a manual payload can no longer be an attribution gap at all.
- Keep the disagreement a refusal. When both readings speak and differ, exactly
  one is wrong and nothing in this function can know which, so it raises quoting
  both readings rather than preferring the declared value. Silently preferring
  either side would attribute AEAT figures to a revision that the other reading
  denies. This answers the instruction the renaming Step left for whoever
  widened attribution.
- Narrow the surviving gap literal's meaning in its own docstring rather than
  renaming it. `payload_name_lacks_modelo_and_filing_year` is now reached only
  when BOTH readings are silent, which for the shipped corpora means a Renta WEB
  Open replay — the corpus that declares neither axis — under a name that
  encodes neither. The token itself is left alone deliberately: a dev-side gate
  outside this Step's bounds constructs it by value.
- Correct the grounding gate's docstring, which claimed the next year-less
  payload would land straight back in the gap set. After this change that is
  true only of a payload no reading can place.

## Outcome

The widening moved nothing. The fold was dumped in full — every evidence
record with its modelo, filing year and casilla ids, every attribution gap,
every unmatched-evidence row, every finding, and all ninety revision rows —
before and after the change, and the two dumps are byte-identical:

```
BEFORE summary: {"attributed": 21, "checked_revisions": 9, "coverage": 0.045995,
                 "declared_groundings": 58, "findings": 0, "payloads_on_disk": 21,
                 "rows": 90, "unattributed": 0, "unmatched_evidence": 0}
AFTER  summary: {"attributed": 21, "checked_revisions": 9, "coverage": 0.045995,
                 "declared_groundings": 58, "findings": 0, "payloads_on_disk": 21,
                 "rows": 90, "unattributed": 0, "unmatched_evidence": 0}
byte-identical full fold: True
```

That is the result the Step was gated on. No payload changed attribution, no
new finding appeared, and no green gate reddened, which was the risk: the
earlier review established that a payload's declared fields and its name can
disagree, and that a payload can carry scenario INPUTS rather than outputs. The
first hazard is now a refusal rather than a silent divergence, and the second
was removed at source by the renaming Step, which took the two volume givens out
of the expected-value map.

Five new cases, all against real bundled payloads with one field or the filename
mutated, each paired with an unmutated control so a refusal can never come from a
fixture that was broken to begin with. A manual payload staged under a year-less
name attributes from its declared axes; a replay payload — which declares neither
— under the same name is still a recorded gap rather than silently dropped;
a declared filing year and a declared modelo each contradicting the name are
refused with both readings quoted; and the whole shipped manual corpus is walked
to prove both readings agree on every file, which is the anti-vacuity floor for
the two contradiction cases. The module is marked `unit`, so the repository's
default lane selects it: `15 tests collected`, `15 passed in 14.04s`, up from ten.

Three mutations flip assertions rather than killing fixtures, each run in a child
process against the real corpus with the source restored byte-for-byte
afterwards and the restore confirmed by digest:

```
control digest 17c5b45d9b8383edda210fc7080998d584bd73244487e0e636410f9b0913d323

=== MUTATION A: attribution reverted to name-keyed only ===
1 failed, 14 passed in 5.65s
FAILED ...::test_a_year_less_name_does_not_demote_a_payload_that_declares_its_own_axes

=== MUTATION B: filing-year disagreement refusal deleted ===
1 failed, 14 passed in 8.88s
FAILED ...::test_a_declared_filing_year_contradicting_the_name_is_refused

=== MUTATION C: both disagreement refusals deleted (declared value silently preferred) ===
2 failed, 13 passed in 5.99s
FAILED ...::test_a_declared_filing_year_contradicting_the_name_is_refused
FAILED ...::test_a_declared_modelo_contradicting_the_name_is_refused

restored digest 17c5b45d9b8383edda210fc7080998d584bd73244487e0e636410f9b0913d323 identical=True
```

Mutation A is the one that matters: reverting the attribution rule to the
pre-change behaviour fails exactly the widening case and nothing else, so the
new case pins the widening rather than merely proving the function was reached.
Every anti-vacuity floor survives all three mutations.

Consumers are unaffected. The grounding gate is `3 passed in 8.05s` with both
honesty directions and the payload-accounting assertion untouched; both modules
together are `18 passed in 20.12s`. The dev-side conformance CLI gate, which
reads the inventory and constructs the gap literal by value, is `31 passed in
44.27s` and was not edited. `ruff format --check` and `ruff check` report
`All checks passed!`, `ty` reports `All checks passed!`, `pyright` reports
`0 errors` (five pre-existing private-usage warnings for the test module's
intra-package imports), and `apidocs scaffold --check` reports `Stub tree is
conformant. No drift detected.` — no module was added, so no stub moved.

## Notes

**Correction: this Step closed without one of its two stated preconditions.**
The originating Step row conditions the widening on it running "once the
malformed payload AND the casilla 44 modelling have landed". Only the first had.
The malformed payload was corrected by the preceding renaming Step, which is
recorded above. The casilla 44 modelling — the M303 regularización prorrata
cuota casilla, which is still an input rather than a computed value carrying the
AEAT manual figure as its oracle expectation — never landed during this Step and
is now tracked as its own Step. This record described neither fact, so a reader
would take both preconditions as satisfied.

It was nonetheless safe to proceed, for a reason this record already evidences
but never connects to the precondition. The preconditions exist so the widening
cannot move an attribution while the corpus is still mid-correction. The
widening moved nothing: the full fold was dumped before and after and the two
dumps are byte-identical, so no payload changed attribution, no finding
appeared, and no gate changed colour. A change proven to be a no-op against the
live corpus cannot be contingent on a corpus correction that has not happened —
the casilla 44 modelling adds a declared grounding, which the fold reads, but it
cannot retroactively alter how a payload that never moved was attributed.

What this Step could not do without the missing precondition is prove the
widening handles the casilla 44 grounding once it exists. That is the honest
residual, and it belongs to the Step that lands the modelling.

**Discovery waiver.** The mandatory semantic-discovery probe was explicitly
waived by the operator for this campaign: the semantic index is broken and its
service is stopped, with a standing instruction not to start, restart, reindex
or otherwise touch it. Grounding was literal search plus whole-file reads of the
grounding fold, both payload corpora, the boundary gate, the grounding gate, and
the dev-side consumers of the gap literal.

The gap literal was deliberately not renamed even though its name is now
narrower than its meaning. A dev-side test module outside this Step's bounds
constructs `UnattributedOraclePayload` with the token spelled out, so renaming
it would have reddened a gate this Step may not edit in order to improve a
docstring. The meaning is corrected where it is declared instead.

One design question was settled against the obvious reading. The disagreement
between a declared axis and the name could have been surfaced as an
`UnattributedOraclePayload` gap row rather than a refusal, which would fit the
screen-not-gate posture the campaign's ADR sets for governance facts. It was
left a refusal: a payload whose two self-descriptions contradict each other is
malformed, not merely unattributable, and downgrading an existing refusal to a
report would weaken a boundary that already holds. The screen posture governs
what the fold REPORTS about a well-formed tree, not whether malformed input is
admitted.

No peer WIP existed on any of the three files at first edit; the working tree
carried a peer's prorrata-rounding change on unrelated registry modules
throughout, untouched here. The commit named its three paths explicitly.

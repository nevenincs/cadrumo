---
tags:
  - '#exec'
  - '#canonical-identifiers'
date: '2026-08-13'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:2edd980fd9cf3b6fd67858c318996841da6a6e8dffe9bfb263211841f6578a88'
step_id: 'S22'
related:
  - "[[2026-08-07-canonical-identifiers-plan]]"
---

# Add a shape-conformance regression over the adopted 8-32 CSV bound pinning its accept and refuse boundaries explicitly, and correct this row's prior claim that the parser-anchor fixtures carry no CSV token. They do. All 60 carry one, 34 distinct, every one 16 uppercase alphanumeric, drawn into the page body by the fixture generators and recorded in each sidecar's replacements_applied list. Construct the boundary value set from the decided bound, covering the shortest and longest accepted forms and the nearest refused ones on each side of both the length and the character-class axis. Keep the corpus sidecar roundtrip replay's corpus inputs and artefact-fidelity behaviour unchanged alongside it, while replacing duplicate local shape checks with the direct canonical predicate, and treat it as this row's control rather than as background. It is the measurement that the legitimate population still passes, and this row does not close until it is green across all 60 fixtures. State in the Step record which claim each instrument proves, shape conformance by the boundary set and artefact fidelity by the fixture replay

## Scope

- `src/cadrumo/domain/justificante/tests/`
- `src/cadrumo/adapters/inbound/justificante/tests/`
- `src/cadrumo/adapters/outbound/aeat/sede/tests/test_declarations_live.py`

## Description

- Add `test_csv_bound_conformance.py` pinning the adopted eight-to-thirty-two
  bound at both of its acceptance surfaces, with every verdict written as a
  literal.
- Cover both axes explicitly: the shortest and longest accepted widths and the
  nearest refused ones on each side, and the accepted character class against
  the nearest refused forms.
- Add two interaction cases proving normalisation cannot rescue an
  out-of-range width.
- Pin the decided bound itself as values, so a widening is a reviewed edit
  rather than something the tree's constant-derived tests absorb silently.
- Run the corpus sidecar roundtrip replay unchanged in its corpus inputs and
  artefact-fidelity behaviour, while correcting its stale local range assertion
  to call the direct canonical predicate.

## Outcome

**Which claim each instrument proves.** The boundary set proves **shape
conformance**: that the adopted bound is actually enforced, at the width and
character-class edges where enforcement either holds or does not, and that it
has not been widened. The fixture replay proves **artefact fidelity**: that the
legitimate population still parses and round-trips through the tightened field
— an entirely different claim, and the one that would catch the tightening
having broken real receipts. Neither substitutes for the other. A boundary set
alone would pass over a parse path that no longer works; a fixture replay alone
would pass over a bound loosened back to anything.

**Two acceptance surfaces, pinned separately.** The same shape is enforced
through two surfaces that deliberately disagree, and conflating them asserts
the wrong verdict for every case-variant input. The **model boundary** — the
retyped receipt csv field — runs the shared normalisation as a before-validator,
stripping and uppercasing *before* its own constraints see the value, so a
lowercase or space-padded token is ACCEPTED-AND-CORRECTED, and the test asserts
both the acceptance and the canonical form it arrives in. The **predicate**
normalises nothing; it answers whether a token already is one complete CSV, so
it REFUSES the same lowercase or padded token. Each is correct for its surface.
The three tokens where the two diverge are additionally listed and asserted as
a divergence in their own right, so the property is stated rather than left
implicit across two tables.

**The boundary set and its verdicts.** On the length axis the shortest accepted
form is eight characters and the longest thirty-two, both accepted by both
surfaces; the nearest refused forms are seven and thirty-three, refused by
both, with the empty string refused by both as well. On the character-class
axis an uppercase-alphanumeric token at mid-window width is accepted by both.
A hyphen separator, an embedded space, trailing punctuation, a non-ASCII letter
and a well-shaped run embedded inside a longer token are refused by both — the
last of these pinning that the match is anchored rather than a substring
search. A lowercase token, a space-padded token and a tab-and-newline-padded
token are accepted-and-corrected at the model boundary and refused by the
predicate. Two interaction cases close the axes against each other: padding a
seven-character token out to thirteen characters is still refused, and
uppercasing a thirty-three-character lowercase token is still refused, so
normalisation cannot buy a value past the width bound.

Thirty-nine cases, all green.

**Every verdict is a literal.** No expectation is derived from the alias, the
predicate or the published length constants at runtime. This is the specific
weakness the row closes: the sibling shape test in the core package builds its
case widths *from* the published constants, so it passes just as happily when
those constants move. This module asserts the constants equal eight and
thirty-two as values, and writes each boundary token out in full, guarded by a
test confirming each literal is the width its name claims.

**The control.** The corpus sidecar roundtrip replay retained its corpus inputs
and artefact-fidelity behaviour and is green: **sixty fixture-parameterised
cases pass**, plus the pair-count guard, sixty-one items in total. Its stale
local eight-to-twenty-four assertion was corrected to call the direct canonical
predicate, so the control now agrees with the adopted eight-to-thirty-two
contract without changing what it replays or proves. This row does not close
without that measurement and it holds.

**Both instruments bite.** The temporary bite proof ran from throwaway pytest
plugins outside the repository tree loaded via `PYTHONPATH`; it did not alter
tracked production or test code for the proof itself. Loosening the bound
in-process to the retired four-to-sixty-four no-pattern shape — the
predicate's pattern swapped, the published constants lowered, the model field
retyped without pattern or normaliser — reds twenty-six of the thirty-nine
cases, including the bound pin itself failing on `assert 4 == 8`, every refused
length case, every refused character-class case and all three divergence cases.
The roundtrip instrument's bite is recorded against its own Step.

## Notes

**Do not overclaim the fixtures.** The sixty sidecars carry sixty tokens,
thirty-four distinct, every one exactly sixteen uppercase alphanumeric
characters. That uniformity is a property of the **sanitiser**, not evidence
about the shape AEAT issues: every fixture token is generator-produced in a
fixed form built from the modelo and year. The fixture replay is evidence about
the parse path and nothing more. The row's prior claim that the parser-anchor
fixtures carry no CSV token is corrected — they carry one each. The fixture
role split is nine parser-anchor and fifty-one formula-verification, all
synthetic-generated.

**No third overlapping home was created.** Two CSV shape test modules already
exist. The core one covers the predicate's character class but parameterises
its widths off the published constants, so it cannot detect the bound moving.
The inbound-adapter one covers the extractor's regex tiers, a different surface
again. Neither reaches the pydantic alias and neither pins the bound as a
value, which is what this module adds; the module's own docstring records that
division so the next reader does not have to re-derive it.

Two tree-wide gates are red at HEAD and neither is owned by this Step: the type
gate at 432 diagnostics across more than 240 files, with the new module in none
of them, and the import-hygiene gate on a test-only private-reach count that
regressed from a documented 94 to a live 107, with the scanner returning zero
sites under this Step's directory. The relative-imports gate is separately red
with six violations in one live-application test module.

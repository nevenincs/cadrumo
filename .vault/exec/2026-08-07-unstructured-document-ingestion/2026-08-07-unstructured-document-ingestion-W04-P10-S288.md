---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-08'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:81f90e20d8b8e12519591902763880efef66107760b6e110cf369c6608cfa94e'
step_id: 'S288'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---

# Give the LLM reader path the country name-to-code resolution the structured e-invoice path already has, since the model reads the country correctly and states it as a printed name (Espana) while supplier_country_code is populated only at _evidence_draft.py 1335 where UBL alpha-2 and Facturae alpha-3 are resolved into one code system - so the capability exists and the reader path simply does not reach it, which is the built-and-unreached shape rather than a missing capability - once wired the field scores against the corpus code representation instead of being excluded as a coverage gap

## Scope

- `src/cadrumo/llm/_evidence_draft_text.py`

## Description

- Resolve the printed country name into a country code on the shared reader
  grounding path, for both the issuing and the billed party, reusing the existing
  vocabulary lookup rather than adding a second one.
- Restore the country leaf to both corpus composites in the ingest harness, pointing
  it at the resolved code field, and delete the interim note that recorded why it was
  unscored.
- Replace the harness test that pinned the interim with one that pins its retirement.
- Cover resolution, non-resolution and name survival from reader-shaped replies.

## Outcome

The reader is asked for the country as the document prints it, because asking a model
for an alpha-2 code would be a translation and translation is inference. Turning that
name into a code is a deterministic lookup against a closed vocabulary. That lookup
already existed, was already exported, and was already used -- but only on the
structured e-invoice lane, where it reconciles the alpha-2 and alpha-3 conventions
those formats disagree about. The reading path carried a correct country name and
derived nothing from it. This is the built-and-unreached shape rather than a missing
capability, and the fix is a call, not a new resolver.

Both properties the row turns on are preserved by the resolver itself rather than by
anything added here. The printed name survives untouched beside the derived code, the
way the numeric fields already keep what the page printed beside what it parsed to; a
derivation that destroyed its input could not be audited. And a name the vocabulary
does not carry produces no code rather than the nearest one -- matching is exact after
normalisation, which is why a misspelling and an uncatalogued name both resolve to
nothing instead of to a neighbour.

The right site was broader than the row's scope. The row names the text reader module,
but both reader lanes ground through one shared function, and that function is where
the draft is assembled. Wiring the shared site covers every caller; wiring the text
module would have covered one.

## Verification

    uv run --no-sync pytest src/cadrumo/llm/tests/test_reader_country_name_resolves_to_code.py -m unit -q -p no:randomly
    6 passed in 9.66s

    uv run --no-sync pytest src/cadrumo/llm/tests -m unit -q -p no:randomly
    455 passed in 61.36s (0:01:01)

    uv run --no-sync pytest dev/ingest_harness/tests/test_field_mapping.py -m integration -q -p no:randomly
    23 passed in 10.76s

The gates were proven to bite by two runtime mutations driven from outside the
repository, each rebinding the resolver in the grounding module's own namespace and
each asserting the window open on a REAL grounded reply before claiming anything:

    scenario=removed: 'Espana' -> None, 'Deutschland' -> None
    window OPEN: the reader path derives no country code
    2 failed, 4 passed in 2.07s

    scenario=defaults-to-spain: 'Espana' -> 'ES', 'Deutschland' -> 'ES'
    window OPEN: every country now resolves to Spain
    3 failed, 3 passed in 1.86s

The two mutations red DIFFERENT sets, which is the result worth having. Removing the
resolution reds only the two cases that assert a code is produced, while the four
absence cases stay correctly green -- that is the pre-wiring state, in which nothing
was wrong, only missing. Making the resolver guess reds the foreign case and BOTH
cases that require an unresolvable name to produce nothing. A single mutation would
have shown the suite responds; two show it distinguishes "not wired" from "wired but
guessing", which are the only two ways this row can be got wrong.

## Notes

**A pre-existing failure, triaged rather than assumed.** One ledger test fails on the
structured path over arithmetic closure. It was attributed by restoring the changed
module's committed bytes, re-running, and observing the identical failure, then
restoring the working copy and confirming the change was still present. It is not
this row's, and it belongs to the in-flight work on the printed-total and suplidos
terms.

**A marker mismatch the runner caught.** The harness suite was first run with the
default marker selection and reported that it had executed zero tests -- a green exit
that selected nothing. The suite carries the integration marker. Reported because the
first reading looked like a pass.

**This change was split by a sweeper, and the halves landed out of order.** The
harness half -- the restored country leaf and the deleted interim note -- was taken
into HEAD by a bare sweeping commit while the wiring half was still uncommitted, so
for a period HEAD scored a leaf whose producer had not landed. The harness test
asserts the MAPPING rather than a produced value, so nothing went red and the split
was invisible to the gates. The wiring half was committed immediately on discovery.

**A catalogue observation, not a matcher one.** Several real country names resolve to
nothing because the vocabulary does not carry them. That is a finding about the
catalogue's coverage and is left as one: widening the matcher to reach them would
reintroduce the near-miss matching the resolver exists to refuse.

---
tags:
  - '#exec'
  - '#canonical-identifiers'
date: '2026-08-13'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:e89327fa5e5aa065040d3ba1f417ae48436e399faa2a7d2961a2f54bd142ce51'
step_id: 'S67'
related:
  - "[[2026-08-07-canonical-identifiers-plan]]"
---

# Retype the SIX further CSV-carrying fields the original rows did not name, on the same adopted bound. THE MEASUREMENT THIS PHASE WAS PLANNED AGAINST WAS INCOMPLETE and this row states the corrected one rather than leaving a reader to re-derive it. The reference and the phase rows both describe three divergent validation strengths across six sites. Re-measured at HEAD immediately before building, the concept spans roughly twelve sites and FIVE strengths -- the documented 8-32 contract inline at four sites, bare str or None at four, the retired 4-64 alias at two, plus TWO strengths named nowhere in the reference or in the phase rows. Those two are verified_justificante_csv at application/overview/_calendar_models.py lines 168 and 329 carrying min_length=1 and max_length=64, and original_csv at domain/filing/_amendment.py line 83 carrying a bare min_length=1. The remaining unnamed sites are justificante_csv at application/filing/_complementaria.py line 66 and verified_justificante_csv at entrypoints/cli/_overview_payloads.py lines 154 and 203, both entirely unconstrained. Rowed as a sibling rather than folded into the phase, because doubling a batch after its rows are written is how scope stops being reviewable, and because a concept-shaped gap left behind a row-shaped close is what this plan already had to correct once in its opening Wave. NOTE that domain/submission/_models.py line 194 is deliberately NOT in this row -- it consumes the JustificanteCsv alias directly, so it must land in whichever commit retires that alias or the retirement is a break rather than a deferral

## Scope

- `src/cadrumo/application/overview/_calendar_models.py`
- `src/cadrumo/domain/filing/_amendment.py`
- `src/cadrumo/application/filing/_complementaria.py`
- `src/cadrumo/entrypoints/cli/_overview_payloads.py`

## Description

- Retype `verified_justificante_csv` on the calendar filing-evidence model and
  on the calendar event model, dropping the `min_length=1, max_length=64`
  bounds those fields carried.
- Retype the same field on the calendar justificante-state carrier protocol,
  which the row's enumeration omitted.
- Retype `original_csv` on the shared amendment record, dropping its bare
  `min_length=1`.
- Retype `justificante_csv` on the submitted-original protocol in the
  complementaria builder.
- Retype `verified_justificante_csv` on both operator-facing calendar payload
  schemas.
- Replace three hyphenated placeholder fixtures the narrowing correctly
  refuses with receipt-shaped values.

## Outcome

Seven declarations across four production modules were re-measured at HEAD and
all seven now name the canonical alias:

- `src/cadrumo/application/overview/_calendar_models.py`, three declarations of
  `verified_justificante_csv`: the state-carrier protocol attribute, and the
  filing-evidence and event model fields.
- `src/cadrumo/domain/filing/_amendment.py`, `original_csv` on the shared
  amendment base.
- `src/cadrumo/application/filing/_complementaria.py`, `justificante_csv` on
  the submitted-original protocol.
- `src/cadrumo/entrypoints/cli/_overview_payloads.py`, `verified_justificante_csv`
  on the calendar filing-evidence and calendar event payload schemas.

The row said six and the measurement says seven, so the discrepancy is
resolved rather than absorbed. Five of the seven are pydantic fields and two
are Protocol attributes. The row's enumeration listed the complementaria
Protocol attribute but omitted the calendar state-carrier Protocol attribute in
a file it had already named. Both Protocol attributes were retyped, because
they exist to describe the shape the concrete models declare, and leaving them
bare would have left the documented shape disagreeing with the validated one.
Neither carries runtime effect; the complementaria module says so in its own
docstring.

The narrowing is real at every site, so what produces each value was checked
before tightening. Every producer is already alias-validated. The calendar
field is written from a parsed receipt's own CSV field, which the justificante
domain schema types on the alias, or from the verified-artefact map, whose
values come from parsing stored receipt bytes and reading that same field. The
amendment field is written from the submitted filing's CSV, which the
submission domain model already types on the alias. The payload schemas are
projected from the application models retyped in this same commit. No site was
found where a legitimately shorter or lower-case value could reach a narrowed
field, so no site was left bare on safety grounds.

The submission domain model site named in the row's tail was confirmed already
done: it consumes the alias directly, having landed with the retirement of the
wider receipt-domain alias.

Three fixtures encoded placeholder identifiers with hyphens, which no AEAT
receipt can carry and which the bound correctly refuses. They were corrected in
the same commit rather than deferred, so the retype and the fixtures it
invalidates land atomically. One of them is an encryption proof asserting the
literal is absent from the database bytes; its literal was updated in step with
the fixture so the proof still bites.

Focused verification: the amendment, complementaria repository, amendment row
identity, complementaria builder and calendar payload suites all pass. The
repository-wide type gate reports no diagnostic in any file this row touched.

## Notes

The two calendar payload schemas are the operator-facing JSON wire surface, so
tightening them changes the advertised JSON Schema for the calendar command:
the affected property gains a minimum length, a maximum length and a pattern
where it previously advertised a plain nullable string. This is intended and in
scope, but it is a wire-contract change and the golden-schema pinning work
needs to know it happened.

The two contended modules were staged through the HEAD-anchored own-only route,
because both carry a concurrent peer's in-flight operator-action work. The
staged hunks were confirmed to contain only this row's lines before committing.

Failures observed in the affected suites that are not this row's and fail
identically without it: agenda cohort partitioning, profile-fact projection,
and a family of export and schema tests failing because a modelo revision
currently resolves no export layouts. The last group is registry work another
campaign is mid-flight on.

One suite run aborted during collection because a peer was writing the registry
tree while the loader fingerprinted it; the run was repeated sequentially.

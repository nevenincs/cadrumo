---
tags:
  - '#exec'
  - '#m303-carry-reconciliation'
date: '2026-08-08'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:80a4dd485683eebf8642195eafa030559912f0e773eb66e0af1f4ef02e79bbc7'
step_id: 'S12'
related:
  - "[[2026-08-07-m303-carry-reconciliation-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace m303-carry-reconciliation with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S12 and 2026-08-07-m303-carry-reconciliation-plan placeholders are machine-filled by
     `vaultspec-core vault add exec`; do not fill them by hand.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar-plan]]' and link the
     parent plan.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

<!-- STEP RECORD:
     This file represents one Step from the originating plan. Identified
     by its canonical leaf identifier (S##) and ancestor display path.
     The Surface the filed disposition from the parsed fichero, which already holds it. REFUSED shape, do not add casillas 72 and 73: the AEAT diseño declares 70, 71, 74, 75, 76 and 77 and not 72 or 73, our export layout carries exactly that set, and AEAT models the disposition as a HEADER at offset 13 plus sin-actividad at offset 391, so two casillas would disagree with the official structure about the concept's kind. THREE FINDINGS FROM THE FIRST WORK, recorded so they are not re-derived. ONE, the value is usable as-is: every field regardless of kind is read through _parse_field_value and appended as a ParsedExportFieldValue carrying raw, a decoded value and a source_locator, so a text header yields a decoded string and the projection change is small. TWO, parsed.fields today has exactly one consumer, _verify_submitted_file_context, which reads only DRAFT-kind fields to cross-check modelo, year and period, so every header field is parsed and discarded. THREE, and this is the blocking design question: NO sibling modelo represents a non-casilla fichero fact anywhere. ObservedCasillaValue requires a casilla_id, there is no ObservedHeaderValue or equivalent, and no observation path surfaces a header. Inventing the first such representation is a design decision to be taken deliberately and NOT settled inside a projection fix, so choose the representation before writing the projection and ## Scope

- `src/cadrumo/adapters/outbound/aeat/sede/_declarations_observations.py`
- `src/cadrumo/adapters/outbound/aeat/sede/_schema.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Surface the filed disposition from the parsed fichero, which already holds it. REFUSED shape, do not add casillas 72 and 73: the AEAT diseño declares 70, 71, 74, 75, 76 and 77 and not 72 or 73, our export layout carries exactly that set, and AEAT models the disposition as a HEADER at offset 13 plus sin-actividad at offset 391, so two casillas would disagree with the official structure about the concept's kind. THREE FINDINGS FROM THE FIRST WORK, recorded so they are not re-derived. ONE, the value is usable as-is: every field regardless of kind is read through _parse_field_value and appended as a ParsedExportFieldValue carrying raw, a decoded value and a source_locator, so a text header yields a decoded string and the projection change is small. TWO, parsed.fields today has exactly one consumer, _verify_submitted_file_context, which reads only DRAFT-kind fields to cross-check modelo, year and period, so every header field is parsed and discarded. THREE, and this is the blocking design question: NO sibling modelo represents a non-casilla fichero fact anywhere. ObservedCasillaValue requires a casilla_id, there is no ObservedHeaderValue or equivalent, and no observation path surfaces a header. Inventing the first such representation is a design decision to be taken deliberately and NOT settled inside a projection fix, so choose the representation before writing the projection

## Scope

- `src/cadrumo/adapters/outbound/aeat/sede/_declarations_observations.py`
- `src/cadrumo/adapters/outbound/aeat/sede/_schema.py`

## Description

- Establish that the parsed export payload already carries the header value in usable form, read at the parser's construction site rather than inferred from the type.
- Establish whether any sibling represents a non-casilla fichero fact, and surface the design choice rather than settling it inside a projection fix.
- Find the existing precedent on second look, after first reporting that none existed.
- Read the discarded header fields and return them keyed by header key.
- Wire them at the capture site.
- Parametrise the verification over four dispositions rather than one.

This record is written by the coordinator after the fact. Its author reached the end of its context and stood down, having verified its working tree clean across every file it touched. The row is left OPEN deliberately, because the work does not yet reach persistence.

## Outcome

The parse-to-projection gap is closed and the projection-to-persistence gap is open. The row therefore stays unchecked.

What landed reads the header fields the observation projection was discarding and returns them keyed by header key, wired at the capture site into the observation's metadata under an `aeat_` prefix. The representation was chosen against the coordinator's authorisation of a new typed header-fact observation, on a precedent the author found by looking again rather than building on its own earlier claim: the filed observation's metadata already carries AEAT's request-type signal off the register row, documented as an AEAT-stated non-casilla fact carried so a later decision can be made against persisted data. That is the same shape, so the precedent existed and had already been read two dispatches earlier without being recognised.

The author then checked whether the typed option was still worth doing, and found that **what it had landed does not reach persistence**. The persisted source metadata is built from a fixed key set that copies exactly one key off the observation, so the new header value is dropped at the persistence boundary. That is the identical defect one layer further down from the one this row exists to fix, and the trap is documented in the very function that would need to change, describing the same thing happening before.

That settles the representation question against what landed, on a reason neither the author nor the coordinator had given: metadata is a flat string mapping and discards the source locator and artefact kind the parser hands back, which the standing grounding requirement forbids. A typed field is also carried structurally and so cannot be dropped by a projection that copies a hand-listed set of keys.

**The row's remaining work is the typed representation, and it is NOT purely additive.** Adding a field to the observation is additive; making it survive requires changing the persistence projection, an existing call site with existing behaviour.

## Verification

    8 passed

Mutation from a plugin loaded outside the repository, restoring the drop-the-headers behaviour: three holders rebound, none still resolving to the original, **3 failed / 5 passed**. The tests that stayed green are the ones pinning the defect described below, which already expect empty, so their survival is correct rather than a gap.

The parametrisation over four dispositions is what turned a working feature into a discovered defect, and it is the most consequential thing in this row:

    C: bytes=7365  PARSE FAIL  payload ended before export record 'modelo-303-page-did'; expected 823, got 18
    I: bytes=7365  PARSE FAIL  (same)
    D: bytes=8188  parsed_ok  fields=191  header=('D','D')
    N: bytes=7365  PARSE FAIL  (same)

Only a refund filing parses, because it carries the bank-details record AEAT needs an account to pay into and the layout requires that record unconditionally. Testing one disposition would have passed on the refund case and shipped.

That defect is rowed separately as `S15`, since it sits in the fichero parse path rather than in this row's scope.

## Notes

Commits: the source was taken into HEAD by a peer's bare whole-index commit under a subject describing unrelated work, and the test landed under its own subject. Both halves are present in HEAD. This record is the only place that attribution exists.

Three limits stated by the author and carried forward rather than resolved:

A full parse roundtrip could not be demonstrated end to end. The minimal draft the roundtrip support builds produces a payload that ends before the expected record, so the finding that the parsed field carries a decoded string rather than a raw slice rests on the parser's construction path and not on a parsed specimen.

The payloads are exporter-produced, so they exercise this layout against this codebase's own writer. No bundled AEAT specimen exists for a non-refund M303 fichero, and a real one could differ.

No bundled facsimile elected devolucion and none filed sin actividad. So the compensacion-versus-devolucion discrimination and the sin-actividad value remain proven in shape and unexercised in value. Now that a disposition can flow for refund filings, that limit will read as demonstrated when it is not, and it belongs in the typed representation's own docstring when that is built, because a record is read once and a docstring is read by everyone who touches the field.

A caveat for whoever fixes `S15`: the three tests pinning the current behaviour must not simply be inverted to assert a disposition comes back. The same parse failure sends the casilla projection into a positional fallback that currently succeeds, so a value will arrive whether or not the layout parse started working. The assertion has to be that the layout path was taken.

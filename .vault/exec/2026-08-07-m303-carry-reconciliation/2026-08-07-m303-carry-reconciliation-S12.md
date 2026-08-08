---
tags:
  - '#exec'
  - '#m303-carry-reconciliation'
date: '2026-08-08'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:6baf86376855cf7f4b17d2c902f65124fa23ad0ef96c46a0a368195a464ffe5e'
step_id: 'S12'
related:
  - "[[2026-08-07-m303-carry-reconciliation-plan]]"
---
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

### Closing half: the typed representation, and it reaches persistence

The remaining work named above is done and the row closes.

`ObservedHeaderFact` is a typed record carrying the header key, the token, the artefact kind and the export parser's own source locator. It lives in `core` rather than beside either surface that needs it, because the outbound AEAT adapter produces the facts and the application persistence payload stores them, and the layered contract puts application below adapters. Core is the one layer both reach without widening a carve-out on an edge that already carries many.

The projection that discarded the fields is now the canonical typed one, and the flat key-to-token mapping is a derived view over it rather than a second walk of the parsed fields. One key wins once, decided in the typed projection, so the two cannot disagree about which of two same-key fields was authoritative.

The fixed key set was deliberately NOT widened. `source_headers` is its own parameter on the observation save, and a test asserts the metadata projection stays header-free. That negative assertion is the discriminating one: without it, a later change could route the facts back through the flat mapping, satisfy every arrival assertion, and silently drop the locators and the types on the way.

`header_key` is a constrained string and not an enum. Measured rather than assumed: 69 distinct values across the bundled modelos, including loader-generated slugs. The registry TOML is the authority for which headers exist, and an enum in core would make core a second authority over registry-driven data.

`source_artefact_kind` is a single-member literal, because only the submitted fichero carries a diseño header today. Unifying it with the casilla observation's five-member sibling is the right end state and is deliberately not done: that literal is a persisted shape, so widening it is a versioned change rather than a rename. The divergence is stated in the docstring so the next reader sees a decision rather than an inconsistency.

The value limit this record asked to be carried forward is now in the type's own docstring, as specified: every value is proven in shape by exporter-produced ficheros, and no bundled facsimile elected devolución or filed sin actividad, so those remain unexercised in value.

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

### Closing half

Strict roundtrip across the encrypted observation boundary with real adapters throughout, real master-key provider, real SQLite engine, real serializer, and every defaultable payload field set non-default:

    uv run --no-sync pytest src/cadrumo/application/calculations/tests/test_observation_header_facts_roundtrip.py -n0 -q -m ""
    3 passed in 46.95s

Setting `member_nif` non-default widens the storage key, so the read goes through the member key rather than the single-filer one. That is part of what the fixture establishes rather than an inconvenience.

The producer end, asserted on what came back OUT of storage rather than on what the capture assembled, because a test checking the observation carried its headers would have passed throughout the entire period the drop existed:

    uv run --no-sync pytest src/cadrumo/application/live/tests/test_filed_header_facts_reach_storage.py -n0 -q -m ""
    2 passed in 58.44s

Mutation from a plugin loaded outside the repository, dropping the typed argument on the way to the payload, asserting the rebinding held the original callable first:

    MUTATION APPLIED: source_headers dropped on the way to the persisted payload (1 holder)
    4 failed, 1 passed in 58.61s

The survivor is the metadata-projection assertion, which touches no persistence and is correct to live.

## Notes

Commits: the source was taken into HEAD by a peer's bare whole-index commit under a subject describing unrelated work, and the test landed under its own subject. Both halves are present in HEAD. This record is the only place that attribution exists.

Three limits stated by the author and carried forward rather than resolved:

A full parse roundtrip could not be demonstrated end to end. The minimal draft the roundtrip support builds produces a payload that ends before the expected record, so the finding that the parsed field carries a decoded string rather than a raw slice rests on the parser's construction path and not on a parsed specimen.

The payloads are exporter-produced, so they exercise this layout against this codebase's own writer. No bundled AEAT specimen exists for a non-refund M303 fichero, and a real one could differ.

No bundled facsimile elected devolucion and none filed sin actividad. So the compensacion-versus-devolucion discrimination and the sin-actividad value remain proven in shape and unexercised in value. Now that a disposition can flow for refund filings, that limit will read as demonstrated when it is not, and it belongs in the typed representation's own docstring when that is built, because a record is read once and a docstring is read by everyone who touches the field.

A caveat for whoever fixes `S15`: the three tests pinning the current behaviour must not simply be inverted to assert a disposition comes back. The same parse failure sends the casilla projection into a positional fallback that currently succeeds, so a value will arrive whether or not the layout parse started working. The assertion has to be that the layout path was taken.

### Residual: nothing refuses a wholesale loss of the header channel

Stated as a residual rather than a caveat, because it is the honest limit of what this boundary can detect.

The anti-tautology proof has two arms and they are not equivalent. Deleting a required field from one persisted fact refuses at load with a validation error, so the typed row is strictly required. Deleting the whole `source_headers` key does NOT refuse: the field defaults to an empty tuple, and it must, because most producers legitimately have no diseño headers and requiring the field would refuse an app filing and an operator-entered row.

So a payload that loses the entire channel re-defaults to empty and loads clean. The only available detection is strict inequality between what was saved and what came back, which the second proof pins directly. There is no refusal to be had here without making the field required, and making it required would refuse legitimate producers.

### Attribution

The source for this closing half landed under peer bare whole-index commit subjects rather than under any subject of mine, as the first half did. One of those sweeps published a broken HEAD: it took the typed projection, which imports the core type, without the core module defining it, so HEAD briefly imported a symbol core did not define. A second sweep took the staged remainder between the add and the commit. This record remains the only place the attribution for either half exists.

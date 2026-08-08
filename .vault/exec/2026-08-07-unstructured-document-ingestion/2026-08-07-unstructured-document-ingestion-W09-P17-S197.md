---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-08'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:5555cc3975d29270d1664803e935b349ba7b584fd9508c7a22f4abab3dde4f86'
step_id: 'S197'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---
# Build the VAT-territory carve-out table

## Scope

- `src/cadrumo/_data/registry`
- `src/cadrumo/domain/iva`

## Description

- Add a legal catalogue entry for Ley 37/1992 art. 3 apartado Tres, the assimilation limb, separate from the existing apartado Dos entry because it rules the opposite way.
- Add the carve-out table recording both directions of art. 3: the territories excluded from the interior del país while sitting inside a Member State, and the territories assimilated to a Member State while sitting outside every one.
- Model assimilation as a pointer to the parent country rather than as a scope, so the answer follows the parent's own status.
- Load the table through the same grounding verifier the territory table uses, so an uncited or unresolvable row refuses at load rather than shipping.
- Consult the carve-outs before the Member State branch in the country resolver, and add their codes to the catalogued vocabulary.
- Gate both directions, the ordering they depend on, and the blast radius of the override.

## Outcome

Twelve territories carried, and the case the table exists for is now fixed rather than merely guarded. Monaco lies outside the Union, every general country register carries it, and it is not a Member State — so the resolver answered third country, which on the issued side is export treatment. Art. 3.Tres says operations with Monaco have the same consideration as operations with France. It now resolves exactly as France does.

Assimilation is a pointer and that is the substantive design choice. The article fixes what a territory is treated AS and says nothing about what the parent establishes, so a row freezing a scope would have been correct in 2015 and wrong from 2021 while still reading as grounded. The Isle of Man is the proof: it followed the United Kingdom into the Community and then out of it without the article changing a word, and the row reproduces that because it never names a scope. The gates assert agreement with the parent rather than a literal, for the same reason — a literal passes identically today and stops being about the law the moment a parent's status is what moved.

The excluded territories carry a scope directly, because there the exclusion and the answer are one provision read twice: art. 3.Dos.1 puts them outside the interior del país and art. 3.Dos.3 then defines any territory outside it as a third territory. Åland, the five French overseas territories and the two Channel Islands are the ones with alpha-2 codes of their own, so they are the ones answerable from this evidence.

The Spanish codes are the deliberate refusal. Canarias and Ceuta y Melilla are excluded by the same provision and would be defensible as third territories in pure tax terms, but this codebase models them as their own scopes so a Canarian party is not flattened into the same value as a Japanese one, and the postal rung owns the sub-national evidence that picks between them. So the rows record that the codes are KNOWN and leave the scope to the postal rung. That is not a null change: before them, an operator was told these were codes the system does not carry, a data gap somebody should close. They are a decision, and now they report as one.

The widening guard was the acceptance test and it passed without being relaxed, going from trivially green to green for a reason.

## Verification

The provision text read from the bundled consolidated law before anything was authored, and the required-text check confirmed to be ANCHOR-scoped rather than a whole-law substring match:

    'recargo de equivalencia'   in_whole_law=True  in_art3_anchor=False
    'Principado de Monaco'      in_whole_law=True  in_art3_anchor=True
    'esto no aparece...'        in_whole_law=False in_art3_anchor=False

The middle row is the citation; the first is the control that makes the third meaningful, since a check against the whole six-hundred-thousand-character law would have passed on it.

Resolver behaviour after wiring:

    MC: scope=eu_member     status=catalogued
    IM: scope=third_country status=catalogued
    AX GP MQ GF RE YT JE GG: scope=third_country
    IC: scope=None status=catalogued
    EA: scope=None status=catalogued
    ES: scope=None  FR: eu_member  GB: third_country  US: third_country

Gates:

    uv run --no-sync pytest src/cadrumo/domain/iva/tests/test_vat_territory_carve_outs.py -n0 -q -m unit
    22 passed in 3.06s

    uv run --no-sync pytest src/cadrumo/domain/iva/tests/test_country_vocabulary_widening_guard.py -n0 -q -m unit
    17 passed in 2.89s

    uv run --no-sync pytest src/cadrumo/domain/iva/tests src/cadrumo/application/ledger/tests -n0 -q -m "unit"
    2 failed, 1751 passed, 22 deselected, 16 warnings in 133.16s

    uv run --no-sync pytest src/cadrumo/domain/iva/tests src/cadrumo/application/ledger/tests src/cadrumo/domain/calculations/registry/tests -n0 -q -m "integration"
    1 failed, 44 passed, 5582 deselected in 93.86s

Mutation proof, from a plugin outside the repository restoring the pre-table behaviour by emptying the carve-out lookup:

    [mutation] carve-out table removed
    [mutation] emptied table consulted 8 times
    12 failed, 27 passed in 0.99s

The consultation counter is the control: an emptied table the resolver never asked would leave the gate green for a reason unrelated to the gate being sound.

## Notes

Six territories the article names are deliberately absent and are a report rather than rows. Helgoland and Büsingen, Livigno, Campione dItalia with the Italian waters of Lake Lugano, Monte Athos, and the sovereign base areas of Akrotiri and Dhekelia have no alpha-2 code of their own, so none can be keyed by the evidence this table is read with. Inventing a key for them would be inventing evidence. They are sub-national territories reachable only by sub-national evidence, the same shape the Spanish postal table already solves for Canarias and Ceuta, and closing them needs that evidence for Germany, Italy and Greece rather than another row here.

The consolidated article reads oddly on two points and the text is right both times. It still excludes the Channel Islands as United Kingdom territory and still assimilates the Isle of Man to the United Kingdom, because its last redaction predates the end of the transition period. Neither is stale in effect: the United Kingdom is no longer a Member State, so both now reach the third-country answer through their parent rather than through the exclusion, which is exactly why assimilation is modelled as a pointer.

Three failures in other lanes were left alone and are not this change. Two ledger preflight tests expect a domestic-identification-on-intra-community reason and receive a missing-identification-state one; both were already red before this row and belong to the preflight lane, where four sibling failures have since been fixed by their owner. One registry test reports unenrolled computed casillas on modelos 303 and 390, which is the modelo registry lane and touches no country evidence.

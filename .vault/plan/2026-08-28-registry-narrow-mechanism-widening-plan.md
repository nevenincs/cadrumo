---
tags:
  - '#plan'
  - '#registry-narrow-mechanism-widening'
date: '2026-08-28'
tier: L2
related:
  - '[[2026-08-28-registry-narrow-mechanism-widening-adr]]'
  - '[[2026-08-28-registry-narrow-mechanism-widening-research]]'
modified: '2026-08-28'
body_schema: body-v2
body_hash: 'sha256:d9bf271eb976e309c7ce0c9926b91a400e76c9bfa622c0cd3f65a57aeeb540f0'
---

# `registry-narrow-mechanism-widening` plan

## Description

## Steps

### Phase `P01` - Decision C: the live blank-emission path

M720 is the only one of the three defects that can produce a wrong file today, so it goes first. The enum member, its mesh enrolment and the M720 re-source land together; none is useful alone, and an unenrolled kind resolves silently to blank, which is the failure being closed.

- [x] `P01.S01` - Add the constant-supplying `BindingSourceKind` member to the canonical core enum, per the accepted taxonomy ADR's procedure: value equal to the stored registry token, with the registry-versus-enum parity gate green in the same change. This is the ONLY live defect of the three -- M720 currently prompts the taxpayer for AEAT's own record-type marker and modelo number, the prompt is answerable-blank, and a blank emits at @1 and @2-4 behind a valid digest. Do NOT reach for an inline literal: that was tried and reverted because three tests pin 'M720 must represent every casilla through a binding, never an inline export field'; `src/cadrumo/core/aggregation.py and the registry-versus-enum parity gate`.
- [x] `P01.S02` - Enrol the constant source kind on the live calculate mesh, or register it explicitly deferred, so it is never a novel unrouted kind. The aggregation rule is categorical: every binding `source` kind must belong to the enrolled-or-explicitly-deferred set, and `collect_unhandled_source_diagnostics` must see it on the live path -- a kind that is neither compiles and silently resolves to blank, the exact failure this decision closes. Prefer enrolment over deferral: the resolver is trivial because the value is carried on the binding itself; `src/cadrumo/application/aggregation/_source_mesh.py and src/cadrumo/application/modelo/_calculation_actions.py`.
- [x] `P01.S03` - Re-source M720's four constant bindings from `manual_input` to the constant kind, carrying the values the diseno states -- '1' and '720' on type_1, '2' and '720' on type_2 (aeat-dr-720, 01-720-599-kb-pdf.pdf: 'Constante numero 1.', 'Constante <<720>>.', 'Constante 2.', 'Constante 720.'). VERIFICATION IS THE POINT OF THIS ROW, not the edit: the three M720 contract tests must stay GREEN, because they are the proof the fix preserved the binding-derived design rather than routing around it. Then confirm both design sheets JOIN their record and that coverage reports zero complaints through the real per-record join rather than the weak any-record fallback, and delete the two M720 entries from the join ratchet; `src/cadrumo/_data/registry/aeat/modelos/720/revisions/2013-y-siguientes/bindings and the join ratchet gate`.

### Phase `P02` - Decisions A and B: the latent gaps and the admission gates

M165's undescribed span and M303's unproven coverage are latent rather than active, so they follow C. The gates close the phase because a declaration mechanism without a both-directions ratchet decays into the honour system it replaced.

- [x] `P02.S04` - Add the fourth `RecordDesignCorrection` kind for a mis-declared range START, enforcing its precondition at EXTRACTION rather than asserting it in prose: admissible only where no field is described in the vacated span in ANY bundled edition, so it can move a filler boundary and can never invent or displace a data row. Declare M165's `02-165-orden-hap-2455-2013.pdf` as its first subject, citing the two sibling editions that publish '102-500 BLANCOS' where the 2013 orden says 104. It joins the existing discriminated union feeding `RecordDesignExtraction.corrections`, so the worklist keeps treating 'corrected' as distinct from 'complete' with no per-kind branch; `src/cadrumo/domain/calculations/registry/record_design_schema.py and record_design.py`.
- [x] `P02.S05` - Stop the auxiliary-envelope header contract pinning slots that are not structural. REWRITTEN 2026-08-28 to match the amended decision B: this row previously said to widen the shape test to a declaration and declare M303's DP30300, and that remedy was WRONG because its premise was. MEASURED: DP30300 matches every structural criterion the recogniser tests -- 13 fields, terminal extent exactly 328, no declared total -- so `_auxiliary_envelope_header`'s shape test PASSES. It is rejected inside `RecordDesignAuxiliaryEnvelopeHeader` on slot CONTENT, for two causes that must not be conflated. Slots 0, 1 and 2 differ only in SPELLING: AEAT writes 'Constante "<T"' in M390's design and a bare '"<T"' in M303's, likewise 'Constante "0"' against '"0"' and the modelo constant; both spellings assert the identical constant, and this is the same variance the row parser already tolerates for naturaleza tokens. Slot 4 differs SEMANTICALLY and is the real blocker: its role is named ANNUAL_PERIOD and pinned to the literal '"0A"', but M390 is annual while M303 is quarterly and monthly, so M303's slot reads '"01"..."12" o "1T"-"4T"' -- a range, not a constant. THE FIX IS TO REMOVE AN ACCIDENTAL PIN, and this codebase has already fixed one instance of the same class: the comment at `_AUXILIARY_ENVELOPE_HEADER_MODELO_INDEX` records that pinning the modelo slot made the contract single-modelo by accident, since every other structural check was already modelo-neutral. The period slot is that same accident one axis over. So the contract keeps asserting STRUCTURE -- roles, lengths, rows, ordinals, extent, and the tag constants that make it an envelope -- and stops asserting the filing CADENCE of whichever modelo carries it, with the period slot accepting the period vocabulary the revision's own selector declares. MUST NOT disturb M232's DR23200 or M390's own page zero, both of which classify correctly today; verify both before and after. Do NOT declare DP30300 an exception: that would freeze a spelling and a cadence difference as a carve-out and leave the next modelo of the same shape hitting the same wall; `src/cadrumo/domain/calculations/registry/record_design_schema.py and record_design.py`.
- [x] `P02.S06` - Give each of the three admissions a both-directions gate, modelled on the provenance-only design exclusion that already works this way: the declared set must be NON-EMPTY, so a dropped declaration cannot turn the mechanism into a rigorous-looking no-op, and every member must STILL need its admission, so a case that stops needing one is deleted rather than left standing. A declaration mechanism invites use, and the research records the discrimination that must survive it -- only an UNCONDITIONAL constant on a blank-capable channel is a defect, while `filler` for M714's 'Constante. Blanco' and M369's conditional '[blanco | constante C]' are correct as they stand. If these admissions start absorbing those, the widening has failed and the gates are what will say so; `the three admission gates under registry tests`.

## Parallelization

## Verification

---
tags:
  - '#exec'
  - '#registry-temporal-coverage'
date: '2026-08-25'
modified: '2026-08-26'
body_schema: 'body-v1'
body_hash: 'sha256:897bfdf375bd9cde8df5f4efb26a9da18c6293299bfb4fe91b6b11be3b69e114'
step_id: 'S51'
related:
  - "[[2026-08-14-registry-temporal-coverage-plan]]"
---
# Acquire and hash-pin the missing historical design eras or constrain unsupported claimed years for Modelos 126, 128, 165, 181, 184, 270, 308, 309, 341, 353, and 576, and adjudicate Modelo 180 ejercicio 2022 on the presentation axis, until the whole-tree claimed-year layout-design gate passes without backdating a newer design or inventing temporal coverage

## Scope

- `src/cadrumo/_data/corpus/aeat_official/disenos_registro`
- `src/cadrumo/_data/registry/aeat/modelos`
- `src/cadrumo/domain/calculations/registry/tests/test_layout_design_applies_to_claimed_years.py`

## Description

- Reproduce the claimed-year gate before editing and preserve its exact live
  divergence census.
- Use VaultSpec RAG to confirm that S51 is the existing owner and avoid creating
  duplicate per-modelo plan rows.
- Acquire official historical AEAT design bytes for Modelos 126, 128, and 181.
- Record exact hashes, byte counts, applicability windows, and source-catalogue
  enrollment without attaching a source to a revision whose geometry has not
  passed coverage validation.

## Outcome

Progress only; this Step remains open.

Commit `69fdf248bc` added five official PDF artefacts and their canonical
manifest and legal-source records. Modelo 126 now has a 2015--2019 design,
Modelo 128 has a 2015--2019 design, and Modelo 181 has distinct 2009, 2016, and
2017 artefacts. Live SHA-256 and byte-count checks match every recorded value.
Corpus/hash tests pass 6 of 6 and source-grounding plus referential-integrity
tests pass 30 of 30.

Current HEAD later attached the exact 2015--2019 and 2020 sources to the M126
and M128 parent layouts. Commit `f662296b22` proves 2019 selection, 2018
refusal, full Page-1 geometry, the narrowly governed combined trailing
`En blanco` filler, and a mutation that reopens the mandatory offset-12 byte.
The isolated selection passes six tests and the existing focused modelo
selection passes twelve. This resolves the original 2019 claimed-year
divergences without backdating selection into 2015--2018.

Commit `2c327ae64c` then added the official Modelo 165 original 2013 design and
official 2016 update with exact hashes and applicability windows of 2013--2015
and 2016--2022. Canonical corpus sync passes for 68 required URLs and 58
manifests, and the registered-design parser test passes. These are acquisition
facts only; no layout or revision source join was claimed.

Commit `7f870ade0b` adds the official Modelo 341 `dr341_2005.pdf`, 44020
bytes with SHA-256 `c1c59a...95c3d`, and scopes its factual authority to
2005-02-01 through 2015-12-31. Corpus sync passes for 69 required URLs and 58
manifests, and the focused acquisition/source-enrollment selection passes five
tests. It remains acquisition-only because 2000--2004 has no matching source
and the required geometry comparison is unavailable during the active registry
relocation.

Commit `63135011cc` adds six official AEAT historical artefacts for Modelos 308
and 309, atomically enrolling their URLs in the canonical synchronizer and
removing the matching historical exclusions. Modelo 308 now has exact 2009 to
July 2011, July 2011 to 2015, and 2016 to 2018 source bytes; Modelo 309 has exact
2004 to 2015, 2016 to 2017, and 2018 to 2022 bytes. Canonical sync passes for 75
URLs and 58 manifests, the corpus proof passes two tests, and the focused 308/309
registry selection passes 17 tests in a detached worktree at the commit.

Commits `422bc44a47` and `97d8650bff` add and independently prove five official
Modelo 353 historical artefacts: the 2008-order and v1.3 PDFs, 2015--2016 XLS,
2017--2019 XLSX, and 2020 XLS. Canonical sync now passes for 80 URLs and 58
manifests; the detached source proof passes seven tests. Only the exact
2015--2016, 2017--2019, and 2020 windows are declared. The structurally differing
older PDFs remain source-only rather than being backdated across the current
2008--2025 revision.

No revision span, export layout, or claimed-year verdict changed in that
commit. The whole-tree claimed-year gate therefore remains the acceptance
criterion, not the acquisition count.

## Notes

The former M126/M128 combined-blank parser blocker is resolved by the generic
coverage authority and the direct isolated proof above. Their pre-2019 years
remain deliberately unselected; the evidence acquisition is not authority to
rewrite legal history or widen a calculation-grade revision.

M181 remains unsupported for 2010--2015 and 2018--2021. The acquired historical
files do not justify backdating or closing those years. The remaining S51
modelos likewise require official historical authority or an evidence-backed
source-era/export ruling; narrowing legal selection spans merely to green the
gate is forbidden.

Modelo 165 remains unjoined because the official original type-2 table has a
real position gap from 102 to 103, so attaching it to the sole open-ended
layout would overstate coverage. Modelo 270's 2013 BOE annex establishes the
historical era, but the corpus currently has no canonical generic BOE-PDF
acquisition route; the current 2023 AEAT design must not be backdated.

Modelo 576 remains an evidence blocker: the historical AEAT index exposes no
positional design, while the BOE 2005, 2007, and 2021 annex chain is graphical
form evidence rather than a parser-usable writer contract. The 2007 order is
effective only from 2008 and therefore cannot establish the missing 2007
geometry.

The 308/309 sources remain acquisition-only until canonical revision-era joins
are authored. Modelo 308 additionally exposes a real selector limitation: the
official design changes inside July 2011, while its current AD-HOC selector can
express only a year boundary. No legal span was narrowed and no later design was
backdated. The whole claimed-year gate is presently unable to reach these
assertions because the active Modelo 200 lane leaves the bundled registry red.

Modelo 353 still requires evidence-backed selector and layout-era splitting for
pre-2021 years. Its already-landed 2026 successor and deadline authority were
not modified. The focused test loads only the canonical Modelo 353 directory and
IVA catalogue so unrelated Modelo 200 full-tree failures cannot masquerade as
evidence for or against this acquisition.

Commit `61cdab0e89` attached the already acquired finite 2015--2019 sources for
Modelos 126 and 128 at revision, layout, and export application-link authority.
It changed no field-level 2020 source reference, selector, grade, geometry, or
export semantics. Generic obligatory-blank coverage and its ordinary-field
negative proof pass, and both historical binaries match the catalogue.

The live whole-tree gate now excludes Modelos 126 and 128 and retains ten
divergences: Modelos 165, 181, 184, 200, 270, 308, 309, 341, 353, and 576.
Modelo 180 is no longer divergent. Modelo 200 is a real 2024-exercise versus
2025-design mismatch governed by the accepted partition ruling and is now
re-carried as a separate temporal Step. S51 remains open until all remaining
divergences are resolved without backdating or invented authority.
## M181 successor-window refusal (2026-08-26)

The official amendment chain establishes the proposed successor boundaries but
not an attachable multi-era export claim: Orden EHA/3514/2009
(BOE-A-2009-21165) is followed by Orden HFP/1923/2016
(BOE-A-2016-12114, first applicable to the 2016 declaration) and Orden
HFP/1192/2022 (BOE-A-2022-20274, first applicable to the 2022 declaration).

The canonical `resolve_record_design_binary` path verified the existing hashes
and byte counts in-memory at the proposed windows: `aeat-dr-181-2009` through
2015, `aeat-dr-181-2016` in 2016, `aeat-dr-181-2017` through 2021, and
`aeat-dr-181-2022` from 2022. However, the canonical strict parser refuses a
coverage claim for every historical binary: the 2009, 2016, and 2017 PDFs each
read two records but report an unidentified restarted record body (at source
rows 455, 376, and 371 respectively). Only the 2022 PDF reads complete. The
strict export-layout coverage helper requires complete source extraction, so
there is no valid geometry proof that the current `modelo-181-fichero-2022`
layout may cite any historical source.

Accordingly this bounded probe changes no M181 applicability metadata, source
attachment, revision selector, authority grade, or layout geometry, and adds no
mutation test for a claim the parser cannot prove. Adding the historic sources
to the layout to silence the claimed-year gate would manufacture multi-era
layout authority. S51 remains open. The whole claimed-year gate was also
unrunnable in the shared worktree because the concurrent Modelo 200 partition
lane currently declares duplicate `modelo-200-2025-0a` deadline ids; that
independent loader refusal does not alter this M181 result.

## M341 historical-layout correction (2026-08-26)

The canonical `resolve_record_design_binary` and generator intermediate were
re-read before authoring. No resolver, selector, validator, producer enum, or
other Python authority was redeclared. The generic strict parser reads the
historical PDF completely as one 619-position record with twenty contiguous
fields, and the generic export-layout coverage validator accepts the authored
record with no gaps.

Modelo 341 now has two selectable layout eras: the bounded `2005-2015`
revision cites only `aeat-dr-341-2005-2015`, while `2016-y-siguientes` cites
only `aeat-dr-341-2016` and retains its materially different variable envelope
plus 800-position page. Filing years 2000-2004 select no revision because no
positional design has been acquired; no later design is backdated to make those
years appear supported. Both revisions remain applicability grade and
agent-reviewed, so the byte/layout proof does not claim filing eligibility or
operator review.

Five focused tests prove the exact historical offsets, hash and source window;
the unsupported 2004 refusal and both real selector boundaries; complete
generic byte coverage; a widened-selector ambiguity mutation; and an offset
mutation that reopens the official `@24+13` position. Modelo 341 passes its
focused `RegistryValidator.validate_modelo` gate. The whole-tree claimed-year
test remains independently blocked by the concurrent Modelo 200 partition's
registry validation failures. This bounded result does not alter that tree and
does not close S51, whose row still owns the other modelos.

## Whole-registry reconciliation (2026-08-26)

The later canonical revision-era joins for Modelos 308, 309, and 341 are now loaded by the bundled authority, so the earlier acquisition-only checkpoint is superseded. Their isolated era/layout modules pass, but the authoritative whole-registry validator exposes committed cross-revision residue that those focused checks did not exercise.

Modelo 308 carries amendment-level legal refs on the 2011-julio-2015 `decl.ejercicio` and `decl.periodo` casillas even though the same semantic casillas retain the underlying approval authority in adjacent eras. Modelo 309's 2004-2015 historical casillas reuse successor semantic roles with incompatible types or constraints, and two historical-only situation roles lack explicit singleton adjudication. Modelo 341 incorrectly marks two presentation roles as intentional singletons even though they co-apply in Modelo 309.

These are genuine S51-owned defects, not grounds to reopen a checked export-adjudication row and not permission to absorb the active Modelo 165 or Modelo 200 lanes. S51 remains open. Closure requires the isolated era proofs, the whole semantic-role/referential gate, and the claimed-year layout-design gate to pass after the active lanes settle.

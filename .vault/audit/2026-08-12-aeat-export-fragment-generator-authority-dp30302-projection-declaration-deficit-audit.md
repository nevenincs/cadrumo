---
tags:
  - '#audit'
  - '#aeat-export-fragment-generator-authority'
date: '2026-08-12'
modified: '2026-08-12'
body_schema: 'body-v1'
body_hash: 'sha256:66719998a9f69bdd635200bbfa750f1c35454ea088b71e01e453a27ce621f515'
related:
  - "[[2026-08-10-aeat-export-fragment-generator-authority-plan]]"
---

# `aeat-export-fragment-generator-authority` audit: `dp30302 projection declaration deficit`

## Scope

Audited whether the next open Step of this campaign, the authoring of reviewed Modelo 303
semantic maps and source-bound render profiles for the five design epochs, can form the
exact anchor bijection its own acceptance contract requires. The audit was triggered by
attempting that Step and finding the anchor set unsatisfiable, not by a scheduled sweep.

Every number below was measured, not estimated. Anchors were loaded through
`load_record_design_intermediate` against the five hash-pinned official binaries named in
the source catalogue. Admissible semantic homes were read from the live loaded snapshot
through `ValidatedRegistryAuthority`, never from a directory listing and never from the
withdrawn manual export tree.

The parser side is sound and is explicitly not a finding. The five epochs yield 406, 406,
426, 429 and 430 anchors counting the thirteen DP30300 prefix slots, which equals the
census contract the campaign already wrote down. Sources, hashes and epochs all resolve.

## Findings

### dp30302-projection-declaration-deficit | critical | The sole admission door for projection entries declares 34 simplified endpoints against 142 simplified anchors, so no exact bijection is authorable

The revision-owned projection endpoint declaration index is, by the accepted design, the
only door through which a semantic-map projection entry may be admitted: the map validator
requires every declared endpoint to appear exactly once and refuses any map reference the
revision does not admit. That index therefore caps the number of projection entries a map
may carry at exactly the number of declarations.

Each of the five selected revisions declares 108 endpoints. Of those, 25 prorrata-activity
and 36 differentiated-deduction endpoints carry official numbered boxes in the 500-524 and
700-735 ranges, 12 exonerado-390 activity endpoints plus one operaciones-con-terceros
endpoint serve DP30304, and the remaining 34 serve DP30302.

DP30302 needs far more than 34. Excluding numbered boxes, source-declared constants and
reserved runs, the record carries 135, 131, 141, 143 and 143 anchors across the 2023,
2024-early, 2024-late, 2025 and 2026 epochs. One anchor in each is the página-complementaria
indicator, which is a producer field; the remainder, 134, 130, 140, 142 and 142, are
simplified-regime anchors. Against 34 declarations that is a shortfall of roughly 108 per
epoch and about 518 across the campaign's five targets.

The shortfall is structural rather than a rounding gap, and its shape is specific. The
declared module endpoints cover the non-agricultural cohort only, activity slots 1 and 2
only, module orders 1 through 7, and two value axes, which is exactly 28. The declared
activity endpoints cover only `activity_code` for the two agricultural slots and only
`iae_epigrafe` for the two non-agricultural slots, which is 4. One fact endpoint per
non-agricultural slot covers `cuota-devengada-operaciones-corrientes`, which is 2. The
official design meanwhile gives the agricultural cohort ten fields per slot across two
slots, being código, volumen de ingresos, índice de cuota, cuota devengada, porcentaje,
ingreso a cuenta, cuota soportada and the fourth-quarter result among them, and gives the
non-agricultural cohort 122 anchors across its two slots. Every agricultural field except
`activity_code`, and every non-agricultural per-activity scalar except the one declared
fact, is undeclared. Those scalars include reducciones, índice corrector de actividad, the
1T/2T/3T percentage and ingreso a cuenta, the 4T cuotas soportadas, the 4T resultado, the
cuota mínima percentage and amount, devolución de cuotas soportadas, cuota anual derivada,
and the temporada day counts.

No alternative home absorbs them. The selected revision carries 40 non-numeric casillas, of
which only ten are simplified-regime related, being the seven `modulos-iva-N-unidades`
entries plus `modulos-iva-orden-id`, `modulos-iva-cuota-devengada` and
`modulos-iva-cuota-derivada`, and those describe a single activity rather than the official
multi-slot design. All 35 bindings on the revision are general-regime IVA liquidation
concepts and none addresses a simplified-regime per-activity scalar. The closed producer
vocabulary holds 32 keys covering presenter, taxpayer, amendment evidence, selected account
and the Modelo 303 identification flags, and none is a simplified-regime row value. The
four draft attributes are filing year and period only.

The consequence is that the map-authoring Step cannot be completed honestly as written. The
bijection validator refuses a map that omits an anchor, and the projection validator refuses
a map that invents a reference the revision does not admit, so there is no compliant way to
place roughly 108 anchors per epoch. The two non-compliant escapes are precisely the ones
this campaign exists to prevent: reclassifying live simplified-regime fields as filler, or
widening the map schema so an undeclared reference is admitted without grounding. Both would
produce a structurally complete file that silently under-declares for every simplified-regime
filer, which is the failure the plan's own census Step was designed to catch.

### s50-structural-coverage-claim-outruns-declared-authority | high | A closed Step's recorded outcome counts the anchors it covers but its declarations do not reach them

The Step that owns the simplified-activity and module row authority is closed and its
execution record states that every nonnumbered DP30302 field is projected through exact
revision-aware source anchors, reporting nonnumbered field counts of 134, 130, 140, 142 and
142. Those counts reproduce exactly against the official binaries, so the record's census is
accurate and was not fabricated.

What does not follow is the coverage claim. A later Step made the revision-owned declaration
index the sole admission door for projection entries, and that index declares 34 simplified
endpoints. Whatever the projector can enumerate internally, only 34 simplified anchors can
reach a generated layout. The record's own phrase, structurally covered, is therefore true of
the counting and false of the routing, and nothing in the closure distinguished the two.

This is the failure mode the campaign's orchestration discipline names directly: delivered
as specified, delivered narrower, and recorded but not implemented all wear the same
checkbox. The record is not dishonest, but it was accepted against a coverage question it
did not actually answer, and the deficit surfaced only when a downstream Step tried to
consume the authority.

### absent-numbered-boxes-referenced-by-official-design | medium | Five official numbered boxes appear in the design but not in the target revisions

Every epoch's design carries numbered boxes that the corresponding revision does not define:
box 46 once, box 110 twice, box 78 once and box 69 once, consistently across all five epochs.
These are separate from the simplified-regime deficit and are small enough to be a genuine
authoring gap rather than a structural one, but they will each refuse the map's casilla
reference check and so must be resolved before the map Step can close. They are recorded here
so the map author does not rediscover them as five unexplained validator refusals.

### absent-numbered-boxes-finding-corrected | low | Four of the five reported absent boxes were an artifact of my own matching, and the fifth is a numbering gap rather than a missing casilla

Correcting the finding above rather than rewriting it, because the original entry is what a
reader would otherwise carry forward. Two errors were mine.

First, box extraction. Several official descriptions state a formula before naming the
field's own box, as in the sum of results reading `( [46] + [58] + [76] ) [64]`. Matching the
FIRST bracket takes a formula operand instead of the field's identity. The field's own box is
the TRAILING bracket. Under the first-bracket rule I reported boxes 46, 110 twice, 78 and 69;
under the correct trailing-bracket rule the candidate set is 46, 110, 78, 87 and 69, so the
original list both double-counted 110 and missed 87 entirely.

Second, and more consequential, resolution key. I checked candidates against casilla `id`
when the official box number lives on casilla `number`. Four of the five resolve immediately
once keyed correctly: `iva.compensacion-pendiente-periodos-anteriores` carries number 110,
`iva.compensacion-aplicada-periodo` carries 78, `iva.compensacion-pendiente-periodos-posteriores`
carries 87 and `iva.resultado` carries 69. They are fully defined, semantically keyed by id
and officially keyed by number, which is the dual-keying this campaign already settled. They
were never missing.

Re-measured against `number`, exactly one box is genuinely absent, and it is the same one in
every epoch: box 46, the general-regime result in DP30301, at ordinal 79 for 2023 through
2025 and ordinal 86 for 2026. The concept is present as `iva.resultado-regimen-general`, but
that casilla's `number` repeats its own id instead of declaring 46, while its four
`compensacion` and `resultado` siblings all declare theirs. So this is a numbering gap on an
existing casilla, not a missing definition, and the fix is to declare the official number on
the casilla that already exists rather than to author a new one. Authoring a second casilla
for box 46 would create exactly the duplicate official-box authority the campaign forbids.

The map author should therefore resolve numbered anchors against casilla `number`, and should
expect one grounding action here rather than five.

### absent-numbered-boxes-finding-withdrawn | none | There is no absent box at all; the official number lives on a second field and every numbered anchor resolves

Third and final refinement of the same finding, appended rather than substituted because the
sequence of three successive corrections is itself the evidence that this surface is easy to
measure wrongly. The finding is now WITHDRAWN in full.

The compiled casilla schema carries two number-bearing fields, `number` and `form_number`. I
measured only the first, in both earlier passes.

The root cause is worth more than the answer, because the next author will reach for the same
shortcut. The very first probe dumped the casilla and filtered the output to a key list that had
been guessed in advance, naming `id`, `number`, `official_number`, `kind`, `label` and
`legal_refs`. `form_number` was present in the model the entire time and the filter discarded it.
Both later measurements then inherited that blind spot without ever re-examining it. The lesson,
stated so it can be reused: filtering a dump to fields you expect, rather than reading the field
set first, is what turns one mistake into three. Read the field set, then filter. `iva.resultado-regimen-general` does declare
its official box: `form_number` is `46`. Nothing is missing, and the numbering-gap conclusion
in the previous correction was wrong in the same way the original finding was wrong, one field
later.

Re-measured across every numbered anchor in all five epochs, resolving against the union of
`number` and `form_number`, the absent set is empty: 174, 174, 182, 182 and 183 numbered
anchors, zero unresolved. There is no box work in this campaign.

The corpus-wide picture explains why the field exists and is worth recording, since the map
author will meet it. Of 16,800 casillas across the loaded corpus, 15,990 carry a numeric
`number` and no `form_number`, 790 carry a semantic `number` and no `form_number`, and only 20
carry `form_number` at all, spread over modelos 180, 190, 303, 349 and 390. In 180, 190, 349
and 390 the pattern is coherent and deliberate: `number` holds a byte range such as `145-160`
for a declarant-summary record while `form_number` holds the printed sequence number such as
`02`. So `form_number` is the sanctioned home for the printed number wherever `number` is
already carrying a different coordinate.

Modelo 303 uses it exactly once, on this casilla, whose `number` degenerately repeats its own
id rather than carrying a competing coordinate. So relative to its 181 numbered siblings the
casilla is stylistically anomalous, while being entirely correctly declared. That is a
cosmetic inconsistency and explicitly NOT a grounding defect. It should not be "tidied" as a
side effect of this campaign: `number` is consumed by other surfaces, and rewriting it to `46`
to match its siblings is a change with consumers, not a formatting fix. It needs its own
justification if anyone ever wants it.

The operative rule for the map author is therefore: resolve a numbered anchor against `number`
first and `form_number` second, and treat neither alone as the official-number authority.

### second-consumer-confirms-the-projection-admission-gap | high | A generation gate independently hits the same declaration requirement, so the deficit is not bookkeeping

The deficit above was found by attempting to author semantic maps. A second, unrelated consumer
reaches the same wall from a different direction, which is worth recording because it changes how the
blocker should be read.

The variable-envelope generation gate fails on all five Modelo 303 epochs with "semantic map omits
target-revision projection declarations", enumerating the differentiated-deduction endpoints from
casilla 700 onward. Its harness declares no projection endpoints, while the selected revision demands
that a map account for all 108. The failure is reproducible sequentially and was proven independent
of unrelated in-flight work by reverting that work and observing identical failures.

So the revision-owned projection admission is not merely inconvenient for a map author; it is already
red for a generation gate that predates the contract. Two consumers, reached independently, both stop
at the same requirement.

That strengthens the case that the declaration deficit is a real structural blocker rather than a
bookkeeping gap, and it means closing it unblocks more than the map rows. It also means the five
failures should NOT be repaired by relaxing the projection bijection or by teaching the harness to
skip it, because both would remove the very check that surfaced the missing declarations twice.

A measurement caution attached to the same run, since it nearly produced a false report. The suite
first appeared to carry twelve failures under parallel execution. Re-run sequentially it carries five,
with the totals reconciling exactly at 236 either way, so seven were execution artefacts of parallel
runs on this backing share rather than genuine failures. The project's own guidance to re-run
sequentially before triaging registry failures existed and had not been applied; applying it changed
the answer. Only the five are real.

## Recommendations

Close the deficit before attempting the map Step again. A plan row now carries this work and
is sequenced ahead of the map authoring; it must extend the grounded declaration index and
its producing authority to every official DP30302 anchor, for both cohorts and every official
activity slot, leaving no anchor unhomed. The extension is registry authoring work and must
carry real legal and source grounding per endpoint rather than a mechanical fan-out of the
existing declarations, because the agricultural and non-agricultural cohorts are governed by
different provisions and the fourth-quarter fields are governed differently from the
1T/2T/3T fields.

Resolve the five absent numbered boxes in the same pass or in an adjacent row, deciding per
box whether the revision should define it or whether the anchor belongs to a non-casilla
home. Do not resolve them by widening the casilla check.

Treat the coverage-versus-routing distinction as a standing acceptance question for the rest
of this campaign. Where a Step claims that a set of official fields is covered, the closing
evidence should name the admission door those fields actually pass through and show the count
on both sides of it, since a census of the anchors alone demonstrably passes while the routing
is short by three quarters.

Do not narrow the map Step's acceptance contract to match what is currently declarable. The
census Step downstream already fixes the required per-epoch classification counts, and
lowering the map contract to fit the deficit would silently move the campaign's completion
criterion rather than meet it.

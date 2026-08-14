---
tags:
  - '#audit'
  - '#registry-campaign-sequencing'
date: '2026-08-14'
modified: '2026-08-14'
body_schema: 'body-v1'
body_hash: 'sha256:af2c0e8f669b767ecdd668e87ede5168e054d31dee6712058b18ad79279c93e6'
related:
  - "[[2026-08-14-registry-campaign-sequencing-audit]]"
  - "[[2026-08-14-registry-campaign-sequencing-operator-attestation-ledger-audit]]"
  - "[[2026-08-14-support-removal-fabricated-grounding-audit]]"
---

# `registry-campaign-sequencing` audit: `Figure reconciliation at HEAD`

## Scope

Every headline figure currently circulating for this campaign — in the working
continuity scratchpad, in the operator-attestation ledger, and in team-lead's
reports to the operator — re-derived independently against the registry tree
at HEAD on 2026-08-14, using `load_registry_tree` and the production
reference-collection helpers directly rather than grepping the filesystem, per
the assignment's method constraint. Every number below comes from a Python
script that loads the real compiled model and reads it, or from calling the
real span-gate test function directly (bypassing a live, unrelated tree-wide
collection break in `conftest.py` by importing the test module through its
proper package path rather than through pytest). Nothing was taken on trust
from another document.

## Findings

### Figure reconciliation at HEAD | info | CONFIRMED: 78 revisions across 66 modelos declare no export layout

`load_registry_tree` over 73 modelos / 97 revisions: 78 revisions carry an
empty `export_layouts` tuple, spanning 66 distinct modelo ids. The two
superseded figures (41, 82) are not reproducible by any measurement this
script performed and are consistent with team-lead's stated reasons for
discarding them (41 was a completeness-manifest-gated subset; 82 predated
Modelo 390 regaining its four layouts). **78/66 is confirmed exact.**

### Figure reconciliation at HEAD | info | CONFIRMED: the attestation surface (97/0, 633/220/413) is exact

Revision review status: 97 total revisions, all 97 `pending_review`, zero
`operator_reviewed` — confirmed tree-wide, no exceptions found. Legal
catalogue: 633 total entries, 220 `operator_reviewed`, 413 `agent_reviewed`
(sums exactly; `LegalReviewStatus` has no third non-pending member, so this
is the complete partition). **Both figures confirmed exact.**

### Figure reconciliation at HEAD | info | CONFIRMED: the seven-modelo aggregate (256/95/161/19, per-modelo breakdown) is exact

For the seven layout-bearing modelos (100, 131, 145, 180, 349, 390, 720),
walking every layout-bearing revision through the real production reference
collector (`_collect_snapshot_ref_ids`, the exact function
`_build_validated_snapshot` calls to determine the legal-review slice) and
unioning the legal-ref ids:

```
union of distinct legal refs           : 256
  already operator_reviewed            :  95
  remaining                            : 161
revision stamps (do not share)         :  19  (100:6 131:4 145:1 180:2 349:1 390:4 720:1)
remaining per modelo                   : 100:119 131:25 145:4 180:2 349:9 390:11 720:0
```

Every one of these numbers reproduces team-lead's circulated figures exactly,
including the specific per-modelo stamp counts and the specific per-modelo
remaining-ref counts (Modelo 100 carrying 119 of the 161 remaining refs).
**Confirmed exact, digit for digit.**

### Figure reconciliation at HEAD | info | CONFIRMED: Modelo 720 is one act from filable, including the 43-field/2-record layout claim

Modelo 720 revision `2013-y-siguientes`: `review_status = pending_review`
(needs the one stamp), 8 distinct legal refs in its derived slice, **zero**
not `operator_reviewed` — all 8 already attested. Its declared export layout
carries two records (`modelo-720-type-1`, `modelo-720-type-2`) each pointing
at a `binding_record` rather than literal field TOML, so the DECLARED field
count reads 0/0 — exactly the trap the continuity scratchpad's own CAUTION
section warns about. Running the real production derivation
(`derive_export_layouts_from_bindings`, the same call `_build_validated_snapshot`
makes before the filing-capability check) resolves the binding-derived
coordinates: **13 fields on `type-1`, 30 on `type-2`, 43 total across 2
records — confirmed exact.** "One act from filable" holds: the only
remaining gap for this modelo is the single revision stamp.

### Figure reconciliation at HEAD | info | CONFIRMED: Modelo 390's four revisions are closed-ended, 2022-2025 only

All four Modelo 390 revisions load with a fully bounded `valid_from`/`valid_to`
pair confined to their own calendar year (`2022`: 2022-01-01 to 2022-12-31;
`2023`: 2023-01-01 to 2023-12-31; `2024`: 2024-01-01 to 2024-12-31; `2025`:
2025-01-01 to 2025-12-31), each carrying exactly one export layout. No
revision is open-ended and none extends into 2026 or before 2022 — confirmed
directly from the loaded `valid_from`/`valid_to` fields, not inferred from
revision-id naming. **Confirmed as stated.**

### Figure reconciliation at HEAD | info | CONFIRMED: the M303 "double-count" retraction is correct

Enumerated every M303 binding's declared fields directly (not probed with a
defaulted `getattr`) across all five revisions. The `applied_rates` field
genuinely exists and is populated, and the values are disjoint exactly as the
retraction states: super-reducido cuota/base bindings carry `(0.04,)`;
super-reducido-transitorio bindings carry `(0.02,)`; the ordinary reducido
bindings carry `(0.10,)` against the reducido-transitorio bindings' `(0.05,
0.075)` two-step window — identical across 2023, 2024-hasta-08-y-2t,
2024-desde-09-y-3t, 2025 and 2026-y-siguientes. There is no field-name
overlap and no shared rate value between an ordinary and a transitorio
binding at any revision. **The retraction is independently confirmed: there
is no double-count.**

### Figure reconciliation at HEAD | critical | CONTRADICTED: the temporal-coverage classification "7 gap / 9 clean / 57 undecidable" does not hold at HEAD

Called `test_every_modelo_revision_span_is_corpus_proven_never_undecidable`
directly (its own real implementation, not a re-derivation) and parsed its
assertion message line by line rather than trusting a summary. The PROVEN GAP
modelo list matches exactly: **200, 220, 303, 322, 353, 604, 714 — 7 modelos,
confirmed.** Everything past that does not hold:

- **UNDECIDABLE is 67 modelos, not 57.** 85 individual revisions across 67
  distinct modelos have fewer than two comparable bundled design years inside
  their claimed span. This is not a rounding difference — it is off by 10
  modelos, and it exactly matches the test's OWN docstring ("67 modelos carry
  at least one UNDECIDABLE revision"), so the test and its docstring agree
  with each other and disagree with the circulating 57.
- **There is no "PROVEN CLEAN" bucket of 9 modelos.** Of the nine modelo ids
  the scratchpad lists as proven clean (036, 100, 115, 123, 130, 131, 202,
  222, 390), seven of them — 036, 100, 115, 123, 130, 222, 390 — appear in
  the UNDECIDABLE list with **zero** clean revisions; none of their revisions
  pass. Only two of the nine, 131 and 202, have ANY passing revision at all
  (131's `2024-y-siguientes`-era 2019-2023 span; 202's 2019-2022 and
  2023-2024 spans), and even those two modelos are NOT fully clean — each
  carries other revisions (131's 2024/2025/2026; 202's 2025-y-siguientes)
  that are themselves UNDECIDABLE. The test's own docstring states this
  outcome explicitly: **"0 of 73 modelos have EVERY revision proven clean."**
  A "PROVEN CLEAN" figure of 9 is not a stale count of a real category — the
  category itself does not exist at the modelo level; the property is proven
  or unproven per REVISION, and the test's own docstring names this exact
  modelo-level-tally mistake as the wrong measurement it replaced.
- **The categories are not mutually exclusive, so a 7+9+57=73 partition was
  never going to be structurally sound.** Modelo 303 itself appears in BOTH
  the PROVEN GAP list (three of its revisions: `2009-y-siguientes`,
  `2024-desde-09-y-3t`, `2024-hasta-08-y-2t`) and the UNDECIDABLE list (its
  remaining revisions have fewer than two comparable years). A modelo-level
  partition that assumes one bucket per modelo cannot represent this, and the
  real per-revision total (9 gap + 85 undecidable + 3 pass = 97) is the only
  count that reconciles against the true revision total.

The real, current, reproducible tally: **9 PROVEN GAP revisions across 7
modelos; 85 UNDECIDABLE revisions across 67 modelos (with overlap: modelo 303
contributes to both); 3 PASS revisions across 2 modelos; 0 of 73 modelos
fully clean.** This is not a new finding — it is the number the test's own
docstring already states, reproduced independently — but the "7/9/57"
framing that has been circulating is wrong on the count and wrong on the
structure, and should stop being cited.

### Figure reconciliation at HEAD | high | This session's own prior ledger audit carries a now-stale figure

The `registry-campaign-sequencing-operator-attestation-ledger-audit` document
(this same session, item 1) states: "Exactly 6 of 73 modelos... declare any
`export`/`export_layouts` directory at all: `100`, `131`, `145`, `180`,
`349`, `720`" and separately states Modelo 390 "are not among them." Both are
now false. The current loaded tree shows **7** layout-bearing modelos — the
same six plus Modelo 390, which carries all four of its revisions with real
resolved export layouts (`m390_layout_count = 4`, confirmed above). This
matches the continuity scratchpad's own (correct) figure and the sequencing
audit's Tier-1 status update noting Modelo 390 as complete and its owning
agent freed for reassignment. The tree moved between when that ledger item
was written and now — Modelo 390's layouts were restored after the ledger was
published — so this is a timing gap, not a fabrication, but it is exactly
the kind of thing this reconciliation exists to catch, including in this
session's own prior output. That ledger item should be corrected to read "7
of 73... including Modelo 390" the next time it is touched.

## Recommendations

Cite `78 revisions / 66 modelos with no export layout` and the
`97/0, 633/220/413` attestation-surface figures as settled — they reproduce
exactly and should not need re-verification unless the tree changes again.
Same for the seven-modelo aggregate (256/95/161/19) and the Modelo 720 and
Modelo 390 findings.

Stop citing "7 proven-gap / 9 proven-clean / 57 undecidable" anywhere it
still appears. Replace it with: 7 modelos carry a proven-gap revision (named
above), 67 modelos carry an undecidable revision, only 2 modelos (131, 202)
have any proven-clean revision at all, and 0 of 73 modelos are fully proven
clean. If a compact framing is needed for the operator, "0 of 73 modelos are
fully corpus-proven; 7 have a confirmed layout defect, the rest lack
sufficient bundled-design evidence to judge" is accurate; a three-bucket
modelo-level partition is not, structurally, regardless of the numbers put
in it.

Correct the `operator-attestation-ledger` audit's item 1 to say 7 of 73
modelos (not 6), including Modelo 390, the next time that document is
amended — flagging here rather than editing it now, since amending it is
outside this document's own scope and it should carry its own explicit
amendment note the way its Modelo 720/2026-map correction did.

No figure in this reconciliation was found to overstate risk — every
correction found here (the undecidable count, the fabricated "proven clean"
bucket, this session's own stale 6-of-73) makes the coverage gap look WORSE
or DIFFERENTLY SHAPED than circulated, never better. That asymmetry is worth
naming on its own: nothing in this pass surfaced an overcautious figure that
could be relaxed.

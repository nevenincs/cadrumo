---
tags:
  - '#audit'
  - '#registry-campaign-sequencing'
date: '2026-08-14'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:0d5da04f004e6d830922c8bd1817bc5f8dda8f87eec73a768fc4b97d0d15c5ab'
related:
  - '[[2026-08-10-aeat-export-fragment-generator-authority-plan]]'
  - '[[2026-08-08-aeat-design-relayout-boundary-plan]]'
  - '[[2026-08-14-registry-temporal-coverage-plan]]'
  - '[[2026-08-13-registry-suite-red-at-head-plan]]'
  - '[[2026-08-10-legal-corpus-vintage-plan]]'
  - '[[2026-08-14-registry-campaign-sequencing-audit]]'
---

# `registry-campaign-sequencing` audit: `Operator attestation ledger`

## Scope

Five registry campaigns are in flight at once, each carrying rows that no agent may
close because they need a human operator's judgement or signature. Per the
`2026-08-14-registry-campaign-sequencing-audit` finding `narrowing-not-recorded`,
these rows are spread across at least three plans with no single list, so the
chain can read complete while several attestations sit unapplied. This document
is that list: every operator-gated item across the five campaigns named in
`related:`, swept row by row rather than trusted from a prior summary, ordered so
the items that unblock the most work come first.

Three items below are not yet plan rows at all — a standing gate an operator
directive is putting in place right now, a data-entry re-stamp the sequencing
audit's Tier 0 finding surfaced, and a ruling raised in this session's
Modelo 303 2024-late semantic-map audit — because an operator ledger that only
echoes existing checkboxes would miss exactly the kind of gate this document
exists to catch.

**Amendment note (2026-08-14, same day as first publication):** item 1 below
was added after the rest of this ledger was written, on explicit correction
from team-lead. The original top item's premise — that a green registry load
unblocks evidence for all five campaigns — still holds on its own terms
(confirmed below: a new fail-closed policy is landing at the FILING boundary,
not the load boundary, so concurrent campaigns keep working), but it is no
longer the load-bearing fact: closing it produces a registry that loads
cleanly and still cannot emit a single filing artifact for the modelos that
matter most. Item 1 outranks everything else in this document for that reason.

## Findings

### Operator attestation ledger | critical | 1. The application cannot produce a filing artifact for IVA, sociedades, or most of the retención family — this is the standing purpose gap, and it outranks every attestation below it

**Where:** not a plan row; a standing fact about the tree, and the object of a
genuine, operator-issued directive (confirmed via team-lead, not executed by
me) to make the registry refuse at the filing boundary until it closes. The
directive is being scoped and recorded as its own decision record by another
agent, citing the sequencing audit — not this ledger, and not me.

**What I independently confirmed, directly against the tree today:**
- **CORRECTION, made explicit rather than silently fixed:** this bullet
  originally read "exactly 6 of 73 modelos... declare any `export`/`export_layouts`
  directory" and listed Modelo 390 as NOT among them. That was measured by a
  raw directory grep at the time and has since been superseded — a same-session
  independent reconciliation
  (`2026-08-14-registry-campaign-sequencing-figure-reconciliation-audit`, using
  `load_registry_tree` rather than a directory listing) found the true count is
  **7 of 73**, because Modelo 390 regained all four of its revisions' real,
  resolved export layouts after this bullet was first written (another agent's
  work landing mid-session on this shared worktree, not an error in either
  measurement at the time each was taken). The corrected set is `100`, `131`,
  `145`, `180`, `349`, `390`, `720`. Modelo 303 and the Impuesto sobre
  Sociedades modelos (`200`/`220`) are still not among them — IVA's Modelo 303
  half and sociedades still have no path to a filing artifact, and most of the
  retención family (everything except 131/145/180/349) still does not either —
  so the correction narrows which modelos are blocked, it does not change the
  standing purpose gap this item exists to report.
- Modelo 303 does not have an `export`/`export_layouts` directory in the tree
  today; instead each revision carries a `support_removal_decisions/`
  directory. History is more tangled than "never" on a literal reading — an
  `export/` directory with real content was added by `ddbae9f538` and touched
  by several later commits before being removed during the multi-revision
  split churn — but the operative fact team-lead's directive rests on is
  current-state, and that holds: there is no Modelo 303 export layout on disk
  right now.
- Modelo 390 lost its export layouts THE SAME DAY, in the annual-epoch split
  commit `f9f3f77704` — confirmed directly: that commit adds
  `0001-export-layout-support-removal.toml` files alongside the split, one per
  revision. It has since regained all four (see correction above); recording
  both facts because the loss was real and dated, and so was the recovery.
- I traced every production consumer of `support_removal_decisions` /
  `SupportRemovalDecision` myself (grep across `domain/` and `application/`,
  excluding tests): identity validation (`_validate_revision_identity.py`),
  id-reference integrity (`_validate_references.py`, `_ids.py`), closure
  checks (`_validate_revision_closure.py`), and `application/registry/_conformance.py`
  (report/CLI payload counts). None of these sit on `application/filing/` or
  `adapters/outbound/aeat/export/` — I grepped both directly and found zero
  production references. Team-lead's correction holds: this declaration is
  not a fail-closed guard on export. It records "there is no layout here"; it
  does not create one, and deleting the record would not either.

**What is already prepared toward closing it, confirmed directly rather than
taken on trust:** four of the five Modelo 303 epoch maps are authored and
green as of this check — `2023` and `2024-early` are committed (with the
casilla-154 amendment from item 3 below), `2024-late` and `2025` are
uncommitted but pass their full epoch-scoped suite (re-ran
`test_modelo_303_semantic_maps.py -k "2025"` myself: 28 passed). The fifth,
`2026`, is NOT yet green — I re-ran its epoch-scoped tests directly and got 56
errors, not the "all green" this item was drafted to report. The task list
shows another agent actively mid-edit on the 2026 map right now, in this same
shared worktree, so this is very likely a live snapshot rather than a stalled
row — but I am recording what I measured, not what I expect to be true
shortly. The deterministic generator, hash-pinned sources, and render-profile
mechanism this all builds on are separately built and green (Waves W01–W03 of
the export-fragment plan, closed). `W04.P07.S20` is the row that atomically
generates and publishes the real Modelo 303 export tree from this authority
once all five maps are closed — it is what turns "reviewed maps exist" into
"the application can emit a filing artifact."

**What is missing:** the 2026 map closing (in progress); then `S52` (the
exact-anchor census gating on all five maps); then `S20` itself; Modelo 390's
own five-epoch map set (`S79`–`S82`, all still open per my earlier
reconciliation this session); and the Impuesto sobre Sociedades / Modelo 200
export layout, which is entirely unscoped in any of the five campaigns this
ledger covers as far as I can find — worth flagging upward as a gap in its
own right rather than assuming it is someone's row.

**What stays blocked until this lands:** everything downstream of `S20` in the
export-fragment plan (`S16`, `S91`, `W04.P08` release), the temporal-coverage
campaign's owned-tree sweep, and — per the operator directive — production
filing itself, by design, once the new standing gate lands. This item is
ranked first because closing every attestation in items 2–8 below produces a
registry that is fully signed off and still cannot file anything for its two
largest modelos.

### Operator attestation ledger | critical | 2. Re-stamp one Impuesto sobre Sociedades orden entry — unblocks evidence for all five campaigns

**Where:** not a plan row. `legal."orden-hac-657-2025:modelo-200"` in
`src/cadrumo/_data/registry/aeat/legal/is.toml` (the sibling entry
`legal."orden-hac-657-2025:art-3"` carries the identical gap and is fixable in
the same sitting). Surfaced by the sequencing audit's `review-status-collision-corrected`
finding.

**What the operator must decide:** whether the bundled BOE-A-2025-12818 excerpt
this entry cites genuinely supports the required-text phrases already recorded,
and if so, re-stamp `review_status` from `agent_reviewed` to `operator_reviewed`
with a real `reviewed_by`. This is a plain read-and-confirm, not a determination.

**What is already prepared:** `corpus_ref`, `document_id`, `effective_from`, and
four `required_text` phrases are authored and grounded against the bundled
corpus. The entry approves Modelo 200 for periods started in 2024, which is
exactly the filing-grade authority the generated export-tree validation checks
for. Routing around it was tried and honestly refused: a fabricated corpus
reference is refused by the build validator, a mismatched required-text phrase
is refused, and the only OTHER operator-reviewed orden entry in this catalogue
(`orden-hfp-816-2017:art-1`, confirmed by direct read) approves Modelo 232, a
different modelo — citing it for Modelo 200 would be a false grounding claim,
not a workaround.

**What is missing:** the operator's own reading and re-stamp. Nothing else.

**What stays blocked until this lands:** per the sequencing audit's own Tier 0
ruling, no registry campaign can produce verifiable evidence until the
review-status collision closes, and this is the one subject in that collision
that is a genuine attestation gap rather than a fixture bug — the other seven
subjects the audit found were mistyped test fixtures requesting a grade their
own tests never claimed, already correctable by an agent. This is the
highest-leverage item among the ATTESTATIONS in this ledger: one entry, fully
prepared, blocking all five campaigns' ability to prove anything against a
warm registry load — though, per item 1 above, a warm load is a narrower win
than filing capability, since the two gates now operate at different
boundaries. Team-lead's brief additionally reported twelve filing-grade
validations in
`dev/registry/tests` depending on this entry; I confirmed the entry, its
grounding, and the false-grounding refusal directly, but did not independently
recount that test figure — a targeted collection run did not reproduce a clean
count under this worktree's marker configuration, so treat "twelve" as reported
rather than re-verified.

### Operator attestation ledger | high | 3. Legal corpus vintage — re-stamp two prepared candidate diffs, escalate one wrong-provision determination

**Where:** this ledger item is the sole outstanding-attestation owner. Its
production targets are `src/cadrumo/_data/registry/aeat/legal/irpf.toml` and
`src/cadrumo/_data/registry/aeat/legal/iva.toml`; the immutable candidate and
falsifier evidence lives in
`.vault/exec/2026-08-10-legal-corpus-vintage/2026-08-10-legal-corpus-vintage-P02-S03.md`
and `...-P02-S04.md`. The originating plan's retired S08/S09 rows no longer
act as a second human task queue.

**What the operator must decide, per entry in `src/cadrumo/_data/registry/aeat/legal/`:**
- `ley-35-2006:art-81` (`irpf.toml`) — confirm three present-clauses (the
  complemento de ayuda para la infancia exclusion, the three-year adoption
  window, and a 150-euro post-alta increment that specifically needs the
  operator's own live BOE reading because it is a money amount) and one
  absent-clause (the repealed per-hijo Seguridad Social cotizaciones ceiling),
  and confirm the vintage move of `effective_from` from 2007-01-01 to
  2023-01-01 on BOE-A-2022-22128.
- `ley-37-1992:art-122` (`iva.toml`) — confirm three present-clauses (apartados
  Uno, Dos, Tres), one absent-clause (the superseded eligibility sentence), and
  the vintage move of `effective_from` from 1993-01-01 to 2016-01-01 on
  BOE-A-2014-12329, which the plan flags as a determination rather than a
  lookup since three modifying laws touch the article.
- `ley-37-1992:art-124` — NOT a re-stamp. The article in force governs the
  régimen especial de la agricultura, ganadería y pesca while the entry's
  notes, `required_text`, and cited excerpt all describe obligaciones formales
  del régimen simplificado — a wrong-provision defect. The operator must first
  determine which provision now carries that obligation, then choose repoint,
  renumber, or retire, then sweep the Modelo 303/390 surfaces citing it. No
  candidate diff is offered deliberately, so this is a genuinely open
  determination, not a pending signature.
- A fourth, carried in from the advisory-grounding campaign because it surfaced
  on the same article: `art-81` in force contains the string `cotizaci` exactly
  once (the 30-day alta rule), so no cotizaciones bound on the guardería
  increment survives in current text, yet a live advisory
  (`guarderia_cotizaciones_ceiling_unbounded`) and a registry formula still
  assert one. Whether that advisory is correctly scoped per filing year is a
  tax review against each Modelo 100 revision, recorded here rather than acted
  on. The direction matters: a surviving repealed ceiling caps a deduction
  BELOW entitlement, which overpays, produces valid output, and raises no
  refusal — the unwatched direction this project has already been burned by
  once.

**What is already prepared:** the first two candidates are fully authored —
every phrase, its PRESENT/ABSENT disposition, the apartado to read it in, and
what observation would falsify it — sitting in the exec records above, checked
against the bundled corpus plus a live BOE cross-check.

**What is missing:** the operator's own live BOE reading and re-stamp for the
first two; a provenance-grounded provision determination for art-124 (no
candidate exists to review — this is authored from scratch by whoever makes the
call); and a tax review of the guardería advisory's per-year scope.

**What stays blocked until this lands:** applying either candidate still
requires the operator's reading, a real commit, and a green registry load at
that commit. The art-124 determination and its Modelo 303/390 citation sweep,
plus the guarderia per-year review, remain open here until explicitly
adjudicated. The completed legal-corpus-vintage implementation and its
dev-screen rows do not wait on those external human acts.
The prepared first two decisions remain cheap to close, which is why this item
ranks above entries still waiting on agent work.

### Operator attestation ledger | high | 4. Rule on the Nota 7 foral-filer allowance before the next Modelo 303 epoch map is authored

**Where:** not yet a plan row anywhere. Raised in
`.vault/audit/2026-08-14-aeat-export-fragment-generator-authority-s69-m303-2024-late-semantic-map-audit.md`
and independently corroborated by the sequencing audit's `nota-7-uniform-gap`
finding. Bears on the still-open export-fragment rows `W04.P07.S70` and
`W04.P07.S71` (the 2025 and 2026 Modelo 303 epoch maps).

**What the operator must decide:** whether the permissive Nota 7 allowance
("Tributación exclusivamente a una Administración Foral... se podrán
cumplimentarán con el valor '00000'"), which spans exactly ten DP30301 rate and
recargo fields across every bundled 2024-late design and is currently
implemented on NONE of them, should be wired through the existing
"foral taxation" identification producer key as a conditional override, or
left deliberately unimplemented as a documented policy choice (writing the real
rate is compliant since the note is permissive, so no filing is wrong today —
this is a missing convenience, not a defect).

**What is already prepared:** the gap is fully measured — all ten affected
ordinals identified (29, 32, 35, 38, 47, 50, 53, 56, 81, 84 in DP30301), the
uniform-not-inconsistent finding confirmed directly against both the bundled
xlsx design text and the TOML entries, and the existing foral-flag producer key
that a routed implementation would attach to already located.

**What is missing:** the ruling itself. This is a five-minute policy call, not
a research task — the two options and their consequences are both already
written down.

**What stays blocked until this lands:** nothing is hard-blocked, since Nota 7
is permissive and every current epoch map is correct without it, but the
sequencing audit's own finding warns that leaving it unruled risks the same gap
being silently re-decided differently per epoch as `S70` and `S71` are
authored. Ranked above the export-fragment worklist rows below because it is
fully prepared and sits on the currently-active campaign's critical path,
unlike those, which still need substantial agent work before there is anything
to review.

### Operator attestation ledger | medium | 5. Registry-suite-red-at-head — four rulings, one of which may resolve to "retire the row" rather than "decide it"

**Where:** `.vault/plan/2026-08-13-registry-suite-red-at-head-plan.md`. This
plan carries no authorising ADR; its own Description records that gap rather
than silencing it, and names two of these four rows as needing one before
execution.

- `P03.S14` (open) — "Attribute the bundled Modelo 303 published designs for
  2015 and model the 2018 mid-course AEAT split as its own revision pair."
  **Flag before ruling:** the sequencing audit's `duplicated-ruling` and
  `excluded-scope-re-proposed` findings show this re-decides a question the
  `aeat-design-relayout-boundary` campaign already owns and already ruled OUT
  of the prescripcion-reachable window (both 2018 and the 2015 boundary are
  recorded there as deliberately refusing rather than modelled). The likely
  correct operator call is to retire this row into the relayout campaign's
  existing row rather than execute it standalone — the sequencing audit's
  Tier 4 recommendation says exactly that. Confirm this before treating it as
  an open design decision.
- `P01.S04` (open) — "Widen the registry verify verb to cover relation offset
  periods and export-layout population, or make it enumerate the invariant
  families it does not check." The operator decides whether to widen coverage
  or disclose scope; this changes what an operator-facing CLI command asserts,
  so the plan reserves the call.
- `P03.S12` (open) — author the missing Modelo 232 revision `2016-2017`
  envelope header/footer export-layout fragments, or retire the empty
  directory if the revision is genuinely layout-less. Choosing wrongly either
  fabricates AEAT structure or silently narrows declared coverage.
- `P03.S15` (open) — narrow the Modelo 720 revision `2013-y-siguientes`
  claimed filing years to those its declared layout design covers, or declare
  the design that covers 2012. Same author-it-or-retire-it shape as S12.

**What is already prepared:** for all four, the plan states the two-way choice
and the risk of choosing wrong; no candidate diff or draft exists for any of
them.

**What is missing:** the ADR the plan's own Description calls for, covering at
minimum `P01.S04` and `P03.S14`, before either executes; and for `P03.S12`/`S15`,
someone to actually read the cited AEAT source and pick a side.

**What stays blocked until this lands:** the plan's remaining thirteen rows do
not depend on this ADR and may proceed independently per its Description — these
four are narrow, self-contained blockers on their own four rows only, not on
the rest of this plan or on other campaigns.

### Operator attestation ledger | medium | 6. Export-fragment legal worklists (`S88`/`S89`/`S90`) — derive the live population before operator action

**Where:** `.vault/plan/2026-08-10-aeat-export-fragment-generator-authority-plan.md`,
rows `W04.P07.S88` (shared), `S89` (Modelo-303-only), and `S90`
(Modelo-390-only) — all open. The plan rows now own only the agent-executable
packet derivation and mutation gates. This ledger remains the sole operational
home for the later human review ceremony.

**What the operator must eventually decide:** per legal reference in the live
derived partition, confirm exact identity, provision, corpus anchor,
presence/absence clauses, applicability, amounts, and rates against live
official authority, one at a time — no bulk promotion permitted. The
population is deliberately not baselined here. The 2026-08-25 observation is
77 selected references partitioned as 38 shared, 13 Modelo-303-only, and 26
Modelo-390-only; 37 are not operator-reviewed. Those counts are diagnostic,
not authority, and must be re-derived by the packet gate.

**What is already prepared:** nothing yet. No worklist document exists under
`.vault/audit/` for any of the three partitions as of this writing (confirmed
by direct search). All three rows are explicitly sequenced after the Modelo 390
split (`S87`, closed) and — per this plan's own serialized release order —
after `S20`, itself still far upstream and blocked on the still-open `S67`
successor epoch maps.

**What is missing:** the agent-doable worklist-preparation clause itself, for
all three rows. There is nothing yet for an operator to sit down with.

**What stays blocked until this lands:** `S91` (below) cannot even begin its
signoff phase, and per this plan's serialized release sequence, campaign
integration and release (`W04.P08`) cannot proceed. Ranked below the fully-prepared
items above because there is no reviewable artifact yet — an operator handed
this today would have nothing to read.

### Operator attestation ledger | medium | 7. Export-fragment revision signoff (`S91`) — nine revisions, blocked upstream on item 6 and review-tier adjudication

**Where:** `.vault/plan/2026-08-10-aeat-export-fragment-generator-authority-plan.md`,
row `W04.P07.S91` (open).

**What the operator must decide:** one-at-a-time signoff for five Modelo 303
revisions (`2023`, `2024-hasta-08-y-2t`, `2024-desde-09-y-3t`, `2025`,
`2026-y-siguientes`) and four Modelo 390 revisions (`2022`, `2023`, `2024`,
`2025`) — nine total — confirming the selected revision and every selected
legal reference is operator-reviewed, before real filing-grade snapshots and the
public M303 filing-instance renderer proof can be built on top.

**What is already prepared:** nothing yet exercisable — this row explicitly
depends on item 6 (the three legal worklists) landing first, and on the still-open
`W04.P07.S70`/`S71` epoch maps and `S20` generation row.

**What is missing:** everything upstream, plus reconciliation of the accepted
temporal-review decision with production snapshot admission. The accepted ADR
requires operator-reviewed revisions and a complete operator-reviewed legal
slice, while production currently admits agent-reviewed revisions and reports
the weakest selected tier. The implementation row may report this refusal but
must not silently resolve the architectural conflict or own the attestation
ceremony.

**What stays blocked until this lands:** the export-fragment campaign's
release phase (`W04.P08`), and per the sequencing audit, the `registry-temporal-coverage`
campaign's owned-tree sweep (`W03.P08.S19`/`S20`), which is explicitly blocked
on this campaign's closure including its `S84` and `S85` rows.

### Operator attestation ledger | low | 8. Temporal-coverage grade promotion (`W03.P07.S17`) — blocked on two whole Waves of agent work landing first

**Where:** `.vault/plan/2026-08-14-registry-temporal-coverage-plan.md`, row
`W03.P07.S17` (open, explicitly marked "BLOCKED on operator attestation" in the
row text itself).

**What the operator must decide:** whether to approve each derived grade-promotion
proposal the row's deriver will emit, per remaining unowned revision — "no
program raising a grade on its own" is the row's own constraint.

**What is already prepared:** nothing yet. The deriver this row builds does not
exist yet; the plan's Description states plainly that "no row in this plan
writes an operator review stamp or raises a grade mechanically," and this row
is sequenced inside Wave `W03`, which requires Waves `W01` and `W02` landed
first per the plan's own Parallelization section.

**What is missing:** two full Waves of agent work (the coverage contract,
snapshot-schema divergence removal, and enforcement-surface installation)
before there is a deriver to run, let alone proposals to review.

**What stays blocked until this lands:** the advisory-to-blocking enforcement
flip in `W03.P08.S20`, which is itself also blocked on the export-fragment
campaign's owned-tree sweep (item 7 above) and on the drift census reporting
zero unenrolled findings. Ranked last because it is the most upstream-blocked
item in this ledger — an operator has nothing to act on here for a long time.

### Operator attestation ledger | info | Items swept and deliberately excluded from this ledger

- `aeat-design-relayout-boundary-plan` — grepped for "operator", "tax review",
  "human", and "attest": the one hit (`W05.P11.S75`) is already closed and
  recorded a deliberate non-change, so this campaign currently carries zero
  open operator-gated rows. Confirmed rather than assumed, since this campaign
  is large (17 open rows) and the most natural place to expect one.
- `registry-suite-red-at-head-plan`, row `P02.S09` — "Sweep the Justificante
  fixtures onto the constrained AeatCsv alias, coordinating with the
  canonical-identifiers owner before editing." The plan's own Parallelization
  section groups this under the same "needing a ruling" heading as the four
  items in entry 5 above, but its gate is cross-campaign agent coordination,
  not a human-only judgement call — another agent owns the surface, not an
  operator. Excluded on that distinction rather than folded in, to keep this
  ledger to genuine human-attestation gates.
- Export-fragment `S88`–`S91` and temporal-coverage `S17` all name "the human
  operator" or "operator attestation" explicitly in their own row text, so
  their inclusion above needed no judgement call, only sequencing.
- Modelo 200's own Impuesto sobre Sociedades export layout gap, surfaced while
  confirming item 1, is not owned by any row in any of the five campaigns
  named in `related:` as far as I could find. Not excluded by judgement —
  flagged because I could not locate an owner, which is itself worth someone
  confirming rather than assuming covered.

## Recommendations

Item 1 is not something an operator "does" in one sitting the way items 2–4
are — it is the standing purpose gap this whole ledger sits inside, and it
should stay pinned at the top of every future revision of this document until
`W04.P07.S20` (Modelo 303) and the Modelo 390 equivalent actually publish real
export trees. Track its sub-parts (2026 map, `S52` census, `S20` generation,
Modelo 390's `S79`–`S82`, and the unowned Modelo 200 layout gap) as their own
progress, not as one checkbox.

Within the attestation items proper, work top to bottom: item 2 (the
Impuesto sobre Sociedades orden re-stamp) first, regardless of any other
priority an operator brings to this session — it is the one item the
sequencing audit's own Tier 0 ruling says precedes all five campaigns
producing verifiable evidence at all against a warm load, it is fully
prepared, and it is a five-minute read. Note it does NOT unblock item 1 — the
new fail-closed policy in item 1 operates at the filing boundary, independent
of whether the load-time review-status collision is closed.

Items 3 and 4 are similarly fully prepared and cheap, and should follow
immediately — item 4 in particular sits on the currently-active campaign's
critical path (`S70`/`S71` cannot author cleanly around an unruled gap).

Item 5's `P03.S14` sub-item needs a decision BEFORE it is treated as a ruling
task: confirm with whoever owns the `aeat-design-relayout-boundary` campaign
that this row should be retired rather than executed, per the sequencing
audit's `duplicated-ruling` finding, and only open an ADR for the remaining
three if a genuine decision is still needed after that.

Items 6 through 8 are correctly sequenced behind agent work this ledger does
not shortcut — do not ask an operator to pre-review a worklist or pre-approve a
grade proposal that does not exist yet. Re-run this reconciliation (or update
this document in place) once any of items 1 or 6–8's upstream agent work
lands, since new prepared material changes what an operator can act on that
day — item 1 especially, since another agent is actively editing the 2026 map
in this same worktree as this document is being written.

No item in this ledger was closed, checked, or acted on by the audit that
produced it — every disposition above is "ready to review" or "not yet ready,"
never "done."

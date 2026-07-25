---
tags:
  - '#audit'
  - '#evidence-revision-identity'
date: '2026-07-25'
modified: '2026-07-25'
related:
  - "[[2026-07-24-evidence-revision-identity-adr]]"
---

# `evidence-revision-identity` audit: `operator walkthrough`

## Scope

Two questions, both answered by driving the shipped CLI as a taxpayer rather than
by reading code. First: what happens when the documented quickstart narrative is
followed in its documented order. Second: how much of the documented narrative is
exercised by the docs-build gate at all.

Every CLI observation below comes from a real walkthrough against a throwaway
storage root, isolation confirmed by an empty profile list before anything was
created. Sequence counts come from a single pass over the committed contract
files.

## Findings

### stranded-filing-target | critical | discard permanently strands a filing target, and it is the escape operators will reach for

`work discard` marks the work unit `descartado`; the follow-up `work create`
re-derives the SAME work-unit id (it is content-addressed over bucket, modelo,
filing year, period and registry revision) and hands the discarded unit back.
Calculate, verify and export then all refuse with "no active work unit matches
this modelo, year and period; run work create first" — the command that just ran.
That (modelo, filing year, period) target is unusable for that profile from then
on. This is reachable by any operator following the obvious instinct to discard
and retry after a refusal, and is entirely independent of the evidence question
that surfaced it.

### post-verify-evidence-never-lands | high | the documented remedy order cannot complete, three mechanisms deep

Followed as written — calculate, verify, export, then the remedy the refusal names
— the narrative cannot complete. Export refuses with
`REFUSED_MODELO_EXPORT_EVIDENCE_MISSING` on a deductible-IVA row with no linked
invoice and names registering and attaching the invoice. The finalized-modelo
write guard refused that attach until this campaign narrowed it; attaching now
succeeds and the evidence does land on the ledger row. It still does not help.
Re-running calculate returns the SAME content-addressed revision id, already
`verificado_completo`, because the id is derived over inputs, binding overrides,
casilla values and contributing transaction ids, and evidence references are in
none of them. Re-running verify returns the SAME verification report id, because
verify is idempotent-guarded on its outcome. The evidence bundle is captured at
verify and frozen, so it is never re-captured and export keeps refusing with the
identical revision id. Linking the invoice BEFORE calculate works cleanly: the
draft's verify-time bundle carries the evidence and both export and the local
filed marker complete. The product is not broken; the ordering is load-bearing and
was undocumented.

### evidence-is-not-a-tax-fact | medium | the narrowed write guard rests on two contracts the codebase already declares

The transaction id derivation hashes the provider identity, effective value date,
amount and narrative only, so an evidence-only edit re-derives the same id and a
finalized revision's contributing-transaction citation keeps resolving. The ledger
filing snapshot's fingerprint field set — the canonical tax facts of a row,
twenty-four fields — omits both evidence references, so the row fingerprint and
the revision's snapshot fingerprint are unchanged. The converse also holds and
matters: evidence IS value-affecting for a FUTURE calculation, since the Renta
first-slice expense pipeline reclassifies an incoming row carrying purchase
evidence as a refund and lets a resolved invoice's taxable base and IVA override
the row's own. The frozen revision is untouched, which is why the exemption holds,
but a post-attach recalculation is not cosmetic.

### finish-line-is-display-only | critical | the docs gate stops exactly where the refusals live

Of 281 committed sequence contracts, 106 execute NOTHING at all, 10 execute
partly, and 165 execute fully. The pattern is not random: the local filing finish
line is display-only. The export verb appears 12 times as a display-only frame
against 5 executed; the local filing verb 14 times against 3. Whole guides never
execute a single frame — the filing spine, the annual IVA summary, the
calculation-value review, the first quarterly filing, the per-modelo export-file
guides and the IRPF and IVA lifecycle guides. The documented narratives therefore
prove profile setup, ledger entry, calculation and verification, then stop
precisely at the two verbs where the refusals live, so a dead end in any
finish-line flow is undetectable by construction. That is the structural reason
this defect shipped. The quickstart export and filed-marker sequences were both
display-only; both now execute the real chain end to end.

### static-frame-split | medium | 100 of 196 display-only frames are purely local and could execute

Splitting by cause: 96 frames are genuinely blocked on something a local sandbox
cannot supply — the AEAT live portal (45), real certificates (11), Google OAuth
(11), interactive passphrase prompts (11), an LLM provider (8), and a tail of
external files and network probes. The other 100 are purely local. Of those, 72
across 40 sequences are directly runnable as written, and 28 across 20 sequences
embed literal placeholder tokens and need a capture rewrite before they can
execute.

## Recommendations

Signposting has landed and is the part that needed no decision: the export and
internal-filing refusals, the post-attach advisory and the quickstart all now
state that the invoice must be linked before calculate, and the advisory
deliberately names no recovery verb because both candidates were measured and both
make the operator's position worse.

The stranded filing target should be fixed independently of the evidence question
and is the sharper item, because it converts a retry instinct into permanent loss
of a filing target. The related decision record must choose between making
`work create` refuse a discarded unit with an instructive next step and making
discard reversible.

Whether an operator already stranded by the ordering gets a non-destructive
recovery path is architecturally significant and is the decision the related
record exists to obtain: folding bundled evidence into calculation revision
identity, or adding an explicit supersede transition that opens a new draft from a
finalized revision.

For the sequence corpus, the 72 directly-runnable frames are the cheap and
valuable half and should be converted first, weighted to the export and filing
verbs. The 96 genuinely blocked frames should record why they cannot execute, so
display-only status is a stated constraint rather than an unexamined default that
hides the next dead end.

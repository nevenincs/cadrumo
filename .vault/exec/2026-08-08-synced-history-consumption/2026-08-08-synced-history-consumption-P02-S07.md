---
tags:
  - '#exec'
  - '#synced-history-consumption'
date: '2026-08-08'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:eef38b54efdc33aac38e9f18c1900880f45532003e4e554e3ab78f64b22dfade'
step_id: 'S07'
related:
  - "[[2026-08-08-synced-history-consumption-plan]]"
---
# Author the decision record ruling which pulled facts are calculation inputs, which are reconciliation targets and which stay display only, plus the mechanism each wired channel uses from the existing one-mechanism-per-calculation-type taxonomy, amending that taxonomy in the same change if no row covers a needed channel. Open every implementing row in the SAME action as the ruling, because a decision record ruling on code is not self-executing and the debt it creates otherwise has no owner while every later reader sees the ruling as in force. Gate: the record cites the census denominator and every ruling maps to an opened row id

## Scope

- `no production files`
- `decision record only`

## Description

- Ruled each census channel from the registry's own declared treatment rather than from an axis invented for the ruling, since that field is per row, carries its own legal refs, and needs no analogy between modelos.
- Opened all five implementing rows in the same action as the ruling, and verified each id resolves exactly once in the plan before citing it.
- Recorded a conditional ruling with a stated trigger for the nine unreachable carries rather than deferring them silently or ruling against an unmeasured fact.
- Declined to classify one reachable, consumed channel because its mechanism sits outside the aggregation taxonomy.
- Carried the reconciliation recommendation as a precondition rather than a recommendation.
- Flipped the record from proposed to accepted, preserving its Problem Statement and Constraints verbatim.

## Outcome

The ruling is per declared treatment. 52 `direct_annual_settlement` carries are CALCULATION INPUTS, which ratifies shipped behaviour and changes nothing. 12 `factual_evidence` carries are RECONCILIATION TARGETS ONLY, which does change shipped behaviour. 17 carries are NOT RULED because they declare no treatment, and a treatment that is undeclared cannot later be cited as authority for having consumed the value. Display only is empty by measurement, not by choice.

The behaviour-change consequence is stated in the record rather than left for a reader to infer. The reachable carries are consumed today, proven by execution on both poles, so ruling the factual-evidence class non-settling describes a change to what ships. Its remedy is constrained in the ruling itself: it must NOT blank the value, because a taxpayer is entitled to the retencion and a silent drop is the over-declaration direction this campaign already measured as unwatched. The value is surfaced carrying its provenance and treatment so a consumer can tell it from a settled figure.

The nine unreachable carries are ruled conditionally with the trigger stated, so the operator's single read-only action resolves them without reopening the decision. Each branch has a stated outcome. The nine split two `direct_annual_settlement` and seven `factual_evidence`, which is this session's correction to an earlier reference that said three and nine and did not reconcile with its own subtotal.

One reachable, consumed channel is deliberately left unclassified. Modelo 130's previous-year economic-activity net income is a cross-modelo fold-in declared as a direct previous-filing carry, which is the row reserved for a same-modelo static carry, so it occupies no row of the taxonomy. Ruling on a channel whose mechanism is undecided would ratify the violation, so the record classifies it only after its mechanism is settled.

No taxonomy amendment was needed. Every channel ruled here uses a mechanism the taxonomy already carries, and the single exception is not a new mechanism but a channel on the wrong existing one.

The record states why the ruling does not erode the non-official-evidence boundary, which its own Constraints demanded of any promotion. That boundary decides whether a filing is PROVEN. This ruling decides what a proven filing's figures are FOR. Nothing here promotes a locally-filed observation to official.

The ruling does NOT lean on revision re-confirmation as a safeguard, and says so. The pull supplies no stamped revision id, the repository resolves the law-determined revision itself, and the carry gate re-confirms by resolving the same triple against the same authority. That is the same call returning the same answer, and it catches a stamp a producer supplied from a snapshot it held, which does not exist on this path.

## Verification

    for id in S16 S17 S18 S19 S20: rg -c "P02.$id\`" <plan>
    P02.S16 resolves: 1
    P02.S17 resolves: 1
    P02.S18 resolves: 1
    P02.S19 resolves: 1
    P02.S20 resolves: 1

Every row id cited in the ruling resolves exactly once in the plan. Exactly once matters as much as at least once, since a duplicated id would make the citation ambiguous.

    uv run --no-sync vaultspec-core vault check adr-status
    ok adr-status: clean

The body-sections and placeholders checks were also run and report nothing against this record, so the accepted status, the section set and the absence of template residue are all machine-confirmed rather than asserted.

The census denominator the gate requires is stated in the record: 1253 bindings across 73 modelos and 90 revisions, 81 carries, 72 pull-reachable and nine not.

No pytest lane was run. This step changed no production code and wrote no test.

## Notes

WHAT THIS RULING DOES NOT SETTLE, stated rather than smoothed over. 17 channels are consumed today on no declared authority and this record does not retrospectively supply one. A later reader must not cite it as having authorised them. The nine Sociedades carries are unresolved by design and their absence from the ruled set is not a ruling that they are out of scope. The Modelo 130 carry is unclassified pending its mechanism.

The two rows opened by earlier steps in this session are deliberately NOT folded in. One gives a Sociedades filer a surface distinguishing no prior filings from unreachable prior filings. The other stops the filed-capture refusal asserting an AEAT fact it cannot know. Both are operator-surface defects rather than consumption rulings, and folding either into the ruling would have hidden it inside a decision record instead of leaving it an owned row.

The plan's five new rows were swept into HEAD by a peer's whole-index commit before this step could commit them. All five were verified present and singular in HEAD afterwards, so nothing was lost or duplicated, and the ruling's citations resolve against the committed plan.

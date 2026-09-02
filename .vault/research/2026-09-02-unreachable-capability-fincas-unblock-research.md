---
tags:
  - '#research'
  - '#unreachable-capability'
date: '2026-09-02'
modified: '2026-09-02'
body_schema: 'body-v2'
body_hash: 'sha256:aa54a8d3dc3b9ea01bd75917203292e8ad7b7796c4b6c9f4e191afe70641aeec'
related:
  - "[[2026-09-02-unreachable-capability-research]]"
---

# `unreachable-capability` research: `what actually blocks the fincas calculation source`

The rental-income engine is the largest finished capability the reachability
audit found, and the campaign stalled on it because the blocker was recorded as
one thing when it is three. This research separates them, and the separation
matters: only one of the three is ours to remove, one is external evidence, and
the third is a plan ordering that no amount of engineering shortcuts.

The headline is that the fincas row cannot honestly be promoted now, and the
reason is not the one the code states. Attempting the persistence fix first
would produce a source that is technically enrolled and legally ungrounded,
which is precisely what `no-silent-under-declaration` forbids.

## Findings

### Three blockers wear one label

The census row `fincas.annual-aggregates` carries
`disposition = "grounding_blocked"`, whose closed meaning in
`src/cadrumo/core/source_connectivity.py:106` is "official evidence has not yet
settled legal substitutability". That is true, but the code disagrees about
what stops it. `src/cadrumo/domain/fincas/source_readiness.py:34` returns
`ready=False` with a persistence reason: the aggregates "are not persisted
through the canonical secure-storage revision boundary". That is the closed
meaning of a different disposition, `ingress_blocked` at line 109, "the typed
fact exists but lacks a governed calculation input path".

Both statements are accurate. The row records only one, so a reader who
consults the census concludes the work is waiting on AEAT, and a reader who
consults the code concludes it is waiting on us. Neither is complete.

The third blocker appears in neither place. The plan that owns this work is
hard-sequenced: `2026-08-22-source-casilla-integration-plan` states that
inventory in W02 must finish before amortization in W03, and W03 before the
remaining candidates in W04, where fincas sits at phase P12. Amortization's
promotion step `W03.P11.S70` is open, so fincas is not merely unfinished, it is
not yet eligible to start.

### The precedent slice ran the whole path and still could not connect

This is the most important finding, because it reframes what success looks
like. Inventory was the designated first vertical slice. Its steps are checked
through `W02.P09.S54`, which required promoting to connected "only when a
grounded row-capable format and every connected proof pass, otherwise record
the evidence-backed blocked disposition with an owned follow-up".

It recorded the blocked disposition. The inventory row today reads
`registry_blocked`. Amortization, the mandatory second slice, reads
`ingress_blocked`.

No row in the census is `connected`. Fifteen entries, and the distribution is
five ingress-blocked, three duplicate-or-stale, two registry-blocked, two
grounding-blocked, two not-applicable, one manual-by-design. The mechanism has
never carried a source to production. So connecting fincas is not a matter of
following a worn path; it would be the first traversal, and the two slices
designed to prove the path both stopped short with honest refusals.

### What the official evidence must settle

The row's `review_condition` is specific, and reading it closely shows why it
resisted a quick answer. Official evidence must adjudicate the mapping at four
grains at once: per-finca, per-contract, annual scalar, and revision. It must
do so for six quantities: ingresos, gastos, amortization, reduction, imputed
rent, and attribution.

Two constraints in that condition are easy to miss and both are load-bearing.
Name overlap with the Modelo 100 inmueble envelope is declared advisory only,
so matching labels prove nothing. And the finca computation must remain
distinct from the encrypted asset-amortization ledger, which is a separate
census candidate in its own right. That second constraint is why the plan keeps
fincas and non-amortization asset facts in different phases.

The row's `advisory_destination_refs` names `modelo:100:family:real-estate-income`
and nothing more. It is deliberately advisory, not a casilla binding, which is
the correct posture while grounding is open.

### One defect here was genuinely ours, and it is fixed

The row's `capability_locators` and `capability_ids` pointed at
`_aggregates.py`, `_amortization_ledger.py` and `_source_readiness.py`. The
private-to-public promotion renamed all three, and none of those paths existed
any more. The census schema validator at
`src/cadrumo/application/registry/source_connectivity.py:190` checks only that
locators are unique, never that they resolve, so six dead references sat in
shipped data without any gate objecting.

That is repaired: all six now point at the public modules and every one
resolves. It changes no disposition, but a blocked row whose evidence pointers
are dead cannot be reviewed at all, so this was a precondition for the review
rather than an improvement to it.

### What would have to be true to promote the row

Working backwards from the connected proofs the mechanism defines in
`src/cadrumo/core/source_connectivity.py:226`, a promoted row needs three
independent executable proofs: resolver enrolment, encrypted revision, and
operator reachability. Mapping those onto the open plan steps gives a concrete
sequence rather than an aspiration.

Resolver enrolment is `W04.P12.S74`, the finca taxonomy, selectors and
resolver. Encrypted revision is `W04.P12.S76`, which is the same boundary the
readiness function currently reports as missing, so the persistence blocker and
that proof are one item, not two. Operator reachability is `W04.P12.S77`, the
CLI workflow, which is the verb the earlier triage assumed was the whole job
and is in fact the last of three.

Ahead of all of them sit `W04.P12.S72`, grounding the per-finca M100 semantics,
and `W04.P12.S73`, deciding the aggregation grain. Neither document exists yet.

### The grounding step is a reading task, not external research

This was the largest open unknown and it resolves in the repository's favour.
The official AEAT Renta manual is bundled for filing years 2020 through 2025,
with extracted text sidecars beside each source PDF, and it covers every
quantity the review condition names: capital inmobiliario, arrendamiento,
gastos deducibles, amortización, reducción, and imputación de rentas
inmobiliarias. It cites casillas directly in bracket notation, including the
`[0102]` to `[0154]` range the rental sections address.

The legal grounding for the computation is further along than the row implies.
Sixty rental parameters already ship across the M100 revisions, each carrying
`legal_refs` to LIRPF article 23 and, for amortisation, additionally to the
RIRPF article 14 rate. Several carry `source_citations` with `required_text`
assertions, so the citation is verified against corpus text rather than
asserted.

What is therefore missing is narrower than "official evidence". The rates,
thresholds, tiers and lookback windows are grounded. The undecided part is the
DESTINATION MAPPING: which casilla each computed aggregate lands in, at which
of the four grains, and how attribution splits across owners. That is
`W04.P12.S72` and `S73`, and both can be executed by reading bundled material.

### What was not investigated

Whether amortization's `ingress_blocked` state has a shorter path
than fincas, which would matter because the sequencing puts it first. And
whether the census validator should gain locator resolution as a gate, which
looks correct but belongs to the source-connectivity owner rather than this
campaign.

## Sources

- `src/cadrumo/_data/source_connectivity/census.toml` — the `fincas.annual-aggregates` row
- `src/cadrumo/core/source_connectivity.py:97` — the closed disposition set
- `src/cadrumo/core/source_connectivity.py:226` — the three executable proof roles
- `src/cadrumo/domain/fincas/source_readiness.py:34` — the persistence reason
- `src/cadrumo/application/registry/source_connectivity.py:190` — the uniqueness-only validator
- `.vault/plan/2026-08-22-source-casilla-integration-plan.md` — W02 through W04, and the hard sequencing statement
- `.vault/adr/2026-08-22-source-casilla-integration-adr.md` — the accepted ratcheted-connectivity decision

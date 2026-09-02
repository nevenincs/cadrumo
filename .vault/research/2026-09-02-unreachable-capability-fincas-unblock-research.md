---
tags:
  - '#research'
  - '#unreachable-capability'
date: '2026-09-02'
modified: '2026-09-02'
body_schema: 'body-v2'
body_hash: 'sha256:4a90adecfe5ff06f83821dfeb6c4ba10486acf412a485378e646c0599a52e23f'
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

### The manual answers the grain question with a worked example

The previous section claimed the grounding step is a reading task. That claim
is now verified rather than asserted, and the material is more specific than
expected. Chapter 4 of the bundled 2025 Renta manual, "Rendimientos del capital
inmobiliario", names the destination casillas individually with their meaning.

Property identity and attribution, which the review condition calls out, are
explicit: the owning contribuyente at `[0062]`, ownership percentage at
`[0063]`, usufruct percentage at `[0064]`, cadastral reference at `[0066]`, and
the use classification across `[0067]` through `[0075]`, where `[0075]` is the
let property and `[0074]` an accessory let. Day counts sit beside several of
them, which is how a property that changes use mid-year is apportioned.

The six quantities the condition enumerates appear together as the declaration
set: ingresos íntegros computables, gastos deducibles, rendimiento neto,
reducciones del rendimiento neto, and the rendimiento mínimo computable.

The grain question is settled by an official worked example rather than by
inference. It computes a single property across two successive tenancies in one
year, stating the ingresos íntegros for the first contract and then for the new
contract, before summing deductible expenses once for the year. So the official
treatment is per-contract for income within a per-property, per-year envelope.
That is the answer the census asks for, and it is an independent worked example
of exactly the kind the calculation-grounding rule prefers over a derived
reading.

What remains genuinely undecided is narrower still: how our per-finca
aggregates map onto that envelope when a taxpayer holds a share rather than
full title, and whether the reducción tier resolution we already ship agrees
with the manual's tier conditions for the same year.

### The reduction engine already agrees with the manual; the ownership model does not

Checking our shipped parameters against the manual point by point closes one of
the two residual unknowns and sharpens the other.

Everything about the reduction agrees. All four tier rates match: 50 per cent
as the general case for contracts from 26 May 2023, 90 for a new contract in a
stressed-market zone where the initial rent was cut by more than 5 per cent
against the previous contract, 70 where those conditions are not met but
another circumstance applies, and 60 for the earlier regime. Both age bounds
match the manual's "entre 18 y 35 años", and the rebaja threshold matches its
"más de un 5 por 100".

The proportional co-tenant rule is implemented too, which was the subtlest
condition in that section. Where a dwelling has several tenants, the manual
applies the reduction only to the share of net income corresponding to those
who qualify, and `domain/fincas/tier_resolver.py` returns a qualifying share of
qualifying co-tenants over tenant count for that tier alone, quoting the BOE
sentence at the implementation site.

The ownership model is where the gap is real. The manual requires the
declaration to carry the owning contribuyente at `[0062]`, the ownership
percentage at `[0063]` and the usufruct percentage at `[0064]`, and it treats
those as per-property facts. The `Finca` model carries cadastral values,
acquisition costs, dates, use type and the stressed-area flag, and no ownership
or usufruct share at all. It assumes full title.

So the attribution question the census names is not an open adjudication about
which grain to choose. It is a concrete modelling gap with the two fields
already specified by the manual. Adding them changes a shipped domain record,
so it belongs to the decision step rather than to this campaign, but the
question it must answer is now narrow and evidenced.

### The census locator gate exists, is thorough, and never sees the live census

The six dead fincas pointers were not a fincas problem. `check_capability_locators`
in `dev/source_connectivity/check.py` already requires every locator to
re-fetch, requires the line number to be within the file, and cross-checks each
`capability_id` against a discovery pass so an id and its locator cannot drift
apart. It is a well-built gate.

Its tests only ever hand it focused or synthetic manifests. Nothing runs it
against the shipped census, so the promotion of private modules to public names
broke pointers in shipped data with no gate objecting. Running it against the
live manifest by hand reports five dead locators across three further rows:

- `censo.modelo-036-profile-status` and `coverage.remaining-ingress-surfaces`
  both point at `application/modelo/_m036_lifecycle.py`, now `m036_lifecycle.py`.
- `inventory.stock-valuation` points twice into
  `domain/contribuyente/inventory/__init__.py` at lines 1161 and 1367; that
  module is now a 20-line inert namespace and the symbols moved to `records.py`
  and `valuation.py`. It also points at `application/inventory/_service.py`,
  now `service.py`.

These were not repaired here, and the reason is worth stating. The row's
`capability_ids` carry an exact correspondence to their locators, down to the
line, so a hand repair can silently attribute a capability to the wrong symbol.
The correct source of truth already exists: `discovered_source_capability_evidence`
resolves each id to its current location, and it disagrees with the census on
both the module AND the line for the inventory entries. Regenerating that block
from discovery is the owner's tooling decision, not a text edit.

### Question for the source-connectivity owner

Two decisions belong to whoever owns the closed disposition vocabulary and the
census schema. Neither is answered here.

First, the fincas row carries `grounding_blocked` while the readiness function
reports the persistence gap that `ingress_blocked` describes. Both are true and
a row holds one. The options are to re-label once the mapping decision lands,
to keep the grounding label until `S72` and `S73` close, or to extend the schema
with a secondary blocker. Each changes what the monotonic enforcement gate
means, which is why it is not an editorial choice.

Second, should locator resolution run against the shipped census in a declared
lane? The gate exists; adding the live manifest to it would have caught all
eleven dead pointers on the commit that renamed the modules. It would also be
red on arrival, so landing it needs the repair above to go first.

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
- `src/cadrumo/_data/corpus/manuals/renta/2025/part1/source.pdf.extracted.md` — chapter 4, casillas `[0062]`-`[0082]` and the two-tenancy worked example
- `dev/source_connectivity/check.py` — `check_capability_locators` and `discovered_source_capability_evidence`

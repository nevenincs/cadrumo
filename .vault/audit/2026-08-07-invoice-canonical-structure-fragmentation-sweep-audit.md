---
tags:
  - '#audit'
  - '#invoice-canonical-structure'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:dc01832aaf24c131f2e14fffd63cffdd9a95b9833278e10859723bdb653183c2'
related: []
---

# `invoice-canonical-structure` audit: `Fragmentation sweep of the invoice and identifier surfaces`

## Scope

A multi-query semantic sweep over the invoice CRUD and identifier surfaces, run before executing `P03.S11` — the Step that repoints the operator's five bare invoice verbs, and therefore the point at which a redeclaration would be created rather than closed.

Seven distinct meaning-based queries were run and their results compared, rather than one query trusted. Standing operator directive, reaffirmed three times on 2026-08-07 and escalated each time:

> *"Do not allow redeclarations of the same concepts — canonical functionalities only. Do not allow the codebase to fragment."*
> *"I demand the RAG is exercised extensively and that ALL FRAGMENTATIONS are treated as CRITICALITIES."*

Outcome: one **critical** cross-domain fragmentation, one **in-scope** redeclaration that `S11` must close rather than create, and one **false positive** recorded because not-a-finding is as useful as a finding.

## Findings

### CRITICAL — "resolve a short id, refusing ambiguity" has no canonical home and ~23 independent implementations

One concept — *take an operator-typed identifier that may be a prefix, match it against a set, refuse rather than guess when it matches more than one* — is implemented independently across at least eight domains. No shared primitive exists.

Measured sites (production only, tests excluded):

- `application/invoices/_lifecycle.py` — catalogue invoices
- `application/ledger/_business_operation_invoice.py` — slim invoices
- `application/ledger/_id_resolution.py` — transactions, with edit lineage
- `application/evidence/_service.py` — evidence bundles
- `application/live/_expedientes.py`, `_notifications.py`, `_verify.py` — three separate live services
- `application/modelo/_m036_lifecycle.py`, `_m145_communication_records.py`
- plus twelve CLI-boundary sites

**Why no symbol sweep would have found this.** The sites share no identifier. Some call the helper `_resolve_id`, some inline the scan, some name the concept only in a docstring. The one helper that calls itself "the single shared CLI-boundary wrapper" is shared *for transactions only* — self-described sharing, scoped to one domain, which reads as canonical until you check what it covers.

**Why it matters beyond tidiness.** Each site independently decides what an ambiguous prefix does. The invoices one names the candidates in its refusal; several live ones deliberately refuse *without* leaking the full ids. Those are different, defensible security postures — arrived at separately, with nothing linking them, and nothing that would notice if one drifted. A concept whose refusal semantics are decided per site is exactly where one site quietly resolves to the first match.

**Not remediated here, deliberately.** It spans eight domains and ~23 files, none of them this campaign's. Refactoring them inside an invoice campaign, in a shared worktree carrying concurrent peer work, would be a large uncoordinated change landing under an unrelated commit subject. It needs its own campaign with a named owner. What this campaign owes it is recorded below.

### IN SCOPE — the `catalogue` sub-noun is an unregistered second operator surface

The operator-surface contract registers exactly one invoice noun-group: `INVOICE = MutatingNounGroupContract(noun="invoice", cli_path="aeat app ledger invoice")`, commented as "one unified invoice noun-group gated by `--kind issued|received`".

`aeat app ledger invoice catalogue ...` appears nowhere in that registry. It is a second command surface exposing the same five operations over a different store — a redeclaration of the operator-facing concept, currently invisible to the CRUD conformance gate because it was never registered as a noun-group at all.

This is `P03.S11`'s job and the reason the Step pairs "repoint the five bare verbs" with "retire the catalogue sub-noun": doing only the first would leave two surfaces for one concept.

### NOT A FINDING — the ledger gate family is adjacent, not fragmented

A sweep for invoice-versus-ledger consistency gates returns five modules: the aggregation screen, a deductible-evidence gate, an export-evidence gate, a ledger-drift gate, and an M200 required-input gate. They look like one concept spread across five files.

They are not. Each answers a different question at a different lifecycle point — value comparison, evidence presence, export evidence, staleness, missing manual input. Collapsing them would merge unrelated concerns.

**The discriminator used throughout this sweep:** do two sites answer the *same question*? The M303 and M390 screens would have (which is why `P05.S25` generalised rather than duplicated). These five do not. Treating fragmentation as a criticality does not mean treating adjacency as fragmentation, and a sweep that cannot tell them apart produces refactors that lose information.

## Recommendations

**Binding on this campaign, immediately:**

- `P03.S11` must repoint the bare verbs onto the EXISTING canonical resolver, never add a twenty-fourth prefix-resolution implementation. The canonical invoice resolver already exists and is the target.
- `P03.S11` must retire the `catalogue` sub-noun in the same change, so the fold ends with one registered operator surface rather than two. Doing only the repoint would leave two surfaces for one concept.
- `P03.S14` removes the slim store, deleting one of the ~23 prefix-resolution sites as a side effect. That is a reduction, not a remediation — the concept still has no home.

**Handed on, with evidence, needing an owner:**

- The prefix-resolution concept needs a canonical home and ~23 consumers repointed to it. The first design question is NOT where to put it but **what its refusal contract is**, because the existing sites disagree: the invoices one names the ambiguous candidates, several live ones deliberately withhold them so a full id is not leaked. Both are defensible; they were arrived at separately with nothing linking them. That disagreement must be settled as a decision before any code moves, or consolidation will silently impose one site's security posture on all of them.

**Recorded as method, since it generalised across this campaign:**

- **Lead with meaning, not symbols.** Every fragmentation found in this campaign — the bucket-attribution comparison written twice, the CLI enum mirroring a domain enum, the second construction authority, the country proxy standing in for a property, this one — shared no identifier between its sites. A symbol sweep finds where a word appears; a meaning sweep finds where a concept is owned.
- **Run several queries and compare.** The highest-value result here came from the fourth query, not the first, and the first query's top hit was a false positive that a later query disambiguated.
- **A duplicate that documents itself as a duplicate is the hardest to see.** Both the retired CLI enum and the transaction-only "single shared wrapper" carried docstrings explaining their relationship to the canonical thing, which reads as considered rather than redundant.

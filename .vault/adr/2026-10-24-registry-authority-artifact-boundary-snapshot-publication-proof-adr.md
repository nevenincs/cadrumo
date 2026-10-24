---
tags:
  - '#adr'
  - '#registry-authority-artifact-boundary'
date: '2026-10-24'
modified: '2026-10-24'
body_schema: 'body-v2'
body_hash: 'sha256:eda7ddad98360f5d92e44cfe96a1a279ccf83e6e22f179a5d6cf600a3f888dcf'
related:
  - "[[2026-10-24-registry-authority-artifact-boundary-snapshot-publication-proof-reference]]"
  - "[[2026-09-14-registry-authority-artifact-boundary-indexed-storage-adr]]"
  - "[[2026-07-17-mcp-call-latency-adr]]"
  - '[[2026-06-10-period-revision-resolution-adr]]'
---
# `registry-authority-artifact-boundary` adr: `snapshot cross-checks proven at publication` | (**status:** `proposed`)

## Problem Statement

`PinnedAuthorityOperation.snapshot()` re-runs every registry snapshot cross-check through `build_validated_snapshot` on each call, in each process, although for an ordinary request the outcome depends only on the published generation and the validator code. Publication validates the whole registry but never proves a single snapshot selector, so runtime is today the only place these checks run. The cost is real but bounded: about 0.12 s of a 0.52 s cold first M100 snapshot and about 0.41 s across a four-snapshot workload, with decode (about 0.40 s) untouched. A runtime memo, being added separately, removes repeats inside one process but not the first build in each new process. Deciding where snapshot validation is owned changes the published schema, the publication gate and the runtime trust boundary, so it needs a decision rather than a local optimization. Evidence: `2026-10-24-registry-authority-artifact-boundary-snapshot-publication-proof-reference`.

## Considerations

- For a request with `on=None` and no `revision_id`, the outcome of a `(modelo, filing_year, period, grade)` cell is a function of generation content, validator code, the period end date and two governed-fact lookups made at the wall-clock date (reference, "What `build_validated_snapshot` does").
- The current generation's set is finite and small: 1,258 cells over 141 revisions, 3,774 cell-grade outcomes, swept in about 23 s. Every refusal is the declared grade ceiling, and outcomes are uniform per `(modelo, revision, grade)` (reference, "Selector set").
- The request space is wider than the declared set. `EVENT-N` admits any concrete `EVENT-n`, years above the horizon are projected, and production callers pass `on` and `revision_id` (reference, "Runtime inputs").
- Logical generation identifies the legal inputs only. A validator change republishes new physical bytes under the same generation (`2026-09-14-registry-authority-artifact-boundary-indexed-storage-adr`, amendment 2026-09-30). A proof therefore certifies something the generation digest does not name.
- The indexed-storage decision already moves invariant work to publication and has runtime rely on the physical digest for integrity and closure. It forbids claiming that runtime revalidated the corpus merely because admission succeeded (same ADR, "Admission and publication").
- Precedent: a validation verdict keyed on input identity, with a full revalidation on mismatch (`2026-07-17-mcp-call-latency-adr`, D1).
- Every snapshot must still resolve from the caller's `(modelo, filing_year, period)` through the canonical temporal resolver, and `revision_id` stays an assertion rather than a selector (`2026-06-10-period-revision-resolution-adr`). This decision keeps selection at runtime and moves only the post-selection checks.
- The checks run against the ambient governed-fact scope. A proof made inside the publishing generation removes the chance that a long-lived host's task scope belongs to another generation (`authority.py:906-925`).

## Considered options

- **Keep runtime validation and rely only on the memo.** Simplest, with no format change, but every fresh process (each worker, CLI child or MCP call host) still pays the first-build checks. Kept as the fallback path and as the baseline the decision must beat.
- **Prove the declared selector set at publication; trust the proof by physical digest and proof contract; validate at runtime on any miss.** Kept (the decision below).
- **Prove at publication and refuse at runtime any request without a proof.** Rejected. It breaks legitimate `on`, `revision_id`, concrete `EVENT-n` and projected-year callers, and turns a performance change into a capability reduction.
- **Prove per revision instead of per cell.** Rejected for now. Uniformity per revision is empirical for today's data only, and selection, period normalization and the filing-date legal review do read year and period. Revisit only with a code-level proof of invariance.
- **Persist complete validated snapshots instead of outcomes.** Rejected. It duplicates revision payloads per cell, inflates the artifact, and moves decode cost rather than removing it.
- **Port the checks or decode to a compiled language.** Rejected on the same evidence: the remaining costs are pydantic construction (already native), GC traversal and these memoizable checks.

## Constraints

- `build_validated_snapshot` stays the single canonical validator, and publication proves cells by calling that same function. No second check implementation, no reduced publication-only variant, and no duplicated selection, precedence or grade logic in SQL (indexed-storage ADR, "Constraints").
- The proof covers exactly: every modelo directory, every filing year from the support floor to the horizon, every declared period token (the symbolic `EVENT-N` as itself), every member of the grade ladder, with `on=None` and `revision_id=None`. Each cell records the selected revision and either success or the typed refusal (failure condition and message).
- A proof is trusted only when all of these match: the database was admitted by physical digest; the proof's contract identity equals the runtime's; the request is in the proven set after canonical period normalization; and the current Madrid date lies inside the proof's recorded fact-date window. Any other request runs `build_validated_snapshot` as today. A missing or untrusted proof never refuses and never weakens a check.
- A trusted refusal raises the same typed error the full path raises. A trusted success builds the snapshot through the same assembly code as the full path (selection, period normalization, export-layout derivation, catalogue slicing, `RegistrySnapshot` construction with its model validators) and skips only the cross-check calls.
- The proof contract identity is a constant owned beside `build_validated_snapshot`. Any change to which checks run or what they mean must change it. It is a validator identity, not legal identity: the logical generation stays the legal-input digest, and a contract change alone needs republication to restore the fast path, not a new generation.
- The proof is a new table in the published database, so it is covered by the physical digest. The store format advances to `cadrumo-authority-sqlite-v5` under the existing refusal-and-republication rule. The descriptor format is unchanged.
- Unchanged by this decision: static inspection (`grade=None`) keeps its narrower non-snapshot claim; the eager `ValidatedRegistryAuthority`, dev conformance, tree validation and diagnostic classification always run full validation; the public helper checks keep their direct callers; stale-draft and capture checks before durable filing output remain mandatory.
- Implementation hypotheses that may change within these constraints: the table shape, the representation of the fact-date window, and whether the publication self-check below runs on every publication or only in the release lane.

## Implementation

We will prove the snapshot cross-checks once, at publication, for the generation's declared selector set, and have runtime trust those outcomes through the admitted physical digest and a proof contract identity, falling back to full runtime validation for every request outside the proof.

- **Publication.** After complete validation and before the descriptor switch, the publisher opens the staged database with a clean reader, binds the governed-fact scope to that reader's operation, and calls `build_validated_snapshot` for every cell in the proven set. It records each outcome, the proof contract identity, and the date window over which the wall-clock fact lookups select the same variants. The two lookups today each have a single open-ended variant, so the window is currently unbounded above. A cell that fails at or below its revision's declared grade refuses publication and preserves the previous descriptor; a refusal above the declared grade is recorded as the expected outcome. (The second rule is an open question; see Consequences.)
- **Publication self-check.** Still on the staged database, for every proven success, the trusted construction must produce a snapshot typed-equal to the full path's. A mismatch refuses publication. This is the differential gate that keeps the two runtime paths from diverging.
- **Runtime.** `PinnedAuthorityOperation.snapshot()` loads the components it already loads, looks up the proof for the normalized request, and takes the trusted branch only under the trust conditions above. Otherwise it calls `build_validated_snapshot` unchanged.
- **Interaction with the runtime memo.** The memo sits outside this decision. It keys on the generation pin and the full request coordinate including grade, and caches successes only. On a memo miss, `snapshot()` takes the trusted branch or the full path. The memo removes repeat cost inside a process; the proof removes the first-build cross-checks in every process. Neither changes the other's key or result.
- **Development currency.** The authority currency check reports a proof contract mismatch distinctly from legal staleness, so a developer sees that the fast path is off rather than a refusal. A repository gate fails when the source of the modules implementing the cross-checks changes without a change to the proof contract identity. Those modules are `snapshot.py`, its check helpers and the registered cross-domain check modules.

Proposed wording for the accepted indexed-storage ADR, to be applied only on approval of this decision: append to "Admission and publication": "Publication also proves the registry snapshot cross-checks for the generation's declared selector set and records the outcomes, their proof contract identity and their fact-date window in the database (`2026-10-24-registry-authority-artifact-boundary-snapshot-publication-proof-adr`). Admission of the physical digest admits those records. Runtime snapshot construction relies on them only inside their recorded contract and otherwise validates in full. This is reliance on a publication proof, not a claim that runtime revalidated the corpus." The store-format sentence moves to `cadrumo-authority-sqlite-v5`.

## Rationale

The checks are pure over generation content for the common request shape, and the set to prove is small, so publication can establish them once at a cost of tens of seconds rather than every process paying them. Falling back on any miss makes the change strictly a fast path. Today's behavior is the floor for every request outside the proof, which is what makes it safe for `on`, `revision_id`, `EVENT-n` and projected years. Binding trust to the physical digest follows the indexed-storage decision's existing division of labor. The explicit contract identity covers the one gap that division leaves: validator code is not part of the logical generation. Reusing `build_validated_snapshot` at publication and adding a differential self-check keep one validator and one assembly path, as rule 14's single-owner requirement demands.

## Consequences

- Expected benefit: removes the cross-check share of each process's first snapshot per modelo, about 0.12 s for a cold M100 and about 0.41 s for a four-snapshot workload on the reference workstation. Decode, lazy imports and GC traversal are unaffected. Acceptance target for a plan: in at least ten fresh processes, the median cross-check time for first M100, M200 and M303 snapshots falls to at most 10% of the paired baseline, with typed-equal results, measured after the runtime memo lands. Missing the target is grounds to reject rather than to lower it.
- Costs: about 25 s more publication time for the sweep, and roughly that again for the self-check; a store-format advance with republication; a few thousand small rows in the artifact; a second runtime branch whose correctness rests on the contract identity and the differential gate.
- Behavior changes: a cell that fails at or below its declared grade now blocks publication instead of failing at request time. A runtime proof hit no longer depends on the ambient governed-fact scope.
- Reconsider if: the memo plus `gc.freeze` make first-build cost immaterial for the product's real process topology; selector-set growth makes the sweep material to publication time; or a check gains a runtime input that the proof cannot represent. In that last case the check stays at runtime and the contract identity changes.
- Open questions for the operator:
  - Should a below-ceiling cell failure refuse publication (recommended: yes, fail closed at the gate), or be recorded and refused only at request time as today?
  - Should a proof contract mismatch fall back to runtime validation (recommended), or refuse until republication?
  - Should the two `today_madrid()` fact lookups be keyed to the filing coordinate instead? That would be a separate semantic decision. If taken, it would remove the fact-date window.
  - Is a repository gate tying check-module sources to the contract identity acceptable, or should the identity be an automatic digest of those sources computed at publication and in the runtime build?
- Related proposed wording elsewhere: the proposed `2026-08-14-registry-temporal-coverage-authority-grade-coverage-adr` describes gates that execute "on every load and every snapshot request". If that record is accepted, it should read "on every snapshot request, or through a publication proof under the snapshot-publication-proof decision".

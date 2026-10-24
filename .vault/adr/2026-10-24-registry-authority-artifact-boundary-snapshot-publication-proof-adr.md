---
tags:
  - '#adr'
  - '#registry-authority-artifact-boundary'
date: '2026-10-24'
modified: '2026-10-24'
body_schema: 'body-v2'
body_hash: 'sha256:92048427ae528030c139ac4d37bcb41e9768ded785be77577207c8650b2ebd71'
related:
  - "[[2026-10-24-registry-authority-artifact-boundary-snapshot-publication-proof-reference]]"
  - "[[2026-09-14-registry-authority-artifact-boundary-indexed-storage-adr]]"
  - "[[2026-07-17-mcp-call-latency-adr]]"
  - '[[2026-06-10-period-revision-resolution-adr]]'
---
# `registry-authority-artifact-boundary` adr: `snapshot cross-checks proven at publication` | (**status:** `accepted`)

## Authorization

Accepted 2026-10-24 by the operator ("accept … go"), relayed by the coordinator, together with four rulings on the open questions of the proposed draft and a general direction to remove divergent routes:

1. A case that fails at or below its declared grade blocks publication.
2. A proof-version mismatch falls back to full validation; it never refuses.
3. The two wall-clock fact lookups stay at today's Madrid date. Moving them to the filing coordinate is out of scope and would be a separate decision.
4. The proof version is computed automatically as a digest, not a hand-maintained constant.
5. Where the design kept two ways of validating the same request, one canonical route is preferred, as long as correctness holds.

The sections below incorporate these rulings. Ruling 5 drops the proposed draft's recorded refusals and its publication self-check. Ruling 4 drops its hand-maintained contract constant and repository gate.

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

- `build_validated_snapshot` stays the single canonical validator and the single snapshot assembly route. A proof does not create a second route. The function takes an optional typed proof, and that proof satisfies only the cross-check step of the same sequence. Publication proves cells by calling the same function without a proof. There is no second check implementation, no publication-only variant, and no selection, precedence or grade logic duplicated in SQL (indexed-storage ADR, "Constraints").
- The proven set is exactly: every modelo directory, every filing year from the support floor to the horizon, every declared period token (the symbolic `EVENT-N` as itself), and every member of the grade ladder, with `on=None` and `revision_id=None`. A cell is recorded only when it passes, together with the revision it selected. Refusals are not recorded: at runtime they take the full path, which reproduces the same typed refusal from the validator itself.
- A cell that fails at or below its revision's declared grade refuses publication and preserves the previous descriptor (ruling 1). A refusal above the declared grade is the expected ladder outcome and is simply not recorded.
- A proof is used only when all of these hold: the database was admitted by physical digest; the request is in the proven set after canonical period normalization and selects the recorded revision; the runtime's validator digest equals the recorded one; and the current Madrid date lies inside the recorded fact-date window. Otherwise the same function runs every check (ruling 2). A missing or unusable proof never refuses and never weakens a check.
- The validator digest is computed automatically (ruling 4). Publication records the import closure of the snapshot validator: `snapshot.py` and the registered cross-domain check modules, followed through their `cadrumo` imports. It records each module's source digest and a digest over that list. Runtime re-hashes exactly the recorded modules once per process and compares. A new import can enter the closure only through an edit to a module already in it, so re-hashing the recorded set cannot report a false match. If a module's source cannot be read, the proof is unusable and the request falls back to full validation.
- The fact-date window is the intersection of the validity windows of the governed-fact variants that the proven checks resolved at the publication date. Today each of the two such facts has one open-ended variant, so the window is open above (ruling 3).
- The validator digest identifies the validator, not the law. The logical generation stays the legal-input digest. A validator change alone needs republication to restore the fast path, not a new generation.
- The proof tables are part of the published database and are covered by the physical digest. The store format advances to `cadrumo-authority-sqlite-v5`. Runtime admits both v5 and the preceding v4. A v4 database is a database without proofs, so every request takes full validation until the operator republishes. The descriptor format is unchanged.
- Unchanged by this decision: static inspection (`grade=None`) keeps its narrower non-snapshot claim; the eager `ValidatedRegistryAuthority`, dev conformance, tree validation and diagnostic classification never pass a proof; the public helper checks keep their direct callers; stale-draft and capture checks before durable filing output remain mandatory.

## Implementation

We will prove the snapshot cross-checks once, at publication, for the generation's declared selector set. Runtime will rely on those passes through the admitted physical digest, an automatic validator digest and a fact-date window. Every other request gets full validation in the same function.

- **Domain.** A registry module owns the proof contract that runtime and publication share. It enumerates the proven set through the canonical directory and temporal selection, defines the proof key and the typed proof value, computes the validator closure digest, and records wall-clock fact lookups to derive the window. `build_validated_snapshot` accepts that typed proof and refuses one that does not match the selected revision and request.
- **Publication.** After complete validation, the publisher sweeps the staged database through the runtime reader, with the governed-fact scope bound to that reader's operation. It writes the passing cells, the validator closure and digest, and the window into the database, then computes the physical digest and installs the file. A below-ceiling failure aborts before installation.
- **Runtime.** On a memo miss, `PinnedAuthorityOperation` reads the proof for the normalized request from its reader. It passes the proof to `build_validated_snapshot` when every trust condition holds, and passes none otherwise.
- **Interaction with the runtime memo** (commit `d83d955504`). The memo keys on the generation pin, the full request coordinate, the grade and the Madrid validation date, and caches successes only. The proof changes neither the memo's key nor its result, only the cost of the build behind a miss.
- **Tests** use the real publisher, reader and validator. A usable proof skips the checks. A physical-digest, validator-digest or window miss runs them. A below-ceiling failure blocks publication. Snapshots are typed-equal with and without a proof across the proven set.

This decision is applied to the indexed-storage ADR as its 2026-10-24 amendment: store format `cadrumo-authority-sqlite-v5`, proofs admitted by physical digest, and v4 still admitted without proofs.

## Rationale

For the common request shape the checks are pure over generation content and validator code, and the set to prove is small. Publication can therefore establish them once, in tens of seconds, instead of every process paying for them. Falling back on any miss makes the change strictly a fast path. Today's behavior remains the floor for every request outside the proof, which keeps `on`, `revision_id`, `EVENT-n` and projected years safe. Binding trust to the physical digest follows the indexed-storage decision's existing division of labor. The automatic validator digest covers the one gap that division leaves, because validator code is not part of the logical generation. Passing the proof into the one validator and recording passes only gives a single assembly route and a single source of refusals, as rule 14's single-owner requirement demands.

## Consequences

- Expected benefit: removes the cross-check share of each process's first snapshot per coordinate. On the reference workstation that is about 0.12 s for a cold M100 and about 0.41 s for a four-snapshot workload. Decode, lazy imports and GC traversal are unaffected. The runtime pays one source re-hash of the recorded closure per process.
- Costs: about 25 s more publication time for the sweep, a store-format advance with republication, and a few thousand small rows in the artifact.
- Behavior changes: a cell that fails at or below its declared grade now blocks publication instead of failing at request time. A runtime proof hit no longer depends on the ambient governed-fact scope. Any edit to a module in the validator closure turns proofs off until republication.
- Reconsider if the memo makes first-build cost immaterial for the product's real process topology, if growth in the selector set makes the sweep material to publication time, or if a check gains a runtime input that the proof cannot represent. In that last case the check stays at runtime.
- Related wording elsewhere: the proposed `2026-08-14-registry-temporal-coverage-authority-grade-coverage-adr` describes gates that execute "on every load and every snapshot request". If that record is accepted, it should read "on every snapshot request, or through a publication proof under the snapshot-publication-proof decision".

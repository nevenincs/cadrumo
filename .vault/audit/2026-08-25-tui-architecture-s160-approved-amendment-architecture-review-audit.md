---
tags:
  - '#audit'
  - '#tui-architecture'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:00e0f3cd8e956d1d1072fd48469085f94a5c1dc3b47c483897ead93c3ae98d86'
related:
  - "[[2026-08-24-tui-registry-api-gate-adr]]"
  - "[[2026-08-25-tui-architecture-s128-workspace-projection-composition-reference]]"
  - "[[2026-08-25-tui-architecture-s160-native-work-capture-owner-atomicity-reconciliation-audit]]"
  - "[[2026-08-25-tui-architecture-workspace-v1-contract-reference]]"
---

# `tui-architecture` audit: `S160 approved amendment architecture review`

## Scope

Independent architecture and lifecycle-boundary review of approved amendment
commit `25fff2fed4`. The review compared the amended accepted Workspace ADR and
the amended S128 composition reference with the approved S160 ruling, the S160
reconciliation audit, the closed S125 model contract, the closed S126 producer
contract, the remediated S159 registry capture, and the exact committed
production tree. No source or plan file was changed.

Discovery led with Vaultspec RAG `0.4.2`, then read the governing records and
epicentre source files whole and closed every conclusion with `git grep` against
current HEAD. The semantic code index reported 98 missing published sections,
so no absence conclusion relies on RAG. The final exact census was re-run before
commit and covered Workspace epoch/contract definitions and consumers, native
registry capture/currentness, work resolution and law selection, both singleton
persistence kernels, work repository ports, active-pointer reads and writers,
and every previously identified parallel work selector/projection path.

The amendment correctly settles the public native WORK operand, visible/exact
absence asymmetry, discarded-state visibility, same-state and mixed ambiguity,
active-only lifecycle reuse, atomic one-record catalogue/revision observation,
WORK-before-REGISTRY capture, registry-owned law selection, pure cross-owner
revision assertion, canonical facade promotion, no-shim/no-bridge cutover,
process-incarnation refusal, root-local generation state, and duplicate
selector/projection teardown. The S128 reference now withdraws its former
pre-capture work read and points to the ADR as the single ordering home. Those
parts pass. The blockers below are narrower incompatibilities that must be
resolved before the plan authorizes implementation.

## Findings

### implicit-pointer-transition-owner | high | Pointer A-B-A has no authoritative transition coordinate or legal lock owner

The ADR makes the root-scoped active-bucket pointer part of the physical WORK
observation when `bucket_id` is omitted, requires every implicit-pointer
transition including A -> B -> A to advance the WORK generation exactly once,
and assigns the transition to one WORK root lock. Current pointer transitions
are instead owned by `core._bucket_pointer_io` and
`application.user_profile._profile_pointer_transaction`: `capture_pointer`
returns unversioned bytes, while `write_pointer`, `restore_pointer`, and the
transactional compare-and-restore surface publish pointer changes under their
own ownership. No public monotonic pointer transition coordinate or WORK lock
participation exists.

This is an architecture-document omission rather than merely unimplemented
code. Polling the current pointer value cannot see B when A -> B -> A completes
between WORK observations, and a new counter in `application.modelo` would be a
duplicate shadow owner that existing pointer writers do not advance. The ADR
does not decide whether the canonical pointer writer publishes a native
revision/generation for WORK to compose, or whether every pointer mutation must
join a promoted shared transition primitive and lock order. Consequently its
ABA assertion is not implementable through the currently named owners without
inventing an ownership edge during coding.

### epoch-comparison-domain | high | S126 treats independent physical roots as one comparable semantic owner

The amendment says generation state is scoped by physical storage root,
distinct roots have independent counters, and their integers are incomparable.
The closed S126 contract can encode only the semantic contributor owner.
`ModeloWorkspaceEpochV1` carries `owner`, kind, schema version, and generation;
`require_successor_of` permits comparison whenever that owner string matches;
and `ModeloWorkspaceContributingProjectionV1.require_contract` requires the
epoch owner to equal `contract.contributor.owner`. For WORK that value is the
fixed semantic identity `application.modelo.work_addressing`, not a physical
root or opaque generation domain.

Two roots can therefore yield equal or ordered S126 epochs with the same owner
and integer even though the amended ADR declares them incomparable. Within one
process incarnation, switching roots can also make the second-pass comparison
or a baseline/cursor revalidation accept the same semantic owner and generation
unless another field distinguishes the domains. Process-incarnation binding
does not solve a root change inside the same process. This is S126
decision-versus-code drift caused by the new root rule; it is not evidence that
the root rule itself must be abandoned.

### dual-law-assertion-shape | high | S125 cannot preserve requested and stored revision assertions independently

The amendment requires one pure application assertion to compare both the
optional requested revision and the optional stored work revision with the
law-selected REGISTRY revision. These are independent facts: a visible target
with persisted work can carry both, an exact target carries the stored axis,
and natural absence carries neither. The closed S125
`ModeloWorkspaceRevisionAssertionV1` has only one disposition and one
`requested_revision_id`; `ModeloWorkspaceResolvedTargetV1` carries only that
single record and no stored revision assertion.

S128 therefore cannot echo both outcomes, identify which assertion mismatched,
or represent the successful two-source case without overloading a field whose
declared meaning is the requested visible-target assertion or falling back to
untyped refusal facts. This is an S125 implementation-contract gap exposed by
the clarified law-assertion decision. The amended ADR and S128 reference agree
with each other; the contradiction is between that accepted decision and the
already-closed model surface.

## Recommendations

Before any S160 or S128 coding, amend the accepted Workspace ADR to name the
implicit-pointer transition authority. The correction must choose one canonical
public pointer-native atomic capture/currentness coordinate, owned by the
existing pointer writer, or one promoted shared mutation primitive and lock
order that every pointer transition uses. It must state how an A -> B -> A
completed between two WORK observations remains visible without a WORK-owned
shadow counter. Extend S160's plan scope, or add a prerequisite row, to cover
the canonical pointer I/O and pointer-transaction owner, public facade,
integration with WORK capture, and a biting between-observations A -> B -> A
test.

Add a pre-S160/S167 S126 contract-correction plan row scoped to
`_workspace_producers.py` and its focused tests. Preserve the native integer
unchanged, but add a safe opaque generation-comparison domain to the epoch (or
make an equivalently typed distinction), require domain equality before epoch
comparison, and include that coordinate in second-pass and baseline/cursor
derivation. Raw root, bucket, namespace, and key values must remain private.
Update the epoch schema/contract digest and adversarially prove same-root
success, distinct-root incomparability, root switching, A -> B -> A, and
cross-process refusal. A global semantic-owner counter is not an equivalent
correction because it contradicts the approved independent-root rule.

Add a pre-S128 S125 contract-correction plan row scoped to
`_workspace_models.py` and its focused tests. Replace the single ambiguous
revision assertion with a strict typed two-axis shape, or a bounded
source-discriminated tuple, that preserves requested and stored revision IDs
and outcomes independently. Prove natural absence, visible work with both
assertions, exact stored assertion, and each mismatch arm. Do not encode either
axis as generic facts or add a compatibility reader.

Keep the plan's persistence and selector teardown explicit: both singleton
one-record kernels, the work repository protocol and adapter, the sole
`application.modelo` facade, the raw work-side registry loader, and every
substitutable work scan identified by the S160 audit must have an owning row.
S128 remains only the capture-and-compose consumer and must not absorb any of
those repairs.

## Disposition

FAIL. The amendment resolves the S160 audit's primary selection, atomic
catalogue, registry split, ordering, facade, and teardown rulings, and the S128
reference now respects the single-home-fact boundary. Planning and coding are
still blocked by one unresolved pointer-transition ownership decision and two
HIGH incompatibilities with the closed S125/S126 contracts. Correct the ADR and
add the named prerequisite contract rows before implementing native WORK
capture or Workspace composition.

## Remediation re-review

### Scope and evidence

Fresh independent re-review at committed HEAD `105a6380199f1858aa266d69f56e9f74c8336bfb` of the substantive remediation bodies in `b9cb7a3682` and their CLI-owned closure metadata in `d22845d2cc`. The three amended records have no later body delta through HEAD, and the relevant audit, Workspace model/producer, pointer model/IO, and pointer-transaction files were clean relative to HEAD. Unrelated shared-worktree changes were preserved.

Discovery again led with semantic Vaultspec RAG searches for the pointer transition owner, epoch comparison domain, and independent revision axes. The code index reported two missing published sections, so every presence and absence conclusion was closed with whole-file reads and exact `git grep` against HEAD. The exact source census found `ModeloWorkspaceEpochV1` only in `_workspace_producers.py` and its focused test, the baseline stamp digest and single `revision_assertion` only in `_workspace_models.py` and its focused test, and zero source occurrences of `comparison_domain`, `requested_revision_assertion`, or `stored_revision_assertion`. That is expected unimplemented state, not contrary implementation evidence.

### Prior HIGH closure

The `implicit-pointer-transition-owner` HIGH is architecturally closed. The accepted ADR now names the existing active-profile pointer owner behind the public `cadrumo.application.user_profile` facade, the public core pointer IO record, and the existing custody-root transaction lock as the sole transition authority. The same pointer record carries a durable monotonic coordinate; clear writes an absent-selection tombstone; each successful state-changing write, restore, or clear advances exactly once; and idempotent no-change does not advance. Because another process must publish through the same locked record, a completed A -> B -> A remains observable even when no WORK capture occurs between transitions. WORK neither persists nor owns a pointer counter.

The implicit and explicit WORK compositions are now disjoint and implementable. Implicit capture atomically composes the authoritative pointer coordinate with the one-record catalogue coordinate, rereads the pointer coordinate under the same dependency order, retries on change, and derives an injective order-preserving native generation from those two owner coordinates. Its comparison domain binds root, pointer-owner physical identity, selected bucket, catalogue namespace/key, and process incarnation. Explicit capture excludes the pointer coordinate, lock, retry limb, and pointer-domain limb and preserves the catalogue generation unchanged. Catalogue and pointer ABA, switched bucket, distinct root, and stale-currentness behavior are all named as biting conformance cases.

The `epoch-comparison-domain` HIGH is architecturally closed. The ADR requires epoch schema version 2 with an opaque native-owner-derived `comparison_domain` beside the unchanged native integer. An S126 registration copies both unchanged; it cannot derive the domain from the semantic owner. Equality, successor checks, and second-pass currentness require exact domain equality before integer comparison, so distinct roots, switched roots, physical scopes, and process incarnations refuse rather than compare coincident integers. The complete owner/kind/schema/domain/generation tuple feeds a separate sorted contributor-epoch digest, the Workspace baseline token, and every cursor or facet continuation. Producer-contract and inventory digests change for schema version 2, the runtime domain stays out of the static stamp, and no schema-version-1 reader remains.

The `dual-law-assertion-shape` HIGH is architecturally closed. S125 now has fixed `requested_revision_assertion` and `stored_revision_assertion` records with source-fixed discriminators, optional revision IDs, and the closed `not_present`/`matched`/`mismatched` disposition. The resolved target and revision-mismatch refusal preserve both axes, including natural absence, exact lookup, visible persisted work, requested-only mismatch, stored-only mismatch, and simultaneous mismatch. S128 performs exactly one WORK capture, then exactly one S159 law-selected REGISTRY capture, and only then applies one pure two-axis assertion without a work reread, raw registry loader, asserted-id selection, or generic-fact escape.

### Required plan prerequisites

The remediation is a decision closure, not proof that the checked S125, S126, or S159 implementations already satisfy it. Before S160/S167/S128 execution, the plan needs explicit CLI-authored ownership for these exact prerequisite changes:

- an S125 contract-correction row replacing the single assertion with the two fixed axes and adding `contributor_epoch_digest` to the baseline/cursor consistency shape, with no compatibility reader;
- an S126 epoch-schema-v2 row adding the opaque comparison domain, domain-before-integer comparison, contract/inventory digest changes, and same-root, distinct-root, switched-root, and cross-process tests;
- a registry-native-coordinate correction row extending the checked S159 capture/currentness surface to derive and return its opaque physical-root/process domain, because current `RegistryAuthorityCapture` and `read_current_generation` expose only the integer and S126 is forbidden to mint the missing coordinate;
- a pointer-authority cutover row owning the pointer record/IO schema, durable coordinate and absent tombstone, public pointer transaction/facade, every production pointer reader/writer/restore/clear migration, custody journal/rollback adaptation, canonical root-lock proof, idempotence, and between-WORK-observations cross-process A -> B -> A;
- a one-record persistence row repairing both singleton `load_revisioned` kernels and exposing the inseparable catalogue/revision observation through `WorkUnitCatalogueRepositoryProtocol` and its concrete adapter, with real present/present, absent/present, and present/absent interleaving tests.

S160 must then depend on those rows and S159, widen beyond `_work_addressing.py`, publish the implicit/explicit WORK native capture/current-coordinate pair through the sole application Modelo facade, converge the pure captured-catalogue selector and every substitutable consumer, remove the raw-loader assertion path, and delete parallel scans rather than bridge them. S161-S166 must each return their native comparison domain as well as generation; S167 follows all eight corrected native surfaces plus S126 v2; S128 follows S160-S167 plus the S125 correction; and S130/S139 retain the aggregate no-duplicate, domain, baseline/cursor, ABA, and two-axis fixed-point proof. None of these prerequisites belongs inside S128 composition.

### Remediation disposition

PASS for the amended architecture. All three prior HIGH decision gaps are resolved without a WORK-owned shadow counter, root/process integer comparison, or collapsed revision evidence. The original FAIL above remains the historical disposition of the earlier amendment and is intentionally not rewritten. This PASS does not assert source delivery or authorize coding under the current narrow plan: implementation remains blocked until the prerequisite rows and row dependencies above are added through the plan verbs.

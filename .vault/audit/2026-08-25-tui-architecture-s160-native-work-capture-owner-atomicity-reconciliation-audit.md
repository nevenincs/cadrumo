---
tags:
  - '#audit'
  - '#tui-architecture'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:bfef99e8d73de1c10e38929c02b4fb5c8afe8c3dc1d730c469ee0ae0b04e74e4'
related:
  - "[[2026-08-24-tui-registry-api-gate-adr]]"
  - "[[2026-08-11-tui-architecture-plan]]"
  - "[[2026-08-25-tui-architecture-s128-workspace-projection-composition-reference]]"
  - "[[2026-08-25-tui-architecture-workspace-v1-contract-reference]]"
  - "[[2026-06-04-modelo-addressing-ux-adr]]"
  - "[[2026-06-10-period-revision-resolution-adr]]"
---
# `tui-architecture` audit: `S160 native work capture owner and atomicity reconciliation`

## Scope

Read-only reconciliation of open Step `W03.P20.S160` at committed HEAD
`9ad389e41ee93aeeabeb6eeddb48d47fcf563452`. The audit compared the accepted
Workspace owner-seam decision, the open plan row, the S128 composition
reference, the existing Modelo addressing and selector authorities, the
work-catalogue persistence port and both singleton persistence kernels, and
every exact production site found to reinterpret the same work-target
coordinate. The scoped source files were clean relative to HEAD; unrelated
shared-worktree changes were neither read as authority nor modified.

Discovery began with live Vaultspec RAG `0.4.2` vault and code searches and was
closed with whole-file reads and targeted `rg` censuses. The census found no
S160 native work capture, current-generation reader, compatibility alias,
fallback, shim, or bridge at HEAD. That absence agrees with the unchecked plan
row; the findings below concern whether the accepted decision and current plan
describe a legal atomic implementation path.

## Decision inventory

- The accepted registry API gate makes `application.modelo.work_addressing` the
  `work` semantic owner and `resolved_work_target` its producer identity. It
  requires one public native projection-plus-generation capture, one public
  current-generation read, one captured semantic value, immutable or
  snapshot-isolated output, and ABA-safe monotonic owner generation
  (`.vault/adr/2026-08-24-tui-registry-api-gate-adr.md:278`, `:326`, and
  `:353`).
- The accepted request contract distinguishes visible and exact work targets:
  exact absence refuses, natural absence is a successful explicit absent-work
  state, stored revision is assertion evidence only, and Workspace never
  creates work (`.vault/adr/2026-08-24-tui-registry-api-gate-adr.md:105`).
- S160 promises to delegate the existing addressing and revision-assertion
  authority without a second selector or repository read path, but scopes only
  `_work_addressing.py` and focused addressing tests
  (`.vault/plan/2026-08-11-tui-architecture-plan.md:168`).
- S167 later registers the native surface, and S128 later composes Workspace
  only from registrations (`.vault/plan/2026-08-11-tui-architecture-plan.md:175`
  and `:176`). Those later Steps cannot repair a torn native capture without
  becoming forbidden alternate owners.

## Findings

### revisioned-read-atomicity | critical | Both singleton kernels can pair one document with another row revision

`ProfileEnvelopedModelSecurePersistence._load_with_revision` obtains the
decoded document through `self.load()` and then loads the secure object again
for its revision (`src/cadrumo/adapters/persistence/profile/_secure_enveloped_document.py:217`,
`:224`, and `:225`). A concurrent A to B transition between those calls returns
document A with revision B. A guarded writer can then write a mutation derived
from A while asserting B and overwrite B without a conflict. The absent/present
interleavings can likewise pair an empty document with a present revision or
discard the first present read.

The bare-document sibling repeats the same split read
(`src/cadrumo/adapters/persistence/profile/_secure_model_document.py:187`,
`:194`, and `:195`). `WorkUnitCatalogueRepository.load_revisioned` delegates to
the enveloped kernel (`src/cadrumo/adapters/persistence/profile/modelos_work_units.py:243`).
Therefore the repository currently offers no atomic catalogue-plus-revision
witness from which S160 can derive an inseparable projection and generation.
Implementing a process counter in `_work_addressing.py` would label a torn value;
re-reading to check it would violate the accepted one-native-capture contract.

### s160-file-scope | critical | The plan omits the persistence and public-facade files the accepted capture requires

The plan names only private `_work_addressing.py` and focused tests, while the
first usable atomic witness must be repaired in the shared persistence kernel
and exposed through the work repository port and concrete adapter. The accepted
decision also requires promotion through the canonical owning-package facade.
Neither the kernel, `modelos_work_units.py`, the domain repository protocol, nor
`application/modelo/__init__.py` appears in the S160 file scope. Staying inside
the row would require either a second repository read path in application code
or a private/non-facade surface; both are expressly forbidden by the same row
and the accepted ADR. This is plan-versus-code drift, not an implementation
detail S167 can defer.

### registry-authority-bypass | high | The existing revision assertion authority is a raw registry-loader path

`resolve_registry_revision_for_work_target` directly calls
`load_registry_tree(bundled_path("registry", "aeat"))` and then
`select_revision` (`src/cadrumo/application/modelo/_work_addressing.py:723` and
`:756`). The always-on registry-authority rule makes
`ValidatedRegistryAuthority` the production orchestration boundary and forbids
raw loader plus independent validation/selection paths. S160's instruction to
delegate this existing function therefore conflicts with its simultaneous
prohibition on an alternate loader. Native capture cannot make the bypass
authoritative merely by wrapping it with a generation.

### s128-capture-order | high | The reference resolves work before the one permitted native work capture

The accepted ADR's consistency protocol begins by invoking each selected S126
registration; each call performs the canonical owner's one atomic capture, and
assembly follows only from those captured projections
(`.vault/adr/2026-08-24-tui-registry-api-gate-adr.md:353` and `:360`). The S128
reference instead directs target resolution through the addressing owner at
step 2 and invokes the selected registrations at step 4
(`.vault/reference/2026-08-25-tui-architecture-s128-workspace-projection-composition-reference.md:44`
and `:46`). Current `resolve_modelo_work_target` reaches the repository through
the selector (`src/cadrumo/application/modelo/_work_addressing.py:695`). The
reference sequence therefore reads work state once to choose the target and a
second time to capture it. A transition between the reads can resolve A and
capture B before the two-pass generation check even begins. The reference is
carrying a sequencing decision that conflicts with its accepted decision home.

### owner-coordinate | high | The semantic owner label does not fix the physical owner or generation scope

The ADR fixes the labels `application.modelo.work_addressing` and
`resolved_work_target`, but the current projection spans three independently
changing coordinates: active-bucket resolution in `_selectors.py`, one
per-bucket encrypted catalogue row behind `WorkUnitCatalogueRepository`, and
law-selected registry state in `resolve_registry_revision_for_work_target`.
The corpus does not state whether the native owner identity is process-wide,
per active-profile selection, per bucket, per secure-store physical root, per
catalogue row, or per resolved target. It also does not state whether an active
bucket A to B to A transition advances one owner generation, selects another
owner, or belongs outside the work epoch.

A catalogue-row generation would advance for unrelated work-unit mutations; a
per-target generation would need a notification or observation mechanism for
every catalogue writer; and revision assertion also depends on the separately
registered registry owner. Each shape has different ABA and lock-order
semantics. The current fixed-point labels are insufficient to test which
transitions must advance the S160 generation.

### address-state-contract | high | Absent, discarded, active-only, exact, and broad-address behavior is under-specified for the native surface

The canonical selector intentionally has two lifecycle views. Natural reads
include discarded units (`natural_target_work_units` at
`src/cadrumo/application/modelo/_selectors.py:324`), while create-or-reuse
filters to `BORRADOR` (`active_natural_target_work_units` at `:363`). Natural
absence returns `ModeloWorkResolution(state=ABSENT)` at `:376`; exact absence
raises `ModeloWorkUnitNotFoundError` at `:465`; the general natural resolver
uses the all-state set at `:490`. Consequently one discarded unit is resolved,
an active plus discarded pair is ambiguous, and the active-create view treats
discarded work as absent before the single writer issues its terminal refusal.

The Workspace ADR says exact absence refuses, zero natural matches is explicit
absence, and multiple active natural matches refuse, but it does not settle the
discarded-only or active-plus-discarded Workspace cases. S160 also names a
resolved-work-target surface without naming its input type. The public
`ModeloWorkTarget` union includes the permissive transport
`ModeloWorkAddress` as well as the two canonical operands
(`src/cadrumo/application/modelo/_work_addressing.py:278`), whereas Workspace V1
admits only the tagged visible and exact operands. Without a ruling, a native
capture can accidentally widen Workspace admission or erase a terminal state.

### selector-policy-fragmentation | high | Four production pathways bypass part or all of the canonical selector policy

The exact census found one canonical natural selector family in
`_selectors.py` and these parallel production paths:

- `work_review_projection._work_unit_for_target` scans the repository itself,
  then filters by law-selected revision (`src/cadrumo/application/modelo/work_review_projection.py:272`,
  `:283`, and `:302`). It can choose the law-revision candidate despite another
  natural candidate, where the canonical selector refuses natural ambiguity.
- `_external_import_actions.py` performs its own active-only natural scan,
  ambiguity branch, revision comparison, and create branch (`:201` through
  `:238`) instead of delegating the canonical active resolver and single writer
  as one policy chain.
- `overview._data_prep._work_unit_step` filters a preloaded active tuple and
  takes `matching[0]` (`src/cadrumo/application/overview/_data_prep.py:325`,
  `:332`, and `:351`), silently selecting where the canonical policy would
  expose ambiguity.
- `_calculate_input.py` performs direct exact catalogue reads at `:1413` and
  `:1421`, then a raw registry load and selection at `:1426` and `:1428`.
  This site is constraint-shape-divergent from a natural selector, so it is not
  classified as a substitutable natural lookup; it is still a parallel
  repository/registry read path that cannot participate in a one-capture
  consistency claim.

The census excluded `_projection.py` year-wide and quarter-wide folds because
their constraint shapes intentionally aggregate multiple periods rather than
resolve one substitutable work target. The four sites above either implement
the same natural coordinate or reread its exact/registry components. S161 has a
planned home for bounded-review convergence, but the external-import, overview,
and calculate-input teardown is not named by S160-S167 or S128.

### lifecycle-boundary | medium | The S128 reference contains a forked implementation decision

The S128 reference is a grounding artifact, yet its numbered algorithm decides
that target resolution precedes native capture. The accepted ADR decides the
opposite one-capture boundary, and the plan does not adjudicate the discrepancy.
This is both displaced decision language and a forked sequencing fact under the
single-home-fact boundary. Editing the reference alone would hide the unresolved
owner/input/absence questions; editing the ADR or plan without author approval
would decide them in an audit. No corpus decision was changed here.

## Recommendations

### Required amendment questions

1. What exact native S160 input is authoritative: only
   `ModeloVisibleFilingTarget | ModeloExactWorkUnitTarget`, or the broader
   `ModeloWorkTarget` including `ModeloWorkAddress`?
2. For natural Workspace reads, are discarded-only targets resolved terminal
   state or explicit absence, and does active-plus-discarded mean ambiguity?
   Must exact targeting continue to expose discarded state while exact absence
   refuses?
3. What is the WORK owner identity and ABA domain: application process,
   active-profile selection, bucket, secure-store physical root, singleton row,
   or individual resolved target? Which A to B to A transitions advance its
   generation?
4. Is law-selected revision part of the WORK native value, or is it assembled
   only from separately captured WORK and REGISTRY values? If it remains in
   WORK, what lock/order or retry contract makes the cross-owner assertion
   atomic without a raw loader or second registry read?
5. Does S128 target resolution occur inside the selected WORK native capture,
   making the reference's current step 2 parsing-only, or does the accepted ADR
   intentionally permit a pre-capture work read? The corpus must name one order.
6. Which additional files and consumer removals belong in S160's atomic scope:
   both singleton kernels, the work repository protocol/adapter, the application
   facade, and the exact duplicate sites? Which later Step owns any remainder?

### Teardown recommendations after the author ruling

- Repair both singleton `_load_with_revision` implementations at their shared
  homes so one `SecureObjectRecord` supplies both decoded document and revision.
  Add real encrypted-SQL interleaving witnesses for present-to-present,
  absent-to-present, and present-to-absent transitions and prove the gate bites.
- Remove the raw loader from `resolve_registry_revision_for_work_target` and
  delegate law selection/assertion to the public validated registry authority.
- Promote the native capture and current-generation read through the sole
  `cadrumo.application.modelo` facade in the same atomic change as its
  implementation and consumer updates; do not add a bridge or alias.
- Delete, rather than wrap indefinitely, the substitutable work-review,
  external-import, and overview selectors. Thread one captured catalogue/work
  value into calculate-input helpers or delegate their exact lookup and registry
  resolution to the canonical public authorities; retain their distinct domain
  error translations at the boundary.
- After the ADR author resolves the questions, amend S160/S161/S128 ownership
  and file scope through the plan verbs, then reduce the S128 reference to
  grounding that cites the accepted sequence. Keep the S130/S139 semantic-plus-
  exact census as the aggregate fixed point.

## Disposition

S160 is not implementable as currently scoped without violating at least one
accepted invariant: atomic projection-plus-generation capture, one repository
read, validated registry authority, or public-facade ownership. The persistence
torn-read defect is independently actionable, but the owner identity, target
lifecycle semantics, registry/work split, capture order, and step ownership
require an approved ADR/plan reconciliation. No production code, ADR decision,
plan decision, or existing lifecycle document was changed by this audit.

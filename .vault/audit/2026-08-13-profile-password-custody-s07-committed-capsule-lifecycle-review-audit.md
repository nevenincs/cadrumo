---
tags:
  - '#audit'
  - '#profile-password-custody'
date: '2026-08-13'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:edc18aa7c92c0b9fbffaa57c6f7f62e4b2402955b6655e7cb806a084d82affbd'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
  - "[[2026-08-13-profile-password-custody-rollup-adr]]"
---

# `profile-password-custody` audit: `S07 committed capsule lifecycle review`

## Scope

Independent review of `W02.P03.S07` against the approved custody roll-up ADR and
the completed S01-S06 execution and audit evidence. The review covered the
committed-capsule aggregate and repository, the lifecycle service, facade
exports, the custody inventory seam, focused real-filesystem tests, and the
production consumers of the replaced public repository, aggregate, and
lifecycle contracts. S08, S09, production remediation, and plan mutation were
excluded.

## Findings

### s07-incomplete-public-cutover | high | Replaced public contracts break live application paths

The new `ProfileRepository`, `ProfileAggregate`, and `ProfileLifecycleService`
are coherent in isolation, but they replace existing facade-exported types in
place without migrating their production consumers. `_orchestration.py` still
constructs `ProfileRepository` with `secure_objects` and `schema`, constructs
`ProfileLifecycleService` with `repository`, `validator`, and `events`, and
calls removed `create`, `delete`, `reactivate`, `complete_setup`, `select`, and
`rename` repository methods plus removed `read` and `edit_fields` lifecycle
methods. Calculation, filing, wizard, overview, modelo-work, and configuration
CLI consumers still require the removed aggregate `record` or `status` fields.
A direct BasedPyright gate over the changed surface and representative live
consumers reports 86 errors, including each of these contract breaks. Thus the
normal application cannot use the refrozen S07 surface even though its two new
focused tests pass.

### s07-duplicate-lifecycle-authority | high | Retired record and manifest writers remain live beside the new sole writer

`UserProfileLifecycleRepository` remains facade-exported and production-wired
through `_orchestration.py`, with live `save` and `delete` mutation surfaces.
The same orchestration module continues to describe and execute manifest,
secure-object record, pointer, tombstone, reactivation, setup-completion, and
rename flows outside the new custody lifecycle service. This is not merely a
downstream read-model dependency: it leaves multiple active lifecycle writers
and retired bucket/manifest authority in the exact application boundary S07 is
required to make capsule-only and single-owner.

### s07-label-collision-publication | high | Duplicate labels can publish committed capsules before becoming ambiguous

`ProfileLifecycleService.create` and `restore` publish the immutable capsule
before `ProfileRepository.set_label`, while `set_label` performs no exact-label
collision preflight or serialized uniqueness check. Two committed UUIDs can
therefore receive the same label and both operations report success; subsequent
label resolution refuses because it finds multiple matches. This regresses the
existing duplicate-label refusal contract and cannot be repaired by a check
after capsule publication. The focused tests cover one successful label only
and do not exercise sequential or concurrent collision.

### s07-inventory-root-follow | high | Capsule discovery enumerates a followed storage-root directory

`list_current_profile_custody_capsule_ids` begins with `Path.is_dir()` and
`Path.iterdir()` on the capsules root. Both follow a symlink or reparse point at
that root before per-candidate current-format recognition applies its anchored
checks. Although a candidate may later be refused, discovery has already
traversed and enumerated an attacker-selected external directory. The sole
application inventory seam therefore does not preserve the established
no-follow storage boundary, and the two focused lifecycle tests contain no
root-link/reparse case.

Verification evidence: the focused lifecycle plus custody transaction selector
passes 29 tests in 28.45 seconds and scoped Ruff passes. Those green gates prove
the isolated happy path and transaction regression only. The production
call-graph BasedPyright gate fails with 86 errors attributable to the S07 public
contract replacement; no unrelated collection failure was involved in that
result.

## Recommendations

S07 remains open. Complete one hard cutover rather than adding compatibility
shims: migrate every production constructor, method call, and aggregate-field
consumer to the capsule-backed boundaries; remove the retired lifecycle writer
and manifest/bucket mutation routes from production composition and the facade;
then run static analysis across the entire affected call graph and real
application lifecycle tests, not only the new module.

Make label uniqueness an application-owned, root-serialized precondition that
is proven before capsule publication for create and restore. Add real sequential
and sibling-process collision tests that prove a refused duplicate leaves no
new capsule, projection, journal ambiguity, or pointer change.

Replace root discovery with the canonical descriptor-relative POSIX and
ancestor-pinned Windows directory primitives, refusing a linked/reparse
capsules root before enumeration. Add real root symlink/reparse tests and retain
the current-format marker validation for every UUID candidate.

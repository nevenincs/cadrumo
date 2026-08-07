---
name: revision-resolution-is-law-determined
trigger: always_on
---

# Revision resolution is law-determined; carried observations stamp it

## Resolution is derived, never injected

Every production calculation, verification, filing, export or projection path
MUST resolve its registry revision from `(modelo, filing_year, period)` through
`ValidatedRegistryAuthority.snapshot` / `select_revision`, or through
`resolve_registry_revision_for_work_target`. A stored, literal, or
operator-supplied `revision_id` may only be **asserted equal** to that
resolution, never injected as the selector.

AEAT binds every `(modelo, filing_year, period)` triple to exactly one revision
by publishing orden, so "which revision applies" is a derived fact. Feeding a
stored id back into resolution makes the stored value *causal* — the defect class
that lets one year's numbers be computed under another year's norms. The
non-overlap window gate guarantees resolution is unique, so a `revision_id`
narrowing can only equal the law-determined pick or refuse.

## How

- **Good:** load the work unit, resolve the snapshot from its `filing_year` and
  `period`, then assert equality and raise an instructive refusal naming both
  revisions on mismatch. A creation-time `--revision` is accepted only when it
  names exactly the resolved id — an assertion handle, not a free override.
- **Bad:** passing a stored `revision_id` into `authority.snapshot(...)` on a
  calculation path, so resolution is *selected* by the stored value.

## Carried observations stamp their revision and re-confirm it

Every persisted calculation observation MUST carry a required, non-empty
law-determined `stamped_revision_id`, and a missing or invalid stamp MUST refuse
at strict load. Every cross-period or cross-year carry MUST re-confirm a
populated stamp against `select_revision` for the source context before trusting
the value; a divergent or otherwise unreconfirmable stamp MUST block the carry.

The carry path is the one place a revision error *compounds across years*: a
prior filed under the wrong revision injects that revision's norms into every
later filing that folds it in.

## How

- **Good:** the producer persists the stamp from the law-selected snapshot it
  already holds; anti-tautology coverage physically deletes the persisted field
  and proves loading fails; the carry gate re-confirms through `select_revision`.
- **Bad:** reconstructing, defaulting, or bypassing a missing stamp — legal
  provenance must exist in the stored evidence itself. Treating a divergent stamp
  as a warning instead of a blocker.

Source: ADR `2026-06-10-period-revision-resolution-adr` (rulings 1 and 3).

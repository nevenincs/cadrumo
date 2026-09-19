---
tags:
  - '#audit'
  - '#profile-password-custody'
date: '2026-08-25'
modified: '2026-08-26'
body_schema: 'body-v1'
body_hash: 'sha256:83af1284f83b25a56ad8075f43584ebe4fb34479fb2678f038d156b8ce17d33e'
related:
  - '[[2026-08-13-profile-password-custody-plan]]'
  - '[[2026-08-24-deadline-window-revision-authority-adr]]'
  - '[[2026-08-14-registry-temporal-coverage-adr]]'
---

# `profile-password-custody` audit: `s252 registry documentation authority review`

## Scope

Formal review of `W06.P12.S252`: the registry-backed documentation adjudication,
the filing dependency inventory guard, the compact overview-calendar projection,
their focused tests, the thirteen scoped page goldens, and the Step execution
record. The review traced the relevant code and accepted decisions with
Vaultspec RAG, then confirmed exact owners and call sites.

The implementation provenance reviewed was concurrent commit `5df2bdc09b`; the
documentation-contract provenance was concurrent commit `f6ce88260c`, plus the
current `iva-lifecycle-q2` contract and current generated sequence records. The
review treated the unrelated export composition and other shared-worktree changes
in those commits as out of scope.

Authority ownership remains intact:

- `cross_period_dependency_inventory` enumerates candidate registry revisions,
  rejects every revision whose `effective_authority_grade` is not
  `RegistryAuthorityGrade.FILING`, and delegates target resolution and snapshot
  construction to `ValidatedRegistryAuthority.snapshot`. It does not reproduce
  applicability, calculation, readiness, or revision-selection rules.
- `overview_calendar_output` serializes `generated_at`, `completeness`,
  `taxpayer_model_declared`, and `incomplete_reason` from the already-built
  application calendar. The compact payload schema admits those fields without
  deriving them, and therefore does not create a second calendar, taxpayer,
  completeness, or deadline authority.
- The documented coordinates match bundled revision epochs: Modelo 184 filing
  year 2024 selects `2015-2024`; Modelo 303 filing year 2026 selects
  `2026-y-siguientes`; and Modelo 390 filing year 2025 selects `2025`. The
  annual lifecycle no longer claims unsupported Modelo 390 filing authority for
  2026.
- Generated JSON records remain owned by `python -m dev.docs.sequences refresh`;
  the authored source remains the `.seq` contract. No generated output was
  promoted into an independent behavioural declaration.

Focused reviewer reruns passed: the three dependency-inventory tests and the
selected calendar coordinate/coverage round-trip test. The execution record also
reports the clean cumulative page, parser/comparator, documented-command,
registry, dependency CLI, calendar payload, and Ruff gates.

## Findings

No findings. The scoped changes preserve the accepted registry-authority and
deadline-window boundaries, exclude dependency targets below filing grade, retain
calendar taxpayer/completeness metadata, and align the documentation examples
with the bundled law-selected revisions.

The known broader `ty` diagnostics in the calendar renderer and the two
binding-readiness fixture-filename failures were not introduced by the reviewed
S252 lines and are not S252 findings.

## Recommendations

Approve `W06.P12.S252` for closure. Keep the unrelated renderer diagnostics and
fixture-policy failures in their owning workstreams; do not widen this Step into a
repository-wide repair.

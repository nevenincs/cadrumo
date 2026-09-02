---
tags:
  - '#audit'
  - '#tui-architecture'
date: '2026-09-03'
modified: '2026-09-03'
body_schema: 'body-v2'
body_hash: 'sha256:c02f9fe4f57672bcbc11d4cb4e0f8b93b243647ceb38e4a43ab1d17d753eac5d'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# `tui-architecture` audit: `w08 p25 s367 review`

## Scope

Independent review of `W08.P25.S367` across the frontend-neutral evidence
provider, its focused contract tests, the CLI composition seam, and the existing
calendar-evidence authority. The review checked independent local/AEAT
authority, available/stale/locked/never-captured/unavailable meaning, natural
address joins, taxpayer filtering, implicit I/O, and preservation of the CLI's
schedule-only degradation behavior.

The provider is pure by inspection and accepts already-loaded values only.
`CalendarEvidenceReadOutcome` preserves stale values and their required
timestamp, rejects values for unobservable states, and keeps the two state
records in the output. The CLI still owns every concrete repository, settings,
artefact and parser adapter; after a successful all-source read it now delegates
reconciliation to `build_calendar_evidence_projection`, while its existing
single `try` boundary continues to return no evidence plus the same warning on
failure. Existing identity behavior is also retained deliberately: a declared
mismatch filters AEAT rows, while an absent declared NIF does not substitute the
known-wrong projection placeholder.

The focused provider plus CLI degradation/local-evidence run passed with 9
tests. Ruff passed for all three reviewed files, and Basedpyright reported 0
errors, warnings or notes. Two direct authority probes nevertheless reproduced
the high-severity defects below.

## Findings

### axis-authority | high | The local bundle can still establish the AEAT axis

`LocalCalendarEvidenceSources` says it is capable of establishing the local
filing axis and structurally excludes every explicit AEAT source. The provider
nevertheless passes its `filing_records` unchanged to the legacy reconciler,
which projects `ModeloRecord.external_evidence` and `aeat_accepted` onto
`aeat_submission_state`, reference and evidence-kind fields. The post-merge mask
only clears those fields when the separately supplied AEAT state is
unobservable. Consequently an `AVAILABLE` but empty AEAT bundle plus one local
record carrying external evidence returns a positive AEAT claim sourced solely
from the local bundle. The direct probe returned `ready_to_file`, `accepted`
and the local record's external reference.

The inverse state is also inconsistent: marking AEAT never-captured or
unavailable suppresses embedded official evidence from the same local record.
Thus the caller must secretly know that `aeat_state` covers evidence embedded
inside `local.value`, even though neither the types nor their documentation
express that aggregation. The split source types do not yet enforce the split
authority they advertise.

### natural-address-determinism | high | Equal-strength evidence for one address is input-order dependent

The provider documents the natural `(modelo, filing year, period)` join as an
owned delegated invariant and its focused test claims determinism, but that test
uses two different addresses. For two active observed events at the same
address and submission rank with different references or timestamps, the
legacy `_stronger_filing_evidence` tie uses `>=` and copies the later candidate.
Reversing the input therefore changes the resulting authoritative reference and
submission time. A direct probe returned `aeat-other` at 10:30 in one order and
`aeat-303-1T` at 09:30 in the reverse order. Conflict references may be sorted,
but the primary evidence claim remains order-dependent.

### provider-test-teeth | medium | Focused tests miss both cross-axis and same-address failures

The new runtime source-type checks are not directly tested, and state/value
mismatch coverage exercises only available and locked with the local bundle.
More importantly, the natural-address case proves only permutation of distinct
addresses, and no case gives a local record embedded AEAT evidence while the
AEAT bundle is empty or unobservable. The I/O test patches only `builtins.open`
and `socket.create_connection`; the current implementation is pure, but that
guard is not a comprehensive detector for `Path.open`, repository construction
or other network entry points. The green focused suite therefore cannot detect
the two production findings above.

### final-remediation-disposition | low | Axis authority and deterministic merging are closed

Final re-review confirms that the provider now reconciles the two bundles
separately, masks the non-owning axis on each result group, and joins those
groups through the calendar-evidence authority. `AeatCalendarEvidenceSources`
explicitly accepts the filing records whose embedded external evidence can
establish AEAT meaning, and the CLI intentionally supplies its already-loaded
records to both inputs. It does not move any repository, settings, encrypted
artefact or parser adapter into application code. The cross-axis probe now
returns `ready_to_file`, `not_observed`, and no AEAT reference when only the
local bundle contains an accepted external-evidence record. This closes
`axis-authority`.

The existing authority now selects both local and AEAT limbs with complete
semantic precedence keys and sorts merged output with those same keys. Reversing
two equal-rank observations at one natural address now produces identical
evidence in both orders, selecting the later `aeat-other` observation at 10:30
and retaining sorted conflict references. This closes
`natural-address-determinism`.

The expanded tests directly cover both wrong-bundle directions, cross-axis
masking, available-empty versus never-captured, stale retention, same-address
permutation, and expected-identity match, mismatch and absence. The final local
focused run passed 19 tests across the provider and CLI degradation/local
evidence seams; Ruff and Basedpyright were clean across the provider, reconciler,
focused test and CLI consumer. Together with direct purity inspection, this
closes `provider-test-teeth` at the reviewed scope. No critical, high or medium
finding remains open.

## Recommendations

1. Make axis ownership explicit before crediting S367. Either project local
   records into local-only rows and route their embedded external evidence
   through the AEAT outcome, or define one typed aggregate whose AEAT state is
   computed from every AEAT-capable source. Do not retain a contract where the
   caller must coordinate undocumented cross-bundle meaning.
2. Give equal-strength evidence a complete deterministic semantic tie-breaker,
   or reject unresolved competing primary claims. Prove permutation equality
   for duplicate natural addresses with different references and timestamps.
3. Add bite-proven cases for cross-axis leakage/suppression, every outcome
   state, wrong source-bundle types, declared identity match/mismatch/absence,
   and a broader no-I/O seam. Preserve the CLI's current warning-and-empty
   degradation integration tests.
4. Do not credit `W08.P25.S367` while the two high-severity findings remain
   open. No critical finding was identified.
5. Final remediation closes recommendations 1 through 4. S367 has no remaining
   review finding above low severity.

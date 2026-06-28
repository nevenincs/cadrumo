---
date: 2026-05-31
modified: '2026-05-31'
tags:
  - '#audit'
  - '#core-authority'
related:
  - "[[2026-05-31-core-authority-adr]]"
  - "[[2026-05-31-core-authority-plan]]"
  - "[[2026-05-31-core-authority-action-tracker-v2-reference]]"
---

# `core-authority` audit: honesty-review campaign-close structural-completion gate

## Scope

Fresh-context honesty review of the core-authority campaign (W01-W12, 102 Steps, L4 plan)
against the core-as-single-authority ADR. Covers: closed-but-not-fixed Steps, orphan follow-up
tasks, ADR-consequence coverage, enforcement-test surface, deferred-Step rationale soundness,
audit-pipeline reliability, cross-campaign contamination, and PROMOTE-001 / W11 / W12
honest-completion status.

## Honest Completion Percentage

Estimated honest ADR-intent delivery: ~72%.

- Rule 1 (placement): ~85% -- most cross-layer relocations landed; 87 STRICT_FROZEN sites remain.
- Rule 2 (directional): ~80% -- core outbound (W09) and adapter-to-application (W08) closed; CalendarCCAA cluster open.
- Rule 3 (error hierarchy): 100% -- FIX-001, MERGE-011, MERGE-012 fully closed with tests.
- Rule 4 (naming): ~90% -- RENAME actions closed; 87 _STRICT_FROZEN redeclarations violate Rule 10.
- Rule 5 (bare-str identity): ~4% -- 2 of 54 PROMOTE-001 sites enrolled; 52 blocked, no protect-list docs.
- Rule 7 (enum consolidation): ~60% -- CalendarCCAA (S31/S32), ProfileFactValue (S33/S34), IVA (S36) deferred.
- Rule 10 (STRICT_FROZEN): ~8% -- canonical in core/_models.py but zero production callers; 87 private copies remain.
- Rule 11 (enforcement test): ~70% -- 10-clause test exists; zero-violation gate BLOCKED at W11 close.

The 97/102 checkbox count hides that W12 S100/S101/S102 self-report COMPLETE while
documenting that the substantive action was blocked at all but 2 sites.
## Findings

### MERGE014-001 | CRIT | STRICT_FROZEN_CONFIG canonical declared but zero production callers

W04.P12.S37/S38/S39 are marked DONE in the plan. core/_models.py declares STRICT_FROZEN_CONFIG
correctly. Live tree inspection finds 87 production files still declaring _STRICT_FROZEN = ConfigDict(...)
locally and zero files importing STRICT_FROZEN_CONFIG from core. S38 and S39 step records contain
no commit hashes proving migration executed. MERGE-014 is a Rule 10 violation across 87 files.
Remediation: execute the 87-site import migration; link to follow-up task 585.

### PROMOTE001-002 | HIGH | PROMOTE-001 bare-str enrollment: 52 of 54 sites blocked, claimed closed

W12.P29 Steps S100/S101/S102 each carry status COMPLETE or DONE while their bodies document
that the substantive promotion was blocked at all but 2 sites. 52 sites remain bare-str
_id/_kind/_status/_state fields at persisted/wire boundaries -- a continuing Rule 5 violation.
Each blocked site requires either a typed alias shape correction or an explicit protect-list
entry with documented rationale. Neither has been done for any of the 52 sites.
Remediation: per-site adjudication in follow-up Wave W13.

### CTIMEX-003 | HIGH | core._time deleted by parallel campaign; live broken import in application/filing

Commit 309d5fc10 (chore/eliminate-shims campaign) deleted aeat.core._time while
application/filing/__init__.py:10 still imports from ...core._time. The module does not exist
on disk. W12 S102 acknowledges this but scopes it out-of-campaign. This is a broken import
causing collection failures across application/ and domain/ test suites. The W12 close gate
was declared passing on a narrowed scope (diagnostics + ledger + core/identity), masking the
regression from the full suite.
Remediation: immediate -- restore core._time or redirect the import to wherever utc_now lives.

### W11GATE-004 | HIGH | W11 close gate was never green when W11 was declared closed

W11.P28.S97 states explicitly: the W11 close gate cannot be declared green while clauses 5,
6, 7, 8, and 10 have unresolved violations. The plan marks W11 complete. The clause 5-8
violations were fixed in S92-S95 commits but S95 lands after S97 in plan order. The gate
assertion was written before the violations it gates on were fixed. Wave W11 was declared
closed before its own acceptance criterion was satisfied.

### CALENDARCCA-005 | MED | CalendarCCAA persists; ADR Rule 7 claim factually wrong; no amendment filed

domain/deadlines/_festivos.py still declares CalendarCCAA (24 live occurrences). S31/S32 are
correctly blocked: incompatible value formats (ISO codes vs lowercase names), different member
sets. The ADR Rule 7 Rationale asserts CalendarCCAA is a 100% geographic duplicate and orders
elimination -- factually wrong per execution evidence. The ADR has not been amended. MERGE-002
remains open with no authoritative wontfix record.
Remediation: ADR amendment closing MERGE-002 as wontfix with documented divergence (task 584).

### PROFILEFACTVALUE-006 | MED | ProfileFactValue name collision persists; rename not executed; ADR not amended

domain/user_profile/_values.py:48 declares ProfileFactValue as a 6-member union
(str, bool, int, Decimal, date, None). domain/calculations/registry/_schema.py:944 declares
it as a 3-member union (bool, int, str). Same name, different shapes, different boundaries.
The correct resolution (rename user_profile copy to UserProfileFactValue) was identified in S33
but neither executed nor captured in the ADR.
Remediation: rename plus ADR amendment closing MERGE-003 as RENAME not MERGE.

### FOLLOWUP-007 | MED | Follow-up tasks 583-587 have no vault document cross-references

The campaign close-report references five follow-up tasks (583-587). No vault documents link
to these identifiers. The honesty-review mandate requires deferred items to be formally tracked
with a follow-up campaign reference. Without vault documents a future agent has no canonical
path to the deferred work.
Remediation: create vault plan or exec stubs cross-referencing each task.

### AUDITPIPE-008 | MED | Audit pipeline produced ~60 false-positives; brief lacked constraint-shape pre-filter

The v2 audits produced ~60 false-positives: W04 3 wrong (domain-divergent enums/types),
W05 1 wrong, W10 3 wrong, W12 52 wrong (96% false-positive rate on PROMOTE-001). The brief
identified bare str where alias exists but did not verify alias constraint-shape compatibility.
Remediation: amend all audit dispatch briefs to include a substitutability pre-filter.

## Recommended Follow-up Wave (W13, ~10 Steps)

- S1: Execute STRICT_FROZEN_CONFIG 87-site migration (MERGE-014, task 585)
- S2: Rename domain/user_profile ProfileFactValue to UserProfileFactValue and update callers
- S3: ADR amendment closing MERGE-003 as RENAME
- S4: ADR Rule 7 amendment for CalendarCCAA wontfix; close MERGE-002 (task 584)
- S5: Restore or redirect core._time import in application/filing/__init__.py
- S6-S8: PROMOTE-001 blocked sites: protect-list entries or alias shape corrections
- S9: Vault stubs for follow-up tasks 583-587
- S10: Amend audit dispatch brief template with constraint-shape pre-filter

## Audit Pipeline Reliability Assessment

Two structural failure modes account for all ~60 false-positives:

1. Semantic-equivalence false-positives (CalendarCCAA, ProfileFactValue, IVA): GPU semantic
   search found structurally similar names but did not check runtime value compatibility.
   Amendment: add value-format and member-set comparison before classifying enums as MERGE candidates.

2. Constraint-shape false-positives (PROMOTE-001, 52 sites): bare-str detector found matching
   suffix fields where an alias exists but did not compare constraint shapes. 96% false-positive rate.
   Amendment: pre-filter must verify alias constraints are a subset of field constraints.

Process change: every audit brief targeting X where Y also exists must include a substitutability
pre-filter as a mandatory step before violation reporting.

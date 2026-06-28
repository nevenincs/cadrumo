---
tags:
  - '#research'
  - '#core-authority'
date: '2026-05-31'
modified: '2026-05-31'
related:
  - "[[2026-05-31-core-authority-audit]]"
  - "[[2026-05-31-core-authority-plan]]"
  - "[[2026-05-31-core-authority-adr]]"
---

# `core-authority` research: deferred-tasks 583-587 resolution tracker

The honesty-review audit (FOLLOWUP-007) identified five follow-up tasks (583-587) that
had no vault document cross-references at campaign close. This document provides the
formal vault cross-reference and records the resolution status of each task.

## Task 583 — PROMOTE-001 protect-list (52 blocked sites)

Subject: 52 PROMOTE-001 candidate sites blocked by constraint-shape incompatibility.

Status: RESOLVED in W13.P31.S105. `PROMOTE001_PROTECT_LIST` frozenset constant added to
`src/aeat/diagnostics/_identity_placement.py`. The `find_bare_str_typed_id_fields` function
now accepts a `protect_list` parameter and skips entries whose constraint shape is
incompatible with `TypedId`. Rationale codes: HEX64, MINLEN, PATTERN, NODOC, TRANSIT.

Honesty-audit reference: AUDITPIPE-008, FOLLOWUP-007.

## Task 584 — CalendarCCAA wontfix (MERGE-002)

Subject: `CalendarCCAA` and `CCAA` were flagged as duplicates. ADR Rule 7 required
adjudication.

Status: RESOLVED in W13.P32.S107. ADR Rule 7 Rationale amended to document MERGE-002 as
WONTFIX. Divergence rationale: incompatible value formats (ISO codes vs lowercase names),
different member sets, different domain roles (calendar vs fiscal classification).
CalendarCCAA is not a geographic duplicate of CCAA.

Honesty-audit reference: PROMOTE-001 audit, FOLLOWUP-007.

## Task 585 — STRICT_FROZEN_CONFIG 87-site import migration (MERGE-014)

Subject: 87 production files declared local `ConfigDict(strict=True, frozen=True,
extra="forbid")` copies instead of importing `STRICT_FROZEN_CONFIG` from `core._models`.

Status: RESOLVED in W13.P30.S104. 84 files migrated (3 bespoke exclusions with
`arbitrary_types_allowed=True` or non-standard extra settings documented inline).
`STRICT_FROZEN_CONFIG` is now the single authoritative declaration.

Honesty-audit reference: FOLLOWUP-003, FOLLOWUP-007.

## Task 586 — ProfileFactValue rename to UserProfileFactValue (MERGE-003)

Subject: Name collision between `domain/user_profile/_values.ProfileFactValue` (6-member
union) and `domain/calculations/registry/_schema.ProfileFactValue` (3-member union).

Status: RESOLVED in W13.P32.S108. `domain/user_profile/_values.ProfileFactValue` renamed
to `UserProfileFactValue`. All callers in `domain/user_profile/`, `application/user_profile/`,
and `application/modelo/_profile_binding.py` migrated. Registry `ProfileFactValue` retains
its name as the domain-canonical calculation concept.

Honesty-audit reference: MERGE-003, FOLLOWUP-007.

## Task 587 — Audit-pipeline substitutability pre-filter (AUDITPIPE-008)

Subject: Audit briefs using the "X where Y exists" pattern had a 96% false-positive rate
because the alias-existence check did not verify constraint-shape compatibility.

Status: RESOLVED in W13.P32.S110. `aeat-swarm-audit-cadence` rule amended to mandate
the substitutability pre-filter. Any audit brief flagging site X where canonical Y exists
must verify Y's constraint shape is a superset of X's before classifying X as actionable.

Honesty-audit reference: AUDITPIPE-008, FOLLOWUP-007.

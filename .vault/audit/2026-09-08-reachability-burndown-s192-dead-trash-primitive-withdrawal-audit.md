---
tags:
  - '#audit'
  - '#reachability-burndown'
date: '2026-09-08'
modified: '2026-09-08'
body_schema: 'body-v2'
body_hash: 'sha256:cfc92ea91bd392b47d249e03a025644eadc63f633149b3fcc1d1144ab2af51a5'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
  - "[[2026-09-04-reachability-burndown-W05-P12-S192]]"
  - "[[2026-08-13-profile-bucket-lifecycle-successor-adr]]"
---

# `reachability-burndown` audit: `S192 dead trash primitive withdrawal implementation review`

## Scope

Independent review of `W05.P12.S192` against the four-file implementation diff, accepted profile-bucket-lifecycle ADR, Step Record, surviving custody deletion transaction, focused bucket tests, production-metastate gate, residue scan, qualified-doc aggregate, and exact reachability signal.

The removed `trash_rename_and_remove` function was test-only. Its private `TreeRemovalErrorPolicy`, literal policy type, logger, recursive-removal helper, and dedicated self-tests had no production consumer. The qualified-doc test contained the only additional assertion naming it. The bucket package and directory-layout docs now correctly describe that module as a path resolver which performs no lifecycle IO.

Deletion authority remains intact and singular. The accepted profile-bucket-lifecycle decision delegates physical local deletion exclusively to custody. The surviving path is `application.user_profile.custody_service`, whose ordered transaction inventories the capsule, revokes session and key material, binds and renames the capsule for deletion, removes the transaction-owned tombstone, and records completion. Its custody helpers and deletion-protocol tests remain present. Removing an unreachable generic `shutil.rmtree` wrapper therefore does not remove or weaken the product deletion path.

Independent verification confirms Ruff passes, `production_metastate` passes, and all 132 retained bucket tests pass. Exact residue search finds no `trash_rename_and_remove`, `TreeRemovalErrorPolicy`, or private removal-helper reference. The exact detector reports 336 unused symbols and 18 orphan tests, confirming the 337-to-336 reduction without a baseline, threshold, or disposition change. The qualified-doc aggregate’s four failures concern unrelated dangling references, its pre-existing population threshold, Pydantic field resolution, and a lazy user-profile export; none names the removed primitive.

## Findings

### final-disposition | low | Approved with no open S192 findings

No deletion-safety, ownership, compatibility, metastate, test-quality, documentation, or Step Record defect was found. The four-file diff matches the authorised scope, custody remains the sole physical profile-deletion owner, and the recorded peer failures are correctly separated from S192.

## Recommendations

Approve `W05.P12.S192` for closure. No S192 remediation remains.

Continue the reachability campaign from the live signal of 336 unused symbols and 18 orphan tests; do not absorb the four peer-owned qualified-doc failures into this step.

---
tags:
  - '#audit'
  - '#arch-remediation-engine-lifecycle'
date: '2026-07-04'
modified: '2026-07-04'
related:
  - "[[2026-07-02-arch-remediation-engine-lifecycle-plan]]"
  - "[[2026-07-02-arch-remediation-engine-lifecycle-adr]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #audit) and one feature tag.
     Replace arch-remediation-engine-lifecycle with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar]]'.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

# `arch-remediation-engine-lifecycle` audit: `campaign close honesty review`

## Scope

Fresh-context campaign-close honesty review for the engine lifecycle campaign
after `vaultspec-core vault plan status
2026-07-02-arch-remediation-engine-lifecycle-plan` reported 11 of 11 steps
complete. The review treated the plan as newly inherited: re-read the plan and
ADR, checked the exec record set, inspected live storage/session lifecycle code,
confirmed the narrow CLI disposal-sweep promise, and ran focused real gates.

Evidence used:

- `vaultspec-core vault plan status
  2026-07-02-arch-remediation-engine-lifecycle-plan`: 11 of 11 complete.
- `vaultspec-core vault check features --feature
  arch-remediation-engine-lifecycle`: clean before this close audit.
- `uv run --no-sync pytest -q
  src/aeat/adapters/persistence/storage/tests/test_engine_session_lifecycle.py
  src/aeat/tests/test_secure_sql.py`: 8 passed.
- Direct source inspection confirmed lazy session-owned engine acquisition in
  `src/aeat/adapters/persistence/storage/runtime.py`, session-owned disposal in
  `src/aeat/adapters/persistence/storage/master_key/_bucket_session.py`, and
  bucket-keyed engine cache ownership in
  `src/aeat/adapters/persistence/storage/sql/engine.py`.

## Findings

### campaign-close-honesty-review | low | Structural closure is supported

No missing implementation item was found. The plan is fully checked, all 11 step
exec records are present, and the focused lifecycle gates pass against the live
tree. The source shape matches the ADR intent: storage runtime acquires the
engine through the active bucket session on first repository access; bucket
session close invalidates and disposes the associated engine handle; the SQL
engine cache is keyed through the bucket identity path while the explicit
database-URL route remains a direct settings path.

### disposal-sweep-boundary | low | Remaining test fixture disposals are outside the promised sweep

The fresh review deliberately searched for remaining `dispose_engine()` calls.
Many tests still use it as fixture cleanup, but the completed step promised the
profile lifecycle, rename, and navigation choreography sweep recorded in
`P03.S10`. The exact promised files, `test_profile_lifecycle_navigation.py` and
`test_profile_rename_maintenance_events.py`, no longer contain
`dispose_engine()` calls. This does not surface a new engine-lifecycle step.

## Recommendations

- Treat `arch-remediation-engine-lifecycle` as closed for Wave 2.
- Add no new engine-lifecycle steps from this honesty review.
- Keep any future broad test-fixture cleanup separate from this campaign; it is
  not required to satisfy the ADR or plan closure.

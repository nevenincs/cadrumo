---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-18'
modified: '2026-08-18'
body_schema: 'body-v1'
body_hash: 'sha256:08b6afd30e6cb9abc8a22ba7fc76f61e0d008cf8b6b8390a81543ef9a87b6109'
step_id: 'S76'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace profile-password-custody with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S76 and 2026-08-13-profile-password-custody-plan placeholders are machine-filled by
     `vaultspec-core vault add exec`; do not fill them by hand.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar-plan]]' and link the
     parent plan.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

<!-- STEP RECORD:
     This file represents one Step from the originating plan. Identified
     by its canonical leaf identifier (S##) and ancestor display path.
     The Have Terra XHigh unblock capsule-backed coverage in the outbound authority adapter's test package, whose autouse fixture writes the retired bucket manifest so capsule discovery refuses that root outright, leaving no test in the package able to seed a current capsule and the degradation path of the identity-provider session reader with no coverage at all, and sequence it behind the manifest ownership ruling since whoever rules that will be holding this fixture and ## Scope

- `src/cadrumo/adapters/outbound/aeat/auth/tests/` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Have Terra XHigh unblock capsule-backed coverage in the outbound authority adapter's test package, whose autouse fixture writes the retired bucket manifest so capsule discovery refuses that root outright, leaving no test in the package able to seed a current capsule and the degradation path of the identity-provider session reader with no coverage at all, and sequence it behind the manifest ownership ruling since whoever rules that will be holding this fixture

## Scope

- `src/cadrumo/adapters/outbound/aeat/auth/tests/`

## Description

<!-- Succinct line-by-line list of steps executed. Use imperative language, mirroring git commit summary lines. -->

## Outcome

The row's cause clause was stale and is corrected: the outbound auth test package's autouse fixture writes NO retired manifest at HEAD — the chain is the canonical capsule door (`isolated_runtime_profile` → `publish_test_profile_capsule`). The real blocker was the UUID harness: every module-level `_BUCKET_ID` in the package was a readable string, which `UUID(str(profile_id))` refused once the harness went UUID-constrained (commit `58cd742301`). Swept to canonical UUIDv4 ids (commit `dadca09566`): `_authenticator_support.py`, the two lifecycle f-string ids, the diagnostics/contract/persistence/roundtrip modules and the per-case resume id. Collection is clean and 49 tests that previously errored at setup now run.

## Notes

Routed finding: the newly-runnable tests expose the next pre-existing layer — `ProfileCustodyTransactionConflictError: profile label is already bound to a committed capsule` across the parametrised shared-contract module (the function-scoped runtime fixture with a fixed bucket id collides across cases in one process). That layer belongs to the runtime-fixture owners (`adapters/persistence/tests/runtime_profile_fixture.py`), not this row. Also repaired: this session's earlier fixture UUIDs carried malformed 10-hex tails; corrected to canonical 12-hex length in the same sweep.

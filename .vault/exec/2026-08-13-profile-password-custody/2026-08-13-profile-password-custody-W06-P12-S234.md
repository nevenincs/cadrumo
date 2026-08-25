---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:6fe84ae72283badc9de1639a514f90a0d9949fbb4f3585afd26cd8bd143f0694'
step_id: 'S234'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

# Use Vaultspec RAG semantic discovery plus targeted symbol and caller confirmation to audit recovery creation, handoff, export, restore, and refusal-witness responsibilities for redeclaration, consolidate substitutable implementations, and correct stale optional-recovery production prose

## Scope

- `src/cadrumo/application/user_profile/ and src/cadrumo/adapters/persistence/storage/custody/ and src/cadrumo/entrypoints/cli/`

## Description

- Locate recovery creation, handoff, export, restore, and governing decisions by meaning with Vaultspec RAG.
- Read the recovery application owner and custody substrate epicentres, then confirm every exact definition and production caller with targeted symbol searches.
- Classify similarly named functions by responsibility and consolidate only substitutable implementations.
- Replace production prose that still described creation recovery as optional.
- Run the focused recovery/capsule contracts and scoped lint.

## Outcome

No code redeclaration remains. Creation is one vertical call chain rather than three competing implementations: `mint_profile_creation_recovery` owns creation-only application policy and secret lifetime, `create_profile_recovery_enrollment_material` is the application port boundary, and `create_profile_custody_recovery_envelope` owns cryptographic substrate construction. The sole production registration caller mints before publication and requires an exact possession proof. The CLI handover has exactly two delivery modes: verified controlling-terminal input or the bounded handoff/verification descriptor pair; absence of either channel refuses creation, so no password-only profile can be published.

Export and restore follow the same boundary split. Application functions own workflow and publication policy, the custody port narrows abstractions, and substrate functions own artifact parsing, destination refusal, password/recovery proof, and unwrap. Each layer has one production caller in the next layer; none is a substitutable copy. Vaultspec RAG also recovered the accepted password-custody, mnemonic-presentation, and profile-state decisions that require this separation.

Stale optional-recovery prose in the application and custody modules was corrected in `d54b753b9b`. A fresh exact wording scan finds no production claim that enrollment is optional. The focused recovery enrollment, recovery custody, and capsule contract selection passes 47 tests; scoped Ruff passes.

## Notes

Semantic discovery was used first and exact search only as the confirmer, per the Vaultspec RAG discipline. Test and developer-fixture helpers were not counted as production declarations. No implementation consolidation was warranted because removing any member of the three-layer chains would collapse an application/port/substrate boundary rather than remove duplicate behavior.

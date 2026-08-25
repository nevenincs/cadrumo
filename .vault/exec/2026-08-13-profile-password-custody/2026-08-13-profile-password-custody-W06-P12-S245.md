---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:9b39d739dd89913a16a551362d100e0ebfc7914b80d4ff3d0367bebd7944a030'
step_id: 'S245'
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
     The S245 and 2026-08-13-profile-password-custody-plan placeholders are machine-filled by
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
     The Migrate harness warm-runtime profile provisioning to the mandatory verified recovery handoff and prove real runtime startup succeeds and ## Scope

- `src/cadrumo-harness/` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Migrate harness warm-runtime profile provisioning to the mandatory verified recovery handoff and prove real runtime startup succeeds

## Scope

- `src/cadrumo-harness/`

## Description

- Discover warm-runtime provisioning and recovery responsibilities with Vaultspec RAG, then confirm every harness registration caller by exact-symbol search.
- Consolidate harness profile facts, passphrase, and exact recovery-possession proof into one shared integration fixture module.
- Provision the warm fixture through canonical application registration with mandatory recovery, consume the real one-shot profile-secret file, and revoke process and durable session acceleration before every warm proof.
- Feed the existing root `--profile-secrets-stdin` contract through the captured warm CLI runtime instead of degrading authenticated local calls to subprocess execution.
- Add cleared-channel anti-tautology and direct global-stdin restoration witnesses without mocks, skips, or replacement authentication logic.
- Preserve unconditional worker relock and explicit fixture cleanup.

## Outcome

All harness profile-registration callers now use one exact recovery-handover helper and one constraint-complete fact fixture. The warm runtime authenticates through the canonical CLI root secret reader on keychain-free state, serves repeated real encrypted reads, relocks after every worker, and starts cleanly again under a rebuilt server. Clearing the retained channel returns `AUTH_STORAGE_KEYRING_UNAVAILABLE`, proving the success path requires the real stdin handoff.

Focused verification passed: the complete responsiveness module passed 6 tests; the harness-delivery and in-process-runtime modules passed 34 tests; the direct stdin-restoration slice passed 2 tests; and scoped Ruff and ty checks passed. The broader xdist integration checkpoint passed 321 tests and reported two independently owned failures: the existing `overview.calendar` schema-size budget and a contention-sensitive unauthenticated registry warm probe. That checkpoint also held 17 serial watchdog tests owned by S246.

Formal review closed with no unresolved CRITICAL, HIGH, or MEDIUM findings. A final Vaultspec RAG search plus targeted caller scan found the one shared `verify_recovery_handover` implementation and no remaining harness recovery lambda or second mnemonic-proof implementation.

## Notes

Shared-worktree writers captured intermediate S245 changes in unrelated commits `2be1f36529` and `6e9b859b3f` while this Step was running. The closing commit therefore contains the remaining fixture consolidation, anti-tautology, evidence, review, and lifecycle closure; these two hashes are recorded as split provenance rather than rewritten or reverted. Active registry and S259 work was not modified.

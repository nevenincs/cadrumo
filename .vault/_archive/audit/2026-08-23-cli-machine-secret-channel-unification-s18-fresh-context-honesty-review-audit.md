---
tags:
  - '#audit'
  - '#cli-machine-secret-channel-unification'
date: '2026-08-23'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:a517fa9f8ac1a71eca2c7ca111c738eefcd1d9d6f3d3ddda1ffd2cc356c910aa'
related:
  - '[[2026-08-23-cli-machine-secret-channel-unification-plan]]'
  - '[[2026-08-23-cli-machine-secret-channel-unification-adr]]'
  - '[[2026-08-23-cli-machine-secret-channel-unification-global-machine-secret-contract-research]]'
  - '[[2026-08-23-cli-machine-secret-channel-unification-keychain-free-cross-process-machine-operation-research]]'
  - '[[2026-08-13-profile-password-custody-rollup-adr]]'
  - '[[2026-08-13-cli-action-envelope-successor-adr]]'
  - '[[2026-08-13-profile-session-lifecycle-successor-adr]]'
  - '[[2026-08-09-cli-action-envelope-hardening-adr]]'
  - '[[2026-08-22-profile-registration-password-policy-canonical-credential-capability-adr]]'
  - '[[2026-08-23-cli-machine-secret-channel-unification-W04-P08-S17]]'
  - '[[2026-08-23-cli-machine-secret-channel-unification-s19-passphrase-rotation-review-audit]]'
  - '[[2026-08-13-profile-password-custody-W03-P06-S209]]'
  - '[[2026-07-01-import-centralization-W06-P90-S403]]'
  - '[[2026-07-18-user-docs-localization-W03-P06-S23]]'
  - '[[2026-06-04-docs-sphinx-ux-W03-P05-S27]]'
---
# `cli-machine-secret-channel-unification` S18 fresh-context honesty review

## Scope

This independent SOL review re-read the current branch history, HEAD, status, feature-scoped diff, all feature research, ADR, plan, execution, audit, index, and phase-summary artifacts, and the governing custody, session, action-envelope, and canonical-credential decisions. It reviewed the live command graph, strict payload models, root authentication gate, descriptor bootstrap and readers, five leaf handlers, metadata generators, four locale catalogues, user documentation, sequence goldens, removal censuses, and their tests.

Discovery used semantic code and ADR search first and exact `rg` confirmation second. The feature-scoped Vault check was repaired before review and returned clean. The broad Vault, import, documentation-localization, sequence, Sphinx, and WSL criteria were then treated as standing close conditions: a red result is preserved below with an exact owner and verification gate, never narrowed to a feature-only substitute.

Fresh focused evidence included 98 unit and conformance cases passing; seven representative S13/S14 real-process cases passing; the S19 keychain-failure rotation case passing in 53.28 seconds; all four live localized `config --help` projections omitting the retired secret environment name while publishing both root and both leaf channel flags; and three target documentation catalogues parsing with zero untranslated, fuzzy, or obsolete entries while preserving all seven machine-secret field and flag literals.

## Findings

### S18-001 | HIGH | RESOLVED | Live help advertised a retired secret environment route

The initial review found live configuration help and fallback prose that still instructed operators to use `CADRUMO_SECRET_PASSPHRASE`, contradicting the hard-cut decision and allowing a machine caller to infer an unsupported channel. Commit `37f45a298ff` removed that route and added a four-locale real-process help gate. Current guidance at `src/cadrumo/locales/en/cli.yml:3143`, `src/cadrumo/locales/es/cli.yml:3386`, `src/cadrumo/locales/ca/cli.yml:3354`, and `src/cadrumo/locales/hu/cli.yml:3353` names `--profile-secrets-stdin`, `--profile-secrets-fd`, `--secrets-stdin`, and `--secrets-fd`; `src/cadrumo/entrypoints/cli/tests/test_help_without_secrets.py:230` refuses the retired name. Direct subprocess help in en, es, ca, and hu passed with all four flags present and the retired name absent. Required remediation is complete.

### S18-002 | HIGH | RESOLVED | The target page sequence golden trailed the remediated root help

Commit `e347f62d4bbadf66a978cc503a116d5104bb7820` refreshed exactly `docs/_sequences/how-to/protect-data-access/protect-data-access-machine-secret-help.json:14`, replacing the obsolete isolated-state sentence with the four explicit root and leaf channels and no retired environment route. Independent current-HEAD verification passed both the specific sequence and the complete `how-to/protect-data-access` page sequence gate. The earlier logout exit-6 report did not reproduce on the committed head; the page-wide gate passed, so it is transient concurrent-tree evidence rather than an open defect. Canonical es, ca, and hu single-page builds with sequence checking enabled each exited zero. The builds still printed the unrelated generated Modelo and six other-page sequence diagnostics formally owned by `docs-sphinx-ux` W03.P05.S27, but the requested target page built successfully in every language. Required remediation is complete.

### S18-003 | MEDIUM | RESOLVED | Localized machine-secret documentation was incomplete after catalogue sync

The synced Spanish, Catalan, and Hungarian `protect-data-access` catalogues initially carried the new machine-secret passages as untranslated. Commit `3ccfb91fa798` translated the complete target catalogues. Current root-channel entries begin at `docs/locales/es/LC_MESSAGES/how-to/protect-data-access.po:293`, `docs/locales/ca/LC_MESSAGES/how-to/protect-data-access.po:287`, and `docs/locales/hu/LC_MESSAGES/how-to/protect-data-access.po:285`. Independent Babel parsing reports zero untranslated, fuzzy, or obsolete entries in each target file and confirms all seven command and payload literals are present in source and translation. Required target remediation is complete; the unrelated thirty-page localization backlog is owned by the formal S23 carry-forward below.

### S18-004 | HIGH | RESOLVED | S19 historical record did not prove keychain-free destructive rotation

The S19 audit previously stopped on the root keychain refusal. Current production consumes the typed self-authenticating posture after target and write-route validation, and `test_config_passphrase_change_self_authenticates_without_a_keychain` now passes against the real entrypoint under `keyring.backends.fail.Keyring`: first rotation succeeds, the old proof refuses, and the new proof completes a second rotation. The durable resolution is recorded at `.vault/audit/2026-08-23-cli-machine-secret-channel-unification-s19-passphrase-rotation-review-audit.md:56` and its Step Record at `.vault/exec/2026-08-23-cli-machine-secret-channel-unification/2026-08-23-cli-machine-secret-channel-unification-W02-P11-S19.md:46`. Required remediation is complete without deleting the historical failure.

### S18-005 | HIGH | RESOLVED | Custody recovery wording forked data restore from credential reset

The accepted custody decision once described recovery restore as generating a new password envelope, while current code and the later canonical-credential decision deliberately restore the original capsule under its existing password envelope and defer lost-password reset. The governing corpus now agrees: `.vault/adr/2026-08-13-profile-password-custody-rollup-adr.md:96` defines one `restore --artifact` recovery-proof variant and unchanged envelope; `.vault/adr/2026-08-22-profile-registration-password-policy-canonical-credential-capability-adr.md:138` keeps lost-password reset deferred; and `.vault/plan/2026-08-13-profile-password-custody-plan.md:100` plus line 108 serialize the same behavior. The action-envelope and sealed-archive successors carry the same grammar. Required remediation is complete; data recovery is not represented as credential reset.

### S18-006 | MEDIUM | RESOLVED | S06 and S10 cited retired patched near-handler tests

The historical S06 and S10 records now state that their patched tests were removed by S17 and that current behavioral authority lives in the S13/S14 fresh-process matrix. The reconciliation is explicit at `.vault/exec/2026-08-23-cli-machine-secret-channel-unification/2026-08-23-cli-machine-secret-channel-unification-W02-P03-S06.md:49`, `.vault/audit/2026-08-23-cli-machine-secret-channel-unification-s10-certificate-machine-secret-audit.md:91`, and `.vault/exec/2026-08-23-cli-machine-secret-channel-unification/2026-08-23-cli-machine-secret-channel-unification-W02-P04-S10.md:45`. No completion claim depends on monkeypatching a handler or transport boundary.

### S18-007 | HIGH | RESOLVED BY FORMAL DEFERRALS | Standing broad gates remain red outside the reviewed implementation

The S17 summary's phrase "feature-owned surface" was insufficient because the ADR and plan require broader gates. S18 preserves each standing criterion through a current run and a concrete open owner:

- Import integrity: the current lane completed with 51 passed and seven failed. Three exact-debt assertions report 115 reaches versus 69 named, including 45 unnamed and one stale entry; eleven forwarding wrappers, three excluded-test false positives, one TUI manifest identity, and 23 dangling targets remain. `.vault/plan/2026-07-01-import-centralization-plan.md:907` reopens the authority as W06.P90.S403, and its Step Record carries the exact zero-failure command and no-baseline-expansion rule. TUI deletion proof remains separately owned by `tui-architecture` W06.P15.S88-S91.
- WSL supervised KDF: the full feature subprocess matrix stops at inherited-PTY worker attestation before CLI dispatch. `.vault/plan/2026-08-13-profile-password-custody-plan.md:143` owns the defect as W03.P06.S209; its record requires the entire machine-secret subprocess module to pass inside WSL with all five leaves, both restore variants, root authentication, collision semantics, no skips, and no weakened supervision. The current 23 POSIX reader cases and two descriptor-zero CLI probes are preserved as partial evidence, not substituted for this gate.
- Documentation localization: the complete gate currently fails for the same thirty of 57 unrelated pages in es, ca, and hu, while fresh-POT equality fails for the same seven unrelated pages and excludes `protect-data-access` from both inventories. `user-docs-localization` W03.P06.S23 owns the finite backlog and requires both complete three-language gates to return zero.
- Full sequence and Sphinx: the broad build still reports six non-machine-secret source-to-golden frame mismatches, missing authored or generated targets, and the previously recorded generated Modelo markup failure. `docs-sphinx-ux` W03.P05.S27 owns those exact items and the full local zero-warning gates; `ci-lane-deconflation` P01.S01 retains the subsequent push-triggered runner observation.

These deferrals do not claim any broad lane green. They preserve the standing acceptance criteria under their correct architectural owners while allowing this feature review to remain bounded to evidence it can honestly close.

### S18-008 | MEDIUM | RESOLVED | Lifecycle counts, links, and single-home boundaries drifted

The S18 plan row now says all twenty-two Steps rather than the obsolete eighteen. The plan and ADR link directly to the custody roll-up, action-envelope successor and hardening decision, profile-session successor, canonical-credential decision, and both feature research records. Decision prose remains in ADRs; execution facts remain in Step Records and audits; the plan maps work without restating its evidence; summaries do not supersede red gate history. The feature index was regenerated after the final S18 artifact update and now includes this audit and its linked carry-forwards.

### S18-009 | INFO | No remaining implementation defect found in the machine-secret contract

The fresh-context review confirmed exactly five leaf paired-channel adopters, one distinct root pair, strict per-leaf fields, unknown and legacy-field refusal, hostile-environment non-interference, exact-target and self-authenticating postures, same-scope and cross-scope collision-before-read semantics, keychain-free root authentication, POSIX descriptor closure, Windows HANDLE bootstrap and closure, locale and metadata parity, and the obsolete importer and route censuses. S13/S14 runtime claims match their real subprocess authorities. No CRITICAL finding was found.

## Recommendations

All feature-owned HIGH findings are resolved and no CRITICAL finding exists. The feature index was regenerated, the feature-scoped Vault fix and read-only checks remained clean, and S18 was closed through the plan CLI. The four broad carry-forward Steps remain intentionally open under their own plans after feature closure; their exact red criteria and verification gates must not be weakened.

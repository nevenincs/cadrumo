---
tags:
  - '#audit'
  - '#secure-object-integrity'
date: '2026-05-22'
modified: '2026-05-22'
related:
  - '[[2026-05-22-secure-object-integrity-attribution-plan]]'
  - '[[2026-05-22-secure-object-integrity-p05-s14-review-audit]]'
  - '[[2026-05-21-secure-object-database-drift-research]]'
---



# `secure-object-integrity-P05-S15` Code Review

P05S15-001 | LOW | S15 verification evidence is sufficient for the secure-object integrity scope
No CRITICAL or HIGH blocker found. The reported S15 gate matrix covers the plan's closeout surface: ruff over touched verification files, locale audit and scaffold check, repair-integrity tests, diagnostics tests, locale parity and honesty tests, storage/config/root-fallback/privacy tests, registry referential-integrity tests, and the JSON registry verification command returning `verified: true`. This is enough evidence for P05.S15 because it exercises the new public privacy contract in `src/aeat/entrypoints/cli/test_repair_privacy_contract.py`, the repair and diagnostics application layers, the root-fallback/config storage protections, locale catalogue consistency, and registry integrity. I did not find a missing S15-specific test family in the supplied evidence.

P05S15-002 | LOW | Public repair privacy contract uses real CLI behavior and isolated encrypted storage
Reviewed `src/aeat/entrypoints/cli/test_repair_privacy_contract.py`. The test creates a real operator profile through the CLI, writes secure-object rows through the real SQL-backed repository, creates an undecryptable row with a different real ephemeral key, and exercises text and JSON CLI output for `config repair`, `config repair list`, and `config repair integrity attribution`. The autouse `AEAT_DATABASE_URL` isolation plus engine disposal matches the P02 hygiene guard's accepted isolation pattern, so the use of `EphemeralMasterKeyProvider` does not recreate the active-profile contamination class. The assertions verify that payload text, taxpayer id, period token, and raw active bucket UUID are absent while safe metadata remains present.

P05S15-003 | LOW | Locale fixes cover the attribution command, but registry-source scaffold values remain catalogue debt
Reviewed `src/aeat/locales/ca.yml` and `src/aeat/locales/hu.yml`. The new `cli.config.repair.integrity_attribution_help` entries are translated and accurately describe metadata-only grouping of undecryptable secure-object rows. The S15 translation fixes also remove English placeholder text from the `wizard.test` section. Separate from the secure-object command, both locale files still carry scaffold self-reference values for `cli.registry.sources_app_help`, `cli.registry.sources.view_help`, and `cli.registry.sources.source_ref_help`. The current renderer prevents raw dotted keys from surfacing directly and the registry CLI has explicit defaults, so this is not a secure-object-integrity blocker. It does show that the locale parity and honesty gates can pass while scaffold self-reference values remain, so this should be tracked as catalogue cleanup rather than treated as S15 failure.

P05S15-004 | LOW | Plan bookkeeping remains unsynced after the reported verification run
The plan still shows `P05.S15` unchecked at review time, and I did not find a dedicated P05.S15 execution note under the secure-object-integrity exec directory. This does not invalidate the supplied gate evidence, but the closeout artifact trail is incomplete until the owner records the S15 verification result and marks the plan row complete.

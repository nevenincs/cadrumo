---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-05-26'
modified: '2026-05-26'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-05-26-secure-storage-production-hardening-w12-p23-s93-domain-repository-slice-exec]]'
---



# `secure-storage-production-hardening` Code Review

S93-DOMAIN-001 | INFO | No review findings in initial domain repository slice

The `vaultspec-code-reviewer` reviewed the transaction, attachment, and justificante domain test migrations for S93. The review found no defects in the modified domain files. The tests now use `isolated_runtime_profile` for runtime-backed persistence, preserve real repository and encrypted storage behavior, avoid mocks, monkeypatches, broad exception masking, `noqa`, and coverage pragmas, and keep the classification/refusal checks as real secure-object writes with concrete exception assertions.

S93-DOMAIN-002 | INFO | Traceability artifact added for this slice

The reviewer noted that the existing S93 execution artifact documented the earlier submission slice rather than these domain files. This audit is paired with the new domain repository slice execution record so the S93 rollout remains traceable while the broad plan row stays open.

S93-DOMAIN-003 | INFO | Submission repository migration reviewed with no findings

After the first reviewer completed, the same S93 migration pattern was applied to the submission domain repository tests. A second `vaultspec-code-reviewer` review found no issues. The file now uses `isolated_runtime_profile`, keeps the classification gate as a real secure-object write, and the combined focused gate covering submission, transactions, attachments, justificantes, and the shared secure SQL helper passes. No `AEAT_DATABASE_URL`, explicit database URL, injected engine, monkeypatch, broad exception, `noqa`, or coverage pragma remains in the combined migrated slice.

S93-DOMAIN-004 | MEDIUM | Modelo anti-tautology tests still used direct ORM mutation

Initial reviewer finding: the modelo anti-tautology tests created a runtime profile but still used direct `get_engine`, `session_scope`, and private ORM row mutation to alter persisted payloads. Resolution: calculation revision, filing record, work-unit, and verification-report tests now mutate encrypted payloads through the runtime-owned `profile.repository.load/save` surface.

S93-DOMAIN-005 | LOW | Usage-ratio corrupt payload test did not assert root cause

Initial reviewer finding: the malformed JSON test asserted only `UsageRatioPersistenceError`, which would not prove the validation cause surfaced. Resolution: the test now asserts the chained cause is `ValidationError` and that the surfaced message contains `Invalid JSON`.

S93-DOMAIN-006 | INFO | Modelo and usage-ratio review findings resolved

The corrected modelo/usage-ratio slice was re-reviewed by `vaultspec-code-reviewer` with no findings. The reviewer confirmed there are no direct engine/session/ORM mutations, mocks, monkeypatches, fakes, stubs, skips, xfails, `noqa`, broad exceptions, or obvious tautological calculation assertions in the reviewed files.

S93-DOMAIN-007 | INFO | Transaction anti-tautology mutation normalized to runtime repository

The combined hygiene scan found the earlier transaction anti-tautology proof still used direct engine/session/ORM access. The test now mutates the persisted encrypted payload through `profile.repository.load/save`, matching the corrected modelo pattern. The combined migrated slice hygiene scan now has no direct engine/session/ORM mutation, deprecated database-route setup, monkeypatching, broad exception swallowing, or masking pragmas.

S93-DOMAIN-008 | LOW | Stale execution wording corrected

Final review found no source-code defects, but noted the execution record still mentioned `get_engine(profile.settings)` for the transaction roundtrip migration. The execution record now states the current runtime-owned `profile.repository.load/save` mutation pattern.

S93-DOMAIN-009 | LOW | Work-unit frozen mutation test retained noqa

Initial review of the work-unit/finca increment found a legitimate but unnecessary `noqa` suppression in the work-unit frozen-model mutation proof. The test now uses direct assignment under `pytest.raises(ValidationError)`, preserving the real pydantic frozen-instance behavior without suppressing lint diagnostics.

S93-DOMAIN-010 | INFO | Work-unit and finca increment reviewed with no findings

The corrected work-unit/finca increment was re-reviewed by `vaultspec-code-reviewer` with no findings. Work-unit tests now use `isolated_runtime_profile` and real repositories without explicit database URLs, injected engines, direct default secure-object setup, monkeypatching, fakes, stubs, skips, xfails, pragmas, `noqa`, type suppressions, or broad exceptions. The finca anti-tautology test still uses the real SQL table repository and now asserts the concrete `ValidationError` boundary.

S93-DOMAIN-011 | INFO | Plan check blocked by unrelated duplicate identifiers

The focused source gates pass, but the plan checker currently reports duplicate W07/W08 canonical identifiers around `S56` through `S61`. That structural plan issue is outside this source slice and should be reconciled before closing S93 or later W12 rows.

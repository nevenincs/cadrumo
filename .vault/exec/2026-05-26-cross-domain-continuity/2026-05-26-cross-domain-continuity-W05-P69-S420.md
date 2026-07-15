---
tags:
  - '#exec'
  - '#cross-domain-continuity'
date: '2026-07-10'
modified: '2026-07-10'
step_id: 'S420'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
---

# Fail close Modelo 369 verification when OSS aggregation sources are unresolved and prove a disclosed zero or missing-source draft cannot gain verificado_completo

## Scope

- `src/aeat/application/modelo/ src/aeat/entrypoints/cli/ src/aeat/**/tests/`

## Description

- Ground the Modelo 369 calculate, verification, and export lifecycle with semantic search, source confirmation, and an independent reference audit.
- Add a Modelo 369 verification finding when registry-owned OSS aggregation bindings have no persisted resolver source provenance.
- Keep calculation advisories non-blocking while preventing the unresolved draft from transitioning to verified-complete.
- Extend the real encrypted-store M369 resolver journey with both unresolved-source and invoice-backed verification cases.
- Repair the review finding: project each positive `unrouted_observation` into a typed `CalculationSourceIssue` persisted beside, not inside, source provenance.
- Make verification consume that durable issue before it accepts resolved provenance, so a candidate that is visible to the resolver but absent from every registry binding cannot verify or export.
- Add real encrypted-store regressions for a positive unrouted OSS invoice, including export refusal with no target or temporary artefact, and a genuine zero-valued unrouted OSS invoice that remains verifiable.
- Repair the continuity review finding: include a verification-blocking source issue in the content-addressed revision identity, so recalculating an existing pre-repair draft creates a new current revision instead of returning the stale issue-free revision.
- Keep the durable issue inside the canonical `BindingSourceKind` taxonomy and assert every refused revision remains `BORRADOR` after verification.
- Repair the direct-legacy review finding: mark current mesh calculations as source-resolution assessed; for a legacy Modelo 369 draft, reconstruct OSS resolution from encrypted invoice evidence during verification and refuse only unresolved or unavailable legacy source state with a recalculate instruction.
- Prove direct legacy unresolved-draft verification and export refuse before any recalculation, while legacy routed and current zero-valued OSS evidence remain viable.
- Seal the assessment marker at persistence: derive it exclusively from the M369 source-mesh provenance/issue channels, remove caller and persistence overrides, and include its `true` state in both calculation identity and read-side integrity rehash while preserving the legacy false identity.
- Remove source provenance and issue channels from the public calculation façade; let only the in-module bucket source mesh invoke the trusted persistence bridge with resolver-derived evidence.
- Prove an attempted public provenance forgery against an encrypted legacy draft cannot change the persisted revision/current pointer, verify, or export; legacy routed and zero-valued current drafts still recalculate into new assessed current revisions.

## Outcome

An empty live OSS catalogue still produces the existing `oss_no_live_source` calculate advisory and saves a draft, but verification now records a blocking finding and leaves that revision in `BORRADOR`. The existing export state gate therefore refuses the draft before any artefact can be written.

A real invoice-backed Modelo 369 calculation persists resolver source provenance and still gains `verificado_completo`. A non-zero invoice observation that no declared registry binding consumes is now persisted as a typed unresolved source issue while its source provenance remains an honest positive candidate trace. Verification turns that issue into a blocking finding with the registry legal and source references, so export refuses before creating either the requested target or a temporary artefact. A genuine all-zero unmatched OSS invoice records no issue and remains verifiable.

Repair verification passed: `uv run --no-sync ruff check` over the eight changed source/test modules, `uv run --no-sync pytest src/aeat/application/modelo/tests/test_dormant_m369_oss_resolver_live.py -q` with `5 passed`, and scoped `git diff --check` (only benign CRLF conversion notices).

Continuity repair verification passed: `uv run --no-sync pytest src/aeat/application/modelo/tests/test_dormant_m369_oss_resolver_live.py src/aeat/application/modelo/tests/test_source_boundary_and_enrollment.py -q` with `16 passed`; the same scoped Ruff and diff checks passed (only benign CRLF conversion notices).

Legacy-assessment repair verification passed: the same adjacent suite reported `16 passed`; scoped Ruff and `git diff --check` passed (only benign CRLF conversion notices).

Sealed-marker repair verification passed: the same adjacent suite reported `16 passed`; scoped Ruff and `git diff --check` passed (only benign CRLF conversion notices).

Trust-boundary repair verification passed: `uv run --no-sync ruff check src/aeat/application/modelo/_calculation_actions.py src/aeat/application/modelo/tests/test_dormant_m369_oss_resolver_live.py` and `uv run --no-sync pytest src/aeat/application/modelo/tests/test_dormant_m369_oss_resolver_live.py src/aeat/application/modelo/tests/test_source_boundary_and_enrollment.py -q` reported `All checks passed!` and `16 passed in 23.44s`; scoped `git diff --check` has no whitespace errors (only benign CRLF conversion notices).

The feature-surface gate also passed the nine owned Python modules through Ruff. `uv run --no-sync vaultspec-core vault check all --feature cross-domain-continuity` exited `0`; its 203 warnings are the existing feature-wide markdown, index, annotation, and unrelated execution-record hygiene backlog, not S420 structural or link failures.

## Notes

- No rolling audit, unrelated source, registry, locale, or plan-row edits were made.
- Renewed review found and the sealed-marker repair resolved both the direct legacy-current-draft bypass and mutable-marker bypass. A subsequent review found caller-controlled provenance could still establish assessment; the public façade is now source-metadata-free. Renewed independent review approved this final trust-boundary correction.

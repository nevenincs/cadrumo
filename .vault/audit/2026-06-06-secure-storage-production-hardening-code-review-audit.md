---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-06-06'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
---

# `secure-storage-production-hardening` Code Review

## S460-001 | HIGH | Recovery verification errors suggested the wrong custody verb

`RecoveryVerificationError` defaulted to `aeat config verify-recovery --recovery-key <WORDS>` even when the failing path was `config recover`. S460 now routes the error registry suggestion to `aeat config recover --recovery-key <WORDS>` and pins the rendered envelope suggestion in recovery-facade coverage.

Status: resolved in S460.

## S455-001 | LOW | Declaration full-boundary corpus was not rerun as one module

S455 changes declaration provenance construction while preserving the existing extraction path for on-disk PDFs. A targeted real corpus declaration parse passed, and the broad declaration boundary module timed out when batched with other focused modules.

Status: accepted for S455. The changed declaration behavior is covered by `test_parser_extracts_legal_entity_nif_from_pdf`, while the full declaration corpus remains expensive and should be run in a longer gate when the inbound campaign batch closes.

## S455-002 | INFO | Inbound parser provenance path review passed

Review checked the S455 diff for local path leakage in successful parser records, the justificante successful dispatch cache, and borrador unrecognised artefact errors. The implementation keeps real file paths only at extraction time and persists digest-derived `.secure-source/<sha256>.pdf` references in parser records.

Status: no action required.

## S456-001 | LOW | Application wizard direct output remains an allow-listed Typer write

S456 intentionally keeps one direct `_typer.echo` call in `application.wizard._commands` because the wizard command factory lives outside the CLI entrypoint package. The risk is that the allow-list could become a paper exception if the helper stopped using central rendering.

Status: resolved in S456. The helper now renders text through `render_command_output(format_name="text", ...)` before the Typer write, and `test_wizard_success_text_uses_central_output_redaction` captures real output to prove UUID-like profile labels are redacted.

## S456-002 | INFO | Redaction inventory review passed

Review checked the corrected inventory root, `_typer.echo` alias detection, application wizard scan scope, and the existing CLI output redaction gates. The integration inventory now runs cleanly when selected with `-m 'unit or integration'`.

Status: no action required.

## S396-001 | INFO | Persona readiness reconciliation review passed

Review checked the S396 disposition matrix against the fresh persona findings inventory, the fresh persona repair plan, secure-storage repair-profile privacy audit, and W15 repair privacy execution records. The reconciliation does not over-assign capability findings to secure-storage and keeps S397/S398 as the owners for research/classification gaps.

Status: no action required.

## S397-001 | INFO | Persona research requirements review passed

Review checked the S397 research requirements against semantic vault search results, the fresh persona findings inventory, the capability-gap design note, the secure-storage architecture ADR, the secure-object integrity plan, and current CLI/application surface discovery. The note keeps FRESH-004 and FRESH-007 as classification questions, treats FRESH-011 as storage-owned but already architecturally backed, and requires S399 retest evidence before S400 can add any repair row.

Status: no action required.

## S398-001 | INFO | Persona classification register review passed

Review checked the S398 plan register against the S396 reconciliation and S397 research requirements. The classification keeps manual-route and profile-guidance findings in CLI workflow or capability ownership, limits W13.P28 secure-storage retesting to unreadable stored-draft readiness plus repair-profile privacy regression, and prevents S400 repair adoption without S399 evidence.

Status: no action required.

## S399-001 | INFO | Secure-storage persona retest review passed

Review checked the S399 retest scope against the S398 classification register and current focused gate results. The selected tests exercise clean Modelo 111 readiness, metadata-only unreadable-row repair diagnostics, repair-profile redaction, quarantine dry-run non-mutation, and sessionless fresh-root repair behavior through existing real fixtures. The sidecar persona agents did not run because the multi-agent runtime returned usage-limit errors, but the same scoped retests were completed locally.

Status: no action required for S399. S400 should not add repair rows unless a later retest contradicts these focused pass results.

## S400-001 | INFO | Testimonial repair-adoption register review passed

Review checked the S400 plan register against the S399 retest record. The register adopts no new repair rows because the secure-storage-owned testimonial findings passed current focused CLI and backend gates, and it preserves a reopen condition for any future degraded-storage consumption or repair-output leakage.

Status: no action required.

## S401-001 | INFO | Testimonial synthesis review passed

Review checked the S401 synthesis against the S396-S400 evidence chain. The final dispositions match the classification and retest results: FRESH-004 and FRESH-007 remain external CLI workflow or capability work, while FRESH-011 and REPAIR-PROFILE-PRIVACY-001 are secure-storage-owned but covered by current passing regression gates.

Status: no action required.

## S460-002 | MEDIUM | Operator-surface contract under-declared root custody verbs

The accepted operator-surface contract only declared `config unlock` while the CLI mounted first-class `config lock`, `config unlock`, `config rekey`, `config recover`, `config show-recovery`, and `config verify-recovery`. S460 now adds an explicit custody domain and mounted command-family rows for each root-level custody child.

Status: resolved in S460.

## S460-003 | LOW | Root-fallback recovery-path coverage still exercised profile switch

The root-fallback real-entrypoint regression continued to exercise `config profile switch` after the static policy table moved to `config unlock`. S460 updates the real-entrypoint regression to drive `config unlock` so the canonical recovery path remains guarded against root-fallback write-policy refusal.

Status: resolved in S460.

## S454-001 | INFO | Filing/modelo localization and error-hierarchy review passed

Review checked the S454 diff against the plan row, locale CLI mandate, central error registry, focused modelo tests, and static exception scans. The promoted modelo calculation-input and revision-pick failures now derive from AEAT error base classes, preserve `ValueError` compatibility where needed, use structured context, and carry locale keys populated through `aeat.locales`. The remaining raw exceptions are Pydantic validator or internal debug-logged parse sentinels, and the one broad export handler re-raises after cleanup.

Status: no action required for S454. The CLI casilla-normalisation integration test remains blocked by the current-tree wizard catalogue registration failure before it reaches the S454 code path.

## S462-001 | INFO | CLI startup wizard-registration review passed

Review checked the S462 diff against the newly tracked W21.P43 row and the failing S454 verification evidence. The root callback now performs wizard catalogue registration before returning from an already-open active bucket session, preserving the existing no-active-profile and bootstrap-exempt refusals. The cold-process regression now supplies the file secret-store backend and dev-test passphrase through `Settings`-backed environment names, so it verifies wizard registration instead of blocking on interactive passphrase input.

Status: no action required.

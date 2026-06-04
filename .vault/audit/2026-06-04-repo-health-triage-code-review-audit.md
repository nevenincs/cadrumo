---
tags:
  - '#audit'
  - '#repo-health-triage'
date: '2026-06-04'
related:
  - '[[2026-06-04-repo-health-triage-plan]]'
  - '[[2026-06-04-repo-health-triage-adr]]'
  - '[[2026-06-04-repo-health-triage-research]]'
---

# `repo-health-triage` Code Review

## W01-001 | HIGH | Public Drive service injection bypassed credential-owned construction

Status: remediated.

The W01 resolver change added a public `drive_service` keyword to
`resolve_document_link`, allowing callers to bypass credential-owned Google Drive
service construction. This conflicted with the minimal-scope resolver posture and
converted the test monkeypatch repair into a production test-double injection
surface.

Remediation removed the public service keyword from `resolve_document_link` and
restored `_download_drive_file` to always construct the Drive service from
credentials. Focused download behavior is covered through the private
`_download_drive_file_from_service` helper instead of the public API.

## W01-002 | MEDIUM | Corpus provenance step overstated relative import conversion

Status: remediated.

The checked W01 plan row claimed the corpus provenance test had been converted to
a relative import, but `src/aeat/_data/corpus` is a data-tree test location with
no package context. Turning the data tree into a package just to satisfy the row
would risk changing package-resource behavior.

Remediation updated the S03 plan action through `vaultspec-core vault plan step edit`
to describe the implemented behavior: remove the AST-visible absolute self-import
through the established `aeat.core.resources` boundary.

## W01-003 | LOW | Phase summaries lacked scoped command-output evidence

Status: remediated.

The W01 phase summaries listed verification commands but did not preserve concise
exit-code and result evidence, despite the ADR requiring scoped command output.

Remediation added focused evidence lines to the W01 phase summaries and corrected
the S10 step record to describe the post-review resolver contract.

## W02-001 | INFO | W02 type-control review found no actionable defects

Status: verified.

The W02 review found no findings and no remaining HIGH or CRITICAL issue. The
review checked the centralized counterpart source-kind subset, typed secure
repository payload accessors, sanitizer parse-error narrowing, narrow
import-linter test-helper exceptions, and W02 plan/exec/audit evidence.

The reviewer noted one non-blocking residual edge: a manually constructed invalid
revision with retired `invoice` source can be silently skipped by the resolver,
but production registry validation rejects that source before resolver use and
current production registry data does not contain `source = "invoice"` entries.

## W03-001 | LOW | Parallel plan step closure left S24 unchecked

Status: remediated.

The W03.P07 review found that `W03.P07.S24` was still unchecked while matching
execution and index records existed for the step. The root cause was a local
workflow error: S24, S25, and S26 were closed in parallel, and concurrent writes
to the same plan file lost the S24 update.

Remediation reran the S24 plan-step closure serially, regenerated the feature
index, removed the stale plan template annotation block, and reran VaultSpec
checks successfully. No HIGH or CRITICAL findings were reported for the W03.P07
code changes. The reviewer noted no behavioral regression in CLI command
registration, storage-session fixture direction, or the `work calculate` typed
boundary extraction.

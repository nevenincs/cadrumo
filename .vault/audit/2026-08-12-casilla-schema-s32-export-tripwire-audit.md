---
tags:
  - '#audit'
  - '#casilla-schema'
date: '2026-08-12'
modified: '2026-08-26'
body_schema: 'body-v1'
body_hash: 'sha256:d78035c810c9360c8559af6d403871a17755001ecb0354bae8fbb46e03d05170'
related:
  - "[[2026-08-10-casilla-schema-dead-surface-adr]]"
---
# `casilla-schema` audit: `S32 export post-write tripwire`

## Scope

Reviewed the accepted dead-surface decision, the complete draft-level export and verification module, the work-unit export orchestration, the S32 implementation diff, its real-byte regression tests, and the S32 execution record. The review covered write/verify ordering, registry-provider identity, closed-verdict enforcement, typed error registration and propagation, unreadable-file classification, receipt and event ordering, temporary-artifact cleanup, direct-draft artifact retention, parser singularity, recursion risk, and test honesty.

## Findings

No findings. Verdict: PASS.

`export_draft` atomically writes the payload, calls `_verify_written_export` with the same `RegistrySchemaAccessor`, and constructs no `DeclaracionExportResult` until `verify_export` returns `DeclaracionVerifyVerdict.MATCH`. Both `MISSING` and `DRIFT` raise the registered `FilingExportError`. The work-unit caller cannot emit `MODELO_EXPORTED` or return a receipt on that branch because `_write_export_tmp` must return before event construction; its existing typed-error handler removes the owned sibling `.tmp`. Direct draft export deliberately retains the failed artefact for inspection, matching the pre-existing ownership policy.

The verifier classifies an existing unreadable path as `MISSING` without leaking `OSError`. The implementation reuses the sole production `parse_export_payload` authority through `verify_export`; it adds no parser, recursive call, duplicate verifier, or dead public surface.

The incompatible-layout regression is non-tautological and uses no fake, mock, stub, patch, monkeypatch, skip, or mirrored parser. Its assembled `ExportLayoutDefinition` also passes a fresh production model-validation round trip. The production renderer writes its optional casilla-only record, the production parser refuses the unmatched trailing bytes, and the assertion invokes `export_draft` itself. Removing the new post-write invocation would make that test return a receipt and fail, so the invocation is load-bearing.

Focused evidence: four post-write verification tests passed; Ruff passed; BasedPyright reported zero errors, warnings, and notes; the error registry and S32 exec frontmatter/mapping were inspected. A broader Modelo 303 success-path probe failed before export during fixture construction because filing-instance evidence was absent. That failure does not exercise S32 and is not attributed to this change.

## Recommendations

Accept S32. Keep the unrelated Modelo 303 fixture failure with its owning test-data campaign; do not expand this step to repair it.

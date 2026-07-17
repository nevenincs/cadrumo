---
tags:
  - '#audit'
  - '#export-publication'
date: '2026-07-17'
modified: '2026-07-17'
related:
  - "[[2026-07-17-export-publication-plan]]"
  - "[[2026-07-17-export-publication-adr]]"
  - "[[2026-07-16-cli-authority-verb-conformance-duplication-authority-audit]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #audit) and one feature tag.
     Replace export-publication with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar]]'.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

# `export-publication` audit: `export durable-layer continuous-gate review`

## Scope

Continuous-gate review of the export-publication durable layer (`_bundle_export.py` and its recovery tests) landed by plan steps S01 through S06: the locked target serialization, the durable PREPARED state, the atomic replace with parent-directory fsync, and the fresh-process reconciliation of prepared exports. The review confirms the crash-window and secret-safety guarantees and flags the latent concurrency and audit-completeness gaps that step S07 (routing both CLI export doors through the service) turns live.

**Status: PASS.** Both crash windows proven, secret-safe, and a clean structural parallel to the reset journal. No Critical or High findings.

## Findings

### crash-window-durability | confirmed | Both PREPARED and replace crash windows are recovered honestly

The durable layer proves restrictive temporary-file permissions, same-target exclusion, every PREPARED and replace crash window, parent-directory durability, and fresh-process reconciliation without premature completion events. The recovery behaviour is a clean structural parallel to the reset journal.

### secret-safety-clean | confirmed | No sensitive-financial-data leaves secure storage

The export durable layer writes only the non-secret operation state outside the target artifact and keeps the target serialization locked; no sensitive-financial-data path is exposed.

### low-1-reconcile-lock-bypass | low | reconcile_prepared_exports can unlink a live staged temp, latent until S07

`reconcile_prepared_exports` does not hold the per-destination lock while it removes staged temporary files and deletes journal state. This is latent today but becomes live when S07 routes both the config profile export and the subject-access-request through the shared service: a reconcile running concurrently with a live same-target export could unlink the live staged temp and cause the export's `os.replace` to spuriously fail with a `ProfileExportError`. Remediation: either `reconcile_prepared_exports` holds the per-destination lock (or a repository lock spanning staged-temp removal plus journal delete) per operation, or the S07 call site guarantees reconcile runs only at exclusive startup. Enrolled as a gated requirement on S07 in the export-publication plan.

### low-2-dead-completed-enum | low | COMPLETED operation-state is declared but unwired, with doc drift

The COMPLETED operation-state enum member is declared but not reached by the current write path, and the surrounding documentation drifts from the implemented PREPARED-then-replace flow. It is either wired into the audit-completion posture (see the observation below) or removed with its docs corrected.

### observation-unaudited-post-replace-egress | observation | A crash after replace but before the audit event leaves a durably-published bundle with no PROFILE_EXPORTED event

A crash in the window after `os.replace` succeeds but before the `PROFILE_EXPORTED` audit event is emitted leaves a durably-published bundle with no corresponding audit record — an un-audited data-egress window. Privacy impact is limited: the bundle is a local file at the operator's own chosen path, not a remote transmission. The coordinator-recommended close is a three-phase journal (PREPARED, then replace plus fsync to COMPLETED, then emit the event; reconcile completes a COMPLETED-but-eventless operation), which also wires the dead COMPLETED enum from LOW-2. Enrolled as a tracked audit-completeness decision in the export-publication plan.

## Recommendations

Close LOW-1 by giving `reconcile_prepared_exports` the destination lock (or gating reconcile to exclusive startup) before S07 makes the race live; a test holding the destination lock must prove reconcile does not remove the live staged temp or raise a spurious `ProfileExportError`. Resolve LOW-2 and the post-replace-egress observation together via the three-phase journal so no durably-published bundle lacks a `PROFILE_EXPORTED` event after reconcile, retiring the dead COMPLETED enum in the same change. Both are enrolled as tracked steps on the export-publication plan; neither blocks the PASS verdict.

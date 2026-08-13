---
tags:
  - '#audit'
  - '#synced-history-consumption'
date: '2026-08-13'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:eec9d3280e36869dd32f1d9eebaf96b0766e929cc2a0f0539e688aff0fba2a4a'
related:
  - "[[2026-08-08-synced-history-consumption-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #audit) and one feature tag.
     Replace synced-history-consumption with a kebab-case feature tag, e.g. #foo-bar.
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

# `synced-history-consumption` audit: `S40 progress diagnostics remediation`

## Scope

Reviewed the uncommitted `P03.S40` remediation in `dev/docs/sequences/__main__.py`, `dev/docs/sequences/_runner.py`, `dev/docs/sequences/tests/test_cli.py`, the removal of `dev/docs/sequences/tests/test_progress_diagnostics.py`, and `dev/docs/tests/test_sequence_goldens.py`. The audit checks the plan's bounded, real-runner diagnostic requirement; CLI input validation; strict receipt validation; real-child page coherence; public/private test topology; duplicate test sites; and the no-test-double rule.

## Findings

### lifecycle-timeout-proof | high | The required public positive-receipt proof is red on the current tree

`TestBothSurfacesRedOnDivergence.test_bounded_check_reports_the_last_real_frame_before_expiry` assumes that a literal 20-second deadline falls after the first lifecycle frame starts and before the check ends. The current focused integration run instead completes through the ordinary golden-divergence path, so it emits no timeout receipt and the test fails. A direct public invocation at that deadline separately timed out before a frame receipt existed. The test correctly derives the reported frame from `discover_sequences` and `executed_frames` once a receipt exists, but its fixed timing premise is not derived and does not tolerate real scheduling variation. This leaves the P03.S40 gate unproven.

### progress-receipt-atomicity | medium | A supervisor can observe a torn or missing last-frame receipt

`_record_frame_progress` writes directly to the sole journal path. The supervisor kills a child on deadline and immediately parses the same file, so termination during the write can be reported as no recorded frame even when the frame has just started. That conflicts with the diagnostic's stated purpose of identifying the last actual frame under a bounded expiry. The remediation has strict parsing, but it cannot distinguish a malformed partial write from a child that never reached a frame.

### lifecycle-timeout-proof-resolution | low | Resolved: the public page-scoped receipt proof is green

The proof now derives the owning page from the enrolled lifecycle seed, discovers every production sequence on that page, invokes the public `check --page --timeout` route, and resolves the reported sequence and frame back against that discovered data. The exact integration test passed on the current tree in 35.11 seconds. It no longer assumes that a particular hard-coded sequence frame is always the one the supervisor observes.

### progress-receipt-atomicity-resolution | low | Resolved: receipt publication is atomic

`_record_frame_progress` now delegates to the canonical `atomic_write_best_effort_text` primitive, which stages a same-directory temporary file and publishes with `os.replace`. The parent therefore reads either a complete prior receipt, a complete current receipt, or no receipt; it cannot observe a partial JSON write produced by this runner.

### synthetic-private-probe | low | Resolved: the synthetic private-helper timeout probe has been removed

The deleted `test_progress_diagnostics.py` was the duplicate synthetic child that manually invoked private runner progress helpers. Its replacement drives the public check command for the lifecycle case and derives its expected locator and argv from discovered production sequence frames; no test double, patch, or copied runner business logic remains in this remediation scope.

### parser-and-receipt-contract | low | Resolved: invalid deadlines and malformed receipts are rejected strictly

`_positive_finite_timeout` rejects non-finite and non-positive CLI values at parsing time. `_SequenceProgressRecord` applies strict, frozen, no-extra receipt validation to the page, sequence id, frame coordinates, source, and argv. The focused integration tests passed all twelve selected cases, including `nan`, both infinities, zero, negatives, empty receipt components, and the real bounded-coherence child route. Direct model validation also rejected non-string, boolean-as-integer, and non-list receipt fields.

### timeout-proof-description | low | The test description still describes the superseded 20-second single-sequence proof

The proof now scopes a discovered owning page with a 30-second bound and accepts whichever discovered sequence and frame is actually executing. Its docstring still says that a twenty-second deadline expires after the first lifecycle overview frame, which is no longer the test's contract.

## Recommendations

1. `lifecycle-timeout-proof` is resolved by the page-scoped, production-discovered public proof. Retain this route and its discovered-frame assertions when the selected page evolves.

2. `progress-receipt-atomicity` is resolved by canonical atomic receipt publication. Keep the receipt outside golden data and retain the strict parsing boundary.

3. For `timeout-proof-description`, update the test docstring to describe the current page-scoped, discovery-derived contract and current bound.


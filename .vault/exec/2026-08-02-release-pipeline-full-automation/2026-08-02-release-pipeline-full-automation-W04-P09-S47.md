---
tags:
  - '#exec'
  - '#release-pipeline-full-automation'
date: '2026-08-02'
modified: '2026-08-02'
body_schema: 'body-v1'
body_hash: 'sha256:b5f7069cf62af1ff4f3776f9f14a081629f81915984aa9e74349f3a2b47e240e'
step_id: 'S47'
related:
  - "[[2026-08-02-release-pipeline-full-automation-plan]]"
---
# Pass the captured refusal text to the alert emitter at all four call sites

## Scope

- `.github/workflows/release-orchestrator.yml`
- `.github/workflows/release-soak-promoter.yml`
- `.github/workflows/publish-release.yml`
- `.github/workflows/docs-publish.yml`
- `dev/release/tests/test_release_alerting.py`

## Description

- Capture each failing or cancelled job's name and conclusion at every alert call site and pass it as `--detail`.
- Keep the docs publisher's own already-specific detail text.
- Add two tests: every invocation supplies a detail, and the rendered payload carries it.

## Outcome

16 passed in the alerting suite; 476 passed across the owned surface.

## Notes

Without a detail the emitter rendered its `(no detail captured)` placeholder on every alert, so the operator received a link and nothing else. That is a working alert channel delivering an empty message - the failure was not that alerting was absent but that it carried no information, which is harder to notice because the mechanism visibly fires.

The two assertions are deliberately paired: passing `--detail` and dropping it in the payload would satisfy the workflow-side check while delivering the same empty alert. The payload test also asserts the placeholder still appears when there genuinely is no detail, so an empty alert stays visibly empty rather than silently blank.

The capture is `|| true` and falls back to a placeholder, because an alert path that failed while collecting its own detail would take down the alert - the failure mode S29's exec record already names.

## Correction made during the work

My first pass at these blocks produced two real defects, caught by inspecting the written files rather than by trusting the edit. Line continuations collapsed, and the fallback rendered as `${{detail:-...}}`, which GitHub Actions parses as an EXPRESSION rather than shell parameter expansion - it would have failed at parse time or substituted an empty string. Rewritten without continuations and verified two ways: all four workflows parse as YAML, and each alert step's run body passes `bash -n`.

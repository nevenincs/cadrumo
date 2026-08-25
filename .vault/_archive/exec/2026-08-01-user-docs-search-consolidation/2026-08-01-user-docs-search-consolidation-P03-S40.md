---
tags:
  - '#exec'
  - '#user-docs-search-consolidation'
date: '2026-08-13'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:1fa7af093cf2fe12a1b17320f63c03711bb9a67b1c1a753dbc3d39173644e037'
step_id: 'S40'
related:
  - "[[2026-08-01-user-docs-search-consolidation-plan]]"
---

# Re-run the per-root multilingual recall probes against the deployed roots

## Scope

- `dev/docs/tests/`

## Description

- Establish, from a fresh personally-verified probe rather than an inherited record, whether this row is workable today.
- Record the deploy gate's current state as the formal deferral reference.

## Outcome

OPEN and correctly deferred. This row cannot be satisfied by any local run, by construction: it exists precisely so that a green CI pass can never stand in for a broken live root.

Re-probed 2026-08-13, read-only, no mutation. The apex answers 200 but is STALE, serving a build last modified 2026-07-12. Every root this row must probe answers 404: the English, Spanish, Catalan and Hungarian roots alike, confirmed on response headers rather than inferred from a cache artefact. So the deployed corpus this row measures does not exist yet.

## Notes

**The blocker narrowed materially today, and the narrowing is the useful finding.** Two technical preconditions that this campaign's records named repeatedly as standing are now both CLEAR, each verified directly rather than taken from the earlier entries:

- The API stub census reports the stub tree conformant with no drift. The 31 missing stubs recorded earlier the same day, owned by other campaigns, have been closed by their owners.
- The cloud session is valid and returns an identity. The credential that lapsed twice across earlier sessions is live.

What remains is therefore ONLY the deploy itself, which is an outward-facing action requiring operator authorisation and is outside an agent's authorisation regardless of how clear the preconditions are. No deploy, publish, upload, cache invalidation or cloud mutation was attempted, and none may be.

One thing an operator can now do that was impossible before this campaign's other rows landed: run the publisher's build-and-validate prefix offline, with no session and writing nothing outward, and get the complete pre-upload verdict in advance. That covers every root's artifact set, each root's own canonically-rooted sitemap, each root's record-bearing index, the apex's own search bundle, and an apex entry that reaches every built language. It stops at the upload, so it cannot answer this row's question, which is by design: the defect class this row exists to catch is a build that is correct while the deployment is not.

Ordered after the redeploy row. Nothing here may be recorded as satisfying it.

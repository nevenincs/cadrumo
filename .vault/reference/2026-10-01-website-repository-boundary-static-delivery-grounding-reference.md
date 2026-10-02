---
tags:
  - '#reference'
  - '#website-repository-boundary'
date: '2026-10-01'
modified: '2026-10-01'
body_schema: 'body-v2'
body_hash: 'sha256:98dbf0bf6658aad637d5119be640f9184f4d6dcf213c787c4de1dcd71eb72da6'
related:
  - "[[2026-09-27-website-repository-boundary-docs-static-delivery-adr]]"
---

# `website-repository-boundary` reference: `historical evidence for static documentation delivery`

## Summary

The accepted static-delivery decision rests on two account audits held in the
portfolio repository. This reference makes their Cadrumo findings discoverable
from this vault. It records observations from 2026-09-26 and 2026-09-27; no live
account, subscription, or delivery state was rechecked during this maintenance.
The findings are evidence for the original decision, not a new delivery ruling.

## Context

### Execution allowance and asset inventory

The 2026-09-26 audit observed HTTP 429 with error 1027 on both documentation
mounts while the control sites returned 200. Its subscription inventory showed
paid R2 and no paid Workers subscription. The measured Cadrumo release contained
69,745 objects, of which 61,622 were Pagefind files. The audit compared this
inventory with the then-documented 20,000-file allowance for Free static assets.
Those observations explain both removing request-time execution and separating
versioned search objects from the static page manifest. The inventory's largest
object was 23,966,312 bytes, below the then-documented 25 MiB object limit.

Source: `Y:/code/portfolio2026-worktrees/main/.vault/audit/2026-09-26-workers-audit-audit.md:22`
and `:36`. Its recorded body fingerprint is
`sha256:121f0efd263d5f77e2c0b53ac1dad46b8487b2376d0357056a88a7400d371579`.
The original API, inventory and HTTP captures are identified there under
`test-results/other-workers-audit/`; this reference does not claim to have
independently replayed those captures.

### Publication and recovery defects

The 2026-09-27 Cadrumo audit found that release-specific workflow concurrency
allowed different releases to compete for one active deployment. Rollback
checked only that an index existed, rather than proving the release complete.
Failed post-activation checks did not automatically restore the previous
pointer. These are the evidence for serialized publishers, complete manifests,
pre-activation verification and rollback after failed activation checks.

It also found an alert routine requiring issue-write permission while its job
granted only contents-read permission; executable routes extending beyond the
documentation mounts; incorrect mixed-precondition handling; and HTML responses
without useful validators. The audit kept browser-cache observations distinct
from proof of edge caching, and preserved the independently owned CloudFront
landing page. The decision's scoped transport, route, cache and alert corrections
follow those findings without authorizing unrelated origin or billing changes.

Source: `Y:/code/portfolio2026-worktrees/main/.vault/audit/2026-09-27-workers-audit-cadrumo-audit.md`,
findings `deployment-ordering`, `rollback-verification`, `failure-alerting`,
`routing`, `conditional-handling` and `html-validators`. Its recorded body
fingerprint is
`sha256:768d47d9bb4d7562d492c9edb0f91e69c0999e880536446380006f90ea8987da`.
Its raw captures are identified under `test-results/cadrumo-deployment-audit/`.

### Coverage limits

Both audit bodies were read for this reconciliation. Their dated observations
remain historical, and this pass does not establish present Cloudflare limits,
current production availability or rollout completion. The accepted decision's
status, commitments, authorization and supersession history are unchanged.

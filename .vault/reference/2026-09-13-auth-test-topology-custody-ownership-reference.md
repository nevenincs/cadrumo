---
tags:
  - '#reference'
  - '#auth-test-topology'
date: '2026-09-13'
modified: '2026-09-13'
body_schema: 'body-v2'
body_hash: 'sha256:ce2d8940e47eefb6503900c6ba9fc32c03ec8c9f690c1faa16354d39f94e64ce'
related: []
---

# `auth-test-topology` reference: `Auth test custody ownership`

The accepted live-auth decomposition keeps application auth responsible for
operator/session policy while persistence and outbound auth adapters own
encrypted storage and provider artefacts. The auth operator proofs under the
application test path directly construct profile workflow, bucket-event,
certificate-session, and draft repositories, so they are cross-layer
integration tests rather than inward unit tests. The accepted test-topology ADR
places those proofs under the narrowest persistence adapter test owner.

## Summary

The operator suite retains auth/session assertions but runs from
`cadrumo.adapters.persistence.profile.tests`, where its concrete profile,
workflow, event, and session fixtures are legal. The transaction-recovery suite
belongs beside it because every case proves durable conflict/recovery behavior.
Application probe and scope contracts remain application-owned; the relocated
tests use adapter-local, protocol-conforming fakes rather than reaching private
inward test helpers. No production compatibility surface or forwarding test
module is required.

---
tags:
  - '#research'
  - '#remote-telemetry'
date: '2026-07-10'
modified: '2026-07-15'
related:
  - "[[2026-07-04-remote-telemetry-adr]]"
---
# remote-telemetry research: warning closeout research grounding

## Question

Which existing decision record provides the necessary evidence grounding for the remote-telemetry feature?

## Findings

This curation bridge records that the governing decision has been reviewed for this feature. It introduces no implementation requirement and does not supersede the accepted decision. Its related metadata is the navigable connection from research to the existing ADR; the ADR's reciprocal relation makes the authority trail explicit.

### Preserved design evidence from the retired CLI wireframe

The superseded April CLI wireframe contained the first detailed exploration of
remote telemetry. The durable evidence is independent of that retired command
tree and is retained here so the wireframe corpus can be archived without
losing the rationale later ratified by the governing ADR:

- telemetry is local-first and performs no network transmission by default;
- remote emission requires explicit, revocable consent and a non-off tier;
- a closed `MetricSchema` registry declares the only counters and timings that
  may be sent remotely;
- the remote payload is an allowlist, not an arbitrary context dictionary plus
  a best-effort denylist;
- `workspace_hash` is pseudonymous and no tax identifier, amount, filename,
  message, or other operator content belongs in the remote payload;
- dry-run inspection and purge/revocation are part of the safety posture; and
- endpoint-side retention remains an operator/project obligation because a
  pseudonymous event can still be personal data.

The old wireframe also sketched retired `aeat configure` and `aeat advanced`
commands and a speculative endpoint deletion API. Those sketches are not
preserved as requirements. Current command ownership and implemented behavior
come only from the accepted remote-telemetry ADR and the live CLI/code surface.

## Recommendation

Keep this record as the evidence bridge for the accepted decision. Future
research that changes the decision should supersede this bridge rather than
silently reviving the retired wireframe or its command vocabulary.

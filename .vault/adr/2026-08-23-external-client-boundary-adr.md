---
tags:
  - "#adr"
  - "#external-client-boundary"
date: '2026-08-23'
related:
  - "[[2026-08-23-external-client-boundary-research]]"
supersedes:
  - '2026-06-30-agent-harness-adr'
  - '2026-07-01-agent-harness-adr'
  - '2026-07-02-agent-harness-refoundation-adr'
  - '2026-07-03-claude-ecosystem-packaging-adr'
  - '2026-07-16-distribution-harness-identity-adr'
  - '2026-07-18-mcpb-signing-publisher-adr'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:528d2651b43ae6f804ae22987a1bb996ee027405f810626c46540260ca8ec12f'
---
# `external-client-boundary` adr: `base product is client-blind` | (**status:** `accepted`)

## Problem Statement

The base Cadrumo product still contains policy, documentation, configuration, packaging, and release behavior for a separate external client even though the live CLI no longer implements `aeat app agent`. The conflict grounded in `2026-08-23-external-client-boundary-research` requires one authoritative dependency boundary.

## Considerations

- The base CLI and application must remain independently useful and releasable.
- External clients need stable, typed product capabilities but do not need the product to know their identity.
- The project forbids compatibility aliases and parallel implementations.
- Existing client-aware ADRs currently contradict the black-box boundary.

## Considered options

### Delete only the stale command documentation

Rejected. It repairs the immediate conformance failure but preserves client policy and release coupling in the base product.

### Rename client-specific surfaces as generic

Rejected where behavior remains client policy. Neutral vocabulary is valid only for capabilities genuinely owned and used by the base product.

### Make the base product client-blind

Accepted. The base owns protocol-neutral commands, result schemas, application services, and stable public contracts. Each external client owns its adapter, policies, configuration, telemetry, documentation, packaging, and release lifecycle.

## Constraints

- No `agent` command, alias, materializer, or deprecated compatibility path may exist under `aeat`.
- `src/cadrumo` must not import, name, configure, store state for, or enforce policy for `cadrumo-harness`, Claude, or another consuming client.
- A protocol-neutral contract may remain only when the base product itself uses and owns it; consumer exposure selection belongs outside the base package.
- External-client artifacts and credentials must not gate or ride inside the base product release cohort.
- Inverse gates must reject reintroduction of client commands, identifiers, artifacts, and publication steps.

## Implementation

Delete stale executable documentation and add a live grammar refusal for `app agent`. Move capability-manifest exposure policy into the harness package while the base retains only generic command and schema contracts. Remove client identity from base configuration, telemetry taxonomy, source prose, package metadata, distribution descriptors, cohorts, workflows, and release instructions. The separate client supplies its own documentation, installation, artifacts, destinations, and release authority.

## Rationale

Dependency inversion is the knockout criterion. A provider cannot remain independent when it owns policy or lifecycle for a consumer. The accepted option preserves reusable product contracts without giving the product knowledge of who consumes them, matching the evidence in `2026-08-23-external-client-boundary-research`.

## Consequences

The base product can build, test, package, and release without the external client. Client releases can evolve or fail independently. The harness must adapt to public base contracts and may need its own repository or release pipeline. Previously accepted client-aware materialization and publication decisions are superseded; no compatibility surface remains.

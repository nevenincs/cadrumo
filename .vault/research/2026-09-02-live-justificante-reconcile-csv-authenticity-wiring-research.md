---
tags:
  - '#research'
  - '#live-justificante-reconcile'
date: '2026-09-02'
modified: '2026-09-02'
body_schema: 'body-v2'
body_hash: 'sha256:ac46e0e9c327b329cc29bdeb8338fe14792817a19c8dc874d4d736352d183219'
related:
  - "[[2026-06-10-live-justificante-reconcile-adr]]"
---

# `live-justificante-reconcile` research: `wiring persisted CSV authenticity`

The unreachable `adapters/outbound/aeat/verify` package is a valid deferred capability, not removable code. The accepted justificante decision explicitly reserves a later increment that verifies captured CSV authenticity and stamps the persisted capture; the live pull path currently persists and binds a capture but never invokes that verifier. The missing increment needs an application-owned, capture-scoped persistence contract before any operator command can safely expose it.

## Findings

### The reachability finding is exact

The package collapse spans `verify/__init__.py` and `verify/contract.py`, both unreachable from shipped roots and used only by tests. The scanner will make both reachable when a real import of `verify.contract.verify_csv` lands, so no detector exception or synthetic root is justified.

### The verifier remains unique and security-bounded

`verify_csv` performs GET-only cotejo verification and has no replacement. Its tests cover malformed CSV refusal, iframe-to-CSV binding, hostile host and route rejection, session ownership and cleanup, POST refusal, and an opt-in live round trip (`src/cadrumo/adapters/outbound/aeat/verify/contract.py:181`). Deleting it would repeal a validated authenticity capability.

### Current capture stops before authenticity evidence

`app live justificante pull` live-gates the request, persists an encrypted `JustificanteCaptureSnapshot`, parses and registers metadata, and stamps filing evidence. It validates that the CSV belongs to the captured route but neither calls the public cotejo verifier nor persists an authenticity verdict. The existing `application.live.verify` service is limited to NIF-IVA and TGVI and is not a safe generic home.

### The governing ADR deliberately deferred this increment

The accepted `2026-06-10-live-justificante-reconcile-adr` names CSV authenticity through `verify_csv` as a later increment that stamps the persisted capture; its completed plan excluded that work. The present finding is therefore missing authorized follow-through, not accidental dead code.

### The smallest safe increment is capture-scoped

The evidence favors an application service that loads a persisted snapshot by bucket and snapshot identity, reuses its captured CSV, invokes the outbound verifier behind `require_live_read`, and persists an idempotent typed authenticity observation tied to that snapshot revision. A natural operator surface is `aeat app live justificante verify SNAPSHOT_ID`, but the ADR must choose the command and evidence schema. Direct CLI-to-adapter wiring would bypass persistence and application policy.

Acceptance must cover correct snapshot dispatch, malformed and unknown identities, verifier refusal, result persistence and idempotency, cross-bucket denial, command registration, and the opt-in real route.

## Sources

- `src/cadrumo/adapters/outbound/aeat/verify/contract.py:181`
- `src/cadrumo/application/live/justificante.py`
- `src/cadrumo/application/live/verify.py`
- `src/cadrumo/entrypoints/cli/_app_live_justificante_cli.py`
- `2026-06-10-live-justificante-reconcile-adr`

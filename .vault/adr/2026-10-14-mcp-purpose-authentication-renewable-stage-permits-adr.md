---
tags:
  - '#adr'
  - '#mcp-purpose-authentication'
date: '2026-10-14'
modified: '2026-10-14'
body_schema: 'body-v2'
body_hash: 'sha256:01f577425bea8529ebe4dadb87d1c5d8ecf9670f1b90de48aab2f5cae62a8c45'
related:
  - "[[2026-09-26-mcp-purpose-authentication-profile-access-adr]]"
  - "[[2026-10-07-modelo-runtime-performance-audit]]"
  - "[[2026-10-13-startup-performance-audit]]"
---
# `mcp-purpose-authentication` adr: `Renewable authority permits for executing operation stages` | (**status:** `rejected`)

This record proposes an amendment to accepted `2026-09-26-mcp-purpose-authentication-profile-access-adr`. That record's accepted text is unchanged until this proposal is approved.

## Problem Statement

Every executing stage of a registered operation, such as START or COMMIT, runs inside an authority permit the runtime grants the profile worker. The permit expires at the earlier of the lease's expiry and 30 seconds from its grant (`AUTHORITY_SECTION_MAXIMUM_SECONDS`, `src/cadrumo/application/runtime/worker_authorization.py:33`; `src/cadrumo/adapters/local_runtime/worker_authorization_lease.py:325-332`). A stage that has not released its permit by then is treated as an effect body of unknown state. The runtime contains it by ending the whole worker process (`src/cadrumo/adapters/local_runtime/worker_authorization.py:176-185`). Every other session and operation the worker holds ends with it, and the frontend receives `runtime_connection_closed` with effect unknown.

Legitimate stages exceed 30 seconds on a loaded host. Docs-sequence runs on 2026-10-14 lost workers this way: a filing-spine calculation START went silent after 17:01:19 and its channel closed 32.9 s into the exchange, and a modelo-303 COMMIT died between its `deferred_false_begin` and `deferred_false_end` phases. The worker logged nothing, because it was terminated. `2026-10-07-modelo-runtime-performance-audit` records an annual verification body of 21.5 s on an unloaded host. `2026-10-13-startup-performance-audit` forbids widening deadlines to make slow paths pass, so the fixed cap cannot simply grow.

## Considerations

- "Every executing stage needs newly admitted authority" and leases are at most five minutes, clipped to parent and grant (`2026-09-26-mcp-purpose-authentication-profile-access-adr`). A stage must keep proving current authority; it must not hold a permit indefinitely.
- Rule 00: ambiguous effects stay `UNKNOWN` or `SETTLING`; a timeout is not proof that a retry is safe; worker containment stays owned through settlement. Ending a worker mid-commit manufactures exactly that ambiguity.
- Rule 12: the supervisor guards irreversible effects; revocation, lock and sign-out must still stop new effects promptly.
- Only process containment proves an effect body in the worker has stopped (`src/cadrumo/adapters/local_runtime/worker_authorization.py:176-185`).
- A worker that is hung or dead must still be contained within a bounded time.

## Considered options

- **A. Renewable stage permits (proposed).** The worker renews the held permit at a fixed interval while the stage runs. Each renewal is re-admitted against current authority and clipped to the lease's expiry. A stage that does not renew in time is contained, as today. Long work proceeds while authority holds; revocation and hangs still end it within one renewal window.
- **B. Bound the section by the lease expiry alone (at most five minutes).** Rejected: it is a widening of the existing bound. Revocation, lock and sign-out could also take up to the lease's remainder to stop an effect body.
- **C. Derive the bound from the operation's declared deadline capability.** Rejected: most definitions declare `ABSENT`, so it gives them no bound. It also ties authority liveness to a scheduling declaration that is not about authority.
- **D. Keep the 30 s cap but contain only the expired stage.** Rejected: the effect body runs in the worker's process, and only containing that process proves it stopped. Stage-level containment would need a separate process per stage.

## Constraints

- A permit window never exceeds `AUTHORITY_SECTION_MAXIMUM_SECONDS` (30 s) from its grant or latest renewal, and never exceeds the lease's expiry. The fixed window is kept; only its renewal is new.
- A renewal is a fresh admission. The runtime re-checks the lease (live, unrevoked, not locked, binding and custody generation current) and the operation's access for the stage's action, exactly as at grant. A refused renewal ends the permit at once.
- The worker requests renewal no later than one third of the window before expiry, so 10 s into a 30 s window, and only while the stage's body has not returned.
- When a permit expires without renewal or release, the runtime contains the worker as today. A missing renewal is a hung or dead worker, not slow work.
- On revocation, lock or sign-out during a stage, the next renewal is refused. The stage then has no authority: the worker stops at its next authority boundary, and a stage that does not release within the remaining window is contained. A COMMIT already past its irreversible boundary keeps the existing cancellation-deferred rules; its outcome is recorded as the supervisor already records it, `UNKNOWN` when not proven.
- Renewal never extends a lease, a grant or a human sign-in; it only re-admits the stage within them.

## Implementation

We will make the worker's held authority permit renewable for the duration of an executing stage, under the constraints above. The permit protocol between the runtime's worker authorization server and the worker's operation authority gains a renewal exchange on the existing authority connection. The runtime handles it by re-running the stage's admission check and extending the permit's deadline to the new clipped window. The worker's authority lease renews from a timer while the stage body runs and stops renewing when the body returns or is cancelled. The 30 s constant, the containment path and the release path stay as they are. The renewal interval is a hypothesis to tune within the one-third rule.

## Rationale

Option A is the only one that both preserves "every executing stage needs newly admitted authority" and stops the runtime from ending healthy workers mid-commit. Authority is proven again every renewal interval, so revocation latency stays within the present 30 s window, and a hung or dead worker is still contained. The cost of a stage becomes bounded by authority, which is the property the ADR cares about, not by a wall-clock guess that `2026-10-13-startup-performance-audit` forbids widening. The evidence is the two worker deaths above and the 21.5 s unloaded body in `2026-10-07-modelo-runtime-performance-audit`.

## Consequences

- Long calculations, verifications and commits complete on a loaded host instead of ending their worker. Other sessions in the worker survive.
- The runtime performs one admission check per renewal interval per running stage. The check is cheap and serialized with existing authority work.
- The authority protocol gains a message, so the worker and the runtime must ship together; an older worker that never renews keeps today's behaviour.
- Reconsider if renewal admission becomes a contention point, or if stage bodies need isolation stronger than the shared worker process.

---
tags:
  - '#adr'
  - '#remote-telemetry'
date: '2026-07-04'
modified: '2026-07-15'
related:
  - "[[2026-06-10-llm-evidence-classification-adr]]"
  - '[[2026-07-10-remote-telemetry-research]]'
---

# `remote-telemetry` adr: `Default-off consent-gated remote telemetry payload allowlist` | (**status:** `accepted`)

## Problem Statement

Issue #407 (EPIC #392, "Kent can trust a hardened Kent-first CLI surface") specified a
full observability surface: local-only diagnostics (run-health, latency, errors,
llm-usage, JSONL sinks with retention) plus an *opt-in remote telemetry tier* so an
operator who wants to help improve the project can contribute anonymised usage signal.
The local-only half has landed across several prior slices (`c1096f98a6`, `7d836282`,
`824c0e5c28`, a follow-up `llm-usage` slice, and the `8e8498f6f` retention window). The
remote-telemetry tier is the one remaining piece of #407's original scope and is the
single most safety-sensitive item in the whole issue: it is the only surface in this
project whose entire purpose is to transmit data off the operator's host.

Every other telemetry primitive already built (`LLMRunTelemetryRecorder`,
`ToolCallTelemetryRecord`, the `core.observability` run-trace sinks) is local-only by
construction — encrypted secure storage or a local JSONL file, never a network call. A
remote tier inverts that invariant for a narrow, explicitly-scoped slice of data, so it
must be designed so that inversion cannot silently widen: the payload contents must be
constrained by a structural allowlist, not by a reviewer remembering to scrub a denylist
of forbidden fields.

This ADR decides the shape of the remote-telemetry consent gate, the payload contract,
and the boundary between "safe to build now" (the gate, the schema, the scrub, a local
no-op sink) and "deferred" (an actual network transport). It also records why the
transport itself is deliberately NOT part of this first slice.

## Considerations

- **`sensitive-financial-data-secure-storage-only`** (project rule): sensitive
  financial data never leaves secure storage, full stop. Telemetry must never touch
  this category of data at all — not "redact it before sending", but "never read it
  into the telemetry payload in the first place".
- **The `llm-evidence-classification` off-host consent precedent**
  (`2026-06-10-llm-evidence-classification-adr`,
  `src/aeat/application/ledger/_evidence_input.py`): the codebase already has exactly
  one off-host-transmission gate, `cloud_evidence_read_permitted`. Its shape —
  default-off deployment flag, gestor-mode absolute bar, per-invocation
  (never-sticky) acknowledgement, single resolver function — is the template this ADR
  reuses rather than re-inventing a second off-host gate with different semantics.
- **The preserved telemetry design evidence** in
  `2026-07-10-remote-telemetry-research` already worked out most of
  the shape Kent needs: a closed `MetricSchema` registry (`counters` /
  `timings_ms`, each entry declaring `remote_allowed: bool`), a `telemetry_tier`
  (`off` / `crash_only` / `full`), an explicit `telemetry_endpoint`, dual-pass
  scrubbing (a stricter remote pass beyond the local scrubber that drops
  `profile_tax_id` / `message` / `context` entirely and replaces `profile_id` with a
  `workspace_hash` pseudonym), an outbox with dry-run/purge, and full consent
  reversibility. This ADR ratifies that shape as the target design and narrows the
  first implementation slice to the part that is safe to ship without a live network
  path: the consent gate, the schema-registry allowlist, and the scrub.
- **`Settings` is the existing central-config surface** (`aeat-schema-central-config`):
  every existing off-host/consent-adjacent flag (`aeat_evidence_cloud_upload_permitted`,
  `aeat_evidence_gestor_mode`) is a typed `pydantic` field on `Settings`. Telemetry
  posture belongs there too, not as an ad-hoc env-var read scattered through call
  sites.
- **No existing production module implements any part of the remote tier.**
  `core.observability` is a deterministic replay/audit-trail substrate for testing, not
  a telemetry pipeline; the `entrypoints/mcp/_telemetry.py` session-trajectory recorder
  is local-only and payload-free by design and is a sibling pattern, not a dependency.
  This is a from-scratch build.

## Considered options

- **A. Ship the full wireframe design in one slice (schema registry + tiers + dual-pass
  scrub + outbox + real HTTP transport).** Rejected as the first slice: the transport is
  the highest-risk, hardest-to-verify-safe component (an actual outbound network call
  carrying operator data), and building it before the gate and scrub are hardened and
  reviewed risks shipping a real transmission path behind an under-tested allowlist.
  The full design remains the target; it is sequenced, not abandoned.
- **B. Denylist-based scrubbing (reuse the existing `redact_structured` / AUDIT rule set
  verbatim on an arbitrary telemetry payload).** Rejected: a denylist scrubs *known*
  sensitive shapes (NIF regex, bearer-token regex, URL host-only) out of an
  otherwise-unconstrained payload. A future telemetry emit site that adds a new field
  (e.g. `description=transaction.description`) ships silently unless someone remembers
  its content matches no existing regex. The safety invariant this ADR needs is
  structural: a field not on the allowlist cannot be transmitted, regardless of its
  content shape.
- **C (chosen). Allowlist-typed payload with a closed metric-key registry, ANDed
  consent gate, and structural exclusion of the whole request/data domain (no
  transaction fields, no NIF, no filenames, no free text) from the payload type itself.**
  The payload model's fields are the entire allowlist; there is no `extra` field, no
  `context: dict[str, Any]` passthrough, and no string field wide enough to carry
  operator-supplied content. A field can only be added to the schema through an
  explicit code change (and, per the wireframe design, an ADR amendment for a new
  metric key), which is the same "closed set changes require an authored decision"
  discipline the project already applies to enums and registry values.
- **D. Route telemetry consent through `ServiceCapability`
  (`resolve_active_capability`).** Considered and deferred: `ServiceCapability` models
  a per-profile opt-in for an external SERVICE the app actively depends on (cloud
  evidence upload, vision, Sheets export) resolved via `resolve_active_capability` and
  gated by the gestor-mode floor. Telemetry is closer to a deployment-wide posture
  (Kent's wireframe walk sets it via `aeat configure defaults set telemetry_opt_in`,
  not a per-profile capability toggle) and has no meaningful per-profile narrowing
  semantics distinct from the deployment flag — a future revision MAY promote it to a
  `ServiceCapability` member once the profile-level use case is concrete, but this ADR
  keeps it as `Settings` fields plus a dedicated resolver mirroring
  `cloud_evidence_read_permitted`'s shape, not the capability resolver itself.

## Constraints

- No live network transport ships in this slice. The transport (the actual HTTP POST to
  `telemetry_endpoint`) is explicitly deferred; this ADR's implementation covers only
  the gate, the schema, the scrub, and a local no-op/file sink that proves the payload
  the transport would eventually send is already safe.
- The metric-key registry MUST be closed and validated at construction: an emitted
  counter/timing whose key is not registered for its command MUST fail loudly in
  development/test builds (never silently drop and never silently widen).
- The consent posture MUST compose with the existing gestor-mode absolute bar
  (`aeat_evidence_gestor_mode` is evidence-specific; telemetry gets its own
  `aeat_telemetry_gestor_mode`-equivalent bar per the same "categorical, cannot be
  narrowed away" shape) — a gestor/professional deployment must never transmit
  telemetry regardless of the deployment flag or any per-invocation acknowledgement.
- The payload allowlist MUST be provable by a structural test, not a documentation
  claim: a test must attempt to construct a payload carrying a financial/identity-shaped
  field and observe a `pydantic` validation failure (unknown field rejected), not merely
  assert that a specific known-bad value gets redacted.

## Implementation

Four pieces land in this slice, all under `src/aeat/core/telemetry/` (a new package,
sibling to `core/observability/`, `core/classification/`, `core/redaction/`):

1. **Settings fields.** `Settings` gains `aeat_telemetry_opt_in: bool = False`,
   `aeat_telemetry_gestor_mode: bool = False`, and `aeat_telemetry_tier:
   TelemetryTier = TelemetryTier.OFF` (a `StrEnum` with members `OFF`, `CRASH_ONLY`,
   `FULL`, declared in `core/telemetry/_tier.py` per
   `aeat-architecture-boundaries`'s closed-value-set discipline). All three default to
   the fully-inert posture. A future `aeat_telemetry_endpoint: str | None = None` field
   is scaffolded but is not read by anything in this slice (no transport exists yet to
   read it).

2. **The consent resolver.** `telemetry_emit_permitted(settings: Settings, *,
   acknowledged: bool) -> bool` in `core/telemetry/_consent.py`, mirroring
   `cloud_evidence_read_permitted`'s exact shape: gestor mode bars absolutely first;
   then `aeat_telemetry_opt_in` must be `True`; then `aeat_telemetry_tier` must not be
   `OFF`; then the per-invocation `acknowledged` flag must be `True` (never sticky,
   re-affirmed every call site the same way the evidence gate is). All four conditions
   AND together; any `False` refuses.

3. **The metric schema registry and the allowlisted payload.** `core/telemetry/
   _schema.py` declares `MetricSchema` (command dotted-path, `counters: Mapping[str,
   CounterSpec]`, `timings_ms: Mapping[str, TimingSpec]`, each spec carrying
   `remote_allowed: bool`) as a closed, code-authored registry
   (`TELEMETRY_METRIC_REGISTRY: Mapping[str, MetricSchema]`), and
   `TelemetryEventPayload` — the one and only shape a telemetry emission can take.
   `TelemetryEventPayload` is a `pydantic` `BaseModel` with `model_config =
   STRICT_FROZEN_CONFIG` (`extra="forbid"`) and EXACTLY these fields: `schema_version`,
   `workspace_hash` (a stable SHA-256 pseudonym derived from a random local instance
   id, never the profile NIF/id), `command` (the dotted metric-schema key, validated
   against the registry), `counters: Mapping[str, int]`, `timings_ms: Mapping[str,
   int]`, `succeeded: bool`, `error_kind: str | None` (a closed short label, not free
   exception text), `captured_at`. There is no `message`, no `context`, no `path`, no
   `description`, no arbitrary string field wide enough to carry operator content —
   the allowlist IS the type. A constructor helper `build_telemetry_payload(...)`
   validates every counter/timing key against the schema for the given `command` and
   drops (never raises past the boundary, but logs loudly in dev) any key whose spec
   sets `remote_allowed=False`, so an existing local-only metric can be registered
   without becoming remote-eligible by default.

4. **The scrub-proof local sink.** `emit_telemetry_event(payload, *, settings, sink=None)`
   in `core/telemetry/_emit.py` is the single call site every future producer uses. It
   (a) calls `telemetry_emit_permitted`; when refused, it is a pure no-op — nothing is
   written, nothing is sent; (b) when permitted, hands the already-allowlisted
   `TelemetryEventPayload` to a `TelemetrySink` protocol. The only sink implemented in
   this slice is `LocalNoopTelemetrySink` (or, if a durable proof-of-shape is useful, a
   local JSONL "outbox" file under the existing local-storage-root convention) —
   deliberately NOT a network client. Building the real HTTP sink is explicitly the
   next slice, gated on this one landing and being reviewed.

The CLI surface (`aeat configure defaults set telemetry_opt_in/telemetry_tier`, `aeat
advanced diagnostics telemetry flush --dry-run`) and locale strings are deferred to the
follow-up slice per this session's scope note; this slice is core-only.

## Rationale

The companion research (`2026-07-10-remote-telemetry-research`) preserves the target
shape evidence (the `MetricSchema` registry, the consent posture, and the
dual-pass-scrub hardening rules) without retaining the superseded CLI wireframe.
Re-deriving the design from scratch would ignore existing, reviewed intent. What that
earlier exploration did not resolve — and what caused #407
to stay open through five local-only slices without ever reaching the remote tier — is
sequencing: the remote tier is the one part of the whole issue where a mistake ships
data off the operator's machine, and the project's own safety rules
(`sensitive-financial-data-secure-storage-only`, the `off-host-evidence-upload-requires-
explicit-consent-gate` precedent codified from `2026-06-10-llm-evidence-classification-
adr`) both say the same thing: build the boundary first, prove it structurally, and add
the actual transmission mechanism last and separately.

Reusing `cloud_evidence_read_permitted`'s exact resolver shape (gestor-bar → deployment
flag → per-invocation acknowledgement, ANDed, never sticky) rather than inventing a new
consent vocabulary keeps the codebase's off-host gates uniform: an auditor who has
verified one gate's shape recognises the other immediately. Modelling the payload as a
`pydantic` model with `extra="forbid"` and a hand-curated, deliberately narrow field set
— rather than as a `dict` scrubbed by regex — is what makes "a sensitive field cannot
reach the payload" a property the type checker and a construction-time test enforce,
not a property a reviewer has to notice is missing from a denylist.

## Consequences

- #407's remaining scope narrows from "the entire remote-telemetry tier" to "wire a real
  HTTP sink behind the now-existing gate + schema + scrub", which is a much smaller,
  independently reviewable follow-up.
- Any future producer that wants to emit a remote-eligible metric must register it in
  `TELEMETRY_METRIC_REGISTRY` first — a deliberate, greppable, ADR-amendable step, not a
  silent code change. This mirrors the existing `no-dormant-source-resolvers` /
  closed-registry discipline elsewhere in the codebase.
- Local-only metrics (the existing `LLMRunTelemetryRecorder`, the MCP
  `ToolCallTelemetryRecord`) are untouched by this ADR; nothing about them becomes
  remote-eligible by this change, and nothing in this slice reads from them — the
  telemetry package introduced here is deliberately empty of producers until the follow-
  up wires real emit call sites.
- The CLI verbs and locale strings promised by the wireframe (`telemetry status/opt-in/
  tier`, `diagnostics telemetry flush --dry-run`) remain open follow-up work; #407
  stays open pending them and the real transport.
- Risk carried forward: because no transport exists yet, this slice cannot be
  fully end-to-end proven against a live remote endpoint. The compensating control is
  that the structural allowlist and consent gate are provable in isolation (no network
  dependency needed to prove they hold), and the transport slice inherits an
  already-hardened boundary rather than needing to invent its own scrubbing on the way
  out the door.

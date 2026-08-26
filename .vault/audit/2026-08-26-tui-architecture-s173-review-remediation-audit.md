---
tags:
  - '#audit'
  - '#tui-architecture'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v1'
body_hash: 'sha256:cb2867b277f6c81a05e244a11a6d8954a6192c05403d226c2e4f36aeef40729d'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
  - "[[2026-08-11-tui-architecture-adr]]"
  - "[[2026-08-26-tui-architecture-s173-authority-remediation-audit]]"
---

# `tui-architecture` audit: `S173 independent review remediation`

## Scope

Follow-up remediation of the independent S173 review failure. Scope is limited
to public capture/current-coordinate introspection exposure and the missing
source-root-only domain proof. S173 remains open pending the prerequisite S175
review and final independent re-review.

## Findings

### public-dto-process-binding | low | CLOSED: coordinate values expose only opaque contract fields

`RegistryAuthorityCapture` now has exactly `projection`, `comparison_domain`,
and `generation` dataclass fields. `RegistryAuthorityCurrentCoordinate` has
exactly `comparison_domain` and `generation`. Neither dataclass stores roots,
PID, nonce, bytes, or a private binding field, so `dataclasses.fields` and
`dataclasses.asdict` expose only the documented opaque contract.

Inherited-process refusal remains authoritative outside the DTOs. The authority
owner records only minted opaque `ContentDigest` domains in process-local
internal state. The after-fork/PID reconstruction clears that state before a
child load; inherited values therefore refuse because their domain was not
minted in the child. A fresh child load mints a nonce-bound child domain.

### source-root-domain | low | CLOSED: source-root-only mismatch is independently proved

The focused native-capture suite now holds the registry root constant, selects a
distinct physical source root, derives that exact pair's opaque domain, and
proves equal-looking generation integers refuse on domain mismatch. This is
separate from the existing distinct-registry-root proof.

## Recommendations

Run the final independent S173 review after S175 is cleared. Preserve the
field-exact public DTO tests and process-local opaque-domain registry; do not
restore a dataclass field carrying process internals or a raw generation API.

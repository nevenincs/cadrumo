---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v2'
body_hash: 'sha256:4deacfed5be14cfe1c1107bf712a061039acc35727030e15d669025ad7251865'
step_id: 'S176'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Hard-move the remote-read host authority to the core defining module and eliminate the registry aeat_hosts surface

## Scope

- `src/cadrumo/domain/calculations/registry/aeat_hosts.py and src/cadrumo/core/remote_authority.py`

## Changes

- `M` `.vault/plan/2026-08-11-tui-architecture-plan.md`
- `verify:` `uv run --no-sync pytest src/cadrumo/domain/calculations/registry/tests/test_remote_authority_canonicalisation.py src/cadrumo/adapters/outbound/aeat/auth/tests/test_clave_landing_authority.py -n0` -> `pass`

## Notes

No source change was needed: the hard move landed under commit c1cff6b325.
Verified at HEAD rather than assumed - the registry aeat_hosts module is
absent, core/remote_authority.py owns REMOTE_READ_SCHEME and
canonical_remote_hostname, every consumer (both clave auth adapters, the
registry remote-state guard, and the tests) imports from that defining module,
and the shipped zero-remnant test already proves the retired module does not
import and the registry package binds neither symbol. This record closes the
plan row against the delivered code.

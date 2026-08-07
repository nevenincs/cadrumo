---
tags:
  - '#exec'
  - '#history-onboarding'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:c75b404ed2eeb61fe4df27664ef2f79771b2531701d66b373302fa2ca8993b13'
step_id: 'S04'
related:
  - "[[2026-08-07-history-onboarding-plan]]"
---

# add the aeat app live filed discover verb emitting the availability report as the envelope result plus the live-scope caveat Notice, verified by test_documented_command_conformance.py and a new JSON-schema conformance case

## Scope

- `src/cadrumo/entrypoints/cli/_app_live.py`

## Description

- Add the `filed discover` verb emitting the tagged union report plus the live-scope caveat notices.
- Add the registered discover result schema and its per-pair payload.
- Land real es, en, ca and hu values for the three new keys through the locale CLI.
- Add the conformance and notice-behaviour tests.

## Outcome

The payload separates the two signals rather than reporting one pair count,
because only the profile-derived count supports a completeness claim. Each pair
carries its signal set AND the derived anomaly flag, so a consumer of the JSON
does not reimplement the asymmetry rule.

Two notices, for two different misreadings. The register-scope caveat is
unconditional, because what the option list establishes does not depend on how
many register-only pairs came back. The second is a WARNING that fires only when
the report carries no taxpayer-specific denominator at all -- the case where the
pair count most looks like coverage and is not.

A missing profile downgrades the report rather than refusing the verb, since the
register read needs no profile; the warning is what stops the downgrade from
reading as a complete answer. The verb is deliberately NOT enrolled in the
profile-bound write allowlist: it is read-only and persists nothing.

## Verification

    uv run --no-sync pytest src/cadrumo/entrypoints/cli/tests/test_app_live_filed_discover.py -q -n 0
    12 passed in 5.48s

    uv run --no-sync pytest src/cadrumo/entrypoints/cli/tests/test_documented_command_conformance.py src/cadrumo/entrypoints/cli/tests/test_json_schema_conformance.py -q -n 0 -m "unit or integration"
    515 passed, 1 warning in 39.59s

## Notes

The envelope round-trip and no-bespoke-notice-field cases are written out
EXPLICITLY in the new test module rather than left to the shared parametrised
gates, and the reason is a pre-existing gap worth reporting. Those gates
parametrise over the schema registry as populated at COLLECTION time, and the
conformance module imports only the config payload modules -- so the entire
`app.*` schema family, including the two already-shipped `filed` verbs, never
reaches them. Collection was measured: 73 parametrised cases, all config or root,
zero app. Relying on them here would have been a green that never ran. Enrolling
the live payload module would sweep roughly 31 schemas into two gates at once and
is outside this row.

The locale keys were landed through the locale CLI in all four catalogues with
real translations. The catalogues carry heavy concurrent peer writes and were
transiently YAML-invalid mid-run; the keys were later confirmed present in HEAD
in all four with the authored values, swept in by a peer commit, so nothing was
re-committed. A HEAD-anchored own-only blob was prepared as a fallback and
discarded once HEAD was confirmed correct, because re-applying it would have
reflowed a peer's neighbouring Catalan string.

Source landed in the peer sweep `24f8fd9add`; content verified byte-identical.
